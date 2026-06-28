"""DB-aware reads for the serving layer.

Reads from Postgres when DATABASE_URL is set and reachable; otherwise falls back
to seed so Phase 0 works without a database. Each accessor returns the data plus
a source tag ('db' | 'seed') so the API can advertise it via X-Data-Source.
"""
from __future__ import annotations

import os

from . import seed
from .schemas import BoardView

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore


def _dsn() -> str | None:
    return os.environ.get("DATABASE_URL")


def db_available() -> bool:
    dsn = _dsn()
    if not (psycopg and dsn):
        return False
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def list_currents() -> tuple[list[dict], str]:
    """Active currents joined with their confirmed hue (CANON §14 R11)."""
    dsn = _dsn()
    if psycopg and dsn:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.name, c.color_key, c.vertical_id, cr.hex, c.status
                    FROM current c
                    JOIN color_registry cr ON cr.color_key = c.color_key
                    WHERE c.status = 'active'
                    ORDER BY c.id
                    """
                )
                rows = cur.fetchall()
            return (
                [
                    dict(currentId=r[0], name=r[1], colorKey=r[2], verticalId=r[3], hex=r[4], status=r[5])
                    for r in rows
                ],
                "db",
            )
        except Exception:
            pass  # fall through to seed
    return (
        [
            dict(currentId=m["id"], name=m["name"], colorKey=m["id"], verticalId="geopolitics", hex=None, status="active")
            for m in seed.META
        ],
        "seed",
    )


def get_board() -> tuple[BoardView, str]:
    """Seed board enriched with DB current names/hues when a DB is present.

    Phase 0: momentum/arc still come from seed (published views aren't generated
    yet); names + color_key are overlaid from the DB to prove the read path.
    """
    board = seed.build_board()
    rows, source = list_currents()
    if source == "db" and rows:
        names = {r["currentId"]: r["name"] for r in rows}
        colors = {r["currentId"]: r["colorKey"] for r in rows}
        for row in board.ranked:
            if row.currentId in names:
                row.name = names[row.currentId]
                row.colorKey = colors[row.currentId]
    return board, source
