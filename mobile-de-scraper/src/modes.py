"""The seven things this actor can pull off mobile.de.

One actor with a `mode` switch rather than seven actors, because every mode
talks to the same service behind the same TLS gate, and the useful runs cross
between them: a search yields `sellerId`s that `dealer_inventory` expands, and
ad ids that `detail` and `dealer_contact` enrich. Splitting them would mean
re-establishing the same session in seven places and would make those
cross-mode runs impossible inside a single dataset.

    search             listings for a filter set or a pasted mobile.de URL
    detail             the full vehicle page for an ad (description, features)
    dealer_inventory   every listing a seller currently has online
    dealer_contact     a seller's imprint -- name, address, phone, HRB, VAT id
    similar_ads        mobile.de's own "similar vehicles" for an ad
    market_count       result counts only, for sizing a market cheaply
    reference_data     the make/model tree and every filter's allowed values
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import Any, Callable

from .client import (
    MobileDeBadRequest,
    MobileDeClient,
    MobileDeError,
    MobileDeNotFound,
)
from .constants import MAX_OFFSET, MAX_RESULTS_PER_QUERY
from .parsers import (
    FilterError,
    clamp_page_size,
    dedupe_listings,
    flatten_model_options,
    describe_dropped_filters,
    is_canonical_search_path,
    rebuild_canonical_path,
    error_record,
    flatten_items,
    listing_url,
    normalise_page_url,
    record,
)

log = logging.getLogger("mobilede.modes")

MODES = (
    "search",
    "detail",
    "dealer_inventory",
    "dealer_contact",
    "similar_ads",
    "market_count",
    "reference_data",
)

# Which input each mode needs before it can do anything.
MODE_REQUIRED_INPUT: dict[str, str] = {
    "search": "searchUrls, or filters (make/model/vehicleCategory/...)",
    "detail": "adIds or adUrls",
    "dealer_inventory": "sellerIds",
    "dealer_contact": "adIds or adUrls",
    "similar_ads": "adIds or adUrls",
    "market_count": "searchUrls, or filters",
    "reference_data": "vehicleCategory (defaults to Car)",
}


class Budget:
    """Shared item cap across every target in a run."""

    def __init__(self, max_items: int | None) -> None:
        self.max_items = max_items if max_items and max_items > 0 else None
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.max_items is not None and self.used >= self.max_items

    def remaining(self, want: int) -> int:
        if self.max_items is None:
            return want
        return max(0, min(want, self.max_items - self.used))

    def take(self, count: int) -> None:
        self.used += count


Emit = Callable[[dict[str, Any]], Any]


# --- search -----------------------------------------------------------------


async def fetch_srp(
    client: MobileDeClient, page_path: str, offset: int, page_size: int
) -> dict[str, Any]:
    """One search request. Returns the whole SRP envelope.

    Paging is done with `ps` (item offset) and NOT with the `page` parameter.
    `page` advances by a fixed 20 rows regardless of `psz`, so `page=2` with
    `psz=100` re-delivers 80 rows you already have. `ps` is a true offset and
    overlaps by nothing -- measured across a 10-request sweep: 2,039 rows,
    zero duplicates.
    """
    sep = "&" if "?" in page_path else "?"
    paged = f"{page_path}{sep}psz={page_size}&ps={offset}"
    return await client.get_json("search/srp", {"url": paged})


async def run_search(
    client: MobileDeClient,
    emit: Emit,
    page_path: str,
    *,
    budget: Budget,
    page_size: int,
    label: str,
    mode: str = "search",
    parent_id: Any = None,
) -> int:
    """Walk one query to its end (or the budget's, or mobile.de's ~2,000 cap).

    A pasted URL that is not `/fahrzeuge/search.html` is normalised first,
    because only that dialect honours the paging parameters -- see
    `parsers.rebuild_canonical_path`. That costs one extra request, and only
    for pasted URLs.
    """
    page_size = clamp_page_size(page_size)

    if not is_canonical_search_path(page_path):
        probe = await client.get_json("search/srp", {"url": page_path})
        canonical = rebuild_canonical_path(
            probe.get("sanitizedFilterParamsString")
        )
        if canonical:
            log.info(
                "[%s] %s does not honour mobile.de's paging parameters; "
                "replaying its filters as %s",
                label, page_path, canonical,
            )
            page_path = canonical
        else:
            log.warning(
                "[%s] %s is not a canonical search URL and mobile.de echoed no "
                "filters for it, so it cannot be paged. Returning the single "
                "page it serves.",
                label, page_path,
            )

    seen: set[str] = set()
    offset = 0
    rank = 0
    total_reported: int | None = None
    emitted = 0

    while True:
        if budget.exhausted:
            log.info("[%s] item budget reached", label)
            break
        if offset > MAX_OFFSET:
            log.warning(
                "[%s] hit mobile.de's result-depth ceiling at %s rows. The query "
                "reports %s matches, but offsets past %s return nothing. Narrow "
                "the query (price band, registration year, single model, postcode "
                "radius) and run the slices to go deeper.",
                label, len(seen), total_reported, MAX_OFFSET,
            )
            break

        payload = await fetch_srp(client, page_path, offset, page_size)
        results = payload.get("searchResults") or {}

        if total_reported is None:
            total_reported = results.get("numResultsTotal")
            dropped = describe_dropped_filters(
                page_path, payload.get("sanitizedFilterParamsString")
            )
            if dropped:
                log.warning(
                    "[%s] mobile.de IGNORED these filters: %s. It applied only "
                    "'%s'. The rows below are the broader result set, not what "
                    "was asked for.",
                    label, ", ".join(dropped),
                    payload.get("sanitizedFilterParamsString"),
                )
            log.info(
                "[%s] %s matches; %s reachable through pagination",
                label,
                total_reported,
                min(total_reported or 0, MAX_RESULTS_PER_QUERY),
            )
            # Page 1 also carries facet counts and metadata that no other
            # endpoint exposes -- worth one row per query.
            await emit(
                record(
                    "search_summary",
                    results.get("searchId"),
                    {
                        "numResultsTotal": total_reported,
                        "reachableTotal": min(
                            total_reported or 0, MAX_RESULTS_PER_QUERY
                        ),
                        "appliedFilters": payload.get("sanitizedFilterParamsString"),
                        "droppedFilters": dropped,
                        "isSeoSrp": payload.get("isSeoSrp"),
                        "aggregations": payload.get("aggregations"),
                        "metaData": payload.get("metaData"),
                    },
                    mode=mode,
                    source_url=f"https://suchen.mobile.de{page_path}",
                    query=label,
                    parent_id=parent_id,
                )
            )

        items = flatten_items(results.get("items"))
        fresh = dedupe_listings(items, seen)

        if not fresh:
            # hasNextPage stays true past the ceiling, so it is never the stop
            # condition -- an empty/all-duplicate page is.
            log.info("[%s] no new rows at offset %s; done", label, offset)
            break

        allowed = budget.remaining(len(fresh))
        for item in fresh[:allowed]:
            rank += 1
            seen.add(str(item.get("id")))
            await emit(
                record(
                    "listing",
                    item.get("id"),
                    item,
                    mode=mode,
                    source_url=listing_url(item),
                    query=label,
                    rank=rank,
                    offset=offset,
                    parent_id=parent_id,
                )
            )
        budget.take(min(allowed, len(fresh)))
        emitted += min(allowed, len(fresh))

        if allowed < len(fresh):
            break
        if total_reported is not None and len(seen) >= total_reported:
            break
        offset += page_size

    log.info("[%s] emitted %s listings", label, emitted)
    return emitted


# --- per-ad modes -----------------------------------------------------------


def ad_path(ad_ref: str) -> str:
    """Accept an ad id or any mobile.de ad URL and return the API's `url` value."""
    ref = str(ad_ref).strip()
    if ref.isdigit():
        return f"/fahrzeuge/details.html?id={ref}"
    path = normalise_page_url(ref)
    # A pasted detail URL carries refId/searchId from whoever copied it; the
    # API accepts them but they are someone else's session, so strip to the id.
    parsed = urllib.parse.urlsplit(path)
    ad_id = urllib.parse.parse_qs(parsed.query).get("id", [None])[0]
    if ad_id:
        return f"/fahrzeuge/details.html?id={ad_id}"
    return path


def ad_id_of(ad_ref: str) -> str | None:
    ref = str(ad_ref).strip()
    if ref.isdigit():
        return ref
    query = urllib.parse.urlsplit(normalise_page_url(ref)).query
    found = urllib.parse.parse_qs(query).get("id", [None])[0]
    if found:
        return found
    # SEO ad URLs end in /<id>.html
    tail = urllib.parse.urlsplit(ref).path.rstrip("/").split("/")[-1]
    stem = tail[:-5] if tail.endswith(".html") else tail
    return stem if stem.isdigit() else None


async def run_detail(
    client: MobileDeClient, emit: Emit, ad_ref: str, *, budget: Budget
) -> int:
    path = ad_path(ad_ref)
    payload = await client.get_json("search/vip", {"url": path})
    ad = payload.get("ad")
    if not ad:
        await emit(
            error_record(
                "empty_payload",
                "search/vip returned 200 with no 'ad' object",
                mode="detail",
                input_value=ad_ref,
                source_url=f"https://suchen.mobile.de{path}",
            )
        )
        return 0
    await emit(
        record(
            "listing_detail",
            ad.get("id"),
            {**ad, "ratings": payload.get("ratings")},
            mode="detail",
            source_url=f"https://suchen.mobile.de{path}",
            query=str(ad_ref),
        )
    )
    budget.take(1)
    return 1


async def run_dealer_contact(
    client: MobileDeClient, emit: Emit, ad_ref: str, *, budget: Budget
) -> int:
    """The seller's legal imprint, which is only reachable per-ad.

    mobile.de has no "dealer profile" endpoint. The imprint -- company name,
    street address, phone, Handelsregister number, VAT id, named directors --
    hangs off an ad id, so a dealer is identified by picking any one of their
    ads. It arrives as one pre-formatted German text block, passed through
    verbatim rather than guessed apart into fields.
    """
    ad_id = ad_id_of(ad_ref)
    if not ad_id:
        await emit(
            error_record(
                "unsupported_input",
                f"Could not find an ad id in {ad_ref!r}",
                mode="dealer_contact",
                input_value=ad_ref,
            )
        )
        return 0
    payload = await client.get_json(f"search/vip/ad-contact/{ad_id}")
    await emit(
        record(
            "dealer_contact",
            ad_id,
            payload,
            mode="dealer_contact",
            source_url=f"https://suchen.mobile.de/fahrzeuge/details.html?id={ad_id}",
            query=str(ad_ref),
        )
    )
    budget.take(1)
    return 1


async def run_similar_ads(
    client: MobileDeClient, emit: Emit, ad_ref: str, *, budget: Budget
) -> int:
    """mobile.de's own "similar vehicles" set for an ad.

    The link is not constructible -- it is handed out inside the ad payload as
    `similarAdsInfo.apiParams` (an /ml-recommendations-by-id/<id> path) -- so
    this mode fetches the ad first.

    `formatSimilarAds` is deliberately NOT sent, because the two forms return
    genuinely different schemas and the unformatted one carries more. It
    shares only about half its fields with an ordinary search listing -- price
    arrives as `p` rather than `price`, and it adds `created`, `modified`,
    `hasDamage`, `makeId`/`modelId` and `images`, which search rows do not
    have. That is why these rows are emitted as `similar_listing` and not
    folded in with `listing`.
    """
    path = ad_path(ad_ref)
    vip = await client.get_json("search/vip", {"url": path})
    ad = vip.get("ad") or {}
    info = ad.get("similarAdsInfo") or {}
    link = info.get("apiParams") or info.get("similarAdsLink") or info.get("link")
    if not link:
        await emit(
            error_record(
                "no_similar_ads",
                "This ad carries no similarAdsInfo link",
                mode="similar_ads",
                input_value=ad_ref,
                source_url=f"https://suchen.mobile.de{path}",
            )
        )
        return 0
    payload = await client.get_json(
        "search/vip/similar-ads", {"similarAdsLink": link}
    )
    items = flatten_items(payload.get("items") or payload.get("ads"))
    count = 0
    for rank, item in enumerate(items, start=1):
        if budget.exhausted:
            break
        await emit(
            record(
                "similar_listing",
                item.get("id"),
                item,
                mode="similar_ads",
                source_url=listing_url(item),
                query=str(ad_ref),
                rank=rank,
                parent_id=ad.get("id"),
            )
        )
        budget.take(1)
        count += 1
    log.info("[similar_ads %s] %s rows", ad_ref, count)
    return count


# --- counts and reference data ---------------------------------------------


async def run_market_count(
    client: MobileDeClient, emit: Emit, page_path: str, *, label: str, budget: Budget
) -> int:
    """Result count for a filter set -- one request, no listings.

    This is the cheap way to size a market: how many diesel Golfs under
    15,000 EUR exist, per postcode, per year. `search/hit-count` takes the
    filters directly as query parameters rather than a page URL.

    Which is exactly why a pasted URL has to be normalised first. An SEO URL
    like `/auto/bmw-3er-reihe.html` carries its filters in the PATH, so
    reading the query string off it yields no filters at all -- and
    `hit-count` with no filters happily returns the whole-site total (1.57
    million) as though it were the answer. So a non-canonical path is probed
    through `search/srp` and its echoed filters used instead.
    """
    path = page_path
    if not is_canonical_search_path(path):
        probe = await client.get_json("search/srp", {"url": path})
        canonical = rebuild_canonical_path(probe.get("sanitizedFilterParamsString"))
        if canonical:
            log.info("[%s] resolved %s -> %s", label, path, canonical)
            path = canonical
        else:
            log.warning(
                "[%s] %s carries no filters mobile.de recognises; the count "
                "below is for the whole %s marketplace.",
                label, path, "site",
            )

    filters = dict(
        urllib.parse.parse_qsl(
            urllib.parse.urlsplit(path).query, keep_blank_values=True
        )
    )
    for telemetry in ("ps", "psz", "ref", "refId"):
        filters.pop(telemetry, None)
    payload = await client.get_json("search/hit-count", filters)
    await emit(
        record(
            "market_count",
            None,
            {
                "count": payload.get("count"),
                "filters": filters,
                "resolvedFrom": page_path if path != page_path else None,
            },
            mode="market_count",
            source_url=f"https://suchen.mobile.de{path}",
            query=label,
        )
    )
    budget.take(1)
    return 1


async def run_reference_data(
    client: MobileDeClient, emit: Emit, vehicle_category: str, *, budget: Budget
) -> int:
    """Every filter's allowed values, plus the model tree for each make.

    This is what turns a human request ("BMW 3 Series") into the `ms=3500;21;;`
    the API needs, and it is the only place the make and model ids are
    published.
    """
    filters = await client.get_json(
        f"search/reference-data/filters/{vehicle_category}"
    )
    data = filters.get("data") or {}
    await emit(
        record(
            "reference_filters",
            vehicle_category,
            data,
            mode="reference_data",
            query=vehicle_category,
        )
    )
    budget.take(1)
    count = 1

    makes = data.get("ms") or []
    log.info("[reference_data] %s makes for %s", len(makes), vehicle_category)
    for make in makes:
        if budget.exhausted:
            break
        make_id = make.get("i")
        if make_id is None:
            continue
        try:
            models = await client.get_json(
                f"search/reference-data/models/{make_id}"
            )
        except (MobileDeNotFound, MobileDeError) as exc:
            await emit(
                error_record(
                    "fetch_failed",
                    f"models/{make_id}: {type(exc).__name__}: {exc}",
                    mode="reference_data",
                    input_value=make.get("n"),
                )
            )
            continue
        await emit(
            record(
                "reference_make",
                make_id,
                {
                    "makeId": make_id,
                    "makeName": make.get("n"),
                    "vehicleCategory": vehicle_category,
                    "models": models.get("data"),
                    "modelOptions": flatten_model_options(make_id, models.get("data")),
                    "msExample": f"{make_id};;;",
                },
                mode="reference_data",
                query=vehicle_category,
                parent_id=vehicle_category,
            )
        )
        budget.take(1)
        count += 1
    return count


# --- dealer inventory -------------------------------------------------------


async def run_dealer_inventory(
    client: MobileDeClient,
    emit: Emit,
    seller_id: Any,
    *,
    budget: Budget,
    page_size: int,
    vehicle_category: str,
) -> int:
    """Everything one seller has online, plus their headline count.

    `sid` is an ordinary search filter, so a dealer's stock is just a search
    -- and is subject to the same ~2,000-row ceiling, which almost no dealer
    reaches.
    """
    sid = str(seller_id).strip()
    try:
        counted = await client.get_json(
            "search/hit-count", {"sid": sid, "vc": vehicle_category}
        )
        await emit(
            record(
                "dealer_summary",
                sid,
                {
                    "sellerId": sid,
                    "adCount": counted.get("count"),
                    "vehicleCategory": vehicle_category,
                },
                mode="dealer_inventory",
                query=sid,
            )
        )
        budget.take(1)
    except MobileDeError as exc:
        log.warning("[dealer %s] hit-count failed: %s", sid, exc)

    path = f"/fahrzeuge/search.html?vc={vehicle_category}&sid={sid}"
    return await run_search(
        client,
        emit,
        path,
        budget=budget,
        page_size=page_size,
        label=f"dealer {sid}",
        mode="dealer_inventory",
        parent_id=sid,
    )


# --- dispatch helper --------------------------------------------------------


async def guarded(
    coro_factory: Callable[[], Any],
    emit: Emit,
    *,
    mode: str,
    input_value: Any,
) -> int:
    """Run one target, turning any failure into a diagnostic row.

    A single dead ad id must not take the run down, and must not vanish
    silently either.
    """
    try:
        return await coro_factory()
    except MobileDeNotFound as exc:
        await emit(error_record("not_found", str(exc), mode=mode, input_value=input_value))
    except MobileDeBadRequest as exc:
        await emit(error_record("bad_request", str(exc), mode=mode, input_value=input_value))
    except FilterError as exc:
        await emit(
            error_record("unsupported_input", str(exc), mode=mode, input_value=input_value)
        )
    except asyncio.CancelledError:
        raise
    except MobileDeError as exc:
        await emit(
            error_record(
                "fetch_failed",
                f"{type(exc).__name__}: {exc}",
                mode=mode,
                input_value=input_value,
            )
        )
    except Exception as exc:  # noqa: BLE001 - a parser fault is data, not a crash
        log.exception("Unexpected failure on %s", input_value)
        await emit(
            error_record(
                "parse_failed",
                f"{type(exc).__name__}: {exc}",
                mode=mode,
                input_value=input_value,
            )
        )
    return 0
