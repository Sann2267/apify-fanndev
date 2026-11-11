"""HTTP client for the Companies Office of Jamaica's `CompanySearch.aspx`
flow: cookie warmup -> WebForms postback search -> async job poll ->
results page. See `constants.py` for the full recon summary.

The retry loop wraps ALL request calls in a broad `except Exception`, same
fix documented in the Botswana CIPA actor's `client.py`: `curl_cffi`'s own
exception hierarchy (`CurlError` -> `OSError`) does NOT inherit from
Python's builtin `ConnectionError`/`TimeoutError` despite sharing class
names, so a narrower except list silently misses real transient failures
and lets them crash the whole run instead of retrying/degrading to a
per-item error record.
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    POLL_INTERVAL_SECS,
    POLL_MAX_ATTEMPTS,
    RETRY_DELAY_BASE_SECS,
    SEARCH_URL,
    TLS_PROFILE,
)
from src.extractor import (
    NoResultsFound,
    extract_database_blob,
    extract_hidden_field,
    extract_redirect_target,
    extract_search_rows,
)


def is_blocked(response) -> bool:
    """403 here is the Zenedge "HIC" rate-limit block observed during recon
    (body markers in `constants.BLOCK_MARKERS`) -- transient, recovers on
    its own within roughly 60-120s. 429/503 are the generic rate-limit/
    unavailable signals. All three are treated as retryable, not fatal."""
    return response.status_code in (403, 429, 503)


class COJClient:
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
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    delay = RETRY_DELAY_BASE_SECS * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE_SECS * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {method} {url}: {last_exc!r}")

    async def get(self, url: str, **kwargs):
        return await self._with_retry("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self._with_retry("POST", url, **kwargs)

    async def _warmup_and_fetch_form(self) -> str:
        """Two GETs of the same URL in one session: the first trips the
        (non-JS, non-blocking) `AspxAutoDetectCookieSupport` cookie probe,
        the second returns the real page with a fresh `__VIEWSTATE`/
        `__EVENTVALIDATION` pair. See constants.py recon summary."""
        await self.get(SEARCH_URL)
        r = await self.get(SEARCH_URL)
        if r.status_code != 200:
            raise RuntimeError(f"GET {SEARCH_URL} (warm) -> HTTP {r.status_code}")
        return r.text

    async def search(self, query: str) -> list[dict]:
        """Run one full search flow and return the raw matched-entity rows
        (upstream's own field names, unmodified). Raises `NoResultsFound`
        for a legitimate zero-match search."""
        form_html = await self._warmup_and_fetch_form()
        viewstate = extract_hidden_field("__VIEWSTATE", form_html)
        viewstate_gen = extract_hidden_field("__VIEWSTATEGENERATOR", form_html)
        event_validation = extract_hidden_field("__EVENTVALIDATION", form_html)
        if not viewstate or not event_validation:
            raise RuntimeError("Could not extract __VIEWSTATE/__EVENTVALIDATION from search page")

        post_data = {
            "__LASTFOCUS": "",
            "__EVENTTARGET": "ctl00$Space$btnSearch",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstate_gen or "",
            "__SCROLLPOSITIONX": "0",
            "__SCROLLPOSITIONY": "0",
            "__EVENTVALIDATION": event_validation,
            "ctl00$Space$org_name": query,
            "ctl00$Timezone": "",
        }
        r = await self.post(SEARCH_URL, data=post_data)
        if r.status_code != 200:
            raise RuntimeError(f"POST {SEARCH_URL} -> HTTP {r.status_code}")
        redirect_url = extract_redirect_target(r.text)
        if not redirect_url:
            raise RuntimeError(f"No redirect target in search POST response: {r.text[:300]!r}")

        # PaymentConfirmation.aspx?cId1=... -- a generic async-job "processing"
        # page, not a paywall (see constants.py). Hit it once to prime the
        # job (already primed by the warmup cookies), then read it for the
        # async job id / poll URL / result controller.
        await self.get(redirect_url)
        confirm_html = (await self.get(redirect_url)).text
        job_id = extract_hidden_field("ctl00_Space_Response", confirm_html)
        poll_url = extract_hidden_field("ctl00_Space_PollURL", confirm_html)
        result_ctrl = extract_hidden_field("ctl00_Space_ResultUiController", confirm_html)
        if not job_id or not poll_url or not result_ctrl:
            raise RuntimeError("Could not extract async job id / poll URL / result controller")

        state = await self._poll_job(poll_url, job_id)
        if state != "Succeeded":
            raise RuntimeError(f"Async search job ended in state {state!r}, expected 'Succeeded'")

        final_url = f"{result_ctrl}&asyncId={job_id}"
        results_r = await self.get(final_url)
        if results_r.status_code != 200:
            raise RuntimeError(f"GET {final_url} -> HTTP {results_r.status_code}")
        database = extract_database_blob(results_r.text)
        return extract_search_rows(database)  # raises NoResultsFound if empty

    async def _poll_job(self, poll_url: str, job_id: str) -> str:
        poll_endpoint = f"{poll_url}asyncState/{job_id}"
        for _ in range(POLL_MAX_ATTEMPTS):
            r = await self.post(poll_endpoint, headers={"Content-Type": "application/json"})
            if r.status_code != 200 or not r.content:
                raise RuntimeError(f"POST {poll_endpoint} -> HTTP {r.status_code}, empty={not r.content}")
            payload = r.json()
            state = payload.get("CurrentState")
            if state == "Succeeded":
                return state
            if state in ("Failed",):
                error_detail = payload.get("Error")
                raise RuntimeError(f"Async job failed: {error_detail!r}")
            await asyncio.sleep(POLL_INTERVAL_SECS)
        raise RuntimeError(f"Async job did not reach 'Succeeded' after {POLL_MAX_ATTEMPTS} polls")

    async def close(self):
        await self.session.close()
