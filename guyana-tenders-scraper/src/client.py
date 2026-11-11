"""HTTP client for eprocure.gov.gy's public, stateless (no-login, no-CAPTCHA)
Frappe JSON API. See `constants.py` for the full recon summary.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix documented across this portfolio (`trinidadtobago-tenders-scraper`,
`jamaica-tenders-scraper`, etc.): `curl_cffi`'s own exception hierarchy
(`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures and lets them crash the
whole run instead of retrying/degrading to a per-item error record.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    DETAIL_ENDPOINT,
    LIST_ENDPOINT,
    MAX_RETRIES,
    RETRY_DELAY_BASE_SECS,
    TLS_PROFILE,
)
from src.extractor import unwrap_frappe_response


def is_blocked(response) -> bool:
    return response.status_code in (403, 429, 503)


class GuyanaEprocureClient:
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
                # A Frappe 417 (structured ValidationError envelope, e.g.
                # "Project not found or not published") is a real, final
                # answer -- not a transient block -- so it's returned
                # straight through rather than retried.
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE_SECS * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE_SECS * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {method} {url}: {last_exc!r}")

    async def fetch_bid_opportunities(self) -> list[dict]:
        """Returns the complete current list of publicly advertised bid
        opportunities. No pagination exists upstream -- this is a single
        unpaginated call (see `constants.py`)."""
        r = await self._with_retry("GET", LIST_ENDPOINT)
        if r.status_code != 200:
            raise RuntimeError(f"GET {LIST_ENDPOINT} -> HTTP {r.status_code}: {r.text[:300]}")
        payload = json.loads(r.text)
        rows = unwrap_frappe_response(payload)
        if not isinstance(rows, list):
            raise RuntimeError(f"get_public_bid_opportunities returned non-list message: {type(rows)}")
        return rows

    async def fetch_project_advertisement(self, project_id: str) -> dict:
        r = await self._with_retry("GET", DETAIL_ENDPOINT, params={"project_id": project_id})
        # A 417 here is Frappe's own structured ValidationError (e.g.
        # unknown/unpublished project_id) -- treated as the final answer,
        # not a transient failure, and re-raised as-is for the caller to
        # translate via unwrap_frappe_response.
        payload = json.loads(r.text)
        return unwrap_frappe_response(payload)

    async def close(self):
        await self.session.close()
