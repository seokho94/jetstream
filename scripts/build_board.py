"""Build the live board, current detail views, and the weekly digest from real
GDELT data (Phase 1 momentum + C-lite detail/digest, no embeddings).

Per current: pull a daily volume timeline + source facets (keyword rules), compute
the 4 momentum signals + state, then cross-current normalize → score → rank.
Writes momentum_point, board_view, current_view (arc/coverage/brief/timeline from
real data), weekly_rank, and digest. The API serves these when present.

Prereq: `docker compose up -d`.   Run: python -m scripts.build_board
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
from pipeline.ingest.gdelt import source_facets, volume_timeline
from pipeline.momentum import rank, signals_for

DSN = os.environ.get("DATABASE_URL", "postgresql://meridian:meridian@localhost:5432/meridian")
STATE_KO = {"rising": "상승", "peaking": "정점", "cooling": "냉각", "steady": "안정"}
WHY = {
    "rising": "단기 가속 — 새로 부상하는 흐름입니다.",
    "cooling": "관심이 식는 국면 — 정점을 지났을 수 있습니다.",
    "peaking": "높은 수준에서 평탄화 — 고점 부근입니다.",
    "steady": "극적 사건 없이 꾸준한 기저 관심이 유지됩니다.",
}
GDELT_GAP = 7.0  # seconds between GDELT calls (avoid 429)


def _minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    return [(v - lo) / (hi - lo) if hi > lo else 0.5 for v in vals]


def _weekly(series: list[tuple[str, int]], n: int = 8) -> list[tuple[str, int]]:
    buckets: dict[str, int] = {}
    for d, c in series:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        buckets.setdefault(f"{y}-W{w:02d}", 0)
        buckets[f"{y}-W{w:02d}"] += c
    return sorted(buckets.items())[-n:]


def _arc(series: list[tuple[str, int]]) -> tuple[list[dict], list[int]]:
    counts = [c for _, c in series]
    norm = _minmax([float(c) for c in counts])
    pts = [{"t": d, "value": round(v, 3)} for (d, _), v in zip(series, norm)]
    peak_idx = sorted(sorted(range(len(counts)), key=lambda i: counts[i], reverse=True)[:5])
    for k, i in enumerate(peak_idx):
        pts[i]["marker"] = k + 1
        pts[i]["eventId"] = series[i][0]
    return pts, peak_idx


def _timeline(series: list[tuple[str, int]], peak_idx: list[int], top_outlets: list[str] | None) -> list[dict]:
    outs = top_outlets or ["GDELT"]
    nodes = []
    for k, i in enumerate(peak_idx):
        d, c = series[i]
        outlet = outs[k % len(outs)]
        url = f"https://{outlet}" if outlet != "GDELT" else ""
        nodes.append(
            {
                "node": k + 1, "date": d, "text": f"{d} 전후 보도 집중 — 일 {c}건", "eventId": d,
                "isLatest": k == len(peak_idx) - 1,
                "sources": [{"text": "", "outlet": outlet, "url": url, "charStart": 0, "charEnd": 0}],
            }
        )
    return nodes


def _coverage(regions: dict[str, int]) -> dict:
    total = sum(regions.values()) or 1
    buckets, hidden = [], []
    for label, n in sorted(regions.items(), key=lambda kv: kv[1], reverse=True):
        if n < 5:
            hidden.append(label)
            continue
        buckets.append({"label": label, "pct": round(n * 100 / total), "n": n})
    return {"axis": "region_block", "minN": 5, "buckets": buckets[:4], "hidden": hidden}


def _brief(name: str, sig: dict, facets: dict) -> dict:
    return {
        "whatsHappening": (
            f"{name}: 최근 2주 추세는 {STATE_KO[sig['state']]}(상대변화 {sig['rel_trend']:+.1%}). "
            f"일평균 보도량 약 {round(sig['baseline_median'])}건, 약 {facets['countries']}개국·"
            f"{facets['outlets']}개 매체가 다루고 있습니다."
        ),
        "whyItMatters": WHY[sig["state"]] + " (실데이터 계산값 · 합성 브리핑 전)",
        "citations": [],
    }


def collect() -> list[dict]:
    """Two passes: timelines first (critical), then source facets (best-effort)."""
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, color_key FROM current WHERE status='active' ORDER BY id")
        currents = [(cid, n, ck) for cid, n, ck in cur.fetchall() if CURRENT_QUERIES.get(cid)]

    series_by: dict[str, list[tuple[str, int]]] = {}
    for cid, _n, _ck in currents:
        try:
            s = volume_timeline(CURRENT_QUERIES[cid], timespan="10w")
            if s:
                series_by[cid] = s
            else:
                print(f"  ! {cid}: empty series")
        except Exception as e:
            print(f"  ! {cid}: GDELT timeline failed ({e})")
        time.sleep(GDELT_GAP)

    facets_by: dict[str, dict] = {}
    for cid in series_by:
        try:
            facets_by[cid] = source_facets(CURRENT_QUERIES[cid])
        except Exception as e:
            facets_by[cid] = {"outlets": 0, "countries": 0, "regions": {}, "top_outlet": None, "n": 0}
            print(f"  ~ {cid}: facets unavailable ({e})")
        time.sleep(GDELT_GAP)

    out: list[dict] = []
    for cid, name, color_key in currents:
        if cid not in series_by:
            continue
        series = series_by[cid]
        facets = facets_by.get(cid, {"outlets": 0, "countries": 0, "regions": {}, "top_outlet": None})
        sig = signals_for(series, spread_outlets=facets["outlets"], spread_countries=facets["countries"])
        out.append({"id": cid, "name": name, "color_key": color_key, "series": series, "facets": facets, "sig": sig})
        print(
            f"  · {cid:<15} state={sig['state']:<8} rel={sig['rel_trend']:<8} "
            f"vol={sig['volume']:<9} persist={sig['persistence_days']}d "
            f"spread={facets['outlets']}out/{facets['countries']}ctry"
        )
    return out


def publish(results: list[dict]) -> None:
    series_map = {r["id"]: r["series"] for r in results}
    facet_map = {r["id"]: r["facets"] for r in results}
    sig_map = {r["id"]: r["sig"] for r in results}
    now = dt.datetime.now(dt.timezone.utc)
    iso = now.isocalendar()
    issue = iso.year * 100 + iso.week
    week_of = now.date() - dt.timedelta(days=now.weekday())

    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        # 1) upsert this run's momentum_point (score filled after ranking)
        for r in results:
            s = r["sig"]
            cur.execute(
                """
                INSERT INTO momentum_point
                  (current_id, t, volume, persistence_days, spread, spread_outlets,
                   spread_countries, accel_d1, accel_d2, baseline_median, baseline_mad, score, state, tau_state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s)
                ON CONFLICT (current_id, t) DO UPDATE SET
                  volume=EXCLUDED.volume, persistence_days=EXCLUDED.persistence_days, spread=EXCLUDED.spread,
                  spread_outlets=EXCLUDED.spread_outlets, spread_countries=EXCLUDED.spread_countries,
                  accel_d1=EXCLUDED.accel_d1, accel_d2=EXCLUDED.accel_d2, baseline_median=EXCLUDED.baseline_median,
                  baseline_mad=EXCLUDED.baseline_mad, state=EXCLUDED.state, tau_state=EXCLUDED.tau_state
                """,
                (
                    r["id"], dt.date.fromisoformat(r["series"][-1][0]), s["volume"], s["persistence_days"],
                    s["spread"], s["spread_outlets"], s["spread_countries"], s["accel_d1"], s["accel_d2"],
                    s["baseline_median"], s["baseline_mad"], s["state"], s["tau_state"],
                ),
            )

        # 2) rank from the FULL momentum_point store (robust to partial GDELT runs)
        cur.execute(
            """
            SELECT DISTINCT ON (mp.current_id) mp.current_id, c.name, c.color_key,
                   mp.volume, mp.persistence_days, mp.spread, mp.accel_d1, mp.state, mp.baseline_median
            FROM momentum_point mp JOIN current c ON c.id = mp.current_id
            WHERE c.status='active' ORDER BY mp.current_id, mp.t DESC
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("no momentum_point rows — nothing published")
            return
        items = [
            {
                "id": r[0], "name": r[1], "color_key": r[2], "state": r[7],
                "_raw": {"volume": float(r[3]), "persist": float(r[4]), "spread": float(r[5]),
                         "accel": float(r[6]) / (float(r[8]) + 1e-6)},
            }
            for r in rows
        ]
        rank(items)
        by_rank = sorted(items, key=lambda it: it["rank"])
        attn = dict(zip([it["id"] for it in items], _minmax([it["score"] for it in items])))
        for it in items:
            cur.execute(
                "UPDATE momentum_point SET score=%s WHERE current_id=%s "
                "AND t=(SELECT max(t) FROM momentum_point WHERE current_id=%s)",
                (it["score"], it["id"], it["id"]),
            )

        # 3) board_view
        ranked = []
        for it in by_rank:
            sm = series_map.get(it["id"])
            spark = [round(v, 3) for v in _minmax([c for _, c in sm][-10:])] if sm else [0.5] * 8
            ranked.append({
                "currentId": it["id"], "name": it["name"], "colorKey": it["color_key"], "rank": it["rank"],
                "state": it["state"], "score": it["score"], "sparkline": spark, "attention": round(attn[it["id"]], 3),
            })
        streamgraph = [
            {"currentId": it["id"], "colorKey": it["color_key"],
             "series": [{"t": wk, "share": s} for wk, s in _weekly(series_map[it["id"]])]}
            for it in by_rank if it["id"] in series_map
        ]
        top = by_rank[0]
        todays_read = {
            "paragraph": (
                f"이번 집계에서 {top['name']}이(가) 모멘텀 1위입니다 — {STATE_KO[top['state']]}. "
                f"흐름간 정규화(4신호 가중) 기반 실데이터 순위입니다."
            ),
            "asOf": now.isoformat(),
        }
        stats = {"currentsTracked": len(items), "newThreads": 0,
                 "storiesScanned": sum(c for sm in series_map.values() for _, c in sm)}
        board_etag = "sha-" + hashlib.sha1(json.dumps(ranked, sort_keys=True).encode()).hexdigest()[:12]
        cur.execute("UPDATE board_view SET is_current=false WHERE is_current")
        cur.execute(
            "INSERT INTO board_view (as_of, generated_at, todays_read, streamgraph, ranked, stats, is_current, etag) "
            "VALUES (%s,%s,%s,%s,%s,%s,true,%s)",
            (now, now, Json(todays_read), Json(streamgraph), Json(ranked), Json(stats), board_etag),
        )

        # 4) current_view (detail) for currents fetched this run — real arc/coverage/brief/timeline
        rank_of = {it["id"]: it["rank"] for it in items}
        state_of = {it["id"]: it["state"] for it in items}
        for cid, series in series_map.items():
            facets = facet_map[cid]
            if not facets.get("n"):
                continue  # facets failed (GDELT 429) — keep the prior good current_view, don't degrade it
            sig = sig_map[cid]
            arc, peak_idx = _arc(series)
            timeline = _timeline(series, peak_idx, facets.get("top_outlets"))
            coverage = _coverage(facets.get("regions", {}))
            brief = _brief(next(it["name"] for it in items if it["id"] == cid), sig, facets)
            cv_etag = "sha-" + hashlib.sha1(f"{cid}{board_etag}".encode()).hexdigest()[:12]
            cur.execute(
                """
                INSERT INTO current_view
                  (current_id, store, version, name, color_key, rank, state, arc, brief, timeline,
                   coverage, as_of, is_last_known_good, etag)
                VALUES (%s,'published',1,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)
                ON CONFLICT (current_id, store, version) DO UPDATE SET
                  name=EXCLUDED.name, color_key=EXCLUDED.color_key, rank=EXCLUDED.rank, state=EXCLUDED.state,
                  arc=EXCLUDED.arc, brief=EXCLUDED.brief, timeline=EXCLUDED.timeline, coverage=EXCLUDED.coverage,
                  as_of=EXCLUDED.as_of, etag=EXCLUDED.etag
                """,
                (
                    cid, next(it["name"] for it in items if it["id"] == cid),
                    next(it["color_key"] for it in items if it["id"] == cid),
                    rank_of[cid], state_of[cid], Json(arc), Json(brief), Json(timeline), Json(coverage), now, cv_etag,
                ),
            )

        # 5a) backfill last week's weekly_rank from as-of-(now−7d) momentum, so the digest
        #     reshuffle shows real movement immediately instead of waiting a calendar week
        prev_dt = now - dt.timedelta(days=7)
        p_iso = prev_dt.isocalendar()
        prev_issue = p_iso.year * 100 + p_iso.week
        prev_week_of = prev_dt.date() - dt.timedelta(days=prev_dt.weekday())
        cur.execute("SELECT count(*) FROM weekly_rank WHERE issue=%s", (prev_issue,))
        if cur.fetchone()[0] == 0:
            name_of = {it["id"]: it["name"] for it in items}
            prev_items = []
            for cid, series in series_map.items():
                if len(series) > 21:
                    f = facet_map[cid]
                    ps = signals_for(series[:-7], spread_outlets=f.get("outlets", 0), spread_countries=f.get("countries", 0))
                    prev_items.append({"id": cid, "name": name_of.get(cid, cid), "state": ps["state"], "_raw": ps["_raw"]})
            if prev_items:
                rank(prev_items)
                for it in prev_items:
                    cur.execute(
                        "INSERT INTO weekly_rank (issue, current_id, week_of, rank, score, state) "
                        "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (issue, current_id) DO NOTHING",
                        (prev_issue, it["id"], prev_week_of, it["rank"], it["score"], it["state"]),
                    )

        # 5) weekly_rank snapshot + digest
        for it in items:
            cur.execute(
                """
                INSERT INTO weekly_rank (issue, current_id, week_of, rank, score, state)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (issue, current_id) DO UPDATE SET
                  rank=EXCLUDED.rank, score=EXCLUDED.score, state=EXCLUDED.state, week_of=EXCLUDED.week_of
                """,
                (issue, it["id"], week_of, it["rank"], it["score"], it["state"]),
            )
        cur.execute("SELECT DISTINCT issue FROM weekly_rank ORDER BY issue DESC LIMIT 2")
        issues = [r[0] for r in cur.fetchall()]
        prev_issue = issues[1] if len(issues) > 1 else None
        this_ranks = {it["id"]: it["rank"] for it in items}
        prev_ranks = {}
        if prev_issue is not None:
            cur.execute("SELECT current_id, rank FROM weekly_rank WHERE issue=%s", (prev_issue,))
            prev_ranks = dict(cur.fetchall())
        meta = {it["id"]: (it["name"], it["color_key"]) for it in items}
        reshuffle = [
            {"currentId": cid, "name": meta[cid][0], "colorKey": meta[cid][1],
             "lastRank": prev_ranks.get(cid, tr), "thisRank": tr}
            for cid, tr in sorted(this_ranks.items(), key=lambda kv: kv[1])
        ]
        deltas = {cid: prev_ranks.get(cid, tr) - tr for cid, tr in this_ranks.items()}  # +rose
        climber = max(deltas, key=deltas.get)
        faller = min(deltas, key=deltas.get)

        def _mv(cid: str) -> dict:
            return {"currentId": cid, "name": meta[cid][0], "lastRank": prev_ranks.get(cid, this_ranks[cid]),
                    "thisRank": this_ranks[cid], "note": ("상승" if deltas[cid] > 0 else "하락" if deltas[cid] < 0 else "유지")}

        digest_lede = f"이번 주 모멘텀 1위는 {top['name']} — {STATE_KO[top['state']]}. 흐름간 정규화 기반 실데이터 집계."
        blurbs = [{"kicker": it["name"], "body": WHY[it["state"]]} for it in by_rank[:3]]
        watch_next = [f"{it['name']}: 다음 주 추세 전환 여부" for it in by_rank[:3]]
        cur.execute(
            """
            INSERT INTO digest (issue, week_of, store, lede, reshuffle, movers, blurbs, watch_next, stats, published_at)
            VALUES (%s,%s,'published',%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (issue) DO UPDATE SET
              week_of=EXCLUDED.week_of, lede=EXCLUDED.lede, reshuffle=EXCLUDED.reshuffle, movers=EXCLUDED.movers,
              blurbs=EXCLUDED.blurbs, watch_next=EXCLUDED.watch_next, stats=EXCLUDED.stats, published_at=EXCLUDED.published_at
            """,
            (issue, week_of, digest_lede, Json(reshuffle), Json({"climber": _mv(climber), "faller": _mv(faller)}),
             Json(blurbs), watch_next, Json(stats), now),
        )
        conn.commit()

    states = ", ".join(f"{it['name']}={it['state']}" for it in by_rank)
    print(f"published: board_view + {len(series_map)} current_view + digest#{issue} · top={top['name']} ({top['state']})")
    print(f"  states: {states}")


def main() -> None:
    print("[build_board] collecting GDELT volume timelines + facets …")
    results = collect()
    if results:
        publish(results)
    else:
        print("no currents collected — check GDELT availability")


if __name__ == "__main__":
    main()
