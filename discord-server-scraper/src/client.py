"""HTTP client for Discord: two pacing tiers, retries, and typed outcomes.

Discord is not fingerprint-gated (see constants.py, "THE GATE"), so this client
is deliberately plainer than the ones in this portfolio that fight DataDome or
Cloudflare. What it does have to get right is pacing, because the two surfaces
behave completely differently:

  /servers*        ~6 requests back to back then HTTP 429 from Cloudflare,
                   with no Retry-After to read. Needs seconds of spacing.
  /api/v10/*       took a 25-request burst without a single non-200 and
                   publishes no rate-limit headers at all. Needs almost none.

Pacing them from one clock would either throttle the API pointlessly or walk
the directory into a 429 wall, so the two tiers keep separate clocks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import urllib.parse
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    API_REQUEST_DELAY_SECS,
    API_ROOT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    ERR_UNKNOWN_INVITE,
    ERR_WIDGET_DISABLED,
    SITE_ROOT,
    TLS_PROFILES,
)

log = logging.getLogger("discord.client")

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)

# A 429 on /servers is a volume signal, not a transport hiccup, and Cloudflare
# sends no Retry-After. Backing off in seconds is what actually clears it;
# recon needed roughly half a minute of quiet after tripping it.
RATE_LIMIT_COOLDOWN_SECS = 30.0


class DiscordError(Exception):
    """Base for the outcomes callers route on."""


class DiscordNotFound(DiscordError):
    """Discord answered definitively that the thing does not exist.

    Covers HTTP 404 on an SSR path and JSON error 10006 (Unknown Invite). Both
    are final answers, so callers write a diagnostic row and move on instead of
    spending retries.
    """


class DiscordForbidden(DiscordError):
    """The resource exists but is not public.

    In practice this is one thing: JSON error 50004 (Widget Disabled), which
    means the owner never switched the server widget on. Most servers have not.
    """


class DiscordBlocked(DiscordError):
    """Transport failure or a status that survived the whole retry ladder."""


class DiscordClient:
    """One client per run, holding a curl_cffi session per TLS profile."""

    def __init__(
        self,
        proxy_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_timeout: int = DEFAULT_TIMEOUT_SECS,
        request_delay: float = DEFAULT_REQUEST_DELAY_SECS,
        api_request_delay: float = API_REQUEST_DELAY_SECS,
    ) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.request_delay = request_delay
        self.api_request_delay = api_request_delay
        self._profile_idx = 0
        self._session: cr.Session | None = None
        # Separate clocks: see the module docstring.
        self._last_at: dict[str, float] = {"page": 0.0, "api": 0.0}
        self._locks: dict[str, asyncio.Lock] = {
            "page": asyncio.Lock(), "api": asyncio.Lock(),
        }
        self.request_count = 0
        self.rate_limited_count = 0

    # -- session plumbing --------------------------------------------------

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    def _session_or_new(self) -> cr.Session:
        if self._session is None:
            kwargs: dict[str, Any] = {
                "impersonate": self.profile,
                "timeout": self.request_timeout,
            }
            if self.proxy_url:
                kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
            self._session = cr.Session(**kwargs)
        return self._session

    def rotate_profile(self) -> str:
        self._profile_idx += 1
        self.close()
        log.info("Rotated TLS profile to %s", self.profile)
        return self.profile

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass
            self._session = None

    # -- pacing ------------------------------------------------------------

    async def _pace(self, tier: str) -> None:
        delay = self.request_delay if tier == "page" else self.api_request_delay
        if delay <= 0:
            return
        async with self._locks[tier]:
            gap = time.monotonic() - self._last_at[tier]
            if gap < delay:
                await asyncio.sleep(delay - gap)
            self._last_at[tier] = time.monotonic()

    # -- core --------------------------------------------------------------

    async def _request(self, url: str, *, tier: str, label: str) -> Any:
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            if attempt:
                delay = min(2**attempt + random.uniform(0, 1.5), 30)
                log.info(
                    "Retry %d/%d for %s in %.1fs",
                    attempt, self.max_retries - 1, label, delay,
                )
                await asyncio.sleep(delay)

            await self._pace(tier)
            session = self._session_or_new()
            self.request_count += 1
            try:
                resp = await asyncio.to_thread(session.get, url)
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_error = exc
                log.warning("Transport error on %s: %s", label, exc)
                self.rotate_profile()
                continue

            if resp.status_code == 429:
                # The only gate Discord actually applies. Spacing clears it;
                # rotating the fingerprint does not, because the limit is not
                # fingerprint-shaped. Sitting still is the fix.
                self.rate_limited_count += 1
                last_error = DiscordBlocked(f"HTTP 429 on {label}")
                log.warning(
                    "Rate limited on %s. Pausing %.0fs. If this repeats, raise "
                    "requestDelaySecs -- Discord allows about six directory "
                    "requests back to back.",
                    label, RATE_LIMIT_COOLDOWN_SECS,
                )
                await asyncio.sleep(RATE_LIMIT_COOLDOWN_SECS)
                continue

            if resp.status_code == 404:
                raise DiscordNotFound(f"HTTP 404 on {label}")

            if resp.status_code == 403:
                detail = _json_error(resp)
                if detail and detail.get("code") == ERR_WIDGET_DISABLED:
                    raise DiscordForbidden(
                        f"{label}: the server widget is switched off by its owner"
                    )
                raise DiscordForbidden(f"HTTP 403 on {label}")

            if resp.status_code in RETRY_STATUS:
                last_error = DiscordBlocked(f"HTTP {resp.status_code} on {label}")
                log.warning("HTTP %s on %s", resp.status_code, label)
                continue

            if resp.status_code >= 400:
                detail = _json_error(resp)
                if detail and detail.get("code") == ERR_UNKNOWN_INVITE:
                    raise DiscordNotFound(f"{label}: unknown or expired invite")
                raise DiscordBlocked(
                    f"HTTP {resp.status_code} on {label}: {(resp.text or '')[:200]}"
                )

            return resp

        raise DiscordBlocked(
            f"{label} failed after {self.max_retries} attempts"
        ) from last_error

    # -- public ------------------------------------------------------------

    async def get_page(
        self, path_or_url: str, *, params: dict[str, Any] | None = None
    ) -> tuple[str, str]:
        """GET a server-rendered page. Returns (final_url, body)."""
        url = _absolute(path_or_url, SITE_ROOT)
        if params:
            # quote_via=quote keeps "science & tech" intact as a path-adjacent
            # value; the default quote_plus would turn spaces into + signs,
            # which Discord's router does not accept.
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        resp = await self._request(url, tier="page", label=url)
        return str(resp.url), (resp.text or "")

    async def get_api(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        """GET a /api/v10 endpoint and decode its JSON."""
        url = _absolute(path, API_ROOT)
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        resp = await self._request(url, tier="api", label=url)
        body = resp.text or ""
        try:
            return json.loads(body)
        except ValueError as exc:
            raise DiscordBlocked(
                f"{url} answered HTTP {resp.status_code} with non-JSON "
                f"({len(body)} bytes); Discord may be serving an error page"
            ) from exc


def _absolute(path_or_url: str, root: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return root.rstrip("/") + "/" + path_or_url.lstrip("/")


def _json_error(resp: Any) -> dict[str, Any] | None:
    """Discord's error bodies are JSON `{"message":..., "code":...}`."""
    try:
        parsed = json.loads(resp.text or "")
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
