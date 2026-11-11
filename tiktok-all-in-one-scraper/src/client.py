"""Transport for TikTok's embed surface: one GET, one state blob, no signing.

Every mode is a single request. There is no warm-up-then-replay dance as in the
Instagram actor, because the embed pages are not gated by cookies -- they are
gated by nothing at all, and their companion loader API is gated by a signature
this actor deliberately does not forge (see `constants.py`).

Failure detection matches the **body**, not the status:

* A walled response is `HTTP 200` carrying the 1.4 KB `SlardarWAF` shell. That is
  what the consumer pages always return; if an embed route ever starts doing it,
  it must be treated as a block and not handed to the parser.
* A missing entity is `HTTP 200` with `isError: true` / a non-zero
  `customErrorCode` inside the state, or `HTTP 404` with the same app shell the
  non-existent embed variants return.
* Rate limiting is `HTTP 503` with an empty body, and it arrives after only a
  handful of requests from one IP.
"""

from __future__ import annotations

import asyncio
import json
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    JSON_HEADERS,
    MAX_RETRIES,
    PAGE_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    STATE_SCRIPT_ID,
    TLS_PROFILE_LADDER,
)

logger = logging.getLogger(__name__)

# The tell of TikTok's WAF shell. Its `slardar-config` block names
# `"bid": "slardar_us_waf"` outright, so there is no ambiguity to weigh.
WAF_MARKER = "SlardarWAF"

# Present on a genuine embed page. Checked before a body marker is allowed to
# condemn a response.
CONTENT_MARKER = STATE_SCRIPT_ID


class BlockedError(Exception):
    """Every retry and TLS profile was exhausted while still walled or throttled."""


class NotFoundError(Exception):
    """The username, video id, hashtag or music id does not resolve publicly."""


def is_walled(status: int, html: str) -> bool:
    """True when a response is TikTok's WAF shell or a throttle, not content."""
    if status in (401, 403, 429, 503):
        return True
    if CONTENT_MARKER in html:
        return False
    return WAF_MARKER in html


class TikTokClient:
    """A fingerprint plus an egress IP, rotated together when TikTok pushes back."""

    def __init__(self, proxy_url: str | None = None, new_proxy_url=None) -> None:
        self._new_proxy_url = new_proxy_url
        self._proxy_url = proxy_url
        self._profile_index = 0
        self.session = self._build_session()

    @property
    def profile(self) -> str:
        return TLS_PROFILE_LADDER[self._profile_index % len(TLS_PROFILE_LADDER)]

    def _build_session(self) -> AsyncSession:
        return AsyncSession(
            impersonate=self.profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=REQUEST_TIMEOUT,
        )

    async def rotate(self) -> None:
        """Fresh fingerprint and, with a proxy configured, a fresh egress IP.

        TikTok's embed throttle is IP-bound, so the proxy rotation is the half
        that recovers a run; the fingerprint rotation is cheap insurance.
        """
        self._profile_index += 1
        if self._new_proxy_url is not None:
            try:
                self._proxy_url = await self._new_proxy_url()
            except Exception as exc:  # noqa: BLE001 - rotation is best-effort
                logger.warning("Could not rotate proxy session: %s", exc)
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110 - closing a dead session is moot
            pass
        self.session = self._build_session()
        logger.info("Rotated to TLS profile %s", self.profile)

    async def get_embed_html(self, url: str) -> str:
        """Fetch an embed page and return its HTML.

        Raises `NotFoundError` when TikTok serves the app shell for a route that
        does not exist, and `BlockedError` once the retry budget is spent.
        """
        last_reason = "unknown"
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(url, headers=PAGE_HEADERS)
            except Exception as exc:  # noqa: BLE001 - network flake, retry
                last_reason = f"{type(exc).__name__}: {exc}"
                logger.warning("Embed fetch error for %s: %s", url, last_reason)
            else:
                html = response.text or ""
                status = response.status_code
                # A 404 on an embed route still ships the ~234 KB app shell, so
                # the status is the only way to tell it apart from a real page.
                if status == 404:
                    raise NotFoundError(f"{url} does not resolve to a public embed")
                if not is_walled(status, html):
                    return html
                if WAF_MARKER in html:
                    last_reason = (
                        f"WAF shell behind HTTP {status} ({len(html)} bytes) -- this "
                        "embed route may have been moved behind the consumer gate"
                    )
                else:
                    last_reason = f"HTTP {status}, {len(html)} bytes"
                logger.warning(
                    "Blocked fetching %s (attempt %d/%d, profile %s): %s",
                    url, attempt + 1, MAX_RETRIES, self.profile, last_reason,
                )
                await self.rotate()
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
        raise BlockedError(f"Could not load {url} after {MAX_RETRIES} attempts: {last_reason}")

    async def get_oembed(self, url: str, video_url: str) -> dict:
        """Call the public oEmbed endpoint. Returns the parsed object.

        TikTok answers an unavailable video with `HTTP 400` and a short body, and
        a region-locked or deleted one with `HTTP 200` and an empty body -- the
        latter would look like a parse failure, so it is named for what it is.
        """
        last_reason = "unknown"
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(
                    url, headers={**JSON_HEADERS, "Referer": video_url}
                )
            except Exception as exc:  # noqa: BLE001 - network flake, retry
                last_reason = f"{type(exc).__name__}: {exc}"
                logger.warning("oEmbed error: %s", last_reason)
            else:
                body = (response.text or "").strip()
                if response.status_code == 400:
                    raise NotFoundError(
                        f"oEmbed rejected {video_url} (HTTP 400) -- the video is "
                        "private, deleted or region-locked"
                    )
                if response.status_code == 200 and not body:
                    raise NotFoundError(
                        f"oEmbed returned an empty 200 for {video_url} -- TikTok "
                        "serves that for a url it will not describe (profile urls, "
                        "unavailable videos)"
                    )
                if response.status_code == 200 and body.startswith("{"):
                    try:
                        payload = json.loads(body)
                    except (ValueError, json.JSONDecodeError):
                        last_reason = "200 with unparseable JSON"
                    else:
                        if isinstance(payload, dict) and payload:
                            return payload
                        last_reason = "200 with an empty JSON object"
                else:
                    last_reason = f"HTTP {response.status_code}, {len(body)} bytes"
                logger.warning(
                    "oEmbed rejected (attempt %d/%d, profile %s): %s",
                    attempt + 1, MAX_RETRIES, self.profile, last_reason,
                )
                await self.rotate()
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
        raise BlockedError(f"oEmbed failed after {MAX_RETRIES} attempts: {last_reason}")

    async def resolve_redirect(self, url: str) -> str:
        """Follow a `vm.tiktok.com` / `vt.tiktok.com` short link to its canonical url.

        Only the destination url is wanted -- the page it lands on is the
        WAF-walled consumer route, which this actor never parses.
        """
        try:
            response = await self.session.get(
                url, headers=PAGE_HEADERS, allow_redirects=True
            )
        except Exception as exc:  # noqa: BLE001 - caller turns this into a row
            raise NotFoundError(f"Could not resolve short link {url}: {exc}") from exc
        final = str(response.url or "")
        if not final or "/video/" not in final:
            raise NotFoundError(
                f"Short link {url} did not redirect to a video url (landed on {final!r})"
            )
        return final

    async def close(self) -> None:
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
