"""HTTP transport for psacard.com.

One rule dominates: the TLS fingerprint decides whether Cloudflare answers at
all (see constants.TLS_LADDER). The client therefore owns a *profile ladder*
rather than a single profile -- it starts on the profile that works today and
only walks the rest if that one starts being challenged, which is exactly the
failure mode to expect when Cloudflare retunes a rule.

A challenge is detected by **body marker as well as status code**, because
Cloudflare serves its interstitial with a 200 as often as with a 403.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    CHALLENGE_MARKERS,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_LADDER,
)


class CertNotFound(Exception):
    """PSA has no such certification number."""


class ChallengedUpstream(Exception):
    """Cloudflare challenged every profile in the ladder."""


def is_challenge(response) -> bool:
    if response.status_code in (403, 429, 503):
        return True
    head = response.content[:20000] if response.content else b""
    return any(m in head for m in CHALLENGE_MARKERS)


class PSAClient:
    def __init__(self, proxy_url: str | None = None, profiles: tuple = TLS_LADDER):
        self.proxy_url = proxy_url
        self.profiles = profiles
        # The working profile is remembered for the life of the client so a
        # multi-cert run pays the ladder cost at most once.
        self._profile_index = 0
        self._session = self._new_session(self.profiles[0])

    def _new_session(self, profile: str) -> AsyncSession:
        session = AsyncSession(
            impersonate=profile,
            proxies={"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None,
            timeout=45,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    @property
    def profile(self) -> str:
        return self.profiles[self._profile_index]

    async def get_html(self, url: str) -> str:
        last_status = None
        for index in range(self._profile_index, len(self.profiles)):
            if index != self._profile_index:
                await self._session.close()
                self._profile_index = index
                self._session = self._new_session(self.profiles[index])

            for attempt in range(MAX_RETRIES):
                try:
                    r = await self._session.request("GET", url, allow_redirects=True)
                except Exception:  # noqa: BLE001 -- network error, retry then fall through
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue

                last_status = r.status_code
                if r.status_code == 404:
                    raise CertNotFound(f"404 for {url}")
                if is_challenge(r):
                    # A challenge is a profile problem, not a timing problem:
                    # retrying the same fingerprint reproduces it exactly.
                    break
                # PSA answers 200 with a redirect to the sign-in app for the
                # account-only sections. Treated as "not public", never parsed.
                if "signin" in str(r.url):
                    raise ChallengedUpstream(
                        f"{url} redirected to a sign-in page -- that section is account-only."
                    )
                return r.text or ""

        raise ChallengedUpstream(
            f"every TLS profile in {self.profiles} was challenged for {url} "
            f"(last status {last_status}). Cloudflare's rule may have changed."
        )

    async def close(self):
        await self._session.close()
