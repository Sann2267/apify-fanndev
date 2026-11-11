"""HTTP client wrapper for treasury.gov.lk.

No login, no CSRF handshake needed to read -- every URL here is a plain GET
returning a fully server-rendered Next.js page (see CRAWLING_METHOD.md). The
site sits behind Sucuri/Cloudproxy, which was observed to occasionally answer
the very first request in a session with an HTTP 307 self-redirect (no
Location header change, no cookie challenge body) before settling into 200s
-- `allow_redirects=True` (curl_cffi's default) handles this transparently,
same as a browser would.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FetchFailed(Exception):
    """A GET never produced a usable 200 response after retries."""


class NotFound(Exception):
    """A GET produced a definitive 404 -- used to detect end-of-archive."""


async def _get(session: AsyncSession, url: str) -> str:
    r = await session.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
    if r.status_code == 404:
        raise NotFound(url)
    if r.status_code != 200:
        raise FetchFailed(f"GET {url} returned {r.status_code}")
    return r.text


async def get_with_retries(url: str, proxy_url: str | None = None) -> str:
    """Runs a single GET with retries. Returns the raw HTML.

    A 404 is NOT retried -- it's raised immediately as NotFound since it's a
    meaningful, stable signal (end of archive), not a transient failure.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            return await _get(session, url)
        except NotFound:
            raise
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException (raised on a failed proxy
            # CONNECT tunnel, DNS failure, TLS handshake error, etc.) does NOT
            # inherit from Python's builtin ConnectionError -- its MRO is
            # RequestException -> CurlError -> OSError, a parallel hierarchy.
            # Both are caught explicitly per this portfolio's Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")


async def fetch_current_notices_page(proxy_url: str | None = None) -> str:
    from src.constants import CURRENT_NOTICES_URL

    return await get_with_retries(CURRENT_NOTICES_URL, proxy_url=proxy_url)


async def fetch_archive_page(page: int, proxy_url: str | None = None) -> str:
    from src.constants import ARCHIVE_URL_TMPL

    return await get_with_retries(ARCHIVE_URL_TMPL.format(page=page), proxy_url=proxy_url)
