"""HTTP client for COMPRASAL's public JSON API (`www.comprasal.gob.sv/api/v1/publico/...`).

No WAF challenge, no CAPTCHA, no login needed for any endpoint used here (see
`constants.py` for the full recon writeup). `curl_cffi` `chrome124` is used
for portfolio-wide consistency even though a bare `urllib` request worked
cleanly during recon -- Cloudflare fronts the site and could tighten up.

The retry loop wraps ALL request calls broadly: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures (portfolio-wide
Babak 22b fix -- also applied in `main.py`'s run-loop).
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    AWARDED_URL,
    DEFAULT_HEADERS,
    DETAIL_URL,
    INSTITUTIONS_URL,
    MAX_RETRIES,
    OPEN_URL,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A request completed (no exception) but returned a non-200 status or
    a body that isn't valid JSON -- treated as retryable up to MAX_RETRIES,
    then raised."""


class ComprasalClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _get_json(self, url: str, params: dict | None = None):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.get(url, params=params)
                if r.status_code == 200:
                    try:
                        return json.loads(r.text)
                    except json.JSONDecodeError as e:
                        last_exc = FetchFailed(f"GET {url} -> HTTP 200 but non-JSON body ({len(r.text)} bytes): {e}")
                elif r.status_code == 404:
                    # The API's own "not found" -- confirmed clean/structured
                    # during recon (e.g. documents endpoint), not a WAF page.
                    # Not retryable -- surfaced immediately as FetchFailed.
                    raise FetchFailed(f"GET {url} -> HTTP 404: {r.text[:300]}")
                elif r.status_code == 500:
                    # COMPRASAL uses HTTP 500 for its own app-level validation
                    # errors too (e.g. an unrecognized detail id) -- confirmed
                    # via a clean {"error":{"message":...,"code":400}} body,
                    # not a crash/WAF page. Not retryable.
                    raise FetchFailed(f"GET {url} -> HTTP 500 (app-level error): {r.text[:300]}")
                else:
                    last_exc = FetchFailed(f"GET {url} -> HTTP {r.status_code}, {len(r.text)} bytes")
            except FetchFailed:
                raise
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
            await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for GET {url}: {last_exc!r}")

    async def fetch_open(self, institucion_id: int | None = None):
        """`/procesos/disponibles` -- all currently open/active processes in
        one response (bare JSON array). `institucion=<id>` is the one
        confirmed-real server-side filter this endpoint accepts."""
        params = {"institucion": institucion_id} if institucion_id is not None else None
        return await self._get_json(OPEN_URL, params=params)

    async def fetch_awarded_page(self, page: int, per_page: int):
        """`/procesos/publicos` -- one page of the historical/awarded ledger.
        Only `page`/`per_page` have a real effect (confirmed during recon --
        `institucion`/date/name params are silently ignored)."""
        return await self._get_json(AWARDED_URL, params={"page": page, "per_page": per_page})

    async def fetch_detail(self, process_id):
        """`/detalle/procesos/publicos/<id>` -- full detail for one process,
        keyed by the process's numeric internal id (not `codigo_proceso`)."""
        return await self._get_json(f"{DETAIL_URL}/{process_id}")

    async def fetch_institutions(self):
        return await self._get_json(INSTITUTIONS_URL)

    async def close(self):
        await self.session.close()
