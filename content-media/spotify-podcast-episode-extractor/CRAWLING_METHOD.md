# How this actor gets its data

Plain HTTP against Spotify's own public web surfaces. No browser, no Spotify
account, no developer application, no API key.

---

## 1. The anonymous token

Every Spotify embed page carries a `__NEXT_DATA__` JSON blob holding an access
token marked `"isAnonymous": true`, served to anybody who loads the page:

```
GET https://open.spotify.com/embed/track/<any id>
 -> props.pageProps.state.settings.session.accessToken
```

That is the only credential used here. Tokens last about an hour; a `401`
mid-run triggers one silent refresh. The web player's *other* token endpoint
(`/api/token`) is signed and is deliberately not touched.

---

## 2. Three GraphQL queries

`api-partner.spotify.com/pathfinder/v1/query` accepts the anonymous token with
no `client-token` header. Queries are *persisted*: an operation name plus the
SHA-256 hash of the query text, both declared in the web player's JavaScript
bundle. The hashes are pinned in `src/constants.py` (harvested 2026-09-20);
when Spotify rotates them the gateway answers HTTP **200** with
`{"errors":[{"message":"PersistedQueryNotFound"}]}` and the client re-harvests
them from the live bundle once, then retries.

- `queryShowMetadataV2` — publisher, description, topics, **rating and review
  count**, cover art.
- `queryPodcastEpisodes` — the episode list, 100 per request, paged with
  `pagingInfo.nextOffset`.
- `getEpisodeOrChapter` — a single episode, for `episodeUrls`.

Looking a show up by *name* adds one `searchSuggestions` query — the web
player's own search box. It is used in preference to
`api.spotify.com/v1/search` because the latter rate-limits by **IP** and, once
tripped, refuses for roughly twenty hours.

---

## 3. The description is the product

Spotify exposes no structured guest, chapter or sponsor data. All of it lives
in one HTML description blob, so this actor parses it:

- **Chapters** from timestamp lines (`12:34 Topic`, `1:02:03 - Topic`).
  Anything whose offset exceeds the episode's own duration is dropped — those
  matches are dates, prices and scores that happen to be shaped like a
  timestamp, and without that check a 400-page description produces dozens of
  fake chapters.
- **Links** de-duplicated and stripped of the trailing punctuation that
  swallows a URL when it ends a sentence.
- **Sponsor domains** are the link domains minus the show's own distribution
  and social platforms — without that filter every podcast "sponsors"
  Spotify, Apple and Instagram.
- **Guest and episode-number hints** from the title, split on the separators
  podcast titles conventionally use and filtered to things shaped like a
  person's name. This is a heuristic and is named as one.

---

## 4. Traps this actor already handles

**Pathfinder never returns 404.** A wrong or private show id comes back as
HTTP 200 whose entity is `{"__typename": "NotFound"}`. Read as data it yields a
row of nulls; here it raises and becomes an `ERROR` record.

**The show query does not know how many episodes there are.** It returns one
sample episode and no `totalCount`; only the episode query carries the real
figure, so the show record takes its `episodeCount` from there.

**Episodes are newest-first, which is a cost control, not just an order.**
Once a page goes older than `releasedAfter`, every later page is older too, so
paging stops. Without that, filtering a recent window on a long-running show
downloads the whole back catalogue in order to throw it away.

**Descriptions come twice.** `description` and `htmlDescription` hold the same
text with different markup; `htmlDescription` is preferred and then stripped,
because the plain field still carries HTML entities.

**Image sources are not in size order.** A 300 px cover routinely precedes the
64 px and 640 px ones, so images are chosen by dimension rather than position.

---

## 5. Proxy

Off by default. This endpoint has no WAF and no IP gate, and the Apify
datacenter range reaches it, so a default-on proxy would bill for nothing.

---

## 6. Rate and courtesy

Requests are spaced, retries back off exponentially, and `429` and `5xx` are
retried a small number of times before the show is recorded as an error rather
than hammered. Only public, unauthenticated pages are read; transcript text and
paywalled audio are not accessed.
