"""HTTP client wrapper -- retry, block detection, ?page pagination."""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    PARAM_PAGE,
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
    """The requested profile does not exist -- HTTP 404."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class SintaClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_html(self, path: str, params: dict | None = None) -> str:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        r = await self._with_retry("GET", url, params=params)
        if r.status_code == 404:
            raise NotFound(url)
        return r.text

    async def paginate(
        self, path: str, params: dict, max_items: int, parse_rows, id_key: str
    ) -> tuple[list[dict], dict]:
        """Walk ?page=1..N. Returns (rows, totals) where totals carries the
        upstream "Page X of Y | Total Records Z" counters from the first
        page, so a caller can see how much is available beyond max_items."""
        from src.extractor import parse_totals

        items: list[dict] = []
        page = 1
        seen: set[str] = set()
        totals: dict = {}
        while len(items) < max_items:
            html = await self.get_html(path, params={**params, PARAM_PAGE: page})
            if page == 1:
                totals = parse_totals(html)
            rows = parse_rows(html)
            if not rows:
                break
            fresh = [r for r in rows if r.get(id_key) not in seen]
            for r in fresh:
                seen.add(r.get(id_key))
            if not fresh:
                break
            items.extend(fresh)
            total_pages = totals.get("totalPages")
            if total_pages and page >= total_pages:
                break
            page += 1
        return items[:max_items], totals

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
