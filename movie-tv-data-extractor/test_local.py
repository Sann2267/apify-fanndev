"""Local test harness: parser unit tests on fixtures, then every mode live.

    python test_local.py --offline          # fixtures only, no network, no key
    python test_local.py --key <TMDB_KEY>   # everything
    python test_local.py --mode charts      # one mode live

The offline half is the regression net and needs no credential at all. It runs
against the JSON in tests/fixtures, so a change to a field mapping or to the
Markdown renderer is caught without spending a TMDB request, and the fixtures
double as a record of the payload shapes this actor was written against.

The live half needs a TMDB key, from --key or the TMDB_API_KEY environment
variable. It is the half that proves the endpoint paths and parameter names are
right, which fixtures by construction cannot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src import parsers  # noqa: E402
from src.client import TmdbAuthError, TmdbClient  # noqa: E402
from src.constants import CHARTS  # noqa: E402
from src.markdown import render  # noqa: E402
from src.modes import (  # noqa: E402
    MODE_REQUIRED_INPUT,
    MODES,
    Budget,
    as_strings,
    build_discover_params,
    resolve_target,
)
from src.parsers import (  # noqa: E402
    clean_text,
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

FIXTURES = pathlib.Path(__file__).parent / "tests" / "fixtures"

PASS = FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


ALL_INCLUDES = {
    "includeCredits": True, "includeImages": True, "includeVideos": True,
    "includeKeywords": True, "includeWatchProviders": True, "includeReviews": True,
    "includeSimilar": True, "includeExternalIds": True, "includeReleaseDates": True,
    "includeAlternativeTitles": True,
}


# -- offline ---------------------------------------------------------------

def test_movie() -> None:
    print("\n[movie detail]")
    parsers.configure("w500")
    data = parse_title(fixture("movie_detail.json"), "movie", region="US", max_cast=2)

    check("title and year", data["title"] == "Inception" and data["year"] == 2010)
    check("imdb id carried through", data["imdbId"] == "tt1375666")
    check("runtime", data["runtimeMins"] == 148)
    check("genres flattened to names", data["genres"] == ["Action", "Science Fiction", "Adventure"])
    check("genre ids kept", data["genreIds"] == [28, 878, 12])
    check("budget", data["budgetUsd"] == 160000000)
    check("profit derived", data["profitUsd"] == 839030630 - 160000000)
    check("return on budget derived", data["returnOnBudget"] == round(839030630 / 160000000, 3))
    check(
        "poster path expanded to a URL at the configured size",
        data["posterUrl"] == "https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg",
        data["posterUrl"],
    )
    check("cast trimmed to the limit", len(data["cast"]) == 2, str(len(data["cast"])))
    check("castCount reports the untrimmed total", data["castCount"] == 3)
    check("first billed cast member", data["cast"][0]["character"] == "Dom Cobb")
    check("director lifted out of crew", data["directors"] == ["Christopher Nolan"])
    check("writer lifted out of crew", data["writers"] == ["Christopher Nolan"])
    check("composer lifted out of crew", data["composers"] == ["Hans Zimmer"])
    check("cinematographer lifted out of crew", data["cinematographers"] == ["Wally Pfister"])
    check("producer lifted out of crew", data["producers"] == ["Emma Thomas"])
    check("full crew omitted unless asked for", "crew" not in data)
    check("keywords flattened", "heist" in data["keywords"])
    check("official trailer picked, not the featurette",
          data["trailerUrl"] == "https://www.youtube.com/watch?v=8hP9D6kZseM", str(data["trailerUrl"]))
    check("image gallery capped and expanded", len(data["backdropUrls"]) == 2)
    check("US certification", data["certification"] == "PG-13", str(data.get("certification")))
    check("GB certification kept too", data["certificationsByCountry"].get("GB") == "12A")
    check("theatrical date is the type-3 release, not the physical one",
          data["theatricalReleaseDate"] == "2010-07-16", str(data.get("theatricalReleaseDate")))
    check("watch providers flattened to the region",
          data["watchProviders"]["streamingOn"] == ["Max"], str(data["watchProviders"]))
    check("other watch regions listed", data["watchRegions"] == ["GB", "US"])
    check("facebook handle became a URL",
          data.get("facebookUrl") == "https://www.facebook.com/inception")
    check("imdb URL built from the id",
          data.get("imdbUrl") == "https://www.imdb.com/title/tt1375666/")
    check("review count from the appended block", data.get("reviewCount") == 7)
    check("recommendations reduced to stubs", data["recommended"][0]["title"] == "The Dark Knight")

    parsers.configure("original")
    with_crew = parse_title(fixture("movie_detail.json"), "movie", include_full_crew=True)
    check("full crew included when asked", len(with_crew["crew"]) == 5)
    check("crewCount always reported", with_crew["crewCount"] == 5)


def test_unknown_money_is_null() -> None:
    print("\n[money: 0 means unknown]")
    payload = fixture("movie_detail.json")
    payload["budget"] = 0
    payload["revenue"] = 0
    data = parse_title(payload, "movie")
    check("zero budget becomes null", data["budgetUsd"] is None)
    check("zero revenue becomes null", data["revenueUsd"] is None)
    check("profit not invented from nulls", data["profitUsd"] is None)
    check("return on budget not invented from nulls", data["returnOnBudget"] is None)


def test_tv() -> None:
    print("\n[tv detail]")
    parsers.configure("original")
    data = parse_title(fixture("tv_detail.json"), "tv", region="US", max_cast=0)

    check("name read from the tv field", data["title"] == "Breaking Bad")
    check("first air date used as release date", data["releaseDate"] == "2008-01-20")
    check("year from first air date", data["year"] == 2008)
    check("season count", data["numberOfSeasons"] == 5)
    check("episode count", data["numberOfEpisodes"] == 62)
    check("networks", data["networks"] == ["AMC"])
    check("created by", data["createdBy"] == ["Vince Gilligan"])
    check("seasons summarised", len(data["seasons"]) == 3)
    check("specials season kept in the summary", data["seasons"][0]["seasonNumber"] == 0)
    check("last episode to air", data["lastEpisodeToAir"]["name"] == "Felina")
    check("no next episode for an ended show", data["nextEpisodeToAir"] is None)
    check("aggregate cast used", data["cast"][0]["name"] == "Bryan Cranston")
    check("per-actor episode count kept", data["cast"][0]["episodeCount"] == 62)
    check("character read out of the roles array", data["cast"][0]["character"] == "Walter White")
    check("aggregate crew jobs array handled", data["directors"] == ["Vince Gilligan"])
    check("writer from the same jobs array", data["writers"] == ["Vince Gilligan"])
    check("content rating read as certification", data["certification"] == "TV-MA")
    check("series keywords come from `results`", "new mexico" in data["keywords"])
    check("instagram URL built", data.get("instagramUrl") == "https://www.instagram.com/breakingbad/")
    check("series has no budget fields", "budgetUsd" not in data)


def test_person() -> None:
    print("\n[person detail]")
    data = parse_person(fixture("person_detail.json"), max_credits=0)
    check("name", data["name"] == "Christopher Nolan")
    check("imdb id", data["imdbId"] == "nm0634240")
    check("alive", data["isAlive"] is True)
    check("age computed", isinstance(data["age"], int) and data["age"] >= 55, str(data.get("age")))
    check("biography cleaned", data["biography"].startswith("Christopher Edward Nolan"))
    check("gender decoded", data["gender"] == "male")
    check("acting credits counted", data["actingCreditCount"] == 2)
    check("crew credits counted", data["crewCreditCount"] == 2)
    check("filmography holds both kinds", len(data["filmography"]) == 4)
    check(
        "acting credits sorted by popularity, not TMDB order",
        data["filmography"][0]["title"] == "Inception", str(data["filmography"][0]),
    )
    check("crew credit carries its job",
          any(c["job"] == "Director" for c in data["filmography"]))
    check("instagram handle expanded",
          data.get("instagramUrl") == "https://www.instagram.com/christophernolan.official/")

    trimmed = parse_person(fixture("person_detail.json"), max_credits=1)
    check("filmography trimmed per kind", len(trimmed["filmography"]) == 2, str(len(trimmed["filmography"])))
    check("counts still report the untrimmed total", trimmed["actingCreditCount"] == 2)


def test_dead_person_age() -> None:
    print("\n[person: age at death]")
    payload = fixture("person_detail.json")
    payload["birthday"] = "1899-08-13"
    payload["deathday"] = "1980-04-29"
    data = parse_person(payload)
    check("age at death, not age now", data["age"] == 80, str(data.get("age")))
    check("ageAtDeath field used", data.get("ageAtDeath") == 80)
    check("isAlive false", data["isAlive"] is False)


def test_season_and_episodes() -> None:
    print("\n[season & episodes]")
    payload = fixture("season_detail.json")
    season = parse_season(payload, series_id=1396, series_name="Breaking Bad")
    check("season number", season["seasonNumber"] == 1)
    check("episode count from the episodes array", season["episodeCount"] == 2)
    check("season URL built", season["tmdbUrl"].endswith("/tv/1396/season/1"))

    ep = parse_episode(payload["episodes"][0], series_id=1396, series_name="Breaking Bad", max_cast=0)
    check("episode name", ep["name"] == "Pilot")
    check("episode code padded", ep["episodeCode"] == "S01E01", str(ep["episodeCode"]))
    check("episode has its OWN rating", ep["voteAverage"] == 8.2)
    check("episode air date", ep["airDate"] == "2008-01-20")
    check("episode director", ep["directors"] == ["Vince Gilligan"])
    check("guest stars parsed", ep["guestStars"][0]["name"] == "Marius Stan")
    check("episode URL built", ep["tmdbUrl"].endswith("/tv/1396/season/1/episode/1"))

    ep2 = parse_episode(payload["episodes"][1], series_id=1396, series_name="Breaking Bad")
    check("episode with no crew still parses", ep2["directors"] == [])


def test_reviews() -> None:
    print("\n[reviews]")
    page = fixture("reviews_page.json")
    review = parse_review(page["results"][0], media_type="movie", parent_id=27205, parent_title="Inception")
    check("author", review["author"] == "Cat Ellington")
    check("reviewer's own score kept", review["authorRating"] == 9)
    check("HTML stripped from the body", "<em>" not in review["content"], review["content"][:60])
    check("entity decoded", "that's" in review["content"], review["content"][:60])
    check("CRLF normalised", "\r" not in review["content"])
    check("content length reported", review["contentLength"] == len(review["content"]))
    check("parent title carried", review["parentTitle"] == "Inception")

    gravatar = parse_review(page["results"][1], media_type="movie", parent_id=27205)
    check(
        "gravatar avatar not prefixed with the TMDB CDN",
        gravatar["authorAvatarUrl"] == "https://secure.gravatar.com/avatar/abc123.jpg",
        str(gravatar["authorAvatarUrl"]),
    )
    check("missing rating stays null", gravatar["authorRating"] is None)


def test_list_rows() -> None:
    print("\n[list rows]")
    page = fixture("discover_page.json")
    row = parse_list_entry(page["results"][0], "movie")
    check("thin row title", row["title"] == "Dune: Part Two")
    check("thin row year", row["year"] == 2024)
    check("thin row carries an id the detail modes accept", row["tmdbId"] == 693134)
    check("thin row poster expanded", row["posterUrl"].startswith("https://image.tmdb.org/"))
    check("null backdrop stays null", parse_list_entry(page["results"][1], "movie")["backdropUrl"] is None)

    person_row = parse_list_entry(
        {"id": 525, "name": "Christopher Nolan", "media_type": "person",
         "known_for_department": "Directing", "profile_path": None,
         "known_for": [{"title": "Inception"}]}, None,
    )
    check("person row uses name, not title", person_row["name"] == "Christopher Nolan")
    check("known-for flattened", person_row["knownFor"] == ["Inception"])


def test_collection_and_company() -> None:
    print("\n[collections & companies]")
    coll = parse_collection(fixture("collection_detail.json"))
    check("collection name", coll["name"] == "The Dark Knight Collection")
    check("part count", coll["partCount"] == 2)
    check(
        "parts sorted into release order, not TMDB order",
        [p["title"] for p in coll["parts"]] == ["Batman Begins", "The Dark Knight"],
        str([p["title"] for p in coll["parts"]]),
    )

    company = parse_company(fixture("company_detail.json"))
    check("company name", company["name"] == "A24")
    check("homepage kept - the lead-generation field", company["homepage"] == "https://a24films.com")
    check("headquarters kept", "New York" in company["headquarters"])
    check("empty description becomes null", company["description"] is None)


def test_markdown() -> None:
    print("\n[markdown rendering]")
    parsers.configure("original")
    movie = parse_title(fixture("movie_detail.json"), "movie", region="US", max_cast=3)
    doc = render("title", movie)
    check("heading names the film and year", doc.startswith("# Inception (2010)"), doc[:40])
    check("tagline rendered in italics", "*Your mind is the scene of the crime.*" in doc)
    check("overview section present", "## Overview" in doc)
    check("cast section present", "## Cast" in doc)
    check("cast rendered as 'name as character'", "- Leonardo DiCaprio as Dom Cobb" in doc)
    check("box office formatted with separators", "$160,000,000" in doc, "")
    check("return on budget rendered", "5.244x" in doc, "")
    check("where to watch names the region", "## Where to watch (US)" in doc)
    check("no python None leaked into the prose", "None" not in doc)
    check("no raw null leaked into the prose", "null" not in doc)

    tv = parse_title(fixture("tv_detail.json"), "tv", region="US")
    tv_doc = render("title", tv)
    check("series doc says it is a series", "**Type:** TV series" in tv_doc)
    check("series doc lists seasons", "## Seasons" in tv_doc)
    check("episode counts rendered for series cast", "(62 episodes)" in tv_doc)
    check("no box office section on a series", "## Box office" not in tv_doc)

    person = parse_person(fixture("person_detail.json"))
    person_doc = render("person", person)
    check("person heading", person_doc.startswith("# Christopher Nolan"))
    check("biography section", "## Biography" in person_doc)
    check("filmography split by credit kind", "## Filmography - acting" in person_doc)

    ep = parse_episode(
        fixture("season_detail.json")["episodes"][0], series_id=1396, series_name="Breaking Bad",
    )
    ep_doc = render("episode", ep)
    check(
        "episode doc names its series, so the chunk stands alone",
        ep_doc.startswith("# Breaking Bad - S01E01: Pilot"), ep_doc[:60],
    )

    review = parse_review(
        fixture("reviews_page.json")["results"][0], media_type="movie",
        parent_id=27205, parent_title="Inception",
    )
    review_doc = render("review", review)
    check("review doc names the film it is about", "Review of Inception" in review_doc)
    check("review doc carries the score", "9/10" in review_doc)

    check("error rows are never rendered as prose", render("error", {"_error": "x"}) is None)


def test_clean_text() -> None:
    print("\n[text cleaning]")
    check("None passes through", clean_text(None) is None)
    check("empty becomes None", clean_text("   ") is None)
    check("tags stripped", clean_text("<p>hi <b>there</b></p>") == "hi there")
    check("entities decoded", clean_text("a &amp; b") == "a & b")
    check("runs of blank lines collapsed", clean_text("a\n\n\n\n\nb") == "a\n\nb")


def test_resolvers() -> None:
    print("\n[input resolution]")
    cases = [
        ("tt1375666", None, None, "tt1375666"),
        ("https://www.imdb.com/title/tt1375666/", None, None, "tt1375666"),
        ("nm0000138", "person", None, "nm0000138"),
        ("https://www.imdb.com/name/nm0000138/", "person", None, "nm0000138"),
        ("https://www.themoviedb.org/movie/27205-inception", "movie", 27205, None),
        ("https://www.themoviedb.org/tv/1399/season/1", "tv", 1399, None),
        ("https://www.themoviedb.org/person/525", "person", 525, None),
        ("movie:27205", "movie", 27205, None),
        ("tv:1399", "tv", 1399, None),
        ("collection:263", "collection", 263, None),
        ("network:49", "network", 49, None),
    ]
    for raw, media_type, tmdb_id, imdb_id in cases:
        target = resolve_target(raw, "movie")
        ok = (
            target.media_type == media_type
            and target.tmdb_id == tmdb_id
            and target.imdb_id == imdb_id
        )
        check(f"resolve {raw}", ok, repr(target))

    bare = resolve_target("27205", "tv")
    check("bare number takes the mode's default media type", bare.media_type == "tv" and bare.tmdb_id == 27205)
    name = resolve_target("The Grand Budapest Hotel", "movie")
    check("a plain name becomes a search", name.name_query == "The Grand Budapest Hotel")
    check("a name needs a lookup", name.needs_lookup is True)
    check("an explicit id does not", resolve_target("movie:1").needs_lookup is False)

    try:
        resolve_target("https://example.com/whatever")
        check("unknown URL rejected", False, "no error raised")
    except ValueError as exc:
        check("unknown URL rejected with a helpful message", "does not recognise" in str(exc))

    check("as_strings splits a comma string", as_strings("a, b,c") == ["a", "b", "c"])
    check("as_strings handles request-list dicts", as_strings([{"url": "x"}]) == ["x"])
    check("as_strings tolerates None", as_strings(None) == [])


def test_client_urls() -> None:
    print("\n[client: auth form and URL building]")
    v3 = TmdbClient("a" * 32, language="en-US")
    check("32-char key treated as a v3 query key", v3.is_bearer is False)
    url = v3.build_url("/movie/27205", {"append_to_response": "credits"})
    check("v3 key travels in the query string", "api_key=" + "a" * 32 in url, url)
    check("language applied run-wide", "language=en-US" in url)
    check("append list not over-escaped", "append_to_response=credits" in url)
    check("key redacted before publication", "REDACTED" in v3.redact(url) and "a" * 32 not in v3.redact(url))

    bearer = TmdbClient("eyJhbGciOiJIUzI1NiJ9.payload.signature")
    check("JWT treated as a v4 bearer token", bearer.is_bearer is True)
    bearer_url = bearer.build_url("/movie/27205")
    check("v4 token never appears in the URL", "api_key" not in bearer_url, bearer_url)
    check("v4 token sent as a header", "Authorization" in bearer._headers())

    check("empty params dropped", "region=" not in v3.build_url("/movie/1", {"region": ""}))

    try:
        TmdbClient("")
        check("empty credential rejected", False, "no error raised")
    except TmdbAuthError as exc:
        check("empty credential rejected with signup instructions", "themoviedb.org/signup" in str(exc))


def test_discover_params() -> None:
    print("\n[discover parameter building]")

    class _NoCallClient:
        """Proves the inlined genre table answers without a network call."""

        async def get(self, *args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError("the genre table should have answered offline")

    async def run() -> None:
        params, notes = await build_discover_params(
            _NoCallClient(),
            {"genres": ["Action", "Science Fiction"], "genreMatch": "any",
             "yearFrom": 2020, "yearTo": 2024, "minRating": 7, "minVotes": 300,
             "sortBy": "vote_average.desc", "withWatchProviders": ["8"],
             "watchRegion": "ID", "withPeople": ["525"]},
            "movie",
        )
        check("genre names mapped to ids", params["with_genres"] == "28|878", str(params.get("with_genres")))
        check("movie date field used", params["primary_release_date.gte"] == "2020-01-01")
        check("upper year bound is the end of the year", params["primary_release_date.lte"] == "2024-12-31")
        check("rating floor", params["vote_average.gte"] == 7)
        check("vote floor", params["vote_count.gte"] == 300)
        check("watch region required alongside the provider", params["watch_region"] == "ID")
        check("with_people allowed for films", params.get("with_people") == "525")
        check("no unknown-genre note", not notes, str(notes))

        tv_params, tv_notes = await build_discover_params(
            _NoCallClient(),
            {"genres": ["Action & Adventure", "Drama"], "genreMatch": "all",
             "yearFrom": 2020, "withPeople": ["525"], "withNetworks": ["213"]},
            "tv",
        )
        check("tv date field used", tv_params["first_air_date.gte"] == "2020-01-01")
        check("movie date field NOT sent to tv", "primary_release_date.gte" not in tv_params)
        check("tv genre table used, not the film one",
              tv_params["with_genres"].startswith("10759"), tv_params["with_genres"])
        check("genreMatch=all joins with a comma, not a pipe",
              tv_params["with_genres"] == "10759,18", tv_params["with_genres"])
        check("with_networks allowed for series", tv_params.get("with_networks") == "213")
        check("with_people rejected for series", "with_people" not in tv_params)
        check("the rejection is reported, not silent", any("withPeople" in n for n in tv_notes), str(tv_notes))

        passthrough, _ = await build_discover_params(
            _NoCallClient(), {"extraQueryParams": {"with_release_type": "3|2"}}, "movie",
        )
        check("escape hatch passes parameters through", passthrough["with_release_type"] == "3|2")

    asyncio.run(run())


def test_dataset_schema() -> None:
    print("\n[dataset envelope]")
    rec = record("title", "movie:27205", {"title": "Inception"}, mode="titleDetails",
                 source_url="https://api.themoviedb.org/3/movie/27205", rank=3, page=1)
    check("envelope keys", set(rec) == {"item_type", "id", "data", "metadata"})
    check("id namespaced by media type", rec["id"] == "movie:27205")
    check("metadata carries the mode", rec["metadata"]["mode"] == "titleDetails")
    check("metadata carries rank and page", rec["metadata"]["rank"] == 3 and rec["metadata"]["page"] == 1)
    check("scrapedAt present", rec["metadata"]["scrapedAt"].endswith("+00:00"))

    from src.parsers import error_record
    err = error_record("tt0000000", "not_found", "no such title", mode="titleDetails")
    check("error rows carry a null id", err["id"] is None)
    check("error rows name the input", err["data"]["_input"] == "tt0000000")

    check("every mode is registered", len(MODES) == 9, str(sorted(MODES)))
    check("every required-input mode exists", set(MODE_REQUIRED_INPUT) <= set(MODES))
    check("charts has no required input", "charts" not in MODE_REQUIRED_INPUT)


def test_output_format() -> None:
    print("\n[output formatting]")
    from src.main import _format_record
    rec = record("title", "movie:1", parse_title(fixture("movie_detail.json"), "movie"),
                 mode="titleDetails")
    as_json = _format_record(dict(rec), "json")
    check("json format untouched", "markdown" not in as_json)

    both = _format_record(dict(rec), "both")
    check("both keeps the structured data", "data" in both and both["markdown"].startswith("# Inception"))

    md = _format_record(dict(rec), "markdown")
    check("markdown format drops the structured body", "data" not in md)
    check("markdown format keeps id and metadata", md["id"] == "movie:1" and "metadata" in md)

    from src.parsers import error_record
    err = _format_record(error_record("x", "not_found", mode="titleDetails"), "markdown")
    check("error row stays structured even in markdown mode", "data" in err)


# -- live ------------------------------------------------------------------

LIVE_INPUTS: dict[str, dict] = {
    "titleDetails": {
        "titleTargets": ["tt1375666", "https://www.themoviedb.org/tv/1396", "The Grand Budapest Hotel"],
        **ALL_INCLUDES, "maxCastMembers": 5, "region": "US",
    },
    "personDetails": {"personTargets": ["nm0634240", "Greta Gerwig"], **ALL_INCLUDES,
                      "maxCreditsPerPerson": 10},
    "seasonEpisodes": {"tvTargets": ["tt0903747"], "seasons": ["1"], "includeSeasonRecords": True},
    "titleReviews": {"titleTargets": ["movie:27205"], "maxPagesPerTarget": 1},
    "discoverTitles": {
        "discoverMediaType": "movie", "genres": ["Science Fiction"], "yearFrom": 2020,
        "yearTo": 2024, "minRating": 7, "minVotes": 300, "sortBy": "vote_average.desc",
        "maxPagesPerTarget": 1,
    },
    "searchByName": {"searchQueries": ["blade runner"], "searchMediaType": "multi",
                     "maxPagesPerTarget": 1},
    "charts": {"chartNames": ["topRatedMovies", "trendingAllWeek"], "maxPagesPerTarget": 1},
    "collectionTitles": {"collectionTargets": ["The Dark Knight Collection", "movie:27205"]},
    "companyProfile": {"companyTargets": ["A24", "network:49"], "includeCompanyTitles": True,
                       "maxPagesPerTarget": 1},
}


async def run_live(only: str | None, key: str) -> None:
    print(f"\n{'=' * 60}\nLIVE SWEEP\n{'=' * 60}")
    parsers.configure("original")
    client = TmdbClient(key, language="en-US", region="US")
    try:
        for mode, extra in LIVE_INPUTS.items():
            if only and mode != only:
                continue
            print(f"\n[{mode}]")
            opts: dict = {"maxItems": 40, "language": "en-US", "region": "US"}
            opts.update(extra)
            for field in ("titleTargets", "personTargets", "tvTargets", "searchQueries",
                          "collectionTargets", "companyTargets", "chartNames"):
                opts.setdefault(field, [])
            rows = []
            async for rec in MODES[mode](client, opts, Budget(40)):
                rows.append(rec)
            good = [r for r in rows if r["item_type"] != "error"]
            bad = [r for r in rows if r["item_type"] == "error"]
            for row in bad:
                print(f"        error: {row['data']['_error']} [{row['data']['_input']}] "
                      f"{row['data'].get('_errorDetail', '')[:120]}")
            check(f"{mode} produced records", bool(good), f"{len(rows)} rows, {len(bad)} errors")
            if not good:
                continue
            sample = good[0]
            check(f"{mode} rows carry a namespaced id", ":" in (sample["id"] or ""), str(sample["id"]))
            check(f"{mode} rows carry a source URL", bool(sample["metadata"]["sourceUrl"]))
            check(f"{mode} source URL has no key in it",
                  "api_key=" not in sample["metadata"]["sourceUrl"]
                  or "REDACTED" in sample["metadata"]["sourceUrl"],
                  sample["metadata"]["sourceUrl"])

            if mode == "titleDetails":
                by_type = {r["data"].get("mediaType") for r in good}
                check("a tt-id and a tv URL both resolved", by_type == {"movie", "tv"}, str(by_type))
                movie = next(r for r in good if r["data"]["mediaType"] == "movie")
                check("live film carries its IMDb id", bool(movie["data"].get("imdbId")))
                check("live film carries cast", bool(movie["data"].get("cast")))
                check("live film carries a director", bool(movie["data"].get("directors")))
                check("live film carries budget", bool(movie["data"].get("budgetUsd")))
                check("live film carries a certification", bool(movie["data"].get("certification")))
                check("live film carries watch providers",
                      bool((movie["data"].get("watchProviders") or {}).get("watchRegion")))
                check("name-only target resolved",
                      any("Budapest" in (r["data"].get("title") or "") for r in good))
            if mode == "personDetails":
                check("live person carries a filmography", bool(good[0]["data"].get("filmography")))
                check("live person carries an IMDb id", bool(good[0]["data"].get("imdbId")))
            if mode == "seasonEpisodes":
                episodes = [r for r in good if r["item_type"] == "episode"]
                check("one row per episode", len(episodes) >= 7, str(len(episodes)))
                check("episodes carry their own ratings",
                      all(e["data"].get("voteAverage") is not None for e in episodes))
                check("episode codes formatted", episodes[0]["data"]["episodeCode"] == "S01E01")
                check("a season summary row was written",
                      any(r["item_type"] == "season" for r in good))
            if mode == "titleReviews":
                check("reviews carry the author's own score",
                      any(r["data"].get("authorRating") is not None for r in good))
                check("review text has no HTML left",
                      all("<" not in (r["data"].get("content") or "") for r in good))
            if mode == "discoverTitles":
                ratings = [r["data"].get("voteAverage") or 0 for r in good]
                check("the rating filter was actually applied", min(ratings) >= 7, str(min(ratings)))
                check("rank continues across the walk",
                      [r["metadata"]["rank"] for r in good] == list(range(1, len(good) + 1)))
            if mode == "charts":
                charts = {r["metadata"].get("chart") for r in good}
                check("both charts returned rows", len(charts) == 2, str(charts))
            if mode == "collectionTitles":
                check("a collection record was written",
                      any(r["item_type"] == "collection" for r in good))
                check("a film resolved to its franchise",
                      len({r["metadata"].get("query") for r in good}) == 2)
            if mode == "companyProfile":
                companies = [r for r in good if r["item_type"] == "company"]
                check("company profile found", bool(companies))
                check("company homepage present", any(c["data"].get("homepage") for c in companies))
                check("catalogue rows written", len(good) > len(companies))
    finally:
        client.close()
    print(f"\n  ({client.request_count} TMDB requests, {client.rate_limited_count} rate limited)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip the live sweep")
    ap.add_argument("--mode", help="run only this mode live")
    ap.add_argument("--key", help="TMDB API key or read-access token")
    args = ap.parse_args()

    test_movie()
    test_unknown_money_is_null()
    test_tv()
    test_person()
    test_dead_person_age()
    test_season_and_episodes()
    test_reviews()
    test_list_rows()
    test_collection_and_company()
    test_markdown()
    test_clean_text()
    test_resolvers()
    test_client_urls()
    test_discover_params()
    test_dataset_schema()
    test_output_format()

    if not args.offline:
        key = args.key or os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_API_READ_ACCESS_TOKEN")
        if not key:
            print(
                "\nSKIPPING the live sweep: no TMDB key. Pass --key <key>, set "
                "TMDB_API_KEY, or run with --offline to silence this."
            )
        else:
            asyncio.run(run_live(args.mode, key))

    print(f"\n{'=' * 60}\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
