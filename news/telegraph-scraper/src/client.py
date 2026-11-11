"""HTTP client wrapper -- warmup, retry, block detection.

`edge101` is the pinned profile (see constants.py) because several
other profiles in the standard ladder (`chrome131`, `chrome124`,
`safari17_0`, `firefox133`) get a 402 "TollBit Token" Akamai block on
telegraph.co.uk. `is_blocked` treats 402 as a block status (in addition
to the usual 403/407/429/503) and also checks for the TollBit/Akamai
block body markers, so if the pinned profile ever gets flagged too (e.g.
a burnt residential-proxy IP), the retry loop fires instead of silently
returning the block page as if it were a real response.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
    WARMUP_URL,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
    b"_fs_ch_",
    b"Request unsuccessful",
    b"Access Issue Help",
    b"TollBit Token",
    b"tollbit.dev",
]


def is_blocked(response) -> bool:
    if response.status_code in (402, 403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class TelegraphClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._warm = False

    async def init_session(self):
        if self._warm:
            return
        r = await self.session.get(WARMUP_URL)
        if is_blocked(r):
            raise RuntimeError(f"Warmup blocked: status={r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"Warmup failed: {r.status_code}")
        self._warm = True

    async def get(self, url: str, **kwargs):
        await self.init_session()
        return await self._with_retry("GET", url, **kwargs)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 404:
                    return r  # real 404 -- not a block, don't retry
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
