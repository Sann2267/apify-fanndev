"""HTTP client wrapper -- retry, block detection, cursor pagination.

No active WAF challenge was found on api.lu.ma during recon (see
CRAWLING_METHOD.md) -- Cloudflare fronts the domain but every endpoint
used here returns clean JSON 200s to a plain request with no TLS
impersonation ladder, no warmup, and no cookies. Retry/backoff scaffolding
is kept anyway per portfolio convention, and to smooth over transient
network errors.
"""

import asyncio
import json

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
    b"Pardon Our Interruption",
]


class NotFound(Exception):
    """The slug/URL does not resolve to any event or calendar -- HTTP 404."""


class InvalidRequest(Exception):
    """The API rejected the request shape/params (HTTP 400) -- a real
    bad-input bug in this actor, not a transient condition, so it must
    NOT be retried."""


class NotSignedIn(Exception):
    """Endpoint requires an authenticated session (HTTP 401) -- out of
    scope per this project's "No Login" constraint (e.g.
    /search/get-results, /event/get-guest-list -- see CRAWLING_METHOD.md)."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class LumaClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_json(self, path: str, params: dict | None = None) -> dict:
        r = await self._with_retry("GET", f"{BASE_URL}{path}", params=params)
        if r.status_code == 404:
            raise NotFound(r.text[:300])
        if r.status_code == 400:
            raise InvalidRequest(r.text[:800])
        if r.status_code == 401:
            raise NotSignedIn(r.text[:300])
        try:
            return json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Non-JSON response from {path}: {r.text[:300]!r}") from e

    async def resolve_url(self, slug: str) -> dict:
        """GET /url?url=<slug> -- the same universal resolver luma.com's
        own frontend uses for every lu.ma/<slug> route. Returns
        {"kind": "event"|"calendar", "data": {...}}. `data` for an event
        is the identical shape as GET /event/get?event_api_id=<id>, so no
        second call is needed for a single-event/single-calendar lookup."""
        return await self.get_json("/url", params={"url": slug})

    async def paginate_calendar(self, calendar_api_id: str, period: str, max_items: int) -> list[dict]:
        """Follow `has_more` / `next_cursor` on /calendar/get-items until
        `max_items` is reached or the upstream list is exhausted."""
        items: list[dict] = []
        cursor = None
        while len(items) < max_items:
            params = {"calendar_api_id": calendar_api_id, "period": period}
            if cursor:
                params["pagination_cursor"] = cursor
            data = await self.get_json("/calendar/get-items", params=params)
            batch = data.get("entries") or []
            if not batch:
                break
            items.extend(batch)
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return items[:max_items]

    async def paginate_discover(
        self, latitude: str | None, longitude: str | None, max_items: int
    ) -> list[dict]:
        """Follow `has_more` / `next_cursor` on /discover/get-paginated-events
        until `max_items` is reached or the upstream list is exhausted.
        With no geo params, results are personalized by the request's own
        IP (confirmed via __NEXT_DATA__'s top-level `countryCode`/
        `latitude`/`longitude` on luma.com's own SSR page) -- so Apify
        proxy country selection also steers this mode's results."""
        items: list[dict] = []
        cursor = None
        while len(items) < max_items:
            params = {}
            if latitude:
                params["geo_latitude"] = latitude
            if longitude:
                params["geo_longitude"] = longitude
            if cursor:
                params["pagination_cursor"] = cursor
            data = await self.get_json("/discover/get-paginated-events", params=params)
            batch = data.get("entries") or []
            if not batch:
                break
            items.extend(batch)
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
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
