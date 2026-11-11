"""One async generator per scrape mode.

Every mode yields dataset records and never raises for a per-target failure:
a target that cannot be fetched becomes a diagnostic error row so downstream
joins always see a row for every input.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable

from .client import (
    NinetyNineChallengeWall,
    NinetyNineClient,
    NinetyNineNotFound,
)
from .constants import (
    DEFAULT_CONCURRENCY,
    DEFAULT_MAX_PAGES,
    HDB_MEDIAN_PATH,
    ID_DETAIL_PREFIX,
    ID_FILTER_PARAMS,
    ID_MAX_PAGE,
    ID_PAGE_PARAM,
    ID_ROOT,
    ID_SEARCH_PREFIXES,
    SG_PAGE_PARAM,
    SG_ROOT,
    SITE_ROOT,
)
from .parsers import (
    UnexpectedShape,
    envelope,
    error_record,
    id_is_404,
    parse_hdb_median,
    parse_id_detail,
    parse_id_locations,
    parse_id_search,
    parse_sg_detail,
    parse_sg_search,
)

log = logging.getLogger("ninetynine.modes")


# -- input normalisation ---------------------------------------------------


def _as_list(value: Any) -> list[str]:
    """Accept ["a"] and [{"url": "a"}] alike -- the Apify request-list editor
    emits the latter, a plain string array the former."""
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("url") or item.get("value") or item.get("slug")
        if item:
            out.append(str(item).strip())
    return out


def id_search_path(target: str) -> str:
    """Normalise an Indonesian search target to a site path.

    Accepts a full URL, "/id/jual/rumah", "jual/rumah", or a location slug as
    the locations facet emits it ("jual/rumah/bandung") -- users paste all of
    these, and the facet output is meant to be fed straight back in.
    """
    t = target.strip()
    if t.startswith("http"):
        t = "/" + t.split("99.co/", 1)[-1].lstrip("/")
    t = t.split("?", 1)[0].strip("/")
    if t.startswith("id/"):
        t = t[3:]
    if not t:
        raise ValueError("empty search target")
    head = t.split("/", 1)[0]
    if head not in ID_SEARCH_PREFIXES:
        raise ValueError(
            f"{target!r} does not start with one of {ID_SEARCH_PREFIXES} "
            f"(e.g. 'jual/rumah' or 'sewa/apartemen')"
        )
    return f"/id/{t}"


def sg_search_path(target: str) -> str:
    t = target.strip()
    if t.startswith("http"):
        t = "/" + t.split("99.co/", 1)[-1].lstrip("/")
    t = t.split("?", 1)[0].strip("/")
    if t.startswith("singapore/"):
        t = t[len("singapore/"):]
    if not t:
        t = "rent"
    return f"/singapore/{t}"


def _id_filter_params(actor_input: dict[str, Any]) -> dict[str, Any]:
    """Map friendly input names onto the Indonesian query parameters.

    Only parameters verified to reach pageProps.data.filter and move
    pagination.count are mapped; anything else would be accepted with HTTP 200
    and silently ignored.
    """
    params: dict[str, Any] = {}
    for friendly, actual in ID_FILTER_PARAMS.items():
        value = actor_input.get(friendly)
        if value not in (None, "", []):
            params[actual] = value
    return params


# -- Indonesia -------------------------------------------------------------


async def mode_id_search(
    client: NinetyNineClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    max_pages = min(
        int(actor_input.get("maxPages") or DEFAULT_MAX_PAGES), ID_MAX_PAGE
    )
    requested = int(actor_input.get("maxPages") or DEFAULT_MAX_PAGES)
    if requested > ID_MAX_PAGE:
        log.warning(
            "maxPages=%d exceeds the anonymous ceiling; Indonesian search is "
            "challenge-gated from page %d, so this run will stop at %d. To "
            "reach deeper inventory, narrow the query (a location slug from "
            "the idLocations mode, a price band, a bedroom count) so each "
            "slice fits inside %d pages.",
            requested, ID_MAX_PAGE + 1, ID_MAX_PAGE, ID_MAX_PAGE,
        )

    include_placements = bool(actor_input.get("includeProjectPlacements", True))
    max_items = int(actor_input.get("maxItemsPerTarget") or 0)
    base_params = _id_filter_params(actor_input)

    for target in _as_list(actor_input.get("idSearchTargets")):
        try:
            path = id_search_path(target)
        except ValueError as exc:
            yield error_record(target, "unparsable_input", str(exc), "S1-id-nextdata")
            continue

        log.info("ID search %s (filters=%s)", path, base_params or "none")
        seen: set[str] = set()
        emitted = 0
        referer = ID_ROOT
        meta: dict[str, Any] = {}
        stopped_early = False

        for page in range(1, max_pages + 1):
            params = dict(base_params)
            if page > 1:
                params[ID_PAGE_PARAM] = page
            try:
                final_url, body = await client.get_page(
                    path, params=params or None, referer=referer
                )
            except NinetyNineChallengeWall as exc:
                # Expected at page 10+, and possible earlier if the edge
                # tightens. It is a fact about reach, not a transport failure.
                log.warning("ID search %s hit the challenge wall at page %d", path, page)
                yield error_record(
                    target, "challenge_wall",
                    f"page {page}: {exc}", "S1-id-nextdata",
                )
                stopped_early = True
                break
            except NinetyNineNotFound as exc:
                yield error_record(target, "not_found", str(exc), "S1-id-nextdata")
                break
            except Exception as exc:  # noqa: BLE001 - one target must not kill the run
                yield error_record(
                    target, "fetch_failed", f"page {page}: {type(exc).__name__}: {exc}",
                    "S1-id-nextdata",
                )
                break

            if id_is_404(body):
                yield error_record(
                    target, "not_found",
                    f"{final_url} rendered the Indonesian 404 page",
                    "S1-id-nextdata",
                )
                break

            try:
                rows, meta = parse_id_search(body)
            except UnexpectedShape as exc:
                yield error_record(
                    target, "unexpected_shape", f"page {page}: {exc}", "S1-id-nextdata"
                )
                break

            if page == 1 and meta.get("totalCount"):
                log.info(
                    "%s: %s listings match; anonymous reach is %d pages "
                    "(~%d listings)",
                    target, meta["totalCount"], max_pages,
                    max_pages * (meta.get("pageSize") or 20),
                )

            fresh = [r for r in rows if r.get("id") and r["id"] not in seen]
            for r in fresh:
                seen.add(r["id"])
            if not fresh:
                log.info("%s: page %d added nothing new -- stopping", target, page)
                break

            for row in fresh:
                if not include_placements and row.get("groupType") == "primary":
                    continue
                if max_items and emitted >= max_items:
                    log.info("%s: reached maxItemsPerTarget=%d", target, max_items)
                    stopped_early = True
                    break
                yield envelope(
                    target, "S1-id-nextdata", "idListing",
                    {
                        **row,
                        "pageNumber": page,
                        "pageUrl": final_url,
                        "totalCount": meta.get("totalCount"),
                        "totalPagesReported": meta.get("totalPagesReported"),
                    },
                )
                emitted += 1
            if stopped_early:
                break
            referer = final_url

        total = meta.get("totalCount") or 0
        if not stopped_early and total > emitted and emitted:
            # Say plainly that the run saw only a slice, and how to get more.
            log.warning(
                "%s: emitted %d of %s matching listings. The rest is behind the "
                "%d-page anonymous ceiling -- split this query by location or "
                "price to reach it.",
                target, emitted, total, ID_MAX_PAGE,
            )
        if emitted == 0 and not stopped_early:
            yield error_record(
                target, "no_results", f"{path} matched nothing", "S1-id-nextdata"
            )


async def mode_id_listing_detail(
    client: NinetyNineClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    concurrency = int(actor_input.get("concurrency") or DEFAULT_CONCURRENCY)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(target: str) -> dict[str, Any]:
        slug = target.strip()
        if slug.startswith("http"):
            slug = slug.split("99.co/", 1)[-1]
        slug = slug.replace("id/properti/", "").strip("/")
        url = f"{SITE_ROOT}{ID_DETAIL_PREFIX}{slug}"
        async with semaphore:
            try:
                final_url, body = await client.get_page(url, referer=ID_ROOT)
            except NinetyNineNotFound as exc:
                return error_record(target, "not_found", str(exc), "S1-id-nextdata")
            except NinetyNineChallengeWall as exc:
                return error_record(target, "challenge_wall", str(exc), "S1-id-nextdata")
            except Exception as exc:  # noqa: BLE001
                return error_record(
                    target, "fetch_failed", f"{type(exc).__name__}: {exc}",
                    "S1-id-nextdata",
                )
            if id_is_404(body):
                return error_record(
                    target, "not_found",
                    f"{final_url} rendered the Indonesian 404 page",
                    "S1-id-nextdata",
                )
            try:
                record = parse_id_detail(body)
            except UnexpectedShape as exc:
                return error_record(
                    target, "unexpected_shape", str(exc), "S1-id-nextdata"
                )
            return envelope(
                target, "S1-id-nextdata", "idListingDetail",
                {**record, "pageUrl": final_url},
            )

    targets = _as_list(actor_input.get("idListingSlugs"))
    for coro in asyncio.as_completed([one(t) for t in targets]):
        yield await coro


async def mode_id_locations(
    client: NinetyNineClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Location facets, the seeds for getting past the 9-page ceiling."""
    targets = _as_list(actor_input.get("idSearchTargets")) or ["jual/rumah"]
    for target in targets:
        try:
            path = id_search_path(target)
        except ValueError as exc:
            yield error_record(target, "unparsable_input", str(exc), "S1-id-nextdata")
            continue
        try:
            final_url, body = await client.get_page(path, referer=ID_ROOT)
            locations = parse_id_locations(body)
        except Exception as exc:  # noqa: BLE001
            yield error_record(
                target, "fetch_failed", f"{type(exc).__name__}: {exc}",
                "S1-id-nextdata",
            )
            continue
        if not locations:
            yield error_record(
                target, "no_results", f"{path} exposed no location facets",
                "S1-id-nextdata",
            )
            continue
        log.info("%s: %d location facets", target, len(locations))
        for loc in locations:
            yield envelope(
                target, "S1-id-nextdata", "idLocation",
                {**loc, "pageUrl": final_url,
                 "searchUrl": f"{SITE_ROOT}/id/{loc['urlSlug']}" if loc.get("urlSlug") else None},
            )


# -- Singapore -------------------------------------------------------------


async def mode_sg_search(
    client: NinetyNineClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    max_pages = int(actor_input.get("maxPages") or DEFAULT_MAX_PAGES)
    max_items = int(actor_input.get("maxItemsPerTarget") or 0)

    for target in _as_list(actor_input.get("sgSearchTargets")):
        path = sg_search_path(target)
        log.info("SG search %s", path)
        seen: set[str] = set()
        emitted = 0
        referer = SG_ROOT
        meta: dict[str, Any] = {}
        stop = False

        for page in range(1, max_pages + 1):
            params = {SG_PAGE_PARAM: page} if page > 1 else None
            try:
                final_url, body = await client.get_page(
                    path, params=params, referer=referer
                )
            except NinetyNineNotFound as exc:
                yield error_record(target, "not_found", str(exc), "S1-sg-jsonld-rsc")
                break
            except NinetyNineChallengeWall as exc:
                yield error_record(
                    target, "challenge_wall", f"page {page}: {exc}", "S1-sg-jsonld-rsc"
                )
                break
            except Exception as exc:  # noqa: BLE001
                yield error_record(
                    target, "fetch_failed",
                    f"page {page}: {type(exc).__name__}: {exc}", "S1-sg-jsonld-rsc",
                )
                break

            try:
                rows, meta = parse_sg_search(body)
            except UnexpectedShape as exc:
                yield error_record(
                    target, "unexpected_shape", f"page {page}: {exc}",
                    "S1-sg-jsonld-rsc",
                )
                break

            if page == 1 and meta.get("totalCount"):
                log.info("%s: %s listings match", target, meta["totalCount"])

            # Singapore repeats a handful of promoted listings across pages,
            # so dedupe -- but never stop on a repeat-only page.
            fresh = [
                r for r in rows
                if r.get("listingId") and r["listingId"] not in seen
            ]
            for r in fresh:
                seen.add(r["listingId"])
            if not rows:
                log.info("%s: page %d is empty -- stopping", target, page)
                break
            if not fresh:
                log.info("%s: page %d was all repeats -- continuing", target, page)
                referer = final_url
                continue

            for row in fresh:
                if max_items and emitted >= max_items:
                    log.info("%s: reached maxItemsPerTarget=%d", target, max_items)
                    stop = True
                    break
                yield envelope(
                    target, "S1-sg-jsonld-rsc", "sgListing",
                    {
                        **row,
                        "pageNumber": page,
                        "pageUrl": final_url,
                        "totalCount": meta.get("totalCount"),
                    },
                )
                emitted += 1
            if stop:
                break
            referer = final_url

        if emitted == 0:
            yield error_record(
                target, "no_results", f"{path} matched nothing", "S1-sg-jsonld-rsc"
            )


async def mode_sg_listing_detail(
    client: NinetyNineClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    concurrency = int(actor_input.get("concurrency") or DEFAULT_CONCURRENCY)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(target: str) -> dict[str, Any]:
        url = target if target.startswith("http") else SITE_ROOT + "/" + target.lstrip("/")
        async with semaphore:
            try:
                final_url, body = await client.get_page(url, referer=SG_ROOT)
            except NinetyNineNotFound as exc:
                return error_record(target, "not_found", str(exc), "S1-sg-jsonld-rsc")
            except NinetyNineChallengeWall as exc:
                return error_record(
                    target, "challenge_wall", str(exc), "S1-sg-jsonld-rsc"
                )
            except Exception as exc:  # noqa: BLE001
                return error_record(
                    target, "fetch_failed", f"{type(exc).__name__}: {exc}",
                    "S1-sg-jsonld-rsc",
                )
            try:
                record = parse_sg_detail(body, final_url)
            except UnexpectedShape as exc:
                return error_record(
                    target, "unexpected_shape", str(exc), "S1-sg-jsonld-rsc"
                )
            return envelope(target, "S1-sg-jsonld-rsc", "sgListingDetail", record)

    targets = _as_list(actor_input.get("sgListingUrls"))
    for coro in asyncio.as_completed([one(t) for t in targets]):
        yield await coro


async def mode_sg_hdb_resale_prices(
    client: NinetyNineClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Median HDB resale prices per town, from 99.co's open JSON API."""
    try:
        payload = await client.get_json(
            HDB_MEDIAN_PATH, referer=f"{SG_ROOT}/hdb-resale-price"
        )
    except Exception as exc:  # noqa: BLE001
        yield error_record(
            HDB_MEDIAN_PATH, "fetch_failed", f"{type(exc).__name__}: {exc}",
            "S1-sg-api",
        )
        return
    try:
        rows = parse_hdb_median(payload)
    except UnexpectedShape as exc:
        yield error_record(
            HDB_MEDIAN_PATH, "unexpected_shape", str(exc), "S1-sg-api"
        )
        return
    log.info("HDB median resale prices: %d towns", len(rows))
    for row in rows:
        yield envelope(HDB_MEDIAN_PATH, "S1-sg-api", "sgHdbMedianPrice", row)


MODES: dict[str, Callable[..., AsyncIterator[dict[str, Any]]]] = {
    "idSearch": mode_id_search,
    "idListingDetail": mode_id_listing_detail,
    "idLocations": mode_id_locations,
    "sgSearch": mode_sg_search,
    "sgListingDetail": mode_sg_listing_detail,
    "sgHdbResalePrices": mode_sg_hdb_resale_prices,
}

MODE_REQUIRED_INPUT: dict[str, str] = {
    "idSearch": "idSearchTargets",
    "idListingDetail": "idListingSlugs",
    "sgSearch": "sgSearchTargets",
    "sgListingDetail": "sgListingUrls",
}
