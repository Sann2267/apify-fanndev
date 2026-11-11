"""HTTP client wrapper -- retry, block detection, listing pagination.

Cloudflare fronts lawrato.com but served no challenge during recon (see
CRAWLING_METHOD.md): listing and profile pages both return full markup to
a plain `curl_cffi` chrome request. Block detection is kept live anyway --
if Cloudflare ever does turn on a challenge, `is_blocked` will catch the
interstitial instead of the parser silently emitting empty records.
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
    """The slug does not resolve to a profile/listing -- HTTP 404."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class LawRatoClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=45,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_html(self, path: str, params: dict | None = None) -> str:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        r = await self._with_retry("GET", url, params=params)
        if r.status_code == 404:
            raise NotFound(url)
        return r.text

    async def paginate_listing(self, path: str, max_items: int, parse_cards) -> list[dict]:
        """Walk ?page=1..N until `max_items` is reached or a page comes back
        short/empty.

        Upstream never 404s past the end -- ?page=999 returns 200 with a
        near-empty shell -- so the only reliable end signals are "0 cards"
        and "fewer cards than a full page".
        """
        from src.constants import PAGE_SIZE

        items: list[dict] = []
        page = 1
        seen_urls: set[str] = set()
        while len(items) < max_items:
            html = await self.get_html(path, params={"page": page} if page > 1 else None)
            cards = parse_cards(html)
            if not cards:
                break
            fresh = [c for c in cards if c.get("profileUrl") not in seen_urls]
            for c in fresh:
                seen_urls.add(c.get("profileUrl"))
            if not fresh:
                # same page served again (upstream clamping) -- stop rather
                # than loop forever
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
