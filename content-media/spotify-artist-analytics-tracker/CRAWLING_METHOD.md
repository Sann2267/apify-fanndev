# How this actor gets its data

Plain HTTP against Spotify's own public web surfaces. No browser, no Spotify
account, no Spotify for Artists login, no developer application, no API key.

---

## 1. The anonymous token

Every Spotify embed page — the little player you can paste into a blog —
carries a `__NEXT_DATA__` JSON blob, and inside it Spotify hands the visitor an
access token marked `"isAnonymous": true`. That token is served to anybody who
loads the page, and it is the only credential this actor uses.

```
GET https://open.spotify.com/embed/track/<any id>
 -> props.pageProps.state.settings.session.accessToken
```

Tokens last about an hour; a `401` mid-run triggers one silent refresh. The web
player's *other* token endpoint (`/api/token`) is signed and is deliberately
not touched.

---

## 2. One GraphQL query per artist

Spotify's web player talks to `api-partner.spotify.com/pathfinder/v1/query`,
which accepts the anonymous token directly — no `client-token` header needed.

Queries there are *persisted*: the client sends an operation name plus the
SHA-256 hash of the query it means, and those hashes are declared in the web
player's JavaScript bundle as `new X("queryArtistOverview","query","9f8134ef…")`.
This actor ships the hashes it needs pinned in `src/constants.py`, harvested
2026-09-20. Spotify rotates them on every web player deploy, and the symptom is
an HTTP **200** whose body is `{"errors":[{"message":"PersistedQueryNotFound"}]}`.
When that happens the client fetches the live bundle once, re-harvests every
hash and retries, so a Spotify deploy costs one extra request instead of a
broken actor.

`queryArtistOverview` returns roughly 110 KB and carries every public number on
an artist page in a single response: stats, discography, top tracks with play
counts, discovery playlists, related artists, concerts and social links. So the
whole record is **one request per artist** — nothing is assembled from
follow-up calls.

Looking an artist up by *name* adds one `searchSuggestions` query. That is the
web player's own search box, used here in preference to
`api.spotify.com/v1/search` because the latter rate-limits by **IP** and, once
tripped, refuses for about twenty hours.

---

## 3. Growth tracking is local, because Spotify publishes no history

Nothing on Spotify's side remembers yesterday's monthly listener count. Each
run therefore writes its readings to a **named** Apify key-value store and
compares the next run against them. The store has to be named rather than
run-scoped: a run-scoped store is deleted with its run, which would make every
run report `isFirstReading`.

Deltas are also expressed per day, so a weekly schedule and a daily schedule
produce comparable numbers.

---

## 4. Traps this actor already handles

**Pathfinder never returns 404.** A wrong or retired artist id comes back as
HTTP 200 whose entity is `{"__typename": "NotFound"}`. Read as data it yields a
row of nulls; here it raises and becomes an `ERROR` record.

**`worldRank` is `0`, not null, for unranked artists** — which is nearly all of
them. Passing it through unchanged puts "0" in a rank column, and any sort then
reads it as the best possible rank. It is normalised to `null`.

**`discoveredOnV2` is padded with placeholders.** Spotify mixes
`{"__typename": "GenericError"}` entries into the same array as real playlists
(4 of 20 on the artist this was verified against). Unfiltered, they become rows
of nulls and inflate the count.

**Spotify uses two spellings for image dimensions in one payload.** Album and
avatar sources carry `width`/`height`; artist header images carry
`maxWidth`/`maxHeight` for the identical concept. Reading only one spelling
makes every candidate tie at zero area, so "largest image" silently returns an
arbitrary one.

**Two different list shapes in the same object.** `relatedArtists` items are
bare artist objects, while `discoveredOnV2` and `featuringV2` items wrap the
entity in a `data` key. They are parsed differently on purpose.

**Discography items hide the release one level down.** Each entry is
`{"releases": {"items": [ <the album> ]}}`; reading the entry itself returns
nothing, which is how a naive parse ends up with an empty discography.

**`playcount` is a decimal string**, not a number — `"1180466354"`.

---

## 5. Proxy

Off by default. This endpoint has no WAF and no IP gate, and the Apify
datacenter range reaches it, so a default-on proxy would bill for nothing.

---

## 6. Rate and courtesy

Requests are spaced, retries back off exponentially, and `429` and `5xx` are
retried a small number of times before the artist is recorded as an error
rather than hammered. Only public, unauthenticated pages are read.
