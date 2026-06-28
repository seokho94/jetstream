"""Curated source registry (Phase 0 starter for the 300–500 target).

Single source of truth for the trusted-outlet whitelist AND the DB `source_registry`
(seeded by scripts.seed_sources). Fields per outlet: tier, country (ISO-3166 a2),
region_block (coverage axis), outlet_type, license_tier (body-storage governance).

WHITELIST (derived) scopes GDELT discovery + crawling; license_tier governs body
persistence (licensed=keep, crawl_ttl=keep then purge, metadata_only=no body).
"""
from __future__ import annotations

# (domain, outlet_name, tier, country, region_block, outlet_type, license_tier)
_ROWS: list[tuple[str, str, str, str, str, str, str]] = [
    # — wires / agencies (tier_1, licensed) —
    ("reuters.com", "Reuters", "tier_1", "GB", "Europe", "wire", "licensed"),
    ("apnews.com", "Associated Press", "tier_1", "US", "North America", "wire", "licensed"),
    ("afp.com", "Agence France-Presse", "tier_1", "FR", "Europe", "wire", "licensed"),
    ("bloomberg.com", "Bloomberg", "tier_1", "US", "North America", "wire", "licensed"),
    # — North America —
    ("nytimes.com", "The New York Times", "tier_1", "US", "North America", "newspaper", "crawl_ttl"),
    ("washingtonpost.com", "The Washington Post", "tier_1", "US", "North America", "newspaper", "crawl_ttl"),
    ("wsj.com", "The Wall Street Journal", "tier_1", "US", "North America", "newspaper", "crawl_ttl"),
    ("cnn.com", "CNN", "tier_1", "US", "North America", "broadcaster", "crawl_ttl"),
    ("nbcnews.com", "NBC News", "tier_2", "US", "North America", "broadcaster", "crawl_ttl"),
    ("abcnews.go.com", "ABC News", "tier_2", "US", "North America", "broadcaster", "crawl_ttl"),
    ("cbsnews.com", "CBS News", "tier_2", "US", "North America", "broadcaster", "crawl_ttl"),
    ("npr.org", "NPR", "tier_1", "US", "North America", "broadcaster", "crawl_ttl"),
    ("politico.com", "Politico", "tier_2", "US", "North America", "digital", "crawl_ttl"),
    ("axios.com", "Axios", "tier_2", "US", "North America", "digital", "crawl_ttl"),
    ("cnbc.com", "CNBC", "tier_2", "US", "North America", "broadcaster", "crawl_ttl"),
    ("newsweek.com", "Newsweek", "tier_3", "US", "North America", "digital", "crawl_ttl"),
    ("time.com", "TIME", "tier_2", "US", "North America", "digital", "crawl_ttl"),
    ("theatlantic.com", "The Atlantic", "tier_2", "US", "North America", "digital", "crawl_ttl"),
    ("latimes.com", "Los Angeles Times", "tier_2", "US", "North America", "newspaper", "crawl_ttl"),
    ("globeandmail.com", "The Globe and Mail", "tier_2", "CA", "North America", "newspaper", "crawl_ttl"),
    ("cbc.ca", "CBC", "tier_2", "CA", "North America", "broadcaster", "crawl_ttl"),
    # — Europe —
    ("bbc.com", "BBC", "tier_1", "GB", "Europe", "broadcaster", "crawl_ttl"),
    ("bbc.co.uk", "BBC", "tier_1", "GB", "Europe", "broadcaster", "crawl_ttl"),
    ("theguardian.com", "The Guardian", "tier_1", "GB", "Europe", "newspaper", "crawl_ttl"),
    ("ft.com", "Financial Times", "tier_1", "GB", "Europe", "newspaper", "crawl_ttl"),
    ("economist.com", "The Economist", "tier_1", "GB", "Europe", "digital", "crawl_ttl"),
    ("telegraph.co.uk", "The Telegraph", "tier_2", "GB", "Europe", "newspaper", "crawl_ttl"),
    ("independent.co.uk", "The Independent", "tier_2", "GB", "Europe", "digital", "crawl_ttl"),
    ("dw.com", "Deutsche Welle", "tier_2", "DE", "Europe", "broadcaster", "crawl_ttl"),
    ("spiegel.de", "Der Spiegel", "tier_2", "DE", "Europe", "digital", "crawl_ttl"),
    ("euronews.com", "Euronews", "tier_2", "FR", "Europe", "broadcaster", "crawl_ttl"),
    ("france24.com", "France 24", "tier_2", "FR", "Europe", "broadcaster", "crawl_ttl"),
    ("lemonde.fr", "Le Monde", "tier_2", "FR", "Europe", "newspaper", "crawl_ttl"),
    ("politico.eu", "Politico Europe", "tier_2", "BE", "Europe", "digital", "crawl_ttl"),
    ("euobserver.com", "EUobserver", "tier_3", "BE", "Europe", "digital", "crawl_ttl"),
    ("themoscowtimes.com", "The Moscow Times", "tier_3", "RU", "Europe", "digital", "crawl_ttl"),
    ("kyivindependent.com", "The Kyiv Independent", "tier_3", "UA", "Europe", "digital", "crawl_ttl"),
    # — MENA —
    ("aljazeera.com", "Al Jazeera", "tier_1", "QA", "MENA", "broadcaster", "crawl_ttl"),
    ("timesofisrael.com", "The Times of Israel", "tier_2", "IL", "MENA", "digital", "crawl_ttl"),
    ("haaretz.com", "Haaretz", "tier_2", "IL", "MENA", "newspaper", "crawl_ttl"),
    ("jpost.com", "The Jerusalem Post", "tier_2", "IL", "MENA", "newspaper", "crawl_ttl"),
    ("arabnews.com", "Arab News", "tier_3", "SA", "MENA", "newspaper", "crawl_ttl"),
    ("thenationalnews.com", "The National", "tier_3", "AE", "MENA", "newspaper", "crawl_ttl"),
    ("middleeasteye.net", "Middle East Eye", "tier_3", "GB", "MENA", "digital", "crawl_ttl"),
    # — Asia —
    ("scmp.com", "South China Morning Post", "tier_2", "HK", "Asia", "newspaper", "crawl_ttl"),
    ("japantimes.co.jp", "The Japan Times", "tier_2", "JP", "Asia", "newspaper", "crawl_ttl"),
    ("nikkei.com", "Nikkei Asia", "tier_2", "JP", "Asia", "newspaper", "crawl_ttl"),
    ("koreaherald.com", "The Korea Herald", "tier_3", "KR", "Asia", "newspaper", "crawl_ttl"),
    ("koreatimes.co.kr", "The Korea Times", "tier_3", "KR", "Asia", "newspaper", "crawl_ttl"),
    ("thehindu.com", "The Hindu", "tier_2", "IN", "Asia", "newspaper", "crawl_ttl"),
    ("indianexpress.com", "The Indian Express", "tier_2", "IN", "Asia", "newspaper", "crawl_ttl"),
    ("timesofindia.indiatimes.com", "The Times of India", "tier_3", "IN", "Asia", "newspaper", "crawl_ttl"),
    ("straitstimes.com", "The Straits Times", "tier_2", "SG", "Asia", "newspaper", "crawl_ttl"),
    ("channelnewsasia.com", "CNA", "tier_2", "SG", "Asia", "broadcaster", "crawl_ttl"),
    ("taipeitimes.com", "Taipei Times", "tier_3", "TW", "Asia", "newspaper", "crawl_ttl"),
    ("dawn.com", "Dawn", "tier_3", "PK", "Asia", "newspaper", "crawl_ttl"),
    # — Oceania —
    ("abc.net.au", "ABC Australia", "tier_2", "AU", "Oceania", "broadcaster", "crawl_ttl"),
    ("smh.com.au", "The Sydney Morning Herald", "tier_2", "AU", "Oceania", "newspaper", "crawl_ttl"),
    ("theage.com.au", "The Age", "tier_3", "AU", "Oceania", "newspaper", "crawl_ttl"),
    ("rnz.co.nz", "RNZ", "tier_3", "NZ", "Oceania", "broadcaster", "crawl_ttl"),
    # — Latin America —
    ("batimes.com.ar", "Buenos Aires Times", "tier_3", "AR", "Latin America", "digital", "crawl_ttl"),
    ("riotimesonline.com", "The Rio Times", "tier_3", "BR", "Latin America", "digital", "crawl_ttl"),
    ("mexiconewsdaily.com", "Mexico News Daily", "tier_3", "MX", "Latin America", "digital", "crawl_ttl"),
    # — Africa —
    ("mg.co.za", "Mail & Guardian", "tier_3", "ZA", "Africa", "newspaper", "crawl_ttl"),
    ("news24.com", "News24", "tier_3", "ZA", "Africa", "digital", "crawl_ttl"),
    ("theafricareport.com", "The Africa Report", "tier_3", "FR", "Africa", "digital", "crawl_ttl"),
    ("nation.africa", "Nation", "tier_3", "KE", "Africa", "newspaper", "crawl_ttl"),
]

SOURCES: dict[str, dict] = {
    domain: {
        "outlet_name": name, "tier": tier, "country": country,
        "region_block": region, "outlet_type": otype, "license_tier": lic,
    }
    for (domain, name, tier, country, region, otype, lic) in _ROWS
}

WHITELIST: set[str] = set(SOURCES)
