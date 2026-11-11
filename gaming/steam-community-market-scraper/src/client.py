"""Async client over the anonymous Steam Community Market RPC layer.

Failure model, because Steam's is unusual:

* An unknown item is **not** a 404. ``QueryDescription`` and
  ``QueryPriceHistory`` answer 200 with ``data: null`` and the order book answers
  ``{"success": false}``. Callers must treat those as "item not found", which
  is why ``query`` returns ``None`` instead of raising for them.
* A malformed argument list is a 400 with an empty body. That is a contract
  change (Valve renamed or reshaped an argument), never a transient, so it is
  raised immediately as ``BadArguments`` rather than retried.
* 429 / 5xx / connection resets are transient: back off exponentially, rotate
  the TLS profile and, when a proxy is configured, take a fresh proxy session
  (= fresh exit IP) before the next attempt.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlencode

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    LISTING_PAGE_ROUTE,
    MAX_RETRIES,
    QUERY_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    ROUTE_DATA_HEADERS,
    TLS_PROFILES,
)

ProxyFactory = Callable[[], Awaitable[str | None]]

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha",
    b"Access Denied",
)


class SteamError(RuntimeError):
    """Base class for refusals worth reporting as an error row."""


class BadArguments(SteamError):
    """HTTP 400: the RPC rejected our argument shape. Not retryable."""


class RetriesExhausted(SteamError):
    """Transient failures outlasted the whole backoff ladder."""


class UnexpectedShape(SteamError):
    """200 OK but not the ``{"data": ...}`` envelope the SPA expects."""


class SteamClient:
    def __init__(
        self,
        proxy_factory: ProxyFactory | None = None,
        max_concurrency: int = 4,
        log: Any = None,
    ) -> None:
        self._proxy_factory = proxy_factory
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._profile_idx = 0
        self._session: AsyncSession | None = None
        self._session_lock = asyncio.Lock()
        self._generation = 0
        self.log = log
        self.requests_made = 0

    # -- session lifecycle -------------------------------------------------

    async def _get_session(self) -> tuple[AsyncSession, int]:
        async with self._session_lock:
            if self._session is None:
                proxy = await self._proxy_factory() if self._proxy_factory else None
                profile = TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]
                self._session = AsyncSession(
                    impersonate=profile,
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    timeout=REQUEST_TIMEOUT,
                )
            return self._session, self._generation

    async def _rotate(self, generation: int, reason: str) -> None:
        """New TLS profile + new proxy session, once per failing generation.

        Concurrent workers that fail on the same session all ask to rotate;
        the generation check makes only the first one do it.
        """
        async with self._session_lock:
            if generation != self._generation:
                return
            self._generation += 1
            self._profile_idx += 1
            old, self._session = self._session, None
            if self.log:
                nxt = TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]
                self.log.warning(f"Rotating session ({reason}) -> TLS profile {nxt}, fresh proxy session")
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    # -- transport -----------------------------------------------------------

    async def _get(self, url: str, headers: dict, label: str) -> Any:
        """GET + JSON decode with backoff. Returns the decoded JSON body."""
        last = "no attempt made"
        for attempt in range(MAX_RETRIES):
            session, generation = await self._get_session()
            try:
                async with self._sem:
                    self.requests_made += 1
                    resp = await session.get(url, headers=headers, allow_redirects=True)
            except Exception as exc:  # connection reset, proxy error, timeout
                last = f"{type(exc).__name__}: {exc}"
                await self._rotate(generation, last[:80])
                await self._sleep(attempt)
                continue

            status = resp.status_code
            head = resp.content[:4096] if resp.content else b""
            # Marker sniffing only on non-JSON bodies: an item description can
            # legitimately contain any of these words.
            is_json = "json" in (resp.headers.get("content-type") or "")
            blocked = not is_json and any(m in head for m in BLOCK_MARKERS)
            if status == 400:
                raise BadArguments(f"{label}: HTTP 400 -- the RPC rejected the arguments")
            if status == 200 and not blocked:
                try:
                    return resp.json()
                except (json.JSONDecodeError, ValueError):
                    raise UnexpectedShape(f"{label}: 200 but body is not JSON ({head[:120]!r})")

            last = "challenge page (HTTP 200)" if status == 200 else f"HTTP {status}"
            if status in (429, 403) or status >= 500 or status == 200:
                await self._rotate(generation, f"{label} {last}")
                await self._sleep(attempt, resp.headers.get("retry-after"))
                continue
            raise SteamError(f"{label}: unexpected HTTP {status}")
        raise RetriesExhausted(f"{label}: gave up after {MAX_RETRIES} attempts ({last})")

    @staticmethod
    async def _sleep(attempt: int, retry_after: str | None = None) -> None:
        delay = RETRY_DELAY_BASE * (2**attempt) + random.uniform(0, 1.0)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(int(retry_after), 60))
        await asyncio.sleep(delay)

    # -- RPC ---------------------------------------------------------------

    async def query(self, route: str, method: str, *args: Any) -> Any:
        """Call a queryAction and return its ``data`` member (may be None)."""
        params = urlencode({"q": method, "qp": json.dumps(list(args), separators=(",", ":"))})
        body = await self._get(f"{BASE_URL}{route}?{params}", QUERY_HEADERS, method)
        if not isinstance(body, dict) or "data" not in body:
            raise UnexpectedShape(f"{method}: response has no 'data' member: {str(body)[:200]}")
        return body["data"]

    async def route_buckets(self, appid: int, name: str) -> dict | None:
        """Variant list for a skin / bucket group via the SSR route loader."""
        url = f"{BASE_URL}{LISTING_PAGE_ROUTE}/{appid}/{quote(name, safe='')}"
        body = await self._get(url, ROUTE_DATA_HEADERS, "routeData")
        return body if isinstance(body, dict) else None
