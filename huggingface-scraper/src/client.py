"""HTTP client wrapper -- retry, block detection, Link-header pagination.

No active WAF challenge was found on huggingface.co/api during recon (see
CRAWLING_METHOD.md) -- it is Hugging Face's own official, documented,
public REST API. Retry/backoff scaffolding is kept anyway per portfolio
convention, and to respect the platform's own rate-limit headers.
"""

import asyncio
import json
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
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

LINK_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


class NotFound(Exception):
    """A specific repo/user/org does not exist (or isn't public) --
    HTTP 404, or HTTP 401 on a repo-detail lookup (see constants.py for
    why 401 means "not found" here, not "unauthorized")."""


class InvalidRequest(Exception):
    """The API rejected the request shape/params (HTTP 400) -- a real
    bad-input bug in this actor, not a transient condition, so it must
    NOT be retried."""


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


def parse_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    m = LINK_NEXT_RE.search(link_header)
    return m.group(1) if m else None


class HuggingFaceClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_repo_json(self, url: str, params: dict | None = None) -> dict:
        """For single-resource lookups (model/dataset detail, user/org
        overview) where 404 always means not-found. Repo-detail callers
        should use get_repo_detail_json instead (401 == not-found)."""
        r = await self._with_retry("GET", url, params=params)
        if r.status_code == 404:
            raise NotFound(r.text[:300])
        if r.status_code == 400:
            raise InvalidRequest(r.text[:800])
        return self._parse_json(r)

    async def get_repo_detail_json(self, url: str) -> dict:
        """Model/dataset/space detail lookups: a nonexistent repo
        returns 401 "Invalid username or password" (confirmed live,
        not a real auth failure -- see constants.py), NOT 404."""
        r = await self._with_retry("GET", url)
        if r.status_code in (401, 404):
            raise NotFound(r.text[:300])
        if r.status_code == 400:
            raise InvalidRequest(r.text[:800])
        return self._parse_json(r)

    async def paginate(self, path: str, params: dict, max_items: int) -> list[dict]:
        """Follow the standard HTTP `Link: <url>; rel="next"` header
        until `max_items` is reached or the upstream list is exhausted."""
        items: list[dict] = []
        url = f"{path}"
        request_params = dict(params)

        while url and len(items) < max_items:
            r = await self._with_retry("GET", url, params=request_params)
            if r.status_code == 400:
                raise InvalidRequest(r.text[:800])
            batch = self._parse_json(r)
            if not isinstance(batch, list):
                raise RuntimeError(f"Expected a JSON list from {r.url}, got {type(batch).__name__}: {r.text[:300]!r}")
            items.extend(batch)
            url = parse_next_link(r.headers.get("Link") or r.headers.get("link"))
            request_params = None  # the next-page URL already carries its own full query string
            if not batch:
                break

        return items[:max_items]

    def _parse_json(self, r):
        try:
            return json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Non-JSON response from {r.url}: {r.text[:300]!r}") from e

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 429 or is_blocked(r):
                    retry_after = r.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else RETRY_DELAY_BASE * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
