"""HTTP client for indotrading.com: TLS impersonation, backoff, rotation."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import urllib.parse
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    BLOCK_MARKERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECS,
    HOME_TITLE_MARKER,
    SITE_ROOT,
    TLS_PROFILES,
    WEBAPI_ROOT,
)

log = logging.getLogger("indotrading.client")

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)


class IndotradingBlocked(Exception):
    """Cloudflare answered with a challenge instead of the page."""


class IndotradingNotFound(Exception):
    """The path is well formed but indotrading has nothing behind it.

    Raised for the homepage-fallback case: the site answers an unknown path
    with HTTP 200 and the full homepage rather than a 404, so a caller that
    asked for a category and got the homepage has hit a dead slug.
    """


class IndotradingClient:
    """One client per run, holding a curl_cffi session for the active profile.

    Cloudflare gates indotrading on the TLS fingerprint only: every
    impersonation profile in the ladder passed recon on the same address that
    plain `requests` was 403'd on. So the ladder is a recovery path, not a
    search -- a challenge body or an unexpected 403 rotates to the next
    profile and rebuilds the session instead of failing the run.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_timeout: int = DEFAULT_TIMEOUT_SECS,
    ) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self._profile_idx = 0
        self._session: cr.Session | None = None

    # -- session plumbing --------------------------------------------------

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx % len(TLS_PROFILES)]

    def _build_session(self) -> cr.Session:
        kwargs: dict[str, Any] = {
            "impersonate": self.profile,
            "timeout": self.request_timeout,
        }
        if self.proxy_url:
            kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
        return cr.Session(**kwargs)

    def _session_or_new(self) -> cr.Session:
        if self._session is None:
            self._session = self._build_session()
        return self._session

    def rotate_profile(self) -> str:
        self._profile_idx += 1
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing must not mask the real error
                pass
        self._session = None
        log.warning("Rotated TLS profile to %s", self.profile)
        return self.profile

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    # -- headers -----------------------------------------------------------

    @staticmethod
    def _document_headers(referer: str | None) -> dict[str, str]:
        """The header set a browser sends for a top-level navigation.

        curl_cffi impersonation already supplies a matching User-Agent and
        header order; these are the navigation-specific fields it cannot know.
        """
        headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "upgrade-insecure-requests": "1",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none" if referer is None else "same-origin",
            "sec-fetch-user": "?1",
        }
        if referer:
            headers["referer"] = referer
        return headers

    @staticmethod
    def _api_headers(referer: str) -> dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "origin": SITE_ROOT,
            "referer": referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }

    @staticmethod
    def _looks_challenged(body: str) -> bool:
        low = body[:6000].lower()
        return any(m in low for m in BLOCK_MARKERS)

    @staticmethod
    def is_home_fallback(body: str) -> bool:
        """True when the site served its homepage in place of a 404."""
        head = body[:4000].lower()
        return HOME_TITLE_MARKER in head

    # -- core calls --------------------------------------------------------

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: Any = None,
        label: str = "",
    ) -> Any:
        label = label or url
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            if attempt:
                # Exponential backoff with jitter, capped so one bad slice
                # cannot stall a long fan-out.
                delay = min(2**attempt + random.uniform(0, 1.5), 30)
                log.info(
                    "Retry %d/%d for %s in %.1fs",
                    attempt, self.max_retries - 1, label, delay,
                )
                await asyncio.sleep(delay)

            session = self._session_or_new()
            try:
                if method == "POST":
                    resp = await asyncio.to_thread(
                        session.post, url, headers=headers,
                        data=json.dumps(json_body),
                    )
                else:
                    resp = await asyncio.to_thread(session.get, url, headers=headers)
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_error = exc
                log.warning("Transport error on %s: %s", label, exc)
                self.rotate_profile()
                continue

            body = resp.text or ""

            if self._looks_challenged(body):
                last_error = IndotradingBlocked(
                    f"Cloudflare challenge on {label} (HTTP {resp.status_code}, "
                    f"profile {self.profile})"
                )
                self.rotate_profile()
                continue

            if resp.status_code == 403:
                last_error = IndotradingBlocked(f"403 on {label}")
                self.rotate_profile()
                continue

            if resp.status_code in RETRY_STATUS:
                last_error = IndotradingBlocked(f"HTTP {resp.status_code} on {label}")
                log.warning("HTTP %s on %s", resp.status_code, label)
                continue

            if resp.status_code == 404:
                # A real 404, and retrying cannot resurrect it. The site uses
                # all three of these to mean "gone", so they are all mapped to
                # one exception: a bare 24-byte body for a dead category slug,
                # a full "Produk Tidak Ditemukan" page for a dead product id,
                # and (handled in get_page) a 200 carrying the homepage.
                raise IndotradingNotFound(f"HTTP 404 on {label}")

            return resp

        raise last_error or IndotradingBlocked(
            f"{label} failed after {self.max_retries} attempts"
        )

    async def get_page(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
        allow_home_fallback: bool = False,
    ) -> tuple[str, str]:
        """GET an HTML page. Returns (final_url, body).

        Raises IndotradingNotFound when the site answers with the homepage,
        which is how it reports an unknown path -- silently, at HTTP 200.
        """
        url = path_or_url
        if url.startswith("/"):
            url = SITE_ROOT + url
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)

        resp = await self._request(
            "GET", url, headers=self._document_headers(referer), label=url
        )
        body = resp.text or ""
        final_url = str(resp.url)

        if not allow_home_fallback and self.is_home_fallback(body):
            raise IndotradingNotFound(
                f"{url} was answered with the homepage (HTTP {resp.status_code}); "
                "the slug or id does not exist"
            )
        return final_url, body

    async def get_json(
        self, path: str, *, params: dict[str, Any] | None = None, referer: str
    ) -> Any:
        url = WEBAPI_ROOT + path
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        resp = await self._request(
            "GET", url, headers=self._api_headers(referer), label=path
        )
        try:
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise IndotradingBlocked(
                f"non-JSON body on {path} (HTTP {resp.status_code}): "
                f"{(resp.text or '')[:200]}"
            ) from exc

    async def post_json(self, path: str, payload: Any, *, referer: str) -> Any:
        url = WEBAPI_ROOT + path
        headers = self._api_headers(referer)
        headers["content-type"] = "application/json"
        resp = await self._request(
            "POST", url, headers=headers, json_body=payload, label=path
        )
        try:
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise IndotradingBlocked(
                f"non-JSON body on {path} (HTTP {resp.status_code}): "
                f"{(resp.text or '')[:200]}"
            ) from exc
