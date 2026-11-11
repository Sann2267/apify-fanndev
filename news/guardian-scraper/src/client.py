import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Verify you are human",
    b"Access Denied",
    b"The Guardian",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(marker in head for marker in BLOCK_MARKERS if marker not in (b"The Guardian",))


class GuardianClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._warm = False

    async def get(self, url: str, **kwargs):
        return await self._with_retry("GET", url, **kwargs)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.request(method, url, **kwargs)
                if is_blocked(response):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                    continue
                return response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
