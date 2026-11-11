"""Thin HTTP client for Shopify storefronts.

There is no WAF to defeat (see constants.py), so this client only has to be
careful about one thing: Shopify frontends happily answer a JSON path with a
200 + an HTML page. `ruggable.com/cart.js` returns 367 KB of HTML with status
200. So every JSON read is content-type checked, never status checked alone.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random

from curl_cffi.requests import AsyncSession

from .constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)


class HttpError(Exception):
    def __init__(self, status: int, detail: str = "") -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


class NotJson(Exception):
    """A 200 that is not JSON -- Shopify's catch-all HTML page, not data."""


class UnexpectedShape(Exception):
    """Upstream JSON did not match the documented Shopify shape."""


class ShopifyClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE) -> None:
        self._proxy_url = proxy_url
        self._profile = profile
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "ShopifyClient":
        proxies = (
            {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
        )
        self._session = AsyncSession(
            impersonate=self._profile,
            proxies=proxies,
            timeout=REQUEST_TIMEOUT,
            headers=dict(DEFAULT_HEADERS),
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    # -- raw ------------------------------------------------------------------

    async def get(self, url: str, allow_redirects: bool = True, retries: int | None = None):
        """GET with exponential backoff on transport errors, 429 and 5xx.

        4xx below 500 are returned to the caller: for this target a 404 or 403 is
        a meaningful answer ("this store disabled the endpoint"), not a failure
        worth retrying.
        """
        if self._session is None:
            raise RuntimeError("ShopifyClient used outside its async context.")

        budget = MAX_RETRIES if retries is None else retries
        last_exc: Exception | None = None
        last_status: int | None = None

        for attempt in range(budget):
            try:
                resp = await self._session.get(url, allow_redirects=allow_redirects)
            except Exception as exc:
                # DNS / TLS / connection resets are common across a big domain
                # list and are usually transient.
                last_exc = exc
                log.debug("GET %s attempt %d transport error: %r", url, attempt + 1, exc)
                await self._sleep_backoff(attempt)
                continue

            if resp.status_code < 500 and resp.status_code != 429:
                return resp

            last_status = resp.status_code
            log.debug("GET %s attempt %d returned %s.", url, attempt + 1, resp.status_code)
            await self._sleep_backoff(attempt)

        # Say WHICH failure mode exhausted the budget: a repeated server status
        # and a transport error need completely different follow-up, and
        # "last=None" tells an operator nothing.
        if last_status is not None:
            cause = f"last HTTP status {last_status}"
        elif last_exc is not None:
            cause = f"last transport error {type(last_exc).__name__}: {str(last_exc)[:120]}"
        else:
            cause = "no response"
        raise HttpError(0, f"Exhausted {budget} attempts for {url} ({cause})")

    # -- json -----------------------------------------------------------------

    async def get_json(self, url: str, allow_redirects: bool = True) -> object:
        """GET and parse JSON, or raise HttpError / NotJson.

        Shopify serves its 404/catch-all as text/html with status 200 on some
        headless frontends, so the content-type check is what actually separates
        data from a decoy.
        """
        resp = await self.get(url, allow_redirects=allow_redirects)
        if resp.status_code != 200:
            raise HttpError(resp.status_code, url)

        ctype = (resp.headers.get("content-type") or "").lower()
        if "json" not in ctype and "javascript" not in ctype:
            raise NotJson(
                f"{url} returned 200 {ctype or 'no content-type'} "
                f"({len(resp.content)} bytes) -- HTML page, not JSON."
            )
        try:
            return json.loads(resp.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise NotJson(f"{url} claimed {ctype} but did not parse: {exc}") from exc

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt) + random.uniform(0.1, 0.5))
