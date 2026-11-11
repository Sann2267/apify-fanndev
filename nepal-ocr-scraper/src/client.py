"""HTTP client for OCR's public CAMIS company-search endpoint.

No WAF, no CAPTCHA, no TLS-fingerprint gate observed on `camis.ocr.gov.np`
during recon -- plain HTTP 200s with a standard gateway response, no
`cf-ray`/challenge markers across dozens of requests (specific queries,
broad queries, a garbage query, and one deliberately unbounded blank
query). `curl_cffi` `chrome124` is used anyway for portfolio-wide
consistency; a plain `requests`/`httpx` baseline was not separately
re-verified to also work here (recon started directly with `curl_cffi`, per
this project's default stack).

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as the sibling registry actors in this collection: `curl_cffi`'s own
exception hierarchy (`CurlError` -> `OSError`) does NOT inherit from
Python's builtin `ConnectionError`/`TimeoutError` despite sharing class
names, so a narrower except list silently misses real transient failures
and lets them crash the whole run instead of retrying/degrading to a
per-item error record.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, REQUEST_TIMEOUT, RETRY_DELAY_BASE, SEARCH_URL, TLS_PROFILE

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class OCRClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
            # camis.ocr.gov.np serves an incomplete certificate chain (missing
            # intermediate) -- a plain system-CA client (curl, browsers with
            # OS-level chain building/AIA fetching) tolerates it, but
            # curl_cffi's bundled cert store does not, and there is no
            # workaround short of skipping verification. Confirmed this is a
            # server misconfiguration, not a MITM/proxy artifact: identical
            # failure from a clean residential-network client with no proxy.
            verify=False,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, body: dict):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.post(SEARCH_URL, json=body)
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {SEARCH_URL}: {last_exc!r}")

    async def search_company(self, body: dict) -> dict:
        r = await self._with_retry(body)
        if r.status_code != 200:
            raise RuntimeError(f"POST {SEARCH_URL} -> HTTP {r.status_code}: {r.text[:300]!r}")
        try:
            return json.loads(r.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(f"Non-JSON response from {SEARCH_URL}: {e!r} body={r.text[:300]!r}") from e

    async def close(self):
        await self.session.close()
