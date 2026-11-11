"""HTTP client wrapper -- retry, block detection, path-segment pagination."""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    PAGE_SIZE,
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
    """The category/company path does not exist -- HTTP 404."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class IndonesiaYPClient:
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
        if r.status_code == 404:
            raise NotFound(url)
        return r.text

    async def paginate_category(self, path_for_page, max_items: int, parse_cards) -> list[dict]:
        """Pagination is a **path segment** (`/category/restaurants/2`), not a
        query string. Both traps below were confirmed live on 2026-09-08 and
        both would loop forever without the duplicate check:

        * `?page=2` returns 200 and silently re-serves **page 1**
          (identical first two companies as the unpaged URL).
        * A page past the end (`/category/restaurants/99999`) also returns
          200 and re-serves **page 1** -- it never 404s and never empties.

        So the only reliable stop signals are "no cards", "short page", and
        "every company on this page was already seen".
        """
        items: list[dict] = []
        page = 1
        seen: set[str] = set()
        while len(items) < max_items:
            html = await self.get_html(path_for_page(page))
            cards = parse_cards(html)
            if not cards:
                break
            fresh = [c for c in cards if c.get("companyId") not in seen]
            for c in fresh:
                seen.add(c.get("companyId"))
            if not fresh:
                break
            items.extend(fresh)
            if len(cards) < PAGE_SIZE:
                break
            page += 1
        return items[:max_items]

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 404:
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
