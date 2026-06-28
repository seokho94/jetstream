"""GDELT collector (Phase 0 backlog).

Plan (ingestion-and-clustering.md): use GDELT DOC 2.0 / GKG 2.1 for article
discovery + metadata, scoped to one vertical via a domain whitelist AND language
AND GKG theme filter, with a daily cap. Track the lastupdate.txt offset cursor;
upsert by canonical-URL hash for idempotency.
"""
from __future__ import annotations


def discover(vertical: str, since: str | None = None) -> list[dict]:
    """Return discovered article stubs ({url, source_domain, published_at, ...})."""
    raise NotImplementedError("Phase 0 backlog: GDELT collector — see phase-0-plan.md")
