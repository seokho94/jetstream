"""Collect (spec §4 stage 1): GDELT discovery + news API + RSS.

NOTE: GDELT yields URLs/metadata, not article bodies. Discover URLs here;
fetch + extract bodies in `normalize` (whitelist-only, SSRF-guarded). See
docs/design/ingestion-and-clustering.md.
"""
