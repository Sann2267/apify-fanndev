"""HTTP client for ROCIP's public "Search for a company or business name"
JSON API (Saint Lucia's Registry of Companies and Intellectual Property).

No WAF, no CAPTCHA, no TLS-fingerprint gate observed anywhere on
`efiling.rocip.gov.lc` during recon -- plain IIS/ASP.NET, no `cf-ray`/
challenge markers, and a bare `curl` baseline (no impersonation at all)
worked for every request tried. `curl_cffi` `chrome124` is used anyway for
portfolio-wide consistency and because it costs nothing. Note the base URL
is plain `http://` -- HTTPS fails the TLS handshake outright on this host
(see `constants.py`).

Same broad-except retry pattern as the rest of this project's registry
actors: `curl_cffi`'s own exception hierarchy (`CurlError` -> `OSError`)
does NOT inherit from Python's builtin `ConnectionError`/`TimeoutError`
despite sharing class names, so a narrow except list would silently miss
real transient failures.

See `constants.py` for the full recon summary and `extractor.py` for the
wire format.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    SEARCH_MODE_MAP,
    SEARCH_URL,
    TLS_PROFILE,
)
from src.extractor import UnexpectedShape, parse_search_response

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


class ROCIPClient:
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

    async def search(self, query: str, mode: str, max_results: int) -> list[dict]:
        """Search ROCIP's Entities/Directors/Shareholders index. `mode` is
        one of `SEARCH_MODE_MAP`'s keys ("entities", "directors",
        "shareholders"). There is no pagination on this endpoint -- the
        server itself caps broad queries at 50 rows (see `constants.py`) --
        so `max_results` only ever trims the single response down, never
        triggers additional requests.
        """
        key = SEARCH_MODE_MAP.get(mode, SEARCH_MODE_MAP["entities"])
        body = {"input": f"key={key},query={query.strip()}", "name": "EntitySearch"}

        r = await self._post_json(SEARCH_URL, body)
        if r.status_code != 200:
            raise RuntimeError(f"POST {SEARCH_URL} -> HTTP {r.status_code}")
        text = r.text.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise UnexpectedShape(f"response body did not parse as JSON: {e}; body={text[:300]!r}") from e
        rows = parse_search_response(data)
        return rows[:max_results]

    async def close(self):
        await self.session.close()
