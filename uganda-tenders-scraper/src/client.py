"""HTTP client for EGP Uganda (egpuganda.go.ug).

No TLS-fingerprint gate and no WAF was found on this target during recon
(see `constants.py`) -- `curl_cffi` is still used for portfolio consistency
and because it copes gracefully with a residential proxy in front of it,
but plain `requests`/`httpx` would also work here.

The retry loop wraps request calls in a broad `except Exception`, same
pattern as every other actor in this portfolio: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures.
"""

import asyncio
import logging
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    AJAX_HEADERS,
    ARCHIVED_BID_NOTICES_AJAX,
    BASE_URL,
    BID_NOTICES_PATH,
    BID_OPENING_DETAIL_PATH,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    NOTICE_DETAIL_PATH,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r'name="_token"[^>]*value="([^"]+)"')


class EGPUgandaClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._token: str | None = None
        self._bid_notices_html: str | None = None

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (429, 502, 503, 504):
                    last_exc = RuntimeError(f"HTTP {r.status_code} transient response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def _ensure_session(self):
        """Primes the CSRF token + session cookie (needed for the archived
        AJAX endpoint) by GETting `/bid-notices` once. Also caches that
        page's HTML so `fetch_latest_open_notices` doesn't need a second
        request."""
        if self._token is not None:
            return
        r = await self._with_retry("GET", f"{BASE_URL}{BID_NOTICES_PATH}")
        if r.status_code != 200:
            raise RuntimeError(f"GET {BID_NOTICES_PATH} -> HTTP {r.status_code}")
        m = TOKEN_RE.search(r.text)
        if not m:
            raise RuntimeError("Could not find CSRF _token on /bid-notices -- page shape may have changed")
        self._token = m.group(1)
        self._bid_notices_html = r.text

    async def fetch_bid_notices_page_html(self) -> str:
        await self._ensure_session()
        return self._bid_notices_html

    async def fetch_archived_bid_notices_page(
        self, start: int, length: int, financial_year: str | None = None
    ) -> dict:
        await self._ensure_session()
        data = {"_token": self._token, "draw": 1, "start": start, "length": length}
        if financial_year:
            data["is_category"] = financial_year
        r = await self._with_retry(
            "POST",
            f"{BASE_URL}{ARCHIVED_BID_NOTICES_AJAX}",
            data=data,
            headers=AJAX_HEADERS,
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {ARCHIVED_BID_NOTICES_AJAX} -> HTTP {r.status_code}")
        body = r.json()
        if "data" not in body:
            raise RuntimeError(f"Unexpected archived-notices response shape: keys={list(body.keys())}")
        return body

    async def fetch_notice_detail(self, notice_id: str) -> tuple[int, str]:
        await self._ensure_session()
        url = f"{BASE_URL}{NOTICE_DETAIL_PATH.format(notice_id=notice_id)}"
        r = await self._with_retry("GET", url)
        return r.status_code, r.text

    async def fetch_bid_opening_detail(self, notice_id: str) -> tuple[int, str]:
        """Opportunistic enrichment -- returns (200, html) if a bid-opening
        record exists for this notice, or (status, "") otherwise (a notice
        still open for bidding reliably returns HTTP 500 here, treated as
        "not available yet", not a fatal error)."""
        await self._ensure_session()
        url = f"{BASE_URL}{BID_OPENING_DETAIL_PATH.format(notice_id=notice_id)}"
        try:
            r = await self.session.request("GET", url)
        except Exception as e:  # noqa: BLE001
            log.warning(f"bid-opening-detail fetch failed for {notice_id}: {e!r}")
            return 0, ""
        if r.status_code != 200:
            return r.status_code, ""
        return 200, r.text

    async def close(self):
        await self.session.close()
