"""HTTP client wrapper -- retry, block detection, dtSearch index harvesting.

No WAF, challenge, or rate limiting of any kind was found on
elibrary.judiciary.gov.ph during recon (see CRAWLING_METHOD.md). Retry/backoff
scaffolding is kept per portfolio convention; the block-marker list is a
defensive no-op unless that posture changes.
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    FALLBACK_SEARCH_INDEXES,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    SEARCH_FORM_URL,
    TLS_PROFILE,
    VERIFY_TLS,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
    b"_px-captcha",
    b"Attention Required! | Cloudflare",
]

# <option value="*{81aab...} sc_decision">
INDEX_OPTION_RE = re.compile(r"""value=["'](\*\{[0-9a-f]+\}\s*(\w+))["']""")


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class ELibraryClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
            verify=VERIFY_TLS,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._indexes: dict[str, str] | None = None

    async def get(self, url: str, params: dict | None = None):
        return await self._with_retry("GET", url, params=params)

    async def post(self, url: str, data: dict, headers: dict | None = None):
        return await self._with_retry("POST", url, data=data, headers=headers)

    async def search_indexes(self) -> dict[str, str]:
        """dtSearch index tokens embed a content hash that changes whenever
        the judiciary rebuilds an index, so they are harvested live and only
        fall back to the recon-time constants if the form can't be read."""
        if self._indexes is not None:
            return self._indexes
        try:
            r = await self.get(SEARCH_FORM_URL)
            if r.status_code == 200:
                found = {name: token for token, name in INDEX_OPTION_RE.findall(r.text)}
                if found:
                    self._indexes = {**FALLBACK_SEARCH_INDEXES, **found}
                    return self._indexes
        except (RuntimeError, ConnectionError, OSError):
            pass  # fall through to the pinned recon-time tokens
        self._indexes = dict(FALLBACK_SEARCH_INDEXES)
        return self._indexes

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

    async def close(self):
        await self.session.close()
