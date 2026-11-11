"""HTTP client wrapper -- retry, block detection, page pagination.

No WAF was found on api.lelang.go.id during recon (see CRAWLING_METHOD.md):
every endpoint returns a clean JSON 200 to a plain request with no TLS
impersonation, no Origin/Referer, and no cookies. The retry/backoff and
block-detection scaffolding below is kept per portfolio convention and to
smooth over transient network errors -- the upstream is a government host
and does time out occasionally under load (observed once on
/landing-page/metadata during recon).
"""

import asyncio
import json

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
    b"Pardon Our Interruption",
]


class NotFound(Exception):
    """The lot ID does not resolve to any auction lot -- HTTP 404."""


class InvalidRequest(Exception):
    """The API rejected the request shape/params (HTTP 400) -- a real
    bad-input bug, not a transient condition, so it must NOT be retried.
    Known trigger: `namakategori=X` without the mandatory `[]` suffix."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class LelangClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_json(self, path: str, params: list | dict | None = None) -> dict:
        """`params` may be a list of (key, value) pairs so that the repeatable
        `namakategori[]` filter can be sent more than once."""
        r = await self._with_retry("GET", f"{BASE_URL}{path}", params=params)
        if r.status_code == 404:
            raise NotFound(r.text[:300])
        if r.status_code == 400:
            raise InvalidRequest(r.text[:800])
        try:
            return json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Non-JSON response from {path}: {r.text[:300]!r}") from e

    async def paginate(self, path: str, extra_params: list | None = None, max_items: int = 100) -> list[dict]:
        """Walk `page` 1..N until `max_items` is reached or the upstream list
        is exhausted. The API returns `totalItem`/`totalPage`/`perPage`, so
        the end is detected three ways (short page, empty page, page past
        totalPage) rather than trusting any single one."""
        items: list[dict] = []
        page = 1
        total_pages = None
        while len(items) < max_items:
            limit = min(PAGE_SIZE, max_items - len(items))
            params = [("page", page), ("limit", limit)]
            if extra_params:
                params.extend(extra_params)
            data = await self.get_json(path, params=params)
            batch = data.get("data") or []
            if not batch:
                break
            items.extend(batch)
            if total_pages is None:
                total_pages = data.get("totalPage")
            if len(batch) < limit:
                break
            if total_pages is not None and page >= total_pages:
                break
            page += 1
        return items[:max_items]

    async def get_list(self, path: str, params: list | None = None) -> list[dict]:
        """For the non-paginated reference endpoints (kategori, kpknl) and the
        fixed-size feed endpoints."""
        data = await self.get_json(path, params=params)
        payload = data.get("data")
        return payload if isinstance(payload, list) else []

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
