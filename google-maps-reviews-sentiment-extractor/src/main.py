"""Google Maps Reviews & Sentiment Extractor -- Apify actor entry point."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from apify import Actor

from src.client import BlockedError, MapsClient, UnexpectedShape
from src.constants import (
    DEFAULT_PAGE_SIZE,
    INNER_LEN,
    MAX_PAGE_SIZE,
    REACTION_CATEGORIES,
    REQUEST_DELAY,
    REVIEWS_URL,
    SLOT_PAGE_SIZE,
    SLOT_PAGE_TOKEN,
    SLOT_PLACE,
    SLOT_QUERY,
    SLOT_REACTIONS,
    SLOT_SORT,
    SLOT_TRAILER,
    SORT_MODES,
)
from src.exporters import BUILDERS
from src.extractor import parse_reviews, unwrap_response, utc_now_iso
from src.geo import GeoFilter
from src.resolver import ResolutionError, ResolvedPlace, resolve
from src.sentiment import score_review, summarise
from src.input_errors import input_error

SOURCE = "S1-getlocalboqproxy"


def build_reqpld(
    feature_id: str,
    sort: int,
    page_size: int | None,
    page_token: str | None,
) -> str:
    """Assemble the GetLocalBoqProxy request payload.

    Slot discipline matters more than it looks: several neighbouring slots
    accept a page token and return a plausible HTTP 200 while ignoring it and
    re-serving page 1. The cursor is slot 19 (see constants.py).
    """
    inner: list[Any] = [None] * INNER_LEN
    inner[SLOT_SORT] = sort
    inner[SLOT_PLACE] = [feature_id, None, None, None]
    inner[SLOT_QUERY] = ""
    inner[SLOT_REACTIONS] = [1, 1, None, [[c] for c in REACTION_CATEGORIES]]
    inner[SLOT_TRAILER] = 0
    if page_token:
        # Page size MUST be null on paginated calls -- sending both is HTTP 400.
        inner[SLOT_PAGE_TOKEN] = page_token
    else:
        inner[SLOT_PAGE_SIZE] = page_size
    return json.dumps([None, [None] * 9 + [inner]], separators=(",", ":"))


async def fetch_page(
    client: MapsClient,
    feature_id: str,
    sort: int,
    page_size: int | None,
    page_token: str | None,
) -> tuple[list, str | None]:
    payload = await client.get_rpc(
        REVIEWS_URL,
        {
            "msc": "gwsrpc",
            "reqpld": build_reqpld(feature_id, sort, page_size, page_token),
            "hl": client.language,
            "gl": client.region,
        },
    )
    raw_reviews, token = unwrap_response(payload)
    return parse_reviews(raw_reviews), token


async def scrape_place(
    client: MapsClient,
    place: ResolvedPlace,
    sort: int,
    max_reviews: int,
    page_size: int,
    only_with_owner_response: bool,
    min_rating: int | None,
    max_rating: int | None,
) -> list[dict]:
    """Page through one place's reviews, de-duplicating by review id."""
    collected: list[dict] = []
    seen: set[str] = set()
    token: str | None = None
    page = 0

    while len(collected) < max_reviews:
        reviews, token = await fetch_page(
            client, place.feature_id, sort, page_size if page == 0 else None, token
        )
        page += 1
        if not reviews:
            Actor.log.info(f"  page {page}: no reviews returned -- end of list")
            break

        fresh = [r for r in reviews if r["reviewId"] not in seen]
        for record in fresh:
            seen.add(record["reviewId"])

        if not fresh:
            # Every id already seen means the cursor stopped advancing. Stop
            # rather than loop forever re-fetching page 1.
            Actor.log.warning(
                f"  page {page}: all {len(reviews)} reviews were duplicates -- "
                "cursor stopped advancing, ending pagination"
            )
            break

        for record in fresh:
            record["sentiment"] = score_review(
                record.get("text"),
                record.get("rating"),
                record.get("language"),
                record.get("textTranslated"),
            ).as_dict()

        kept = fresh
        if only_with_owner_response:
            kept = [r for r in kept if r.get("ownerResponse")]
        if min_rating is not None:
            kept = [r for r in kept if (r.get("rating") or 0) >= min_rating]
        if max_rating is not None:
            kept = [r for r in kept if (r.get("rating") or 0) <= max_rating]

        collected.extend(kept)
        Actor.log.info(
            f"  page {page}: +{len(fresh)} new ({len(kept)} kept), "
            f"total {min(len(collected), max_reviews)}/{max_reviews}"
        )

        if not token:
            Actor.log.info("  no next-page cursor -- end of list")
            break
        await asyncio.sleep(REQUEST_DELAY)

    return collected[:max_reviews]


def envelope(raw_input: str, record_type: str, payload: dict) -> dict:
    return {
        "_input": raw_input,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        **payload,
    }


def error_record(raw_input: str, error: str, detail: str) -> dict:
    return {
        "_input": raw_input,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": error,
        "_errorDetail": detail,
    }


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_inputs: list[str] = []
        for key in ("placeUrls", "placeIds", "startUrls"):
            for item in actor_input.get(key) or []:
                value = item.get("url") if isinstance(item, dict) else item
                if value:
                    raw_inputs.append(str(value).strip())
        raw_inputs = list(dict.fromkeys(raw_inputs))

        if not raw_inputs:
            raise input_error(
                "No places supplied. Provide Google Maps URLs, Place IDs, CIDs or "
                "feature ids via placeUrls / placeIds."
            )

        mode = actor_input.get("mode", "reviews")
        sort_key = actor_input.get("sortBy", "newest")
        if sort_key not in SORT_MODES:
            raise input_error(f"sortBy must be one of {sorted(SORT_MODES)}, got {sort_key!r}")
        sort = SORT_MODES[sort_key]

        max_reviews = int(actor_input.get("maxReviewsPerPlace", 100))
        page_size = min(int(actor_input.get("pageSize", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        language = actor_input.get("language", "en")
        region = actor_input.get("region", "US")
        min_rating = actor_input.get("minRating")
        max_rating = actor_input.get("maxRating")
        only_owner = bool(actor_input.get("onlyWithOwnerResponse")) or mode == "owner_responses"
        summary_only = mode == "summary_only"
        export_formats = actor_input.get("exportFormats") or []
        on_missing_coords = actor_input.get("onMissingCoordinates", "keep")

        try:
            geo = GeoFilter(
                bounding_box=actor_input.get("boundingBox"),
                center_lat=actor_input.get("centerLatitude"),
                center_lng=actor_input.get("centerLongitude"),
                radius_km=actor_input.get("radiusKm"),
                area_name=actor_input.get("areaName"),
            )
        except ValueError as exc:
            raise input_error(f"Invalid geographic filter: {exc}") from exc

        # -- proxy ---------------------------------------------------------
        # Residential is the default because Google rate-limits by exit IP at
        # volume. Reconnaissance found no WAF on these endpoints, so a run with
        # proxy disabled is legitimate -- and create_proxy_configuration must not
        # be called at all in that case, or the SDK fails a no-proxy run.
        proxy_input = actor_input.get("proxyConfiguration") or {}
        proxy_url: str | None = None
        if proxy_input.get("useApifyProxy"):
            # Never force a proxy group: which groups exist differs per account
            # (a free plan has no DATACENTER at all), and naming one the account
            # cannot use fails the whole run at input validation. Passing None
            # lets Apify pick whatever that account actually has.
            groups = proxy_input.get("apifyProxyGroups") or None
            # Pin the exit country to the requested region by default. An exit IP
            # in a GDPR country makes Google serve a consent interstitial instead
            # of the page, which reads downstream as "place not found".
            country = proxy_input.get("apifyProxyCountry") or region.upper()
            try:
                configuration = await Actor.create_proxy_configuration(
                    groups=groups, country_code=country
                )
                if configuration:
                    proxy_url = await configuration.new_url()
                    Actor.log.info(
                        f"Using Apify proxy groups={groups or 'account default'} country={country}"
                    )
            except Exception as exc:
                Actor.log.warning(
                    f"Proxy configuration unavailable ({exc}); continuing without a proxy."
                )
        else:
            # The default. These endpoints have no WAF, and the platform's own IP
            # is verified working -- see README on why residential is a trap here.
            Actor.log.info("No proxy configured -- using the direct connection.")

        Actor.log.info(
            f"mode={mode} sort={sort_key} places={len(raw_inputs)} "
            f"maxReviewsPerPlace={max_reviews} geo={geo.description}"
        )

        all_records: list[dict] = []
        failures = 0

        async with MapsClient(
            proxy_url=proxy_url, language=language, region=region, log=Actor.log
        ) as client:
            for index, raw in enumerate(raw_inputs, start=1):
                Actor.log.info(f"[{index}/{len(raw_inputs)}] {raw}")
                try:
                    place = await resolve(raw, client)
                except ResolutionError as exc:
                    failures += 1
                    Actor.log.warning(f"  cannot resolve: {exc}")
                    record = error_record(raw, "unresolvable_input", str(exc))
                    await Actor.push_data(record)
                    all_records.append(record)
                    continue

                verdict = geo.matches(place.latitude, place.longitude)
                if verdict is False:
                    Actor.log.info(f"  skipped: outside {geo.description}")
                    record = envelope(raw, "SKIPPED", {
                        "featureId": place.feature_id,
                        "placeName": place.name,
                        "latitude": place.latitude,
                        "longitude": place.longitude,
                        "_warning": f"outside_geo_filter:{geo.description}",
                    })
                    await Actor.push_data(record)
                    all_records.append(record)
                    continue
                if verdict is None and geo.active:
                    # No coordinates in the supplied URL, so the filter cannot be
                    # evaluated. Never drop silently.
                    if on_missing_coords == "skip":
                        Actor.log.warning("  skipped: no coordinates to test the geo filter")
                        record = envelope(raw, "SKIPPED", {
                            "featureId": place.feature_id,
                            "placeName": place.name,
                            "_warning": "no_coordinates_for_geo_filter",
                        })
                        await Actor.push_data(record)
                        all_records.append(record)
                        continue
                    Actor.log.warning(
                        "  no coordinates in this input -- geo filter cannot be applied, "
                        "keeping the place (set onMissingCoordinates=skip to drop it)"
                    )

                place_payload = {
                    "featureId": place.feature_id,
                    "placeId": place.place_id,
                    "cid": place.cid,
                    "placeName": place.name,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "mapsUrl": place.maps_url,
                    "resolvedVia": place.source,
                }

                # summary_only still needs reviews to aggregate over -- it just
                # stops after a single page instead of walking the whole list.
                target = page_size if summary_only else max_reviews
                try:
                    reviews = await scrape_place(
                        client, place, sort, target, page_size,
                        only_owner, min_rating, max_rating,
                    )
                except (BlockedError, UnexpectedShape) as exc:
                    failures += 1
                    Actor.log.error(f"  failed: {exc}")
                    record = error_record(
                        raw,
                        "blocked" if isinstance(exc, BlockedError) else "schema_changed",
                        str(exc),
                    )
                    await Actor.push_data(record)
                    all_records.append(record)
                    continue

                summary = summarise(reviews)
                place_record = envelope(raw, "PLACE", {**place_payload, **summary})
                await Actor.push_data(place_record)
                all_records.append(place_record)

                if not summary_only:
                    for review in reviews:
                        record = envelope(raw, "REVIEW", {
                            "featureId": place.feature_id,
                            "placeId": place.place_id,
                            "placeName": place.name,
                            **review,
                        })
                        await Actor.push_data(record)
                        all_records.append(record)

                Actor.log.info(
                    f"  done: {summary['reviewsAnalysed']} reviews | "
                    f"pos {summary['sentimentCounts']['positive']} / "
                    f"neu {summary['sentimentCounts']['neutral']} / "
                    f"neg {summary['sentimentCounts']['negative']} | "
                    f"owner replies {summary['reviewsWithOwnerResponse']}"
                )

        # -- exports -------------------------------------------------------
        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                payload = builder(all_records)
                if payload is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload):,} bytes)")

        reviews_pushed = sum(1 for r in all_records if r.get("recordType") == "REVIEW")
        Actor.log.info(
            f"Finished: {len(all_records)} records "
            f"({reviews_pushed} reviews, {failures} failed input(s))"
        )
        if failures and failures == len(raw_inputs):
            raise RuntimeError(
                "Every input failed -- see the ERROR records in the dataset for details."
            )
