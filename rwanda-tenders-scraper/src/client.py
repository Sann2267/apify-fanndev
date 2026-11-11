"""HTTP client for UMUCYO (www.umucyo.gov.rw), Rwanda's official e-GP portal.

No TLS-fingerprint gate and no WAF was found on this target during recon
(see `constants.py`) -- `curl_cffi` is still used for portfolio consistency
and because it copes gracefully with a residential proxy in front of it,
but plain `requests`/`httpx` would also work here.

Session handling: a single `curl_cffi.AsyncSession` carries the `JSESSIONID`
cookie set on the first GET across every subsequent listing/detail POST.
The site's own HTML embeds a classic `;jsessionid=<id>` URL-rewriting
suffix in its `<form action=...>` markup, but recon confirmed this is
*not* required -- the cookie alone is sufficient (verified with a fresh
cookie jar carrying no jsessionid in any URL at all).

The retry loop wraps request calls in a broad exception list, same pattern
as every other actor in this portfolio: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    DETAIL_PATH,
    EMPTY_FILTERS,
    FORM_HEADERS,
    LIST_PAGE_SIZE,
    LIST_PATH,
    MAX_RETRIES,
    MENU_ID,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

log = logging.getLogger(__name__)


class UmucyoClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._primed = False

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (429, 502, 503, 504):
                    last_exc = RuntimeError(f"HTTP {r.status_code} transient response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except (RequestException, ConnectionError, OSError) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, plus OSError
                # (curl_cffi's CurlError base) to be safe.
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def _ensure_session(self):
        """Primes the JSESSIONID cookie by GETting the listing page once."""
        if self._primed:
            return
        r = await self._with_retry("GET", f"{BASE_URL}{LIST_PATH}", params={"menuId": MENU_ID})
        if r.status_code != 200:
            raise RuntimeError(f"GET {LIST_PATH} -> HTTP {r.status_code}")
        self._primed = True

    async def fetch_list_page(
        self,
        page_no: int,
        page_size: int = LIST_PAGE_SIZE,
        filters: dict | None = None,
    ) -> str:
        await self._ensure_session()
        data = {
            "currentPageNo": page_no,
            "searchConditions": "",
            **EMPTY_FILTERS,
            **(filters or {}),
            "recordCountPerPage": page_size,
        }
        r = await self._with_retry(
            "POST",
            f"{BASE_URL}{LIST_PATH}",
            params={"menuId": MENU_ID},
            data=data,
            headers=FORM_HEADERS,
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {LIST_PATH} page={page_no} -> HTTP {r.status_code}")
        return r.text

    async def fetch_detail(self, tend_refer_no: str, tend_stage_cd: str, tend_type_cd: str) -> str:
        await self._ensure_session()
        data = {
            "tendReferNo": tend_refer_no,
            "tendStageCd": tend_stage_cd,
            "tendTypeCd": tend_type_cd,
            "currentPageNo": 1,
            "searchConditions": "",
        }
        r = await self._with_retry(
            "POST",
            f"{BASE_URL}{DETAIL_PATH}",
            params={"menuId": MENU_ID},
            data=data,
            headers=FORM_HEADERS,
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {DETAIL_PATH} ref={tend_refer_no} -> HTTP {r.status_code}")
        return r.text

    async def close(self):
        await self.session.close()
