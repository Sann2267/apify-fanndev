"""tbm=map search: build the pb, page through results, dedupe by feature id."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from src.client import MapsClient
from src.constants import (
    REQUEST_DELAY,
    SEARCH_PAGE_SIZE,
    SEARCH_TAIL,
    SEARCH_URL,
    SEARCH_VIEWPORT,
)
from src.places import extract_search_places, parse_place


def build_pb(latitude: float, longitude: float, distance: float, offset: int) -> str:
    return (
        SEARCH_VIEWPORT.format(distance=int(distance), longitude=longitude, latitude=latitude)
        + SEARCH_TAIL.format(offset=offset)
    )


async def search_page(
    client: MapsClient,
    query: str,
    latitude: float,
    longitude: float,
    distance: float,
    offset: int,
) -> list[dict]:
    """One page of results (up to 20 leads)."""
    return [lead for _, lead in await search_page_raw(
        client, query, latitude, longitude, distance, offset)]


async def search_page_raw(
    client: MapsClient,
    query: str,
    latitude: float,
    longitude: float,
    distance: float,
    offset: int,
) -> list[tuple]:
    """One page as (raw positional record, parsed lead) pairs.

    The status checks need the raw record: claim status is carried by an action
    link buried in the record, not by any field the lead parser surfaces.
    """
    payload = await client.get_rpc(
        SEARCH_URL,
        {
            "tbm": "map",
            "authuser": "0",
            "hl": client.language,
            "gl": client.region,
            "pb": build_pb(latitude, longitude, distance, offset),
            "q": query,
        },
    )
    if payload is None:
        return []
    pairs = []
    for record in extract_search_places(payload):
        lead = parse_place(record)
        if lead:
            pairs.append((record, lead))
    return pairs


async def search_point(
    client: MapsClient,
    query: str,
    latitude: float,
    longitude: float,
    distance: float,
    max_results: int,
    seen: set[str],
    on_page: Callable[[int, int, int], None] | None = None,
) -> list[tuple]:
    """Page through one search centre as (raw record, parsed lead) pairs.

    `seen` is shared across every centre so overlapping tiles do not re-emit the
    same business; it is also why the duplicate check cannot live per-page.
    """
    collected: list[tuple] = []
    offset = 0
    page = 0

    while len(collected) < max_results:
        pairs = await search_page_raw(client, query, latitude, longitude, distance, offset)
        leads = [lead for _, lead in pairs]
        page += 1
        if not leads:
            break

        fresh = [pair for pair in pairs if pair[1]["featureId"] not in seen]
        for _, lead in fresh:
            seen.add(lead["featureId"])
        collected.extend(fresh)

        if on_page:
            on_page(page, len(leads), len(fresh))

        # A short page means Google has no more for this viewport. An all-duplicate
        # page means this tile overlaps ground already covered -- stop either way
        # rather than paging into nothing.
        if len(leads) < SEARCH_PAGE_SIZE or not fresh:
            break

        offset += SEARCH_PAGE_SIZE
        await asyncio.sleep(REQUEST_DELAY)

    return collected[:max_results]
