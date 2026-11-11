"""HTTP client wrapper for ARMP's public listing and search endpoints.

No login, no CSRF handshake needed to read -- see constants.py for the full
recon summary. `avis` is a plain GET; `dossiers` and `contrats` are plain
form-encoded POSTs that any browser's own "Rechercher" button issues.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    CONTRATS_URL,
    CONTRATS_WILDCARD_FIELDS,
    DOSSIERS_URL,
    DOSSIERS_WILDCARD_FIELDS,
    HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A GET/POST never produced a usable 200 response after retries."""


async def _request(session: AsyncSession, method: str, url: str, **kwargs) -> str:
    r = await session.request(method, url, headers=HEADERS, timeout=120, **kwargs)
    if r.status_code != 200:
        raise FetchFailed(f"{method} {url} returned {r.status_code}")
    return r.text


async def _with_retries(method: str, url: str, proxy_url: str | None = None, **kwargs) -> str:
    """Runs a single GET/POST with retries. Returns the raw response body."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=120,
        )
        try:
            return await _request(session, method, url, **kwargs)
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
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {method} {url!r}: {last_exc!r}")


async def fetch_avis_page(proxy_url: str | None = None) -> str:
    from src.constants import AVIS_URL

    return await _with_retries("GET", AVIS_URL, proxy_url=proxy_url)


async def fetch_dossiers_page(year: str, proxy_url: str | None = None) -> str:
    data = {"annee_dos": year, **DOSSIERS_WILDCARD_FIELDS}
    return await _with_retries("POST", DOSSIERS_URL, proxy_url=proxy_url, data=data)


async def fetch_contrats_json(year: str, proxy_url: str | None = None) -> str:
    data = {"ANNEE": year, **CONTRATS_WILDCARD_FIELDS}
    return await _with_retries("POST", CONTRATS_URL, proxy_url=proxy_url, data=data)
