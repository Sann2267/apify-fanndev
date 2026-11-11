"""HTTP client for www.eprocure.gov.bd (Bangladesh's national e-GP portal).

Fully stateless -- no cookies, no session priming, no TLS gotcha needed
(see constants.py for the full recon writeup). Every call is a plain
POST/GET with `curl_cffi`'s `chrome124` impersonation, used for
portfolio-wide consistency even though recon showed plain `curl` works
identically here.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    AWARDED_DETAIL_URL,
    AWARDED_SEARCH_URL,
    DEFAULT_HEADERS,
    DETAIL_URL,
    LIST_SEARCH_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A request never produced a usable 200 response after retries."""


class EprocureClient:
    def __init__(self, proxy_url: str | None = None):
        self.session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code != 200:
                    raise FetchFailed(f"{method} {url} -> HTTP {r.status_code}: {r.text[:300]!r}")
                return r
            except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
                # NOTE: curl_cffi's own ConnectionError/RequestException does
                # NOT inherit from Python's builtin ConnectionError -- its MRO
                # is RequestException -> CurlError -> OSError, a parallel
                # hierarchy. Both listed, per this project's portfolio-wide
                # Babak 22b fix.
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {method} {url!r}: {last_exc!r}")

    async def fetch_list(self, keyword: str, proc_nature: str, page_no: int, size: int) -> str:
        """Live/open tenders via TenderDetailsServlet -- see constants.py for
        why every one of these fields must be present even when blank."""
        data = {
            "funName": "AllTenders",
            "viewType": "Live",
            "departmentId": "",
            "office": "",
            "procNature": proc_nature,
            "procType": "",
            "procMethod": "0",
            "tenderId": "",
            "refNo": "",
            "pubDtFrm": "",
            "pubDtTo": "",
            "closeDtFrm": "",
            "closeDtTo": "",
            "cpvCategory": "",
            "isFrame": "0",
            "pageNo": str(page_no),
            "size": str(size),
            "h": "t",
            "keyword": keyword,
        }
        r = await self._with_retry("POST", LIST_SEARCH_URL, data=data)
        return r.text

    async def fetch_awarded(self, keyword: str, page_no: int, size: int) -> str:
        """Awarded contracts (Notice of Award) via SearchNoaServlet."""
        data = {"keyword": keyword, "pageNo": str(page_no), "size": str(size)}
        r = await self._with_retry("POST", AWARDED_SEARCH_URL, data=data)
        return r.text

    async def fetch_detail(self, tender_id: str) -> str:
        r = await self._with_retry("GET", DETAIL_URL, params={"id": tender_id, "h": "t"})
        return r.text

    async def fetch_awarded_detail(self, tender_id: str, pkg_lot_id: str) -> str:
        r = await self._with_retry("GET", AWARDED_DETAIL_URL, params={"tenderid": tender_id, "pkgLotId": pkg_lot_id})
        return r.text

    async def close(self):
        await self.session.close()
