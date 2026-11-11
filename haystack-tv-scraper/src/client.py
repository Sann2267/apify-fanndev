"""HTTP client for haystack.tv -- anonymous-token bootstrap, retry, backoff.

There is no WAF to defeat here (see constants.py), so this client is deliberately
thin. The only real work it does is:

  * fetch the anonymous `hs_access_token` JWT from a www page's Set-Cookie,
  * attach the `hs-client-version` / `hs-client-os` contract headers,
  * re-bootstrap once on 401 (token expired / rejected),
  * walk a client-version ladder once on 400 "Please Upgrade" (version retired),
  * exponential backoff on 429/5xx/transport errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random

from curl_cffi.requests import AsyncSession

from .constants import (
    ACCESS_TOKEN_COOKIE,
    CLIENT_OS,
    CLIENT_VERSION,
    CLIENT_VERSION_LADDER,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
    WARMUP_URL,
)

log = logging.getLogger(__name__)


class TokenBootstrapError(Exception):
    """www.haystack.tv did not hand out an anonymous token. Circuit breaker."""


class UpstreamVersionRetired(Exception):
    """Every client version in the ladder was rejected with 'Please Upgrade'."""


class UnexpectedShape(Exception):
    """Upstream returned JSON we do not recognise. Investigate before next run."""


class HttpError(Exception):
    def __init__(self, status: int, detail: str = "") -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


class HaystackClient:
    """One session == one anonymous identity. Cheap to create, safe to share."""

    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE) -> None:
        self._proxy_url = proxy_url
        self._profile = profile
        self._session: AsyncSession | None = None
        self._token: str | None = None
        self._client_version = CLIENT_VERSION

    # -- lifecycle ------------------------------------------------------------

    def _new_session(self) -> AsyncSession:
        proxies = (
            {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
        )
        return AsyncSession(
            impersonate=self._profile,
            proxies=proxies,
            timeout=REQUEST_TIMEOUT,
            headers=dict(DEFAULT_HEADERS),
        )

    async def __aenter__(self) -> "HaystackClient":
        self._session = self._new_session()
        await self.bootstrap_token()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    # -- auth -----------------------------------------------------------------

    async def bootstrap_token(self, force: bool = False) -> str:
        """Load a www page and lift the anonymous JWT out of its Set-Cookie.

        Haystack issues `hs_access_token` to every visitor with no sign-in. The
        JWT decodes to {"isAnonymous": true, ...} and is accepted by the API for
        roughly a year, so one fetch per run is enough.
        """
        if self._token and not force:
            return self._token
        if self._session is None:
            self._session = self._new_session()

        last_status: object = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._session.get(WARMUP_URL)
                last_status = resp.status_code
                token = self._read_token_cookie()
                if token:
                    self._token = token
                    log.info("Anonymous token acquired (%d chars).", len(token))
                    return token
                log.warning(
                    "Warmup %s returned %s but set no %s cookie.",
                    WARMUP_URL,
                    resp.status_code,
                    ACCESS_TOKEN_COOKIE,
                )
            except Exception as exc:  # transport-level; retry
                last_status = repr(exc)
                log.warning("Warmup attempt %d failed: %r", attempt + 1, exc)
            await self._sleep_backoff(attempt)

        raise TokenBootstrapError(
            f"Could not obtain {ACCESS_TOKEN_COOKIE} from {WARMUP_URL} "
            f"after {MAX_RETRIES} attempts (last={last_status})."
        )

    def _read_token_cookie(self) -> str | None:
        if self._session is None:
            return None
        for cookie in self._session.cookies.jar:
            if cookie.name == ACCESS_TOKEN_COOKIE and cookie.value:
                return cookie.value
        return None

    def _headers(self, authed: bool) -> dict[str, str]:
        headers = {
            "hs-client-version": self._client_version,
            "hs-client-os": CLIENT_OS,
        }
        if authed and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    # -- requests -------------------------------------------------------------

    async def get_json(
        self,
        url: str,
        params: dict | None = None,
        authed: bool = True,
    ) -> object:
        """GET `url` and return parsed JSON, or raise.

        Raises UnexpectedShape on a 200 that does not parse as JSON, so a silent
        HTML error page never lands in the dataset as an empty record.
        """
        resp = await self.get(url, params=params, authed=authed)
        if resp.status_code != 200:
            raise HttpError(resp.status_code, resp.text[:400])
        try:
            return json.loads(resp.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise UnexpectedShape(
                f"200 from {url} did not parse as JSON: {exc}; "
                f"body head={resp.content[:200]!r}"
            ) from exc

    async def get(self, url: str, params: dict | None = None, authed: bool = True):
        if self._session is None:
            self._session = self._new_session()
        if authed and not self._token:
            await self.bootstrap_token()

        reauthed = False
        version_bumped = False
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._session.get(
                    url, params=params, headers=self._headers(authed)
                )
            except Exception as exc:  # transport-level; retry
                last_exc = exc
                log.warning("GET %s attempt %d transport error: %r", url, attempt + 1, exc)
                await self._sleep_backoff(attempt)
                continue

            status = resp.status_code

            if status == 200:
                return resp

            # Token rejected -- re-bootstrap once, then retry immediately.
            if status == 401 and authed and not reauthed:
                log.warning("401 from %s -- re-bootstrapping anonymous token.", url)
                reauthed = True
                await self.bootstrap_token(force=True)
                continue

            # Client version retired -- walk the ladder once.
            if status == 400 and not version_bumped and self._looks_like_upgrade(resp):
                version_bumped = True
                if self.refresh_client_version():
                    continue

            # 4xx below are answers, not failures: let the caller classify them.
            if status in (400, 403, 404, 410):
                return resp

            # 429 / 5xx -- back off and retry.
            log.warning("GET %s attempt %d returned %s.", url, attempt + 1, status)
            await self._sleep_backoff(attempt)

        raise HttpError(
            0, f"Exhausted {MAX_RETRIES} retries for {url} (last_exc={last_exc!r})"
        )

    @staticmethod
    def _looks_like_upgrade(resp) -> bool:
        head = resp.content[:512] if resp.content else b""
        return b"Please Upgrade" in head or b"no longer supported" in head

    def refresh_client_version(self) -> bool:
        """Advance to the next untried client version. Raises when exhausted."""
        try:
            idx = CLIENT_VERSION_LADDER.index(self._client_version)
        except ValueError:
            idx = -1
        if idx + 1 >= len(CLIENT_VERSION_LADDER):
            raise UpstreamVersionRetired(
                f"All client versions rejected: {CLIENT_VERSION_LADDER}. "
                "Read the live bundle constant `Ca=` and update CLIENT_VERSION."
            )
        self._client_version = CLIENT_VERSION_LADDER[idx + 1]
        log.warning(
            "Client version bumped to %s after 'Please Upgrade'.", self._client_version
        )
        return True

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        delay = RETRY_DELAY_BASE * (2**attempt) + random.uniform(0.1, 0.6)
        await asyncio.sleep(delay)


def build_proxy_url(password: str, country: str = "US") -> str:
    """Apify Residential with a sticky session (manual fallback; see README)."""
    session_id = "hs" + "".join(random.choices("0123456789abcdef", k=10))
    return (
        f"http://groups-RESIDENTIAL,country-{country},session-{session_id}"
        f":{password}@proxy.apify.com:8000"
    )
