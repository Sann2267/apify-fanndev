"""HTTP client for bolpatra.gov.np (Nepal's national e-GP portal).

Unlike most sibling scrapers in this collection's tender vertical (e.g.
`ghana-tenders-scraper`, all-GET, fully stateless), this site's listing
search is a stateful Struts2 form POST: a plain GET of `/searchOpportunity`
establishes a `JSESSIONID` before the search POST. This does not
deterministically change the row count returned (see constants.py -- the
site's own row count per query is flaky, 10 or 30, independent of
anything observed on the request side) but it mirrors what a real browser
session does and is cheap, so this client always primes first anyway.
`curl_cffi`'s `AsyncSession` keeps cookies automatically across requests
made on the same session object, so one session per logical run of "warm
up, then search or fetch details" is enough; there's no need for a manual
cookie jar.

No CAPTCHA, no WAF challenge, no TLS-fingerprint gate observed anywhere on
this host during recon -- plain `curl` (no TLS impersonation at all) got
clean 200s throughout (as long as a User-Agent header is sent -- a bare
UA-less request gets a flat nginx 403, unrelated to TLS). `curl_cffi`
`chrome124` is used anyway for portfolio-wide consistency.

**TLS gotcha, same class of bug as `nepal-ocr-scraper`'s
`camis.ocr.gov.np`:** `bolpatra.gov.np` serves only its leaf certificate,
not the DigiCert intermediate (`DigiCert Global G2 TLS RSA SHA256 2020
CA1`) needed to complete the chain. A client that does OS-level chain
building/AIA-fetching (Windows `schannel`-backed `curl`, browsers) accepts
it silently; `curl_cffi`'s bundled OpenSSL cert store does not and fails
every request with `CertificateVerifyError: unable to get local issuer
certificate` until `verify=False` is set explicitly. Confirmed this is a
server misconfiguration, not a local/proxy artifact (identical failure
from a clean residential connection with no proxy in the loop).
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    DASHBOARD_URL,
    DEFAULT_HEADERS,
    DETAIL_URL,
    ENTITY_AUTOCOMPLETE_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    SEARCH_PAGE_URL,
    SEARCH_RESULT_URL,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A request never produced a usable 200 response after retries."""


class BolpatraClient:
    """One session per logical unit of work (one search, or one batch of
    detail fetches) -- stateless between separate `search()`/`latest()`
    calls is fine since each call primes its own session first."""

    def __init__(self, proxy_url: str | None = None):
        self.session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
            # bolpatra.gov.np serves an incomplete certificate chain (missing
            # intermediate) -- see module docstring. No workaround short of
            # skipping verification.
            verify=False,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._primed = False

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code != 200:
                    raise FetchFailed(f"{method} {url} -> HTTP {r.status_code}: {r.text[:300]!r}")
                return r
            except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
                # NOTE: curl_cffi's own ConnectionError/RequestException does
                # NOT inherit from Python's builtin ConnectionError -- its MRO
                # is RequestException -> CurlError -> OSError, a parallel
                # hierarchy. Both listed, per this project's portfolio-wide
                # Babak 22b fix.
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {method} {url!r}: {last_exc!r}")

    async def _prime_session(self):
        """One GET of the search page to establish a JSESSIONID. Required
        for the 30-row (vs. 10-row) response on a keyword search -- see
        constants.py. Idempotent per client instance."""
        if self._primed:
            return
        await self._with_retry("GET", SEARCH_PAGE_URL)
        self._primed = True

    async def fetch_latest(self) -> str:
        """The homepage's 'recent opportunities' dashboard -- always the 30
        most-recently-published tenders, no filters, works fully cold."""
        r = await self._with_retry("POST", DASHBOARD_URL)
        return r.text

    async def search(self, form_fields: dict) -> str:
        """A filtered search. Primes the session first (see above)."""
        await self._prime_session()
        r = await self._with_retry("POST", SEARCH_RESULT_URL, data=form_fields)
        return r.text

    async def resolve_entity_id(self, term: str) -> tuple[str, str] | None:
        """Resolves a free-text public-entity name to bolpatra's internal
        numeric id via its public autocomplete endpoint. Returns
        (id, matched_name) for the first suggestion, or None if there were
        no suggestions at all."""
        r = await self._with_retry("GET", ENTITY_AUTOCOMPLETE_URL, params={"term": term})
        try:
            suggestions = r.json()
        except ValueError as e:
            raise FetchFailed(f"Non-JSON response from {ENTITY_AUTOCOMPLETE_URL}: {e!r} body={r.text[:300]!r}") from e
        if not suggestions:
            return None
        first = suggestions[0]
        return str(first.get("id")), (first.get("name") or "").strip()

    async def fetch_detail(self, tender_id: str) -> str:
        r = await self._with_retry("GET", DETAIL_URL, params={"tenderId": tender_id})
        return r.text

    async def close(self):
        await self.session.close()
