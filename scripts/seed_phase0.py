"""Seed Phase 0: one vertical + ~6 hand-curated currents with stable IDs.

Run after applying the schema:
    psql "$DATABASE_URL" -f pipeline/db/schema.sql
    python -m scripts.seed_phase0

Idempotent (ON CONFLICT DO NOTHING). color_key references the confirmed
color_registry seeded by schema.sql (CANON §14 R11).
"""
from __future__ import annotations

from pipeline.db.connection import connect

VERTICAL = ("geopolitics", "Geopolitics")

# (current_id, name, color_key) — color_key must be a non-reserved color_registry row.
CURRENTS = [
    ("ai-governance", "AI governance", "ai-governance"),
    ("cost-of-living", "Cost of living", "cost-of-living"),
    ("energy", "Energy", "energy"),
    ("climate", "Climate", "climate"),
    ("middle-east", "Middle East", "middle-east"),
    ("china", "China", "china"),
]


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vertical(id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            VERTICAL,
        )
        for cid, name, color_key in CURRENTS:
            cur.execute(
                """
                INSERT INTO current (id, vertical_id, name, color_key)
                VALUES (%s, 'geopolitics', %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (cid, name, color_key),
            )
        conn.commit()
    print(f"seeded vertical '{VERTICAL[0]}' + {len(CURRENTS)} currents")


if __name__ == "__main__":
    main()
