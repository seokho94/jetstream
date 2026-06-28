"""Seed source_registry from the curated pipeline.sources list. Idempotent.

Run after the schema is applied:  python -m scripts.seed_sources
(docker compose's initdb only runs SQL, so this seeds the registry separately.)
"""
from __future__ import annotations

from pipeline.db.connection import connect
from pipeline.sources import SOURCES


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        for domain, m in SOURCES.items():
            cur.execute(
                """
                INSERT INTO source_registry
                  (domain, outlet_name, tier, country, region_block, outlet_type, license_tier, is_whitelisted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,true)
                ON CONFLICT (domain) DO UPDATE SET
                  outlet_name=EXCLUDED.outlet_name, tier=EXCLUDED.tier, country=EXCLUDED.country,
                  region_block=EXCLUDED.region_block, outlet_type=EXCLUDED.outlet_type,
                  license_tier=EXCLUDED.license_tier, is_whitelisted=true
                """,
                (domain, m["outlet_name"], m["tier"], m["country"], m["region_block"], m["outlet_type"], m["license_tier"]),
            )
        conn.commit()
    print(f"seeded {len(SOURCES)} sources into source_registry")


if __name__ == "__main__":
    main()
