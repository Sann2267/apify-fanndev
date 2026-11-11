"""HTTP client wrapper -- retry, block detection, GraphQL error surfacing.

Same pattern as the sibling `twitch-channel-scraper`/
`twitch-analytics-scraper` actors in this portfolio: no active WAF
challenge was found on gql.twitch.tv during recon (see
CRAWLING_METHOD.md).
"""

import asyncio
import json

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    GQL_URL,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

BLOCK_MARKERS = [
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"captcha-delivery.com",
    b"Pardon Our Interruption",
]


class IntegrityCheckFailed(Exception):
    """Twitch's device-attestation gate rejected the request. Not
    expected to trigger in this actor (no `after`-cursor pagination is
    used), but kept for parity/defense-in-depth with the sibling actors."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class TwitchClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )

    async def graphql(self, query: str, variables: dict | None = None) -> dict:
        """POST an inline GraphQL query + variables, return the parsed
        `data` dict. Variables (not string interpolation) are used for
        all user-supplied values -- safe against injection.
        """
        body = {"query": query, "variables": variables or {}}
        r = await self._with_retry("POST", GQL_URL, headers=DEFAULT_HEADERS, json=body)
        try:
            payload = json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Non-JSON response from {GQL_URL}: {r.text[:300]!r}") from e

        errors = payload.get("errors")
        if errors:
            first = errors[0]
            code = (first.get("extensions") or {}).get("code")
            if code == "IntegrityCheckFailed":
                raise IntegrityCheckFailed(first.get("message", "failed integrity check"))
            raise RuntimeError(f"GraphQL error(s): {json.dumps(errors)[:500]}")

        return payload.get("data") or {}

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
