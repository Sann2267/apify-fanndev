"""HTTP client: curl_cffi TLS impersonation, exponential backoff, host failover.

The target needs no token, no cookie warm-up and no signed parameters — the one
thing it *does* need is to be asked on the un-challenged host. This client keeps
that decision in one place and fails loudly if the open host ever closes.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession

from .constants import (
    BROWSER_HEADERS,
    CHALLENGE_MARKERS,
    HOST_LADDER,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_LADDER,
    TLS_PROFILE,
)


class BlockedError(RuntimeError):
    """Every host/TLS combination was challenged — retrying will not help."""


class UnexpectedShape(RuntimeError):
    """A 200 came back but the document no longer matches the parsed contract.

    Raised rather than returning [] so an upstream redesign surfaces as a failed
    run instead of silently emptying the dataset.
    """


def is_challenge(status: int, body: str) -> bool:
    """True when Cloudflare served an interstitial instead of the page."""
    if status in (403, 503) and any(m in body for m in CHALLENGE_MARKERS):
        return True
    return status == 403


class YellowPagesClient:
    """Async fetcher with a TLS ladder and an ordered host ladder."""

    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str = TLS_PROFILE,
        timeout: int = REQUEST_TIMEOUT,
        log: Any = None,
    ) -> None:
        self.proxy_url = proxy_url
        self.profile = profile
        self.timeout = timeout
        self.log = log
        self._session: AsyncSession | None = None
        # Host + profile that last worked; tried first to avoid re-walking the
        # ladder on every request.
        self._host = HOST_LADDER[0]
        self._profile_idx = 0

    async def __aenter__(self) -> "YellowPagesClient":
        self._session = AsyncSession(
            impersonate=self.profile,
            timeout=self.timeout,
            headers=dict(BROWSER_HEADERS),
            proxies={"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None,
            verify=False,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _debug(self, msg: str) -> None:
        if self.log:
            self.log.debug(msg)

    def _warn(self, msg: str) -> None:
        if self.log:
            self.log.warning(msg)

    @property
    def host(self) -> str:
        return self._host

    def build(self, path: str, params: dict[str, Any] | None = None, host: str | None = None) -> str:
        base = (host or self._host) + path
        if params:
            clean = {k: v for k, v in params.items() if v not in (None, "")}
            if clean:
                return base + ("&" if "?" in base else "?") + urlencode(clean)
        return base

    async def get_text(self, path: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
        """Fetch a document. Returns (html, resolved_url).

        Walks host x TLS ladder on challenge, and backs off exponentially on
        transport errors and 429/5xx.
        """
        if self._session is None:
            raise RuntimeError("YellowPagesClient used outside its async context manager")

        last_detail = "no attempt made"

        # Try the known-good host first, then the rest of the ladder.
        hosts = [self._host] + [h for h in HOST_LADDER if h != self._host]

        for host in hosts:
            for attempt in range(MAX_RETRIES):
                url = self.build(path, params, host=host)
                try:
                    resp = await self._session.get(url, allow_redirects=True)
                except Exception as exc:  # transport: DNS blips, resets, timeouts
                    last_detail = f"{type(exc).__name__}: {exc}"
                    await self._sleep(attempt)
                    continue

                body = resp.text or ""

                if resp.status_code == 200 and not is_challenge(200, body):
                    if host != self._host:
                        self._warn(f"host failover: now using {host}")
                        self._host = host
                    return body, str(resp.url)

                if is_challenge(resp.status_code, body):
                    # A challenge is a property of the zone, not of this attempt.
                    # Rotate the TLS profile once, then move to the next host.
                    last_detail = (
                        f"cf-mitigated={resp.headers.get('cf-mitigated', '-')} "
                        f"status={resp.status_code} host={host}"
                    )
                    if self._profile_idx + 1 < len(TLS_LADDER):
                        self._profile_idx += 1
                        await self._reopen(TLS_LADDER[self._profile_idx])
                        self._warn(f"challenged on {host}; retrying with TLS {self.profile}")
                        continue
                    break  # exhausted profiles on this host -> next host

                # A record that does not exist 302s to /410 (Gone) rather than
                # answering 404, so treat both — and a landing on /410 — as
                # "absent" and let the caller decide whether that is fatal.
                if resp.status_code in (404, 410) or str(resp.url).rstrip("/").endswith("/410"):
                    return "", str(resp.url)

                if resp.status_code in (429, 500, 502, 503, 504):
                    last_detail = f"status={resp.status_code} host={host}"
                    await self._sleep(attempt, floor=2.0 if resp.status_code == 429 else 0.0)
                    continue

                last_detail = f"unexpected status={resp.status_code} host={host}"
                await self._sleep(attempt)

        raise BlockedError(f"all hosts/profiles exhausted for {path} ({last_detail})")

    async def _reopen(self, profile: str) -> None:
        """Swap the TLS fingerprint; curl_cffi binds it at session creation."""
        if self._session is not None:
            await self._session.close()
        self.profile = profile
        self._session = AsyncSession(
            impersonate=profile,
            timeout=self.timeout,
            headers=dict(BROWSER_HEADERS),
            proxies={"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None,
            verify=False,
        )

    async def _sleep(self, attempt: int, floor: float = 0.0) -> None:
        delay = max(floor, RETRY_DELAY_BASE ** (attempt + 1)) + random.uniform(0, 0.4)
        self._debug(f"backoff {delay:.2f}s (attempt {attempt + 1}/{MAX_RETRIES})")
        await asyncio.sleep(delay)
