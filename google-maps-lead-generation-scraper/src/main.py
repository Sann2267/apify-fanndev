"""Google Maps Lead Generation & Contact Scraper -- Apify actor entry point."""

from __future__ import annotations

import asyncio
from typing import Any

from apify import Actor

from src.client import BlockedError, MapsClient, UnexpectedShape
from src.constants import PLACE_PB, PLACE_URL, REQUEST_DELAY
from src.enrich import enrich_website
from src.exporters import BUILDERS
from src.geo import GeoTarget
from src.places import extract_detail_place, parse_place, utc_now_iso
from src.resolver import ResolutionError, resolve
from src.search import search_point
from src.input_errors import input_error

SOURCE_SEARCH = "S1-tbm-map-search"
SOURCE_DETAIL = "S2-preview-place"


def envelope(raw_input: str, source: str, payload: dict, record_type: str = "LEAD") -> dict:
    return {
        "_input": raw_input,
        "_source": source,
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


async def fetch_place_detail(client: MapsClient, feature_id: str) -> dict | None:
    payload = await client.get_rpc(
        PLACE_URL,
        {"authuser": "0", "hl": client.language, "gl": client.region,
         "pb": PLACE_PB.format(feature_id=feature_id)},
    )
    record = extract_detail_place(payload)
    return parse_place(record) if record is not None else None


async def enrich_all(
    client: MapsClient,
    leads: list[dict],
    concurrency: int,
    follow_contact: bool,
) -> None:
    """Enrich leads in place, bounded by a semaphore."""
    targets = [lead for lead in leads if lead.get("website")]
    if not targets:
        return
    Actor.log.info(f"Enriching {len(targets)} lead(s) with a website "
                   f"(concurrency {concurrency})...")
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def one(lead: dict) -> None:
        nonlocal done
        async with semaphore:
            lead.update(await enrich_website(client, lead["website"], follow_contact))
        done += 1
        if done % 25 == 0:
            Actor.log.info(f"  enriched {done}/{len(targets)}")

    await asyncio.gather(*(one(lead) for lead in targets))
    with_email = sum(1 for lead in targets if lead.get("emails"))
    with_social = sum(1 for lead in targets if lead.get("socialProfiles"))
    Actor.log.info(f"  enrichment done: {with_email} with email, {with_social} with socials")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        queries = [str(q).strip() for q in (actor_input.get("searchQueries") or []) if str(q).strip()]
        direct: list[str] = []
        for key in ("placeUrls", "placeIds", "startUrls"):
            for item in actor_input.get(key) or []:
                value = item.get("url") if isinstance(item, dict) else item
                if value:
                    direct.append(str(value).strip())
        direct = list(dict.fromkeys(direct))

        if not queries and not direct:
            raise input_error(
                "Nothing to do. Supply searchQueries (e.g. 'dentist') together with a "
                "location, and/or placeUrls / placeIds for specific businesses."
            )

        max_per_query = int(actor_input.get("maxResultsPerQuery", 100))
        language = actor_input.get("language", "en")
        region = actor_input.get("region", "US")
        enrich = bool(actor_input.get("enrichFromWebsite", True))
        follow_contact = bool(actor_input.get("followContactPage", True))
        enrich_concurrency = max(1, min(int(actor_input.get("enrichmentConcurrency", 6)), 15))
        fetch_details = bool(actor_input.get("fetchPlaceDetails"))
        require_phone = bool(actor_input.get("requirePhone"))
        require_website = bool(actor_input.get("requireWebsite"))
        require_email = bool(actor_input.get("requireEmail"))
        min_rating = actor_input.get("minRating")
        export_formats = actor_input.get("exportFormats") or []

        try:
            geo = GeoTarget(
                bounding_box=actor_input.get("boundingBox"),
                center_lat=actor_input.get("centerLatitude"),
                center_lng=actor_input.get("centerLongitude"),
                radius_km=actor_input.get("radiusKm"),
                area_name=actor_input.get("areaName"),
                tile_km=actor_input.get("tileSizeKm"),
            )
        except ValueError as exc:
            raise input_error(f"Invalid geographic input: {exc}") from exc

        if queries and not geo.active:
            raise input_error(
                "A search query needs a location: set areaName (e.g. 'jakarta'), or "
                "centerLatitude + centerLongitude + radiusKm, or boundingBox. "
                "Without one, Google decides where to search from the exit IP and the "
                "results would not be reproducible."
            )

        # -- proxy ---------------------------------------------------------
        # Off by default. Measured on the platform: these endpoints have no WAF,
        # the platform IP works, and RESIDENTIAL is answered with consent/CAPTCHA
        # interstitials. Never hardcode a group -- which groups exist differs per
        # account, and naming a missing one fails the run before it starts.
        proxy_input = actor_input.get("proxyConfiguration") or {}
        proxy_url: str | None = None
        if proxy_input.get("useApifyProxy"):
            groups = proxy_input.get("apifyProxyGroups") or None
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
            Actor.log.info("No proxy configured -- using the direct connection.")

        centres = geo.search_centres()
        Actor.log.info(
            f"queries={len(queries)} directPlaces={len(direct)} geo={geo.description} "
            f"searchCentres={len(centres)} maxResultsPerQuery={max_per_query} enrich={enrich}"
        )

        all_records: list[dict] = []
        leads: list[dict] = []
        failures = 0

        async with MapsClient(
            proxy_url=proxy_url, language=language, region=region, log=Actor.log
        ) as client:
            # -- 1. free-text searches ------------------------------------
            for query in queries:
                seen: set[str] = set()
                found: list[dict] = []
                outside = 0
                distance = geo.viewport_distance()
                for index, (lat, lng) in enumerate(centres, start=1):
                    if len(found) >= max_per_query:
                        break
                    try:
                        batch = await search_point(
                            client, query, lat, lng, distance,
                            max_per_query - len(found), seen,
                        )
                    except (BlockedError, UnexpectedShape) as exc:
                        failures += 1
                        Actor.log.error(f"  search failed at centre {index}: {exc}")
                        all_records.append(error_record(query, "search_failed", str(exc)))
                        break

                    # Filter by area HERE, not after the whole query. Google honours
                    # the viewport loosely and a tile on the edge of an area can
                    # return a full page of out-of-area businesses. Counting those
                    # toward the result cap would end the query having collected
                    # nothing usable and never visit the remaining tiles.
                    kept_batch = []
                    for lead in batch:
                        if geo.matches(lead.get("latitude"), lead.get("longitude")) is False:
                            outside += 1
                        else:
                            kept_batch.append(lead)

                    found.extend(kept_batch[: max_per_query - len(found)])
                    Actor.log.info(
                        f"[{query}] centre {index}/{len(centres)} "
                        f"({lat:.4f},{lng:.4f}) +{len(kept_batch)} kept"
                        f"{f' ({len(batch) - len(kept_batch)} outside)' if len(kept_batch) != len(batch) else ''}"
                        f" -> {len(found)}/{max_per_query}"
                    )
                    await asyncio.sleep(REQUEST_DELAY)
                if outside:
                    Actor.log.info(
                        f"[{query}] {outside} result(s) discarded as outside {geo.description}"
                    )

                for lead in found:
                    lead["_searchQuery"] = query
                    lead["_source"] = SOURCE_SEARCH
                leads.extend(found)

            # -- 2. directly supplied places ------------------------------
            for raw in direct:
                try:
                    place = await resolve(raw, client)
                except ResolutionError as exc:
                    failures += 1
                    Actor.log.warning(f"cannot resolve {raw!r}: {exc}")
                    all_records.append(error_record(raw, "unresolvable_input", str(exc)))
                    continue
                try:
                    lead = await fetch_place_detail(client, place.feature_id)
                except (BlockedError, UnexpectedShape) as exc:
                    failures += 1
                    Actor.log.error(f"detail failed for {raw!r}: {exc}")
                    all_records.append(error_record(raw, "detail_failed", str(exc)))
                    continue
                if not lead:
                    failures += 1
                    all_records.append(error_record(
                        raw, "no_place_data",
                        "Google returned no place record for this identifier."))
                    continue
                lead["_searchQuery"] = None
                lead["_source"] = SOURCE_DETAIL
                lead["_input"] = raw
                leads.append(lead)
                Actor.log.info(f"resolved {raw!r} -> {lead['name']}")
                await asyncio.sleep(REQUEST_DELAY)

            # -- 3. geographic filtering for directly-supplied places ------
            # Search results were filtered per tile above; this covers places
            # given by URL/ID, which never went through a search centre.
            if geo.active:
                inside, outside, unknown = [], 0, 0
                for lead in leads:
                    verdict = geo.matches(lead.get("latitude"), lead.get("longitude"))
                    if verdict is True:
                        inside.append(lead)
                    elif verdict is False:
                        outside += 1
                    else:
                        unknown += 1
                        inside.append(lead)
                if outside or unknown:
                    Actor.log.info(
                        f"Geo filter {geo.description}: kept {len(inside)}, "
                        f"dropped {outside} outside, {unknown} without coordinates (kept)"
                    )
                leads = inside

            # -- 3b. top up from the place detail endpoint ----------------
            # Google serves two different richnesses of search record and picks
            # between them by client/IP: the full one carries the 7-day schedule
            # and review counts, the reduced one carries today's hours only. A
            # datacenter IP reliably gets the reduced form, so this top-up is
            # what makes opening hours complete on the platform. One extra
            # request per lead, hence opt-in.
            if fetch_details and leads:
                partial = [l for l in leads
                           if not l.get("openingHoursComplete") or l.get("reviewsCount") is None]
                Actor.log.info(f"Fetching place details for {len(partial)} lead(s)...")
                filled = 0
                for lead in partial:
                    try:
                        detail = await fetch_place_detail(client, lead["featureId"])
                    except (BlockedError, UnexpectedShape) as exc:
                        Actor.log.warning(f"  hours lookup failed for {lead['name']!r}: {exc}")
                        continue
                    if detail:
                        # The detail response is richer than a search entry in
                        # more than one way, so top up everything it knows
                        # better -- not just the schedule we came for.
                        if len(detail.get("openingHours") or []) > len(lead.get("openingHours") or []):
                            lead["openingHours"] = detail["openingHours"]
                            lead["openingHoursComplete"] = detail.get("openingHoursComplete", False)
                            filled += 1
                        for field in ("reviewsCount", "reviewsUrl", "rating", "plusCode",
                                      "description", "website", "websiteDomain", "phone",
                                      "phoneE164", "openNow"):
                            if lead.get(field) in (None, "", []) and detail.get(field) not in (None, "", []):
                                lead[field] = detail[field]
                    await asyncio.sleep(REQUEST_DELAY)
                Actor.log.info(
                    f"  place details: {filled}/{len(partial)} schedules completed "
                    f"(review counts and descriptions are topped up regardless)"
                )

            if not fetch_details and leads:
                reduced = sum(1 for l in leads if not l.get("openingHoursComplete"))
                if reduced > len(leads) // 2:
                    Actor.log.warning(
                        f"{reduced}/{len(leads)} leads came back with a partial opening-hours "
                        "schedule -- Google served this run its reduced record. Set "
                        "fetchPlaceDetails=true to recover review counts and descriptions "
                        "(one extra request per lead). Note the full weekly schedule often "
                        "cannot be recovered from a datacenter IP at all."
                    )

            # -- 4. enrichment --------------------------------------------
            if enrich and leads:
                await enrich_all(client, leads, enrich_concurrency, follow_contact)

        # -- 5. quality filters --------------------------------------------
        def wanted(lead: dict) -> bool:
            if require_phone and not lead.get("phone"):
                return False
            if require_website and not lead.get("website"):
                return False
            if require_email and not lead.get("emails"):
                return False
            if min_rating is not None and (lead.get("rating") or 0) < float(min_rating):
                return False
            return True

        kept = [lead for lead in leads if wanted(lead)]
        if len(kept) != len(leads):
            Actor.log.info(f"Quality filters kept {len(kept)} of {len(leads)} leads.")

        for lead in kept:
            record = envelope(
                lead.get("_input") or lead.get("_searchQuery") or lead["featureId"],
                lead.pop("_source", SOURCE_SEARCH),
                {k: v for k, v in lead.items() if k != "_input"},
            )
            await Actor.push_data(record)
            all_records.append(record)

        for record in [r for r in all_records if r.get("recordType") == "ERROR"]:
            await Actor.push_data(record)

        # -- 6. exports ------------------------------------------------------
        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                filename = filename.replace("reviews", "leads")
                payload = builder(all_records)
                if payload is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload):,} bytes)")

        with_email = sum(1 for r in kept if r.get("emails"))
        with_phone = sum(1 for r in kept if r.get("phone"))
        with_site = sum(1 for r in kept if r.get("website"))
        Actor.log.info(
            f"Finished: {len(kept)} leads | {with_phone} with phone, "
            f"{with_site} with website, {with_email} with email | {failures} failure(s)"
        )
        if failures and not kept:
            raise RuntimeError(
                "No leads collected and every input failed -- see the ERROR records."
            )
