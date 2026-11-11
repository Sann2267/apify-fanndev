"""HTTP transport for the three official sources.

One session, per-host headers. The header split is not cosmetic: sending a
custom User-Agent to ``api.nasdaq.com`` makes the connection die with an HTTP/2
stream reset, because the UA then contradicts the impersonated TLS fingerprint.
SEC, by contrast, asks for a contact UA and accepts it.

Failure vocabulary kept deliberately narrow, because each source encodes
"nothing here" differently and conflating them would produce silent holes:

* ``NotPublished`` -- FINRA answers **403 AccessDenied** for a date whose file
  does not exist yet (verified: 2026-09-16 = 200/544 KB, 2026-09-17 = 403).
  That is a calendar fact, not a block, so it must never be retried as one.
* ``UpstreamNotFound`` -- SEC 404 for an unknown CIK.
* ``BlockedUpstream`` -- anything that still looks like a block after retries.

Nasdaq needs a fourth: it returns **HTTP 200 with a soft error inside the body**
(``status.rCode = 400`` for an unknown symbol, ``data = null`` plus a ``message``
for a non-Nasdaq listing). Callers therefore read the parsed body, not the
status code -- see ``get_nasdaq``.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    MAX_RETRIES,
    NASDAQ_HEADERS,
    RETRY_DELAY_BASE,
    SEC_HEADERS,
    TLS_PROFILE,
)

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"Request Rate Threshold Exceeded",  # SEC's own rate-limit page
)


class NotPublished(Exception):
    """The file exists in the schedule but has not been published yet."""


class UpstreamNotFound(Exception):
    """404 -- the identifier does not exist upstream."""


class BlockedUpstream(Exception):
    """Rate limited or challenged, and retries did not clear it."""


def _looks_blocked(response) -> bool:
    if response.status_code in (429, 503):
        return True
    head = response.content[:4096] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class MarketDataClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=45,
        )
        # SEC's fair-access policy is a rate ceiling, so SEC calls are serialised
        # through a semaphore rather than left to the caller's concurrency.
        self._sec_gate = asyncio.Semaphore(4)

    async def get_nasdaq(self, url: str) -> dict:
        """Return Nasdaq's parsed body. Soft errors stay in the body for the
        caller to interpret -- see module docstring."""
        r = await self._with_retry("GET", url, headers=NASDAQ_HEADERS)
        if r.status_code == 404:
            raise UpstreamNotFound(f"404 for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}: {r.text[:200]!r}")
        try:
            return r.json()
        except Exception as e:  # noqa: BLE001 -- any decode failure is a shape change
            raise BlockedUpstream(f"non-JSON answer from {url}: {r.text[:200]!r}") from e

    async def get_finra(self, url: str) -> str:
        """Return a FINRA pipe-delimited file as text."""
        r = await self._with_retry("GET", url, headers={"Accept": "text/plain,*/*"})
        if r.status_code in (403, 404):
            raise NotPublished(
                f"FINRA has not published {url} (HTTP {r.status_code}). Files appear "
                f"with a 1-2 day lag and never exist for weekends or market holidays."
            )
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}")
        return r.text or ""

    async def get_sec(self, url: str, params: dict | None = None) -> dict:
        async with self._sec_gate:
            r = await self._with_retry("GET", url, headers=SEC_HEADERS, params=params)
        if r.status_code == 404:
            raise UpstreamNotFound(f"404 for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}: {r.text[:200]!r}")
        try:
            return r.json()
        except Exception as e:  # noqa: BLE001
            raise BlockedUpstream(f"non-JSON answer from {url}: {r.text[:200]!r}") from e

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (403, 404):
                    return r  # definitive for these sources; never retried
                if _looks_blocked(r):
                    last_exc = BlockedUpstream(f"blocked response {r.status_code} for {url}")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are retryable
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise BlockedUpstream(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
