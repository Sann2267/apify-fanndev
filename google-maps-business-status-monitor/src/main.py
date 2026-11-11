"""Google Maps Business Verification & Status Monitoring -- Apify actor entry point."""

from __future__ import annotations

import asyncio
from typing import Any

from apify import Actor

from src.client import BlockedError, MapsClient, UnexpectedShape
from src.constants import PLACE_PB, PLACE_URL, REQUEST_DELAY
from src.exporters import BUILDERS
from src.geo import GeoTarget
from src.places import extract_detail_place, parse_place, utc_now_iso
from src.resolver import ResolutionError, resolve
from src.search import search_point
from src.status import assess, matches_filters, summarise
from src.input_errors import input_error

SOURCE_SEARCH = "S1-tbm-map-search"
SOURCE_DETAIL = "S2-preview-place"


def envelope(raw_input: str, source: str, record_type: str, payload: dict) -> dict:
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


async def fetch_detail(client: MapsClient, feature_id: str) -> Any:
    payload = await client.get_rpc(
        PLACE_URL,
        {"authuser": "0", "hl": client.language, "gl": client.region,
         "pb": PLACE_PB.format(feature_id=feature_id)},
    )
    return extract_detail_place(payload)


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
                "location to prospect an area, and/or placeUrls / placeIds to audit "
                "specific businesses."
            )

        max_per_query = int(actor_input.get("maxResultsPerQuery", 100))
        language = actor_input.get("language", "en")
        region = actor_input.get("region", "US")
        verify_with_detail = bool(actor_input.get("verifyWithPlaceDetails"))
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitAreaSummary", True))

        filters = {
            "onlyUnclaimed": bool(actor_input.get("onlyUnclaimed")),
            "onlyWithoutWebsite": bool(actor_input.get("onlyWithoutWebsite")),
            "onlyWithoutPhone": bool(actor_input.get("onlyWithoutPhone")),
            "onlyClosed": bool(actor_input.get("onlyClosed")),
            "excludePermanentlyClosed": bool(actor_input.get("excludePermanentlyClosed")),
            "minOpportunityScore": actor_input.get("minOpportunityScore"),
        }

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
                "centerLatitude + centerLongitude + radiusKm, or boundingBox."
            )

        # No proxy by default. These endpoints have no WAF and the claim signal
        # survives even Google's reduced record, so the platform IP is fine here.
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
                Actor.log.warning(f"Proxy configuration unavailable ({exc}); running direct.")
        else:
            Actor.log.info("No proxy configured -- using the direct connection.")

        centres = geo.search_centres()
        Actor.log.info(
            f"queries={len(queries)} directPlaces={len(direct)} geo={geo.description} "
            f"centres={len(centres)} maxResultsPerQuery={max_per_query} "
            f"verifyWithPlaceDetails={verify_with_detail}"
        )

        all_records: list[dict] = []
        assessed: list[dict] = []
        failures = 0

        async with MapsClient(
            proxy_url=proxy_url, language=language, region=region, log=Actor.log
        ) as client:
            # -- 1. prospect an area ---------------------------------------
            for query in queries:
                seen: set[str] = set()
                found: list[tuple] = []
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
                    kept = [pair for pair in batch
                            if geo.matches(pair[1].get("latitude"),
                                           pair[1].get("longitude")) is not False]
                    found.extend(kept[: max_per_query - len(found)])
                    Actor.log.info(
                        f"[{query}] centre {index}/{len(centres)} +{len(kept)} "
                        f"-> {len(found)}/{max_per_query}"
                    )
                    await asyncio.sleep(REQUEST_DELAY)

                for record, lead in found:
                    lead["_searchQuery"] = query
                    assessed.append({"label": query, "record": record,
                                     "lead": lead, "source": SOURCE_SEARCH})

            # -- 2. audit specific businesses ------------------------------
            for raw in direct:
                try:
                    place = await resolve(raw, client)
                except ResolutionError as exc:
                    failures += 1
                    Actor.log.warning(f"cannot resolve {raw!r}: {exc}")
                    all_records.append(error_record(raw, "unresolvable_input", str(exc)))
                    continue
                try:
                    record = await fetch_detail(client, place.feature_id)
                except (BlockedError, UnexpectedShape) as exc:
                    failures += 1
                    Actor.log.error(f"detail failed for {raw!r}: {exc}")
                    all_records.append(error_record(raw, "detail_failed", str(exc)))
                    continue
                lead = parse_place(record) if record is not None else None
                if not lead:
                    failures += 1
                    all_records.append(error_record(
                        raw, "no_place_data", "Google returned no record for this identifier."))
                    continue
                lead["_searchQuery"] = None
                assessed.append({"label": raw, "record": record,
                                 "lead": lead, "source": SOURCE_DETAIL})
                await asyncio.sleep(REQUEST_DELAY)

            # -- 3. optional detail verification ---------------------------
            # Closure wording is only ever on the detail record, and Google keeps
            # closed businesses out of search results, so this is the only way a
            # search-discovered listing can be confirmed closed.
            if verify_with_detail:
                targets = [a for a in assessed if a["source"] == SOURCE_SEARCH]
                Actor.log.info(f"Verifying {len(targets)} listing(s) against place details...")
                for position, item in enumerate(targets, start=1):
                    try:
                        record = await fetch_detail(client, item["lead"]["featureId"])
                    except (BlockedError, UnexpectedShape) as exc:
                        Actor.log.warning(f"  verify failed for {item['lead']['name']!r}: {exc}")
                        continue
                    if record is not None:
                        detail_lead = parse_place(record)
                        if detail_lead:
                            item["record"] = record
                            item["lead"] = {**item["lead"],
                                            **{k: v for k, v in detail_lead.items()
                                               if v not in (None, "", [])}}
                            item["source"] = SOURCE_DETAIL
                    if position % 25 == 0:
                        Actor.log.info(f"  verified {position}/{len(targets)}")
                    await asyncio.sleep(REQUEST_DELAY)

        # -- 4. assess, filter, emit ---------------------------------------
        rows: list[dict] = []
        for item in assessed:
            lead = item["lead"]
            verdict = assess(item["record"], lead)
            payload = {k: v for k, v in lead.items() if k != "_input"}
            payload.update(verdict)
            payload["verifiedWithPlaceDetails"] = item["source"] == SOURCE_DETAIL
            if not matches_filters(verdict, filters):
                continue
            rows.append(payload)
            record_out = envelope(item["label"], item["source"], "BUSINESS", payload)
            await Actor.push_data(record_out)
            all_records.append(record_out)

        if emit_summary and rows:
            summary = summarise(rows)
            summary_record = envelope(
                ", ".join(queries) or "direct", SOURCE_SEARCH, "AREA_SUMMARY",
                {"area": geo.description, "queries": queries, **summary},
            )
            await Actor.push_data(summary_record)
            all_records.append(summary_record)
            Actor.log.info(
                f"Area summary: {summary['unclaimed']}/{summary['businessesAssessed']} unclaimed "
                f"({summary['unclaimedPercent']}%), {summary['withoutWebsite']} without a website, "
                f"{summary['unclaimedAndNoWebsite']} with both, "
                f"{summary['highOpportunityCount']} high-opportunity"
            )

        for record in [r for r in all_records if r.get("recordType") == "ERROR"]:
            await Actor.push_data(record)

        # -- 5. exports ------------------------------------------------------
        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                filename = filename.replace("reviews", "business-status")
                payload_bytes = builder(all_records)
                if payload_bytes is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload_bytes, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload_bytes):,} bytes)")

        unclaimed = sum(1 for r in rows if r.get("isUnclaimed"))
        no_site = sum(1 for r in rows if not r.get("hasWebsite"))
        closed = sum(1 for r in rows if not r.get("isOperational"))
        Actor.log.info(
            f"Finished: {len(rows)} business(es) kept | {unclaimed} unclaimed, "
            f"{no_site} without a website, {closed} closed | {failures} failure(s)"
        )
        if failures and not rows:
            raise RuntimeError(
                "Nothing collected and every input failed -- see the ERROR records."
            )
