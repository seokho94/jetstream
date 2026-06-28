"""Refresh published current_view briefs with grounded LLM synthesis.

Per current: GDELT facets (article URLs) → crawl whitelisted bodies → Claude
Citations brief → UPDATE current_view.brief. Key-gated (no-op without
ANTHROPIC_API_KEY). Uses only facets calls (no timelines), so it's lighter on
GDELT than build_board. Best-effort: currents whose fetch is rate-limited keep
their existing brief.

Run: python -m scripts.synthesize_briefs
"""
from __future__ import annotations

import os
import time

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pipeline.cluster.rules import CURRENT_QUERIES  # noqa: E402
from pipeline.ingest.gdelt import source_facets  # noqa: E402
from pipeline.normalize.crawl import crawl  # noqa: E402
from pipeline.synthesis.synthesize import available, synthesize_brief  # noqa: E402

DSN = os.environ.get("DATABASE_URL", "postgresql://meridian:meridian@localhost:5432/meridian")
GAP = 8.0


def main() -> None:
    if not available():
        print("ANTHROPIC_API_KEY not set — nothing to do")
        return
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name FROM current WHERE status='active' ORDER BY id")
        currents = [(cid, name) for cid, name in cur.fetchall() if CURRENT_QUERIES.get(cid)]

    updated = 0
    for cid, name in currents:
        try:
            arts = source_facets(CURRENT_QUERIES[cid]).get("articles", [])
        except Exception as e:
            print(f"  ~ {cid}: facets failed ({e})")
            time.sleep(GAP)
            continue
        docs = []
        for a in arts[:4]:
            body = crawl(a.get("url", ""))
            if body:
                docs.append({"title": a.get("title", ""), "url": a.get("url", ""),
                             "outlet": a.get("outlet", ""), "body": body["body"]})
        brief = synthesize_brief(name, docs)
        if brief:
            with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE current_view SET brief=%s WHERE current_id=%s AND store='published'",
                    (Json(brief), cid),
                )
                conn.commit()
            updated += 1
            print(f"  · {cid:<15} grounded brief: {len(brief['citations'])} citations, {len(docs)} sources → updated")
        else:
            print(f"  - {cid:<15} no grounded brief (docs={len(docs)})")
        time.sleep(GAP)
    print(f"updated {updated} briefs")


if __name__ == "__main__":
    main()
