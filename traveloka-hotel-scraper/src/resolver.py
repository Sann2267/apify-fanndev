"""Turn whatever the user supplied into Traveloka hotel IDs.

Three ways in, in increasing breadth:

* a property URL or a bare numeric ID -- exact, no request needed;
* a text query -- `/v1/hotel/autocomplete` answers with the properties whose
  names match, which is how you assemble a competitor set;
* a sitemap sweep -- `robots.txt` allows `/*/sitemap/**`, and the hotel-detail
  index fans out to ~520 leaf sitemaps of 5,000 property URLs each.

There is deliberately no "every hotel in city X" path: that is
`/v2/hotel/searchList`, and it is behind an AWS WAF CAPTCHA.
"""

from __future__ import annotations

import gzip
import logging
import re
from urllib.parse import urlsplit

from curl_cffi import requests

from src.constants import (
    AUTOCOMPLETE,
    AUTOCOMPLETE_GROUPS,
    HOTEL_ROW_TYPES,
    REFERER_SEARCH,
    SITEMAP_INDEX,
    SITEMAP_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Traveloka property URLs end in `-<numeric id>`; the slug before it is cosmetic.
_URL_ID = re.compile(r"-(\d{3,})(?:[/?#]|$)")
_BARE_ID = re.compile(r"^\d{3,}$")
_LOC_TAG = re.compile(r"<loc>([^<]+)</loc>")


def hotel_id_from_url(value: str) -> str | None:
    """Extract the numeric property ID from a Traveloka URL or a bare ID."""
    value = (value or "").strip()
    if not value:
        return None
    if _BARE_ID.match(value):
        return value
    match = _URL_ID.search(urlsplit(value).path or value)
    return match.group(1) if match else None


def property_url(hotel_id: str, slug: str | None = None, locale: str = "en-id") -> str:
    """Rebuild a canonical property URL. The slug is optional for Traveloka."""
    tail = f"{slug}-{hotel_id}" if slug else hotel_id
    return f"https://www.traveloka.com/{locale}/hotel/indonesia/{tail}"


def _rows(payload: dict) -> list[dict]:
    """Flatten the autocomplete response, keeping each row's group name."""
    out: list[dict] = []
    for group in AUTOCOMPLETE_GROUPS:
        block = payload.get(group)
        if not isinstance(block, dict):
            continue
        for row in block.get("rows") or []:
            if isinstance(row, dict):
                out.append({**row, "_group": group})
    return out


async def resolve_query(client, query: str, limit: int, locale: str,
                        currency: str) -> tuple[list[dict], list[dict]]:
    """Return (property rows, geo rows) matching a free-text query."""
    path, domain = AUTOCOMPLETE
    data = {
        "query": query,
        "clientInterface": "desktop",
        "fields": [],
        "maxResult": max(limit, 10),
        "currency": currency,
    }
    payload = await client.call_async(path, domain, data, REFERER_SEARCH)
    rows = _rows(payload)
    hotels, geos = [], []
    for row in rows:
        row_type = (row.get("type") or "").upper()
        if row_type in HOTEL_ROW_TYPES and row.get("id"):
            hotels.append(row)
        elif row.get("id"):
            geos.append(row)
    logger.info("Autocomplete %r -> %d properties, %d places.",
                query, len(hotels), len(geos))
    return hotels[:limit], geos


def _fetch_xml(url: str, tls_profile: str, proxy_url: str | None) -> str:
    resp = requests.get(
        url, impersonate=tls_profile, timeout=SITEMAP_TIMEOUT,
        proxies=({"http": proxy_url, "https": proxy_url} if proxy_url else None),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"sitemap {url} returned HTTP {resp.status_code}")
    raw = resp.content
    # Leaf sitemaps are gzipped; CloudFront sometimes decompresses in transit.
    try:
        raw = gzip.decompress(raw)
    except (OSError, EOFError):
        pass
    return raw.decode("utf-8", "replace")


def sweep_sitemap(limit: int, tls_profile: str, proxy_url: str | None,
                  skip_leaves: int = 0) -> list[tuple[str, str]]:
    """Collect up to `limit` (hotel_id, slug) pairs from the hotel sitemaps."""
    index = _fetch_xml(SITEMAP_INDEX, tls_profile, proxy_url)
    leaves = _LOC_TAG.findall(index)
    logger.info("Hotel sitemap index lists %d leaf sitemaps.", len(leaves))

    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for leaf in leaves[skip_leaves:]:
        if len(found) >= limit:
            break
        try:
            body = _fetch_xml(leaf, tls_profile, proxy_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping sitemap %s: %s", leaf, exc)
            continue
        for url in _LOC_TAG.findall(body):
            hotel_id = hotel_id_from_url(url)
            if not hotel_id or hotel_id in seen:
                continue
            seen.add(hotel_id)
            slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
            slug = slug[: -(len(hotel_id) + 1)] if slug.endswith("-" + hotel_id) else ""
            found.append((hotel_id, slug))
            if len(found) >= limit:
                break
    logger.info("Sitemap sweep collected %d property IDs.", len(found))
    return found
