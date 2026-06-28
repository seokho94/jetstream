"""Body crawler (normalize stage, spec §4 stage 2).

Fetches + extracts article bodies for WHITELISTED domains only, with SSRF guards:
scheme allowlist, registrable-domain whitelist, private/loopback/reserved-IP
rejection, response-size cap, and redirect re-validation. Uses trafilatura for
main-content extraction. No API key required.

Run:  python -m pipeline.normalize.crawl <url>
"""
from __future__ import annotations

import ipaddress
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

from pipeline.ingest.gdelt import USER_AGENT, registrable_domain
from pipeline.sources import WHITELIST

try:
    import trafilatura
except ImportError:  # pragma: no cover
    trafilatura = None  # type: ignore

MAX_BYTES = 2_000_000  # 2 MB cap


def _host_is_public(host: str) -> bool:
    """Reject hosts that resolve to a private/loopback/reserved address (SSRF guard)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def is_crawlable(url: str) -> bool:
    s = urllib.parse.urlsplit(url)
    if s.scheme not in ("http", "https"):
        return False
    host = (s.hostname or "").lower()
    if not host or registrable_domain(host) not in WHITELIST:
        return False
    return _host_is_public(host)


def fetch_html(url: str, timeout: int = 15) -> str | None:
    if not is_crawlable(url):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (whitelist-guarded)
            final_host = urllib.parse.urlsplit(resp.geturl()).hostname or ""
            if registrable_domain(final_host) not in WHITELIST:
                return None  # redirected off the whitelist
            raw = resp.read(MAX_BYTES + 1)
    except (urllib.error.URLError, ValueError, TimeoutError, ConnectionError):
        return None
    return raw[:MAX_BYTES].decode("utf-8", "replace")


def extract_body(html: str, url: str = "") -> str | None:
    if trafilatura is None:
        return None
    return trafilatura.extract(html, url=url or None, favor_precision=True) or None


def crawl(url: str) -> dict | None:
    """Return {url, body, chars} for a whitelisted article, or None on any failure."""
    html = fetch_html(url)
    if not html:
        return None
    body = extract_body(html, url)
    if not body:
        return None
    return {"url": url, "body": body, "chars": len(body)}


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m pipeline.normalize.crawl <url>")
        return
    url = sys.argv[1]
    print("crawlable:", is_crawlable(url))
    result = crawl(url)
    if result:
        print(f"extracted {result['chars']} chars:")
        print(result["body"][:500])
    else:
        print("no body extracted")


if __name__ == "__main__":
    main()
