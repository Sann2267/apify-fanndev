"""HTTP client for the Solomon Islands Business Registry's "Entity Search"
Catalyst (Foster Moore) service. See `constants.py` for the full recon
summary and wire-protocol notes.

No WAF, no CAPTCHA, no TLS-fingerprint gate observed anywhere on
`solomonbusinessregistry.gov.sb` during recon. `curl_cffi` `chrome124` is
used anyway for portfolio-wide consistency.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as `botswana-cipa-scraper`/`guardian-nigeria-scraper`: `curl_cffi`'s own
exception hierarchy (`CurlError` -> `OSError`) does NOT inherit from
Python's builtin `ConnectionError`/`TimeoutError` despite sharing class
names, so a narrower except list silently misses real transient failures.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, SEARCH_START_TEMPLATE, TLS_PROFILE
from src.extractor import (
    NoResultsFound,
    PageState,
    extract_detail_tab,
    extract_form_fields,
    extract_search_results,
    find_button_node,
    find_tabs,
    parse_page_state,
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


class SearchSession:
    """Everything needed to drive one guest "Entity Search" -> click-through
    flow. `form_fields` carries forward the search form's own current hidden
    field values (see `extractor.extract_form_fields`)."""

    def __init__(self, state: PageState, search_node_id: str, search_container_id: str, form_fields: dict, register: str):
        self.state = state
        self.search_node_id = search_node_id
        self.search_container_id = search_container_id
        self.form_fields = form_fields
        self.register = register


class SBRClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._frag_id = 1

    def _next_frag_id(self) -> str:
        # Must look like a small integer -- see constants.py's recon note:
        # a non-numeric value silently breaks the fragment response AND
        # appears to corrupt the rest of the view-instance's session state.
        self._frag_id += 1
        return str(self._frag_id)

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

    async def get(self, url: str, **kwargs):
        return await self._with_retry("GET", url, **kwargs)

    async def start_search(self, register: str) -> SearchSession:
        url = SEARCH_START_TEMPLATE.format(register=register)
        r = await self.get(url, allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"GET {url} -> HTTP {r.status_code}")
        page_html = r.text
        state = parse_page_state(page_html)
        node_id, container_id = find_button_node(page_html, "Search")
        form_start = page_html.find("<form method='post' id=\"viewInstanceForm\"")
        form_end = page_html.find("</form>", form_start)
        form_fields = extract_form_fields(page_html[form_start:form_end]) if form_start != -1 else {}
        return SearchSession(state, node_id, container_id, form_fields, register)

    def _headers(self, session_global: str, async_request: bool) -> dict:
        headers = {
            "x-security-token": "null",
            "x-catalyst-session-global": session_global,
            "x-catalyst-secured": "true",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        if async_request:
            headers["x-catalyst-async"] = "true"
        return headers

    async def search(self, session: SearchSession, query: str) -> list[dict]:
        data = dict(session.form_fields)
        data["QueryString"] = query
        data["SourceAppCode"] = session.register
        data.update(
            {
                "_CBASYNCUPDATE_": "true",
                "_CBHTMLFRAGNODEID_": session.search_container_id,
                "_CBHTMLFRAGID_": self._next_frag_id(),
                "_CBHTMLFRAG_": "true",
                "_CBNODE_": session.search_node_id,
                "_CBNAME_": "buttonPush",
                "_VIKEY_": session.state.vikey,
            }
        )
        headers = self._headers(session.state.session_global, async_request=True)
        r = await self._with_retry("POST", session.state.action_url, data=data, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"POST {session.state.action_url} -> HTTP {r.status_code}")
        return extract_search_results(r.text)  # raises NoResultsFound if empty

    async def open_entity(self, session: SearchSession, query: str, node_id: str) -> tuple[str, PageState, str]:
        """Click a search result's link (a FULL form submit, not a fragment
        request -- matches the real page's `catCallback`). Returns
        `(entity_view_url, detail_page_state, detail_page_html)`."""
        data = dict(session.form_fields)
        data["QueryString"] = query
        data["SourceAppCode"] = session.register
        data.update({"_CBNODE_": node_id, "_CBNAME_": "invokeMenuCb", "_VIKEY_": session.state.vikey})
        headers = self._headers(session.state.session_global, async_request=False)
        r = await self._with_retry(
            "POST", session.state.action_url, data=data, headers=headers, allow_redirects=True
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {session.state.action_url} (invokeMenuCb) -> HTTP {r.status_code}")
        detail_html = r.text
        detail_state = parse_page_state(detail_html)
        return str(r.url), detail_state, detail_html

    async def fetch_entity_detail(self, detail_state: PageState, detail_html: str) -> dict:
        """Merge the pre-rendered "General Details" tab (tab 0, already in
        `detail_html`) with one fragment fetch per remaining tab (Addresses,
        Directors, Shares & Shareholders, Filings, ... -- whatever tabs this
        entity/register actually has)."""
        tabs = find_tabs(detail_html)
        if not tabs:
            raise RuntimeError("No tabs found on entity detail page -- page shape may have changed")
        detail: dict = {}
        for tab in tabs:
            if tab["index"] == 0:
                fields = extract_detail_tab(detail_html, scope_selector='div.appTabSelected[role="tabpanel"]')
            else:
                data = {
                    "_CBASYNCUPDATE_": "true",
                    "_CBHTMLFRAGNODEID_": tab["container"],
                    "_CBHTMLFRAGID_": self._next_frag_id(),
                    "_CBHTMLFRAG_": "true",
                    "_CBNODE_": tab["nodeId"],
                    "_CBNAME_": "tabSelect",
                    "_CBVALUE_": str(tab["index"]),
                    "_VIKEY_": detail_state.vikey,
                }
                headers = self._headers(detail_state.session_global, async_request=True)
                r = await self._with_retry("POST", detail_state.action_url, data=data, headers=headers)
                if r.status_code != 200:
                    raise RuntimeError(f"POST {detail_state.action_url} (tab {tab['label']!r}) -> HTTP {r.status_code}")
                fields = extract_detail_tab(r.text)
            for key, value in fields.items():
                if key in detail and isinstance(detail[key], list) and isinstance(value, list):
                    detail[key].extend(value)
                else:
                    detail[key] = value
            detail.setdefault("_tabs", []).append(tab["label"])
        return detail

    async def close(self):
        await self.session.close()
