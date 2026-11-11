"""HTTP client for GOJEP's public, stateless (no-login, no-CAPTCHA) tender
listing tables. See `constants.py` for the full recon summary.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix documented across this portfolio (`jamaica-coj-scraper`,
`djibouti-odpic-scraper`, etc.): `curl_cffi`'s own exception hierarchy
(`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures and lets them crash
the whole run instead of retrying/degrading to a per-item error record.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    AWARDED_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    OPENED_BIDS_URL,
    OPENED_FIXED_PARAMS,
    OPENED_URL,
    RETRY_DELAY_BASE_SECS,
    TLS_PROFILE,
)
from src.extractor import (
    extract_pager_prefix,
    extract_total_count,
    parse_awarded_page,
    parse_bidders_page,
    parse_opened_page,
)


def is_blocked(response) -> bool:
    return response.status_code in (403, 429, 503)


class GojepClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        # Discovered from page 1 of whichever listing is fetched first this
        # run, then reused for subsequent `-p=<n>` page requests -- see
        # constants.py "Pagination" note on why this isn't hard-coded.
        self._pager_prefix: dict[str, str | None] = {}

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE_SECS * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE_SECS * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {method} {url}: {last_exc!r}")

    async def _fetch_listing_page(
        self, key: str, base_url: str, fixed_params: dict, page: int, sort_field: str | None, sort_desc: bool
    ) -> tuple[str, int | None]:
        # The table-instance id prefix (`d-<digits>`) needed to address a
        # specific page/sort must be read off a previous response from this
        # same table -- if we don't have it yet but this call needs it
        # (sorting, or page > 1), spend one throwaway plain GET to learn it
        # first. Cheap: happens at most once per (key, client instance).
        if (sort_field or page > 1) and key not in self._pager_prefix:
            warm = await self._with_retry("GET", base_url, params=fixed_params)
            if warm.status_code != 200:
                raise RuntimeError(f"GET {base_url} (pager warmup) -> HTTP {warm.status_code}")
            self._pager_prefix[key] = extract_pager_prefix(warm.text)
            if page == 1 and not sort_field:
                return warm.text, extract_total_count(warm.text)

        params = dict(fixed_params)
        prefix = self._pager_prefix.get(key)
        if prefix:
            if page > 1:
                params[f"{prefix}-p"] = page
            if sort_field:
                params[f"{prefix}-s"] = sort_field
                # Confirmed empirically (2026-08-27): o=2 is ascending
                # (A-Z/oldest-first), o=1 is descending -- the reverse of
                # what the UI's sort-arrow icon order would suggest.
                params[f"{prefix}-o"] = "1" if sort_desc else "2"
        r = await self._with_retry("GET", base_url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {base_url} page={page} -> HTTP {r.status_code}")
        html = r.text
        if key not in self._pager_prefix:
            self._pager_prefix[key] = extract_pager_prefix(html)
        return html, extract_total_count(html)

    async def fetch_opened_page(
        self, page: int, sort_field: str | None = None, sort_desc: bool = True
    ) -> tuple[list[dict], int | None]:
        html, total = await self._fetch_listing_page(
            "opened", OPENED_URL, OPENED_FIXED_PARAMS, page, sort_field, sort_desc
        )
        return parse_opened_page(html), total

    async def fetch_awarded_page(
        self, page: int, sort_field: str | None = None, sort_desc: bool = True
    ) -> tuple[list[dict], int | None]:
        html, total = await self._fetch_listing_page("awarded", AWARDED_URL, {}, page, sort_field, sort_desc)
        return parse_awarded_page(html), total

    async def fetch_bidders(self, resource_id: str) -> list[dict]:
        r = await self._with_retry("GET", OPENED_BIDS_URL, params={"resourceId": resource_id})
        if r.status_code != 200:
            raise RuntimeError(f"GET {OPENED_BIDS_URL} resourceId={resource_id} -> HTTP {r.status_code}")
        return parse_bidders_page(r.text)

    async def close(self):
        await self.session.close()
