# How this actor gets its data

Plain HTTP against Spotify's own public web surfaces. No browser, no Spotify
account, no developer application, no API key.

---

## 1. The public charts service — no credential at all

```
GET https://charts-spotify-com-service.spotify.com/public/v0/charts
```

This answers 83 KB of JSON to an anonymous request with no token, no cookie and
no headers beyond a plain `Accept`. It carries the three global weekly charts —
tracks, albums and artists — with fifty entries each, and every entry has real
chart data: `currentRank`, `previousRank`, `peakRank`, `entryStatus`,
`appearancesOnChart`.

That single path is all there is publicly. Per-country charts, daily charts and
historical dates live under `/auth/v0/…`, which answers `401` without a
logged-in session, and every other path variant tried returns `404`. Hence the
second surface below.

---

## 2. Country charts, via the anonymous token

Every Spotify embed page carries a `__NEXT_DATA__` blob holding an access token
marked `"isAnonymous": true`, served to anybody who loads the page:

```
GET https://open.spotify.com/embed/track/<any id>
 -> props.pageProps.state.settings.session.accessToken
```

That token is accepted by `api-partner.spotify.com/pathfinder/v1/query`, the
web player's GraphQL gateway, with no `client-token` header. Queries there are
*persisted*: an operation name plus the SHA-256 hash of the query text, both
declared in the web player's JavaScript bundle. The hashes are pinned in
`src/constants.py` (harvested 2026-09-20); when Spotify rotates them the
gateway answers HTTP **200** with `{"errors":[{"message":
"PersistedQueryNotFound"}]}`, and the client re-harvests them from the live
bundle once and retries.

Chart playlists are read with `fetchPlaylist` — the same query as any other
playlist. Rank is playlist position.

---

## 3. Why the chart catalogue is pinned rather than discovered

**Spotify hides chart playlists from every search surface.** Searching for
"Top 50 - Indonesia" through the web player's own search returns ordinary
editorial playlists — Hot Hits Indonesia, New Music Friday Indonesia — and
never the chart itself. The Web API's playlist search does not return them
either; it returns user-made imitations with similar names. Search results are
also biased by exit IP, so the same query from another country returns a
different set.

There is therefore no way to discover a chart by name at runtime. Every id in
`src/catalog.py` was fetched and confirmed to be a live ranked playlist: 49
daily, 14 weekly.

---

## 4. Traps this actor already handles

**Pathfinder never returns 404, and retired charts look identical to typos.**
A dead id answers HTTP 200 with `{"__typename": "NotFound"}`. Spotify's Viral
50 charts were discontinued and every one of their ids now does exactly this,
so the actor keeps a `RETIRED` list and explains what happened instead of
reporting an empty chart.

**Spotify writes `0`, not null, for "no value".** On the public charts service,
`previousRank: 0` means *was not on the chart*, and `peakRank: 0` /
`appearancesOnChart: 0` mean *not published*. Passing those through claims a
track was ranked zeroth and peaked at zero. All of them are normalised to
`null`.

**The chart attributes give a count with no names.** `new_entries_count` says
"3" and never which three, which is why movement is computed locally from the
previous run's order rather than read from Spotify.

**A first run is not a 100% turnover.** With no stored previous order, marking
every entry `NEW_ENTRY` would be indistinguishable from a real complete
turnover, so the first run marks entries `BASELINE`.

**Image sources are not in size order, and playlists nest them one level
deeper** than tracks do — `{"items": [{"sources": […]}]}` rather than
`{"sources": […]}`. Images are chosen by dimension across both shapes.

**`playcount` is a decimal string**, not a number.

---

## 5. Proxy

Off by default. Neither endpoint has a WAF or an IP gate. Chart contents do not
follow the exit IP either — the territory comes from the chart id, not from
your address — so a proxy changes nothing about the result.

---

## 6. Rate and courtesy

One request per chart; requests are spaced, retries back off exponentially, and
`429` and `5xx` are retried a small number of times before a chart is recorded
as an error rather than hammered. Only public, unauthenticated pages are read.
