"""HTTP client: warm-up, retry with exponential backoff, TLS ladder fallback."""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from curl_cffi.requests import AsyncSession

from src.constants import (
    BROWSER_HEADERS,
    CONSENT_SOCS,
    MAX_RETRIES,
    NAVIGATE_HEADERS,
    RETRY_DELAY_BASE,
    TLS_LADDER,
    TLS_PROFILE,
    WARMUP_URL,
)


class BlockedError(RuntimeError):
    """Upstream refused the request in a way retrying will not fix."""


class UnexpectedShape(RuntimeError):
    """Upstream answered 200 but the payload no longer matches the contract.

    Raised loudly rather than returning an empty list, so a Google-side schema
    change surfaces as a failed run instead of silently emptying the dataset.
    """


def strip_xssi(text: str) -> str:
    """Remove Google's anti-XSSI prefix."""
    for prefix in (")]}'\n\n", ")]}'\n", ")]}'"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


class MapsClient:
    """Thin wrapper around curl_cffi with Google-specific session handling."""

    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str = TLS_PROFILE,
        language: str = "en",
        region: str = "US",
        timeout: int = 45,
        log: Any = None,
    ) -> None:
        self.proxy_url = proxy_url
        self.profile = profile
        self.language = language
        self.region = region
        self.timeout = timeout
        self.log = log
        self._session: AsyncSession | None = None
        self._warm = False

    @property
    def session(self) -> AsyncSession:
        """The live session. Raises if used outside the async context manager."""
        if self._session is None:
            raise RuntimeError("MapsClient used outside its async context manager")
        return self._session

    # -- lifecycle ---------------------------------------------------------
    def _build_session(self, profile: str) -> AsyncSession:
        kwargs: dict[str, Any] = {"impersonate": profile, "timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        session = AsyncSession(**kwargs)
        # Google serves a consent interstitial to clients without these in
        # several regions -- which matters far more behind a proxy, where the
        # exit IP's country decides whether the GDPR wall appears at all.
        # CONSENT alone is no longer enough; SOCS is what current Google checks.
        session.cookies.set("CONSENT", "YES+1", domain=".google.com")
        session.cookies.set("SOCS", CONSENT_SOCS, domain=".google.com")
        return session

    async def __aenter__(self) -> "MapsClient":
        self._session = self._build_session(self.profile)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def reset(self, profile: str | None = None) -> None:
        """Drop the session (and its cookie jar) and force a fresh warm-up."""
        await self.close()
        if profile:
            self.profile = profile
        self._session = self._build_session(self.profile)
        self._warm = False

    # -- warm-up -----------------------------------------------------------
    async def ensure_warm(self) -> None:
        """Visit the Maps root once per session to seed Google's cookie jar."""
        if self._warm:
            return
        assert self._session is not None
        resp = await self._session.get(WARMUP_URL, headers=NAVIGATE_HEADERS)
        if resp.status_code != 200:
            raise BlockedError(f"warm-up returned HTTP {resp.status_code}")
        self._warm = True

    # -- requests ----------------------------------------------------------
    async def get_html(self, url: str, params: dict | None = None) -> str:
        """GET an HTML page using navigation headers."""
        assert self._session is not None
        resp = await self._request(url, params=params, headers=NAVIGATE_HEADERS)
        return resp.text

    async def get_rpc(self, url: str, params: dict) -> Any:
        """GET a Google RPC endpoint and return parsed JSON.

        An empty body is a real answer from this endpoint (it means "request
        understood, nothing to give"), so it maps to None rather than an error.
        """
        await self.ensure_warm()
        resp = await self._request(url, params=params, headers=BROWSER_HEADERS)
        body = resp.text
        if not body.strip():
            return None
        try:
            return json.loads(strip_xssi(body))
        except json.JSONDecodeError as exc:
            raise UnexpectedShape(
                f"RPC returned non-JSON ({len(body)} bytes): {body[:200]!r}"
            ) from exc

    async def _request(self, url: str, params: dict | None, headers: dict):
        """Issue a request with exponential backoff and a TLS ladder fallback."""
        assert self._session is not None
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._session.get(url, params=params, headers=headers)
            except Exception as exc:  # transport-level failure
                last_error = exc
                await self._backoff(attempt, f"transport error: {exc}")
                continue

            if resp.status_code == 200:
                return resp

            # 400 means our payload is wrong -- retrying identical bytes cannot
            # help, so fail fast with a diagnostic instead of burning retries.
            if resp.status_code == 400:
                raise UnexpectedShape(
                    "Google rejected the request payload (HTTP 400). The "
                    "GetLocalBoqProxy contract has most likely changed."
                )

            if resp.status_code in (403, 429, 503):
                # Rotate identity before the next attempt: new TLS profile and a
                # fresh cookie jar (and a fresh exit IP when a rotating proxy is
                # configured).
                last_error = BlockedError(f"HTTP {resp.status_code}")
                next_profile = TLS_LADDER[(attempt + 1) % len(TLS_LADDER)]
                await self._backoff(attempt, f"HTTP {resp.status_code}; rotating to {next_profile}")
                await self.reset(next_profile)
                continue

            last_error = BlockedError(f"HTTP {resp.status_code}")
            await self._backoff(attempt, f"HTTP {resp.status_code}")

        raise BlockedError(f"retries exhausted: {last_error}")

    async def _backoff(self, attempt: int, reason: str) -> None:
        delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 0.4)
        if self.log:
            self.log.warning(f"retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s ({reason})")
        await asyncio.sleep(delay)
