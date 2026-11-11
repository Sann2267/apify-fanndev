"""Turn TMDB's raw payloads into the flat records this actor publishes.

Every record leaves here in one envelope -- item_type, id, data, metadata --
so a single dataset can hold movies, shows, people, episodes, reviews, chart
rows, collections, companies and diagnostics and still be joined on `id`.

Four normalisations are applied everywhere and are worth stating once:

* Image paths become URLs. TMDB publishes `poster_path: "/abc.jpg"`, which is
  useless on its own: it has to be joined to a CDN host and a size token. That
  join happens here, once, so no buyer has to learn TMDB's image scheme.
* Money gets its derived fields. `budget` and `revenue` are both published, so
  profit and return-on-budget are computed rather than left as homework -- and
  a zero in either field is turned into null, because TMDB uses 0 to mean
  "nobody has entered this", not "this film earned nothing".
* Credits are split by function. A raw crew array is 200 rows of mixed jobs;
  what a buyer wants is `directors`, `writers`, `producers`. Those are lifted
  out by job title and the full array is kept only when it is asked for.
* snake_case becomes camelCase. TMDB is snake_case throughout; the rest of
  this portfolio publishes camelCase, and a dataset that mixes both is a
  dataset every downstream join gets wrong at least once.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from .constants import DEFAULT_IMAGE_SIZE, IMAGE_ROOT, SITE_ROOT

# Set once per run from the `imageSize` input. TMDB's own /configuration
# endpoint publishes the valid size tokens; `original` is always valid and is
# what this falls back to.
_IMAGE_SIZE = DEFAULT_IMAGE_SIZE

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")

DIRECTOR_JOBS = {"director"}
WRITER_JOBS = {"writer", "screenplay", "story", "novel", "author", "teleplay"}
PRODUCER_JOBS = {"producer", "executive producer", "co-producer", "line producer"}
COMPOSER_JOBS = {"original music composer", "composer", "music"}
DOP_JOBS = {"director of photography", "cinematography"}
EDITOR_JOBS = {"editor", "film editor"}


def configure(image_size: str | None) -> None:
    """Pin the image size for the whole run."""
    global _IMAGE_SIZE
    _IMAGE_SIZE = (image_size or DEFAULT_IMAGE_SIZE).strip() or DEFAULT_IMAGE_SIZE


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def image_url(path: Any, size: str | None = None) -> str | None:
    """Expand a TMDB image path into a URL, or pass an existing URL through."""
    if not path:
        return None
    text = str(path)
    if text.startswith(("http://", "https://")):
        return text
    return f"{IMAGE_ROOT}/{size or _IMAGE_SIZE}/{text.lstrip('/')}"


def clean_text(value: Any) -> str | None:
    """Flatten a text field to something an LLM can read without pre-cleaning.

    TMDB overviews and biographies are plain text, but user reviews are not:
    they arrive with raw HTML, stray entities and Windows line endings pasted
    in from wherever the reviewer wrote them. Stripping that here is the whole
    point of the RAG-ready output -- a buyer feeding this into a prompt should
    never have to run their own sanitiser first.
    """
    if value is None:
        return None
    text = str(value)
    if "<" in text and ">" in text:
        text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    text = _WS_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def _money(value: Any) -> int | None:
    """TMDB writes 0 for "unknown", which is not the same as zero dollars."""
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _year(date_str: Any) -> int | None:
    text = str(date_str or "")[:4]
    return int(text) if text.isdigit() else None


def _names(items: Any, key: str = "name") -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(i.get(key)) for i in items if isinstance(i, dict) and i.get(key)]


def _ids(items: Any) -> list[int]:
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if isinstance(item, dict) and item.get("id") is not None:
            try:
                out.append(int(item["id"]))
            except (TypeError, ValueError):
                continue
    return out


def record(
    item_type: str,
    record_id: Any,
    data: dict[str, Any],
    *,
    mode: str,
    source_url: str | None = None,
    query: str | None = None,
    rank: int | None = None,
    page: int | None = None,
    parent_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "scrapedAt": now_iso(),
        "sourceUrl": source_url,
        "mode": mode,
    }
    if query is not None:
        meta["query"] = query
    if rank is not None:
        meta["rank"] = rank
    if page is not None:
        meta["page"] = page
    if parent_id is not None:
        meta["parentId"] = parent_id
    if extra_meta:
        meta.update(extra_meta)
    return {
        "item_type": item_type,
        "id": None if record_id is None else str(record_id),
        "data": data,
        "metadata": meta,
    }


def error_record(
    subject: str, kind: str, detail: str = "", *, mode: str = "", **meta: Any
) -> dict[str, Any]:
    """A diagnostic row.

    The run never finishes with an empty dataset: a buyer joining on this
    output reads "no rows" as a crash, while an error row says exactly which
    input failed and why.
    """
    return record(
        "error",
        None,
        {"_error": kind, "_errorDetail": detail, "_input": subject},
        mode=mode,
        **meta,
    )


# -- credits ---------------------------------------------------------------

def _person_stub(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "personId": entry.get("id"),
        "name": entry.get("name"),
        "originalName": entry.get("original_name"),
        "profileUrl": image_url(entry.get("profile_path")),
        "tmdbUrl": f"{SITE_ROOT}/person/{entry.get('id')}" if entry.get("id") else None,
    }


def parse_cast(cast: Any, limit: int = 0) -> list[dict[str, Any]]:
    """Normalise a cast array from either `credits` or `aggregate_credits`.

    The two differ in one load-bearing way. A movie's cast entry has a single
    `character`; a series' aggregate cast entry has a `roles` array, because
    one actor can play several parts across seasons, plus the episode count
    that tells you who is a lead and who appeared once. Both are flattened to
    the same shape so a mixed dataset stays joinable.
    """
    if not isinstance(cast, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in cast:
        if not isinstance(entry, dict):
            continue
        roles = entry.get("roles")
        if isinstance(roles, list) and roles:
            characters = [str(r.get("character")) for r in roles if isinstance(r, dict) and r.get("character")]
            episode_count = entry.get("total_episode_count")
        else:
            characters = [str(entry["character"])] if entry.get("character") else []
            episode_count = entry.get("episode_count")
        row = _person_stub(entry)
        row.update({
            "character": characters[0] if characters else None,
            "characters": characters,
            "order": entry.get("order"),
            "episodeCount": episode_count,
            "creditId": entry.get("credit_id"),
        })
        out.append(row)
        if limit and len(out) >= limit:
            break
    return out


def _crew_jobs(entry: dict[str, Any]) -> list[str]:
    """Aggregate crew entries carry a `jobs` array; plain ones carry `job`."""
    jobs = entry.get("jobs")
    if isinstance(jobs, list) and jobs:
        return [str(j.get("job")) for j in jobs if isinstance(j, dict) and j.get("job")]
    return [str(entry["job"])] if entry.get("job") else []


def parse_crew(crew: Any) -> dict[str, Any]:
    """Split a crew array into the roles buyers actually filter on."""
    buckets: dict[str, list[str]] = {
        "directors": [], "writers": [], "producers": [],
        "composers": [], "cinematographers": [], "editors": [],
    }
    full: list[dict[str, Any]] = []
    if not isinstance(crew, list):
        return {**buckets, "crew": full}

    for entry in crew:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        jobs = _crew_jobs(entry)
        row = _person_stub(entry)
        row.update({
            "job": jobs[0] if jobs else None,
            "jobs": jobs,
            "department": entry.get("known_for_department") or entry.get("department"),
            "creditId": entry.get("credit_id"),
        })
        full.append(row)
        if not name:
            continue
        for job in jobs:
            low = job.lower()
            if low in DIRECTOR_JOBS and name not in buckets["directors"]:
                buckets["directors"].append(name)
            elif low in WRITER_JOBS and name not in buckets["writers"]:
                buckets["writers"].append(name)
            elif low in PRODUCER_JOBS and name not in buckets["producers"]:
                buckets["producers"].append(name)
            elif low in COMPOSER_JOBS and name not in buckets["composers"]:
                buckets["composers"].append(name)
            elif low in DOP_JOBS and name not in buckets["cinematographers"]:
                buckets["cinematographers"].append(name)
            elif low in EDITOR_JOBS and name not in buckets["editors"]:
                buckets["editors"].append(name)
    return {**buckets, "crew": full}


# -- appended sub-payloads -------------------------------------------------

def parse_external_ids(payload: Any) -> dict[str, Any]:
    """Every official handle TMDB holds for a title or a person.

    This is the closest thing in TMDB to the contact data an all-in-one
    extractor is usually asked for: it is the subject's own public IMDb page,
    homepage and social accounts, published by TMDB for that purpose. No
    private contact detail exists in this API and none is synthesised here.
    """
    if not isinstance(payload, dict):
        return {}
    handles = {
        "imdbId": payload.get("imdb_id"),
        "wikidataId": payload.get("wikidata_id"),
        "facebookId": payload.get("facebook_id"),
        "instagramId": payload.get("instagram_id"),
        "twitterId": payload.get("twitter_id"),
        "tiktokId": payload.get("tiktok_id"),
        "youtubeId": payload.get("youtube_id"),
        "tvdbId": payload.get("tvdb_id"),
        "freebaseMid": payload.get("freebase_mid"),
    }
    urls = {}
    if handles.get("imdbId"):
        kind = "name" if str(handles["imdbId"]).startswith("nm") else "title"
        urls["imdbUrl"] = f"https://www.imdb.com/{kind}/{handles['imdbId']}/"
    if handles.get("instagramId"):
        urls["instagramUrl"] = f"https://www.instagram.com/{handles['instagramId']}/"
    if handles.get("twitterId"):
        urls["twitterUrl"] = f"https://x.com/{handles['twitterId']}"
    if handles.get("facebookId"):
        urls["facebookUrl"] = f"https://www.facebook.com/{handles['facebookId']}"
    if handles.get("tiktokId"):
        urls["tiktokUrl"] = f"https://www.tiktok.com/@{handles['tiktokId']}"
    return {k: v for k, v in {**handles, **urls}.items() if v}


def parse_videos(payload: Any) -> dict[str, Any]:
    """Trailers and clips, with the main trailer lifted to the top.

    TMDB returns them newest-first, not most-important-first, so the one a
    buyer means by "the trailer" is picked out explicitly: an official YouTube
    trailer if there is one, else any trailer, else nothing.
    """
    results = (payload or {}).get("results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        return {"videos": [], "trailerUrl": None}
    videos = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        site = str(entry.get("site") or "")
        key = entry.get("key")
        url = None
        if key and site.lower() == "youtube":
            url = f"https://www.youtube.com/watch?v={key}"
        elif key and site.lower() == "vimeo":
            url = f"https://vimeo.com/{key}"
        videos.append({
            "name": entry.get("name"),
            "type": entry.get("type"),
            "site": entry.get("site"),
            "url": url,
            "isOfficial": entry.get("official"),
            "publishedAt": entry.get("published_at"),
            "size": entry.get("size"),
        })
    trailer = next(
        (v["url"] for v in videos if v["type"] == "Trailer" and v["isOfficial"] and v["url"]),
        None,
    ) or next((v["url"] for v in videos if v["type"] == "Trailer" and v["url"]), None)
    return {"videos": videos, "trailerUrl": trailer}


def parse_images(payload: Any, per_kind: int = 10) -> dict[str, Any]:
    """Poster, backdrop and logo URLs, highest-rated first.

    Capped per kind because a popular film carries several hundred posters and
    nobody wants 300 URLs in a dataset cell.
    """
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for tmdb_key, our_key in (
        ("posters", "posterUrls"), ("backdrops", "backdropUrls"),
        ("logos", "logoUrls"), ("profiles", "profileUrls"),
        ("stills", "stillUrls"),
    ):
        entries = payload.get(tmdb_key)
        if not isinstance(entries, list) or not entries:
            continue
        ranked = sorted(
            (e for e in entries if isinstance(e, dict)),
            key=lambda e: (e.get("vote_average") or 0, e.get("vote_count") or 0),
            reverse=True,
        )
        out[our_key] = [image_url(e.get("file_path")) for e in ranked[:per_kind] if e.get("file_path")]
    return out


def parse_watch_providers(payload: Any, region: str | None) -> dict[str, Any]:
    """Where a title can legally be streamed, rented or bought.

    TMDB returns every country at once. A buyer almost always wants one, so the
    requested region is flattened to the top and the rest is kept as a country
    list rather than a wall of nested objects.
    """
    results = (payload or {}).get("results") if isinstance(payload, dict) else None
    if not isinstance(results, dict) or not results:
        return {"watchRegions": [], "watchProviders": {}}
    country = (region or "US").upper()
    block = results.get(country) or {}
    flat: dict[str, Any] = {"watchRegion": country if block else None, "watchLink": block.get("link")}
    for tmdb_key, our_key in (
        ("flatrate", "streamingOn"), ("rent", "rentFrom"),
        ("buy", "buyFrom"), ("ads", "freeWithAdsOn"), ("free", "freeOn"),
    ):
        flat[our_key] = _names(block.get(tmdb_key), "provider_name")
    return {
        "watchRegions": sorted(results.keys()),
        "watchProviders": flat,
    }


def parse_certification(payload: Any, region: str | None, media_type: str) -> dict[str, Any]:
    """The age rating for the requested country.

    Movies publish it under `release_dates`, series under `content_ratings`,
    in two different shapes. Both are reduced to one `certification` string
    plus the country-keyed map, so a movie row and a series row can be filtered
    with the same expression.
    """
    results = (payload or {}).get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return {}
    country = (region or "US").upper()
    by_country: dict[str, str] = {}
    theatrical: dict[str, str] = {}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("iso_3166_1") or "").upper()
        if media_type == "tv":
            if entry.get("rating"):
                by_country[code] = str(entry["rating"])
            continue
        for release in entry.get("release_dates") or []:
            if not isinstance(release, dict):
                continue
            cert = (release.get("certification") or "").strip()
            if cert and code not in by_country:
                by_country[code] = cert
            # type 3 is the theatrical release; type 4 is digital, 5 physical.
            if release.get("type") == 3 and release.get("release_date") and code not in theatrical:
                theatrical[code] = str(release["release_date"])[:10]
    out: dict[str, Any] = {
        "certification": by_country.get(country),
        "certificationsByCountry": by_country,
    }
    if theatrical:
        out["theatricalReleaseDate"] = theatrical.get(country)
        out["theatricalReleaseByCountry"] = theatrical
    return out


def parse_keywords(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    # Movies return {"keywords": [...]}, series return {"results": [...]}.
    return _names(payload.get("keywords") or payload.get("results"))


def _related(payload: Any, limit: int = 20) -> list[dict[str, Any]]:
    results = (payload or {}).get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    out = []
    for entry in results[:limit]:
        if not isinstance(entry, dict):
            continue
        out.append({
            "tmdbId": entry.get("id"),
            "title": entry.get("title") or entry.get("name"),
            "year": _year(entry.get("release_date") or entry.get("first_air_date")),
            "voteAverage": entry.get("vote_average"),
        })
    return out


# -- titles ----------------------------------------------------------------

def parse_title(
    payload: dict[str, Any],
    media_type: str,
    *,
    region: str | None = None,
    max_cast: int = 0,
    include_full_crew: bool = False,
) -> dict[str, Any]:
    """One movie or one series, with every appended sub-payload folded in.

    `media_type` is passed in rather than sniffed, because a movie and a series
    share almost every field name while meaning different things by them -- a
    movie has `title` and `release_date`, a series has `name` and
    `first_air_date` -- and guessing wrong silently produces a row of nulls.
    """
    is_tv = media_type == "tv"
    tmdb_id = payload.get("id")
    title = payload.get("title") or payload.get("name")
    original_title = payload.get("original_title") or payload.get("original_name")
    release_date = payload.get("release_date") or payload.get("first_air_date")

    budget = _money(payload.get("budget"))
    revenue = _money(payload.get("revenue"))

    data: dict[str, Any] = {
        "mediaType": media_type,
        "tmdbId": tmdb_id,
        "imdbId": payload.get("imdb_id"),
        "title": title,
        "originalTitle": original_title,
        "originalLanguage": payload.get("original_language"),
        "tagline": clean_text(payload.get("tagline")),
        "overview": clean_text(payload.get("overview")),
        "status": payload.get("status"),
        "releaseDate": str(release_date)[:10] if release_date else None,
        "year": _year(release_date),
        "genres": _names(payload.get("genres")),
        "genreIds": _ids(payload.get("genres")),
        "homepage": payload.get("homepage") or None,
        "tmdbUrl": f"{SITE_ROOT}/{media_type}/{tmdb_id}" if tmdb_id else None,
        "posterUrl": image_url(payload.get("poster_path")),
        "backdropUrl": image_url(payload.get("backdrop_path")),
        "voteAverage": payload.get("vote_average"),
        "voteCount": payload.get("vote_count"),
        "popularity": payload.get("popularity"),
        "isAdult": payload.get("adult"),
        "spokenLanguages": _names(payload.get("spoken_languages"), "english_name")
        or _names(payload.get("spoken_languages")),
        "productionCompanies": _names(payload.get("production_companies")),
        "productionCompanyIds": _ids(payload.get("production_companies")),
        "productionCountries": _names(payload.get("production_countries")),
    }

    if is_tv:
        last_ep = payload.get("last_episode_to_air") or {}
        next_ep = payload.get("next_episode_to_air") or {}
        data.update({
            "firstAirDate": str(payload.get("first_air_date") or "")[:10] or None,
            "lastAirDate": str(payload.get("last_air_date") or "")[:10] or None,
            "inProduction": payload.get("in_production"),
            "numberOfSeasons": payload.get("number_of_seasons"),
            "numberOfEpisodes": payload.get("number_of_episodes"),
            "episodeRunTimeMins": payload.get("episode_run_time"),
            "type": payload.get("type"),
            "networks": _names(payload.get("networks")),
            "networkIds": _ids(payload.get("networks")),
            "originCountries": payload.get("origin_country") or [],
            "createdBy": _names(payload.get("created_by")),
            "seasons": [
                {
                    "seasonNumber": s.get("season_number"),
                    "name": s.get("name"),
                    "episodeCount": s.get("episode_count"),
                    "airDate": str(s.get("air_date") or "")[:10] or None,
                    "overview": clean_text(s.get("overview")),
                    "posterUrl": image_url(s.get("poster_path")),
                    "voteAverage": s.get("vote_average"),
                }
                for s in payload.get("seasons") or []
                if isinstance(s, dict)
            ],
            "lastEpisodeToAir": {
                "seasonNumber": last_ep.get("season_number"),
                "episodeNumber": last_ep.get("episode_number"),
                "name": last_ep.get("name"),
                "airDate": str(last_ep.get("air_date") or "")[:10] or None,
            } if last_ep else None,
            "nextEpisodeToAir": {
                "seasonNumber": next_ep.get("season_number"),
                "episodeNumber": next_ep.get("episode_number"),
                "name": next_ep.get("name"),
                "airDate": str(next_ep.get("air_date") or "")[:10] or None,
            } if next_ep else None,
        })
    else:
        data.update({
            "runtimeMins": payload.get("runtime") or None,
            "budgetUsd": budget,
            "revenueUsd": revenue,
            # Both derived fields are null unless BOTH numbers are real, so a
            # film with an unknown budget never shows up as infinitely
            # profitable in someone's sorted spreadsheet.
            "profitUsd": (revenue - budget) if (budget and revenue) else None,
            "returnOnBudget": round(revenue / budget, 3) if (budget and revenue) else None,
        })
        collection = payload.get("belongs_to_collection")
        if isinstance(collection, dict):
            data["collection"] = {
                "collectionId": collection.get("id"),
                "name": collection.get("name"),
                "posterUrl": image_url(collection.get("poster_path")),
            }

    # -- appended blocks ---------------------------------------------------
    credits = payload.get("aggregate_credits") or payload.get("credits")
    if isinstance(credits, dict):
        data["cast"] = parse_cast(credits.get("cast"), limit=max_cast)
        data["castCount"] = len(credits.get("cast") or [])
        crew = parse_crew(credits.get("crew"))
        full = crew.pop("crew")
        data.update(crew)
        if include_full_crew:
            data["crew"] = full
        data["crewCount"] = len(full)

    if isinstance(payload.get("external_ids"), dict):
        ids = parse_external_ids(payload["external_ids"])
        # A movie publishes imdb_id at the top level too; never let an empty
        # appended block blank out a value that was already there.
        data.update({k: v for k, v in ids.items() if v})

    if payload.get("videos"):
        data.update(parse_videos(payload["videos"]))
    if payload.get("images"):
        data.update(parse_images(payload["images"]))
    if payload.get("keywords"):
        data["keywords"] = parse_keywords(payload["keywords"])
    if payload.get("watch/providers"):
        data.update(parse_watch_providers(payload["watch/providers"], region))
    if payload.get("release_dates") or payload.get("content_ratings"):
        data.update(parse_certification(
            payload.get("release_dates") or payload.get("content_ratings"),
            region, media_type,
        ))
    if payload.get("recommendations"):
        data["recommended"] = _related(payload["recommendations"])
    if payload.get("similar"):
        data["similar"] = _related(payload["similar"])
    if isinstance(payload.get("alternative_titles"), dict):
        alts = (payload["alternative_titles"].get("titles")
                or payload["alternative_titles"].get("results") or [])
        data["alternativeTitles"] = [
            {"country": a.get("iso_3166_1"), "title": a.get("title"), "type": a.get("type")}
            for a in alts if isinstance(a, dict)
        ]
    if isinstance(payload.get("reviews"), dict):
        data["reviewCount"] = payload["reviews"].get("total_results")
    if isinstance(payload.get("episode_groups"), dict):
        # Alternative episode orderings -- chronological vs broadcast vs DVD.
        # They ride along with alternative_titles on a series and are worth
        # publishing: for an anime or a long-running show, "episode 12" means
        # a different episode depending on which order the buyer is working in.
        data["episodeGroups"] = [
            {
                "groupId": g.get("id"),
                "name": g.get("name"),
                "description": clean_text(g.get("description")),
                "groupCount": g.get("group_count"),
                "episodeCount": g.get("episode_count"),
                "type": g.get("type"),
                "network": (g.get("network") or {}).get("name")
                if isinstance(g.get("network"), dict) else None,
            }
            for g in payload["episode_groups"].get("results") or []
            if isinstance(g, dict)
        ]

    return data


# -- people ----------------------------------------------------------------

def parse_person(
    payload: dict[str, Any], *, max_credits: int = 0
) -> dict[str, Any]:
    """One person, with their filmography folded in.

    The filmography is sorted by popularity rather than left in TMDB's order,
    which is effectively arbitrary: a 300-credit actor's first ten rows would
    otherwise be voice cameos and archive footage rather than the roles anyone
    knows them for.
    """
    tmdb_id = payload.get("id")
    data: dict[str, Any] = {
        "mediaType": "person",
        "tmdbId": tmdb_id,
        "imdbId": payload.get("imdb_id"),
        "name": payload.get("name"),
        "alsoKnownAs": payload.get("also_known_as") or [],
        "biography": clean_text(payload.get("biography")),
        "knownForDepartment": payload.get("known_for_department"),
        "birthday": payload.get("birthday"),
        "deathday": payload.get("deathday"),
        "isAlive": payload.get("deathday") is None,
        "placeOfBirth": payload.get("place_of_birth"),
        "gender": {0: "unknown", 1: "female", 2: "male", 3: "non-binary"}.get(
            payload.get("gender"), "unknown"
        ),
        "homepage": payload.get("homepage") or None,
        "popularity": payload.get("popularity"),
        "profileUrl": image_url(payload.get("profile_path")),
        "tmdbUrl": f"{SITE_ROOT}/person/{tmdb_id}" if tmdb_id else None,
    }

    birthday, deathday = payload.get("birthday"), payload.get("deathday")
    age = _age(birthday, deathday)
    if age is not None:
        data["age"] = age
        data["ageAtDeath" if deathday else "ageNow"] = age

    if isinstance(payload.get("external_ids"), dict):
        data.update({k: v for k, v in parse_external_ids(payload["external_ids"]).items() if v})
    if payload.get("images"):
        data.update(parse_images(payload["images"]))

    combined = payload.get("combined_credits")
    if isinstance(combined, dict):
        acting = _filmography(combined.get("cast"), "cast", max_credits)
        crew_credits = _filmography(combined.get("crew"), "crew", max_credits)
        data["filmography"] = acting + crew_credits
        data["actingCreditCount"] = len(combined.get("cast") or [])
        data["crewCreditCount"] = len(combined.get("crew") or [])
        data["knownFor"] = [c["title"] for c in (acting or crew_credits)[:5] if c.get("title")]
    return data


def _age(birthday: Any, deathday: Any) -> int | None:
    """Age now, or age at death when the person has died."""
    try:
        born = _dt.date.fromisoformat(str(birthday)[:10])
    except (TypeError, ValueError):
        return None
    try:
        end = _dt.date.fromisoformat(str(deathday)[:10]) if deathday else _dt.date.today()
    except (TypeError, ValueError):
        end = _dt.date.today()
    years = end.year - born.year - ((end.month, end.day) < (born.month, born.day))
    return years if 0 <= years < 130 else None


def _filmography(entries: Any, kind: str, limit: int) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        media_type = entry.get("media_type") or "movie"
        release = entry.get("release_date") or entry.get("first_air_date")
        rows.append({
            "creditKind": kind,
            "mediaType": media_type,
            "tmdbId": entry.get("id"),
            "title": entry.get("title") or entry.get("name"),
            "year": _year(release),
            "releaseDate": str(release)[:10] if release else None,
            "character": entry.get("character") if kind == "cast" else None,
            "job": entry.get("job") if kind == "crew" else None,
            "department": entry.get("department") if kind == "crew" else None,
            "episodeCount": entry.get("episode_count"),
            "voteAverage": entry.get("vote_average"),
            "voteCount": entry.get("vote_count"),
            "popularity": entry.get("popularity"),
            "posterUrl": image_url(entry.get("poster_path")),
            "tmdbUrl": f"{SITE_ROOT}/{media_type}/{entry.get('id')}" if entry.get("id") else None,
        })
    rows.sort(key=lambda r: (r.get("popularity") or 0), reverse=True)
    return rows[:limit] if limit else rows


# -- episodes --------------------------------------------------------------

def parse_episode(
    payload: dict[str, Any], *, series_id: Any = None, series_name: str | None = None,
    max_cast: int = 0,
) -> dict[str, Any]:
    """One episode, with its own rating -- the field this mode exists for."""
    season_no = payload.get("season_number")
    episode_no = payload.get("episode_number")
    data: dict[str, Any] = {
        "mediaType": "episode",
        "seriesId": series_id,
        "seriesName": series_name,
        "tmdbId": payload.get("id"),
        "seasonNumber": season_no,
        "episodeNumber": episode_no,
        "episodeCode": (
            f"S{int(season_no):02d}E{int(episode_no):02d}"
            if isinstance(season_no, int) and isinstance(episode_no, int) else None
        ),
        "name": payload.get("name"),
        "overview": clean_text(payload.get("overview")),
        "airDate": str(payload.get("air_date") or "")[:10] or None,
        "runtimeMins": payload.get("runtime") or None,
        "episodeType": payload.get("episode_type"),
        "productionCode": payload.get("production_code") or None,
        "voteAverage": payload.get("vote_average"),
        "voteCount": payload.get("vote_count"),
        "stillUrl": image_url(payload.get("still_path")),
        "tmdbUrl": (
            f"{SITE_ROOT}/tv/{series_id}/season/{season_no}/episode/{episode_no}"
            if series_id is not None else None
        ),
    }
    crew = parse_crew(payload.get("crew"))
    crew.pop("crew", None)
    data.update(crew)
    if payload.get("guest_stars"):
        data["guestStars"] = parse_cast(payload.get("guest_stars"), limit=max_cast)
    return data


def parse_season(
    payload: dict[str, Any], *, series_id: Any = None, series_name: str | None = None
) -> dict[str, Any]:
    return {
        "mediaType": "season",
        "seriesId": series_id,
        "seriesName": series_name,
        "tmdbId": payload.get("id"),
        "seasonNumber": payload.get("season_number"),
        "name": payload.get("name"),
        "overview": clean_text(payload.get("overview")),
        "airDate": str(payload.get("air_date") or "")[:10] or None,
        "episodeCount": len(payload.get("episodes") or []),
        "voteAverage": payload.get("vote_average"),
        "posterUrl": image_url(payload.get("poster_path")),
        "tmdbUrl": (
            f"{SITE_ROOT}/tv/{series_id}/season/{payload.get('season_number')}"
            if series_id is not None else None
        ),
    }


# -- reviews ---------------------------------------------------------------

def parse_review(
    payload: dict[str, Any], *, media_type: str, parent_id: Any = None,
    parent_title: str | None = None,
) -> dict[str, Any]:
    """One user review, cleaned for sentiment work.

    The rating is the point of difference from a scraped review: TMDB
    publishes the reviewer's own 0-10 score alongside the text, so a sentiment
    model has a ground-truth label to be scored against instead of only the
    prose.
    """
    author = payload.get("author_details") or {}
    content = clean_text(payload.get("content")) or ""
    return {
        "mediaType": "review",
        "reviewId": payload.get("id"),
        "parentMediaType": media_type,
        "parentId": parent_id,
        "parentTitle": parent_title,
        "author": payload.get("author") or author.get("username"),
        "authorUsername": author.get("username"),
        "authorRating": author.get("rating"),
        "authorAvatarUrl": _avatar(author.get("avatar_path")),
        "content": content,
        "contentLength": len(content),
        "createdAt": payload.get("created_at"),
        "updatedAt": payload.get("updated_at"),
        "url": payload.get("url"),
    }


def _avatar(path: Any) -> str | None:
    """Gravatar avatars arrive as a path with a nested absolute URL inside it.

    TMDB stores them as "/https://secure.gravatar.com/avatar/abc", so joining
    the CDN host on the front would produce a URL that 404s.
    """
    if not path:
        return None
    text = str(path)
    if text.startswith("/http"):
        return text[1:]
    return image_url(text)


# -- list rows -------------------------------------------------------------

def parse_list_entry(entry: dict[str, Any], media_type_hint: str | None = None) -> dict[str, Any]:
    """A row from a search, discover, chart or trending response.

    These payloads are deliberately thin -- TMDB returns about 15 fields per
    row, not the 60 a detail call returns -- so this parser stays thin too and
    the row carries a `tmdbId` the detail modes can be re-run on.
    """
    media_type = entry.get("media_type") or media_type_hint or "movie"
    if media_type == "person":
        known_for = entry.get("known_for") or []
        return {
            "mediaType": "person",
            "tmdbId": entry.get("id"),
            "name": entry.get("name"),
            "knownForDepartment": entry.get("known_for_department"),
            "popularity": entry.get("popularity"),
            "profileUrl": image_url(entry.get("profile_path")),
            "knownFor": [k.get("title") or k.get("name") for k in known_for if isinstance(k, dict)],
            "tmdbUrl": f"{SITE_ROOT}/person/{entry.get('id')}" if entry.get("id") else None,
        }
    release = entry.get("release_date") or entry.get("first_air_date")
    return {
        "mediaType": media_type,
        "tmdbId": entry.get("id"),
        "title": entry.get("title") or entry.get("name"),
        "originalTitle": entry.get("original_title") or entry.get("original_name"),
        "originalLanguage": entry.get("original_language"),
        "overview": clean_text(entry.get("overview")),
        "releaseDate": str(release)[:10] if release else None,
        "year": _year(release),
        "genreIds": entry.get("genre_ids") or [],
        "voteAverage": entry.get("vote_average"),
        "voteCount": entry.get("vote_count"),
        "popularity": entry.get("popularity"),
        "isAdult": entry.get("adult"),
        "originCountries": entry.get("origin_country") or [],
        "posterUrl": image_url(entry.get("poster_path")),
        "backdropUrl": image_url(entry.get("backdrop_path")),
        "tmdbUrl": f"{SITE_ROOT}/{media_type}/{entry.get('id')}" if entry.get("id") else None,
    }


# -- collections and companies --------------------------------------------

def parse_collection(payload: dict[str, Any]) -> dict[str, Any]:
    parts = [p for p in payload.get("parts") or [] if isinstance(p, dict)]
    parts.sort(key=lambda p: str(p.get("release_date") or "9999"))
    return {
        "mediaType": "collection",
        "tmdbId": payload.get("id"),
        "name": payload.get("name"),
        "overview": clean_text(payload.get("overview")),
        "posterUrl": image_url(payload.get("poster_path")),
        "backdropUrl": image_url(payload.get("backdrop_path")),
        "partCount": len(parts),
        "parts": [parse_list_entry(p, "movie") for p in parts],
        "tmdbUrl": f"{SITE_ROOT}/collection/{payload.get('id')}" if payload.get("id") else None,
    }


def parse_company(payload: dict[str, Any], kind: str = "company") -> dict[str, Any]:
    """A production company or a TV network.

    `homepage` is the field worth noticing: for an independent producer looking
    for a distributor or a co-production partner, the company's own site is the
    route to a real contact, and TMDB publishes it for a large share of the
    companies it holds.
    """
    return {
        "mediaType": kind,
        "tmdbId": payload.get("id"),
        "name": payload.get("name"),
        "description": clean_text(payload.get("description")),
        "headquarters": payload.get("headquarters") or None,
        "originCountry": payload.get("origin_country") or None,
        "homepage": payload.get("homepage") or None,
        "logoUrl": image_url(payload.get("logo_path")),
        "parentCompany": (payload.get("parent_company") or {}).get("name")
        if isinstance(payload.get("parent_company"), dict) else None,
        "tmdbUrl": f"{SITE_ROOT}/{kind}/{payload.get('id')}" if payload.get("id") else None,
    }
