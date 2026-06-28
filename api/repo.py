"""DB-aware reads for the serving layer.

Reads from Postgres when DATABASE_URL is set and reachable; otherwise falls back
to seed so Phase 0 works without a database. Each accessor returns the data plus
a source tag ('db' | 'seed') so the API can advertise it via X-Data-Source.
"""
from __future__ import annotations

import os

from . import seed
from .schemas import BoardView, CurrentView, Digest

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
                    FROM current c JOIN color_registry cr ON cr.color_key = c.color_key
                    WHERE c.status = 'active' ORDER BY c.id
                    """
                )
                rows = cur.fetchall()
            return ([dict(currentId=r[0], name=r[1], colorKey=r[2], verticalId=r[3], hex=r[4], status=r[5]) for r in rows], "db")
        except Exception:
            pass
    return (
        [dict(currentId=m["id"], name=m["name"], colorKey=m["id"], verticalId="geopolitics", hex=None, status="active") for m in seed.META],
        "seed",
    )


def _board_from_db() -> BoardView | None:
    """Read the published board_view (the real board built by scripts.build_board)."""
    dsn = _dsn()
    if not (psycopg and dsn):
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, as_of, generated_at, is_current, todays_read, streamgraph, ranked, stats, etag
                FROM board_view WHERE is_current ORDER BY id DESC LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("SELECT issue, week_of, lede FROM digest WHERE store='published' ORDER BY issue DESC LIMIT 1")
            d = cur.fetchone()
        teaser = (
            {"issue": d[0], "weekOf": d[1].isoformat(), "lede": d[2]}
            if d else seed.build_board().digestTeaser
        )
        bid, as_of, generated_at, is_current, todays_read, streamgraph, ranked, stats, etag = row
        return BoardView(
            id=bid, asOf=as_of.isoformat(), generatedAt=generated_at.isoformat(), isCurrent=is_current,
            todaysRead=todays_read, streamgraph=streamgraph, ranked=ranked, digestTeaser=teaser,
            stats=stats, etag=etag, lang="en",
        )
    except Exception:
        return None


def get_board() -> tuple[BoardView, str]:
    """Prefer the real published board_view; else seed enriched with DB current names/hues."""
    board = _board_from_db()
    if board is not None:
        return board, "db"
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


def get_current(current_id: str) -> tuple[CurrentView | None, str]:
    """Published current_view (real arc/coverage/brief/timeline) when present, else seed."""
    dsn = _dsn()
    if psycopg and dsn:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT current_id, name, color_key, rank, state, arc, brief, timeline, coverage, as_of, etag
                    FROM current_view
                    WHERE current_id=%s AND store='published' AND is_last_known_good
                    ORDER BY version DESC LIMIT 1
                    """,
                    (current_id,),
                )
                row = cur.fetchone()
            if row:
                return (
                    CurrentView(
                        currentId=row[0], store="published", version=1, name=row[1], colorKey=row[2],
                        rank=row[3], state=row[4], arc=row[5], brief=row[6], timeline=row[7], coverage=row[8],
                        asOf=row[9].isoformat(), isLastKnownGood=True, etag=row[10], lang="en",
                    ),
                    "db",
                )
        except Exception:
            pass
    return (seed.build_current(current_id), "seed")


def get_digest(issue: int) -> tuple[Digest, str]:
    """Published digest (real reshuffle/movers from weekly_rank) when present, else seed."""
    dsn = _dsn()
    if psycopg and dsn:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT issue, week_of, lede, reshuffle, movers, blurbs, watch_next, stats FROM digest WHERE issue=%s",
                    (issue,),
                )
                row = cur.fetchone()
            if row:
                return (
                    Digest(
                        issue=row[0], weekOf=row[1].isoformat(), store="published", lede=row[2],
                        reshuffle=row[3], movers=row[4], blurbs=row[5], watchNext=row[6], stats=row[7], lang="en",
                    ),
                    "db",
                )
        except Exception:
            pass
    return (seed.build_digest(issue), "seed")
