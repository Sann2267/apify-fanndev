# Movie & TV Data Extractor (All-in-One)

Nine movie and TV extractors in one actor, built on The Movie Database's
official API. Paste IMDb ids, TMDB links, or just the names of what you want —
the actor works out what each one is and returns a clean, flat record.

No browser, no headless Chrome, no HTML parsing. Every mode is plain JSON over
HTTPS, which is why a hundred full film records cost a hundred requests and
finish in under a minute on the smallest memory setting.

**You bring your own TMDB key.** It is free, takes about a minute, and there is
no usage charge on TMDB's side: sign up at
[themoviedb.org/signup](https://www.themoviedb.org/signup), open
[themoviedb.org/settings/api](https://www.themoviedb.org/settings/api), and
paste either the short **API Key** or the long **API Read Access Token** into
the `tmdbApiKey` field. The actor detects which one you gave it.

---

## Why this is a TMDB actor and not an IMDb scraper

If you came here searching for an IMDb scraper, this is the honest version of
that answer, and it is worth thirty seconds of your time.

IMDb's own terms forbid what a rented scraper does. `imdb.com/robots.txt` ends
with `User-agent: *` / `Disallow: /`, its header states that automated data
mining is prohibited without written permission, and IMDb's API returns this
inside every response body:

> "Public, commercial, and/or non-private use of the IMDb data provided by this
> API is not allowed."

Every IMDb page also sits behind an AWS WAF challenge that returns HTTP 202 with
zero content bytes to any non-browser client.

TMDB is the alternative that is actually meant to be used this way: a public,
documented API whose terms permit commercial use with attribution, maintained
by a community of around a million editors. **And it keeps the IMDb thread
intact** — TMDB stores the IMDb id of nearly every film, series and person it
holds, so this actor takes `tt1375666` as input and returns `imdbId` and
`imdbUrl` on the way out. Your IMDb-keyed spreadsheet still joins.

What TMDB does **not** have, so you are not surprised later: IMDb trivia,
Metacritic scores, IMDb's own Top 250 ordering, and IMDb's volume of user
reviews. TMDB has its own ratings, its own curated charts, and a much smaller
review corpus. Budget, revenue, cast, crew, certifications, streaming
availability, episodes and people are all comprehensive.

---

## The nine modes

| Mode | What one run gives you |
|---|---|
| **Title Details** | Full record per film or series: overview, genres, runtime, budget, revenue, profit, cast with characters, directors and writers by name, age certification per country, streaming availability, keywords, trailer, posters |
| **Person Details** | An actor, director or creator: biography, birth and death, complete filmography sorted by popularity, official IMDb / Instagram / X / TikTok handles |
| **Seasons & Episodes** | Every episode of a series with **its own rating**, air date, runtime, synopsis, director, writer and guest stars |
| **Reviews** | User reviews with **the reviewer's own 0–10 score**, HTML stripped and whitespace normalised, ready for sentiment work |
| **Discover** | Advanced search: genre, year range, minimum rating, minimum vote count, runtime, original language, streaming service, studio, network, person, keyword |
| **Search by Name** | Turn a column of names into TMDB ids that every other mode accepts |
| **Charts** | Popular, Top Rated, Now Playing, Upcoming, On The Air, Airing Today and Trending — for films, series and people |
| **Collections** | A whole franchise in release order, from the collection's name or from any single film in it |
| **Companies & Networks** | A studio or network profile with its homepage and headquarters, optionally with its entire catalogue |

---

## What makes it cheap

TMDB lets a single request carry up to twenty appended sub-resources. This
actor uses that everywhere. Asking for a film **with** its cast, crew, external
ids, keywords, certifications, streaming availability, trailers and image
gallery is **one HTTP request** — not nine.

That is why every "include" switch in the input is on or off purely by how
large you want each record to be, not by how much the run will cost. Switching
all of them on costs exactly the same number of requests as switching them all
off.

Two switches genuinely do cost more, and both say so in their description:

- **`fetchFullDetails`** turns any list mode into a bulk extractor — each thin
  discover/search/chart row becomes a complete record. One extra request per
  row.
- **`includeCompanyTitles`** walks a studio's whole catalogue.

A 100-film discover run with full details is about 101 requests and finishes in
roughly a minute at 512 MB.

---

## RAG and LLM output

Set **Output format** to `Markdown` (or `Both`) and every record is also
published as a self-contained document:

```markdown
# Inception (2010)

*Your mind is the scene of the crime.*

- **Type:** Movie
- **Released:** 2010-07-15
- **Runtime:** 2h 28m (148 min)
- **Genres:** Action, Science Fiction, Adventure
- **Rating:** 8.4/10 from 36,258 votes
- **Certification:** PG-13
- **IMDb:** tt1375666

## Overview
Cobb, a skilled thief who commits corporate espionage by infiltrating the
subconscious of his targets, is offered a chance to regain his old life...

## Key crew
- **Directed by:** Christopher Nolan
- **Music by:** Hans Zimmer

## Cast
- Leonardo DiCaprio as Dom Cobb
- Joseph Gordon-Levitt as Arthur

## Box office
- **Budget:** $160,000,000
- **Revenue:** $839,030,630
- **Profit:** $679,030,630
- **Return on budget:** 5.244x

## Where to watch (US)
- **Streaming:** Max
```

Three things about these documents matter if you are building a retrieval
index:

- **Each one stands alone.** The film is named in the text, not only in a
  metadata column, so a chunk retrieved by itself still says what it is about.
- **Empty fields are omitted, never rendered as `None` or `N/A`.** A model
  reading "Budget: None" will tell someone the budget was none.
- **Diagnostic rows are never rendered as prose.** A failed lookup stays
  structured instead of teaching your index that "no results" is a fact about a
  film.

---

## Input examples

**Films and shows you already have, in any mix of formats**

```json
{
  "mode": "titleDetails",
  "tmdbApiKey": "YOUR_TMDB_KEY",
  "titleTargets": [
    "tt1375666",
    "https://www.imdb.com/title/tt0903747/",
    "https://www.themoviedb.org/movie/27205-inception",
    "tv:1399",
    "The Grand Budapest Hotel"
  ],
  "region": "GB"
}
```

**Every episode of a series, with per-episode ratings**

```json
{
  "mode": "seasonEpisodes",
  "tmdbApiKey": "YOUR_TMDB_KEY",
  "tvTargets": ["tt0903747"],
  "seasons": []
}
```

**Highly-rated recent sci-fi that is on Netflix in Indonesia**

```json
{
  "mode": "discoverTitles",
  "tmdbApiKey": "YOUR_TMDB_KEY",
  "discoverMediaType": "movie",
  "genres": ["Science Fiction"],
  "yearFrom": 2020,
  "yearTo": 2025,
  "minRating": 7,
  "minVotes": 300,
  "withWatchProviders": ["8"],
  "watchRegion": "ID",
  "sortBy": "vote_average.desc",
  "fetchFullDetails": true,
  "maxPagesPerTarget": 3
}
```

**A RAG corpus of the Top Rated chart**

```json
{
  "mode": "charts",
  "tmdbApiKey": "YOUR_TMDB_KEY",
  "chartNames": ["topRatedMovies"],
  "maxPagesPerTarget": 10,
  "fetchFullDetails": true,
  "outputFormat": "markdown"
}
```

---

## Output shape

Every record — film, series, person, season, episode, review, chart row,
collection, company or diagnostic — leaves in the same envelope, so one dataset
stays joinable:

```json
{
  "item_type": "title",
  "id": "movie:27205",
  "data": { "...": "the record body" },
  "metadata": {
    "scrapedAt": "2026-09-21T13:40:02+00:00",
    "sourceUrl": "https://api.themoviedb.org/3/movie/27205?...",
    "mode": "titleDetails",
    "query": "tt1375666",
    "rank": 1
  }
}
```

The `id` is namespaced by media type (`movie:27205`, `tv:1399`, `person:138`,
`tv:1396:s1:e1`, `review:5b2f…`, `collection:263`, `company:41077`) so two
records can never collide across types.

A few normalisations worth knowing about:

- **Image paths become URLs**, at the size you picked. TMDB returns
  `/abc.jpg`, which is useless on its own.
- **`budget: 0` becomes `null`.** TMDB writes 0 for "nobody has entered this",
  which is not the same as a film that cost nothing — and `profitUsd` and
  `returnOnBudget` are only computed when both numbers are real, so an unknown
  budget never shows up as infinite profit in a sorted spreadsheet.
- **A series' cast is the aggregate cast**, with per-actor episode counts. TMDB's
  plain `credits` on a series returns only the last season's crew, which is
  almost never what anyone means by "the cast of this show".
- **Your API key is stripped from every published URL** before it reaches the
  dataset or the log.

---

## Diagnostics

The run never finishes with an empty dataset. Anything that could not be
resolved becomes a row saying which input failed and why — `unresolvable_target`,
`not_found`, `wrong_media_type`, `no_collection`, `no_reviews`, `no_results`,
`fetch_failed`, `auth_failed`. A downstream job joining on this output reads
zero rows as a crash, so it always gets an answer.

A rejected API key stops the run immediately rather than retrying: it cannot
come right, and retrying it once per request across a large run would only
spend your compute to reach the same conclusion.

---

## Proxies

Off by default, and that is the right setting. TMDB is a keyed API with no IP
gate — it serves a datacentre address exactly as it serves a residential one,
and its rate limit follows your key rather than your address. The only reason
to turn a proxy on is to make requests leave from a specific country when you
care about region-sensitive fields such as streaming availability.

---

## Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.
