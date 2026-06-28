"""GDELT collector — discovery + volume timelines (spec §4 stage 1).

GDELT DOC 2.0 API yields article URLs/metadata (NOT bodies) and volume
timelines. We:
  1. discover() — query a vertical, whitelist-filter, emit Article *stubs*,
  2. volume_timeline() — per-query daily article counts (drives momentum v0).

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

from pipeline.sources import WHITELIST  # curated trusted-outlet set

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "JetstreamBot/0.0 (+phase0; news currents)"

# Vertical → GDELT DOC query. Phase 0 = geopolitics only (spec §8/§9).
VERTICAL_QUERIES: dict[str, str] = {
    "geopolitics": (
        '(geopolitics OR diplomacy OR sanctions OR "foreign policy" OR '
        '"national security" OR military OR treaty) sourcelang:english'
    ),
}

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
    if parts[-2] in {"co", "com", "go", "org", "gov", "ac", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _parse_seendate(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).isoformat()


def _lang_iso(name: str) -> str:
    return _LANG_MAP.get((name or "").lower(), (name or "und").lower()[:2])


def _get_json(params: dict, retries: int = 5) -> dict:
    """GET the DOC API with retry/backoff on 429/5xx. Returns parsed JSON."""
    req = urllib.request.Request(
        f"{GDELT_DOC_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
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
            return json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"GDELT non-JSON response: {raw[:160]!r}")
    raise RuntimeError("GDELT fetch failed after retries")


def _to_stub(article: dict) -> dict:
    url = article.get("url", "")
    return {
        "url": url,
        "canonical_url": canonicalize_url(url),
        "source_domain": registrable_domain(article.get("domain", "")),
        "published_at": _parse_seendate(article.get("seendate", "")),
        "language": _lang_iso(article.get("language", "")),
        "title": article.get("title", "").strip(),
        "source_country": article.get("sourcecountry", "") or None,
        "body": None,
        "body_extracted": False,
        "is_canonical": True,
    }


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

    raw = _get_json(
        {"query": query, "mode": "artlist", "format": "json",
         "maxrecords": str(max(1, min(max_records, 250))), "timespan": timespan, "sort": "datedesc"}
    ).get("articles", []) or []

    stubs: list[dict] = []
    seen: set[str] = set()
    dropped_offlist = 0
    deduped = 0
    for art in raw:
        stub = _to_stub(art)
        if whitelist_only and stub["source_domain"] not in WHITELIST:
            dropped_offlist += 1
            continue
        if stub["canonical_url"] in seen:
            deduped += 1
            continue
        seen.add(stub["canonical_url"])
        stubs.append(stub)

    return {
        "vertical": vertical, "fetched": len(raw), "kept": len(stubs),
        "dropped_offlist": dropped_offlist, "deduped": deduped, "stubs": stubs,
    }


def volume_timeline(query: str, timespan: str = "10w", drop_last: bool = True) -> list[tuple[str, int]]:
    """Daily article-count series for a query → [(YYYY-MM-DD, count)].

    Uses GDELT DOC mode=timelinevolraw (value = matching article count/day).
    drop_last removes the in-progress current day (partial, biases momentum).
    """
    data = _get_json(
        {"query": query, "mode": "timelinevolraw", "format": "json", "timespan": timespan}
    ).get("timeline", [])
    if not data:
        return []
    points = data[0].get("data", [])
    series: list[tuple[str, int]] = []
    for p in points:
        try:
            d = datetime.strptime(p["date"], "%Y%m%dT%H%M%SZ").date().isoformat()
        except (ValueError, KeyError, TypeError):
            continue
        series.append((d, int(p.get("value", 0))))
    if drop_last and len(series) > 1:
        series = series[:-1]
    return series


# GDELT sourcecountry (country name) → coarse region_block for coverage (design §10).
COUNTRY_REGION = {
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    "United Kingdom": "Europe", "Ireland": "Europe", "France": "Europe", "Germany": "Europe",
    "Spain": "Europe", "Italy": "Europe", "Netherlands": "Europe", "Belgium": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe", "Finland": "Europe",
    "Poland": "Europe", "Austria": "Europe", "Switzerland": "Europe", "Portugal": "Europe",
    "Greece": "Europe", "Czech Republic": "Europe", "Hungary": "Europe", "Romania": "Europe",
    "Ukraine": "Europe", "Russia": "Europe",
    "Israel": "MENA", "Iran": "MENA", "Saudi Arabia": "MENA", "United Arab Emirates": "MENA",
    "Qatar": "MENA", "Turkey": "MENA", "Egypt": "MENA", "Iraq": "MENA", "Syria": "MENA",
    "Lebanon": "MENA", "Jordan": "MENA", "Yemen": "MENA", "Kuwait": "MENA",
    "China": "Asia", "Japan": "Asia", "South Korea": "Asia", "India": "Asia", "Pakistan": "Asia",
    "Indonesia": "Asia", "Singapore": "Asia", "Malaysia": "Asia", "Thailand": "Asia",
    "Vietnam": "Asia", "Philippines": "Asia", "Taiwan": "Asia", "Hong Kong": "Asia",
    "Bangladesh": "Asia", "Sri Lanka": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
    "Brazil": "Latin America", "Argentina": "Latin America", "Chile": "Latin America",
    "Colombia": "Latin America", "Peru": "Latin America", "Venezuela": "Latin America",
    "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa", "Ethiopia": "Africa",
    "Ghana": "Africa", "Morocco": "Africa", "Algeria": "Africa",
}


def source_facets(query: str, timespan: str = "1w", maxrecords: int = 250) -> dict:
    """One artlist call → spread (outlets, countries) + region coverage + top outlet."""
    arts = _get_json(
        {"query": query, "mode": "artlist", "format": "json",
         "maxrecords": str(max(1, min(maxrecords, 250))), "timespan": timespan, "sort": "datedesc"}
    ).get("articles", []) or []
    outlets: dict[str, int] = {}
    countries: set = set()
    regions: dict[str, int] = {}
    for a in arts:
        dom = registrable_domain(a.get("domain", ""))
        if dom:
            outlets[dom] = outlets.get(dom, 0) + 1
        sc = a.get("sourcecountry")
        if sc:
            countries.add(sc)
            reg = COUNTRY_REGION.get(sc, "Other")
            regions[reg] = regions.get(reg, 0) + 1
    wl_articles = []
    for a in arts:
        dom = registrable_domain(a.get("domain", ""))
        if dom in WHITELIST and a.get("url"):
            wl_articles.append({"url": a["url"], "title": a.get("title", "").strip(), "outlet": dom})
        if len(wl_articles) >= 6:
            break
    wl = {d: c for d, c in outlets.items() if d in WHITELIST}
    ranked_outlets = sorted((wl or outlets).items(), key=lambda kv: kv[1], reverse=True)
    top_outlets = [d for d, _ in ranked_outlets[:5]]
    return {"outlets": len(outlets), "countries": len(countries), "regions": regions,
            "top_outlets": top_outlets, "top_outlet": top_outlets[0] if top_outlets else None,
            "n": len(arts), "articles": wl_articles}


def source_breadth(query: str, timespan: str = "1w", maxrecords: int = 250) -> tuple[int, int]:
    """Distinct outlets + countries covering a query (spread signal, design §1.3)."""
    arts = _get_json(
        {"query": query, "mode": "artlist", "format": "json",
         "maxrecords": str(max(1, min(maxrecords, 250))), "timespan": timespan, "sort": "datedesc"}
    ).get("articles", []) or []
    outlets = {registrable_domain(a.get("domain", "")) for a in arts if a.get("domain")}
    countries = {a.get("sourcecountry") for a in arts if a.get("sourcecountry")}
    return len(outlets), len(countries)


def main() -> None:
    ap = argparse.ArgumentParser(description="GDELT discovery (Phase 0).")
    ap.add_argument("--vertical", default="geopolitics")
    ap.add_argument("--max", type=int, default=75, help="GDELT maxrecords (≤250)")
    ap.add_argument("--timespan", default="24h", help="e.g. 24h, 3d, 1w")
    ap.add_argument("--all-domains", action="store_true", help="disable whitelist filter")
    ap.add_argument("--out", help="write stubs to a JSON file")
    args = ap.parse_args()

    result = discover(
        vertical=args.vertical, max_records=args.max, timespan=args.timespan,
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
