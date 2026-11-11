"""HTTP client wrapper for gov.sr's public WordPress REST API.

No login, no CSRF handshake needed to read -- see constants.py for the full
recon summary. Every call here is a plain GET against a public REST route;
the same requests any browser tab issues just by visiting the corresponding
page (WordPress' block-editor frontend fetches these routes itself for
Elementor-templated pages) or its `/wp-json/...` form directly.
"""

import asyncio
import time

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    CATEGORIES_URL,
    CRAWL_DELAY,
    HEADERS,
    MAX_RETRIES,
    NOTICES_CATEGORY_SLUG,
    PER_PAGE,
    POSTS_URL,
    RETRY_DELAY_BASE,
    TENDERS_CPT_URL,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


class _RateLimiter:
    """Process-wide pacing gate honoring robots.txt's `Crawl-delay: 60` --
    every call into this module shares this single limiter, so the actual
    request rate against `gov.sr` never exceeds one request per
    `CRAWL_DELAY` seconds no matter how many pages this run needs to walk."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            delay = self._last + self.min_interval - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


_rate_limiter = _RateLimiter(CRAWL_DELAY)


async def _request(session: AsyncSession, url: str, params: dict) -> tuple[str, dict]:
    r = await session.get(url, headers=HEADERS, params=params, timeout=60)
    if r.status_code != 200:
        raise FetchFailed(f"GET {url} params={params} returned {r.status_code}")
    return r.text, dict(r.headers)


async def _with_retries(url: str, params: dict, proxy_url: str | None = None) -> tuple[str, dict]:
    """Runs a single rate-limited GET with retries. Returns (body, headers)."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        await _rate_limiter.wait()
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            return await _request(session, url, params)
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per the portfolio-wide Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for GET {url!r} params={params!r}: {last_exc!r}")


async def fetch_tenders_page(page: int, category_id: int | None, proxy_url: str | None = None) -> tuple[str, dict]:
    """One page of the `aanbestedingen` custom post type (thin ministry
    procurement notices), embedding the category taxonomy term so the
    ministry/sector name comes back inline without a second request."""
    params = {"per_page": PER_PAGE, "page": page, "orderby": "date", "order": "desc", "_embed": "wp:term"}
    if category_id:
        params["categories"] = category_id
    return await _with_retries(TENDERS_CPT_URL, params, proxy_url=proxy_url)


async def fetch_notices_page(page: int, category_id: int, proxy_url: str | None = None) -> tuple[str, dict]:
    """One page of regular `post`s tagged with the "Aanbestedingen" category
    -- the larger, internationally/donor-financed solicitations that carry
    full rendered body content already in the list response."""
    params = {
        "per_page": PER_PAGE,
        "page": page,
        "orderby": "date",
        "order": "desc",
        "categories": category_id,
        "_embed": "wp:term",
    }
    return await _with_retries(POSTS_URL, params, proxy_url=proxy_url)


async def resolve_category_id(slug: str, proxy_url: str | None = None) -> int | None:
    """Looks up a category's numeric id by slug rather than hardcoding it,
    so a future taxonomy reshuffle on gov.sr's end doesn't silently break
    this actor. Returns None if no category with that slug exists (caller
    decides how to treat that -- for the fixed "Aanbestedingen" notices
    category this is treated as UnexpectedShape; a user-supplied optional
    filter slug that doesn't resolve is instead treated as "no match")."""
    body, _ = await _with_retries(CATEGORIES_URL, {"slug": slug}, proxy_url=proxy_url)
    import json

    matches = json.loads(body)
    if not matches:
        return None
    return matches[0]["id"]


async def resolve_notices_category_id(proxy_url: str | None = None) -> int:
    category_id = await resolve_category_id(NOTICES_CATEGORY_SLUG, proxy_url=proxy_url)
    if category_id is None:
        raise FetchFailed(f"No category found for slug={NOTICES_CATEGORY_SLUG!r} -- taxonomy may have changed")
    return category_id
