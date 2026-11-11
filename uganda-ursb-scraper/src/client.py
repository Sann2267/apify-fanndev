"""HTTP client for URSB's public eRegistry "Name Search" API.

Unlike CIPA (Botswana) or PACRA (Zambia), URSB exposes a genuinely plain
JSON REST endpoint -- no session/view-tree/delta protocol to drive, just a
`GET` with query params. The only gate is the TLS handshake fingerprint (see
`constants.py`'s recon summary) -- `curl_cffi` clears it on the first try
with any modern Chrome/Edge/Safari profile.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as `botswana-cipa-scraper/src/client.py` and `guardian-nigeria-scraper/
src/client.py`: `curl_cffi`'s own exception hierarchy (`CurlError` ->
`OSError`) does NOT inherit from Python's builtin `ConnectionError`/
`TimeoutError` despite sharing class names, so a narrower except list
silently misses real transient failures and lets them crash the whole run
instead of retrying/degrading to a per-item error record.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    API_BASE,
    DEFAULT_HEADERS,
    MAX_PAGES_PER_QUERY,
    MAX_RETRIES,
    NAME_SEARCH_PATH,
    PAGE_LIMIT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
    b"Prohibited Access",  # URSB's own TLS-gate 403 body, see constants.py
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class PaginationTimeout(Exception):
    """A page fetch beyond the first page timed out -- treated as "stop
    paginating, keep what was already collected" (see Gotcha 3 in
    constants.py), not a fatal error."""


class URSBClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    last_exc = RuntimeError(f"HTTP {r.status_code} blocked/prohibited response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def _search_page(self, name: str, page: int, limit: int) -> dict:
        params = {"name": name, "page": page, "limit": limit}
        r = await self._with_retry("GET", f"{API_BASE}{NAME_SEARCH_PATH}", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {NAME_SEARCH_PATH}?name={name!r}&page={page} -> HTTP {r.status_code}")
        body = r.json()
        if "data" not in body or "content" not in body["data"]:
            raise RuntimeError(f"Unexpected name-search response shape: keys={list(body.keys())}")
        return body["data"]

    async def search_all(self, name: str, max_results: int) -> tuple[list[dict], bool]:
        """Pages through `name-search` until `max_results` is reached or a
        short/empty page is seen (the only reliable end-of-results signal --
        see Gotcha 1 in constants.py; the response's own `pagination` block
        cannot be trusted). Returns `(items, truncated_by_timeout)` -- the
        second value is True if a deep-pagination timeout (Gotcha 3) cut the
        run short of `max_results` while more pages may still exist.
        """
        limit = min(PAGE_LIMIT, max_results) or 1
        items: list[dict] = []
        page = 1
        truncated = False
        while len(items) < max_results and page <= MAX_PAGES_PER_QUERY:
            try:
                data = await self._search_page(name, page, limit)
            except RuntimeError as e:
                if page == 1:
                    raise  # first page must succeed, or the query is genuinely broken
                log.warning(f"page {page} fetch failed for {name!r}, stopping pagination early: {e!r}")
                truncated = True
                break
            content = data.get("content") or []
            items.extend(content)
            if len(content) < limit:
                break  # short page -- reliable end-of-results signal
            page += 1
        return items[:max_results], truncated

    async def close(self):
        await self.session.close()
