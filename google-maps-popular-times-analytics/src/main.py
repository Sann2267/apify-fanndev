"""Google Maps Popular Times & Traffic Analytics -- Apify actor entry point."""

from __future__ import annotations

import asyncio
from typing import Any

from apify import Actor

from src.client import BlockedError, MapsClient, UnexpectedShape
from src.constants import PLACE_PB, PLACE_URL
from src.exporters import BUILDERS
from src.geo import GeoTarget
from src.places import extract_detail_place, parse_place, utc_now_iso
from src.popular_times import parse as parse_popular_times
from src.popular_times import to_long_rows
from src.resolver import ResolutionError, resolve
from src.search import search_point
from src.input_errors import input_error

SOURCE = "S1-preview-place"

# Google degrades an IP's responses once enough requests accumulate: it starts
# returning a reduced place record with no popular-times block at all. That is
# indistinguishable, per place, from "this venue has no foot-traffic data", so
# the run watches for a long unbroken run of misses and says so explicitly
# rather than quietly reporting an empty dataset.
DEGRADED_STREAK = 12


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
                "Nothing to do. Supply searchQueries (e.g. 'gym') together with a location, "
                "and/or placeUrls / placeIds for specific venues."
            )

        max_per_query = int(actor_input.get("maxPlacesPerQuery", 50))
        language = actor_input.get("language", "en")
        region = actor_input.get("region", "US")
        output_format = actor_input.get("outputFormat", "wide")
        only_with_data = bool(actor_input.get("onlyPlacesWithPopularTimes", True))
        request_delay = max(0.0, float(actor_input.get("requestDelaySeconds", 1.5)))
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
                "centerLatitude + centerLongitude + radiusKm, or boundingBox."
            )

        # Residential is the DEFAULT for this actor, unlike its sibling Maps actors.
        # Google strips the popular-times block from the record it serves datacenter
        # IPs, so without a residential exit this actor returns nothing useful:
        # measured on the platform, 0% coverage direct vs 62.5% through RESIDENTIAL.
        proxy_input = actor_input.get("proxyConfiguration")
        if proxy_input is None:
            proxy_input = {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}
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
            Actor.log.warning(
                "Proxy is disabled. Google serves datacenter IPs a reduced record with no "
                "popular-times data, so this run will probably return 0% coverage. Enable "
                "the residential proxy unless you are running from a consumer connection."
            )

        centres = geo.search_centres()
        Actor.log.info(
            f"queries={len(queries)} directPlaces={len(direct)} geo={geo.description} "
            f"centres={len(centres)} maxPlacesPerQuery={max_per_query} "
            f"format={output_format} delay={request_delay}s"
        )

        all_records: list[dict] = []
        long_rows: list[dict] = []
        failures = 0
        scanned = with_data = with_live = 0
        miss_streak = 0
        degraded_warned = False

        async with MapsClient(
            proxy_url=proxy_url, language=language, region=region, log=Actor.log
        ) as client:
            # ---- collect the candidate places -----------------------------
            candidates: list[tuple[str, dict]] = []   # (input label, lead)

            for query in queries:
                seen: set[str] = set()
                found: list[dict] = []
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
                    kept = [b for b in batch
                            if geo.matches(b.get("latitude"), b.get("longitude")) is not False]
                    found.extend(kept[: max_per_query - len(found)])
                    Actor.log.info(
                        f"[{query}] centre {index}/{len(centres)} +{len(kept)} "
                        f"-> {len(found)}/{max_per_query}"
                    )
                    await asyncio.sleep(request_delay)
                candidates.extend((query, lead) for lead in found)

            for raw in direct:
                try:
                    place = await resolve(raw, client)
                except ResolutionError as exc:
                    failures += 1
                    Actor.log.warning(f"cannot resolve {raw!r}: {exc}")
                    all_records.append(error_record(raw, "unresolvable_input", str(exc)))
                    continue
                candidates.append((raw, {"featureId": place.feature_id,
                                         "name": place.name, "placeId": place.place_id}))

            Actor.log.info(f"Collecting popular times for {len(candidates)} place(s)...")

            # ---- one detail call per place; only it carries the histogram --
            for label, lead in candidates:
                try:
                    record = await fetch_detail(client, lead["featureId"])
                except (BlockedError, UnexpectedShape) as exc:
                    failures += 1
                    Actor.log.error(f"  detail failed for {lead.get('name')!r}: {exc}")
                    all_records.append(error_record(label, "detail_failed", str(exc)))
                    continue

                scanned += 1
                full = parse_place(record) if record is not None else None
                if full:
                    # The detail record is richer than the search entry; prefer it.
                    lead = {**lead, **{k: v for k, v in full.items() if v not in (None, "", [])}}

                popular = parse_popular_times(record) if record is not None else None

                if popular:
                    with_data += 1
                    miss_streak = 0
                    if popular["hasLiveData"]:
                        with_live += 1
                else:
                    miss_streak += 1
                    if miss_streak >= DEGRADED_STREAK and not degraded_warned:
                        degraded_warned = True
                        Actor.log.warning(
                            f"{miss_streak} places in a row returned no popular-times block. "
                            "Google degrades an IP's responses after enough requests and stops "
                            "sending this data entirely. Re-run later, raise requestDelaySeconds, "
                            "or enable a proxy so the run gets a different exit IP -- see the "
                            "README section 'Why some runs return little data'."
                        )
                    if only_with_data:
                        await asyncio.sleep(request_delay)
                        continue

                payload = {k: v for k, v in lead.items() if k != "_input"}
                payload["hasPopularTimes"] = popular is not None
                if popular:
                    payload.update(popular)

                if output_format == "long" and popular:
                    rows = to_long_rows(lead, popular)
                    long_rows.extend(rows)
                    for row in rows:
                        record_out = envelope(label, "POPULAR_TIMES_HOUR", row)
                        await Actor.push_data(record_out)
                        all_records.append(record_out)
                else:
                    record_out = envelope(label, "PLACE", payload)
                    await Actor.push_data(record_out)
                    all_records.append(record_out)

                await asyncio.sleep(request_delay)

        for record in [r for r in all_records if r.get("recordType") == "ERROR"]:
            await Actor.push_data(record)

        # ---- exports -------------------------------------------------------
        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                filename = filename.replace("reviews", "popular-times")
                payload_bytes = builder(all_records)
                if payload_bytes is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload_bytes, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload_bytes):,} bytes)")

        coverage = round(100.0 * with_data / scanned, 1) if scanned else 0.0
        Actor.log.info(
            f"Finished: {scanned} place(s) checked, {with_data} with popular times "
            f"({coverage}% coverage), {with_live} with a live reading, {failures} failure(s)"
        )
        if scanned and with_data == 0:
            Actor.log.warning(
                "No popular-times data was returned for any place. Either none of these "
                "venues have foot-traffic data, or Google has degraded this exit IP. "
                "Try again later or from a different IP before concluding the former."
            )
