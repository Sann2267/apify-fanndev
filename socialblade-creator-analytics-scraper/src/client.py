"""HTTP client wrapper -- retry and block detection.

Cloudflare fronts socialblade.com but served no challenge to a `curl_cffi`
chrome request during recon (YouTube, TikTok, Twitch, Instagram profiles
and the YouTube top-100 list all returned full server-rendered payloads).
Block detection stays live so a future challenge surfaces as an error
rather than as an empty `__NEXT_DATA__` parse.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
]


class NotFound(Exception):
    """The profile/list does not exist upstream -- HTTP 404 or 400."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class SocialBladeClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=45,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_html(self, path: str) -> str:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        r = await self._with_retry("GET", url)
        # 400 is upstream's answer to an unsupported list size
        # (/youtube/top/50, /youtube/top/250), not a transient fault.
        if r.status_code in (400, 404):
            raise NotFound(f"{url} (HTTP {r.status_code})")
        return r.text

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (400, 404):
                    return r
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
