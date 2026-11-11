"""HTTP client for ODPIC's public "publication_registre" WordPress REST route.

Like Comoros's ANPI directory, this is a plain WordPress REST endpoint that
returns clean JSON directly -- no HTML parsing, no session/transaction
state, no login/nonce required for GET. Unlike ANPI's custom route, this is
WordPress core's generic `wp/v2/<post_type>` route, so pagination totals
arrive as `X-WP-Total`/`X-WP-TotalPages` response headers rather than in the
JSON body. See `constants.py` for the full recon summary.

Retry loop wraps ALL request calls in a broad `except Exception`, same fix
as every other actor in this portfolio: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    API_PATH,
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    PER_PAGE,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)
from src.extractor import UnexpectedShape

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Attention Required",
    b"Pardon Our Interruption",
    b"Access Denied",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class ODPICClient:
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
                if r.status_code == 400:
                    # Not retryable -- a bad param (e.g. per_page out of
                    # bounds, malformed date). Surface immediately.
                    return r
                if is_blocked(r):
                    last_exc = RuntimeError(f"HTTP {r.status_code} blocked/prohibited response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def fetch_page(self, filters: dict, page: int, per_page: int = PER_PAGE) -> tuple[list[dict], int]:
        """Fetches one page of `/wp-json/wp/v2/publication_registre`. Returns
        `(rows, total)` where `total` is the upstream `X-WP-Total` count for
        this filter set. Raises `RuntimeError` on a non-200 response or
        `UnexpectedShape` if the JSON isn't a list (fail loud, per
        `.ai/CLAUDE.md` principle 6, rather than silently returning an empty
        page on an upstream shape change).
        """
        params = {k: v for k, v in filters.items() if v not in (None, "")}
        params["page"] = page
        params["per_page"] = per_page
        r = await self._with_retry("GET", f"{BASE_URL}{API_PATH}", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {API_PATH} page={page} params={params} -> HTTP {r.status_code}: {r.text[:300]!r}")
        try:
            payload = r.json()
        except ValueError as e:
            raise UnexpectedShape(f"Non-JSON response for page={page} params={params}: {e!r}") from e
        if not isinstance(payload, list):
            raise UnexpectedShape(f"Response is not a list of rows: {str(payload)[:300]!r}")
        total = int(r.headers.get("X-WP-Total", len(payload)))
        return payload, total

    async def close(self):
        await self.session.close()
