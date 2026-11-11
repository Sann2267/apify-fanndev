"""HTTP client wrapper -- retry, block detection, archive pagination,
publication-profile HTML extraction.

No active WAF was found on any Substack publication host during recon (see
CRAWLING_METHOD.md) -- retry/backoff scaffolding is kept anyway per
portfolio convention, to smooth over transient network errors.
"""

import asyncio
import json
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    ARCHIVE_PAGE_SIZE,
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

_PRELOADS_RE = re.compile(r'window\._preloads\s*=\s*JSON\.parse\("(.*?)"\)</script>', re.S)


class NotFound(Exception):
    """The slug/URL does not resolve to any post -- HTTP 404."""


class NotAuthorized(Exception):
    """Endpoint requires an authenticated session (HTTP 401/403) -- e.g. the
    `/api/v1/publication` family. Out of scope per this project's
    "No Login" constraint; the publication-profile fallback (S2-html) is
    used instead. See CRAWLING_METHOD.md."""


def is_blocked(response) -> bool:
    # 403 is deliberately excluded here: Substack itself uses a plain
    # `403 "Not authorized"` for endpoints that require a login (e.g.
    # `/api/v1/publication`, see constants.py) -- confirmed live, not a WAF
    # challenge. Treating it as "blocked" would waste the full retry budget
    # on a response that will never change, and would keep get_json's own
    # `NotAuthorized` handling below from ever being reached.
    if response.status_code in (407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class SubstackClient:
    def __init__(
        self,
        proxy_url: str | None = None,
        new_proxy_url=None,
        profile: str = TLS_PROFILE,
    ):
        """`new_proxy_url` (optional async callable, no args) is Apify's own
        `proxy_config.new_url` -- called to grab a fresh sticky residential
        session (usually a different egress IP) when the current one gets
        blocked mid-run, instead of retrying the same possibly-bad IP 5
        times in a row. Confirmed live (2026-08-29): a run through the
        Apify Residential proxy exhausted all 5 retries on a single flaky
        IP that a fresh sticky session had no trouble with."""
        self._new_proxy_url = new_proxy_url
        self._profile = profile
        self.session = self._build_session(proxy_url)

    def _build_session(self, proxy_url: str | None) -> AsyncSession:
        session = AsyncSession(
            impersonate=self._profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        session.headers.update(DEFAULT_HEADERS)
        return session

    async def _rotate_proxy(self):
        if not self._new_proxy_url:
            return
        old_session = self.session
        new_url = await self._new_proxy_url()
        self.session = self._build_session(new_url)
        await old_session.close()

    async def get_json(self, host: str, path: str, params: dict | None = None) -> dict | list:
        r = await self._with_retry("GET", f"https://{host}{path}", params=params)
        if r.status_code == 404:
            raise NotFound(r.text[:300])
        if r.status_code in (401, 403):
            raise NotAuthorized(r.text[:300])
        try:
            return json.loads(r.text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Non-JSON response from {host}{path}: {r.text[:300]!r}") from e

    async def fetch_post(self, host: str, slug: str) -> dict:
        return await self.get_json(host, f"/api/v1/posts/{slug}")

    async def paginate_archive(self, host: str, sort: str, max_items: int) -> list[dict]:
        """Follow `offset`/`limit` on /api/v1/archive until `max_items` is
        reached or the upstream page comes back empty (confirmed live: an
        offset past the end of the list returns `200 []`, not an error)."""
        items: list[dict] = []
        offset = 0
        while len(items) < max_items:
            batch = await self.get_json(
                host, "/api/v1/archive", params={"sort": sort, "offset": offset, "limit": ARCHIVE_PAGE_SIZE}
            )
            if not batch:
                break
            items.extend(batch)
            offset += ARCHIVE_PAGE_SIZE
        return items[:max_items]

    async def fetch_publication_profile(self, host: str) -> dict:
        """S2-html: the `pub` object embedded in `window._preloads` on the
        publication homepage. No public unauthenticated JSON endpoint was
        found for this (see constants.py recon summary)."""
        r = await self._with_retry("GET", f"https://{host}/")
        if r.status_code == 404:
            raise NotFound(r.text[:300])
        m = _PRELOADS_RE.search(r.text)
        if not m:
            raise RuntimeError(f"window._preloads not found in homepage HTML for {host}")
        preloads = json.loads(json.loads('"' + m.group(1) + '"'))
        pub = preloads.get("pub")
        if not pub:
            raise RuntimeError(f"window._preloads has no 'pub' key for {host}")
        return pub

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        last_status = None
        last_body_head = b""
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    last_status = r.status_code
                    last_body_head = (r.content or b"")[:300]
                    await self._rotate_proxy()
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(
            f"Exhausted {MAX_RETRIES} retries for {url}: last_status={last_status} "
            f"last_body_head={last_body_head!r} last_exc={last_exc!r}"
        )

    async def close(self):
        await self.session.close()
