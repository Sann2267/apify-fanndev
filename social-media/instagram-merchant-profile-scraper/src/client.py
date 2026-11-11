"""HTTP client for Instagram's public web surfaces.

Instagram does not need a login for a public profile, but it does need a
warm page load first: the profile HTML sets `csrftoken`/`mid`/`ig_did`
cookies that the JSON API expects, and it is the entity page -- not the
site root -- that must be warmed (see `.ai/skills/warm-page-token-harvest`).
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    API_HEADERS,
    MAX_RETRIES,
    PAGE_HEADERS,
    PROFILE_PAGE,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE_LADDER,
)

logger = logging.getLogger(__name__)

# Instagram answers a throttled/blocked anonymous request with a login wall
# or a challenge rather than a clean status code, so the body matters.
BLOCK_MARKERS = (
    b"/accounts/login/",
    b"challenge_required",
    b"Please wait a few minutes",
    b"rate limited",
    b"login_required",
)


class BlockedError(Exception):
    """Every retry and every TLS profile was exhausted while still gated."""


class NotFound(Exception):
    """The username does not resolve to a public Instagram profile."""


class UpstreamShapeError(Exception):
    """A 200 response did not carry the shape this actor expects."""


def _is_blocked(response) -> bool:
    if response.status_code in (401, 403, 429, 503):
        return True
    # A login redirect is Instagram's throttle response for anonymous
    # traffic; the status is still 200, so only the body reveals it.
    body = response.content[:4096] if response.content else b""
    return any(marker in body for marker in BLOCK_MARKERS)


class InstagramClient:
    def __init__(self, proxy_url: str | None = None, new_proxy_url=None):
        self._new_proxy_url = new_proxy_url
        self._profile_index = 0
        self._proxy_url = proxy_url
        self.session = self._build_session(proxy_url)

    @property
    def _profile(self) -> str:
        return TLS_PROFILE_LADDER[self._profile_index % len(TLS_PROFILE_LADDER)]

    def _build_session(self, proxy_url: str | None) -> AsyncSession:
        return AsyncSession(
            impersonate=self._profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )

    async def _rotate(self) -> None:
        """New fingerprint and, when a proxy is configured, a new egress IP.

        Instagram's anonymous throttle is IP-bound far more than
        fingerprint-bound, so the proxy rotation is the part that matters
        here; the profile rotation is cheap insurance.
        """
        self._profile_index += 1
        if self._new_proxy_url is not None:
            try:
                self._proxy_url = await self._new_proxy_url()
            except Exception as exc:  # noqa: BLE001 - rotation is best-effort
                logger.warning("Could not rotate proxy session: %s", exc)
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
        self.session = self._build_session(self._proxy_url)
        logger.info("Rotated to TLS profile %s", self._profile)

    async def warm_profile(self, username: str) -> str:
        """Load the profile page and keep its cookies. Returns the HTML.

        Doubles as strategy S2's data source, so the warm-up is never a
        wasted request.
        """
        url = PROFILE_PAGE.format(username=username)
        last = "unknown"
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(url, headers=PAGE_HEADERS)
            except Exception as exc:  # noqa: BLE001
                last = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 404:
                    raise NotFound(f"@{username} does not exist")
                if not _is_blocked(response):
                    return response.text
                last = f"blocked with HTTP {response.status_code}"
                logger.warning(
                    "Blocked warming @%s (attempt %d, %s)", username, attempt + 1, self._profile
                )
                await self._rotate()
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise BlockedError(f"Could not load @{username} after {MAX_RETRIES} attempts: {last}")

    async def profile_api(self, username: str) -> dict | None:
        """`web_profile_info` for a username, or None if it yields nothing.

        Returns None rather than raising when the payload is empty: this
        endpoint intermittently returns no user for accounts whose HTML page
        loads perfectly, and the caller falls back to parsing that HTML.
        """
        headers = {**API_HEADERS, "Referer": PROFILE_PAGE.format(username=username)}
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(
                    "https://www.instagram.com/api/v1/users/web_profile_info/",
                    params={"username": username}, headers=headers,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("API error for @%s: %s", username, exc)
            else:
                if response.status_code == 404:
                    raise NotFound(f"@{username} does not exist")
                if not _is_blocked(response):
                    try:
                        payload = response.json()
                    except Exception:  # noqa: BLE001 - fall back to HTML
                        return None
                    if not isinstance(payload, dict):
                        return None
                    user = (payload.get("data") or {}).get("user")
                    return user or None
                await self._rotate()
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        return None

    async def close(self) -> None:
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
