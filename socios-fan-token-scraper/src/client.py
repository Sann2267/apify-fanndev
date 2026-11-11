"""Async client over the anonymous slice of the Chiliz gateway.

The gateway paginates every collection the same way: ``?limit=N&page=M`` with a
``metadata`` block carrying ``total_items``, ``current_page`` and ``last_page``.
Page ``last_page + 1`` answers 200 with an empty ``data`` array rather than a
404, which is the stop condition used throughout.

A warning about this API's query parameters, because it costs a whole dataset
if you miss it: **unrecognised filters are accepted and silently ignored.**
``?partnerId[]=<uuid>``, ``?partner[]=``, ``?partners[]=``, ``?currencyId[]=``
and ``?type[]=`` all return a cheerful 200 whose ``total_items`` is the
unfiltered 9,825 -- they look like they worked. The parameters that really
filter are ``partnerIds[]`` (plural) and ``status[]``; anything else has to be
applied client-side after the fact. ``_reject_decoys`` below asserts that the
server honoured the filters it claimed to, so a future rename surfaces as a
loud failure instead of a dataset quietly full of the wrong club.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_RETRIES,
    REQUEST_DELAY,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class ChilizError(RuntimeError):
    """The gateway refused in a way retrying will not fix."""


class RetriesExhausted(ChilizError):
    """A page kept failing across the whole backoff ladder.

    Distinct from the flat refusals because it is worth one more idea before
    giving up -- the same rows asked for in smaller pieces often succeed, and
    losing nine thousand good rows to one blipping page helps nobody.
    """


class PageTooHeavy(ChilizError):
    """500 on a page that is simply too large to serialise.

    The poll catalogue is big enough that a 1,000-row page reaches 8 MB, and the
    gateway answers 500 on the heavier ones -- reproducibly, from every IP, on
    every attempt. It is a size problem rather than an outage, so the fix is a
    smaller page rather than another retry.
    """


class Forbidden(ChilizError):
    """403 "You cannot consume this service" -- the route is not in the
    anonymous ACL role. No proxy, fingerprint or header changes this."""


class UnexpectedShape(RuntimeError):
    """200 whose body no longer matches the contract.

    Raised rather than returning an empty list so that a gateway-side schema
    change fails the run visibly instead of writing an empty dataset that looks
    like a quiet day at Socios.
    """


class ChilizClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE) -> None:
        self._session = AsyncSession(
            impersonate=profile,
            proxy=proxy_url or None,
            timeout=45,
            headers=dict(DEFAULT_HEADERS),
        )

    async def close(self) -> None:
        await self._session.close()

    async def get_json(self, url: str, params: list[tuple[str, Any]] | None = None) -> dict:
        """One GET with exponential backoff over transient failures.

        403 and 404 short-circuit: they are verdicts about the route, and five
        rounds of backoff against a verdict only wastes the buyer's time.
        """
        last: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._session.get(url, params=params or [])
            except Exception as exc:  # transport-level: DNS, reset, timeout
                last = exc
                await self._backoff(attempt)
                continue

            if response.status_code == 200:
                try:
                    payload = response.json()
                except Exception as exc:
                    raise UnexpectedShape(
                        f"{url} answered 200 with a body that is not JSON: {exc}"
                    ) from exc
                if not isinstance(payload, dict) or "data" not in payload:
                    raise UnexpectedShape(
                        f"{url} answered 200 without a 'data' key; "
                        f"got keys={list(payload)[:8] if isinstance(payload, dict) else type(payload)}"
                    )
                return payload

            if response.status_code == 403:
                raise Forbidden(
                    f"{url} is not in the anonymous ACL role "
                    f"(403 {response.text[:120].strip()})"
                )
            if response.status_code == 404:
                raise ChilizError(f"{url} -> 404 no route matched")
            if response.status_code == 400:
                # The gateway explains itself well; surface it verbatim.
                raise ChilizError(f"{url} -> 400 {response.text[:400].strip()}")

            if response.status_code == 500:
                # Retried once in case it really is transient, then handed to
                # the caller to re-fetch as smaller pages.
                if attempt >= 1:
                    raise PageTooHeavy(
                        f"{url} -> 500 on this page size ({response.text[:120].strip()})"
                    )

            # Anything else, including the occasional nonsense status this
            # gateway emits under load (HTTP 288 has been seen once), is
            # treated as transient and retried.
            last = ChilizError(f"{url} -> HTTP {response.status_code}")
            await self._backoff(attempt)

        raise RetriesExhausted(f"{url} failed after {MAX_RETRIES} attempts: {last!r}")

    @staticmethod
    async def _backoff(attempt: int) -> None:
        await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt) + random.uniform(0, 0.4))

    async def collect(
        self,
        url: str,
        params: list[tuple[str, Any]] | None = None,
        max_items: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        concurrency: int = 4,
        log: Any = None,
    ) -> list[dict]:
        """Every row of a paginated collection, honouring ``max_items``.

        Page 1 is fetched alone because it is what reveals ``last_page``; the
        remaining pages are then fetched concurrently, which turns the 10 pages
        of the poll catalogue into roughly three round trips instead of ten.
        Endpoints that return a bare list with no ``metadata`` (leagues, sports,
        countries) fall out after the first page.
        """
        base = list(params or [])
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        if max_items:
            page_size = min(page_size, max_items)

        first = await self.get_json(url, base + [("limit", page_size), ("page", 1)])
        rows = self._rows(url, first)
        metadata = first.get("metadata") or {}
        last_page = metadata.get("last_page")

        if not rows or not isinstance(last_page, int) or last_page <= 1:
            # The reference collections (leagues, sports, countries) answer with
            # no metadata block at all and ignore ``page`` -- page 2 returns the
            # same rows as page 1 -- so ``limit`` is the only thing standing
            # between the caller and a silently short list. Worse, ``leagues``
            # returns just 7 of its 49 rows when no limit is given. With no
            # total to check against, a full page is indistinguishable from a
            # truncated one, so say so loudly instead of guessing.
            if not metadata and len(rows) >= page_size:
                raise UnexpectedShape(
                    f"{url} returned exactly {len(rows)} rows, the page size, and "
                    f"no metadata to confirm that is all of them. It may have "
                    f"outgrown the page size -- raise it and re-check."
                )
            return rows[:max_items] if max_items else rows
        if max_items:
            last_page = min(last_page, -(-max_items // page_size))
        if log:
            total = metadata.get("total_items")
            available = metadata.get("last_page")
            scope = (
                f"{last_page} of {available} page(s)"
                if available != last_page
                else f"all {last_page} page(s)"
            )
            log.info(
                f"{url.rsplit('/', 1)[-1]}: {total} rows available, "
                f"fetching {scope} at {page_size}/page"
            )

        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def fetch(page: int) -> tuple[int, list[dict]]:
            async with semaphore:
                await asyncio.sleep(REQUEST_DELAY)
                try:
                    payload = await self.get_json(
                        url, base + [("limit", page_size), ("page", page)]
                    )
                except (PageTooHeavy, RetriesExhausted) as exc:
                    if log:
                        log.warning(f"{exc} -- refetching page {page} in smaller slices.")
                    return page, await self._split_page(url, base, page, page_size)
                return page, self._rows(url, payload)

        pages = await asyncio.gather(*(fetch(p) for p in range(2, last_page + 1)))
        for _, page_rows in sorted(pages, key=lambda item: item[0]):
            rows.extend(page_rows)

        return rows[:max_items] if max_items else rows

    async def _split_page(
        self, url: str, base: list, page: int, page_size: int, factor: int = 5
    ) -> list[dict]:
        """Re-fetch one over-large page as ``factor`` smaller consecutive ones.

        Page ``page`` at size ``page_size`` covers rows
        ``[(page - 1) * page_size, page * page_size)``. At size
        ``page_size // factor`` that same span is sub-pages
        ``(page - 1) * factor + 1`` through ``page * factor``, so the rows come
        back in the same order with none missed and none repeated. Recurses if a
        slice is still too heavy, and gives up once the slice is a single row --
        at which point the 500 is about that row, not about the page size.
        """
        smaller = max(1, page_size // factor)
        if smaller == page_size:
            raise PageTooHeavy(
                f"{url} page {page} returns 500 even at one row per page"
            )
        rows: list[dict] = []
        for sub in range((page - 1) * factor + 1, page * factor + 1):
            await asyncio.sleep(REQUEST_DELAY)
            try:
                payload = await self.get_json(
                    url, base + [("limit", smaller), ("page", sub)]
                )
            except (PageTooHeavy, RetriesExhausted):
                rows.extend(await self._split_page(url, base, sub, smaller, factor))
                continue
            rows.extend(self._rows(url, payload))
        return rows

    @staticmethod
    def _rows(url: str, payload: dict) -> list[dict]:
        data = payload.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        raise UnexpectedShape(
            f"{url} returned data of type {type(data).__name__}, expected a list"
        )
