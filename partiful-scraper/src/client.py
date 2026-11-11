"""HTTP client wrapper -- Partiful's public Next.js SSR pages.

No WAF was found on partiful.com during recon (see CRAWLING_METHOD.md) --
Vercel-hosted, and every page fetched here (event, host profile,
discover) returned a clean 200 to a plain curl_cffi request with an
ordinary Chrome impersonation profile, no warmup request, and no cookie
jar carried between calls. Retry/backoff scaffolding is kept anyway per
portfolio convention, and to smooth over transient network errors.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import BASE_URL, DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE
from src.extractor import extract_next_data

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
    b"Access Denied",
]


class NotFound(Exception):
    """The id/URL does not resolve to any event or host profile --
    Partiful's own Next.js /404 route (confirmed via the SSR payload's
    `page` field, not status code alone -- see CRAWLING_METHOD.md)."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class PartifulClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_page_props(self, path: str) -> dict:
        """GET a partiful.com page and return its
        __NEXT_DATA__.props.pageProps. Raises NotFound if the page
        resolved to Next.js's own /404 route."""
        r = await self._with_retry("GET", f"{BASE_URL}{path}")
        data = extract_next_data(r.text)
        if r.status_code == 404 or data.get("page") == "/404":
            raise NotFound(path)
        return data.get("props", {}).get("pageProps", {})

    async def get_event(self, event_id: str) -> dict:
        return await self.get_page_props(f"/e/{event_id}")

    async def get_host(self, user_id: str) -> dict:
        return await self.get_page_props(f"/u/{user_id}")

    async def get_discover(self) -> dict:
        return await self.get_page_props("/discover")

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
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
