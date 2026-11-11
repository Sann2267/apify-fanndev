"""HTTP client for arbitrary third-party websites.

The important difference from a single-target scraper: there is no target. Every
request goes to a different company's site, so a failure is normal data about
that prospect (parked domain, expired certificate, firewall) rather than a sign
that anything is wrong on our side. Failures are therefore classified and
returned, never retried into the ground.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from curl_cffi.requests import AsyncSession

from src.constants import (
    BROWSER_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailure(RuntimeError):
    """A site could not be fetched. `kind` says what a buyer should conclude."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def classify_transport_error(exc: Exception) -> str:
    """Map a transport exception onto something a buyer can act on."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if "resolve" in text or "name or service" in text or "getaddrinfo" in text:
        return "dns_failure"
    if "certificate" in text or "ssl" in text or "tls" in text:
        return "tls_failure"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "connection" in text or "refused" in text or "reset" in text:
        return "connection_failed"
    return "transport_error"


class WebClient:
    def __init__(
        self,
        proxy_url: str | None = None,
        profile: str = TLS_PROFILE,
        timeout: int = 30,
        log: Any = None,
    ) -> None:
        self.proxy_url = proxy_url
        self.profile = profile
        self.timeout = timeout
        self.log = log
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "WebClient":
        kwargs: dict[str, Any] = {"impersonate": self.profile, "timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        self._session = AsyncSession(**kwargs)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def fetch(self, url: str) -> dict:
        """Fetch a page and return its body, headers, cookies and final URL."""
        if self._session is None:
            raise RuntimeError("WebClient used outside its async context manager")

        last: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._session.get(
                    url, headers=BROWSER_HEADERS, allow_redirects=True
                )
            except Exception as exc:
                kind = classify_transport_error(exc)
                # A domain that does not resolve will not resolve on retry, and
                # a bad certificate will not fix itself either. Both are final
                # answers about the prospect, so return immediately.
                if kind in ("dns_failure", "tls_failure"):
                    raise FetchFailure(kind, f"{type(exc).__name__}: {exc}") from exc
                last = exc
                await self._backoff(attempt, kind)
                continue

            if resp.status_code < 400:
                return {
                    "html": resp.text,
                    "headers": dict(resp.headers),
                    "cookies": list(resp.cookies.keys()),
                    "finalUrl": str(resp.url),
                    "statusCode": resp.status_code,
                }

            # 4xx is the site's settled answer; only 429/5xx are worth retrying.
            if resp.status_code < 500 and resp.status_code != 429:
                raise FetchFailure(
                    "http_error", f"HTTP {resp.status_code} at {resp.url}"
                )
            last = FetchFailure("http_error", f"HTTP {resp.status_code}")
            await self._backoff(attempt, f"HTTP {resp.status_code}")

        raise FetchFailure("unreachable", f"retries exhausted: {last}")

    async def fetch_text(self, url: str) -> str | None:
        """Best-effort fetch for optional extras; None rather than raising."""
        try:
            result = await self.fetch(url)
        except FetchFailure:
            return None
        except Exception:
            return None
        return result["html"]

    async def _backoff(self, attempt: int, reason: str) -> None:
        delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 0.3)
        if self.log:
            self.log.warning(f"retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s ({reason})")
        await asyncio.sleep(delay)
