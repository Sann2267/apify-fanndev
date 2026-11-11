"""HTTP client for ProcureTT's public, stateless (no-login, no-CAPTCHA)
GravityView listing/detail tables. See `constants.py` for the full recon
summary.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix documented across this portfolio (`jamaica-tenders-scraper`,
`ghana-tenders-scraper`, etc.): `curl_cffi`'s own exception hierarchy
(`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures and lets them crash the
whole run instead of retrying/degrading to a per-item error record.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    NOTICE_TYPES,
    RETRY_DELAY_BASE_SECS,
    TLS_PROFILE,
)
from src.extractor import extract_pagination, parse_detail_page, parse_listing_page


def is_blocked(response) -> bool:
    return response.status_code in (403, 429, 503)


class ProcureTTClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

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

    async def fetch_listing_page(
        self, notice_type: str, page: int, sort_field: int | None, sort_desc: bool
    ) -> tuple[list[dict], int | None, int | None]:
        """Returns `(rows, total, page_size)`. `total`/`page_size` are
        `None` when the view renders no pagination widget (the whole
        register fit on one page) -- see `extract_pagination`."""
        cfg = NOTICE_TYPES[notice_type]
        url = f"{BASE_URL}{cfg['path']}"
        params = {}
        if page > 1:
            params["pagenum"] = page
        if sort_field is not None:
            params[f"sort[{sort_field}]"] = "desc" if sort_desc else "asc"

        r = await self._with_retry("GET", url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {url} page={page} -> HTTP {r.status_code}")
        html = r.text
        rows = parse_listing_page(html, cfg["expected_labels"])
        total, page_size = extract_pagination(html)
        return rows, total, page_size

    async def fetch_detail(self, notice_type: str, entry_id: str) -> dict:
        cfg = NOTICE_TYPES[notice_type]
        url = f"{BASE_URL}{cfg['path']}entry/{entry_id}/"
        r = await self._with_retry("GET", url)
        if r.status_code != 200:
            raise RuntimeError(f"GET {url} -> HTTP {r.status_code}")
        return parse_detail_page(r.text)

    async def close(self):
        await self.session.close()
