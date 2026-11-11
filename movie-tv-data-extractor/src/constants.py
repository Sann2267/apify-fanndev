"""Endpoints, defaults and the lookup tables this actor ships with.

WHY TMDB AND NOT IMDB
---------------------
This actor was specified as an IMDb all-in-one extractor. IMDb was surveyed
first and the result is worth recording, because it is counter-intuitive:

  * IMDb's GraphQL endpoints (caching.graphql.imdb.com, api.graphql.imdb.com)
    accept arbitrary anonymous queries -- no token, no persisted-query hash,
    only `Content-Type: application/json` plus `x-imdb-client-name` and an
    imdb.com Origin. Technically the whole graph is reachable over plain HTTP.
  * Every HTML page, by contrast, answers HTTP 202 with zero content bytes and
    `x-amzn-waf-action: challenge` on all five TLS profiles this portfolio
    tests. The pages are walled; the API is not.
  * But www.imdb.com/robots.txt ends with `User-agent: *` / `Disallow: /`, its
    header states that automated data mining is prohibited without written
    permission, and every GraphQL response carries this in its own payload:
    "Public, commercial, and/or non-private use of the IMDb data provided by
    this API is not allowed."

A rented Apify Actor is public, commercial use. So the open door is not one to
walk through, and this actor is built on The Movie Database instead, whose API
terms do allow commercial use with attribution.

One consequence is load-bearing in the client: www.themoviedb.org (the
*website*) disallows ClaudeBot and anthropic-ai in its own robots.txt. Only
api.themoviedb.org is used here. There is no HTML fallback anywhere in this
actor, and none should ever be added.
"""

from __future__ import annotations

API_ROOT = "https://api.themoviedb.org/3"
IMAGE_ROOT = "https://image.tmdb.org/t/p"
SITE_ROOT = "https://www.themoviedb.org"

# TMDB is not fingerprint-gated -- it is a documented API with a key. curl_cffi
# is used for consistency with the rest of this portfolio and because its
# connection reuse is good, not because a fingerprint has to be defeated.
TLS_PROFILES = ("chrome131", "chrome124", "firefox133", "safari17_0")

DEFAULT_TIMEOUT_SECS = 45
DEFAULT_MAX_RETRIES = 4

# TMDB's published limit is roughly 50 requests/second per key, which no
# sensible run approaches. A small default delay keeps a 500-title run well
# under it without making the run feel slow.
DEFAULT_REQUEST_DELAY_SECS = 0.12

DEFAULT_LANGUAGE = "en-US"
DEFAULT_IMAGE_SIZE = "original"
RESULTS_PER_PAGE = 20  # TMDB fixes this; `page` is the only paging control.

# TMDB refuses `page` above 500 on every paged endpoint.
MAX_PAGE = 500

# -- append_to_response ----------------------------------------------------
# The single biggest cost lever in this actor. One /movie/{id} call with these
# appended returns what would otherwise be eight or nine separate requests, for
# the price of one, and TMDB allows up to 20 appends per call.

MOVIE_APPENDS = {
    "credits": "credits",
    "images": "images",
    "videos": "videos",
    "keywords": "keywords",
    "watchProviders": "watch/providers",
    "reviews": "reviews",
    "similar": "recommendations,similar",
    "externalIds": "external_ids",
    "releaseDates": "release_dates",
    "alternativeTitles": "alternative_titles",
}

TV_APPENDS = {
    # aggregate_credits is the series-wide cast with episode counts per role;
    # plain `credits` on a TV record returns only the last season's crew, which
    # is almost never what a buyer means by "the cast of this show".
    "credits": "aggregate_credits,credits",
    "images": "images",
    "videos": "videos",
    "keywords": "keywords",
    "watchProviders": "watch/providers",
    "reviews": "reviews",
    "similar": "recommendations,similar",
    "externalIds": "external_ids",
    "releaseDates": "content_ratings",
    "alternativeTitles": "alternative_titles,episode_groups",
}

PERSON_APPENDS = {
    "credits": "combined_credits",
    "images": "images",
    "externalIds": "external_ids",
    "alternativeTitles": "translations",
}

SEASON_APPENDS = {
    "credits": "credits",
    "images": "images",
    "videos": "videos",
    "externalIds": "external_ids",
}

# -- charts ----------------------------------------------------------------
# Name -> (path, media_type). These are TMDB's own curated lists, the nearest
# equivalent of IMDb's Top 250 / Popular / Coming Soon pages.

CHARTS: dict[str, tuple[str, str]] = {
    "popularMovies": ("/movie/popular", "movie"),
    "topRatedMovies": ("/movie/top_rated", "movie"),
    "nowPlayingMovies": ("/movie/now_playing", "movie"),
    "upcomingMovies": ("/movie/upcoming", "movie"),
    "popularTv": ("/tv/popular", "tv"),
    "topRatedTv": ("/tv/top_rated", "tv"),
    "onTheAirTv": ("/tv/on_the_air", "tv"),
    "airingTodayTv": ("/tv/airing_today", "tv"),
    "popularPeople": ("/person/popular", "person"),
    "trendingAllDay": ("/trending/all/day", "all"),
    "trendingAllWeek": ("/trending/all/week", "all"),
    "trendingMoviesDay": ("/trending/movie/day", "movie"),
    "trendingMoviesWeek": ("/trending/movie/week", "movie"),
    "trendingTvDay": ("/trending/tv/day", "tv"),
    "trendingTvWeek": ("/trending/tv/week", "tv"),
    "trendingPeopleWeek": ("/trending/person/week", "person"),
}

# -- genres ----------------------------------------------------------------
# TMDB's genre IDs are stable and shared by both /genre/*/list endpoints, so
# they are inlined: a buyer types "Action" and the actor sends 28 without
# spending a request to look it up. The live list is still fetched when a genre
# name is not found here, so a new genre never breaks a run.

MOVIE_GENRES = {
    "action": 28, "adventure": 12, "animation": 16, "comedy": 35,
    "crime": 80, "documentary": 99, "drama": 18, "family": 10751,
    "fantasy": 14, "history": 36, "horror": 27, "music": 10402,
    "mystery": 9648, "romance": 10749, "science fiction": 878, "sci-fi": 878,
    "tv movie": 10770, "thriller": 53, "war": 10752, "western": 37,
}

TV_GENRES = {
    "action & adventure": 10759, "action": 10759, "adventure": 10759,
    "animation": 16, "comedy": 35, "crime": 80, "documentary": 99,
    "drama": 18, "family": 10751, "kids": 10762, "mystery": 9648,
    "news": 10763, "reality": 10764, "sci-fi & fantasy": 10765,
    "science fiction": 10765, "sci-fi": 10765, "fantasy": 10765,
    "soap": 10766, "talk": 10767, "war & politics": 10768, "war": 10768,
    "western": 37,
}

# TMDB's error bodies carry a numeric status_code that is more precise than the
# HTTP status. These are the ones this actor routes on.
TMDB_INVALID_KEY = 7
TMDB_RESOURCE_NOT_FOUND = 34
TMDB_SUSPENDED_KEY = 32
TMDB_INVALID_PAGE = 22
