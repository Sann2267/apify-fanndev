"""HTTP client for ANPI's public "Annuaire des entreprises" JSON REST route.

Unlike Botswana's CIPA (a stateful Verne/Foster Moore delta protocol) or
Malawi's CRIPC (server-rendered HTML), Comoros's ANPI directory is a plain
WordPress REST route (`GET /wp-json/anpi/v1/annonces`) that returns clean
JSON directly -- no HTML parsing, no session/transaction state, no nonce
required for GET. See `constants.py` for the full recon summary.

Retry loop wraps ALL request calls in a broad `except Exception`, same fix
as every other actor in this portfolio: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list silently misses real transient failures.
"""

import asyncio
import time

from curl_cffi.requests import AsyncSession

from src.constants import (
    API_PATH,
    BASE_URL,
    CRAWL_DELAY,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    PER_PAGE,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)
from src.extractor import UnexpectedShape


class _RateLimiter:
    """Process-wide pacing gate honoring robots.txt's `Crawl-delay: 10` --
    every `ANPIClient` instance (one per job) shares this single limiter, so
    the actual request rate against `investcomoros.net` never exceeds one
    request per `CRAWL_DELAY` seconds no matter how many jobs/pages are
    queued concurrently (see constants.py)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            delay = self._last + self.min_interval - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


_rate_limiter = _RateLimiter(CRAWL_DELAY)

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


class ANPIClient:
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
                await _rate_limiter.wait()
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    last_exc = RuntimeError(f"HTTP {r.status_code} blocked/prohibited response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def fetch_page(self, filters: dict, page: int, per_page: int = PER_PAGE) -> dict:
        """Fetches one page of `/wp-json/anpi/v1/annonces`. Returns the
        parsed `{"total", "pages", "data"}` dict. Raises `RuntimeError` on a
        non-200 response or `UnexpectedShape` if the JSON doesn't have the
        keys this actor depends on (fail loud, per .ai/CLAUDE.md #6, rather
        than silently returning an empty page on an upstream shape change).
        """
        params = {k: v for k, v in filters.items() if v not in (None, "")}
        params["page"] = page
        params["per_page"] = per_page
        r = await self._with_retry("GET", f"{BASE_URL}{API_PATH}", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"GET {API_PATH} page={page} params={params} -> HTTP {r.status_code}")
        try:
            payload = r.json()
        except ValueError as e:
            raise UnexpectedShape(f"Non-JSON response for page={page} params={params}: {e!r}") from e
        if not isinstance(payload, dict) or "data" not in payload or "total" not in payload:
            raise UnexpectedShape(f"Response missing 'data'/'total' keys: {str(payload)[:300]!r}")
        return payload

    async def close(self):
        await self.session.close()
