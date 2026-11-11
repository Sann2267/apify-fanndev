"""HTTP transport for snapchat.com -- fetch, retry, block detection, payload lift.

Transport only: every response is reduced to the page's ``__NEXT_DATA__``
``pageProps`` dict and handed to the extractor. Two upstream answers are
*normal* and must not be confused with failures:

* **404** -- the username does not exist (verified: a made-up handle returns a
  6 KB 404 while real handles return 135 KB-1.4 MB). Raised as ``ProfileNotFound``
  so the caller can emit a not_found row instead of retrying four times.
* **Missing sections** -- an account with no lenses simply has ``lenses: []``.
  Empty is a real answer about that account, not a parse failure.

A document that arrives *without* ``__NEXT_DATA__`` is neither of those: it means
the page shape changed or something intercepted the response, so it raises
``UnexpectedShape`` rather than returning an empty record (fail loud, never
fail silent -- .ai/conventions/error-handling.md).
"""

import asyncio
import json
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Access denied",
    b"Request blocked",
)


class ProfileNotFound(Exception):
    """HTTP 404 -- no such username. Not retryable."""


class UnexpectedShape(Exception):
    """200 OK but the document carries no __NEXT_DATA__ payload."""


class BlockedUpstream(Exception):
    """Challenge page or a block status code survived every retry."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class SnapchatClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=45,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_page_props(self, url: str) -> dict:
        """Fetch a Snapchat page and return its ``props.pageProps`` dict."""
        r = await self._with_retry("GET", url)
        if r.status_code == 404:
            raise ProfileNotFound(f"404 for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}: {r.text[:200]!r}")

        m = _NEXT_DATA_RE.search(r.text or "")
        if not m:
            raise UnexpectedShape(
                f"no __NEXT_DATA__ in {url} ({len(r.content)} bytes). Snapchat's page "
                f"shape changed, or the response was intercepted."
            )
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            raise UnexpectedShape(f"__NEXT_DATA__ in {url} is not valid JSON: {e}") from e

        props = (data.get("props") or {}).get("pageProps")
        if not isinstance(props, dict):
            raise UnexpectedShape(f"__NEXT_DATA__ in {url} has no props.pageProps object")
        # buildId is the only useful thing outside pageProps; it identifies the
        # deployed frontend build and makes shape drift diagnosable from the data.
        props["_buildId"] = data.get("buildId")
        return props

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 404:
                    return r  # definitive, never retried
                if is_blocked(r):
                    last_exc = BlockedUpstream(f"blocked response {r.status_code} for {url}")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- every network error is retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise BlockedUpstream(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
