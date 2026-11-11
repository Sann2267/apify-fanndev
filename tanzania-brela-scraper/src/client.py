"""HTTP client for BRELA ORS's public business/company search JSON API.

See `constants.py` for the full recon summary. Key point: the WAF in front
of `ors.brela.go.tz` blocks form-urlencoded/query-string requests with a
generic 403 "Web Application Firewall" signature page regardless of
parameter values -- the fix is sending the exact JSON-POST shape the real
front-end uses (`Content-Type: application/json`, JSON-encoded body), which
passes cleanly and needs no cookies/session at all.

Same broad-except retry pattern as the rest of this project's registry
actors: `curl_cffi`'s own exception hierarchy (`CurlError` -> `OSError`)
does NOT inherit from Python's builtin `ConnectionError`/`TimeoutError`
despite sharing class names, so a narrow except list would silently miss
real transient failures.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    ENTITY_TYPE_MAP,
    MAX_RETRIES,
    PAGE_SIZE,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    SEARCH_URL,
    TLS_PROFILE,
)
from src.extractor import UnexpectedShape, parse_search_response

BLOCK_MARKERS = [
    b"Web Application Firewall",
    b"Just a moment",
    b"challenge-platform",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class BRELAClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _post_json(self, url: str, body: dict):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.post(url, data=json.dumps(body))
                if is_blocked(r):
                    last_exc = RuntimeError(f"blocked (HTTP {r.status_code})")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def search(self, query: str, entity_type: str, max_results: int) -> list[dict]:
        """Search by name (any non-purely-numeric query) or by
        registration/incorporation number (purely-numeric query). Confirmed
        during recon that the `bn_name`/`bn_number` field names are NOT
        actually type-gated server-side -- they match the same underlying
        columns for both business names and companies -- so this client
        always sends one or the other, never needs cm_name/cm_number too.
        Pages through `PageNumber` until `max_results` is reached or the
        server reports no more records.
        """
        is_number = query.strip().isdigit()
        field = "bn_number" if is_number else "bn_name"
        object_type = ENTITY_TYPE_MAP.get(entity_type)

        rows: list[dict] = []
        page = 1
        total = None
        while len(rows) < max_results:
            page_size = min(PAGE_SIZE, max_results - len(rows))
            body = {field: query.strip(), "PageSize": page_size, "PageNumber": page}
            if object_type:
                body["object_type"] = object_type
            r = await self._post_json(SEARCH_URL, body)
            if r.status_code != 200:
                raise RuntimeError(f"POST {SEARCH_URL} -> HTTP {r.status_code}")
            text = r.text.strip()
            if not text:
                # Empty body: observed when required query fields are missing
                # entirely -- shouldn't happen here since `field` is always
                # set, but treat as zero matches rather than a hard error.
                break
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise UnexpectedShape(f"response body did not parse as JSON: {e}; body={text[:300]!r}") from e
            page_rows, total = parse_search_response(data)
            rows.extend(page_rows)
            if not page_rows or len(rows) >= total:
                break
            page += 1
        return rows[:max_results]

    async def close(self):
        await self.session.close()
