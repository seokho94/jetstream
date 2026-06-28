"""Build the live board from real GDELT data (Phase 0 thin slice).

For each seeded current: pull a daily volume timeline from GDELT (keyword rules),
run momentum v0, write a momentum_point, then rank by score and publish a
board_view row. The API serves this board_view when present.

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
from pipeline.ingest.gdelt import volume_timeline
from pipeline.momentum.v0 import momentum_v0

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
    items = sorted(buckets.items())
    return items[-n:]


def collect() -> list[dict]:
    """Fetch + score each current. Returns list of per-current result dicts."""
    out: list[dict] = []
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, color_key FROM current WHERE status='active' ORDER BY id")
        currents = cur.fetchall()

    for cid, name, color_key in currents:
        query = CURRENT_QUERIES.get(cid)
        if not query:
            print(f"  - {cid}: no rule, skipped")
            continue
        try:
            series = volume_timeline(query, timespan="10w")
        except Exception as e:  # GDELT outage / throttle → skip this current
            print(f"  ! {cid}: GDELT failed ({e})")
            continue
        if not series:
            print(f"  ! {cid}: empty series")
            continue
        counts = [c for _, c in series]
        m = momentum_v0(counts)
        out.append({"id": cid, "name": name, "color_key": color_key, "series": series, "m": m})
        print(f"  · {cid:<15} state={m['state']:<8} vol={m['volume']:<8} persist={m['persistence_days']}d days={len(series)}")
        time.sleep(1)  # be polite to GDELT
    return out


def publish(results: list[dict]) -> None:
    if not results:
        print("no results — board_view not updated")
        return

    scores = [r["m"]["score"] for r in results]
    attn = dict(zip([r["id"] for r in results], _minmax(scores)))
    ranked_sorted = sorted(results, key=lambda r: r["m"]["score"], reverse=True)

    ranked = [
        {
            "currentId": r["id"], "name": r["name"], "colorKey": r["color_key"],
            "rank": i + 1, "state": r["m"]["state"], "score": round(r["m"]["score"], 3),
            "sparkline": [round(v, 3) for v in _minmax([c for _, c in r["series"]][-10:])],
            "attention": round(attn[r["id"]], 3),
        }
        for i, r in enumerate(ranked_sorted)
    ]
    streamgraph = [
        {
            "currentId": r["id"], "colorKey": r["color_key"],
            "series": [{"t": wk, "share": s} for wk, s in _weekly(r["series"])],
        }
        for r in results
    ]
    top = ranked_sorted[0]
    now = dt.datetime.now(dt.timezone.utc)
    todays_read = {
        "paragraph": (
            f"이번 집계에서 {top['name']}이(가) 모멘텀 1위입니다 — {STATE_KO[top['m']['state']]}. "
            f"실데이터(GDELT) 기반 계산값이며, 합성 브리핑은 다음 단계입니다."
        ),
        "asOf": now.isoformat(),
    }
    stats = {
        "currentsTracked": len(results),
        "newThreads": 0,
        "storiesScanned": sum(c for r in results for _, c in r["series"]),
    }
    etag = "sha-" + hashlib.sha1(json.dumps(ranked, sort_keys=True).encode()).hexdigest()[:12]

    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        for r in results:
            last_date = dt.date.fromisoformat(r["series"][-1][0])
            m = r["m"]
            cur.execute(
                """
                INSERT INTO momentum_point
                  (current_id, t, volume, persistence_days, spread, spread_outlets,
                   spread_countries, accel_d1, accel_d2, baseline_median, baseline_mad,
                   score, state, tau_state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (current_id, t) DO UPDATE SET
                  volume=EXCLUDED.volume, persistence_days=EXCLUDED.persistence_days,
                  accel_d1=EXCLUDED.accel_d1, baseline_median=EXCLUDED.baseline_median,
                  baseline_mad=EXCLUDED.baseline_mad, score=EXCLUDED.score,
                  state=EXCLUDED.state, tau_state=EXCLUDED.tau_state
                """,
                (
                    r["id"], last_date, m["volume"], m["persistence_days"], m["spread"],
                    m["spread_outlets"], m["spread_countries"], m["accel_d1"], m["accel_d2"],
                    m["baseline_median"], m["baseline_mad"], m["score"], m["state"], m["tau_state"],
                ),
            )
        cur.execute("UPDATE board_view SET is_current=false WHERE is_current")
        cur.execute(
            """
            INSERT INTO board_view (as_of, generated_at, todays_read, streamgraph, ranked, stats, is_current, etag)
            VALUES (%s,%s,%s,%s,%s,%s,true,%s)
            """,
            (now, now, Json(todays_read), Json(streamgraph), Json(ranked), Json(stats), etag),
        )
        conn.commit()
    print(f"published board_view (etag {etag}) · top={top['name']} ({top['m']['state']}) · scanned={stats['storiesScanned']:,}")


def main() -> None:
    print("[build_board] collecting GDELT volume timelines …")
    results = collect()
    publish(results)


if __name__ == "__main__":
    main()
