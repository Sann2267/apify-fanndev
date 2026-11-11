"""HTTP client for CAIPO's `searchDbApi` JSON endpoint.

No WAF, no CAPTCHA, no TLS-fingerprint gate observed anywhere on
`caipo.gov.bb` during recon -- a bare `curl` (zero impersonation) got a
clean `200` JSON response on the first try. `curl_cffi` is used anyway for
portfolio-wide consistency and because it costs nothing.

The retry loop wraps ALL request calls in a broad `except Exception`, same
pattern as `botswana-cipa-scraper/src/client.py`: `curl_cffi`'s own
exception hierarchy (`CurlError` -> `OSError`) does NOT inherit from
Python's builtin `ConnectionError`/`TimeoutError` despite sharing class
names, so a narrower except list silently misses real transient failures.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import AUTOCOMPLETE_URL, DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, SEARCH_URL, TLS_PROFILE
from src.extractor import SearchApiError, parse_search_response

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


class CAIPOClient:
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

    async def search(
        self,
        name: str | None = None,
        name_condition: str = "Contains",
        number: str | None = None,
        number_condition: str = "Contains",
        category: str | None = None,
    ) -> tuple[list[dict], int, bool]:
        form: dict[str, str] = {}
        if name:
            form["name_search_con"] = name_condition
            form["name_search_param"] = name
        if number:
            form["number_search_con"] = number_condition
            form["number_search_param"] = number
        if category:
            form["category_search_con"] = "Equals"
            form["category_search_param"] = category
        if not form:
            raise SearchApiError("At least one of name/number/category must be supplied")

        r = await self._with_retry("POST", SEARCH_URL, data=form)
        if r.status_code != 200:
            raise RuntimeError(f"POST {SEARCH_URL} -> HTTP {r.status_code}")
        payload = r.json()
        return parse_search_response(payload)

    async def autocomplete(self, term: str) -> list[dict]:
        """Not used in the main search flow -- kept for completeness/testing
        since it was reverse-engineered alongside `searchDbApi`."""
        r = await self._with_retry("POST", AUTOCOMPLETE_URL, data={"term": term, "type": "name"})
        if r.status_code != 200:
            raise RuntimeError(f"POST {AUTOCOMPLETE_URL} -> HTTP {r.status_code}")
        return r.json()

    async def close(self):
        await self.session.close()
