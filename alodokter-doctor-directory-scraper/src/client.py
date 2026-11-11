"""HTTP client wrapper -- retry, block detection, ?page pagination."""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SOFT_404_MAX_BYTES,
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
    """The specialty/doctor slug does not exist upstream.

    Note this is raised for a **200** response too: an unknown specialty
    slug returns HTTP 200 with a ~17 KB shell rather than a 404 (verified
    against dokter-rehabilitasi-medik / dokter-anestesi /
    dokter-kulit-dan-kelamin), so size is the tell.
    """


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class AlodokterClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=45,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_html(self, path: str, params: dict | None = None, check_soft_404: bool = False) -> str:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        r = await self._with_retry("GET", url, params=params)
        if r.status_code == 404:
            raise NotFound(url)
        if check_soft_404 and len(r.content) < SOFT_404_MAX_BYTES:
            raise NotFound(f"{url} (soft 404: {len(r.content)} bytes)")
        return r.text

    async def paginate(self, path: str, max_items: int, parse_listing) -> list[dict]:
        """Walk ?page=1..N. A page past the end returns 200 with an empty
        ItemList, so "no doctors parsed" is the stop signal; the seen-slug
        guard is belt-and-braces against a future clamp-to-page-1 change."""
        items: list[dict] = []
        page = 1
        seen: set[str] = set()
        while len(items) < max_items:
            html = await self.get_html(
                path, params={"page": page} if page > 1 else None, check_soft_404=(page == 1)
            )
            batch = parse_listing(html)
            if not batch:
                break
            fresh = [d for d in batch if d.get("profileUrl") not in seen]
            for d in fresh:
                seen.add(d.get("profileUrl"))
            if not fresh:
                break
            items.extend(fresh)
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
