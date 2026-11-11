"""The nine extraction modes, and the input resolution they share.

Inputs are deliberately forgiving. Someone assembling a watchlist has a mix of
things in front of them -- a TMDB URL, an IMDb URL copied from a search result,
a bare `tt` id out of a spreadsheet, and a film title they only know the name
of -- and cannot be expected to convert them into TMDB numeric ids first.
`resolve_target` accepts all of those and works out what it is holding, falling
back to a search when it is holding nothing but a name.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, AsyncIterator, Callable

from .client import TmdbBlocked, TmdbClient, TmdbNotFound
from .constants import (
    CHARTS,
    MAX_PAGE,
    MOVIE_APPENDS,
    MOVIE_GENRES,
    PERSON_APPENDS,
    RESULTS_PER_PAGE,
    SEASON_APPENDS,
    TV_APPENDS,
    TV_GENRES,
)
from .parsers import (
    error_record,
    parse_collection,
    parse_company,
    parse_episode,
    parse_list_entry,
    parse_person,
    parse_review,
    parse_season,
    parse_title,
    record,
)

log = logging.getLogger("tmdb.modes")

IMDB_TITLE_RE = re.compile(r"\b(tt\d{7,10})\b")
IMDB_NAME_RE = re.compile(r"\b(nm\d{7,10})\b")
DIGITS_ONLY = re.compile(r"^\d+$")

MEDIA_PATHS = {"movie": "movie", "tv": "tv", "person": "person"}


class Budget:
    """A shared ceiling on dataset rows for the whole run."""

    def __init__(self, limit: int) -> None:
        self.limit = max(0, int(limit or 0))
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.limit > 0 and self.used >= self.limit

    def take(self, n: int = 1) -> bool:
        if self.exhausted:
            return False
        self.used += n
        return True

    @property
    def remaining(self) -> int | None:
        return None if self.limit == 0 else max(0, self.limit - self.used)


def as_strings(value: Any) -> list[str]:
    """Normalise an input array that may arrive as a list, a string, or junk."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("\n", ",").split(",")]
        return [p for p in parts if p]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, dict):
                # An `editor: requestListSources` field yields {"url": ...}.
                item = item.get("url") or item.get("value") or ""
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    return [str(value).strip()]


# -- input resolution ------------------------------------------------------

class Target:
    """What a single user-supplied string turned out to be.

    `media_type` may be None when the input was a bare number or a plain name,
    in which case the mode's own default decides. `needs_lookup` marks the two
    forms that cost an extra request to resolve: an IMDb id, and a free-text
    name.
    """

    __slots__ = ("raw", "media_type", "tmdb_id", "imdb_id", "name_query")

    def __init__(
        self,
        raw: str,
        media_type: str | None = None,
        tmdb_id: int | None = None,
        imdb_id: str | None = None,
        name_query: str | None = None,
    ) -> None:
        self.raw = raw
        self.media_type = media_type
        self.tmdb_id = tmdb_id
        self.imdb_id = imdb_id
        self.name_query = name_query

    @property
    def needs_lookup(self) -> bool:
        return self.tmdb_id is None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Target({self.raw!r}, media_type={self.media_type}, "
            f"tmdb_id={self.tmdb_id}, imdb_id={self.imdb_id}, name={self.name_query!r})"
        )


def resolve_target(raw: str, default_media_type: str | None = None) -> Target:
    """Work out what a user-supplied reference actually is.

    Accepted, in the order they are tested:

        https://www.themoviedb.org/movie/27205-inception   TMDB URL
        https://www.themoviedb.org/tv/1399/season/1        TMDB URL (series)
        https://www.imdb.com/title/tt1375666/              IMDb URL
        https://www.imdb.com/name/nm0000138/               IMDb URL (person)
        tt1375666 / nm0000138                              bare IMDb id
        movie:27205 / tv:1399 / person:138                 explicit TMDB id
        27205                                              bare TMDB id
        Inception                                          a name to search for

    A bare number is a TMDB id in the mode's own media type, never an IMDb id:
    IMDb ids always carry their `tt`/`nm` prefix, so there is no ambiguity to
    resolve, only a default to apply.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty target")

    imdb_name = IMDB_NAME_RE.search(text)
    if imdb_name:
        return Target(text, media_type="person", imdb_id=imdb_name.group(1))
    imdb_title = IMDB_TITLE_RE.search(text)
    if imdb_title:
        # Media type stays None: only TMDB's /find can say whether a tt id is a
        # film or a series, and guessing would send half the run to /movie/0.
        return Target(text, media_type=None, imdb_id=imdb_title.group(1))

    if "://" in text or text.startswith(("themoviedb.org", "www.themoviedb.org")):
        url = text if "://" in text else "https://" + text
        parsed = urllib.parse.urlparse(url)
        segments = [s for s in parsed.path.split("/") if s]
        if segments and segments[0] in ("movie", "tv", "person", "collection", "company", "network"):
            kind = segments[0]
            # TMDB URLs are "/movie/27205-inception": the id is the numeric
            # head of the slug, and the words after the dash are decoration.
            ident = segments[1].split("-")[0] if len(segments) > 1 else ""
            if DIGITS_ONLY.match(ident):
                return Target(text, media_type=kind, tmdb_id=int(ident))
        raise ValueError(
            f"{text!r} is a URL this actor does not recognise. Use a "
            "themoviedb.org or imdb.com link, a bare IMDb id, or just the name."
        )

    prefixed = re.match(r"^(movie|tv|person|collection|company|network)\s*[:=/]\s*(\d+)$", text, re.I)
    if prefixed:
        return Target(text, media_type=prefixed.group(1).lower(), tmdb_id=int(prefixed.group(2)))

    if DIGITS_ONLY.match(text):
        return Target(text, media_type=default_media_type, tmdb_id=int(text))

    return Target(text, media_type=default_media_type, name_query=text)


async def lookup_by_imdb(client: TmdbClient, imdb_id: str) -> tuple[str, int]:
    """Resolve an IMDb id to a TMDB media type and id.

    This is the bridge that lets an actor built on TMDB answer an IMDb-shaped
    question. TMDB's /find returns one bucket per media type, all but one of
    them empty, so the first non-empty bucket is the answer.
    """
    payload = await client.get(f"/find/{imdb_id}", {"external_source": "imdb_id"})
    for bucket, media_type in (
        ("movie_results", "movie"),
        ("tv_results", "tv"),
        ("person_results", "person"),
        ("tv_episode_results", "tv_episode"),
        ("tv_season_results", "tv_season"),
    ):
        results = payload.get(bucket) or []
        if results and isinstance(results[0], dict) and results[0].get("id"):
            return media_type, int(results[0]["id"])
    raise TmdbNotFound(f"IMDb id {imdb_id} is not in TMDB")


async def lookup_by_name(
    client: TmdbClient, query: str, media_type: str | None
) -> tuple[str, int, str]:
    """Resolve a name to the best-matching TMDB record.

    `/search/multi` is used when no media type is known, because it ranks
    across films, series and people together -- searching /search/movie for
    "Breaking Bad" returns a 2011 short film, which is technically correct and
    entirely useless.
    """
    path = f"/search/{media_type}" if media_type in MEDIA_PATHS else "/search/multi"
    payload = await client.get(path, {"query": query, "include_adult": "false"})
    results = [r for r in (payload.get("results") or []) if isinstance(r, dict) and r.get("id")]
    if not results:
        raise TmdbNotFound(f"nothing on TMDB matches {query!r}")
    best = results[0]
    kind = best.get("media_type") or media_type or "movie"
    label = best.get("title") or best.get("name") or query
    return kind, int(best["id"]), label


async def resolve(
    client: TmdbClient, target: Target, default_media_type: str | None
) -> tuple[str, int, str | None]:
    """Turn any Target into (media_type, tmdb_id, resolved_label)."""
    if target.tmdb_id is not None:
        media_type = target.media_type or default_media_type or "movie"
        return media_type, target.tmdb_id, None
    if target.imdb_id:
        media_type, tmdb_id = await lookup_by_imdb(client, target.imdb_id)
        return media_type, tmdb_id, None
    if target.name_query:
        media_type, tmdb_id, label = await lookup_by_name(
            client, target.name_query, target.media_type or default_media_type
        )
        log.info("Resolved %r to %s %s (%s)", target.name_query, media_type, tmdb_id, label)
        return media_type, tmdb_id, label
    raise ValueError(f"cannot resolve {target.raw!r}")


# -- shared fetch helpers --------------------------------------------------

def _appends(opts: dict[str, Any], table: dict[str, str]) -> str:
    """Build append_to_response from the include* switches.

    TMDB allows up to 20 appended sub-requests per call and charges for one, so
    everything switched on travels in a single round trip. Switching all of
    them off is a legitimate choice: it makes a 500-title run return the core
    metadata at the lowest possible payload size.
    """
    parts: list[str] = []
    for option, appended in table.items():
        if opts.get(f"include{option[0].upper()}{option[1:]}", False):
            parts.extend(appended.split(","))
    # dict.fromkeys de-duplicates while keeping order, which matters because
    # `credits` appears in two entries of the TV table.
    return ",".join(dict.fromkeys(p for p in parts if p))


async def fetch_title(
    client: TmdbClient, media_type: str, tmdb_id: int, opts: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    """One movie or series, with every switched-on block appended."""
    table = TV_APPENDS if media_type == "tv" else MOVIE_APPENDS
    params: dict[str, Any] = {}
    appends = _appends(opts, table)
    if appends:
        params["append_to_response"] = appends
    if opts.get("includeImages"):
        # Without this, TMDB filters images to the run's language and a film
        # with no English-tagged poster comes back with an empty gallery.
        params["include_image_language"] = f"{(opts.get('language') or 'en')[:2]},null"
    path = f"/{media_type}/{tmdb_id}"
    payload = await client.get(path, params)
    return payload, client.redact(client.build_url(path, params))


def title_record(
    payload: dict[str, Any], media_type: str, opts: dict[str, Any], *,
    mode: str, source_url: str, query: str | None = None, rank: int | None = None,
) -> dict[str, Any]:
    data = parse_title(
        payload, media_type,
        region=opts.get("region"),
        max_cast=int(opts.get("maxCastMembers") or 0),
        include_full_crew=bool(opts.get("includeFullCrew")),
    )
    return record(
        media_type_item_type(media_type), f"{media_type}:{payload.get('id')}", data,
        mode=mode, source_url=source_url, query=query, rank=rank,
    )


def media_type_item_type(media_type: str) -> str:
    return {"movie": "title", "tv": "title", "person": "person"}.get(media_type, media_type)


async def paged(
    client: TmdbClient,
    path: str,
    params: dict[str, Any],
    *,
    max_pages: int,
    budget: Budget,
    label: str,
) -> AsyncIterator[tuple[dict[str, Any], int, int]]:
    """Walk a paged TMDB list, yielding (entry, page, rank).

    `rank` continues across pages, so row 21 of a Top Rated walk is rank 21 and
    not page 2 row 1 -- the number a buyer means by "position in the chart".

    Two ceilings are respected: TMDB refuses `page` above 500, and its
    `total_pages` is authoritative, so a request for 30 pages of a 3-page
    result set stops at 3 instead of spending 27 requests on empty responses.
    """
    rank = 0
    page = 1
    total_pages: int | None = None
    while page <= max_pages and page <= MAX_PAGE:
        if budget.exhausted:
            return
        payload = await client.get(path, {**params, "page": page})
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            if page == 1:
                log.info("%s returned no results", label)
            return
        if total_pages is None:
            total_pages = int(payload.get("total_pages") or 0) or None
            total_results = payload.get("total_results")
            log.info(
                "%s: %s result(s) across %s page(s); reading up to %d page(s)",
                label, total_results, total_pages, min(max_pages, total_pages or max_pages),
            )
        for entry in results:
            if not isinstance(entry, dict):
                continue
            rank += 1
            yield entry, page, rank
            if budget.exhausted:
                return
        if total_pages is not None and page >= total_pages:
            return
        page += 1


# -- mode: titleDetails ----------------------------------------------------

async def mode_title_details(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    default_type = opts.get("defaultMediaType") or "movie"
    for raw in opts["titleTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw, default_type)
            media_type, tmdb_id, _ = await resolve(client, target, default_type)
        except (ValueError, TmdbNotFound) as exc:
            yield error_record(raw, "unresolvable_target", str(exc), mode="titleDetails")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="titleDetails")
            continue

        if media_type == "person":
            yield error_record(
                raw, "wrong_media_type",
                f"{raw} is a person, not a title. Run it through the "
                "personDetails mode instead.",
                mode="titleDetails",
            )
            continue
        if media_type not in ("movie", "tv"):
            media_type = default_type

        try:
            payload, source = await fetch_title(client, media_type, tmdb_id, opts)
        except TmdbNotFound:
            yield error_record(
                raw, "not_found",
                f"no {media_type} with TMDB id {tmdb_id}",
                mode="titleDetails",
            )
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="titleDetails")
            continue

        budget.take()
        yield title_record(
            payload, media_type, opts,
            mode="titleDetails", source_url=source, query=raw,
        )


# -- mode: personDetails ---------------------------------------------------

async def mode_person_details(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["personTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw, "person")
            media_type, tmdb_id, _ = await resolve(client, target, "person")
        except (ValueError, TmdbNotFound) as exc:
            yield error_record(raw, "unresolvable_target", str(exc), mode="personDetails")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="personDetails")
            continue

        if media_type != "person":
            yield error_record(
                raw, "wrong_media_type",
                f"{raw} resolved to a {media_type}, not a person. Run it "
                "through the titleDetails mode instead.",
                mode="personDetails",
            )
            continue

        params: dict[str, Any] = {}
        appends = _appends(opts, PERSON_APPENDS)
        if appends:
            params["append_to_response"] = appends
        path = f"/person/{tmdb_id}"
        try:
            payload = await client.get(path, params)
        except TmdbNotFound:
            yield error_record(raw, "not_found", f"no person with TMDB id {tmdb_id}", mode="personDetails")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="personDetails")
            continue

        data = parse_person(payload, max_credits=int(opts.get("maxCreditsPerPerson") or 0))
        budget.take()
        yield record(
            "person", f"person:{payload.get('id')}", data,
            mode="personDetails",
            source_url=client.redact(client.build_url(path, params)),
            query=raw,
        )


# -- mode: seasonEpisodes --------------------------------------------------

def _wanted_seasons(opts: dict[str, Any], available: list[dict[str, Any]]) -> list[int]:
    """Which season numbers to pull.

    Season 0 is TMDB's "Specials" bucket and is excluded unless it is asked for
    by number, because a buyer who asks for "every season of this show" and
    gets Christmas specials interleaved by air date usually did not mean that.
    """
    requested = [int(s) for s in as_strings(opts.get("seasons")) if s.lstrip("-").isdigit()]
    if requested:
        return requested
    numbers = [
        int(s["season_number"]) for s in available
        if isinstance(s, dict) and s.get("season_number") is not None
    ]
    return [n for n in numbers if n > 0] or numbers


async def mode_season_episodes(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["tvTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw, "tv")
            media_type, tmdb_id, _ = await resolve(client, target, "tv")
        except (ValueError, TmdbNotFound) as exc:
            yield error_record(raw, "unresolvable_target", str(exc), mode="seasonEpisodes")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="seasonEpisodes")
            continue

        if media_type != "tv":
            yield error_record(
                raw, "wrong_media_type",
                f"{raw} resolved to a {media_type}. Episodes exist only for "
                "TV series; use titleDetails for films.",
                mode="seasonEpisodes",
            )
            continue

        try:
            series = await client.get(f"/tv/{tmdb_id}", {})
        except TmdbNotFound:
            yield error_record(raw, "not_found", f"no series with TMDB id {tmdb_id}", mode="seasonEpisodes")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="seasonEpisodes")
            continue

        series_name = series.get("name")
        seasons = _wanted_seasons(opts, series.get("seasons") or [])
        if not seasons:
            yield error_record(
                raw, "no_seasons",
                f"{series_name or tmdb_id} has no seasons listed on TMDB",
                mode="seasonEpisodes",
            )
            continue
        log.info(
            "%s (TMDB %s): pulling %d season(s): %s",
            series_name, tmdb_id, len(seasons), ", ".join(str(s) for s in seasons),
        )

        for season_no in seasons:
            if budget.exhausted:
                return
            params: dict[str, Any] = {}
            appends = _appends(opts, SEASON_APPENDS)
            if appends:
                params["append_to_response"] = appends
            path = f"/tv/{tmdb_id}/season/{season_no}"
            try:
                payload = await client.get(path, params)
            except TmdbNotFound:
                yield error_record(
                    raw, "season_not_found",
                    f"{series_name or tmdb_id} has no season {season_no}",
                    mode="seasonEpisodes", parent_id=f"tv:{tmdb_id}",
                )
                continue
            except TmdbBlocked as exc:
                yield error_record(
                    raw, "fetch_failed", str(exc),
                    mode="seasonEpisodes", parent_id=f"tv:{tmdb_id}",
                )
                continue

            source = client.redact(client.build_url(path, params))
            if opts.get("includeSeasonRecords", True):
                budget.take()
                yield record(
                    "season", f"tv:{tmdb_id}:s{season_no}",
                    parse_season(payload, series_id=tmdb_id, series_name=series_name),
                    mode="seasonEpisodes", source_url=source,
                    query=raw, parent_id=f"tv:{tmdb_id}",
                )

            for episode in payload.get("episodes") or []:
                if budget.exhausted:
                    return
                if not isinstance(episode, dict):
                    continue
                data = parse_episode(
                    episode, series_id=tmdb_id, series_name=series_name,
                    max_cast=int(opts.get("maxCastMembers") or 0),
                )
                budget.take()
                yield record(
                    "episode",
                    f"tv:{tmdb_id}:s{season_no}:e{episode.get('episode_number')}",
                    data, mode="seasonEpisodes", source_url=source,
                    query=raw, parent_id=f"tv:{tmdb_id}:s{season_no}",
                )


# -- mode: titleReviews ----------------------------------------------------

async def mode_title_reviews(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    default_type = opts.get("defaultMediaType") or "movie"
    max_pages = int(opts.get("maxPagesPerTarget") or 5)
    for raw in opts["titleTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw, default_type)
            media_type, tmdb_id, label = await resolve(client, target, default_type)
        except (ValueError, TmdbNotFound) as exc:
            yield error_record(raw, "unresolvable_target", str(exc), mode="titleReviews")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="titleReviews")
            continue

        if media_type not in ("movie", "tv"):
            yield error_record(
                raw, "wrong_media_type",
                f"{raw} resolved to a {media_type}; reviews exist for films "
                "and series only.",
                mode="titleReviews",
            )
            continue

        path = f"/{media_type}/{tmdb_id}/reviews"
        found = 0
        try:
            async for entry, page, rank in paged(
                client, path, {}, max_pages=max_pages, budget=budget,
                label=f"reviews of {label or raw}",
            ):
                data = parse_review(
                    entry, media_type=media_type, parent_id=tmdb_id, parent_title=label,
                )
                found += 1
                budget.take()
                yield record(
                    "review", f"review:{entry.get('id')}", data,
                    mode="titleReviews",
                    source_url=client.redact(client.build_url(path, {"page": page})),
                    query=raw, rank=rank, page=page, parent_id=f"{media_type}:{tmdb_id}",
                )
        except TmdbNotFound:
            yield error_record(raw, "not_found", f"no {media_type} {tmdb_id}", mode="titleReviews")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="titleReviews")
            continue

        if found == 0:
            # Worth an explicit row: TMDB carries far fewer reviews than IMDb,
            # and a silent empty result reads like a broken run.
            yield error_record(
                raw, "no_reviews",
                f"TMDB holds no user reviews for {label or raw}. Its review "
                "corpus is much smaller than IMDb's; popular recent releases "
                "have them, catalogue titles often do not.",
                mode="titleReviews", parent_id=f"{media_type}:{tmdb_id}",
            )


# -- mode: discoverTitles --------------------------------------------------

async def _genre_ids(
    client: TmdbClient, names: list[str], media_type: str
) -> tuple[list[int], list[str]]:
    """Map genre names to TMDB ids, falling back to the live list.

    The inlined table covers every genre TMDB currently publishes, so the live
    call almost never fires; it exists so that a genre added next year resolves
    instead of silently dropping the filter and returning the whole catalogue.
    """
    table = TV_GENRES if media_type == "tv" else MOVIE_GENRES
    ids: list[int] = []
    unknown: list[str] = []
    for name in names:
        text = name.strip()
        if DIGITS_ONLY.match(text):
            ids.append(int(text))
            continue
        found = table.get(text.lower())
        if found:
            ids.append(found)
        else:
            unknown.append(text)
    if unknown:
        try:
            payload = await client.get(f"/genre/{media_type}/list", {})
            live = {
                str(g.get("name", "")).lower(): g.get("id")
                for g in payload.get("genres") or [] if isinstance(g, dict)
            }
        except (TmdbNotFound, TmdbBlocked):
            live = {}
        still_unknown = []
        for name in unknown:
            found = live.get(name.lower())
            if found:
                ids.append(int(found))
            else:
                still_unknown.append(name)
        unknown = still_unknown
    return ids, unknown


async def build_discover_params(
    client: TmdbClient, opts: dict[str, Any], media_type: str
) -> tuple[dict[str, Any], list[str]]:
    """Translate the plain-language filters into TMDB's discover parameters.

    The date parameter is the one that has to be chosen by media type: a film
    is filtered on `primary_release_date`, a series on `first_air_date`, and
    sending a film's parameter to /discover/tv is silently ignored rather than
    rejected -- which looks exactly like a year filter that does not work.
    """
    params: dict[str, Any] = {}
    notes: list[str] = []
    is_tv = media_type == "tv"

    genres = as_strings(opts.get("genres"))
    if genres:
        ids, unknown = await _genre_ids(client, genres, media_type)
        if ids:
            joiner = "," if str(opts.get("genreMatch") or "any").lower() == "all" else "|"
            params["with_genres"] = joiner.join(str(i) for i in ids)
        if unknown:
            notes.append(
                f"ignored unknown genre(s): {', '.join(unknown)}. Valid "
                f"{media_type} genres: {', '.join(sorted(set(TV_GENRES if is_tv else MOVIE_GENRES)))}"
            )

    date_field = "first_air_date" if is_tv else "primary_release_date"
    year_from, year_to = opts.get("yearFrom"), opts.get("yearTo")
    if year_from:
        params[f"{date_field}.gte"] = f"{int(year_from)}-01-01"
    if year_to:
        params[f"{date_field}.lte"] = f"{int(year_to)}-12-31"

    if opts.get("minRating") not in (None, ""):
        params["vote_average.gte"] = opts["minRating"]
    if opts.get("maxRating") not in (None, ""):
        params["vote_average.lte"] = opts["maxRating"]
    if opts.get("minVotes") not in (None, ""):
        params["vote_count.gte"] = opts["minVotes"]
    if opts.get("minRuntime") not in (None, ""):
        params["with_runtime.gte"] = opts["minRuntime"]
    if opts.get("maxRuntime") not in (None, ""):
        params["with_runtime.lte"] = opts["maxRuntime"]

    if opts.get("sortBy"):
        params["sort_by"] = opts["sortBy"]
    if opts.get("withOriginalLanguage"):
        params["with_original_language"] = opts["withOriginalLanguage"]
    params["include_adult"] = "true" if opts.get("includeAdult") else "false"

    for field, param in (
        ("withCompanies", "with_companies"),
        ("withKeywords", "with_keywords"),
        ("withPeople", "with_people"),
        ("withNetworks", "with_networks"),
        ("withWatchProviders", "with_watch_providers"),
    ):
        values = as_strings(opts.get(field))
        if not values:
            continue
        if param in ("with_people", "with_networks") and is_tv != (param == "with_networks"):
            # with_people is movie-only, with_networks is tv-only.
            notes.append(f"ignored {field}: it applies to {'series' if param == 'with_networks' else 'films'} only")
            continue
        params[param] = "|".join(values)

    if params.get("with_watch_providers"):
        region = opts.get("watchRegion") or opts.get("region") or "US"
        params["watch_region"] = region

    extra = opts.get("extraQueryParams")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value not in (None, ""):
                params[str(key)] = value

    return params, notes


async def mode_discover_titles(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    media_type = "tv" if str(opts.get("discoverMediaType") or "movie").lower() == "tv" else "movie"
    max_pages = int(opts.get("maxPagesPerTarget") or 5)
    params, notes = await build_discover_params(client, opts, media_type)
    for note in notes:
        log.warning("discoverTitles: %s", note)

    path = f"/discover/{media_type}"
    log.info(
        "Discover %s with %s; up to %d page(s) = %d titles",
        media_type,
        ", ".join(f"{k}={v}" for k, v in sorted(params.items())) or "no filters",
        max_pages, max_pages * RESULTS_PER_PAGE,
    )

    emitted = 0
    try:
        async for entry, page, rank in paged(
            client, path, params, max_pages=max_pages, budget=budget,
            label=f"discover/{media_type}",
        ):
            emitted += 1
            async for row in _emit_list_entry(
                client, entry, media_type, opts, budget,
                mode="discoverTitles", item_type="discover_result",
                source_url=client.redact(client.build_url(path, {**params, "page": page})),
                query=None, rank=rank, page=page,
            ):
                yield row
    except (TmdbNotFound, TmdbBlocked) as exc:
        yield error_record(f"discover/{media_type}", "fetch_failed", str(exc), mode="discoverTitles")
        return

    if emitted == 0:
        yield error_record(
            f"discover/{media_type}", "no_results",
            "No titles matched those filters. The usual cause is a minimum "
            "vote count combined with a narrow year range, or a genre that "
            "does not exist for this media type.",
            mode="discoverTitles",
        )


async def _emit_list_entry(
    client: TmdbClient,
    entry: dict[str, Any],
    media_type_hint: str | None,
    opts: dict[str, Any],
    budget: Budget,
    *,
    mode: str,
    item_type: str,
    source_url: str,
    query: str | None,
    rank: int | None,
    page: int | None,
) -> AsyncIterator[dict[str, Any]]:
    """Emit one list row, optionally upgraded to a full detail record.

    `fetchFullDetails` is the switch that turns any list mode into a bulk
    extractor: the thin 15-field row becomes the same record titleDetails
    would have produced. It costs exactly one extra request per row, which is
    why it is off by default and why the log says what it is about to spend.
    """
    media_type = entry.get("media_type") or media_type_hint or "movie"

    if opts.get("fetchFullDetails") and media_type in ("movie", "tv", "person"):
        tmdb_id = entry.get("id")
        try:
            if media_type == "person":
                params: dict[str, Any] = {}
                appends = _appends(opts, PERSON_APPENDS)
                if appends:
                    params["append_to_response"] = appends
                payload = await client.get(f"/person/{tmdb_id}", params)
                data = parse_person(payload, max_credits=int(opts.get("maxCreditsPerPerson") or 0))
                budget.take()
                yield record(
                    "person", f"person:{tmdb_id}", data, mode=mode,
                    source_url=client.redact(client.build_url(f"/person/{tmdb_id}", params)),
                    query=query, rank=rank, page=page,
                )
                return
            payload, source = await fetch_title(client, media_type, int(tmdb_id), opts)
            budget.take()
            yield title_record(
                payload, media_type, opts, mode=mode,
                source_url=source, query=query, rank=rank,
            )
            return
        except (TmdbNotFound, TmdbBlocked) as exc:
            # Fall through to the thin row rather than losing it: a detail call
            # that fails should cost detail, not the whole result.
            log.warning(
                "Full details failed for %s %s (%s); keeping the list row",
                media_type, entry.get("id"), exc,
            )

    budget.take()
    yield record(
        media_type_item_type(media_type) if item_type == "detail" else item_type,
        f"{media_type}:{entry.get('id')}",
        parse_list_entry(entry, media_type_hint),
        mode=mode, source_url=source_url, query=query, rank=rank, page=page,
    )


# -- mode: searchByName ----------------------------------------------------

async def mode_search_by_name(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    kind = str(opts.get("searchMediaType") or "multi").lower()
    path = f"/search/{kind}" if kind in ("movie", "tv", "person", "multi", "collection", "company") else "/search/multi"
    max_pages = int(opts.get("maxPagesPerTarget") or 3)
    hint = kind if kind in MEDIA_PATHS else None

    for query in opts["searchQueries"]:
        if budget.exhausted:
            return
        params: dict[str, Any] = {
            "query": query,
            "include_adult": "true" if opts.get("includeAdult") else "false",
        }
        if opts.get("yearFrom") and kind == "movie":
            params["primary_release_year"] = int(opts["yearFrom"])
        found = 0
        try:
            async for entry, page, rank in paged(
                client, path, params, max_pages=max_pages, budget=budget,
                label=f"search {kind} {query!r}",
            ):
                found += 1
                if kind in ("collection", "company"):
                    budget.take()
                    parsed = (
                        parse_collection(entry) if kind == "collection"
                        else parse_company(entry)
                    )
                    yield record(
                        kind, f"{kind}:{entry.get('id')}", parsed,
                        mode="searchByName",
                        source_url=client.redact(client.build_url(path, {**params, "page": page})),
                        query=query, rank=rank, page=page,
                    )
                    continue
                async for row in _emit_list_entry(
                    client, entry, hint, opts, budget,
                    mode="searchByName", item_type="search_result",
                    source_url=client.redact(client.build_url(path, {**params, "page": page})),
                    query=query, rank=rank, page=page,
                ):
                    yield row
        except (TmdbNotFound, TmdbBlocked) as exc:
            yield error_record(query, "fetch_failed", str(exc), mode="searchByName")
            continue
        if found == 0:
            yield error_record(
                query, "no_results", f"nothing on TMDB matches {query!r}",
                mode="searchByName",
            )


# -- mode: charts ----------------------------------------------------------

async def mode_charts(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    names = opts.get("chartNames") or ["topRatedMovies"]
    max_pages = int(opts.get("maxPagesPerTarget") or 5)
    for name in names:
        if budget.exhausted:
            return
        entry_spec = CHARTS.get(name)
        if not entry_spec:
            yield error_record(
                name, "unknown_chart",
                f"{name!r} is not a chart this actor publishes. Valid names: "
                + ", ".join(sorted(CHARTS)),
                mode="charts",
            )
            continue
        path, media_hint = entry_spec
        hint = media_hint if media_hint in MEDIA_PATHS else None
        try:
            async for entry, page, rank in paged(
                client, path, {}, max_pages=max_pages, budget=budget, label=name,
            ):
                async for row in _emit_list_entry(
                    client, entry, hint, opts, budget,
                    mode="charts", item_type="chart_entry",
                    source_url=client.redact(client.build_url(path, {"page": page})),
                    query=name, rank=rank, page=page,
                ):
                    row["metadata"]["chart"] = name
                    yield row
        except (TmdbNotFound, TmdbBlocked) as exc:
            yield error_record(name, "fetch_failed", str(exc), mode="charts")
            continue


# -- mode: collectionTitles ------------------------------------------------

async def mode_collection_titles(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["collectionTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw, "collection")
        except ValueError as exc:
            yield error_record(raw, "unresolvable_target", str(exc), mode="collectionTitles")
            continue

        collection_id = target.tmdb_id if target.media_type == "collection" else None
        try:
            if collection_id is None and target.media_type in ("movie", None) and target.tmdb_id:
                # A film was given: read its franchise off the film itself.
                payload = await client.get(f"/movie/{target.tmdb_id}", {})
                belongs = payload.get("belongs_to_collection")
                if not isinstance(belongs, dict) or not belongs.get("id"):
                    yield error_record(
                        raw, "no_collection",
                        f"{payload.get('title') or raw} does not belong to a "
                        "TMDB collection - it is a standalone film.",
                        mode="collectionTitles",
                    )
                    continue
                collection_id = int(belongs["id"])
            elif collection_id is None:
                search = await client.get("/search/collection", {"query": target.name_query or raw})
                results = [r for r in (search.get("results") or []) if isinstance(r, dict)]
                if not results:
                    yield error_record(
                        raw, "not_found",
                        f"no TMDB collection matches {raw!r}. Collections are "
                        "named like 'The Dark Knight Collection'.",
                        mode="collectionTitles",
                    )
                    continue
                collection_id = int(results[0]["id"])

            path = f"/collection/{collection_id}"
            payload = await client.get(path, {})
        except TmdbNotFound:
            yield error_record(raw, "not_found", f"no collection {collection_id}", mode="collectionTitles")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="collectionTitles")
            continue

        source = client.redact(client.build_url(path, {}))
        data = parse_collection(payload)
        budget.take()
        yield record(
            "collection", f"collection:{collection_id}", data,
            mode="collectionTitles", source_url=source, query=raw,
        )

        if not opts.get("includeCollectionParts", True):
            continue
        for rank, part in enumerate(payload.get("parts") or [], start=1):
            if budget.exhausted:
                return
            if not isinstance(part, dict):
                continue
            async for row in _emit_list_entry(
                client, part, "movie", opts, budget,
                mode="collectionTitles", item_type="discover_result",
                source_url=source, query=raw, rank=rank, page=None,
            ):
                row["metadata"]["parentId"] = f"collection:{collection_id}"
                yield row


# -- mode: companyProfile --------------------------------------------------

async def mode_company_profile(
    client: TmdbClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    max_pages = int(opts.get("maxPagesPerTarget") or 3)
    for raw in opts["companyTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw, "company")
        except ValueError as exc:
            yield error_record(raw, "unresolvable_target", str(exc), mode="companyProfile")
            continue

        kind = target.media_type if target.media_type in ("company", "network") else "company"
        company_id = target.tmdb_id
        try:
            if company_id is None:
                if kind == "network":
                    yield error_record(
                        raw, "unsupported_input",
                        "TMDB publishes no network search endpoint. Give a "
                        "network id as network:49, or the network's TMDB URL.",
                        mode="companyProfile",
                    )
                    continue
                search = await client.get("/search/company", {"query": target.name_query or raw})
                results = [r for r in (search.get("results") or []) if isinstance(r, dict)]
                if not results:
                    yield error_record(raw, "not_found", f"no company matches {raw!r}", mode="companyProfile")
                    continue
                company_id = int(results[0]["id"])
            path = f"/{kind}/{company_id}"
            payload = await client.get(path, {})
        except TmdbNotFound:
            yield error_record(raw, "not_found", f"no {kind} {company_id}", mode="companyProfile")
            continue
        except TmdbBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="companyProfile")
            continue

        source = client.redact(client.build_url(path, {}))
        budget.take()
        yield record(
            "company", f"{kind}:{company_id}", parse_company(payload, kind),
            mode="companyProfile", source_url=source, query=raw,
        )

        if not opts.get("includeCompanyTitles"):
            continue
        # A network's catalogue lives on /discover/tv, a company's on both.
        searches = (
            [("tv", {"with_networks": str(company_id)})] if kind == "network"
            else [("movie", {"with_companies": str(company_id)}),
                  ("tv", {"with_companies": str(company_id)})]
        )
        for media_type, filters in searches:
            if budget.exhausted:
                return
            discover_path = f"/discover/{media_type}"
            params = {**filters, "sort_by": opts.get("sortBy") or "popularity.desc"}
            try:
                async for entry, page, rank in paged(
                    client, discover_path, params, max_pages=max_pages, budget=budget,
                    label=f"{kind} {company_id} {media_type} catalogue",
                ):
                    async for row in _emit_list_entry(
                        client, entry, media_type, opts, budget,
                        mode="companyProfile", item_type="discover_result",
                        source_url=client.redact(client.build_url(discover_path, {**params, "page": page})),
                        query=raw, rank=rank, page=page,
                    ):
                        row["metadata"]["parentId"] = f"{kind}:{company_id}"
                        yield row
            except (TmdbNotFound, TmdbBlocked) as exc:
                yield error_record(raw, "fetch_failed", str(exc), mode="companyProfile")
                continue


ModeFn = Callable[[TmdbClient, dict[str, Any], Budget], AsyncIterator[dict[str, Any]]]

MODES: dict[str, ModeFn] = {
    "titleDetails": mode_title_details,
    "personDetails": mode_person_details,
    "seasonEpisodes": mode_season_episodes,
    "titleReviews": mode_title_reviews,
    "discoverTitles": mode_discover_titles,
    "searchByName": mode_search_by_name,
    "charts": mode_charts,
    "collectionTitles": mode_collection_titles,
    "companyProfile": mode_company_profile,
}

# Which input array each mode cannot run without. discoverTitles and charts are
# absent because both have meaningful defaults: an unfiltered discover walk and
# the Top Rated chart.
MODE_REQUIRED_INPUT: dict[str, tuple[str, ...]] = {
    "titleDetails": ("titleTargets",),
    "personDetails": ("personTargets",),
    "seasonEpisodes": ("tvTargets",),
    "titleReviews": ("titleTargets",),
    "searchByName": ("searchQueries",),
    "collectionTitles": ("collectionTargets",),
    "companyProfile": ("companyTargets",),
}
