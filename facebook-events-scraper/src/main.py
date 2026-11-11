"""Facebook Events Scraper -- Apify actor entry point."""

from __future__ import annotations

from datetime import datetime, timezone

from apify import Actor

from src.events import EventsUnavailable, page_events, search_events
from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession
from src.parser import matches_filters, page_ref, summarise
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.input_errors import input_error

SOURCE = "events"


def epoch_from_date(value: str | None, label: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD, got {value!r}")
    return int(parsed.timestamp())


def read_input(actor_input: dict) -> tuple[list[str], list[str]]:
    terms = [str(t).strip() for t in (actor_input.get("searchTerms") or []) if str(t).strip()]

    # A location is expressed inside the search term, because Facebook's event
    # search takes no location parameter that a signed-out client can use.
    locations = [str(c).strip() for c in (actor_input.get("locations") or []) if str(c).strip()]
    if locations and terms:
        terms = [f"{term} {location}" for term in terms for location in locations]
    elif locations:
        terms = list(locations)

    slugs: list[str] = []
    for key in ("pages", "startUrls"):
        for item in actor_input.get(key) or []:
            value = item.get("url") if isinstance(item, dict) else item
            slug = page_ref(str(value or ""))
            if slug:
                slugs.append(slug)
    return list(dict.fromkeys(terms)), list(dict.fromkeys(slugs))


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        terms, slugs = read_input(actor_input)
        if not terms and not slugs:
            raise input_error(
                "Nothing to scrape. Supply searchTerms (Facebook's event search is "
                "text-only, so put the city in the term: 'yoga new york'), "
                "locations, or pages whose events tab to read."
            )

        max_events = max(1, min(int(actor_input.get("maxEventsPerQuery", 30)), 500))
        filters = {
            "excludePast": bool(actor_input.get("excludePast", True)),
            "excludeCanceled": bool(actor_input.get("excludeCanceled", True)),
            "onlyOnline": bool(actor_input.get("onlyOnline")),
            "onlyInPerson": bool(actor_input.get("onlyInPerson")),
            "nameContains": actor_input.get("nameContains"),
            "placeContains": actor_input.get("placeContains"),
            "startsAfterEpoch": epoch_from_date(actor_input.get("startsAfter"), "startsAfter"),
            "startsBeforeEpoch": epoch_from_date(actor_input.get("startsBefore"), "startsBefore"),
        }
        if filters["onlyOnline"] and filters["onlyInPerson"]:
            raise input_error(
                "onlyOnline and onlyInPerson exclude each other -- enabling both "
                "can only ever return an empty dataset."
            )
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        Actor.log.info(f"{len(terms)} search(es) and {len(slugs)} page(s).")
        if filters["startsAfterEpoch"] or filters["startsBeforeEpoch"]:
            Actor.log.info(
                "A date filter is set. Events from a page's events tab carry the "
                "date sentence but no exact timestamp, so those are dropped by the "
                "filter rather than admitted on a guess."
            )

        records: list[dict] = []
        kept: list[dict] = []
        failures = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            jobs = [("search", term) for term in terms] + [("page", slug) for slug in slugs]

            for kind, target in jobs:
                label = f"{kind}:{target}"
                try:
                    if kind == "search":
                        events, meta = await search_events(
                            session, target, max_events, log=Actor.log
                        )
                    else:
                        events, meta = await page_events(
                            session, target, max_events, log=Actor.log
                        )
                except (EventsUnavailable, BlockedError) as exc:
                    failures += 1
                    record = error_record(SOURCE, label, "events_unavailable", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue
                except Exception as exc:
                    failures += 1
                    record = error_record(
                        SOURCE, label, "unexpected_error", f"{type(exc).__name__}: {exc}"
                    )
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                if meta.get("paginationUnavailable"):
                    Actor.log.warning(
                        f"{label}: kept the {len(events)} rendered event(s); "
                        "Facebook's pagination query could not be replayed this run."
                    )

                selected = [e for e in events if matches_filters(e, filters)]
                Actor.log.info(
                    f"{label}: {len(selected)} event(s) kept of {len(events)} "
                    f"in {meta['requestsMade']} request(s)"
                )

                for event in selected:
                    record = {
                        **envelope(SOURCE, label, "EVENT"),
                        **event,
                        "source": kind,
                        "query": target,
                        "sourceUrl": meta["sourceUrl"],
                    }
                    records.append(record)
                    kept.append(event)
                    await Actor.push_data(record)

        if emit_summary and kept:
            stats = summarise(kept)
            summary = {
                **envelope(SOURCE, f"{len(terms)} search(es), {len(slugs)} page(s)",
                           "RUN_SUMMARY"),
                **stats,
                "searchesRun": len(terms),
                "pagesRead": len(slugs),
                "failures": failures,
            }
            records.append(summary)
            await Actor.push_data(summary)
            Actor.log.info(
                f"Summary: {stats['eventsCollected']} event(s), "
                f"{stats['inPerson']} in person, {stats['online']} online, "
                f"{stats['withPlace']} with a place, {stats['withTimestamp']} with an "
                "exact start time"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(kept)} event(s) | {failures} failure(s)")
        if failures and not kept:
            raise RuntimeError(
                "Nothing could be read and no events were collected -- see the ERROR records."
            )
