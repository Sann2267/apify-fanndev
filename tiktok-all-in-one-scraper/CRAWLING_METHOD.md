# How this actor gets TikTok data

Recon date: **2026-09-12**. Everything below was measured, not assumed. Where a
surface is closed, the measurement that closed it is quoted so the next person
does not have to re-probe it.

## The short version

TikTok's **consumer** web app is shut to plain HTTP, and its internal JSON APIs
are signature-gated. Its **embed widgets** and **oEmbed endpoint** are not,
because they exist to be consumed by third-party sites. This actor uses only the
latter: one GET per target, parse the server-rendered state, done. No browser, no
`msToken`, no `X-Bogus`, no cookies, no account.

## What is closed, and how that was established

### The consumer pages return a WAF shell with HTTP 200

```
GET /@nasa                 -> 200, 1,462 bytes
GET /@user/video/<id>      -> 200, 1,462 bytes
```

Both bodies are the same thing: a stub whose only real content is a
`slardar-config` block naming `"bid": "slardar_us_waf"`. No data, no markup, just
the WAF's own telemetry bootstrap.

This is **not** a TLS-fingerprint gate. The body was byte-identical across
`chrome124`, `chrome120`, `safari17_0`, `firefox133` and `edge101` from the same
IP. That is worth stating plainly, because elsewhere in this portfolio a
fingerprint swap *did* reopen a blocked endpoint (Blibli's merchant API answers
403 to chrome and 200 to safari). Here it changes nothing, so the actor does not
bother trying.

### The tag / music / search / explore pages return a 375 KB decoy

```
GET /tag/nasa      -> 200, 375 KB
GET /music/<slug>  -> 200, 376 KB
GET /search?q=...  -> 200, 369 KB
GET /explore       -> 200, 384 KB
```

All four carry `<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">` — which looks
exactly like a win. It is not. Its `__DEFAULT_SCOPE__` holds five keys:

| key | size |
|---|---:|
| `webapp.i18n-translation` | 185 KB |
| `webapp.biz-context` | 42 KB |
| `webapp.app-context` | 30 KB |
| `seo.abtest` | ~0 KB |
| `webapp.a-b` | ~0 KB |

No `itemList`, no `userInfo`, no `challengeInfo`. It is the app shell plus the UI
dictionary — and the fact that all four different URLs return the *same*
251 KB payload is the giveaway. A status-only or size-only health check passes
this with flying colours, which is precisely the silent-empty failure this
codebase forbids.

### The internal APIs need a signature this actor will not forge

```
GET /api/user/detail/?uniqueId=nasa       -> 200, 0 bytes
GET /api/post/item_list/?secUid=...       -> 200, 0 bytes
GET /api/comment/list/?aweme_id=...       -> 200, {"status_code":5}
GET /api/recommend/embed_playlist/?...    -> 200, {"status_msg":"url doesn't match"}
```

These want `X-Bogus`/`X-Gnarly` plus an `msToken` minted by TikTok's own
obfuscated JS. Getting them means shipping a browser or reimplementing a signer
that is deliberately hostile to reimplementation — and re-breaking on every
rotation. Out of scope, and the actor does not advertise the surfaces that depend
on them.

### The business properties are no better

```
GET ads.tiktok.com/business/creativecenter/...      -> 200, 20 KB SPA shell, no __NEXT_DATA__
GET ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list
                                                    -> 200, {"code":40101,"msg":"no permission"}
GET library.tiktok.com/ads?region=US                -> 200, 37 KB, no __NEXT_DATA__
```

Warming the Creative Center page first does not help: it sets **zero cookies**.
The `40101` persists with or without a `Referer`, and the page's JS bundles carry
no `creative_radar_api` path to copy. So Top Ads and trend-discovery data are not
in this actor.

## What is open, and what each route gives

Every route below was verified to carry **real values**, not just a 200.

### `GET /embed/v2/<videoId>` — the richest surface

302 KB, containing `<script id="__FRONTITY_CONNECT_STATE__">`. Inside, under a
key named after the request path, sits `videoData`:

```
itemInfos         id, text (caption), createTime, covers, videoMeta,
                  diggCount, commentCount, shareCount, playCount,
                  isAd, isOriginal, isOfficial, isECVideo, brandOrganicType,
                  locationCreated
authorInfos       secUid, userId, uniqueId, nickName, signature, verified, covers
authorStats       followerCount, followingCount, heartCount, videoCount, diggCount
musicInfos        musicId, musicName, authorName, playUrl, covers
challengeInfoList structured hashtags (often empty even when the caption has tags)
imagePostInfo     non-null for photo carousels
```

Measured on video `7626254334065511711`: playCount 11000, diggCount 427,
shareCount 14, commentCount 10, author `complex` with followerCount 6,300,000 and
heartCount 394,000,000, sound "euphoria" by "inertia. & Aurenth".

The quietly valuable part is `authorStats`: **one video request also yields the
uploader's full account numbers**, so a list of video urls doubles as a creator
dataset without a second request per account.

### `GET /embed/@<username>` — account stats

310 KB, state contains `userInfo`: `id`, `uniqueId`, `nickname`, `signature`,
`verified`, `privateAccount`, `followerCount`, `followingCount`, `heartCount`,
`avatarThumbUrl`.

It does **not** contain a video list. That is a property of the surface, not a
gap in the parser, so every profile row carries
`_warning=profile_embed_does_not_publish_a_video_list`.

### `GET /embed/tag/<hashtag>` and `GET /embed/music/<musicId>` — listings

290 KB and 303 KB. Both render the same playlist payload:

```
playlistType   "hashtag" | "music"
videoList      ~6 videos for a tag, ~9 for a sound
embedInfo      id, videoCount (the tag/sound's TOTAL), artist, coverUrl
```

`videoList` rows are thinner than the video route on purpose — TikTok ships
`id`, `desc`, `playCount`, `coverUrl`, `originCoverUrl`, `dynamicCoverUrl`,
`playAddr`, `authorUniqueId`, `privateItem` and dimensions, but **no
like/comment/share counters**. Feed the ids back through `video` mode when the
full engagement set matters.

Measured on `#nasa`: `entityVideoCount` 1,919,314 with the page shipping 6
videos, the top one at 46,400,000 plays. On sound `7301919715965077506`:
`entityVideoCount` 91,900, page ships 9.

**The single-page ceiling is real and documented rather than papered over.** The
embed's own "load more" calls `/api/recommend/...`, which is the signature-gated
endpoint above. So `maxItemsPerTarget` cannot conjure a seventh video for a tag,
and every listing row says so via
`_warning=single_page_surface_embed_playlist_is_not_paginable`.

### `GET /oembed?url=<video url>` — the official record

1.3 KB of JSON: `title`, `author_name`, `author_unique_id`, `author_url`,
`thumbnail_url`, `thumbnail_width/height`, `embed_product_id`, `embed_type`. No
engagement counters. Useful for validating a large list of urls cheaply, or for
thumbnails, at 1/230th the bytes of the embed page.

It is strict about input: a **profile** url returns `200` with an **empty body**,
and an unavailable video returns `400`. Both are reported as `NOT_FOUND` with the
reason spelled out, because an empty 200 otherwise looks like a parser fault.

### Embed variants that do not exist

Confirmed with `404` (not rate-limit noise, which is `503`):
`/embed/v2/@user`, `/embed/v2/tag/<t>`, `/embed/hashtag/<t>`,
`/embed/user/<secUid>`, `/embed/playlist/<id>`, `/embed/@user/playlist`.

## Operational notes

**Rate limiting is IP-bound and arrives fast.** Repeated embed requests from one
IP start returning `HTTP 503` with an empty body after a handful of calls. The
client treats 503 as a block, rotates the TLS profile *and* the proxy session,
and backs off exponentially (`2s, 4s, 8s`) across 4 attempts. Rotating the
fingerprint alone does not lift it — the proxy is the half that matters, which is
why a proxyless run logs a warning up front.

**Retries distinguish three failure kinds, because they need different
responses:**

| Symptom | Meaning | Row |
|---|---|---|
| `503`, empty body | IP throttled | retry, then `BLOCKED_AFTER_RETRIES` |
| `404` on a valid route | entity gone | `NOT_FOUND`, no retry |
| `200` with `isError: true` / `customErrorCode` | entity gone, reported inside a 200 | `NOT_FOUND`, no retry |
| state blob missing or reshaped | TikTok moved the payload | `UPSTREAM_SHAPE_CHANGED`, logged at ERROR |
| `SlardarWAF` on an embed route | the route was moved behind the consumer gate | treated as a block, detail says so |

That last row is the canary. If TikTok ever pulls the embed widgets behind the
WAF, the actor will say exactly that instead of quietly returning nulls.

**Numbers are reported as served.** `playCount` is rounded by TikTok at scale
(11000, not 11043). The `videoMeta` block is unreliable in two different ways,
both observed on 2026-09-12: on video `7626254334065511711` it was **absent
entirely** on one fetch (width/height/duration all null) and present with the
placeholder values `ratio: 99, duration: 99` on another. Nothing here is
corrected or back-filled; the fields are nullable in the output schema and the
rounding is flagged in `_warning`.

## Reproducing the recon

```bash
python test_local.py              # all five modes against live TikTok
python test_local.py video music  # just these two
```

The test asserts **non-null required fields per mode**, not just "it returned
rows" — a mode that yields a row of nulls fails. That is the check that would
have caught the 375 KB decoy if it had ever been wired in.
