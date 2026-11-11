"""HTTP client wrapper -- retry, block detection, GraphQL error surfacing.

No active WAF challenge was found on gql.twitch.tv during recon (see
CRAWLING_METHOD.md) -- the endpoint is Twitch's own public, unauthenticated
web-client GraphQL API. Retry/backoff scaffolding is kept anyway per
portfolio convention, and to smooth over transient network errors.
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
    """Twitch's device-attestation gate rejected the request (deep
    pagination beyond page 1) -- not retryable with an HTTP-only client.
    See CRAWLING_METHOD.md."""


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
        """POST an inline GraphQL query + variables, return the parsed `data` dict.

        Variables (not string interpolation) are used for all user-supplied
        values (e.g. `login`) -- safe against injection and the standard
        way to parameterize a GraphQL POST body.

        Raises IntegrityCheckFailed if Twitch's device-attestation gate
        rejects the request (only observed on `after`-cursor pagination
        beyond page 1). Raises RuntimeError on any other GraphQL `errors`
        entry -- those indicate a real schema/field-shape change and must
        fail loud, not silently return partial data.
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
