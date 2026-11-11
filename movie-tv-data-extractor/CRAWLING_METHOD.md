# Crawling method

Recon notes for this actor: what was surveyed, what was found, and which of it
is load-bearing. Written 2026-09-21.

## 1. IMDb was the original target, and it was rejected

The brief was an IMDb all-in-one extractor. IMDb was surveyed first. The result
is counter-intuitive enough to be worth keeping.

### The pages are walled

Every `www.imdb.com` HTML page answers **HTTP 202 with a 1,997-byte body and
zero content**, carrying `x-amzn-waf-action: challenge` and an AWS WAF
proof-of-work bootstrap (`window.gokuProps`, `challenge.js`). This was
identical across all five TLS profiles this portfolio tests — `chrome131`,
`chrome124`, `safari17_0`, `firefox133`, `edge101` — so it is not a fingerprint
gate. `m.imdb.com` behaves the same.

### The API is wide open

`caching.graphql.imdb.com` and `api.graphql.imdb.com` accept **arbitrary ad-hoc
GraphQL queries anonymously**. No token, no persisted-query hash, no signature.
The requirements are only:

```
Content-Type: application/json
x-imdb-client-name: imdb-web-next
Origin: https://www.imdb.com
Referer: https://www.imdb.com/
```

A bare POST without those headers is 403; with them, a full query for
`title(id: "tt1375666")` returns rating, vote count and plot. GET is refused
with a real error message (`GraphQL requests must use POST`), not a WAF
challenge. Introspection is the one thing that is gated (`Unauthorized
introspection request`).

`v3.sg.media-imdb.com/suggestion/…` and the v2 equivalent (the autocomplete
endpoint) are also fully open with no WAF.

### Why none of that was used

Three independent statements of the same rule:

1. `www.imdb.com/robots.txt` ends with `User-agent: *` / `Disallow: /`.
2. Its header comment: *"Use of any device, tool, or process designed to data
   mine or scrape the content using automated means is prohibited without prior
   written permission from IMDb."*
3. Every GraphQL response body carries its own disclaimer:
   *"Public, commercial, and/or non-private use of the IMDb data provided by
   this API is not allowed."*

The GraphQL hosts serve no `robots.txt` of their own (403 / 404), so there is no
permission to be read there either. A rented Store actor is public, commercial
use. The surface being open is not the same as the surface being available.

**Do not revisit this.** The finding is not "IMDb is hard"; it is "IMDb is easy
and off-limits". A future session that rediscovers the open GraphQL endpoint
should stop at this file.

## 2. TMDB: which host, and one trap

TMDB was chosen because its API terms permit commercial use with attribution,
and because it carries the IMDb id of nearly everything it holds — which keeps
an IMDb-keyed dataset joinable without touching IMDb.

**One load-bearing distinction.** `www.themoviedb.org` — the *website* —
disallows `ClaudeBot`, `Claude-User`, `Claude-Web`, `Claude-SearchBot` and
`anthropic-ai` in its own `robots.txt` with `Disallow: /`. Only
`api.themoviedb.org` is used in this actor. **There is no HTML fallback
anywhere in this code and none should ever be added** — not as a rescue path,
not for a field the API is missing. If the API does not have it, the actor does
not publish it.

`api.themoviedb.org` serves no `robots.txt` (404). It is a documented,
key-authenticated API; the key is the permission.

## 3. No gate, so the client is plain

TMDB applies no fingerprint gate, no IP gate and no challenge. `curl_cffi` is
used for consistency with the rest of this portfolio and for connection reuse,
not to defeat anything. The rate limit (~50 requests/second) follows the **key**,
not the address, which is why the proxy is off by default and documented as
useful only for choosing an exit country.

Three things the client does have to get right:

- **Credential form detection.** TMDB issues a 32-character v3 key and a v4 JWT
  read-access token from the same settings page. A v3 key goes in the query
  string, a v4 token in an `Authorization: Bearer` header, and sending either
  the other way is an instant 401. The form is sniffed (`eyJ` prefix plus two
  dots) rather than configured, because buyers paste whichever they copied.
- **A 401 is fatal, never retried.** It cannot come right, and four retries per
  request across a 500-title run would spend the buyer's compute to reach the
  same answer.
- **The key is stripped from every published URL.** Records carry the exact
  endpoint they came from, which is only safe because `redact()` runs first.

## 4. append_to_response is the whole cost model

TMDB allows up to 20 appended sub-resources per request and charges for one.
Credits, external ids, keywords, images, videos, watch providers, release dates,
alternative titles and recommendations all travel in the same call as the title
itself.

This is why every `include*` switch in the input schema changes record size but
not request count, and why the schema says so explicitly — a buyer who assumes
each toggle costs a request will under-use the actor.

Two per-media-type details that are easy to get wrong:

- **A series needs `aggregate_credits`, not `credits`.** Plain `credits` on a TV
  record returns only the most recent season's crew. The aggregate version
  returns the series-wide cast with per-actor episode counts, and its entries
  carry a `roles[]` array (an actor can play several parts) and a `jobs[]`
  array instead of a scalar `character` / `job`. Both shapes are flattened to
  one in `parse_cast` / `parse_crew`.
- **`include_image_language` is required** when appending images, or TMDB
  filters the gallery to the run's language and a film with no English-tagged
  poster returns an empty gallery.

## 5. Discover parameters that fail silently

TMDB's `/discover` endpoint **ignores** parameters that do not apply instead of
rejecting them, which looks exactly like a filter that does not work:

- Films filter on `primary_release_date.gte/lte`; series on
  `first_air_date.gte/lte`. Sending the film parameter to `/discover/tv` is
  accepted and ignored.
- `with_people` is movie-only. `with_networks` is tv-only. Both are dropped for
  the wrong media type — and the actor logs a note rather than dropping them
  quietly.
- `with_watch_providers` does nothing without `watch_region`, because
  availability is per country. The actor fills the region in from the run's
  `region` when the buyer did not set one.
- `with_genres` joined with `|` means *any*; joined with `,` means *all*. Three
  genres with `all` returns almost nothing — that is TMDB being literal.

Genre **names** are mapped to ids from an inlined table, with a live
`/genre/{type}/list` call only as a fallback for a name the table does not know,
so a genre added next year resolves instead of the filter silently vanishing.
Film and series genre tables are different (`Action` is 28 for films, but series
have `Action & Adventure` at 10759 and no plain `Action`).

## 6. Payload traps handled in the parsers

- **`budget: 0` and `revenue: 0` mean "unknown"**, not zero dollars. Both become
  `null`, and `profitUsd` / `returnOnBudget` are computed only when both numbers
  are real — otherwise an unknown budget sorts as infinite profit.
- **Gravatar avatars arrive as `/https://secure.gravatar.com/avatar/abc`** — a
  path with an absolute URL inside it. Joining the CDN host on the front
  produces a 404.
- **Movie keywords are under `keywords.keywords`; series keywords are under
  `keywords.results`.** Same appended block, two different shapes.
- **Certifications live in `release_dates` for films and `content_ratings` for
  series**, in two different structures. Both reduce to one `certification`
  string so a mixed dataset filters with one expression.
- **Release `type: 3` is theatrical**; 4 is digital, 5 physical. Taking the first
  entry gives you the DVD date about a third of the time.
- **A collection's `parts` are not in release order.** They are sorted here.
- **A person's `combined_credits` are in no useful order** — the first ten rows
  of a 300-credit actor are voice cameos and archive footage. Sorted by
  popularity.
- **`page` above 500 is refused** on every paged endpoint, and `total_pages` is
  authoritative: asking for 30 pages of a 3-page result set otherwise spends 27
  requests on empty responses.

## 7. Fixtures

`tests/fixtures/*.json` are hand-built payloads matching the shapes above,
covering the aggregate-credits shape, the gravatar avatar, the zero-budget case,
the two keyword shapes and the specials season. They let the whole parser and
Markdown layer be regression-tested with no key and no network
(`python test_local.py --offline`). The live sweep in the same file is what
proves the endpoint paths and parameter names, which fixtures by construction
cannot.
