"""Haystack News (haystack.tv) Apify actor -- 8 modes over one internal API.

Modes and what they read from the input:

  videos        <- targets        feed of videos for a category/channel/topic/location
  video-detail  <- videoUrls      the 45-field video object (llm tags, views, analytics)
  search        <- queries        video search
  discover      <- queries        entity search: channels / locations / topics
  channels      <- (nothing)      the full 483-channel directory
  taxonomy      <- (nothing)      categories, live channels, special streams, locations
  polls         <- (nothing)      every poll with its live vote counts
  local-events  <- locations      local events per city (premium-capped, see README)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from apify import Actor

from .client import (
    HaystackClient,
    HttpError,
    TokenBootstrapError,
    UnexpectedShape,
    UpstreamVersionRetired,
)
from .constants import (
    EP_CHANNEL,
    EP_LOCAL_EVENTS,
    EP_PLAYLIST,
    EP_POLLS_DATA,
    EP_SEARCH,
    EP_SITEMAP,
    EP_SITEMAP_XML,
    EP_SUGGEST,
    LOCAL_EVENT_CATEGORIES,
    LOCAL_EVENT_SORTS,
    SNAPSHOT_QUALITY,
)
from .extractor import (
    category_record,
    channel_record,
    error_record,
    local_event_record,
    playlist_meta,
    poll_record,
    simple_record,
    tag_group_records,
    video_id_of,
    video_record,
)
from .targets import Target, location_slug_to_query, parse_targets

log = logging.getLogger("haystack")

TARGET_MODES = {"videos", "video-detail"}
QUERY_MODES = {"search", "discover"}
CATALOG_MODES = {"channels", "taxonomy", "polls"}

# Modes whose per-input failures are expected and should become error records
# rather than crashing the run.
RECOVERABLE = (HttpError, UnexpectedShape, asyncio.TimeoutError)


class RunCounters:
    def __init__(self) -> None:
        self.pushed = 0
        self.errors = 0


async def push(record: dict, counters: RunCounters) -> None:
    await Actor.push_data(record)
    counters.pushed += 1
    if record.get("_error"):
        counters.errors += 1


# -- videos / video-detail ----------------------------------------------------


async def fetch_playlist(client: HaystackClient, params: dict) -> dict:
    payload = await client.get_json(
        EP_PLAYLIST, params={"snapshotQuality": SNAPSHOT_QUALITY, **params}
    )
    if not isinstance(payload, dict):
        raise UnexpectedShape(
            f"/playlist returned {type(payload).__name__}, expected object."
        )
    if "streams" not in payload:
        raise UnexpectedShape(
            f"/playlist response has no 'streams' key; got {sorted(payload)[:12]}"
        )
    return payload


async def run_videos(
    client: HaystackClient,
    target: Target,
    counters: RunCounters,
    max_items: int,
    include_tag_groups: bool,
) -> None:
    source = f"S1-playlist-{target.kind}"
    try:
        payload = await fetch_playlist(client, target.playlist_params())
    except RECOVERABLE as exc:
        await push(error_record(target.raw, _error_kind(exc), str(exc)), counters)
        return

    streams = payload.get("streams") or []
    if not streams:
        await push(
            error_record(
                target.raw,
                "empty_feed",
                f"kind={target.kind} value={target.value!r} returned 0 streams.",
            ),
            counters,
        )
        return

    meta = playlist_meta(payload)
    for stream in streams[:max_items]:
        if not isinstance(stream, dict):
            raise UnexpectedShape(
                f"stream entry is {type(stream).__name__}, expected object."
            )
        await push(video_record(stream, target.raw, source, "VIDEO", meta), counters)

    if include_tag_groups:
        for rec in tag_group_records(payload, target.raw, source):
            await push(rec, counters)


async def run_video_detail(
    client: HaystackClient, target: Target, counters: RunCounters
) -> None:
    """The first stream of a video-anchored playlist is the full 45-field object.

    The feed shape carries ~27 fields; anchoring on the video itself adds
    sourceUrl, downloadUrl, llm (topic/emotion classification), views,
    exit_ratio / exit_users, cluster, haystackTags and videoTypeFlags.
    """
    source = "S1-playlist-video"
    try:
        payload = await fetch_playlist(client, target.playlist_params())
    except RECOVERABLE as exc:
        await push(error_record(target.raw, _error_kind(exc), str(exc)), counters)
        return

    streams = payload.get("streams") or []
    if not streams:
        await push(error_record(target.raw, "not_found", "0 streams returned."), counters)
        return

    detail = streams[0]
    wanted = target.value.lower()
    got_id = (video_id_of(detail) or "").lower()
    got_slug = (detail.get("slug") or "").lower()
    if wanted not in (got_id, got_slug) and not got_slug.endswith(wanted):
        # Haystack fell back to a generic feed -- the id/slug does not exist.
        await push(
            error_record(
                target.raw,
                "not_found",
                f"Anchor did not resolve: asked {target.value!r}, got id={got_id!r} slug={got_slug!r}.",
            ),
            counters,
        )
        return

    await push(video_record(detail, target.raw, source, "VIDEO_DETAIL"), counters)


# -- search / discover --------------------------------------------------------


def _term_match(stream: dict, terms: list[str]) -> bool:
    """Does any query term appear in the clip's own text fields?"""
    haystack = " ".join(
        [
            str(stream.get("title") or ""),
            str(stream.get("author") or ""),
            " ".join(str(c) for c in stream.get("categories") or []),
            " ".join(
                str(t.get("tag", "")) for t in stream.get("topics") or [] if isinstance(t, dict)
            ),
        ]
    ).lower()
    return any(term in haystack for term in terms)


async def run_search(
    client: HaystackClient, query: str, counters: RunCounters, max_items: int
) -> None:
    source = "S1-playlist-search"
    try:
        payload = await fetch_playlist(client, {"search": query})
    except RECOVERABLE as exc:
        await push(error_record(query, _error_kind(exc), str(exc)), counters)
        return

    streams = payload.get("streams") or []
    if not streams:
        await push(error_record(query, "no_results", "Search returned 0 streams."), counters)
        return

    meta = playlist_meta(payload)
    pushed = streams[:max_items]
    for stream in pushed:
        await push(video_record(stream, query, source, "VIDEO", meta), counters)

    # Haystack's search NEVER reports "no results" -- a nonsense query still
    # returns ~20 loosely-ranked clips (verified: two different gibberish
    # queries overlapped only 5/20, so it is fuzzy ranking, not a fixed
    # fallback list). Since search is semantic, a literal-term miss is not
    # proof of a bad hit, so we measure relevance and flag it rather than
    # dropping rows the consumer might legitimately want.
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) >= 3]
    matched = sum(1 for s in pushed if _term_match(s, terms)) if terms else None
    summary = simple_record(
        {
            "query": query,
            "resultsReturned": len(pushed),
            "resultsMatchingQueryTerms": matched,
            "termMatchRatio": round(matched / len(pushed), 2)
            if matched is not None and pushed
            else None,
        },
        query,
        source,
        "SEARCH_SUMMARY",
    )
    if matched == 0:
        summary["_warning"] = "low_relevance_no_literal_term_match"
    await push(summary, counters)


async def run_discover(client: HaystackClient, query: str, counters: RunCounters) -> None:
    """Entity search -- which channels / locations / topics match a keyword."""
    source = "S1-search"
    try:
        payload = await client.get_json(
            EP_SEARCH, params={"type": "channels,locations,topics", "q": query}
        )
    except RECOVERABLE as exc:
        await push(error_record(query, _error_kind(exc), str(exc)), counters)
        return

    if not isinstance(payload, dict):
        raise UnexpectedShape(f"/search returned {type(payload).__name__}, expected object.")

    found = 0
    for key, record_type in (
        ("channels", "CHANNEL"),
        ("locations", "LOCATION"),
        ("topics", "TOPIC"),
    ):
        for item in payload.get(key) or []:
            if not isinstance(item, dict):
                continue
            await push(simple_record(item, query, source, record_type), counters)
            found += 1

    if not found:
        await push(error_record(query, "no_results", "Entity search matched nothing."), counters)


# -- catalogues ---------------------------------------------------------------


async def run_channels(client: HaystackClient, counters: RunCounters) -> None:
    payload = await client.get_json(EP_CHANNEL, authed=False)
    if not isinstance(payload, list):
        raise UnexpectedShape(f"/channel returned {type(payload).__name__}, expected list.")
    log.info("Channel directory: %d channels.", len(payload))
    for channel in payload:
        if not isinstance(channel, dict):
            raise UnexpectedShape("channel entry is not an object.")
        await push(channel_record(channel, "channels", "S1-channel"), counters)


async def run_taxonomy(client: HaystackClient, counters: RunCounters) -> None:
    """The sitemap catalogue: categories, live channels, special streams, locations."""
    payload = await client.get_json(EP_SITEMAP, authed=False)
    if not isinstance(payload, dict):
        raise UnexpectedShape(f"/sitemap returned {type(payload).__name__}, expected object.")

    source = "S1-sitemap"

    for path, category in (payload.get("hsChannels") or {}).items():
        if isinstance(category, dict):
            await push(category_record(path, category, "taxonomy", source), counters)

    for name, category in (payload.get("videoCategories") or {}).items():
        if isinstance(category, dict):
            rec = simple_record(category, "taxonomy", source, "VIDEO_CATEGORY")
            rec.setdefault("categoryName", name)
            await push(rec, counters)

    for live in payload.get("liveChannels") or []:
        if isinstance(live, dict):
            await push(simple_record(live, "taxonomy", source, "LIVE_CHANNEL"), counters)

    for kind, items in (payload.get("specialStreams") or {}).items():
        for item in items or []:
            if isinstance(item, dict):
                rec = simple_record(item, "taxonomy", source, "SPECIAL_STREAM")
                rec.setdefault("specialStreamKind", kind)
                await push(rec, counters)

    # Location slugs only exist in the XML sitemap, not the JSON one.
    await _push_locations(client, counters)


async def _push_locations(client: HaystackClient, counters: RunCounters) -> None:
    try:
        resp = await client.get(EP_SITEMAP_XML, authed=False)
    except RECOVERABLE as exc:
        log.warning("Could not load sitemap.xml for locations: %r", exc)
        return
    if resp.status_code != 200:
        log.warning("sitemap.xml returned %s; skipping locations.", resp.status_code)
        return

    slugs = sorted(set(re.findall(r"/location/([a-z0-9-]+)</loc>", resp.text)))
    log.info("sitemap.xml: %d location slugs.", len(slugs))
    for slug in slugs:
        await push(
            simple_record(
                {"slug": slug, "webUrl": f"https://www.haystack.tv/location/{slug}"},
                "taxonomy",
                "S2-sitemap-xml",
                "LOCATION",
            ),
            counters,
        )


async def run_polls(client: HaystackClient, counters: RunCounters) -> None:
    """Polls come from the SvelteKit SSR payload, which is plain JSON here."""
    payload = await client.get_json(EP_POLLS_DATA, authed=False)
    polls = _polls_from_sveltekit(payload)
    if polls is None:
        raise UnexpectedShape(
            "Could not locate the poll array in /polls/__data.json. "
            "SvelteKit's devalue layout may have changed."
        )
    log.info("Polls: %d.", len(polls))
    for poll in polls:
        await push(poll_record(poll, "polls", "S1-polls-ssr"), counters)


def _polls_from_sveltekit(payload: object) -> list[dict] | None:
    """Pull the poll objects out of SvelteKit's flattened devalue array.

    The payload is {"nodes":[{"type":"data","data":[...]}]} where `data` is a
    flat array and every nested value is an integer index into it. Rather than
    implementing the whole devalue hydrator, we scan the flat array for the
    objects that look like a poll and resolve just their own fields -- which is
    both shorter and far more tolerant of layout changes.
    """
    if not isinstance(payload, dict):
        return None

    for node in payload.get("nodes") or []:
        if not isinstance(node, dict) or node.get("type") != "data":
            continue
        flat = node.get("data")
        if not isinstance(flat, list):
            continue

        def deref(idx: object) -> object:
            # Negative indices are devalue sentinels (-1 undefined, -2 hole...).
            if isinstance(idx, bool) or not isinstance(idx, int):
                return idx
            if idx < 0 or idx >= len(flat):
                return None
            value = flat[idx]
            if isinstance(value, list):
                return [deref(i) for i in value]
            if isinstance(value, dict):
                return {k: deref(v) for k, v in value.items()}
            return value

        polls = [
            {key: deref(value) for key, value in item.items()}
            for item in flat
            if isinstance(item, dict) and "question" in item and "choices" in item
        ]
        if polls:
            return polls
    return None


# -- local events -------------------------------------------------------------


async def resolve_location(client: HaystackClient, slug: str) -> dict | None:
    """slug -> the geo object /localEvents needs (city, region, country, lng_lat)."""
    query = location_slug_to_query(slug)
    try:
        payload = await client.get_json(
            EP_SUGGEST, params={"type": "city_or_zip", "search": query}, authed=False
        )
    except RECOVERABLE as exc:
        log.warning("Location suggest failed for %r: %r", slug, exc)
        return None
    if not isinstance(payload, list):
        return None

    results = [
        item.get("result")
        for item in payload
        if isinstance(item, dict) and isinstance(item.get("result"), dict)
    ]
    for result in results:
        if result.get("slug") == slug:
            return result
    # No exact slug match -- fall back to the top suggestion and flag it.
    if results:
        top = dict(results[0])
        top["_resolvedBy"] = "top_suggestion"
        return top
    return None


async def run_local_events(
    client: HaystackClient, slug: str, counters: RunCounters, deep: bool
) -> None:
    """Harvest local events for one city.

    Anonymous users get 10 events per query out of a much larger `total`
    (Houston: 700). `page` / `limit` / `offset` are all ignored server-side, so
    the only way to widen the harvest is to slice on the two filters the API
    does honour -- `sort` and `category`. Deep mode runs all 3 sorts x 5
    categories + 3 bare sorts (18 calls) and dedupes; measured 66 unique events
    for Houston vs 10 for a single call.
    """
    location = await resolve_location(client, slug)
    if location is None:
        await push(
            error_record(slug, "location_unresolved", f"No Haystack city matches {slug!r}."),
            counters,
        )
        return

    geo = json.dumps(
        {
            "city": location.get("city"),
            "region": location.get("region"),
            "country": location.get("country"),
            "lng_lat": location.get("lng_lat"),
            "slug": location.get("slug", slug),
        }
    )

    slices: list[tuple[str, dict]] = [("base", {})]
    for sort in LOCAL_EVENT_SORTS:
        slices.append((f"sort={sort}", {"sort": sort}))
    if deep:
        for sort in LOCAL_EVENT_SORTS:
            for category in LOCAL_EVENT_CATEGORIES:
                slices.append(
                    (f"sort={sort}&category={category}", {"sort": sort, "category": category})
                )

    seen: set[str] = set()
    total = None
    hidden = None
    failures: list[str] = []

    for slice_tag, extra in slices:
        try:
            payload = await client.get_json(EP_LOCAL_EVENTS, params={"geo": geo, **extra})
        except RECOVERABLE as exc:
            failures.append(f"{slice_tag}: {type(exc).__name__}")
            log.warning("local-events slice %s for %s failed: %r", slice_tag, slug, exc)
            continue
        if not isinstance(payload, dict):
            raise UnexpectedShape(
                f"/localEvents returned {type(payload).__name__}, expected object."
            )

        # `total` is scoped to the slice's own filter (category=sports reports 46,
        # unfiltered reports 700), so only the unfiltered slices describe the city.
        if "category" not in extra:
            total = payload.get("total", total)
            hidden = payload.get("eventsHidden", hidden)

        for event in payload.get("events") or []:
            if not isinstance(event, dict):
                continue
            event_id = event.get("id")
            if event_id in seen:
                continue
            if event_id:
                seen.add(event_id)
            await push(
                local_event_record(event, slug, "S1-localEvents", location, slice_tag),
                counters,
            )

    if not seen:
        detail = (
            f"{len(failures)} slice(s) failed: {failures[:5]}"
            if failures
            else "All slices returned 0 events."
        )
        await push(error_record(slug, "no_events", detail), counters)
        return

    # Report the premium cap honestly rather than implying the harvest is complete.
    summary = simple_record(
        {
            "locationSlug": location.get("slug", slug),
            "city": location.get("city"),
            "region": location.get("region"),
            "eventsHarvested": len(seen),
            "eventsTotalUpstream": total,
            "eventsHiddenByPaywall": hidden,
            "slicesTried": len(slices),
            "slicesFailed": len(failures),
            "slicesFailedDetail": failures or None,
        },
        slug,
        "S1-localEvents",
        "LOCAL_EVENTS_SUMMARY",
    )
    if isinstance(total, int) and len(seen) < total:
        summary["_warning"] = "premium_capped_partial_harvest"
    await push(summary, counters)


# -- driver -------------------------------------------------------------------


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, HttpError):
        if exc.status == 404:
            return "not_found"
        if exc.status == 401:
            return "auth_rejected"
        if exc.status == 400:
            return "invalid_request"
        if exc.status == 0:
            return "retries_exhausted"
        return f"http_{exc.status}"
    if isinstance(exc, UnexpectedShape):
        return "unexpected_shape"
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    return "exception"


async def _maybe_proxy_url(proxy_input: object) -> str | None:
    """Resolve a proxy URL, or None to go direct.

    haystack.tv has no anti-bot layer, so a proxy is genuinely optional here and
    the default input leaves it off. Only build a ProxyConfiguration when the
    user actually asked for one -- calling create_proxy_configuration
    unconditionally makes the SDK demand an Apify proxy password and kills runs
    that never wanted a proxy in the first place.
    """
    if not isinstance(proxy_input, dict):
        return None
    if not (proxy_input.get("useApifyProxy") or proxy_input.get("proxyUrls")):
        return None
    try:
        config = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
    except Exception as exc:
        # A misconfigured proxy must not fail a run that works fine direct.
        log.warning("Proxy configuration failed (%r) -- continuing without a proxy.", exc)
        return None
    if config is None:
        return None
    return await config.new_url()


def _wire_logging() -> None:
    """Route our loggers through Apify's handler so INFO/WARNING reach the run log."""
    apify_logger = logging.getLogger("apify")
    for name in ("haystack", "src.client"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            for handler in apify_logger.handlers:
                logger.addHandler(handler)
        logger.propagate = not logger.handlers


async def main() -> None:
    async with Actor:
        _wire_logging()
        raw_input = await Actor.get_input() or {}

        mode = (raw_input.get("mode") or "videos").strip()
        targets_in = raw_input.get("targets") or []
        video_urls_in = raw_input.get("videoUrls") or []
        queries_in = raw_input.get("queries") or []
        locations_in = raw_input.get("locations") or []
        max_items = int(raw_input.get("maxItemsPerTarget") or 50)
        max_concurrency = max(1, min(int(raw_input.get("maxConcurrency") or 4), 16))
        include_tag_groups = bool(raw_input.get("includeTagGroups"))
        deep_events = bool(raw_input.get("deepLocalEvents", True))

        proxy_url = await _maybe_proxy_url(raw_input.get("proxyConfiguration"))
        log.info("Mode=%s concurrency=%d proxy=%s", mode, max_concurrency, bool(proxy_url))

        counters = RunCounters()

        try:
            async with HaystackClient(proxy_url=proxy_url) as client:
                await _dispatch(
                    client=client,
                    mode=mode,
                    counters=counters,
                    targets_in=targets_in,
                    video_urls_in=video_urls_in,
                    queries_in=queries_in,
                    locations_in=locations_in,
                    max_items=max_items,
                    max_concurrency=max_concurrency,
                    include_tag_groups=include_tag_groups,
                    deep_events=deep_events,
                )
        except (TokenBootstrapError, UpstreamVersionRetired) as exc:
            # Circuit breakers: the run must fail loudly so ops investigates.
            log.error("Fatal: %s", exc)
            raise

        log.info("Done. pushed=%d errors=%d", counters.pushed, counters.errors)
        await Actor.set_value(
            "RUN_SUMMARY",
            {"mode": mode, "pushed": counters.pushed, "errors": counters.errors},
        )


async def _dispatch(
    *,
    client: HaystackClient,
    mode: str,
    counters: RunCounters,
    targets_in: list,
    video_urls_in: list,
    queries_in: list,
    locations_in: list,
    max_items: int,
    max_concurrency: int,
    include_tag_groups: bool,
    deep_events: bool,
) -> None:
    sem = asyncio.Semaphore(max_concurrency)

    async def bounded(coro_factory):
        async with sem:
            await coro_factory()

    if mode in CATALOG_MODES:
        if mode == "channels":
            await run_channels(client, counters)
        elif mode == "taxonomy":
            await run_taxonomy(client, counters)
        else:
            await run_polls(client, counters)
        return

    if mode == "videos":
        targets, bad = parse_targets(targets_in, default_kind="category")
        await _report_bad(bad, counters)
        if not targets:
            raise ValueError(
                "Mode 'videos' needs at least one entry in `targets` "
                "(e.g. news, channel/abc7, tag/trump, location/houston-tx)."
            )
        await asyncio.gather(
            *(
                bounded(
                    lambda t=t: run_videos(client, t, counters, max_items, include_tag_groups)
                )
                for t in targets
            )
        )
        return

    if mode == "video-detail":
        targets, bad = parse_targets(video_urls_in, default_kind="video")
        await _report_bad(bad, counters)
        if not targets:
            raise ValueError("Mode 'video-detail' needs at least one entry in `videoUrls`.")
        await asyncio.gather(
            *(bounded(lambda t=t: run_video_detail(client, t, counters)) for t in targets)
        )
        return

    if mode in QUERY_MODES:
        queries = [str(q).strip() for q in queries_in if str(q).strip()]
        if not queries:
            raise ValueError(f"Mode {mode!r} needs at least one entry in `queries`.")
        if mode == "search":
            await asyncio.gather(
                *(
                    bounded(lambda q=q: run_search(client, q, counters, max_items))
                    for q in queries
                )
            )
        else:
            await asyncio.gather(
                *(bounded(lambda q=q: run_discover(client, q, counters)) for q in queries)
            )
        return

    if mode == "local-events":
        slugs = _location_slugs(locations_in)
        if not slugs:
            raise ValueError(
                "Mode 'local-events' needs at least one entry in `locations` "
                "(e.g. houston-tx or https://www.haystack.tv/location/houston-tx)."
            )
        await asyncio.gather(
            *(
                bounded(lambda s=s: run_local_events(client, s, counters, deep_events))
                for s in slugs
            )
        )
        return

    raise ValueError(
        f"Unknown mode {mode!r}. Valid: videos, video-detail, search, discover, "
        "channels, taxonomy, polls, local-events."
    )


def _location_slugs(raws: list) -> list[str]:
    targets, _bad = parse_targets(raws, default_kind="location")
    return [t.value for t in targets if t.value]


async def _report_bad(bad: list[tuple[str, str]], counters: RunCounters) -> None:
    for raw, detail in bad:
        await push(error_record(raw, "bad_input", detail), counters)
