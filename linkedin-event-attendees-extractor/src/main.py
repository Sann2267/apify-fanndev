"""LinkedIn Event Attendees Extractor -- Apify actor entry point.

People who registered for an event about your category have already raised their
hand on the topic. This actor turns a LinkedIn event URL into that list.

**A ``li_at`` session cookie is required.** LinkedIn redirects
``/events/{id}`` straight to the login wall for anonymous visitors -- there is
no guest view of an event at all, let alone its attendees. Verified 2026-09-20.

Two limits worth knowing before you run this, because they are LinkedIn's and no
scraper gets past them:

* An event's attendee list is only visible to people LinkedIn decides may see
  it -- typically the organiser, and attendees on events whose organiser left
  the list public. A cookie for an account with no relationship to the event
  will often read the event fine and return no attendees.
* Many events publish an attendee **count** while withholding the **names**.

When that happens this actor reports the count, says which case it hit, and
exits successfully rather than looking like it broke.
"""

from __future__ import annotations

import asyncio
import re

from apify import Actor

from src import exporters
from src.linkedin import AuthRequired, LinkedInClient, LinkedInError, proxy_url_from
from src.parse import clean_url, collapse, html_to_text
from src.runtime import (
    clamp,
    clamp_float,
    dedupe,
    envelope,
    error_record,
    event_url,
    notice_record,
    string_list,
)
from src.voyager import (
    QueryIdResolver,
    first_text,
    person_from_voyager,
    require_cookie,
    walk,
)
from src.input_errors import input_error

SOURCE_EVENT = "voyager-event"
SOURCE_ATTENDEES = "voyager-event-attendees"

COLUMNS = [
    "fullName", "firstName", "lastName", "headline", "profileUrl", "location",
    "attendanceStatus", "eventName", "eventUrl", "eventStartAt",
    "eventOrganiser", "eventAttendeeCount", "recordType",
]

PAGE_SIZE = 50

_EVENT_ID = re.compile(r"/events/(?:[^/?#]*?-)?(\d{10,})")


def event_identifier(url: str) -> str | None:
    """LinkedIn's numeric event id out of any event URL form."""
    match = _EVENT_ID.search(url or "")
    if match:
        return match.group(1)
    tail = (url or "").rstrip("/").split("/")[-1]
    return tail if re.fullmatch(r"\d{10,}", tail) else None


async def read_event(client: LinkedInClient, identifier: str, url: str) -> dict:
    """The event's own record: name, timing, organiser and attendee count."""
    # The decorated REST path is preferred over GraphQL here: it takes no
    # rotating queryId, so it survives LinkedIn's web releases better.
    payload = await client.voyager(
        f"events/professionalEvents/urn:li:fsd_professionalEvent:{identifier}"
    )
    name = next((first_text(n) for n in walk(payload, "name") if first_text(n)), None)
    description = next(
        (first_text(n) for n in walk(payload, "description") if first_text(n)), None
    )
    counts = [n for n in walk(payload, "attendeeCount") if isinstance(n, int)]
    organiser = None
    for node in walk(payload, "organizingEntity") + walk(payload, "organizer"):
        organiser = first_text(node)
        if organiser:
            break
    times = [n for n in walk(payload, "startsAt") if isinstance(n, int)]
    return {
        "eventId": identifier,
        "eventUrl": clean_url(url),
        "eventName": collapse(name),
        "eventDescription": collapse(html_to_text(description))[:2000] or None,
        "eventOrganiser": organiser,
        "eventAttendeeCount": counts[0] if counts else None,
        "eventStartAtEpochMs": times[0] if times else None,
    }


async def attendees_via_voyager(
    client: LinkedInClient,
    resolver: QueryIdResolver,
    identifier: str,
    wanted: int,
    log,
) -> list[dict]:
    """The attendee roster, when LinkedIn is willing to serve it."""
    query_id = await resolver.get("eventAttendees", "voyagerEventsDashProfessionalEvents")
    collected: list[dict] = []
    start = 0
    while len(collected) < wanted and start < 5000:
        variables = (
            f"(eventUrn:urn%3Ali%3Afsd_professionalEvent%3A{identifier},"
            f"start:{start},count:{min(PAGE_SIZE, wanted - len(collected))})"
        )
        try:
            payload = await client.graphql(query_id, variables)
        except LinkedInError as exc:
            if start == 0:
                raise
            log.warning(f"Attendee paging stopped at {start}: {exc}")
            break
        batch: list[dict] = []
        for group in walk(payload, "elements"):
            if not isinstance(group, list):
                continue
            for element in group:
                if not isinstance(element, dict):
                    continue
                person = person_from_voyager(element)
                if person and person.get("profileUrl"):
                    person["attendanceStatus"] = (
                        first_text(element.get("attendeeStatus")) or "REGISTERED"
                    )
                    batch.append(person)
        if not batch:
            break
        collected.extend(batch)
        start += PAGE_SIZE
        if len(batch) < PAGE_SIZE:
            break

    seen: set[str] = set()
    unique = []
    for person in collected:
        key = (person.get("profileUrl") or "").lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(person)
    return unique[:wanted]


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        urls = dedupe(
            [
                normalised
                for raw in string_list(actor_input.get("eventUrls"))
                + string_list(actor_input.get("startUrls"))
                if (normalised := event_url(raw))
            ]
        )
        if not urls:
            raise input_error(
                "No usable event URLs. Give a linkedin.com/events/... link or a "
                "bare numeric event id in eventUrls."
            )

        max_per_event = clamp(actor_input.get("maxAttendeesPerEvent"), 1, 5000, 200)
        max_total = clamp(actor_input.get("maxAttendees"), 1, 20000, 1000)

        records: list[dict] = []

        try:
            cookie = require_cookie(actor_input, "The LinkedIn event surface")
        except AuthRequired as exc:
            # A missing cookie is a configuration gap, not a crash. The run
            # succeeds and the dataset explains itself.
            log.warning(str(exc))
            for url in urls:
                records.append(
                    notice_record(url, "cookie_required", str(exc))
                )
            await Actor.push_data(records)
            exporters.configure(
                preferred=COLUMNS, sheet="Attendees", stem="event-attendees"
            )
            await exporters.write_exports(
                Actor, actor_input.get("exportFormats") or [], records
            )
            return

        proxy = await proxy_url_from(
            Actor,
            actor_input,
            required_reason=(
                "You supplied a session cookie but no proxy. LinkedIn weighs the "
                "exit IP against where your account normally signs in, and an "
                "Apify datacenter IP is exactly the mismatch that gets a session "
                "flagged. Enable a RESIDENTIAL proxy in your own country."
            ),
        )
        client = LinkedInClient(
            log,
            li_at=cookie,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 3.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )
        resolver = QueryIdResolver(client, log)

        emitted = 0
        for url in urls:
            identifier = event_identifier(url)
            if not identifier:
                records.append(
                    error_record(
                        url,
                        "unparsable_event",
                        "No numeric event id in this URL. LinkedIn event links "
                        "end in a 19-digit id, as in /events/my-event-7178.../",
                    )
                )
                continue

            try:
                event = await read_event(client, identifier, url)
            except LinkedInError as exc:
                code = (
                    "auth_required" if isinstance(exc, AuthRequired) else "fetch_failed"
                )
                records.append(error_record(url, code, str(exc)))
                log.warning(f"{url}: {exc}")
                continue

            records.append({**envelope(SOURCE_EVENT, url, "EVENT"), **event})
            log.info(
                f"{event.get('eventName') or identifier}: "
                f"{event.get('eventAttendeeCount')} attendees reported."
            )

            try:
                people = await attendees_via_voyager(
                    client, resolver, identifier, max_per_event, log
                )
            except LinkedInError as exc:
                records.append(error_record(url, "attendees_failed", str(exc)))
                log.warning(f"{url}: attendee list unavailable -- {exc}")
                continue

            if not people:
                records.append(
                    notice_record(
                        url,
                        "attendee_list_withheld",
                        "LinkedIn served the event but no attendee roster. "
                        "Attendee lists are visible only to accounts LinkedIn "
                        "decides may see them - usually the organiser, and "
                        f"attendees of public-list events. The event reports "
                        f"{event.get('eventAttendeeCount')} attendees, so the "
                        "count is real even though the names were withheld.",
                    )
                )
                continue

            for person in people:
                if emitted >= max_total:
                    break
                records.append(
                    {
                        **envelope(SOURCE_ATTENDEES, url, "ATTENDEE"),
                        **person,
                        "eventName": event.get("eventName"),
                        "eventUrl": event.get("eventUrl"),
                        "eventOrganiser": event.get("eventOrganiser"),
                        "eventAttendeeCount": event.get("eventAttendeeCount"),
                    }
                )
                emitted += 1
            log.info(f"{event.get('eventName') or identifier}: {len(people)} attendees read.")

        log.info(
            f"{emitted} attendee(s) across {len(urls)} event(s). "
            f"HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(
            preferred=COLUMNS, sheet="Attendees", stem="event-attendees"
        )
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
