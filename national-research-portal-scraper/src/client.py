"""HTTP transport shared by the three portals.

All three answered plain HTTP during recon, so the client stays thin: retry
with backoff, block detection by marker as well as status, and a JSON helper
for CiNii's OpenSearch API.

Government portals go down for maintenance far more often than commercial
sites, which is why ``ServiceUnavailable`` is a distinct exception: a portal
that is temporarily out must not look like a portal that has changed shape.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

BLOCK_MARKERS = (b"Just a moment", b"challenge-platform", b"cf-mitigated", b"Access Denied")
MAINTENANCE_MARKERS = (b"Maintenance", b"maintenance", b"\xec\xa0\x90\xea\xb2\x80")  # incl. KR "inspection"


class NotFoundUpstream(Exception):
    """404 from the portal."""


class ServiceUnavailable(Exception):
    """The portal is up but not serving data (maintenance, 5xx)."""


class BlockedUpstream(Exception):
    """Challenged or blocked after retries."""


def _looks_blocked(response) -> bool:
    if response.status_code in (403, 429):
        return True
    head = response.content[:4096] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class PortalClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_html(self, url: str, params: dict | None = None) -> str:
        r = await self._with_retry("GET", url, params=params)
        if r.status_code == 404:
            raise NotFoundUpstream(f"404 for {url}")
        if r.status_code >= 500:
            raise ServiceUnavailable(f"HTTP {r.status_code} for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}")
        html = r.text or ""
        head = r.content[:4096] if r.content else b""
        if any(m in head for m in MAINTENANCE_MARKERS) and len(html) < 40000:
            raise ServiceUnavailable(f"{url} is serving a maintenance page")
        return html

    async def get_json(self, url: str, params: dict | None = None) -> dict:
        r = await self._with_retry("GET", url, params=params, headers={"Accept": "application/json"})
        if r.status_code == 404:
            raise NotFoundUpstream(f"404 for {url}")
        if r.status_code >= 500:
            raise ServiceUnavailable(f"HTTP {r.status_code} for {url}")
        if r.status_code >= 400:
            raise BlockedUpstream(f"HTTP {r.status_code} for {url}")
        try:
            return r.json()
        except Exception as e:  # noqa: BLE001 -- a non-JSON answer is a shape change
            raise BlockedUpstream(f"non-JSON answer from {url}: {r.text[:200]!r}") from e

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, allow_redirects=True, **kwargs)
                if r.status_code == 404:
                    return r
                if _looks_blocked(r):
                    last_exc = BlockedUpstream(f"blocked response {r.status_code} for {url}")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are retryable
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise BlockedUpstream(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
