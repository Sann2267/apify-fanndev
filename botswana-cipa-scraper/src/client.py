"""HTTP client for CIPA's "Search the Register" (Verne/Foster Moore) flow.

No WAF, no CAPTCHA, no TLS-fingerprint gate observed anywhere on
`cipa.co.bw` during recon -- plain `nginx`, no `cf-ray`/challenge markers on
any of ~20 requests tried. `curl_cffi` `chrome124` is used anyway for
portfolio-wide consistency and because it costs nothing; a plain
`requests`/`httpx` baseline was not separately re-verified to also work
(recon started directly with `curl_cffi`, per this project's default stack),
so the profile choice here is "known-good", not "proven necessary".

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix as `guardian-nigeria-scraper/src/client.py`: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures (proxy CONNECT tunnel
failures, DNS hiccups) and lets them crash the whole run instead of
retrying/degrading to a per-item error record.
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, SEARCH_START_URL, TLS_PROFILE
from src.extractor import (
    extract_entity_detail,
    extract_search_results,
    find_button_by_label,
    find_by_attribute,
    parse_delta_state,
    parse_view_tree_from_html,
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
    """Holds the per-transaction state needed to drive one `NameOrNumber`
    search + click-through to `entityView` inside one guest Verne session
    (cookie `x-catalyst-registry-session`)."""

    def __init__(self, post_url: str, name_field_id: str, search_button_id: str, entity_type_field_id: str | None):
        self.post_url = post_url
        self.name_field_id = name_field_id
        self.search_button_id = search_button_id
        self.entity_type_field_id = entity_type_field_id


class CIPAClient:
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

    async def get(self, url: str, **kwargs):
        return await self._with_retry("GET", url, **kwargs)

    async def _post_commands(self, post_url: str, commands: list[dict]) -> dict:
        """POST a delta-mode command batch and return the parsed node map.
        `returnRootHtmlOnChange: False, returnChangesOnly: True` matches the
        page's own `Catalyst.returnRootHtmlOnChange`/`Catalyst.delta` config
        -- see constants.py's recon summary for why the opposite silently
        returns an empty-but-200 response.
        """
        payload = {"returnRootHtmlOnChange": False, "returnChangesOnly": True, "commands": commands}
        r = await self._with_retry("POST", post_url, json=payload, headers={"Content-Type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"POST {post_url} -> HTTP {r.status_code}")
        return parse_delta_state(r.text)

    async def start_search(self) -> SearchSession:
        r = await self.get(SEARCH_START_URL, allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_START_URL} -> HTTP {r.status_code}")
        txn = r.url.rstrip("/").rsplit("/master/ui/", 1)[-1]
        post_url = f"https://www.cipa.co.bw/master/ui/{txn}"
        view_tree = parse_view_tree_from_html(r.text)
        name_field_id = find_by_attribute(view_tree, "NameOrNumber")
        search_button_id = find_button_by_label(view_tree, "Search")
        entity_type_field_id = find_by_attribute(view_tree, "EntityType")
        if not name_field_id or not search_button_id:
            raise RuntimeError("Could not locate NameOrNumber field / Search button in search page view tree")
        return SearchSession(post_url, name_field_id, search_button_id, entity_type_field_id)

    async def search(self, session: SearchSession, query: str, entity_type: str | None = None) -> list[dict]:
        commands = []
        if entity_type and entity_type != "any" and session.entity_type_field_id:
            commands.append(
                {"type": "view-node-set-attribute-value", "id": session.entity_type_field_id, "value": entity_type}
            )
        commands.append({"type": "view-node-set-attribute-value", "id": session.name_field_id, "value": query})
        commands.append({"type": "view-node-button-click", "id": session.search_button_id})
        node_map = await self._post_commands(session.post_url, commands)
        return extract_search_results(node_map)

    async def open_entity(self, session: SearchSession, node_id: str) -> str:
        """Click a search result's hyperlink node; returns the `entityView`
        permalink URL from the `<redirect>` response."""
        payload = {
            "returnRootHtmlOnChange": False,
            "returnChangesOnly": True,
            "commands": [{"type": "view-node-button-click", "id": node_id}],
        }
        r = await self._with_retry(
            "POST", session.post_url, json=payload, headers={"Content-Type": "application/json"}
        )
        if r.status_code != 200:
            raise RuntimeError(f"POST {session.post_url} -> HTTP {r.status_code}")
        m = re.search(r"<redirect>([^<]+)</redirect>", r.text)
        if not m:
            raise RuntimeError(f"No <redirect> in click response: {r.text[:300]!r}")
        return m.group(1)

    async def fetch_entity_detail(self, entity_view_url: str) -> dict:
        """`entityView` permalinks were confirmed to load with a completely
        fresh session (no cookies) -- no session affinity needed with the
        search step, so this can be called concurrently across queries."""
        r = await self.get(entity_view_url, allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"GET {entity_view_url} -> HTTP {r.status_code}")
        view_tree = parse_view_tree_from_html(r.text)
        return extract_entity_detail(view_tree)

    async def close(self):
        await self.session.close()
