"""HTTP client wrapper -- warmup, retry, block detection.

eprocure.zppa.org.zm is a plain BigIP-fronted Java web app (the "European
Dynamics" e-GP platform). No Cloudflare/DataDome/Akamai/etc. WAF, no
CAPTCHA was observed on any page this actor touches -- confirmed with
`curl_cffi` across chrome124/chrome131/safari17_0/edge101 impersonation
profiles, all returning clean 200s with identical content. `curl_cffi`
impersonation is used anyway as this portfolio's default posture (see
.ai/CLAUDE.md principle #2), not because a block was ever seen.

One real access-control quirk (not a WAF): some *individual tender detail
pages* (`cft/prepareViewCfTWS.do?resourceId=...`) 302-redirect to
`/cas/login` instead of returning the page. This happens for tenders whose
bid-submission deadline has already passed (i.e. every row surfaced by the
"Opened Bid Details" listing) -- currently-open tenders load fine with no
login. This is a per-tender access rule on the *detail* page, not a
site-wide login wall on *listings* (the listing tables themselves, and
detail pages for still-open tenders, are all freely public). See
CRAWLING_METHOD.md.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    HOME_URL,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
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
    # NOTE: 302/303 is NOT treated as blocked here -- the CAS-login redirect
    # on closed-tender detail pages is an expected, meaningful response the
    # caller inspects directly (see main.py fetch_detail), not a WAF signal.
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class ZppaClient:
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
        r = await self.session.get(HOME_URL)
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
