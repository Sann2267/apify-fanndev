"""HTTP client for Samoa Business Registries' "Company Search" flow.

No WAF, no CAPTCHA, no TLS-fingerprint gate observed anywhere on
`www.businessregistries.gov.ws` during recon -- plain `nginx`, no `cf-ray`/
challenge markers, and a bare `curl` baseline (no impersonation at all)
worked for every request tried. `curl_cffi` `chrome124` is used anyway for
portfolio-wide consistency and because it costs nothing.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as `botswana-cipa-scraper/src/client.py`: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures and lets them crash the
whole run instead of retrying/degrading to a per-item error record.

See `constants.py` for the recon summary and `extractor.py` for the wire
format. Short version of the protocol (full detail in CRAWLING_METHOD.md):
this is a per-session "view instance" state machine, NOT a REST API. Every
interactive element (search button, pagination link, detail-view link, tab
switch) has a server-generated node id that is DIFFERENT on every fresh
session -- there is no stable "the search button is always W870" shortcut.
Every step re-parses the current page/fragment for the node ids it needs
next.
"""

import asyncio
import re
import time

from curl_cffi.requests import AsyncSession

from src.constants import (
    AJAX_HEADERS,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SEARCH_START_URL,
    TLS_PROFILE,
)
from src.extractor import (
    UnexpectedShape,
    extract_filings,
    extract_general_details,
    extract_search_results,
    extract_tab_records,
    find_pager_node_id,
    unwrap_fragment,
)

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


_ACTION_RE = re.compile(r'action="(https://[^"]*update\.html[^"]*)"')
_VIKEY_RE = re.compile(r"viewInstanceKey:'([^']*)'")
_SESSTOKEN_RE = re.compile(r"x-catalyst-session-global':'([^']*)'")
_ADV_FIELD_RE = re.compile(r'name="(node\w+-Advanced)"')
_CONTAINER_RE = re.compile(r'id="AsyncWrapper(W\d+)"')
_SEARCH_BTN_RE = re.compile(r'class="[^"]*\bappSearchButton\b[^"]*"[^>]*\sid="node(W\d+)"')
_TAB_NODE_RE = re.compile(r'id="tabul(W\d+)"')


class SearchSession:
    """Per-transaction state for one guest "Company Search" view instance."""

    def __init__(self, action_url: str, vikey: str, sesstoken: str, adv_field: str, container: str, search_btn: str):
        self.action_url = action_url
        self.vikey = vikey
        self.sesstoken = sesstoken
        self.adv_field = adv_field
        self.container = container
        self.search_btn = search_btn
        self.pager_node: str | None = None
        self.last_query: str = ""


class DetailSession:
    """Per-transaction state for one company's "View ... Company Details"
    view instance (separate from the search session that led to it)."""

    def __init__(self, action_url: str, vikey: str, tab_node: str):
        self.action_url = action_url
        self.vikey = vikey
        self.tab_node = tab_node


class SamoaBRClient:
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

    async def start_search(self) -> SearchSession:
        r = await self._with_retry("GET", SEARCH_START_URL, allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_START_URL} -> HTTP {r.status_code}")
        page = r.text
        action_m = _ACTION_RE.search(page)
        vikey_m = _VIKEY_RE.search(page)
        sesstoken_m = _SESSTOKEN_RE.search(page)
        adv_m = _ADV_FIELD_RE.search(page)
        container_m = _CONTAINER_RE.search(page)
        btn_m = _SEARCH_BTN_RE.search(page)
        if not all([action_m, vikey_m, sesstoken_m, adv_m, container_m, btn_m]):
            raise UnexpectedShape("could not locate one or more required fields on the search start page")
        return SearchSession(
            action_url=action_m.group(1),
            vikey=vikey_m.group(1),
            sesstoken=sesstoken_m.group(1),
            adv_field=adv_m.group(1),
            container=container_m.group(1),
            search_btn=btn_m.group(1),
        )

    def _ajax_headers(self, session: SearchSession) -> dict:
        return {**AJAX_HEADERS, "x-catalyst-session-global": session.sesstoken}

    async def search(self, session: SearchSession, query: str) -> list[dict]:
        """Runs the search (page 1). Raises `NoResultsFound` (propagated from
        `extract_search_results`) on a genuine zero-match query."""
        session.last_query = query
        frag_id = str(int(time.time() * 1000))
        data = {
            "QueryString": query,
            session.adv_field: "N",
            "viewInstanceNamespace": "",
            "_CBASYNCUPDATE_": "true",
            "_CBHTMLFRAGNODEID_": session.container,
            "_CBHTMLFRAGID_": frag_id,
            "_CBHTMLFRAG_": "true",
            "_CBNODE_": session.search_btn,
            "_VIKEY_": session.vikey,
            "_CBNAME_": "buttonPush",
        }
        r = await self._with_retry("POST", session.action_url, data=data, headers=self._ajax_headers(session))
        if r.status_code != 200:
            raise RuntimeError(f"POST {session.action_url} (search) -> HTTP {r.status_code}")
        fragment = unwrap_fragment(r.text, frag_id)
        session.pager_node = find_pager_node_id(fragment)
        return extract_search_results(fragment)

    async def next_page(self, session: SearchSession, page_num: int) -> list[dict]:
        """Fetches page `page_num` (2, 3, ...) of the CURRENT search. Must be
        called only after a successful `search()` (needs `session.pager_node`,
        only present once results exist)."""
        if not session.pager_node:
            return []
        frag_id = str(int(time.time() * 1000) + page_num)
        data = {
            "QueryString": session.last_query,
            session.adv_field: "N",
            "viewInstanceNamespace": "",
            "_CBASYNCUPDATE_": "true",
            "_CBHTMLFRAGNODEID_": session.container,
            "_CBHTMLFRAGID_": frag_id,
            "_CBHTMLFRAG_": "true",
            "_CBNODE_": session.pager_node,
            "_VIKEY_": session.vikey,
            "_CBNAME_": "selectPage",
            "_CBVALUE_": str(page_num),
        }
        r = await self._with_retry("POST", session.action_url, data=data, headers=self._ajax_headers(session))
        if r.status_code != 200:
            raise RuntimeError(f"POST {session.action_url} (page {page_num}) -> HTTP {r.status_code}")
        fragment = unwrap_fragment(r.text, frag_id)
        return extract_search_results(fragment)

    async def open_detail(self, session: SearchSession, row: dict) -> tuple[DetailSession, dict]:
        """Clicks a search result's hyperlink (a FULL, non-fragment form
        submit in the real site -- `catCallback`, not
        `catHtmlFragmentCallback`) and follows the redirect chain to the
        company's detail page. Returns the new `DetailSession` plus the
        General-Details tab fields (already embedded in that page)."""
        data = {
            "QueryString": session.last_query,
            session.adv_field: "N",
            "viewInstanceNamespace": "",
            "_CBNODE_": row["nodeId"],
            "_VIKEY_": session.vikey,
            "_CBNAME_": "invokeMenuCb",
        }
        r = await self._with_retry(
            "POST",
            session.action_url,
            data=data,
            headers={"x-catalyst-session-global": session.sesstoken},
            allow_redirects=True,
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {session.action_url} (open detail) -> HTTP {r.status_code}")
        page = r.text
        action_m = _ACTION_RE.search(page)
        vikey_m = _VIKEY_RE.search(page)
        tab_m = _TAB_NODE_RE.search(page)
        if not action_m or not vikey_m:
            raise UnexpectedShape("detail page missing form action/viewInstanceKey")
        detail_session = DetailSession(
            action_url=action_m.group(1),
            vikey=vikey_m.group(1),
            tab_node=tab_m.group(1) if tab_m else "",
        )
        return detail_session, extract_general_details(page)

    async def fetch_tab(self, search_session: SearchSession, detail_session: DetailSession, tab_index: int) -> str:
        """POSTs a `tabSelect` fragment request for tab `tab_index` (1-5) on
        an already-open detail view instance. Returns the raw unwrapped
        fragment HTML -- caller picks `extract_tab_records` or
        `extract_filings` depending on which tab this is."""
        if not detail_session.tab_node:
            return ""
        frag_id = str(int(time.time() * 1000) + tab_index)
        data = {
            "viewInstanceNamespace": "",
            "_CBASYNCUPDATE_": "true",
            "_CBHTMLFRAGID_": frag_id,
            "_CBHTMLFRAG_": "true",
            "_CBNODE_": detail_session.tab_node,
            "_VIKEY_": detail_session.vikey,
            "_CBNAME_": "tabSelect",
            "_CBVALUE_": str(tab_index),
        }
        r = await self._with_retry(
            "POST", detail_session.action_url, data=data, headers=self._ajax_headers(search_session)
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {detail_session.action_url} (tab {tab_index}) -> HTTP {r.status_code}")
        return unwrap_fragment(r.text, frag_id)

    async def fetch_full_detail(self, search_session: SearchSession, row: dict) -> dict:
        """Opens a search result and pulls every tab into one merged dict:
        `generalDetails` fields at top level, plus `addresses`, `directors`,
        `shareholders`, `shareParcels` (lists of row dicts), and `filings`
        (list of {filingType, submittedAt, filedAt})."""
        detail_session, general = await self.open_detail(search_session, row)
        result = dict(general)
        if detail_session.tab_node:
            addr_html = await self.fetch_tab(search_session, detail_session, 1)
            dir_html = await self.fetch_tab(search_session, detail_session, 2)
            sh_html = await self.fetch_tab(search_session, detail_session, 3)
            sp_html = await self.fetch_tab(search_session, detail_session, 4)
            filings_html = await self.fetch_tab(search_session, detail_session, 5)
            result["addresses"] = extract_tab_records(addr_html)
            result["directors"] = extract_tab_records(dir_html)
            result["shareholders"] = extract_tab_records(sh_html)
            result["shareParcels"] = extract_tab_records(sp_html)
            result["filings"] = extract_filings(filings_html)
        return result

    async def close(self):
        await self.session.close()
