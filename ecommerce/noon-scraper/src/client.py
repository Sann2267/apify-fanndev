"""HTTP client for the noon catalogue gateway.

No WAF was found behind `/_vs/nc/` during recon, so this client is deliberately
plain: no token harvesting and no signature. What it does have
to get right is the difference between the four answers that matter:

  200 + JSON body            the real thing.
  404 + {"userMessage": ...} a genuinely dead SKU or category. Final answer,
                             never retried.
  403/200 + AkamaiGHost body the Akamai edge ACL -- this is what the S2 origin
                             host returns from a denied network. Retrying is
                             pointless; the caller falls back or gives up.
  5xx / transport            transient; retried with exponential backoff and
                             a rotated TLS profile.

The TLS ladder is insurance, not a measured requirement: all five profiles
returned byte-identical payloads during recon. It exists so that a future edge
rule on this host degrades into a rotation rather than a dead actor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

from curl_cffi import requests as cr

from .constants import (
    BLOCK_MARKERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    GATEWAY_HOST,
    INSTANT_API_PREFIX,
    INSTANT_DEFAULTS,
    MP_API_PREFIX,
    ORIGIN_HOST,
    RATE_LIMIT_COOLDOWN_SECS,
    RETRY_STATUS,
    SITE_PATH_BY_LOCALE,
    TLS_PROFILES,
)

log = logging.getLogger("noon.client")


class NoonError(Exception):
    """Base for the outcomes callers route on."""


class NoonNotFound(NoonError):
    """The catalogue answered definitively that the entity does not exist."""


class NoonBlocked(NoonError):
    """An edge refused us, or a status survived the whole retry ladder."""


def _looks_blocked(body: bytes) -> bool:
    """Detect an edge refusal from the body, not just the status.

    The Akamai deny page is small and can arrive under a 403 or, on some
    paths, a 200. Only the head is scanned -- these markers are always in the
    first bytes and the real payloads are hundreds of KB.
    """
    head = body[:2048]
    return any(m in head for m in BLOCK_MARKERS)


class NoonClient:
    """Async JSON client over the noon catalogue gateway.

    Parameters mirror the actor input so every knob a run exposes is honoured
    here rather than hard-coded.
    """

    def __init__(
        self,
        *,
        proxy_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_timeout: int = DEFAULT_TIMEOUT_SECS,
        request_delay: float = DEFAULT_REQUEST_DELAY_SECS,
        allow_origin_fallback: bool = True,
    ) -> None:
        self.proxy_url = proxy_url
        self.max_retries = max(1, int(max_retries))
        self.request_timeout = int(request_timeout)
        self.request_delay = max(0.0, float(request_delay))
        self.allow_origin_fallback = allow_origin_fallback
        self._profile_idx = 0
        self._session: cr.AsyncSession | None = None
        # Set once S1 has proved itself, so a later transient failure on the
        # gateway is not misread as "the gateway is gone, switch to origin".
        self._gateway_ok = False
        # Diagnostic from the Minutes storefront warm-up; None until first use.
        self._instant_warm: str | None = None

    # -- plumbing --------------------------------------------------------

    def _session_for(self, profile: str) -> cr.AsyncSession:
        """One session per profile switch, so connection reuse still applies."""
        if self._session is None:
            kwargs: dict[str, Any] = {
                "impersonate": profile,
                "timeout": self.request_timeout,
            }
            if self.proxy_url:
                kwargs["proxies"] = {"http": self.proxy_url, "https": self.proxy_url}
            self._session = cr.AsyncSession(**kwargs)
        return self._session

    async def _reset_session(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001 - closing must never break a run
                pass
            self._session = None

    def _next_profile(self) -> str:
        self._profile_idx = (self._profile_idx + 1) % len(TLS_PROFILES)
        return TLS_PROFILES[self._profile_idx]

    @property
    def profile(self) -> str:
        return TLS_PROFILES[self._profile_idx]

    async def close(self) -> None:
        await self._reset_session()

    # -- headers ---------------------------------------------------------

    @staticmethod
    def mp_headers(locale: str) -> dict[str, str]:
        """Headers for the main marketplace catalogue.

        Recon showed the endpoint answers 200 with NO custom headers at all,
        but `x-locale` is the one that actually changes the answer (country,
        currency and language), so it is always sent. The rest make the call
        look like the Minutes app's own server-side fetch.
        """
        return {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "x-locale": locale,
            "x-mp": "noon",
            "x-experience": "noon",
            "x-platform": "web",
            "referer": f"{GATEWAY_HOST}/",
            "origin": GATEWAY_HOST,
        }

    @staticmethod
    def instant_headers(locale: str, zone: dict[str, str] | None = None) -> dict[str, str]:
        """Headers for noon Minutes.

        Minutes is warehouse-scoped: without the lat/lng and zone codes the
        service cannot decide which dark store's catalogue to answer with.
        """
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "x-locale": locale,
            "x-mp": "nooninstant",
            "x-experience": "nooninstant",
            "x-platform": "mweb",
            "referer": f"{GATEWAY_HOST}/",
            "origin": GATEWAY_HOST,
        }
        headers.update(INSTANT_DEFAULTS)
        if zone:
            headers.update({k: v for k, v in zone.items() if v})
        return headers

    # -- core fetch ------------------------------------------------------

    async def get_json(
        self,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        allow_404: bool = False,
        prefix: str = MP_API_PREFIX,
        allow_origin_fallback: bool | None = None,
    ) -> dict[str, Any]:
        """GET a catalogue path and return parsed JSON.

        Tries the S1 gateway host first and, only if S1 is refused at the edge
        before it has ever worked, the S2 origin host. Raises NoonNotFound on a
        real 404 (unless allow_404), NoonBlocked on anything that survives the
        ladder.
        """
        use_fallback = (
            self.allow_origin_fallback if allow_origin_fallback is None
            else allow_origin_fallback
        )
        hosts = [GATEWAY_HOST]
        if use_fallback and not self._gateway_ok:
            hosts.append(ORIGIN_HOST)

        last_detail = "no attempt made"
        for host in hosts:
            url = f"{host}{prefix}{path}"
            try:
                data = await self._get_with_retries(
                    url, headers=headers, params=params, allow_404=allow_404
                )
            except NoonBlocked as exc:
                last_detail = f"{host}: {exc}"
                log.warning("Host %s refused us (%s); trying next host if any.", host, exc)
                continue
            if host == GATEWAY_HOST:
                self._gateway_ok = True
            return data
        raise NoonBlocked(last_detail)

    async def _get_with_retries(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        allow_404: bool,
    ) -> dict[str, Any]:
        delay = 1.0
        last_detail = ""
        for attempt in range(1, self.max_retries + 1):
            if self.request_delay:
                await asyncio.sleep(self.request_delay)
            session = self._session_for(self.profile)
            try:
                resp = await session.get(url, headers=headers, params=params)
            except Exception as exc:  # noqa: BLE001 - transport errors are retryable
                last_detail = f"{type(exc).__name__}: {exc}"
                log.warning("Transport error (attempt %d/%d) on %s: %s",
                            attempt, self.max_retries, url, last_detail)
                await self._reset_session()
                self._next_profile()
                await asyncio.sleep(delay + random.uniform(0, 0.4))
                delay = min(delay * 2, 30.0)
                continue

            body = resp.content or b""
            status = resp.status_code

            # An edge refusal can wear a 200, so check the body first.
            if _looks_blocked(body):
                raise NoonBlocked(
                    f"edge refusal at {url.split('/')[2]} (HTTP {status}, "
                    f"{len(body)} bytes). This is the Akamai ACL, not a "
                    f"fingerprint gate -- retrying cannot clear it."
                )

            if status == 404:
                detail = body[:200].decode("utf-8", "replace")
                if allow_404:
                    return {}
                raise NoonNotFound(f"HTTP 404 from noon: {detail}")

            if status == 200:
                try:
                    return json.loads(body)
                except ValueError as exc:
                    # A 200 that is not JSON is a shape change, not a hiccup.
                    # Fail loud rather than return an empty dict.
                    raise NoonBlocked(
                        f"200 but body is not JSON ({exc}); first bytes: "
                        f"{body[:120]!r}"
                    ) from exc

            if status in RETRY_STATUS:
                last_detail = f"HTTP {status}"
                if status == 429:
                    log.warning("HTTP 429 -- sitting still for %.0fs (a volume "
                                "limit is not fingerprint-shaped).",
                                RATE_LIMIT_COOLDOWN_SECS)
                    await asyncio.sleep(RATE_LIMIT_COOLDOWN_SECS)
                else:
                    log.warning("HTTP %d (attempt %d/%d) on %s; backing off %.1fs",
                                status, attempt, self.max_retries, url, delay)
                    await asyncio.sleep(delay + random.uniform(0, 0.4))
                    delay = min(delay * 2, 30.0)
                await self._reset_session()
                self._next_profile()
                continue

            # Anything else (401/403/...) is not something a retry fixes.
            raise NoonBlocked(
                f"HTTP {status} from {url}: {body[:200].decode('utf-8', 'replace')}"
            )

        raise NoonBlocked(f"all {self.max_retries} attempts failed ({last_detail})")

    # -- typed calls -----------------------------------------------------

    async def catalog_page(
        self, path: str, *, locale: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """A listing page: search, category or brand -- all one endpoint shape."""
        return await self.get_json(path, headers=self.mp_headers(locale), params=params)

    async def product_detail(self, sku: str, *, locale: str) -> dict[str, Any]:
        """PDP for a SKU.

        The slug segment is cosmetic: recon confirmed `/<anything>/<sku>/p/`
        returns the same 113 KB payload as the real slug, while a bogus SKU
        with the real slug 404s. So the actor never has to resolve a slug and
        callers can pass a bare SKU.
        """
        return await self.get_json(
            f"/p/{sku}/p/", headers=self.mp_headers(locale)
        )

    async def _warm_instant(self, locale: str) -> str:
        """GET the Minutes storefront once before using its API.

        Two jobs. It picks up whatever the edge wants to set, and -- more
        useful -- it tells us WHICH failure we are looking at when the API
        404s, because the storefront page and the API are routed separately.
        """
        if self._instant_warm is not None:
            return self._instant_warm
        country = locale.split("-")[-1]
        site = SITE_PATH_BY_LOCALE.get((country, locale.split("-")[0]), "uae-en")
        url = f"{GATEWAY_HOST}/{site}/"
        try:
            session = self._session_for(self.profile)
            resp = await session.get(url, headers={"accept": "text/html,*/*"})
            self._instant_warm = f"HTTP {resp.status_code}, {len(resp.content)} bytes"
        except Exception as exc:  # noqa: BLE001 - diagnostic only
            self._instant_warm = f"{type(exc).__name__}: {exc}"
        log.info("noon Minutes storefront warm-up (%s): %s", url, self._instant_warm)
        return self._instant_warm

    async def instant_page(
        self, path: str, *, locale: str, params: dict[str, Any],
        zone: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """A noon Minutes listing page (different service, different shape)."""
        warm = await self._warm_instant(locale)
        try:
            return await self.get_json(
                path,
                headers=self.instant_headers(locale, zone),
                params=params,
                prefix=INSTANT_API_PREFIX,
                # The origin host does not mount `/_svc/` at all -- falling back
                # to it turns a clear "Minutes refused us" into a meaningless
                # `404 page not found` from a Go router. Measured on the first
                # cloud run, which is exactly how this was found.
                allow_origin_fallback=False,
            )
        except (NoonBlocked, NoonNotFound) as exc:
            # Minutes is gated on the CLIENT NETWORK, by a path-scoped rule.
            # Measured from an Apify datacentre address: on the SAME host, the
            # marketplace gateway `/_vs/nc/` returned 200 and full data, while
            # the Minutes storefront page and `/_svc/` both returned 403 with
            # a ~6 KB challenge body. From a residential address both work.
            # So this is not about the query, the zone or the country -- it is
            # the exit IP, and a proxy is the fix.
            raise NoonBlocked(
                "noon Minutes refused this network. On the same host the main "
                "noon catalogue answered normally, so this is a rule on the "
                "Minutes paths specifically, not an outage and not a bad "
                f"query. Storefront warm-up: {warm}. Underlying: {exc}. "
                "Fix: switch on Apify Proxy (RESIDENTIAL, country of the "
                "storefront you want) for this mode -- the other seven modes "
                "do not need it."
            ) from exc
