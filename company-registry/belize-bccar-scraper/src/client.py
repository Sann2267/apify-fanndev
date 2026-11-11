"""HTTP client for BCCAR's public "Search for a Business Entity" API.

No TLS/WAF gate exists on this endpoint (see constants.py) -- the only thing
a caller needs to get right is the lightweight session bootstrap: GET the
search page once to receive a session cookie and an NCSRF token (read from
a hidden `<input>` on the page), then send that token back as an `NCSRF`
request header on every POST to the list endpoint.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as `uganda-ursb-scraper/src/client.py` and other actors in this project:
`curl_cffi`'s own exception hierarchy (`CurlError` -> `OSError`) does NOT
inherit from Python's builtin `ConnectionError`/`TimeoutError` despite
sharing class names, so a narrower except list silently misses real
transient failures.
"""

import asyncio
import logging
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    BOOTSTRAP_PATH,
    DEFAULT_HEADERS,
    MAX_PAGES_PER_QUERY,
    MAX_RETRIES,
    PAGE_LIMIT,
    RETRY_DELAY_BASE,
    SEARCH_PATH,
)

log = logging.getLogger(__name__)

NCSRF_RE = re.compile(r'name="NCSRF"\s+value="([^"]*)"')


class BCCARClient:
    def __init__(self, proxy_url: str | None = None):
        self.session = AsyncSession(
            impersonate="chrome124",
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._ncsrf: str | None = None

    async def _bootstrap(self):
        """GET the public search page to obtain a session cookie + NCSRF
        token (read from the page's own hidden #csrf input, matching the
        real app's own `jcall` logic in js/lib.js -- see constants.py)."""
        r = await self.session.get(f"{BASE_URL}{BOOTSTRAP_PATH}")
        if r.status_code != 200:
            raise RuntimeError(f"GET {BOOTSTRAP_PATH} -> HTTP {r.status_code}")
        m = NCSRF_RE.search(r.text)
        if not m:
            raise RuntimeError("Could not find NCSRF token on search page -- page shape may have changed")
        self._ncsrf = m.group(1)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (403, 429, 503):
                    last_exc = RuntimeError(f"HTTP {r.status_code}")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def _search_page(self, filters: dict, page: int, page_size: int, _retried_bootstrap: bool = False) -> dict:
        if not self._ncsrf:
            await self._bootstrap()

        body = {"PageSize": page_size, "PageNumber": page, **filters}
        r = await self._with_retry(
            "POST",
            f"{BASE_URL}{SEARCH_PATH}",
            json=body,
            headers={"NCSRF": self._ncsrf, "Content-Type": "application/json"},
        )
        # A missing/stale NCSRF token gets a 303 redirect to a fallback app
        # route instead of a clean 4xx (see constants.py) -- treat that (or
        # any non-200, or a 200 body missing the expected "Result" key) as
        # "session needs a fresh bootstrap", retried once.
        ok = r.status_code == 200
        data = None
        if ok:
            try:
                data = r.json()
            except Exception:
                ok = False
        if not ok or "Result" not in data or "Map" not in data:
            if _retried_bootstrap:
                raise RuntimeError(f"POST {SEARCH_PATH} -> HTTP {r.status_code}, unexpected body shape after re-bootstrap")
            self._ncsrf = None
            return await self._search_page(filters, page, page_size, _retried_bootstrap=True)
        return data

    async def search_all(self, filters: dict, max_results: int) -> tuple[list[dict], int]:
        """Pages through `list/public/business.json` until `max_results` is
        reached, `TotalRecordCount` is exhausted, or a short/empty page is
        seen. Returns `(items, total_record_count)` -- items are plain
        `{field: value}` dicts built by zipping each response's `Map` column
        names onto each `Records` row (see constants.py for the response
        shape). `TotalRecordCount` was confirmed reliable during recon, so it
        drives the stop condition directly (unlike some other registries in
        this project where server-reported totals can't be trusted).
        """
        page_size = min(PAGE_LIMIT, max_results) or 1
        items: list[dict] = []
        total = 0
        page = 1
        while len(items) < max_results and page <= MAX_PAGES_PER_QUERY:
            data = await self._search_page(filters, page, page_size)
            total = data.get("TotalRecordCount", 0)
            columns = data.get("Map") or []
            rows = data.get("Records") or []
            items.extend(dict(zip(columns, row)) for row in rows)
            if len(rows) < page_size or len(items) >= total:
                break
            page += 1
        return items[:max_results], total

    async def close(self):
        await self.session.close()
