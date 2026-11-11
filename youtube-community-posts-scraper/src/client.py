"""HTTP transport for youtube.com community-post pages.

``/@handle/posts`` answered 200 on every probe on 2026-09-20 across four TLS
profiles, with no challenge. The failure mode to guard against is not a block
but an **empty answer**: a full-size page whose post list never arrives.

``get`` therefore takes the marker it needs and keeps asking until the body
contains it. A body that never carries it raises :class:`Reduced`, which the
caller turns into a ``REDUCED`` record -- distinct from a channel that has
genuinely never posted, and distinct again from a channel whose community tab
is switched off (the page says so in words; see ``constants.UNAVAILABLE_MARKER``).
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_ATTEMPTS,
    MIN_PAGE_BYTES,
    RETRY_DELAY_BASE,
    TLS_LADDER,
)

log = logging.getLogger(__name__)

BLOCK_MARKERS = (
    "Just a moment",
    "challenge-platform",
    "Our systems have detected unusual traffic",
    "confirm you're not a robot",
)


class Blocked(Exception):
    """A genuine challenge, as opposed to a reduced page."""


class NotFound(Exception):
    """No such video, channel or handle."""


class Reduced(Exception):
    """200 with a real page that never carried the payload we asked for.

    Distinct from :class:`Blocked` on purpose. The caller turns this into a
    ``REDUCED`` record so a user can tell "YouTube withheld it" apart from
    "this video genuinely has no description".
    """


class YouTubeClient:
    def __init__(self, proxy_url: str | None = None, profile: str | None = None):
        self._proxy_url = proxy_url
        self._ladder = list(TLS_LADDER)
        if profile:
            self._ladder = [profile] + [p for p in self._ladder if p != profile]
        self._winner = self._ladder[0]
        self.attempts_used = 0

    def _new_session(self, profile: str) -> AsyncSession:
        session = AsyncSession(
            impersonate=profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=75,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    async def get(
        self,
        url: str,
        marker: str | None = None,
        min_bytes: int = MIN_PAGE_BYTES,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> tuple[str, str, int]:
        """Return ``(body, winning_tls_profile, attempts)``.

        ``marker`` is the substring the body must contain to count as a real
        answer. Rotating the TLS profile between attempts costs nothing and
        occasionally shakes a different edge node loose.
        """
        order = [self._winner] + [p for p in self._ladder if p != self._winner]
        last_len = 0

        for attempt in range(1, max_attempts + 1):
            profile = order[(attempt - 1) % len(order)]
            session = self._new_session(profile)
            try:
                response = await session.get(url)
                body = response.text or ""
                last_len = len(body)

                if response.status_code == 404:
                    raise NotFound(url)
                if any(m in body[:6000] for m in BLOCK_MARKERS):
                    raise Blocked(f"challenge page on {profile}")
                if response.status_code >= 400:
                    log.debug("%s -> HTTP %s on %s", url, response.status_code, profile)
                elif len(body) >= min_bytes and (marker is None or marker in body):
                    self._winner = profile
                    self.attempts_used = attempt
                    return body, profile, attempt
            except (NotFound, Blocked):
                raise
            except Exception as exc:  # network-level, worth another rung
                log.debug("%s on %s: %s", type(exc).__name__, profile, exc)
            finally:
                await session.close()

            if attempt < max_attempts:
                await asyncio.sleep(RETRY_DELAY_BASE * attempt)

        self.attempts_used = max_attempts
        raise Reduced(
            f"{url}: {max_attempts} attempts, last body {last_len}B, "
            f"marker {marker!r} never present"
        )
