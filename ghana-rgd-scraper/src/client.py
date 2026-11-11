"""HTTP client wrapper for ORC's Name Search app.

Each search is a fresh GET (mint session + CSRF token) immediately followed
by a POST (spend that token) -- see constants.py for why the token must be
this fresh. The whole GET+POST pair is retried together on failure (a stale
token manifests as a 403 or a bare 302-to-home, and a brand-new session
self-heals it -- there is no point retrying just the POST with the same
now-burned token).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    APP_BASE,
    GET_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SEARCH_HEADERS_EXTRA,
    SEARCH_URL,
    TLS_PROFILE,
    WARMUP_URL,
)


class SearchFailed(Exception):
    """The GET+POST pair never produced a usable results fragment."""


async def _one_attempt(bizname: str, search_type: str, proxy_url: str | None) -> str:
    session = AsyncSession(
        impersonate=TLS_PROFILE,
        proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
        timeout=60,
    )
    try:
        r = await session.get(WARMUP_URL, headers=GET_HEADERS)
        if r.status_code != 200:
            raise SearchFailed(f"warmup GET returned {r.status_code}")

        csrf_start = r.text.find('name="_csrf"')
        if csrf_start == -1:
            raise SearchFailed("no _csrf hidden field found on warmup page -- page shape has likely changed")
        value_start = r.text.find('value="', csrf_start) + len('value="')
        value_end = r.text.find('"', value_start)
        csrf = r.text[value_start:value_end]
        if not csrf:
            raise SearchFailed("_csrf field was empty -- page shape has likely changed")

        headers = {
            **SEARCH_HEADERS_EXTRA,
            "HX-Current-URL": WARMUP_URL,
            "Origin": APP_BASE.rsplit("/orc-app", 1)[0],
            "Referer": WARMUP_URL,
        }
        data = {"_csrf": csrf, "bizName": bizname, "searchType": search_type}
        r2 = await session.post(SEARCH_URL, data=data, headers=headers)

        if r2.status_code != 200:
            raise SearchFailed(f"search POST returned {r2.status_code} (likely a burned/stale CSRF token)")
        if "hx-trigger" not in {k.lower() for k in r2.headers.keys()}:
            # A 200 without the namesFound trigger header is the site's own
            # signal that the request wasn't recognized as a real search
            # (falls back to re-rendering the bare form) -- treat as a
            # retryable failure, not a valid "zero results" response.
            raise SearchFailed("response missing hx-trigger header -- request likely fell back to full-page render")
        return r2.text
    finally:
        await session.close()


async def search(bizname: str, search_type: str, proxy_url: str | None = None) -> str:
    """Runs the GET+POST pair with retries. Returns the raw HTML results fragment."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await _one_attempt(bizname, search_type, proxy_url)
        except (SearchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException (raised on a failed proxy
            # CONNECT tunnel, DNS failure, TLS handshake error, etc.) does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per guardian-nigeria-scraper's
            # documented fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
    raise SearchFailed(f"Exhausted {MAX_RETRIES} attempts for bizName={bizname!r}: {last_exc!r}")
