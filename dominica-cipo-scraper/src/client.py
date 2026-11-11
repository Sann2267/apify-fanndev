"""HTTP client for CIPO's e-Filing/OCRS `loadInfoProc` JSON API.

No WAF, no CAPTCHA, no TLS-fingerprint gate observed anywhere on
`efiling.cipo.gov.dm` during recon -- `curl_cffi` impersonating chrome124,
chrome131, safari17_0, and edge101 all returned byte-identical 200 JSON
responses. `curl_cffi` is used anyway for portfolio-wide consistency.

The retry loop wraps request calls in a broad `except Exception`, same fix
as `guardian-nigeria-scraper/src/client.py` and every other actor's client
in this project: `curl_cffi`'s own exception hierarchy (`CurlError` ->
`OSError`) does NOT inherit from Python's builtin `ConnectionError`/
`TimeoutError` despite sharing class names, so a narrower except list
silently misses real transient failures and lets them crash the whole run
instead of retrying/degrading to a per-item error record.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import API_URL, DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, SEARCH_TYPE_KEYS, TLS_PROFILE
from src.extractor import NoResultsFound, parse_response, validate_query

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


class CIPOClient:
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

    async def _load_info_proc(self, input_str: str, proc_name: str) -> list[dict]:
        payload = {"input": input_str, "name": proc_name}
        r = await self._with_retry("POST", API_URL, json=payload)
        # NOTE: upstream returns its own "Divide by zero" error (see
        # constants.py) as HTTP 500 with a well-formed `{"message": ...}`
        # JSON body -- NOT HTTP 200 as initially assumed during recon (recon
        # used `curl -s` without `-D -` and missed the status line). So the
        # status code is deliberately NOT gated on here; both 200 (rows) and
        # 500 (message) bodies are parsed the same way via parse_response(),
        # which raises UpstreamError for the message case. Only a body that
        # isn't even JSON is treated as a hard transport failure.
        try:
            data = json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"POST {API_URL} ({proc_name}) -> HTTP {r.status_code}, non-JSON body: {r.text[:300]!r}") from e
        return parse_response(data)

    async def search(self, query: str, search_type: str) -> list[dict]:
        """Raises `InvalidQuery`, `UpstreamError`, or `NoResultsFound` --
        see extractor.py. `search_type` must be a key of SEARCH_TYPE_KEYS."""
        validate_query(query)
        key = SEARCH_TYPE_KEYS[search_type]
        rows = await self._load_info_proc(f"key={key},query={query}", "EntitySearch")
        if not rows:
            raise NoResultsFound()
        return rows

    async def entity_info(self, entity_id: str) -> dict:
        """Follow-up Directors/Secretaries/Schareholders(sic) lookup for one
        entity. Returns `{}` (not an error) for an entity with nothing on
        file, or an unknown/malformed id -- confirmed during recon that a
        deliberately-invalid all-zero GUID returns a clean
        all-null-fields row rather than a 404 or error."""
        rows = await self._load_info_proc(f"entityId={entity_id}", "EntityInfo")
        return rows[0] if rows else {}

    async def close(self):
        await self.session.close()
