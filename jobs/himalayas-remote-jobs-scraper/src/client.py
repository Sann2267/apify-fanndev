"""HTTP transport for the Himalayas jobs feed.

The feed answered 200 on every probe with no challenge, so this stays thin.
Two things are still worth encoding:

* The HTML side of the same host answers **403** (`/companies/<slug>`,
  `/jobs/<slug>`), so a 403 here means "you left the JSON feed", not "you are
  blocked" -- and the error says so, because the wrong diagnosis sends the next
  maintainer hunting for a WAF that is not there.
* A 200 whose body is not the documented envelope is a failure, not something
  to parse into zero jobs.
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE, TLS_PROFILE


class FeedUnavailable(Exception):
    """The feed did not return its documented JSON envelope."""


class HimalayasClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_json(self, url: str) -> dict:
        last: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request("GET", url, allow_redirects=True)
            except Exception as exc:  # noqa: BLE001 -- network errors are retryable
                last = exc
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            if r.status_code == 403:
                raise FeedUnavailable(
                    f"403 for {url}. On this host a 403 means the request left the public "
                    f"JSON feed -- the HTML pages (/companies/<slug>, /jobs/<slug>) are all "
                    f"403 while /jobs/api is open. Check the path before suspecting a block."
                )
            if r.status_code >= 400:
                last = FeedUnavailable(f"HTTP {r.status_code} for {url}")
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            try:
                payload = r.json()
            except (json.JSONDecodeError, ValueError) as exc:
                last = FeedUnavailable(f"200 but not JSON for {url}: {exc}")
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                continue

            if not isinstance(payload, dict) or "jobs" not in payload:
                raise FeedUnavailable(
                    f"200 with an unexpected shape for {url}: top-level keys "
                    f"{sorted(payload)[:8] if isinstance(payload, dict) else type(payload).__name__}. "
                    f"The documented envelope carries a 'jobs' list."
                )
            return payload

        raise FeedUnavailable(f"Exhausted {MAX_RETRIES} retries for {url}: {last!r}")

    async def close(self):
        await self.session.close()
