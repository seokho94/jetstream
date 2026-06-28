"""Minimal Postgres connection helper (psycopg 3)."""
import os

try:  # psycopg is optional until the DB work starts.
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore

DEFAULT_DSN = "postgresql://meridian:meridian@localhost:5432/meridian"


def get_dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


def connect():
    """Open a connection. Requires `pip install -e .` (psycopg)."""
    if psycopg is None:
        raise RuntimeError("psycopg not installed — run `pip install -e .`")
    return psycopg.connect(get_dsn())
