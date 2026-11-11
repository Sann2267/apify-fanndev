"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

See CRAWLING_METHOD.md for the full recon behind every selector/decoding
scheme used here.
"""

import base64
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_domain(url_or_domain: str) -> str:
    value = url_or_domain.strip().lower()
    if "//" not in value:
        value = "https://" + value
    netloc = urlparse(value).netloc or value
    return netloc[4:] if netloc.startswith("www.") else netloc


def decode_bing_redirect(href: str) -> str:
    """Bing wraps every organic result href in a `bing.com/ck/a?...&u=`
    tracking redirect. The real destination is the `u` query param with
    a fixed 2-character `a1` prefix stripped, then base64url-decoded
    (confirmed live -- see CRAWLING_METHOD.md). Falls back to the raw
    href unchanged if it isn't in this shape (e.g. already a direct
    link)."""
    if "bing.com/ck/a" not in href:
        return href
    qs = parse_qs(urlparse(href).query)
    u = (qs.get("u") or [None])[0]
    if not u or not u.startswith("a1"):
        return href
    b64 = u[2:]
    b64 += "=" * (-len(b64) % 4)
    try:
        return base64.urlsafe_b64decode(b64).decode("utf-8", errors="replace")
    except (base64.binascii.Error, UnicodeDecodeError):
        return href


def extract_bing_results(html: str, query: str, target_domain: str | None) -> dict:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("li.b_algo")
    if not items:
        raise UnexpectedShape("No li.b_algo elements found -- Bing SERP shape has likely changed.")

    target_norm = normalize_domain(target_domain) if target_domain else None
    results = []
    target_rank = None
    for rank, item in enumerate(items, start=1):
        h2 = item.select_one("h2")
        a = h2.select_one("a") if h2 else None
        if a is None:
            continue
        raw_href = a.get("href") or ""
        real_url = decode_bing_redirect(raw_href)
        caption = item.select_one("div.b_caption p, p.b_lineclamp2, p.b_lineclamp3, p.b_lineclamp4")
        domain = normalize_domain(real_url) if real_url else None
        is_target = bool(target_norm and domain and (domain == target_norm or domain.endswith("." + target_norm)))
        if is_target and target_rank is None:
            target_rank = rank
        results.append(
            {
                "rank": rank,
                "title": a.get_text(strip=True),
                "url": real_url,
                "domain": domain,
                "snippet": caption.get_text(strip=True) if caption else None,
                "isTarget": is_target,
            }
        )

    return {
        "_input": query,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "query": query,
        "targetDomain": target_norm,
        "targetFound": target_rank is not None,
        "targetRank": target_rank,
        "resultCount": len(results),
        "results": results,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
