"""HTTP transport for storeleads.app report pages.

The site answers plain HTTP with no challenge, so the client is thin: retry,
block detection, and one hard rule -- a 404 is definitive. Storeleads returns
its 20 KB "Not Found" page for any platform slug it does not publish, and
retrying that four times only wastes requests.

One page was observed to hang past 30 s during recon while its siblings
returned in under a second. The timeout is therefore generous and the retry
loop treats a timeout as transient rather than as a block.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

BLOCK_MARKERS = (b"Just a moment", b"challenge-platform", b"cf-mitigated", b"Access denied")


class ReportNotFound(Exception):
    """404 -- no report published for that platform slug."""


class BlockedUpstream(Exception):
    """Challenge or block that survived the retries."""


def _looks_blocked(response) -> bool:
    if response.status_code in (403, 429, 503):
        return True
    head = response.content[:4096] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class StoreLeadsClient:
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
            raise ReportNotFound(f"404 for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}")
        html = r.text or ""
        if len(html) < 2000:
            raise BlockedUpstream(f"suspiciously small body ({len(html)} bytes) for {url}")
        return html

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 404:
                    return r
                if _looks_blocked(r):
                    last_exc = BlockedUpstream(f"blocked response {r.status_code} for {url}")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- timeouts included, all retryable
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise BlockedUpstream(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
