"""Fetching events from Facebook's two open event surfaces.

Facebook's general search is closed to signed-out clients -- `/search/pages/`,
`/search/groups/`, `/search/top/` and every other vertical return HTTP 404. The
event search is the one exception: `/events/search/?q=<term>` returns 200 with
real, server-rendered event nodes. That is why this actor searches by text
rather than by a location picker: the picker is not reachable, and the search
term is. Putting the city in the query works -- `"jakarta concert"` returned
Jakarta concerts, `"new york yoga"` returned New York yoga classes.

A page's own events tab (`/{slug}/events`) is the second surface, and it is the
better one when you already know whose events you want.

What is *not* open: the individual event page. `/events/<id>/` returns a 67 KB
generic shell with `og:description` = "See posts, photos and more on Facebook",
for real and invented ids alike. So there is no detail fetch to offer, and the
fields an event page would add -- the full description, the guest list -- are not
part of this actor's output rather than being half-guessed from somewhere else.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from src.fbcore import BlockedError, FacebookSession, harvest_preloaders, is_hollow
from src.parser import (
    cursor_from_html,
    is_detailed,
    merge_event,
    next_cursor,
    parse_events,
    parse_events_html,
)

BASE = "https://www.facebook.com/"
SEARCH_ROOT = "SearchCometResultsInitialResultsQuery"
SEARCH_PAGINATION = "SearchCometResultsPaginatedResultsQuery"
PAGE_EVENTS_PAGINATION = "ProfileCometAppCollectionEventsRendererPaginationQuery"


class EventsUnavailable(RuntimeError):
    """Facebook served no events for this query or page."""


def search_url(term: str) -> str:
    return f"{BASE}events/search/?" + urllib.parse.urlencode({"q": term})


def page_events_url(slug: str) -> str:
    return f"{BASE}{slug}/events"


async def _paginate(
    session: FacebookSession,
    html: str,
    url: str,
    query_name: str,
    events: list[dict],
    max_events: int,
    meta: dict,
    log: Any = None,
) -> list[dict]:
    cursor = cursor_from_html(html)
    doc_id = await session.bundle_doc_id(html, query_name) if cursor else None
    preloaders = harvest_preloaders(html)
    base_vars: dict[str, Any] = {}
    for _, (_, variables) in preloaders.items():
        if len(variables) > len(base_vars):
            base_vars = variables

    if not cursor or not doc_id or not base_vars:
        meta["paginationUnavailable"] = True
        return events[:max_events]

    meta["paginated"] = True
    seen = {e["eventId"] for e in events if e["eventId"]}
    while len(events) < max_events and cursor:
        variables = dict(base_vars)
        variables["cursor"] = cursor
        variables["count"] = 10
        try:
            payload = await session.graphql(html, query_name, doc_id, variables, referer=url)
        except BlockedError as exc:
            meta["paginationStoppedBy"] = str(exc)
            break
        meta["requestsMade"] += 1

        fresh = [e for e in parse_events(payload) if e["eventId"] not in seen]
        if not fresh:
            break
        for event in fresh:
            seen.add(event["eventId"])
        events.extend(fresh)
        if log:
            log.info(f"  +{len(fresh)} event(s) (running total {len(events)})")
        cursor = next_cursor(payload)

    return events[:max_events]


async def _fetch_detailed(
    session: FacebookSession, url: str, meta: dict, log: Any = None
) -> tuple[str, list[dict]]:
    """Fetch, and refetch once if the response came back without event detail.

    Facebook serves this surface at two levels: sometimes every event node
    carries its date, place and cover photo, sometimes the same URL returns only
    name-and-link stubs. It is not a parse failure and it is not sticky -- a
    second request usually returns the detailed variant. One retry is worth the
    request; a loop would not be, so it stops after one and says what it got.
    """
    html = await session.get_html(url)
    events = parse_events_html(html)
    if events and not any(is_detailed(event) for event in events):
        if log:
            log.info(
                "  Facebook returned name-and-link stubs for these events; "
                "refetching once for the detailed variant."
            )
        retry_html = await session.get_html(url)
        meta["requestsMade"] += 1
        retry_events = parse_events_html(retry_html)
        if any(is_detailed(event) for event in retry_events):
            by_id = {e["eventId"] or e["name"]: e for e in retry_events}
            for event in events:
                other = by_id.pop(event["eventId"] or event["name"], None)
                if other:
                    merge_event(event, other)
            events.extend(by_id.values())
            html = retry_html
        meta["refetchedForDetail"] = True
    meta["eventsWithDetail"] = sum(1 for event in events if is_detailed(event))
    return html, events


async def search_events(
    session: FacebookSession,
    term: str,
    max_events: int,
    log: Any = None,
) -> tuple[list[dict], dict]:
    url = search_url(term)
    meta = {"sourceUrl": url, "requestsMade": 1, "paginated": False}
    html, events = await _fetch_detailed(session, url, meta, log)
    if not events:
        raise EventsUnavailable(
            f"Facebook returned no events for {term!r}. Event search is text-only: "
            "put the city in the query, e.g. 'yoga new york' or 'konser jakarta'."
        )
    if len(events) >= max_events:
        return events[:max_events], meta
    events = await _paginate(
        session, html, url, SEARCH_PAGINATION, events, max_events, meta, log
    )
    return events, meta


async def page_events(
    session: FacebookSession,
    slug: str,
    max_events: int,
    log: Any = None,
) -> tuple[list[dict], dict]:
    url = page_events_url(slug)
    meta = {"sourceUrl": url, "requestsMade": 1, "paginated": False}
    html = await session.get_html(url)
    if is_hollow(html):
        raise EventsUnavailable(
            "Facebook served the empty shell (~330 KB). No page resolves to this slug."
        )
    events = parse_events_html(html)
    meta["eventsWithDetail"] = sum(1 for event in events if is_detailed(event))
    if not events:
        raise EventsUnavailable(
            "The page rendered but published no events. Most pages have none."
        )
    if len(events) >= max_events:
        return events[:max_events], meta
    events = await _paginate(
        session, html, url, PAGE_EVENTS_PAGINATION, events, max_events, meta, log
    )
    return events, meta
