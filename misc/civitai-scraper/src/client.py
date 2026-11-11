"""HTTP client wrapper -- retry, block detection, pagination-following.

No active WAF challenge was found on civitai.com/api/v1 during recon (see
CRAWLING_METHOD.md) -- it is Civitai's own official, documented, public
REST API. Retry/backoff scaffolding is kept anyway per portfolio
convention, and to smooth over transient network errors.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_LIMIT,
    MAX_RETRIES,
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
    """A specific resource (e.g. a model ID) does not exist -- HTTP 404."""


class InvalidRequest(Exception):
    """The API rejected the request shape/params (HTTP 400, Zod
    validation error) -- a real bad-input bug in this actor, not a
    transient condition, so it must NOT be retried."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class CivitaiClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_json(self, url: str, params: dict | None = None) -> dict:
        r = await self._with_retry("GET", url, params=params)
        if r.status_code == 404:
            raise NotFound(r.text[:300])
        if r.status_code == 400:
            raise InvalidRequest(r.text[:800])
        try:
            return json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Non-JSON response from {r.url}: {r.text[:300]!r}") from e

    async def paginate(self, path: str, params: dict, max_items: int) -> list[dict]:
        """Follow `metadata.nextPage` (both cursor- and page-based
        connections use this same field name) until `max_items` is
        reached or the upstream list is exhausted."""
        items: list[dict] = []
        url = f"{BASE_URL}{path}"
        request_params = dict(params)
        request_params["limit"] = min(int(params.get("limit", MAX_LIMIT)), MAX_LIMIT)

        while url and len(items) < max_items:
            data = await self.get_json(url, params=request_params)
            batch = data.get("items") or []
            items.extend(batch)
            next_page = (data.get("metadata") or {}).get("nextPage")
            if not next_page or not batch:
                break
            url = next_page
            request_params = None  # nextPage is already a full URL with its own query string

        return items[:max_items]

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
