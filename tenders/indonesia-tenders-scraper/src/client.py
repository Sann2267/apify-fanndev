"""HTTP client wrapper for LKPP's SPSE Nasional public tender search.

Two things about this target are not what they look like at first glance
(both documented in full in CRAWLING_METHOD.md):

1. **Session-stateful.** The search page (`GET /nasional/lelang`) issues an
   `SPSE_SESSION` cookie whose value embeds the very `authenticityToken`
   ("___AT=<token>") that the listing AJAX endpoint (`POST
   /nasional/dt/lelang`) also expects as a form field -- the two must come
   from the *same* client, so a single `curl_cffi.AsyncSession` (cookie jar
   + TLS connection) is created once per run and reused across every
   list-page and detail-page request, rather than opening a fresh session
   per request.

2. **Filtering happens via the search page's own query string, not the
   DataTables "search box".** The DataTable's client-side search input
   (`search[value]` in the POST body) is silently ignored server-side --
   confirmed by sending a nonsense value and getting byte-identical
   results back. The *real* filters (fiscal year, category, procuring
   agency, winning-contractor name) are read from `GET /nasional/lelang`'s
   own query string and get baked into the AJAX URL that page then renders
   inline (`ajax: {url: "/nasional/dt/lelang?tahun=2026&kategoriId=7..."}`
   in its own `<script>` block). So this client always does a filtered GET
   of the search page *first* to discover the correct AJAX URL for that
   filter combination, then POSTs pagination requests against it.
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    AJAX_HEADERS,
    DETAIL_ENDPOINT_TEMPLATE,
    HEADERS,
    LIST_ENDPOINT,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    ROOT,
    SEARCH_PAGE,
    TLS_PROFILE,
)

TOKEN_RE = re.compile(r"authenticityToken\s*=\s*'([a-f0-9]+)'")
AJAX_URL_RE = re.compile(r"""url\s*:\s*["']([^"']+)["']""")


class FetchFailed(Exception):
    """A request never produced a usable response after retries."""


class RecordNotFound(Exception):
    """A detail GET for a specific tender code came back genuinely empty --
    no such record (distinct from a transient/blocked failure)."""


class SpseSession:
    """One (cookie jar, authenticityToken, filtered-ajax-URL) triple,
    refreshed on demand."""

    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url
        self.session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.token: str | None = None
        self.ajax_path: str = LIST_ENDPOINT  # overwritten by warm_up() once filters are known
        self._filters: dict = {}

    async def close(self):
        await self.session.close()

    async def warm_up(
        self, tahun: int | None = None, kategori_id: str = "", instansi_id: str = "", rekanan: str = ""
    ):
        """(Re-)fetches the search page with the given filters applied,
        capturing both a fresh session cookie + authenticityToken and the
        AJAX URL the site itself computed for this exact filter combo."""
        params = {}
        if tahun:
            params["tahun"] = tahun
        if kategori_id:
            params["kategoriId"] = kategori_id
        if instansi_id:
            params["instansiId"] = instansi_id
        if rekanan:
            params["rekanan"] = rekanan
        self._filters = params

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.get(SEARCH_PAGE, params=params, headers=HEADERS)
                if r.status_code != 200 or not r.content:
                    raise FetchFailed(f"GET {SEARCH_PAGE} params={params} returned {r.status_code}")
                token_m = TOKEN_RE.search(r.text)
                ajax_m = AJAX_URL_RE.search(r.text)
                if not token_m or not ajax_m:
                    raise FetchFailed(
                        f"GET {SEARCH_PAGE} params={params} returned 200 but no authenticityToken/ajax "
                        "URL was found in it -- upstream page shape has likely changed"
                    )
                self.token = token_m.group(1)
                self.ajax_path = ajax_m.group(1)
                return
            except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
                # NOTE: curl_cffi's own RequestException/ConnectionError does not
                # inherit from Python's builtin ConnectionError -- its MRO is
                # RequestException -> CurlError -> OSError, a parallel hierarchy.
                # Both are caught explicitly, per the portfolio-wide Babak 22b fix.
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts warming up SPSE session: {last_exc!r}")

    async def ensure_token(self):
        if self.token is None:
            await self.warm_up()

    async def fetch_list_page(self, start: int, length: int) -> dict:
        """One page of the national "Cari Paket" listing for whichever
        filters the last warm_up() call applied, newest first by the
        site's own default ordering."""
        await self.ensure_token()
        url = f"{ROOT}{self.ajax_path}"
        data = {"draw": 1, "start": start, "length": length, "authenticityToken": self.token}

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.post(url, data=data, headers=AJAX_HEADERS)
                if r.status_code == 403:
                    # A stale/expired token or session cookie -- refresh both
                    # (same filters) and retry once rather than treating it as
                    # a hard block.
                    await self.warm_up(**self._filters_kwargs())
                    url = f"{ROOT}{self.ajax_path}"
                    data["authenticityToken"] = self.token
                    r = await self.session.post(url, data=data, headers=AJAX_HEADERS)
                if r.status_code != 200 or not r.content:
                    raise FetchFailed(f"POST {url} start={start} returned {r.status_code} ({len(r.content)} bytes)")
                try:
                    return r.json()
                except ValueError as e:
                    raise FetchFailed(f"POST {url} start={start} returned non-JSON body: {e!r}") from e
            except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r} start={start}: {last_exc!r}")

    def _filters_kwargs(self) -> dict:
        return {
            "tahun": self._filters.get("tahun"),
            "kategori_id": self._filters.get("kategoriId", ""),
            "instansi_id": self._filters.get("instansiId", ""),
            "rekanan": self._filters.get("rekanan", ""),
        }

    async def fetch_detail(self, kode: str) -> str:
        """The public announcement ("Pengumuman") page for one tender code.
        Requires a same-origin Referer -- the app's own router (not a WAF)
        rejects a direct hit with no Referer as "Akses Ditolak" (Access
        Denied). Raises RecordNotFound for a code with no such tender."""
        await self.ensure_token()
        url = DETAIL_ENDPOINT_TEMPLATE.format(kode=kode)
        headers = {**HEADERS, "Referer": SEARCH_PAGE}

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.get(url, headers=headers)
                if r.status_code == 404:
                    raise RecordNotFound(kode)
                if r.status_code != 200 or not r.content:
                    raise FetchFailed(f"GET {url} returned {r.status_code} ({len(r.content)} bytes)")
                if "Akses Ditolak" in r.text or "Terjadi Kesalahan" in r.text:
                    raise RecordNotFound(kode)
                return r.text
            except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r}: {last_exc!r}")
