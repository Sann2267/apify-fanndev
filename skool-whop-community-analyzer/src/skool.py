"""Skool client -- fetch a community's /about page and pull its embedded
`__NEXT_DATA__` JSON. No login, no WAF challenge encountered during
recon (see CRAWLING_METHOD.md).
"""

import json
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SKOOL_BASE_URL,
    SKOOL_NEXT_DATA_RE,
    TLS_PROFILE,
)

import asyncio

_SLUG_RE = re.compile(r"^(?:https?://)?(?:www\.)?skool\.com/", re.IGNORECASE)
_NEXT_DATA_RE = re.compile(SKOOL_NEXT_DATA_RE, re.DOTALL)

BLOCK_MARKERS = [b"Just a moment", b"challenge-platform", b"captcha-delivery.com"]


class NotFoundOrPrivate(Exception):
    """The slug doesn't resolve to a public community -- Skool 30x-redirects
    unknown/private/removed slugs to /signup rather than returning a 404."""


class UnexpectedShape(Exception):
    """__NEXT_DATA__ didn't contain props.pageProps.currentGroup -- Skool's
    page structure changed; investigate before trusting further output."""


def extract_slug(raw: str) -> str:
    s = raw.strip()
    s = _SLUG_RE.sub("", s)
    s = s.split("?")[0].split("#")[0]
    return s.strip("/")


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


def parse_display_price(metadata: dict) -> dict | None:
    """`displayPrice` is a JSON-encoded *string* (not a nested object) on
    communities that disclose their price unauthenticated, e.g.
    '{"currency":"usd","amount":700,"recurring_interval":"month"}'
    (confirmed live on skool.com/freegroup -- $7/month). Many paid
    communities do NOT expose this field to guests at all (confirmed on
    skool.com/thetradingcafe, membership=1/paid, zero displayPrice in the
    unauthenticated payload) -- treat absence as "not disclosed", not an
    error. Lives at currentGroup.metadata.displayPrice, not top-level."""
    raw = metadata.get("displayPrice")
    if not raw or not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    amount = parsed.get("amount")
    interval = parsed.get("recurring_interval")
    if amount is None:
        return None
    amount_usd = amount / 100
    if interval == "year":
        monthly_usd = round(amount_usd / 12, 2)
    elif interval == "month":
        monthly_usd = amount_usd
    else:
        monthly_usd = None
    return {
        "amountUsd": amount_usd,
        "currency": parsed.get("currency"),
        "interval": interval,
        "monthlyEquivalentUsd": monthly_usd,
    }


class SkoolClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_community(self, slug: str) -> dict:
        r = await self._with_retry("GET", f"{SKOOL_BASE_URL}/{slug}/about")
        final_url = str(r.url)
        if "/signup" in final_url or r.status_code == 404:
            raise NotFoundOrPrivate(f"'{slug}' -> {final_url} (status={r.status_code})")

        m = _NEXT_DATA_RE.search(r.text)
        if not m:
            raise UnexpectedShape(f"No __NEXT_DATA__ script found for '{slug}'")
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            raise UnexpectedShape(f"__NEXT_DATA__ is not valid JSON for '{slug}': {e}") from e

        current_group = data.get("props", {}).get("pageProps", {}).get("currentGroup")
        if not current_group or not isinstance(current_group, dict):
            raise UnexpectedShape(
                f"props.pageProps.currentGroup missing for '{slug}' -- keys="
                f"{list(data.get('props', {}).get('pageProps', {}).keys())}"
            )
        return current_group

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
