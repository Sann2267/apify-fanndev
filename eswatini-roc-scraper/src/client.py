"""HTTP client for Eswatini's public "Company Name Search"
(`online.gov.sz/e-companysearch.aspx`).

No WAF, no CAPTCHA, no TLS-fingerprint gate observed during recon -- plain
`nginx` fronting an ASP.NET 4.0 app. `curl_cffi` `chrome124` is used anyway
for portfolio-wide consistency; a plain `requests`/`httpx` baseline was not
separately re-verified to also work (recon started directly with
`curl_cffi`, per this project's default stack).

This is a classic ASP.NET WebForms postback flow, NOT a REST/JSON API:
1. `GET` the search page to obtain the session cookie (`ASP.NET_SessionId`)
   and the three hidden postback tokens (`__VIEWSTATE`,
   `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`).
2. `POST` those same tokens back, plus the search term, on the SAME session
   (cookie-bearing client) -- ASP.NET's server-side `__EVENTVALIDATION`
   check is tied to the session that issued the GET.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as other actors in this portfolio: `curl_cffi`'s own exception hierarchy
(`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    SEARCH_URL,
    TLS_PROFILE,
)
from src.extractor import extract_postback_tokens, extract_search_results

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class EswatiniROCClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
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

    async def search(self, query: str) -> list[dict]:
        """Run one GET (fetch postback tokens) + POST (submit search) round
        trip on this client's own session, and return the parsed result
        rows. Raises `NoResultsFound` (from extractor) if the search
        legitimately matched nothing."""
        r = await self._with_retry("GET", SEARCH_URL)
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_URL} -> HTTP {r.status_code}")
        tokens = extract_postback_tokens(r.text)

        data = {
            **tokens,
            "ctl00$MainContent$txtreserve": query,
            "ctl00$MainContent$Button1": "search",
        }
        r2 = await self._with_retry("POST", SEARCH_URL, data=data)
        if r2.status_code != 200:
            raise RuntimeError(f"POST {SEARCH_URL} -> HTTP {r2.status_code}")
        return extract_search_results(r2.text)

    async def close(self):
        await self.session.close()
