"""HTTP client for the Bahamas RGD's public "Company Search" API.

A plain JSON REST endpoint under `cars.rgd.gov.bs/api/public/` -- no
session/login/CAPTCHA gate for the free name-search tier (see
`constants.py`'s recon summary). `curl_cffi` is used for consistency with
the rest of the portfolio, not because any TLS/WAF gate was actually found.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix documented in `uganda-ursb-scraper/src/client.py` and
`botswana-cipa-scraper/src/client.py`: `curl_cffi`'s own exception hierarchy
(`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures.
"""

import logging
import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    API_BASE,
    DEFAULT_HEADERS,
    ENTITIES_HISTORY_PATH,
    ENTITIES_PATH,
    MAX_RETRIES,
    PAGE_SIZE,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)


class TooBroadError(Exception):
    """Raised when the API returns HTTP 200 with a genuinely empty (0-byte)
    body -- observed for short/very common query terms (see Gotcha 2 in
    constants.py). Distinct from a real "no matches" ([])."""


class BahamasRGDClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, url: str, params: dict):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.get(url, params=params)
                if r.status_code in (403, 429, 502, 503, 504):
                    last_exc = RuntimeError(f"HTTP {r.status_code} from {url}")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def search(self, name: str, include_history: bool = False) -> list[dict]:
        """Returns up to 3 best-matching entities (the free tier's hard cap
        -- see Gotcha 1 in constants.py). Raises `TooBroadError` if the query
        was too broad/common for the backend to answer (Gotcha 2)."""
        path = ENTITIES_HISTORY_PATH if include_history else ENTITIES_PATH
        params = {"name": name, "pageNo": 1, "pageSize": PAGE_SIZE}
        r = await self._with_retry(f"{API_BASE}{path}", params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {path}?name={name!r} -> HTTP {r.status_code}")
        if not r.content:
            raise TooBroadError(f"name={name!r} -> empty 0-byte body (too broad/common)")
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response shape for name={name!r}: {type(data)}")
        return data

    async def close(self):
        await self.session.close()
