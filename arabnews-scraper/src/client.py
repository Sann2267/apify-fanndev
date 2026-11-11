"""HTTP client wrapper -- warmup, retry, profile rotation, block detection.

Arab News sits behind Cloudflare, which scores the TLS fingerprint (see
constants.py for the measured profile matrix). The one thing this client must
get right is that a 403 is a *fingerprint* verdict, not a transient error:
sleeping and replaying the same handshake reproduces it exactly. Every retry
after a block therefore rotates to the next profile in the ladder and opens a
fresh session, because curl_cffi fixes the fingerprint at session construction.

The warmup is what surfaces this first, since it is the first request of a run.
It walks the whole ladder before giving up, so a run only fails when Cloudflare
has refused every measured-good fingerprint on that exit IP.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILES,
    WARMUP_URL,
)

log = logging.getLogger("arabnews.client")

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
    b"_fs_ch_",
    b"Request unsuccessful",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class ArabNewsClient:
    def __init__(self, proxy_url: str | None = None, profile: str | None = None):
        self.proxy_url = proxy_url
        self._profiles = list(TLS_PROFILES)
        if profile and profile in self._profiles:
            # Start the ladder at the caller's choice rather than ignoring it.
            self._profiles.remove(profile)
            self._profiles.insert(0, profile)
        elif profile:
            self._profiles.insert(0, profile)
        self._profile_idx = 0
        self.session: AsyncSession | None = None
        self._warm = False
        self._open_session()

    @property
    def profile(self) -> str:
        return self._profiles[self._profile_idx % len(self._profiles)]

    def _open_session(self) -> None:
        """A session per fingerprint -- curl_cffi binds it at construction."""
        self.session = AsyncSession(
            impersonate=self.profile,
            proxies=(
                {"http": self.proxy_url, "https": self.proxy_url}
                if self.proxy_url
                else None
            ),
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def rotate_profile(self) -> str:
        """Move to the next fingerprint and rebuild the session behind it."""
        previous = self.profile
        self._profile_idx += 1
        await self._close_session()
        self._open_session()
        self._warm = False
        log.info("Cloudflare blocked %s; rotating to %s", previous, self.profile)
        return self.profile

    async def _close_session(self) -> None:
        if self.session is not None:
            try:
                await self.session.close()
            except Exception:  # noqa: BLE001 -- closing must not mask the real error
                pass
            self.session = None

    async def init_session(self):
        """Warm up, walking the profile ladder until one is let through."""
        if self._warm:
            return
        attempts = len(self._profiles)
        last_status = None
        for attempt in range(attempts):
            r = await self.session.get(WARMUP_URL)
            last_status = r.status_code
            if not is_blocked(r):
                self._warm = True
                if attempt:
                    log.info("Warmup succeeded on profile %s", self.profile)
                return
            if attempt < attempts - 1:
                await self.rotate_profile()
                await asyncio.sleep(RETRY_DELAY_BASE)
        raise RuntimeError(
            f"Warmup failed: {last_status}. Cloudflare refused all "
            f"{attempts} TLS profiles on this exit IP. This is an address "
            f"reputation problem, not a parsing one -- run with the Apify "
            f"RESIDENTIAL proxy group, which is this actor's default."
        )

    async def get(self, url: str, **kwargs):
        await self.init_session()
        return await self._with_retry("GET", url, **kwargs)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    # A block is a verdict on the fingerprint, so replaying the
                    # same one is pointless -- take the next profile.
                    await self.rotate_profile()
                    await self.init_session()
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self._close_session()
