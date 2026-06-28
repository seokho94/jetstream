"""Build the live board from real GDELT data (Phase 1 momentum).

For each seeded current: pull a daily volume timeline + source breadth from GDELT
(keyword rules), compute the 4 momentum signals + within-current state, then
cross-current normalize → score → rank, write momentum_point rows, and publish a
board_view. The API serves this board_view when present.

Prereq: `docker compose up -d` (DB with schema + seeded currents).
Run:     python -m scripts.build_board
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time

import psycopg
from psycopg.types.json import Json

from pipeline.cluster.rules import CURRENT_QUERIES
from pipeline.ingest.gdelt import source_breadth, volume_timeline
from pipeline.momentum import rank, signals_for

DSN = os.environ.get("DATABASE_URL", "postgresql://meridian:meridian@localhost:5432/meridian")
STATE_KO = {"rising": "상승", "peaking": "정점", "cooling": "냉각", "steady": "안정"}


def _minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    return [(v - lo) / (hi - lo) if hi > lo else 0.5 for v in vals]


def _weekly(series: list[tuple[str, int]], n: int = 8) -> list[tuple[str, int]]:
    """Daily (date, count) → last n ISO-week sums [(YYYY-Www, sum)]."""
    buckets: dict[str, int] = {}
    for d, c in series:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        buckets.setdefault(f"{y}-W{w:02d}", 0)
        buckets[f"{y}-W{w:02d}"] += c
    return sorted(buckets.items())[-n:]


GDELT_GAP = 5.0  # seconds between GDELT calls (avoid 429)


def collect() -> list[dict]:
    """Fetch + score each current. Two passes so the critical timelines go first
    (when the rate budget is freshest); breadth is best-effort (spread=0 on fail)."""
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, color_key FROM current WHERE status='active' ORDER BY id")
        currents = [(cid, name, ck) for cid, name, ck in cur.fetchall() if CURRENT_QUERIES.get(cid)]

    # Pass A — daily volume timelines (critical).
    series_by: dict[str, list[tuple[str, int]]] = {}
    for cid, _name, _ck in currents:
        try:
            s = volume_timeline(CURRENT_QUERIES[cid], timespan="10w")
            if s:
                series_by[cid] = s
            else:
                print(f"  ! {cid}: empty series")
        except Exception as e:
            print(f"  ! {cid}: GDELT timeline failed ({e})")
        time.sleep(GDELT_GAP)

    # Pass B — source breadth for spread (best-effort; only for currents we kept).
    breadth_by: dict[str, tuple[int, int]] = {}
    for cid in series_by:
        try:
            breadth_by[cid] = source_breadth(CURRENT_QUERIES[cid])
        except Exception as e:
            breadth_by[cid] = (0, 0)
            print(f"  ~ {cid}: spread unavailable ({e}); using 0")
        time.sleep(GDELT_GAP)

    out: list[dict] = []
    for cid, name, color_key in currents:
        if cid not in series_by:
            continue
        series = series_by[cid]
        outlets, countries = breadth_by.get(cid, (0, 0))
        sig = signals_for(series, spread_outlets=outlets, spread_countries=countries)
        out.append({"id": cid, "name": name, "color_key": color_key, "series": series, "sig": sig})
        print(
            f"  · {cid:<15} state={sig['state']:<8} rel={sig['rel_trend']:<8} "
            f"vol={sig['volume']:<9} persist={sig['persistence_days']}d spread={outlets}out/{countries}ctry"
        )
    return out


def publish(results: list[dict]) -> None:
    """Upsert this run's momentum_point, then derive board_view from the FULL
    momentum_point store (robust to partial GDELT runs; re-running refreshes)."""
    series_map = {r["id"]: r["series"] for r in results}
    now = dt.datetime.now(dt.timezone.utc)

    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        # 1) upsert this run's momentum_point rows (score filled after ranking)
        for r in results:
            s = r["sig"]
            last_date = dt.date.fromisoformat(r["series"][-1][0])
            cur.execute(
                """
                INSERT INTO momentum_point
                  (current_id, t, volume, persistence_days, spread, spread_outlets,
                   spread_countries, accel_d1, accel_d2, baseline_median, baseline_mad,
                   score, state, tau_state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s)
                ON CONFLICT (current_id, t) DO UPDATE SET
                  volume=EXCLUDED.volume, persistence_days=EXCLUDED.persistence_days,
                  spread=EXCLUDED.spread, spread_outlets=EXCLUDED.spread_outlets,
                  spread_countries=EXCLUDED.spread_countries, accel_d1=EXCLUDED.accel_d1,
                  accel_d2=EXCLUDED.accel_d2, baseline_median=EXCLUDED.baseline_median,
                  baseline_mad=EXCLUDED.baseline_mad, state=EXCLUDED.state, tau_state=EXCLUDED.tau_state
                """,
                (
                    r["id"], last_date, s["volume"], s["persistence_days"], s["spread"],
                    s["spread_outlets"], s["spread_countries"], s["accel_d1"], s["accel_d2"],
                    s["baseline_median"], s["baseline_mad"], s["state"], s["tau_state"],
                ),
            )

        # 2) read the latest momentum_point per current (full cohort) + meta
        cur.execute(
            """
            SELECT DISTINCT ON (mp.current_id) mp.current_id, c.name, c.color_key,
                   mp.volume, mp.persistence_days, mp.spread, mp.accel_d1, mp.state, mp.baseline_median
            FROM momentum_point mp JOIN current c ON c.id = mp.current_id
            WHERE c.status='active'
            ORDER BY mp.current_id, mp.t DESC
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("no momentum_point rows — board_view not updated")
            return

        items = [
            {
                "id": r[0], "name": r[1], "color_key": r[2], "state": r[7],
                "_raw": {
                    "volume": float(r[3]), "persist": float(r[4]), "spread": float(r[5]),
                    "accel": float(r[6]) / (float(r[8]) + 1e-6),  # relative slope (size-free)
                },
            }
            for r in rows
        ]
        rank(items)  # cross-current score + rank
        by_rank = sorted(items, key=lambda it: it["rank"])
        attn = dict(zip([it["id"] for it in items], _minmax([it["score"] for it in items])))

        # 3) write the cross-cohort score back to momentum_point (latest row per current)
        for it in items:
            cur.execute(
                "UPDATE momentum_point SET score=%s WHERE current_id=%s "
                "AND t=(SELECT max(t) FROM momentum_point WHERE current_id=%s)",
                (it["score"], it["id"], it["id"]),
            )

        ranked = []
        for it in by_rank:
            sm = series_map.get(it["id"])
            spark = [round(v, 3) for v in _minmax([c for _, c in sm][-10:])] if sm else [0.5] * 8
            ranked.append(
                {
                    "currentId": it["id"], "name": it["name"], "colorKey": it["color_key"],
                    "rank": it["rank"], "state": it["state"], "score": it["score"],
                    "sparkline": spark, "attention": round(attn[it["id"]], 3),
                }
            )
        streamgraph = [
            {
                "currentId": it["id"], "colorKey": it["color_key"],
                "series": [{"t": wk, "share": s} for wk, s in _weekly(series_map[it["id"]])],
            }
            for it in by_rank
            if it["id"] in series_map
        ]
        top = by_rank[0]
        todays_read = {
            "paragraph": (
                f"이번 집계에서 {top['name']}이(가) 모멘텀 1위입니다 — {STATE_KO[top['state']]}. "
                f"흐름간 정규화(4신호 가중) 기반 실데이터 순위이며, 합성 브리핑은 다음 단계입니다."
            ),
            "asOf": now.isoformat(),
        }
        stats = {
            "currentsTracked": len(items),
            "newThreads": 0,
            "storiesScanned": sum(c for sm in series_map.values() for _, c in sm),
        }
        etag = "sha-" + hashlib.sha1(json.dumps(ranked, sort_keys=True).encode()).hexdigest()[:12]

        cur.execute("UPDATE board_view SET is_current=false WHERE is_current")
        cur.execute(
            """
            INSERT INTO board_view (as_of, generated_at, todays_read, streamgraph, ranked, stats, is_current, etag)
            VALUES (%s,%s,%s,%s,%s,%s,true,%s)
            """,
            (now, now, Json(todays_read), Json(streamgraph), Json(ranked), Json(stats), etag),
        )
        conn.commit()

    states = ", ".join(f"{it['name']}={it['state']}" for it in by_rank)
    print(f"published board_view (etag {etag}) · {len(items)} currents · top={top['name']} ({top['state']})")
    print(f"  states: {states}")


def main() -> None:
    print("[build_board] collecting GDELT volume timelines + breadth …")
    results = collect()
    publish(results)


if __name__ == "__main__":
    main()
