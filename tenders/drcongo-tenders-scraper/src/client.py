"""HTTP client for marchepublic.cd (DRC's SIGMAP public procurement portal).

No TLS-fingerprint gate and no WAF was found on this target during recon
(see CRAWLING_METHOD.md) -- `curl_cffi` is used for portfolio consistency and
residential-proxy compatibility, not because it's load-bearing here.

Navigating this JSF/PrimeFaces app requires replaying its own AJAX protocol:
prime a fresh ViewState from `index.xhtml`, POST a PrimeFaces AJAX postback
that "clicks" one mega-menu item (which the server answers with a bare
`<redirect>` partial-response and stores server-side, session-scoped, which
publication type was selected), then GET `publication.xhtml` in the same
session to render that category's DataView grid. The ViewState is re-primed
before every category click rather than reused across requests -- it did not
survive being reused for a second POST during recon (a stale ViewState
silently produced a validation-error response instead of real results).
"""

import asyncio
import re

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    AJAX_HEADERS,
    HEADERS,
    INDEX_URL,
    MAX_RETRIES,
    PUBLICATION_URL,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)

VIEWSTATE_RE = re.compile(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"')


class FetchFailed(Exception):
    """Raised after exhausting retries, or on a response shape that means
    the JSF navigation itself failed (no ViewState found, no redirect)."""


class SigmapClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=25,
        )
        self.session.headers.update(HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code in (429, 502, 503, 504):
                    last_exc = RuntimeError(f"HTTP {r.status_code} transient response")
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except (RequestException, ConnectionError, OSError) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from the
                # builtin one (parallel MRO, same name) -- both listed, plus
                # OSError (curl_cffi's CurlError base), per the portfolio-wide
                # Babak 22b fix.
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def fetch_category_page(self, jsf_source_id: str) -> str:
        """Primes a fresh ViewState from index.xhtml, "clicks" the given
        mega-menu item via a PrimeFaces AJAX postback, follows the server's
        own redirect instruction, then GETs publication.xhtml in the same
        session to render whichever category was just selected."""
        r = await self._with_retry("GET", INDEX_URL)
        if r.status_code != 200:
            raise FetchFailed(f"GET index.xhtml -> HTTP {r.status_code}")
        m = VIEWSTATE_RE.search(r.text)
        if not m:
            raise FetchFailed("no javax.faces.ViewState found on index.xhtml -- page shape has likely changed")
        view_state = m.group(1)

        data = {
            "landing-menu": "landing-menu",
            "javax.faces.ViewState": view_state,
            "javax.faces.source": jsf_source_id,
            "javax.faces.partial.event": "click",
            "javax.faces.partial.execute": "landing-menu",
            jsf_source_id: jsf_source_id,
            "javax.faces.partial.ajax": "true",
        }
        r2 = await self._with_retry("POST", INDEX_URL, data=data, headers=AJAX_HEADERS)
        if r2.status_code != 200:
            raise FetchFailed(f"POST category click {jsf_source_id} -> HTTP {r2.status_code}")
        if "<redirect" not in r2.text:
            raise FetchFailed(
                f"category click {jsf_source_id} did not redirect -- page shape has likely changed: {r2.text[:200]!r}"
            )

        r3 = await self._with_retry("GET", PUBLICATION_URL)
        if r3.status_code != 200:
            raise FetchFailed(f"GET publication.xhtml -> HTTP {r3.status_code}")
        return r3.text

    async def close(self):
        await self.session.close()
