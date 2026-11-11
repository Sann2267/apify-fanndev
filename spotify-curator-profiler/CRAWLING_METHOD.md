# How this actor gets its data

Plain HTTP against Spotify's own public web surfaces. No browser, no Spotify
account, no developer application, no API key.

---

## 1. What is closed, and why this actor is shaped the way it is

Spotify's user-profile surfaces are **not** open to an anonymous client. This
was established by testing, not assumed:

| Attempt | Result |
| --- | --- |
| `spclient.wg.spotify.com/user-profile-view/v3/profile/<user>` | `403 RBAC: access denied` |
| …the same with a valid `client-token` obtained from `clienttoken.spotify.com` | still `403` |
| `…/profile/<user>/playlists` and `…/following` | `403` |
| `api.spotify.com/v1/users/<user>` | `429 QUOTA_EXCEEDED` |
| `open.spotify.com/user/<user>` rendered HTML | display name only, no playlists |
| `open.spotify.com/embed/user/<user>` | `404` |

There is therefore **no public way to list a user's playlists or their
following**. A "user library scraper" cannot be built against an anonymous
client, and this actor does not pretend otherwise.

The inverse relationship is wide open: every playlist carries its owner's name,
id, avatar and social handle, and playlist search is unrestricted. So curators
are profiled from their playlists rather than the other way round.

---

## 2. The anonymous token

Every Spotify embed page carries a `__NEXT_DATA__` JSON blob holding an access
token marked `"isAnonymous": true`, served to anybody who loads the page:

```
GET https://open.spotify.com/embed/track/<any id>
 -> props.pageProps.state.settings.session.accessToken
```

That is the only credential used. Tokens last about an hour; a `401` triggers
one silent refresh. The web player's *other* token endpoint (`/api/token`) is
signed and is deliberately not touched.

---

## 3. Two GraphQL queries

`api-partner.spotify.com/pathfinder/v1/query` accepts the anonymous token with
no `client-token` header. Queries are persisted — an operation name plus the
SHA-256 hash of the query text, declared in the web player's JavaScript bundle
and pinned in `src/constants.py`. When Spotify rotates them the gateway answers
HTTP **200** with `{"errors":[{"message":"PersistedQueryNotFound"}]}` and the
client re-harvests from the live bundle once, then retries.

- `searchSuggestions` — discovery. One request per keyword.
- `fetchPlaylist` — one request per playlist, returning the follower count, the
  owner block **and** a page of tracks together. Because the tracks arrive in
  the same response, taste profiling costs nothing extra.

Search runs here rather than on `api.spotify.com/v1/search`, which rate-limits
by **IP** and, once tripped, refuses for roughly twenty hours.

---

## 4. Traps this actor already handles

**Search has a hard 30-result ceiling and silently ignores paging.** `limit`,
`offset` and every other paging variable are accepted without error and change
nothing. A caller who assumes pagination works quietly profiles the same fifteen
playlists forever, so the actor never paginates search and says plainly that
coverage comes from more keywords.

**Search results are geo-biased by exit IP.** The same query from a different
country returns a different set — which is a feature when profiling a local
scene and a trap when you assume the results are global.

**Spotify's editorial account dominates every niche.** Left in, "Spotify" tops
every curator ranking by an order of magnitude. Editorial playlists are
identified by owner id and excluded by default rather than silently skewing the
output.

**Pathfinder never returns 404.** A deleted or private playlist answers HTTP
200 with `{"__typename": "NotFound"}`. Read as data it becomes a curator row of
nulls; here it raises and becomes an `ERROR` record.

**Playlist covers nest one level deeper than track covers** —
`{"items": [{"sources": […]}]}` rather than `{"sources": […]}` — and sources
are not in size order. Images are chosen by dimension across both shapes.

**Playlists are not only tracks.** Podcast episodes and local files sit in the
same array under a different `__typename`; they are skipped so they cannot
distort the taste sample.

**`playcount` is a decimal string**, not a number.

---

## 5. Proxy

Off by default — neither endpoint has a WAF or an IP gate. It is worth turning
on for one specific reason: search results follow the exit IP's country, so a
proxy in the target market surfaces local curators that a default exit will
not.

---

## 6. Rate and courtesy

Requests are spaced, retries back off exponentially, and `429` and `5xx` are
retried a small number of times before a playlist is recorded as an error
rather than hammered. Only public, unauthenticated pages are read — no attempt
is made to reach the profile endpoints that require a login.
