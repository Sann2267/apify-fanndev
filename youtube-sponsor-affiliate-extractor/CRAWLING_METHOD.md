# Crawling method — YouTube Sponsor & Affiliate Link Extractor

All figures measured 2026-09-20 from a single residential IP, `curl_cffi` with
TLS impersonation, no login and no cookies.

## The surface that works

`GET https://www.youtube.com/watch?v=<id>` — a plain HTML page, 1.1–1.3 MB,
carrying an inline assignment:

```js
var ytInitialPlayerResponse = { ... };
```

`videoDetails.shortDescription` is the complete description with newlines
preserved. `microformat.playerMicroformatRenderer` adds `publishDate`,
`uploadDate` and `category`. `captions.playerCaptionsTracklistRenderer.captionTracks`
lists the subtitle languages.

Measured description sizes:

| Video | bytes | URLs |
| --- | --- | --- |
| `dQw4w9WgXcQ` | 2375 | 11 |
| `kJQP7kiw5Fk` | 848 | 10 |
| `9bZkp7q19f0` | 491 | 11 |
| `jNQXAC9IVRw` | 272 | 0 |

## Extraction must count braces, not match a regex

A non-greedy `ytInitialPlayerResponse\s*=\s*(\{.+?\})` stops at the **first**
closing brace and returns a truncated object. During recon that produced
`desc=0B` and an empty title for `kJQP7kiw5Fk`, whose description is in fact 848
bytes. The failure is indistinguishable from "this video has no description",
which is why `extract_json_blob` is a string-aware brace scanner.

## The reduced page

The watch page returns 200 every time, but does not always include the player
response. Three attempts per video, same IP, same session:

| Video | attempts carrying a description |
| --- | --- |
| `dQw4w9WgXcQ` | 3/3 |
| `jNQXAC9IVRw` | 2/3 |
| `9bZkp7q19f0` | 1/3 |
| `M3HKLzjvKPc` | 1/3 |
| `3PFJ9SETS4M` | 1/3 |
| `kJQP7kiw5Fk` | 0/3 |

Variants tried on `9bZkp7q19f0`, five attempts each:

| Variant | hits |
| --- | --- |
| plain | 2/5 |
| `Cookie: CONSENT=YES+cb; SOCS=CAI` | 1/5 |
| `&bpctr=9999999999&has_verified=1` | 1/5 |
| cookie + `bpctr` | 1/5 |
| `m.youtube.com` + Android UA | 1/5 |

Nothing helps. Retrying does: with the six-attempt ladder, `kJQP7kiw5Fk`
(0/3 above) parsed on attempt 5 in live testing.

This is a reduced page, not a block — no challenge markers, no 403, full HTML.
The same shape is documented for Amazon detail pages elsewhere in this portfolio.

## Channel video IDs come from the raw page, deliberately

On `@mkbhd/videos`, the parsed `ytInitialData` object was structurally valid —
`responseContext`, `contents`, `header`, `metadata`, `topbar`, `microformat` all
present — and contained **zero** video IDs, while the raw body held 30 (210 on a
later fetch). The grid is populated in a region the top-level parse does not
always cover.

So `parse_channel_video_ids` scans the text from the `ytInitialData` assignment
onward, which is surface-accurate and cannot pick up IDs from earlier prefetch
scripts.

## The transcript: closed, and here is exactly how

`captionTracks[].baseUrl` is a signed URL carrying `signature`, `expire`,
`sparams`, `ip=0.0.0.0`, `key=yt8`. Every request to it returned **HTTP 200 with
a 0-byte body**:

| Variant | result |
| --- | --- |
| plain | 200, 0 B |
| `&fmt=json3` | 200, 0 B |
| `&fmt=srv3` | 200, 0 B |
| `+ Referer: watch?v=…` | 200, 0 B |
| `+ Cookie: CONSENT=YES+cb` | 200, 0 B |
| `&xorp=true&fmt=json3` | 200, 0 B |
| `GET /api/timedtext?v=…&lang=en` | 200, 0 B |

InnerTube `POST /youtubei/v1/player` with the public web key:

| Client | result |
| --- | --- |
| `ANDROID` 19.09.37 | HTTP 400 |
| `IOS` 19.09.3 | HTTP 400 |
| `WEB` 2.20240304 | 200, `playabilityStatus: UNPLAYABLE`, 0 caption tracks |
| `TVHTML5_SIMPLY_EMBEDDED_PLAYER` | 200, `ERROR`, 0 caption tracks |

This is a token/IP gate, not a dead surface — competing Store Actors record
hundreds of thousands of successful runs per month against it. The untested
route, in cost order: a residential exit IP, then
`youtubei/v1/get_transcript` with `params` harvested from the page, then a
BotGuard `pot` token.

Until one of those is verified, this Actor reports `captionLanguages` and stops
there rather than shipping a field that is empty most of the time.

## Live chat and community posts

Both were probed for adjacent Actors on the same day:

- `live_chat_replay?v=<id>` returns **HTTP 400** for every video tested,
  including ones with `isLiveContent: true`, and the watch page carries no
  `live_chat_replay` reference at all.
- `/@handle/community` answers *"This Community isn't available"*. The working
  path is `/@handle/posts`, which yields 10 `backstagePostRenderer` entries per
  page with poll, image and vote data.

Neither belongs in this Actor; the second is covered by
`youtube-community-posts-scraper`.

## Not to be confused with

`youtube-sponsor-detector` (same portfolio) marks **sponsor segments inside the
video timeline** — where the ad read starts and ends. This Actor reads the
**description** and identifies **who is paying and with what offer**. Different
surface, different question, no overlap in output.
