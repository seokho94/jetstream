"""Ground the current_view timeline (spec §5.3 sourced timeline).

Per peak-day node: GDELT date-filtered artlist (±2 days) → crawl bodies → Claude
Citations one-sentence "what happened" → write node.text + node.sources (with
source URLs). Key-gated. GDELT-heavy (one date-filtered call per node), so each
run grounds the most-recent N still-generic nodes per current and is idempotent
(skips already-grounded nodes) — re-run to accumulate under GDELT rate limits.

Run: python -m scripts.synthesize_timeline
"""
from __future__ import annotations

import os
import time

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pipeline.cluster.rules import CURRENT_QUERIES  # noqa: E402
from pipeline.ingest.gdelt import articles_near  # noqa: E402
from pipeline.normalize.crawl import crawl  # noqa: E402
from pipeline.synthesis.synthesize import available, synthesize_event  # noqa: E402

DSN = os.environ.get("DATABASE_URL", "postgresql://meridian:meridian@localhost:5432/meridian")
GAP = 8.0
RECENT_NODES = 3  # ground at most this many still-generic nodes per current per run


_BAD = ("죄송", "제공된", "문서에", "문서들", "정보가 없", "정보가 포함", "포함되어 있지", "찾을 수 없")


def _is_generic(text: str) -> bool:
    """True for the computed placeholder ('… 보도 집중 …')."""
    return "보도 집중" in text


def _is_refusal(text: str) -> bool:
    """A prior run may have written a model refusal/meta-answer; treat it as not-grounded."""
    return any(m in text for m in _BAD)


def main() -> None:
    if not available():
        print("ANTHROPIC_API_KEY not set — nothing to do")
        return
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_id, name, timeline FROM current_view WHERE store='published' ORDER BY current_id")
        rows = cur.fetchall()

    total = 0
    for cid, name, timeline in rows:
        query = CURRENT_QUERIES.get(cid)
        if not query:
            continue
        changed = False
        for n in timeline:  # scrub any prior refusal text so the UI never shows it; make it regroundable
            if _is_refusal(n.get("text", "")):
                n["text"] = f"{n['date']} 전후 보도 집중 시점"
                n["sources"] = []
                changed = True
        todo = sorted([n for n in timeline if _is_generic(n.get("text", ""))], key=lambda n: n["date"], reverse=True)
        todo = todo[:RECENT_NODES]
        if not todo and not changed:
            print(f"  - {cid:<15} 모든 노드 grounded")
            continue
        for node in todo:
            date = node["date"]
            try:
                arts = articles_near(query, date)
            except Exception as e:
                print(f"  ~ {cid:<15} {date}: GDELT 실패 ({e})")
                time.sleep(GAP)
                continue
            docs = []
            for a in arts[:3]:
                body = crawl(a.get("url", ""))
                if body:
                    docs.append({"title": a.get("title", ""), "url": a.get("url", ""),
                                 "outlet": a.get("outlet", ""), "body": body["body"]})
            event = synthesize_event(name, date, docs)
            if event:
                node["text"] = event["text"]
                node["sources"] = event["sources"]
                changed = True
                total += 1
                print(f"  · {cid:<15} {date}: {event['text'][:64]}")
            else:
                print(f"  - {cid:<15} {date}: 근거 없음 (docs={len(docs)})")
            time.sleep(GAP)
        if changed:
            with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE current_view SET timeline=%s WHERE current_id=%s AND store='published'",
                    (Json(timeline), cid),
                )
                conn.commit()
    print(f"grounded {total} timeline nodes")


if __name__ == "__main__":
    main()
