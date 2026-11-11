"""HTTP client wrapper -- retry, block detection, feed fetch.

The feed host answered every recon request with a clean 200 and no
challenge, but it enforces one hard gate: the `x-fsign` header. A request
without it gets HTTP 401 and a 323-byte error body, which is why 401 is
treated as a configuration failure (raise immediately, do not retry) rather
than as a transient block -- retrying a missing header 4 times just wastes
4 requests.

An *empty* body (1 byte) is a normal upstream answer here, not an error:
Flashscore returns it for a detail feed that does not exist for that match
(e.g. lineups for a match that never published a lineup) and for a sport/day
combination with no fixtures. Callers get "" and decide what it means.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    FEED_BASE,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Access denied",
]


class FeedUnauthorized(Exception):
    """HTTP 401 -- the x-fsign header was missing or has been rotated
    upstream. Not retryable: every retry produces the same 401."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class FlashscoreClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_feed(self, feed_id: str) -> str:
        """Fetch one feed and return its raw delimited body ("" when the
        upstream has nothing for that feed -- see module docstring)."""
        r = await self._with_retry("GET", FEED_BASE + feed_id)
        if r.status_code == 401:
            raise FeedUnauthorized(
                f"401 for {feed_id} -- x-fsign rejected. The constant may have been "
                f"rotated upstream; re-read it from flashscore.com's bundle. Body: {r.text[:200]!r}"
            )
        if r.status_code == 404:
            return ""
        body = r.text or ""
        return "" if len(body.strip()) <= 1 else body

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 401:
                    return r
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- all network errors are retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
