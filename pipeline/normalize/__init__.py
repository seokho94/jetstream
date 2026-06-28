"""Ingest & normalize (spec §4 stage 2): body fetch+extract (trafilatura),
language detect, canonical-URL + SimHash dedup, title+lede embedding (原文 직접,
bge-m3@v1.5). license_tier governs body persistence (licensed/crawl_ttl/metadata_only).
"""
