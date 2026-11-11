"""HTTP client for npc.gov.pg -- both the WordPress REST list routes
(disposals-notice/contracts-awarded discovery) and plain HTML page fetches
(tender-advertisement listing page + every individual detail page).

No WAF, no login, no rate limiting observed during recon (see
`constants.py`), but the retry loop still wraps every request the same way
as the rest of this portfolio: `curl_cffi`'s own exception hierarchy
(`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REST_HEADERS,
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


class NPCClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )

    async def _with_retry(self, url: str, headers: dict, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.get(url, headers=headers, **kwargs)
                if r.status_code == 404:
                    return r  # not retryable -- caller decides how to handle
                if is_blocked(r):
                    last_exc = RuntimeError(f"HTTP {r.status_code} blocked/prohibited response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def fetch_html(self, url: str) -> str:
        r = await self._with_retry(url, headers=DEFAULT_HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"GET {url} -> HTTP {r.status_code}")
        return r.text

    async def fetch_rest_page(self, post_type: str, page: int, per_page: int) -> tuple[list[dict], int]:
        """Fetches one page of `/wp-json/wp/v2/<post_type>`. Returns
        `(rows, total)` where `total` is the upstream `X-WP-Total` count.
        Raises `RuntimeError` on non-200 or `UnexpectedShape` on a shape that
        isn't a JSON list (fail loud per `.ai/CLAUDE.md` principle 6)."""
        url = f"{BASE_URL}/wp-json/wp/v2/{post_type}"
        params = {"page": page, "per_page": per_page, "orderby": "date", "order": "desc"}
        r = await self._with_retry(url, headers=REST_HEADERS, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {post_type} page={page} -> HTTP {r.status_code}: {r.text[:300]!r}")
        try:
            payload = r.json()
        except ValueError as e:
            raise UnexpectedShape(f"Non-JSON response for {post_type} page={page}: {e!r}") from e
        if not isinstance(payload, list):
            raise UnexpectedShape(f"{post_type} response is not a list of rows: {str(payload)[:300]!r}")
        total = int(r.headers.get("X-WP-Total", len(payload)))
        return payload, total

    async def close(self):
        await self.session.close()
