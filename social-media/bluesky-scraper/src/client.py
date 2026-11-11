"""HTTP client for the Bluesky AppView (AT Protocol XRPC).

Two behaviours matter here and nothing else does:

1. `public.api.bsky.app` is an open, unauthenticated JSON API with no WAF.
   Retry/backoff exists only to ride out transient network faults.

2. `app.bsky.feed.searchPosts` on `api.bsky.app` sits behind an nginx IP
   token-bucket (~5 requests, then HTTP 403 for ~60s). A 403 there is a
   *rate* signal, not a ban: the fix is a new exit IP, and failing that,
   a ~65s wait. This is the only place proxy rotation earns its cost.
"""

import asyncio
import json
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    PUBLIC_HOST,
    MAX_LIMIT,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SEARCH_BLOCK_COOLDOWN,
    SEARCH_MAX_BLOCK_WAITS,
    SEARCH_METHOD,
    SEARCH_PACE_NO_PROXY,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)


class NotFound(Exception):
    """The requested actor / post / list does not exist upstream."""


class InvalidRequest(Exception):
    """Upstream rejected the request shape (HTTP 400).

    This is a bug in *this* actor's params, not a transient condition,
    so it must never be retried.
    """


class AuthRequired(Exception):
    """Endpoint needs a logged-in session (HTTP 401 AuthMissing).

    Out of scope: this actor is public-data / no-login by constraint.
    """


class RateLimited(Exception):
    """The searchPosts IP bucket is empty and rotation did not help."""


def _is_search_block(response) -> bool:
    """nginx's stock 403 body, served by `api.bsky.app` when the
    per-IP searchPosts bucket is exhausted. Detected by body marker as
    well as status because a bare 403 status alone is ambiguous -- the
    same code comes back from the CDN for a genuinely blocked path."""
    if response.status_code != 403:
        return False
    head = response.content[:2048] if response.content else b""
    return b"Request forbidden by administrative rules" in head or b"403 Forbidden" in head


class BlueskyClient:
    def __init__(
        self,
        proxy_url: str | None = None,
        proxy_provider=None,
        profile: str = TLS_PROFILE,
    ):
        """`proxy_provider` is an optional async callable returning a
        fresh proxy URL. It is invoked only when the search bucket
        blocks us -- a new exit IP is a new bucket."""
        self._profile = profile
        self._proxy_provider = proxy_provider
        self._proxy_url = proxy_url
        self.session = self._new_session(proxy_url)
        self._did_cache: dict[str, str] = {}
        self._last_search_at: float = 0.0

    def _new_session(self, proxy_url: str | None) -> AsyncSession:
        session = AsyncSession(
            impersonate=self._profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    async def _rotate(self) -> bool:
        """Swap in a fresh exit IP. Returns False when no provider is
        configured (local runs), so the caller falls back to waiting."""
        if not self._proxy_provider:
            return False
        try:
            new_url = await self._proxy_provider()
        except Exception as exc:  # noqa: BLE001 -- rotation is best-effort
            log.warning("Proxy rotation failed: %r", exc)
            return False
        await self.session.close()
        self._proxy_url = new_url
        self.session = self._new_session(new_url)
        return True

    # ------------------------------------------------------------ core
    async def get_json(self, host: str, method: str, params: dict | None = None) -> dict:
        url = f"{host}/xrpc/{method}"
        response = await self._with_retry(url, params or {}, is_search=method == SEARCH_METHOD)

        if response.status_code == 400:
            body = response.text[:800]
            # The AppView returns 400 InvalidRequest for a handle/DID that
            # does not resolve, which is semantically a 404 for our caller.
            if "not found" in body.lower() or "could not resolve" in body.lower():
                raise NotFound(body)
            raise InvalidRequest(body)
        if response.status_code == 401:
            raise AuthRequired(response.text[:300])
        if response.status_code == 404:
            raise NotFound(response.text[:300])
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} from {method}: {response.text[:300]}")

        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Non-JSON response from {method}: {response.text[:300]!r}"
            ) from exc

    async def _pace_search(self):
        """Without a proxy, keep under the bucket instead of draining it.

        Measured: blocked attempts keep the bucket empty, so a 300s rest
        after an eager retry storm still yielded zero tokens. Staying
        below the limit is the only cheap way through."""
        if self._proxy_provider:
            return
        elapsed = asyncio.get_running_loop().time() - self._last_search_at
        if self._last_search_at and elapsed < SEARCH_PACE_NO_PROXY:
            await asyncio.sleep(SEARCH_PACE_NO_PROXY - elapsed)

    async def _with_retry(self, url: str, params: dict, is_search: bool):
        last_exc: Exception | None = None
        block_waits = 0

        for attempt in range(MAX_RETRIES):
            if is_search:
                await self._pace_search()
            try:
                response = await self.session.get(url, params=params)
            except Exception as exc:  # noqa: BLE001 -- network faults are retryable
                last_exc = exc
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue
            if is_search:
                self._last_search_at = asyncio.get_running_loop().time()

            if is_search and _is_search_block(response):
                # A new IP is a new bucket -- always cheaper than waiting.
                if await self._rotate():
                    log.info("searchPosts blocked; rotated to a fresh exit IP")
                    continue
                block_waits += 1
                if block_waits > SEARCH_MAX_BLOCK_WAITS:
                    raise RateLimited(
                        "searchPosts is IP-rate-limited and no proxy is configured. "
                        "Enable Apify Proxy (RESIDENTIAL) so the actor can rotate "
                        "exit IPs instead of waiting."
                    )
                log.info(
                    "searchPosts bucket empty and no proxy to rotate to -- "
                    "waiting %.0fs (%d/%d)",
                    SEARCH_BLOCK_COOLDOWN, block_waits, SEARCH_MAX_BLOCK_WAITS,
                )
                await asyncio.sleep(SEARCH_BLOCK_COOLDOWN)
                continue

            if response.status_code in (429, 502, 503, 504):
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            return response

        if last_exc:
            raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")
        raise RateLimited(f"Exhausted {MAX_RETRIES} retries for {url} (still blocked)")

    # ------------------------------------------------------- identity
    async def resolve_did(self, actor: str) -> str:
        """Handle -> DID, memoised for the lifetime of the run.

        This is NOT optional politeness. An `at://` URI whose authority
        is a handle rather than a DID makes `getLikes`, `getQuotes` and
        `getPosts` return **HTTP 200 with an empty array**, and makes
        `getRepostedBy` return HTTP 500 -- verified against a post with
        known non-zero likes/quotes/reposts. Only `getPostThread`
        tolerates a handle. Emitting those silent empties as real results
        would quietly corrupt datasets, so every post-shaped URI is
        normalised to its DID form before use."""
        if actor.startswith("did:"):
            return actor
        key = actor.lower()
        if key in self._did_cache:
            return self._did_cache[key]
        data = await self.get_json(
            PUBLIC_HOST, "com.atproto.identity.resolveHandle", {"handle": key}
        )
        did = data.get("did")
        if not did:
            raise NotFound(f"handle {actor!r} did not resolve to a DID")
        self._did_cache[key] = did
        return did

    async def to_did_uri(self, at_uri: str) -> str:
        """Rewrite `at://<handle>/<collection>/<rkey>` to its DID form."""
        if not at_uri.startswith("at://"):
            return at_uri
        rest = at_uri[len("at://"):]
        authority, _, tail = rest.partition("/")
        if authority.startswith("did:"):
            return at_uri
        did = await self.resolve_did(authority)
        return f"at://{did}/{tail}" if tail else f"at://{did}"

    # ------------------------------------------------------- pagination
    async def paginate(
        self,
        host: str,
        method: str,
        params: dict,
        items_key: str,
        max_items: int,
    ) -> list[dict]:
        """Follow the XRPC `cursor` until it is absent, the page comes
        back empty, or `max_items` is reached.

        Three stop conditions, all required: upstream drops `cursor` at
        the end of most collections, but a few return a stable cursor
        forever -- so an empty page and a repeated cursor both terminate
        too, otherwise the actor would spin."""
        collected: list[dict] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()

        while len(collected) < max_items:
            page_params = dict(params)
            page_params["limit"] = min(MAX_LIMIT, max_items - len(collected))
            if cursor:
                page_params["cursor"] = cursor

            data = await self.get_json(host, method, page_params)
            batch = data.get(items_key) or []
            if not batch:
                break
            collected.extend(batch)

            cursor = data.get("cursor")
            if not cursor or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)

        return collected[:max_items]

    async def close(self):
        await self.session.close()
