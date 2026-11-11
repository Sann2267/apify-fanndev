"""HTTP client wrapper for the PNG IPA Registry Services 'corp' API.

See `constants.py` for the full recon summary. In short: `/Api/Corp/*` calls
need a rotating `PA-Token` header harvested from a real page fetch, plus the
session cookies (`ASP.NET_SessionId`, `ARRAffinity`) that fetch establishes.
This client harvests the token once per client instance, threads the
rotating value returned on each API response into the next call, and
re-harvests (once) on a 401/403 before giving up.
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    API_HEADERS,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    PROFILE_API_URL,
    PROFILE_PAGE_URL,
    RETRY_DELAY_BASE,
    SEARCH_API_URL,
    SEARCH_PAGE_URL,
    TLS_PROFILE,
)

PA_TOKEN_RE = re.compile(r'id="paToken"(?:\s+value="([^"]*)")?')


class PaTokenNotFound(Exception):
    """The harvest page didn't contain a #paToken hidden input -- page shape drift."""


class IpaApiError(Exception):
    """Non-2xx from /Api/Corp/* that isn't a recognized auth-retry case."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body[:300]}")


class IpaClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._pa_token: str | None = None

    async def _harvest_token(self, page_url: str) -> str:
        r = await self._request_with_retry("GET", page_url)
        if r.status_code != 200:
            raise RuntimeError(f"Token-harvest page {page_url} returned {r.status_code}")
        m = PA_TOKEN_RE.search(r.text)
        if not m or not m.group(1):
            raise PaTokenNotFound(f"No #paToken hidden input found on {page_url}")
        self._pa_token = m.group(1)
        return self._pa_token

    async def _api_get(self, url: str, params: dict, referer: str, harvest_url: str) -> dict:
        if not self._pa_token:
            await self._harvest_token(harvest_url)

        for attempt in range(2):  # 1 retry after a fresh token harvest
            headers = {**API_HEADERS, "Referer": referer, "PA-Token": self._pa_token}
            r = await self._request_with_retry("GET", url, params=params, headers=headers)

            new_token = r.headers.get("PA-Token")
            if new_token:
                self._pa_token = new_token

            if r.status_code == 200:
                return r.json()
            if r.status_code in (401, 403) and attempt == 0:
                await self._harvest_token(harvest_url)
                continue
            raise IpaApiError(r.status_code, r.text)

        raise IpaApiError(r.status_code, r.text)  # noqa: F821 -- loop always assigns r before falling through

    async def search_corp(self, term: str, page: int, page_size: int, entity_type_id: int | None) -> dict:
        params = {
            "Term": term,
            "PaginationPageSize": page_size,
            "PaginationCurrentPage": page,
            "ExcludePending": "true",
            "OrderBy": "",
            "OrderAscending": "true",
        }
        if entity_type_id:
            params["CompanyTypeId"] = entity_type_id
        return await self._api_get(SEARCH_API_URL, params, SEARCH_PAGE_URL, SEARCH_PAGE_URL)

    async def get_corp_profile(self, corp_id: str) -> dict:
        # Token is harvested from the *search* page, not
        # `EntityProfile.aspx?id=<corp_id>` -- an invalid/nonexistent
        # corp_id makes that page-load 302-redirect server-side to a generic
        # `Error.aspx`, which carries an EMPTY `#paToken` (no `value=` attr
        # at all). The search page has no such per-ID failure mode and the
        # token is bound to the session, not to which page fetched it, so
        # harvesting from there works for every corp_id including bad ones
        # (which the JSON API itself handles gracefully -- see
        # extractor.is_not_found_profile).
        referer = f"{PROFILE_PAGE_URL}?id={corp_id}"
        return await self._api_get(PROFILE_API_URL, {"id": corp_id}, referer, SEARCH_PAGE_URL)

    async def _request_with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (429, 500, 502, 503, 504):
                    last_exc = RuntimeError(f"HTTP {r.status_code} from {url}")
                    await self._sleep(attempt)
                    continue
                return r
            except (RuntimeError, ConnectionError, RequestException) as e:
                # NOTE: curl_cffi's own `ConnectionError` (raised on a failed
                # proxy CONNECT tunnel, DNS failure, etc.) does NOT inherit
                # from Python's builtin `ConnectionError` -- its MRO is
                # RequestException -> CurlError -> OSError, a parallel
                # hierarchy with the same class name. Both are caught
                # explicitly here (see guardian-nigeria-scraper/src/main.py
                # for the same fix applied at the call-site level) so a
                # transient proxy/network hiccup retries instead of crashing
                # the whole item.
                last_exc = e
                await self._sleep(attempt)
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    @staticmethod
    async def _sleep(attempt: int):
        await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))

    async def close(self):
        await self.session.close()
