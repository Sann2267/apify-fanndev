"""HTTP transport for sales.bcpea.org.

The portal answered every recon request with a clean 200 and no challenge, so
this stays thin. Two behaviours are worth encoding:

* A property id that does not exist returns the portal's own **404 page**, and
  retrying it is waste -- ``PropertyNotFound`` is raised immediately, which
  matters for the range mode where missing ids are expected and normal.
* Every page carries the same ~400 KB filter shell. A body far smaller than
  that is not a valid page, so an unexpectedly small 200 is treated as a
  failure instead of being parsed into empty records.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

BLOCK_MARKERS = (b"Just a moment", b"challenge-platform", b"cf-mitigated", b"Access denied")
MIN_PAGE_BYTES = 20000


class PropertyNotFound(Exception):
    """No sale published under that id."""


class BlockedUpstream(Exception):
    """Blocked, challenged, or an unusable body after retries."""


def _looks_blocked(response) -> bool:
    if response.status_code in (403, 429, 503):
        return True
    head = response.content[:4096] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class BCPEAClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_html(self, url: str) -> str:
        r = await self._with_retry("GET", url)
        if r.status_code == 404:
            raise PropertyNotFound(f"404 for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}")
        html = r.text or ""
        if len(html) < MIN_PAGE_BYTES:
            raise BlockedUpstream(
                f"unexpectedly small body ({len(html)} bytes) for {url} -- the portal "
                f"normally serves 400 KB+, so this is not a usable page."
            )
        return html

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, allow_redirects=True, **kwargs)
                if r.status_code == 404:
                    return r
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
