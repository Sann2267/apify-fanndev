"""HTTP client wrapper for ctb.gov.vu.

Each listing page is a plain GET with a Joomla `?start=N` offset -- no
session/CSRF handshake. See constants.py for the full recon summary,
including why TLS certificate verification is disabled for this host
specifically (an incomplete cert chain on the server's own side, not a WAF
signal).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


async def _request(session: AsyncSession, url: str, params: dict) -> str:
    r = await session.get(url, headers=HEADERS, params=params, timeout=60)
    if r.status_code != 200:
        raise FetchFailed(f"GET {url} params={params} returned {r.status_code}")
    return r.text


async def fetch_page(url: str, start: int, proxy_url: str | None = None) -> str:
    """Runs a single GET with retries. Returns the response body."""
    params = {"start": start} if start else {}
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
            verify=False,  # ctb.gov.vu serves an incomplete cert chain -- see constants.py
        )
        try:
            return await _request(session, url, params)
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per the portfolio-wide Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for GET {url!r} start={start}: {last_exc!r}")
