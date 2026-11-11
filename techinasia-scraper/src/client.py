"""HTTP client for the three Tech in Asia backends.

Handles retry with exponential backoff, TLS-profile fallback, and the one
genuinely volatile artifact on this target: the Algolia search credentials,
which live in an app bundle whose filename carries a content hash.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Any

from curl_cffi.requests import AsyncSession

from src.constants import (
    ALGOLIA_APP_ID,
    ALGOLIA_INDEX_POSTS,
    ALGOLIA_SEARCH_KEY,
    ALGOLIA_TRENDING_KEY,
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILES,
)

log = logging.getLogger("techinasia")


class TransientError(Exception):
    """Recoverable: worth another attempt or another profile."""


class NotFound(Exception):
    """The entity does not exist. Expected; emits an error record."""


class UnexpectedShape(Exception):
    """Upstream JSON no longer looks like what we parse. Fail loud."""


class AlgoliaCredentialsBurned(Exception):
    """The harvested search key stopped working and re-harvesting failed."""


# The config object literal the front end ships:
#   algolia:{apiKey:"...",appId:"...",trendingQuestionsKey:"...", ...}
_ALGOLIA_BLOCK = re.compile(r"algolia:\{(.{0,600}?)\}", re.DOTALL)
_ALGOLIA_FIELD = re.compile(r'(\w+)\s*:\s*"([^"]+)"')
_BUNDLE_SRC = re.compile(r'src="((?:https?:)?//[^"]*?/assets/[^"]*?app\.[^"]*?\.js)"')


class TechInAsiaClient:
    """One session, reused across a run. Not safe to share across event loops."""

    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILES[0]):
        self._proxy_url = proxy_url
        self._profile = profile
        self._profile_index = 0
        self._session: AsyncSession | None = None
        self._algolia_app_id = ALGOLIA_APP_ID
        self._algolia_key = ALGOLIA_SEARCH_KEY
        self._algolia_trending_key = ALGOLIA_TRENDING_KEY
        self._algolia_refreshed = False

    # -- session ----------------------------------------------------------

    def _build_session(self) -> AsyncSession:
        proxies = None
        if self._proxy_url:
            proxies = {"http": self._proxy_url, "https": self._proxy_url}
        session = AsyncSession(
            impersonate=self._profile,
            proxies=proxies,
            timeout=REQUEST_TIMEOUT,
            verify=True,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            self._session = self._build_session()
        return self._session

    async def _rotate_profile(self) -> bool:
        """Move to the next TLS profile. Returns False once the ladder is spent.

        No WAF was found on this target, so this exists for the day one appears
        rather than for any block we have actually observed.
        """
        self._profile_index += 1
        if self._profile_index >= len(TLS_PROFILES):
            return False
        self._profile = TLS_PROFILES[self._profile_index]
        log.warning(f"Rotating TLS profile to {self._profile}.")
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001 - closing a dead session must not raise
                pass
        self._session = None
        return True

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    # -- core request -----------------------------------------------------

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: str | None = None,
        headers: dict | None = None,
        allow_404: bool = False,
    ) -> Any:
        """Issue a request and return parsed JSON.

        Raises NotFound on 404, TransientError once the retry budget is spent,
        and UnexpectedShape if a 200 does not carry JSON.
        """
        last_detail = "no attempt made"

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                )
            except Exception as exc:  # noqa: BLE001 - network layer, retry then rotate
                last_detail = f"{type(exc).__name__}: {exc}"
                log.warning(f"{method} {url} raised {last_detail} (attempt {attempt + 1}).")
                if attempt == MAX_RETRIES - 2 and not await self._rotate_profile():
                    pass
                await self._backoff(attempt)
                continue

            status = response.status_code

            if status == 404:
                if allow_404:
                    return None
                raise NotFound(f"404 for {url}")

            if status == 200:
                try:
                    return json.loads(response.content)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    head = response.content[:200]
                    # An HTML body on a JSON route means the path fell through
                    # to the SPA shell -- the route does not exist.
                    if head.lstrip()[:9].lower() == b"<!doctype":
                        raise NotFound(
                            f"{url} returned the SPA HTML shell, not JSON -- route does not exist"
                        ) from exc
                    raise UnexpectedShape(
                        f"200 from {url} was not JSON: {head!r}"
                    ) from exc

            if status == 400:
                # The WP REST layer uses 400 for out-of-range page/per_page.
                # Callers clamp ahead of time, so this is a real signal.
                raise UnexpectedShape(
                    f"400 from {url} params={params}: {response.content[:200]!r}"
                )

            if status in (401, 403):
                raise TransientError(
                    f"HTTP {status} from {url}: {response.content[:200]!r}"
                )

            last_detail = f"HTTP {status}: {response.content[:200]!r}"
            log.warning(f"{method} {url} -> {last_detail} (attempt {attempt + 1}).")
            if status in (429, 503) and attempt >= 1:
                await self._rotate_profile()
            await self._backoff(attempt)

        raise TransientError(f"Exhausted {MAX_RETRIES} attempts for {url}: {last_detail}")

    @staticmethod
    async def _backoff(attempt: int) -> None:
        delay = RETRY_DELAY_BASE * (2**attempt) + random.uniform(0.1, 0.6)
        await asyncio.sleep(delay)

    async def get_json(self, url: str, params: dict | None = None, allow_404: bool = False) -> Any:
        return await self.request_json("GET", url, params=params, allow_404=allow_404)

    # -- Algolia ----------------------------------------------------------

    async def algolia_query(self, index: str, payload: dict, *, trending: bool = False) -> dict:
        """Query an Algolia index, re-harvesting the key once if it is rejected."""
        try:
            return await self._algolia_call(index, payload, trending=trending)
        except TransientError as exc:
            if self._algolia_refreshed:
                raise AlgoliaCredentialsBurned(
                    f"Algolia rejected the harvested key and a refresh did not help: {exc}"
                ) from exc
            log.warning("Algolia rejected the seeded key -- re-harvesting from the app bundle.")
            await self.refresh_algolia_credentials()
            try:
                return await self._algolia_call(index, payload, trending=trending)
            except TransientError as exc2:
                raise AlgoliaCredentialsBurned(
                    f"Algolia still rejecting after re-harvest: {exc2}"
                ) from exc2

    async def _algolia_call(self, index: str, payload: dict, *, trending: bool) -> dict:
        key = self._algolia_trending_key if trending else self._algolia_key
        url = f"https://{self._algolia_app_id}-dsn.algolia.net/1/indexes/{index}/query"
        result = await self.request_json(
            "POST",
            url,
            data=json.dumps(payload),
            headers={
                "X-Algolia-Application-Id": self._algolia_app_id,
                "X-Algolia-API-Key": key,
                "Content-Type": "application/json",
            },
        )
        if not isinstance(result, dict) or "hits" not in result:
            raise UnexpectedShape(
                f"Algolia {index} response had no 'hits' key: {str(result)[:200]}"
            )
        return result

    async def refresh_algolia_credentials(self) -> None:
        """Re-read appId / apiKey from the live app bundle.

        The bundle URL carries a content hash (app.<hash>.js) that changes on
        every front-end deploy, so the path is discovered from the homepage
        rather than pinned.
        """
        self._algolia_refreshed = True

        home = await self.session.get(f"{BASE_URL}/")
        if home.status_code != 200:
            raise AlgoliaCredentialsBurned(
                f"Cannot reach the homepage to re-harvest Algolia keys (HTTP {home.status_code})."
            )

        match = _BUNDLE_SRC.search(home.text)
        if not match:
            raise AlgoliaCredentialsBurned(
                "No app.<hash>.js bundle found on the homepage -- the front end was restructured."
            )
        bundle_url = match.group(1)
        if bundle_url.startswith("//"):
            bundle_url = "https:" + bundle_url

        bundle = await self.session.get(bundle_url)
        if bundle.status_code != 200:
            raise AlgoliaCredentialsBurned(
                f"Bundle {bundle_url} returned HTTP {bundle.status_code}."
            )

        block = _ALGOLIA_BLOCK.search(bundle.text)
        if not block:
            raise AlgoliaCredentialsBurned(
                "The algolia:{...} config block is gone from the bundle."
            )
        fields = dict(_ALGOLIA_FIELD.findall(block.group(1)))

        app_id = fields.get("appId")
        api_key = fields.get("apiKey")
        if not app_id or not api_key:
            raise AlgoliaCredentialsBurned(
                f"Bundle config block missing appId/apiKey; saw keys {sorted(fields)}."
            )

        self._algolia_app_id = app_id
        self._algolia_key = api_key
        self._algolia_trending_key = fields.get("trendingQuestionsKey", self._algolia_trending_key)
        log.info(f"Re-harvested Algolia credentials from {bundle_url.rsplit('/', 1)[-1]}.")

    async def verify_algolia(self) -> bool:
        """Cheap liveness probe used before a search run."""
        try:
            await self.algolia_query(ALGOLIA_INDEX_POSTS, {"query": "", "hitsPerPage": 1})
            return True
        except AlgoliaCredentialsBurned:
            return False
