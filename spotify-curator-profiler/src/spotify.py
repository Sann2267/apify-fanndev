"""Anonymous Spotify client: token harvest, GraphQL pathfinder, open Web API.

No Spotify account, cookie or developer application is involved anywhere here.

Three public surfaces, each verified open on 2026-09-20:

1. ``open.spotify.com/embed/<type>/<id>`` carries a ``__NEXT_DATA__`` blob whose
   ``settings.session.accessToken`` is the anonymous bearer token Spotify hands
   to every visitor (``isAnonymous: true``). It is the only credential used.
2. ``api-partner.spotify.com/pathfinder/v1/query`` -- the web player's GraphQL
   gateway -- accepts that token with no ``client-token`` header. Its queries
   are persisted: the client sends an operation name plus the SHA-256 hash of
   the query text, both harvested from the web player bundle.
3. ``api.spotify.com/v1/search`` accepts the same token. Every *entity*
   endpoint on that host (``/v1/tracks``, ``/v1/artists``, ``/v1/users``, ...)
   answers ``429 QUOTA_EXCEEDED`` to an anonymous token, so search is the only
   way in -- which is why ISRC and popularity enrichment costs one request per
   track instead of coming free with the playlist.

Two failure modes are handled rather than raised, because both are routine: a
401 means the token aged out (they last about an hour), and a 200 carrying
``PersistedQueryNotFound`` means Spotify shipped a new web player and rotated
its query hashes. The first refreshes the token; the second re-harvests every
hash from the live bundle, so a deploy on Spotify's side costs one extra
request rather than breaking the actor.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import Any

from curl_cffi.requests import AsyncSession

from src.constants import (
    BUNDLE_PATTERN,
    EMBED_TOKEN_URL,
    MAX_RETRIES,
    PARTNER_URL,
    PERSISTED_QUERIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
    USER_AGENT,
    WEB_API_URL,
    WEB_PLAYER_URL,
)

NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
# The bundle declares each persisted query as new Klass("name","query","<sha256>").
OP_PATTERN = re.compile(r'\("([A-Za-z0-9_]+)","(?:query|mutation)","([0-9a-f]{64})"')


def dig_items(data: dict) -> list:
    """The hit list inside a searchSuggestions payload, or an empty list."""
    node = (data or {}).get("searchV2") or {}
    results = node.get("topResultsV2") or {}
    items = results.get("itemsV2")
    return items if isinstance(items, list) else []


class SpotifyError(RuntimeError):
    """Spotify refused the request in a way retrying will not fix."""


class UnexpectedShape(RuntimeError):
    """Spotify answered 200 but the payload no longer matches the contract.

    Raised loudly rather than returning an empty list, so a Spotify-side schema
    change surfaces as a failed run instead of a silently empty dataset.
    """


class NotFound(RuntimeError):
    """Spotify answered 200 with a ``NotFound`` entity -- a dead or private id.

    Pathfinder never 404s. A playlist that does not exist, a retired editorial
    chart and a typo in an id all come back as HTTP 200 whose entity carries
    ``__typename: "NotFound"``, so this is the only way to tell them apart from
    a real result.
    """


class SpotifyClient:
    """Async client over the three open Spotify surfaces."""

    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str = TLS_PROFILE,
        market: str = "US",
        timeout: int = 45,
        log: Any = None,
    ) -> None:
        self.proxy_url = proxy_url
        self.profile = profile
        self.market = market
        self.timeout = timeout
        self.log = log
        self._session: AsyncSession | None = None
        self._token: str | None = None
        self._queries: dict[str, str] = dict(PERSISTED_QUERIES)
        self._queries_refreshed = False
        self.requests_made = 0

    # -- lifecycle ---------------------------------------------------------
    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("SpotifyClient used outside its async context manager")
        return self._session

    async def __aenter__(self) -> "SpotifyClient":
        kwargs: dict[str, Any] = {"impersonate": self.profile, "timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        self._session = AsyncSession(**kwargs)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _note(self, level: str, message: str) -> None:
        if self.log is not None:
            getattr(self.log, level)(message)

    # -- token -------------------------------------------------------------
    async def token(self, force: bool = False) -> str:
        """The anonymous bearer token, harvested from an embed page and cached."""
        if self._token and not force:
            return self._token
        response = await self.session.get(
            EMBED_TOKEN_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if response.status_code != 200:
            raise SpotifyError(
                f"Could not load the embed page that carries the anonymous token "
                f"(HTTP {response.status_code}). Spotify may be refusing this IP -- "
                f"try enabling the proxy option."
            )
        match = NEXT_DATA.search(response.text)
        if not match:
            raise UnexpectedShape(
                "The Spotify embed page no longer contains a __NEXT_DATA__ block, so "
                "the anonymous token cannot be read."
            )
        try:
            blob = json.loads(match.group(1))
            session = blob["props"]["pageProps"]["state"]["settings"]["session"]
            self._token = session["accessToken"]
        except (KeyError, TypeError, ValueError) as exc:
            raise UnexpectedShape(
                f"The Spotify embed page no longer exposes an anonymous access token: {exc}"
            ) from exc
        self.requests_made += 1
        return self._token

    # -- persisted query hashes -------------------------------------------
    async def _refresh_queries(self) -> bool:
        """Re-harvest persisted query hashes from the live web player bundle.

        Runs at most once per run, and only after Spotify has already answered
        ``PersistedQueryNotFound`` -- the bundle is several megabytes, so it is
        never fetched speculatively.
        """
        if self._queries_refreshed:
            return False
        self._queries_refreshed = True
        self._note(
            "info",
            "Spotify rotated its GraphQL query hashes -- re-harvesting them from "
            "the live web player bundle.",
        )
        page = await self.session.get(
            WEB_PLAYER_URL, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}
        )
        self.requests_made += 1
        bundle = BUNDLE_PATTERN.search(page.text)
        if not bundle:
            self._note("warning", "Could not locate the web player bundle URL.")
            return False
        script = await self.session.get(bundle.group(0), headers={"User-Agent": USER_AGENT})
        self.requests_made += 1
        found = dict(OP_PATTERN.findall(script.text))
        if not found:
            self._note(
                "warning",
                "The web player bundle no longer declares query hashes in a "
                "recognised form.",
            )
            return False
        changed = sum(1 for name, digest in found.items() if self._queries.get(name) != digest)
        self._queries.update(found)
        self._note("info", f"Harvested {len(found)} query hashes ({changed} changed).")
        return changed > 0

    # -- GraphQL -----------------------------------------------------------
    async def graphql(self, operation: str, variables: dict) -> dict:
        """Run a persisted pathfinder query and return its ``data`` object."""
        for attempt in range(1, MAX_RETRIES + 1):
            digest = self._queries.get(operation)
            if not digest:
                raise SpotifyError(f"No persisted query hash known for {operation!r}.")
            extensions = {"persistedQuery": {"version": 1, "sha256Hash": digest}}
            response = await self.session.get(
                PARTNER_URL,
                params={
                    "operationName": operation,
                    "variables": json.dumps(variables, separators=(",", ":")),
                    "extensions": json.dumps(extensions, separators=(",", ":")),
                },
                headers={
                    "Authorization": f"Bearer {await self.token()}",
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "app-platform": "WebPlayer",
                    "Origin": "https://open.spotify.com",
                    "Referer": "https://open.spotify.com/",
                },
            )
            self.requests_made += 1

            if response.status_code == 401:
                await self.token(force=True)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                await self._backoff(attempt, f"{operation}: HTTP {response.status_code}")
                continue
            if response.status_code != 200:
                raise SpotifyError(
                    f"{operation} failed with HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise UnexpectedShape(f"{operation} returned non-JSON: {exc}") from exc

            errors = payload.get("errors") or []
            messages = " ".join(str(error.get("message", "")) for error in errors)
            if "PersistedQueryNotFound" in messages:
                if await self._refresh_queries():
                    continue
                raise SpotifyError(
                    f"Spotify rotated the persisted query hash for {operation!r} and a "
                    f"replacement could not be harvested. This usually clears within a day."
                )
            data = payload.get("data")
            if data is None:
                raise SpotifyError(
                    f"{operation} returned no data"
                    + (f": {messages[:200]}" if messages else ".")
                )
            return data

        raise SpotifyError(f"{operation} still failing after {MAX_RETRIES} attempts.")

    async def entity(self, operation: str, variables: dict, union_key: str) -> dict:
        """A GraphQL query whose result is a single entity union.

        Turns Spotify's hollow 200 -- ``__typename: "NotFound"`` -- into a real
        :class:`NotFound`, so a dead id cannot reach the dataset as an empty row.
        """
        data = await self.graphql(operation, variables)
        node = data.get(union_key)
        if not isinstance(node, dict):
            raise UnexpectedShape(f"{operation} no longer returns an object at {union_key!r}.")
        typename = node.get("__typename")
        if typename in ("NotFound", "GenericError", "RestrictedContent"):
            raise NotFound(
                f"Spotify has no readable entity here (__typename={typename}). The id may "
                f"be wrong, private, region-restricted or retired."
            )
        return node

    # -- open Web API ------------------------------------------------------
    async def search(
        self,
        query: str,
        kind: str,
        limit: int = 20,
        offset: int = 0,
        market: str | None = None,
    ) -> dict:
        """``/v1/search`` -- the one Web API endpoint open to an anonymous token."""
        params = {"q": query, "type": kind, "limit": str(limit), "offset": str(offset)}
        market = self.market if market is None else market
        if market:
            params["market"] = market
        for attempt in range(1, MAX_RETRIES + 1):
            response = await self.session.get(
                f"{WEB_API_URL}/search",
                params=params,
                headers={
                    "Authorization": f"Bearer {await self.token()}",
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )
            self.requests_made += 1
            if response.status_code == 401:
                await self.token(force=True)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                await self._backoff(attempt, f"search: HTTP {response.status_code}")
                continue
            if response.status_code != 200:
                raise SpotifyError(
                    f"Search failed with HTTP {response.status_code}: {response.text[:200]}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise UnexpectedShape(f"Search returned non-JSON: {exc}") from exc
        raise SpotifyError(f"Search still failing after {MAX_RETRIES} attempts.")

    async def suggest(self, query: str) -> list[dict]:
        """Free-text search through pathfinder, returned as a flat hit list.

        Each hit is ``{"kind": "Track"|"Playlist"|"Artist"|..., "data": {...}}``
        in Spotify's own relevance order. This is the web player's own search
        box, and unlike ``/v1/search`` it has shown no request ceiling -- but it
        also ignores every paging variable and always returns at most
        :data:`SEARCH_SUGGESTIONS_CAP` hits, so there is no second page to ask
        for.
        """
        data = await self.graphql("searchSuggestions", {"query": query})
        items = dig_items(data)
        hits = []
        for entry in items:
            node = (entry or {}).get("item") or {}
            payload = node.get("data") or {}
            kind = payload.get("__typename")
            if kind:
                hits.append({"kind": kind, "data": payload})
        return hits

    async def get_json(
        self, url: str, params: dict | None = None, authorize: bool = False
    ) -> Any:
        """Plain JSON GET, used for the unauthenticated public charts service."""
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if authorize:
            headers["Authorization"] = f"Bearer {await self.token()}"
        for attempt in range(1, MAX_RETRIES + 1):
            response = await self.session.get(url, params=params or {}, headers=headers)
            self.requests_made += 1
            if response.status_code == 429 or response.status_code >= 500:
                await self._backoff(attempt, f"HTTP {response.status_code}")
                continue
            if response.status_code != 200:
                raise SpotifyError(
                    f"{url} failed with HTTP {response.status_code}: {response.text[:200]}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise UnexpectedShape(f"{url} returned non-JSON: {exc}") from exc
        raise SpotifyError(f"{url} still failing after {MAX_RETRIES} attempts.")

    # -- helpers -----------------------------------------------------------
    async def _backoff(self, attempt: int, reason: str) -> None:
        delay = RETRY_DELAY_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.4)
        self._note(
            "warning",
            f"{reason} -- retrying in {delay:.1f}s (attempt {attempt}/{MAX_RETRIES}).",
        )
        await asyncio.sleep(delay)
