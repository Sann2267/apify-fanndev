# How this actor gets its data

Plain HTTP against Spotify's own public web surfaces. No browser, no Spotify
account, no developer application, no API key, and nothing is logged into.

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

Tokens last about an hour. A `401` mid-run triggers one silent refresh.

The web player's *other* token endpoint (`/api/token`) is signed and is
deliberately not touched.

---

## 2. The GraphQL gateway

Spotify's web player talks to `api-partner.spotify.com/pathfinder/v1/query`.
It accepts the anonymous token directly — no `client-token` header is needed.

Queries there are *persisted*: instead of sending GraphQL text, the client sends
an operation name plus the SHA-256 hash of the query it means. Those hashes are
declared in the web player's own JavaScript bundle, in the form

```js
new X("fetchPlaylist", "query", "86dde7b9…", null)
```

This actor ships the hashes it needs pinned in `src/constants.py`, harvested
2026-09-20. Spotify rotates them whenever it deploys a new web player, and the
symptom is an HTTP **200** whose body is `{"errors":[{"message":
"PersistedQueryNotFound"}]}`. When that happens the client fetches the live
bundle once, re-harvests every hash, and retries — so a Spotify deploy costs one
extra request instead of a broken actor. The pinned copies exist so the common
case never pays for a multi-megabyte bundle download.

Operations used here: `fetchPlaylist` (playlist header plus a page of tracks)
and `getTrack` (a single song, with its label and copyright lines).

---

## 3. Why ISRC needs a second, rate-limited endpoint

`api.spotify.com/v1/search` also accepts the anonymous token, and it is the only
place ISRC and the 0–100 popularity score are visible. Every *entity* endpoint
on that host (`/v1/tracks`, `/v1/artists`, `/v1/albums`, `/v1/users`, …) answers
`429 QUOTA_EXCEEDED` to an anonymous token no matter how idle it is, so search
is the only way in — one request per track.

Search itself is rate-limited, and measurement on 2026-09-20 showed the limit is
harsh and **bound to the IP, not the token**: a few dozen requests, then `429`
with `Retry-After: 73444` (about 20 hours), and a freshly minted token does not
clear it. Hence enrichment is opt-in, capped, proxy-friendly, and stops the
moment the first `429` arrives rather than retrying into a longer ban.

Everything else in this actor runs on the GraphQL gateway, which showed no such
ceiling.

---

## 4. Traps this actor already handles

**Pathfinder never returns 404.** A playlist that does not exist, one that is
private, and a typo in an id all come back as HTTP 200 whose entity is
`{"__typename": "NotFound"}`. Reading such a response as data produces a row of
nulls; here it raises and becomes an `ERROR` record.

**Image sources are not in size order, and playlists nest them one level
deeper.** Covers arrive as `{"sources": [...]}` on tracks and albums but as
`{"items": [{"sources": [...]}]}` on playlists, and within a list a 300 px
cover routinely precedes the 64 px and 640 px ones. Picking by position gives
thumbnails; picking only the first shape gives a null playlist cover. Images are
chosen by dimension, across both shapes.

**`playcount` is a decimal string, not a number.** It arrives as `"174332694"`.

**Playlists are not only tracks.** Podcast episodes and local files sit in the
same `items` array under a different `__typename`; they are skipped, while the
position counter keeps counting so positions stay truthful.

**The page-size echo lies.** `pagingInfo` repeats whatever limit was requested,
even when the server returned fewer items, so paging is driven by counting the
items that actually arrived.

**One song, many ids.** Spotify mints a separate track id per release, so the
same recording can appear under several ids with different play counts. ISRC
matching prefers the playlist's own `trackUri` and falls back to a title-plus-
artist match only when that fails — labelling the result honestly in
`isrcLookup`, because a different release can carry a different ISRC.

---

## 5. Proxy

Off by default. None of these endpoints carries a WAF or an IP gate, and the
Apify datacenter range reaches all of them, so a default-on proxy would bill for
nothing. Turn it on for ISRC enrichment, where the rate limit is per IP.

---

## 6. Rate and courtesy

Requests are spaced, retries back off exponentially, and `429` and `5xx` are
retried a small number of times before the input is recorded as an error rather
than hammered. Only public, unauthenticated pages are read.
