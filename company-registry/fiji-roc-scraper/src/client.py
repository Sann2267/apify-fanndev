"""HTTP client for Fiji ROC's public "Buy Information" search
(`roc.digital.gov.fj/BuyInformation/Search`).

No CAPTCHA and no WAF challenge observed anywhere in this flow during recon
(Cloudflare fronts the domain but never issued a challenge across ~40
requests). `curl_cffi` `chrome124` is used for portfolio-wide consistency,
not because a plain baseline was seen to fail.

The retry loop wraps ALL request calls in a broad `except Exception`, same
pattern as `botswana-cipa-scraper/src/client.py`: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures.
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    AJAX_HEADERS,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SEARCH_PAGE_URL,
    SEARCH_RESULTS_URL,
    SEARCH_TOKEN_RE_TEMPLATE,
    TLS_PROFILE,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
]

_TOKEN_RE = re.compile(SEARCH_TOKEN_RE_TEMPLATE)


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class LoginRequired(Exception):
    """The public search page itself redirected to the ROC Pass OIDC login
    (auth.digital.gov.fj) instead of rendering the search form -- the
    currently-open no-login search path documented in constants.py has
    apparently been closed off. Investigate before retrying blindly."""


class FijiROCClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def start_session(self) -> str:
        """GET the search page to establish cookies + a fresh antiforgery
        token. Raises LoginRequired if the site redirected us to the OIDC
        login instead (the public path documented in constants.py closed)."""
        r = await self._with_retry("GET", SEARCH_PAGE_URL, allow_redirects=True)
        if "auth.digital.gov.fj" in str(r.url):
            raise LoginRequired(f"GET {SEARCH_PAGE_URL} redirected to login: {r.url}")
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_PAGE_URL} -> HTTP {r.status_code}")
        m = _TOKEN_RE.search(r.text)
        if not m:
            raise RuntimeError("Could not find __RequestVerificationToken on BuyInformation/Search page")
        return m.group(1)

    async def search(self, token: str, search_number: str = "", search_name: str = "") -> int:
        """POST the search form. Returns the upstream match count (a bare
        integer in the response body)."""
        data = {
            "SearchNumber": search_number,
            "SearchName": search_name,
            "__RequestVerificationToken": token,
        }
        r = await self._with_retry("POST", SEARCH_PAGE_URL, data=data, headers=AJAX_HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"POST {SEARCH_PAGE_URL} -> HTTP {r.status_code}")
        try:
            return int(r.text.strip())
        except ValueError as e:
            raise RuntimeError(f"Unexpected non-integer search count response: {r.text[:200]!r}") from e

    async def get_results_page(self, skip: int, take: int) -> dict:
        """GET one page of the Kendo grid results. Same session/cookies as
        the preceding search() call are required (server-side result set is
        session-scoped, not encoded in the query string)."""
        params = {"take": take, "skip": skip, "page": (skip // take) + 1, "pageSize": take}
        r = await self._with_retry("GET", SEARCH_RESULTS_URL, params=params, headers=AJAX_HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_RESULTS_URL} -> HTTP {r.status_code}")
        try:
            return r.json()
        except Exception as e:  # noqa: BLE001 -- surfaces as a clear diagnostic below
            raise RuntimeError(f"Non-JSON response from GetSearchResults: {r.text[:200]!r}") from e

    async def close(self):
        await self.session.close()
