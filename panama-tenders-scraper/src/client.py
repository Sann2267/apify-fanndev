"""HTTP client for Panama DGCP's OCDS API
(`ocdsv2dev.panamacompraencifras.gob.pa/api/v1/*`).

No WAF, no CAPTCHA, no TLS-fingerprint gate observed during recon -- plain
`nginx` serving an Angular app's backend API. `curl_cffi` `chrome124` is used
for portfolio-wide consistency. See `constants.py`'s module docstring for the
full recon writeup, including the two real quirks handled here:
`verify=False` (server-side incomplete TLS cert chain) and an explicit
`Accept: application/json` header (otherwise the Angular catch-all route
returns its `index.html` shell instead of JSON).

The retry loop wraps ALL request calls broadly: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures (portfolio-wide
Babak 22b fix) -- see `main.py`.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RECORD_DETAIL_URL,
    RECORDS_URL,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A request completed (no exception) but returned an unexpected non-200,
    non-404 status or an empty body -- treated as retryable up to
    MAX_RETRIES, then raised."""


class PanamaComprasClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
            # ocdsv2dev.panamacompraencifras.gob.pa serves an incomplete
            # certificate chain (missing intermediate) -- see constants.py
            # module docstring. No workaround short of skipping verification.
            verify=False,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _request(self, url: str):
        """GET with retries. A 404 is returned as-is (NOT retried) -- for
        this API it's a well-formed "no such ocid" JSON response, not a
        transient failure signal. Any other non-200 or a network exception
        is retried with exponential backoff."""
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request("GET", url)
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue
            if r.status_code == 200 and r.content:
                return r
            if r.status_code == 404:
                return r  # caller decides -- a well-formed "not found"
            last_exc = FetchFailed(f"GET {url} -> HTTP {r.status_code}, {len(r.content)} bytes")
            await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for GET {url}: {last_exc!r}")

    async def fetch_records_page(self, url: str | None = None) -> dict:
        """Fetches one page of the `/api/v1/records` feed -- the very first
        page if `url` is `None`/falsy, or a specific `links.next` cursor URL
        carried over from a prior page (or a prior run's `startCursor`
        input)."""
        r = await self._request(url or RECORDS_URL)
        if r.status_code != 200:
            raise RuntimeError(f"unexpected HTTP {r.status_code} fetching records page {url or RECORDS_URL}")
        return json.loads(r.content.decode("utf-8"))

    async def fetch_record(self, ocid: str) -> dict | None:
        """Fetches one tender by its OCDS `ocid`. Returns `None` (not an
        exception) when the API cleanly reports the ocid doesn't exist
        (HTTP 404) -- that's a legitimate "not found" outcome for the caller
        to turn into an `_error: not_found` record, not a transient/blocked
        signal."""
        url = RECORD_DETAIL_URL.format(ocid=ocid)
        r = await self._request(url)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise RuntimeError(f"unexpected HTTP {r.status_code} fetching record {ocid!r}")
        return json.loads(r.content.decode("utf-8"))

    async def close(self):
        await self.session.close()
