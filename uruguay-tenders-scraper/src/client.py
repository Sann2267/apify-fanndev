"""HTTP client wrapper for ARCE's public OCDS RSS/record/release endpoints.

No login, no CSRF handshake, no API key -- see CRAWLING_METHOD.md. The RSS
feed returns plain XML; `record` and any release link return plain JSON.
"""

import asyncio
import re
import xml.etree.ElementTree as ET

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    HEADERS,
    MAX_RETRIES,
    RECORD_ENDPOINT,
    RETRY_DELAY_BASE,
    RSS_LATEST,
    RSS_MONTH,
    TLS_PROFILE,
)

_TITLE_RE = re.compile(r"id_compra:(\d+),release_id:(.+)")


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


class RecordNotFound(Exception):
    """A record GET for a specific id_compra came back 404 -- no such purchase."""


async def _get(url: str, proxy_url: str | None = None):
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            r = await session.get(url, headers=HEADERS)
            if r.status_code == 404:
                raise RecordNotFound(url)
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"GET {url} returned {r.status_code} ({len(r.content)} bytes)")
            return r
        except RecordNotFound:
            raise
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError (raised on
            # a failed proxy CONNECT tunnel, DNS failure, TLS handshake error,
            # etc.) does NOT inherit from Python's builtin ConnectionError --
            # its MRO is RequestException -> CurlError -> OSError, a parallel
            # hierarchy. Both are caught explicitly, per the portfolio-wide
            # Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


def _parse_rss_items(xml_text: str) -> list[dict]:
    """Parses the RSS feed into flat release-event rows. Raises FetchFailed
    (not silently returning []) if the feed's own <item> shape has changed in
    a way this parser doesn't recognize."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise FetchFailed(f"RSS feed returned unparseable XML: {e!r}") from e

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        m = _TITLE_RE.match(title)
        if not m:
            raise FetchFailed(f"RSS <item><title> did not match the expected 'id_compra:N,release_id:X' shape: {title!r}")
        id_compra, release_id = m.group(1), m.group(2)
        items.append(
            {
                "idCompra": int(id_compra),
                "releaseId": release_id,
                "pubDate": (item.findtext("pubDate") or "").strip() or None,
                "releaseUrl": (item.findtext("link") or "").strip() or None,
                "eventType": (item.findtext("category") or "").strip() or None,
                "guid": (item.findtext("guid") or "").strip() or None,
            }
        )
    return items


async def fetch_rss(year: int | None, month: int | None, proxy_url: str | None = None) -> list[dict]:
    """Fetches one RSS window: the platform-wide latest 500 releases (no
    year/month), or every release published in one calendar month (both
    required together -- year-only 404s upstream, see CRAWLING_METHOD.md).
    Always newest-first."""
    if year and month:
        url = RSS_MONTH.format(year=year, month=month)
    else:
        url = RSS_LATEST
    r = await _get(url, proxy_url=proxy_url)
    return _parse_rss_items(r.text)


async def fetch_record(id_compra: int, proxy_url: str | None = None) -> dict:
    """Fetches the purchase-level record package for one id_compra. This is a
    *linked* OCDS record package -- `records[0].releases` is a list of
    {url, date, tag} references, not full release content inline (contrast
    Ecuador SERCOP's compiled record). Raises RecordNotFound on upstream 404
    (confirmed live: an unknown id_compra returns 404 with a JSON error
    body, not a 200 empty shell)."""
    url = RECORD_ENDPOINT.format(id_compra=id_compra)
    try:
        r = await _get(url, proxy_url=proxy_url)
    except RecordNotFound:
        raise RecordNotFound(id_compra) from None
    try:
        data = r.json()
    except ValueError as e:
        raise FetchFailed(f"record id_compra={id_compra} returned non-JSON body: {e!r}") from e

    records = data.get("records")
    if not isinstance(records, list) or not records:
        raise RecordNotFound(id_compra)
    return data


async def fetch_release_by_url(url: str, proxy_url: str | None = None) -> dict:
    """Follows one release link (as returned verbatim by `fetch_record` or
    `fetch_rss`) and returns its full release-package JSON. Upgrades a plain
    http:// link to https:// -- both work, but this actor's own outbound
    requests otherwise stay on https throughout."""
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    r = await _get(url, proxy_url=proxy_url)
    try:
        data = r.json()
    except ValueError as e:
        raise FetchFailed(f"release {url} returned non-JSON body: {e!r}") from e
    releases = data.get("releases")
    if not isinstance(releases, list) or not releases:
        raise FetchFailed(f"release {url} response missing a non-empty 'releases' list -- keys seen: {list(data.keys())}")
    return data
