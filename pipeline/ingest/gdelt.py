"""GDELT collector — discovery layer (spec §4 stage 1, ingestion-and-clustering.md).

GDELT DOC 2.0 API yields article URLs + metadata (NOT bodies). We:
  1. query one vertical (keyword/lang scope),
  2. filter to a trusted-domain whitelist (volume + quality + crawl-safety),
  3. normalize each hit into an Article *stub* (canonical_url, source_domain, ...).

Bodies are fetched + extracted later in `pipeline.normalize` (whitelist-only,
SSRF-guarded). No external key required.

Run:  python -m pipeline.ingest.gdelt --vertical geopolitics --max 30
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "MeridianBot/0.0 (+phase0; news currents)"

# Vertical → GDELT DOC query. Phase 0 = geopolitics only (spec §8/§9).
VERTICAL_QUERIES: dict[str, str] = {
    "geopolitics": (
        '(geopolitics OR diplomacy OR sanctions OR "foreign policy" OR '
        '"national security" OR military OR treaty) sourcelang:english'
    ),
}

# Starter trusted-domain whitelist (placeholder for the 300–500 SourceRegistry set).
WHITELIST: set[str] = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "theguardian.com",
    "nytimes.com", "washingtonpost.com", "wsj.com", "ft.com", "economist.com",
    "bloomberg.com", "aljazeera.com", "cnn.com", "nbcnews.com", "abcnews.go.com",
    "cbsnews.com", "npr.org", "politico.com", "axios.com", "france24.com",
    "dw.com", "euronews.com", "scmp.com", "japantimes.co.jp", "thehindu.com",
    "timesofindia.indiatimes.com", "afp.com", "cnbc.com", "newsweek.com", "time.com",
}

# GDELT language names → ISO-639-1 (the common ones; fallback handled below).
_LANG_MAP = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "portuguese": "pt", "italian": "it", "arabic": "ar", "russian": "ru",
    "chinese": "zh", "japanese": "ja", "korean": "ko", "hindi": "hi",
}
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "igshid", "ref")


def canonicalize_url(url: str) -> str:
    """Normalize for dedup: lowercase host, drop fragment + tracking params, sort query."""
    s = urllib.parse.urlsplit(url)
    host = (s.hostname or "").lower()
    if s.port and s.port not in (80, 443):
        host = f"{host}:{s.port}"
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(s.query, keep_blank_values=False)
        if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    query.sort()
    path = s.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((s.scheme.lower() or "https", host, path, urllib.parse.urlencode(query), ""))


def registrable_domain(domain: str) -> str:
    """Crude eTLD strip: keep the last two labels (good enough for the whitelist)."""
    d = domain.lower().lstrip(".")
    parts = d.split(".")
    if len(parts) <= 2:
        return d
    # handle common two-part suffixes (co.uk, go.jp, ...)
    if parts[-2] in {"co", "com", "go", "org", "gov", "ac", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _parse_seendate(s: str) -> str:
    """GDELT 'YYYYMMDDTHHMMSSZ' → ISO-8601 UTC."""
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).isoformat()


def _lang_iso(name: str) -> str:
    return _LANG_MAP.get((name or "").lower(), (name or "und").lower()[:2])


def _to_stub(article: dict) -> dict:
    """Map a GDELT DOC artlist record to an Article stub (no body yet)."""
    url = article.get("url", "")
    domain = registrable_domain(article.get("domain", ""))
    return {
        "url": url,
        "canonical_url": canonicalize_url(url),
        "source_domain": domain,
        "published_at": _parse_seendate(article.get("seendate", "")),
        "language": _lang_iso(article.get("language", "")),
        "title": article.get("title", "").strip(),
        "source_country": article.get("sourcecountry", "") or None,
        "body": None,
        "body_extracted": False,
        "is_canonical": True,
    }


def _fetch(query: str, max_records: int, timespan: str, retries: int = 3) -> list[dict]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max(1, min(max_records, 250))),
        "timespan": timespan,
        "sort": "datedesc",
    }
    req = urllib.request.Request(
        f"{GDELT_DOC_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:  # 429 throttling / 5xx → backoff
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2**attempt)  # 1s, 2s, 4s
                continue
            raise RuntimeError(f"GDELT HTTP {e.code} (rate-limited?); try again later") from e
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"GDELT unreachable: {e.reason}") from e
        try:
            return json.loads(raw).get("articles", []) or []
        except json.JSONDecodeError:
            # GDELT returns a plain-text error (e.g. throttling) instead of JSON.
            raise RuntimeError(f"GDELT non-JSON response: {raw[:160]!r}")
    raise RuntimeError("GDELT fetch failed after retries")


def discover(
    vertical: str = "geopolitics",
    max_records: int = 75,
    timespan: str = "24h",
    whitelist_only: bool = True,
) -> dict:
    """Discover article stubs for a vertical. Returns {stubs, kept, dropped, deduped}."""
    query = VERTICAL_QUERIES.get(vertical)
    if not query:
        raise ValueError(f"unknown vertical {vertical!r}; known: {sorted(VERTICAL_QUERIES)}")

    raw = _fetch(query, max_records, timespan)
    stubs: list[dict] = []
    seen: set[str] = set()
    dropped_offlist = 0
    deduped = 0
    for art in raw:
        stub = _to_stub(art)
        if whitelist_only and stub["source_domain"] not in WHITELIST:
            dropped_offlist += 1
            continue
        if stub["canonical_url"] in seen:  # cheap canonical-URL dedup (SimHash is in normalize)
            deduped += 1
            continue
        seen.add(stub["canonical_url"])
        stubs.append(stub)

    return {
        "vertical": vertical,
        "fetched": len(raw),
        "kept": len(stubs),
        "dropped_offlist": dropped_offlist,  # logged, never silent (design principle)
        "deduped": deduped,
        "stubs": stubs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="GDELT discovery (Phase 0).")
    ap.add_argument("--vertical", default="geopolitics")
    ap.add_argument("--max", type=int, default=75, help="GDELT maxrecords (≤250)")
    ap.add_argument("--timespan", default="24h", help="e.g. 24h, 3d, 1w")
    ap.add_argument("--all-domains", action="store_true", help="disable whitelist filter")
    ap.add_argument("--out", help="write stubs to a JSON file")
    args = ap.parse_args()

    result = discover(
        vertical=args.vertical,
        max_records=args.max,
        timespan=args.timespan,
        whitelist_only=not args.all_domains,
    )
    print(
        f"[gdelt] vertical={result['vertical']} fetched={result['fetched']} "
        f"kept={result['kept']} dropped_offlist={result['dropped_offlist']} deduped={result['deduped']}"
    )
    for s in result["stubs"][:10]:
        print(f"  · {s['source_domain']:<22} {s['published_at'][:16]}  {s['title'][:70]}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result["stubs"], f, ensure_ascii=False, indent=2)
        print(f"[gdelt] wrote {len(result['stubs'])} stubs → {args.out}")


if __name__ == "__main__":
    main()
