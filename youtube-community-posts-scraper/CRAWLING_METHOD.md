# Crawling method — YouTube Community Post & Poll Scraper

All figures measured 2026-09-20 from a single residential IP, `curl_cffi` with
TLS impersonation, no login and no cookies.

## The wrong path, and how convincingly it fails

`GET /@handle/community` returns **HTTP 200 with a 761 KB page** — full
navigation, full topbar, valid `ytInitialData` — containing:

```
"This Community isn't available"
"Visit this creator's channel to see their content."
```

Zero `backstagePostRenderer`, zero `pollRenderer`, zero `contentText`. Measured
on `@MrBeast` and `@veritasium`, both of which post regularly, and retried with
three cookie variants:

| Cookie | Page | posts | polls |
| --- | --- | --- | --- |
| none | 761 KB | 0 | 0 |
| `CONSENT=YES+cb` | 764 KB | 0 | 0 |
| `SOCS=CAI` | 764 KB | 0 | 0 |
| `CONSENT` + full `SOCS` | 760 KB | 0 | 0 |

A scraper pointed at this path reports every channel on YouTube as having no
community posts, with a 200 and a megabyte of HTML to back it up.

## The working path

`GET /@handle/posts`:

| Handle | Page | `backstagePostRenderer` | `pollRenderer` | `continuationItemRenderer` |
| --- | --- | --- | --- | --- |
| `@MrBeast` | 960–965 KB | **10** | 2 | 3 |
| `@veritasium` | 934 KB | **10** | 1 | 3 |
| `@mkbhd` | — | **8** | 0 | — |

## Post structure

Keys on `backstagePostRenderer`, measured:

```
actionButtons, authorEndpoint, authorText, authorThumbnail, backstageAttachment,
collapseButton, contentText, expandButton, loggingDirectives, postId,
publishedTimeText, surface, trackingParams, voteCount, voteStatus
```

Parsing is **structural** — each field read by key from the renderer object —
rather than by text scanning. Posts are heterogeneous (text only, four images,
a poll, a video), and a text scanner attaches the wrong media to the wrong post
while producing perfectly plausible-looking rows.

| Field | Path | Measured example |
| --- | --- | --- |
| Text | `contentText.runs[].text` | 956-byte post on `@veritasium` |
| Likes | `voteCount.simpleText` | `"1.9M"`, accessibility `"1.9M likes"` |
| Published | `publishedTimeText.runs[].text` | `"5 months ago (edited)"` |
| Channel ID | `authorEndpoint.browseEndpoint.browseId` | `UCX6OQ3DkcsbYNE6H8uQQuVA` |
| Images | `backstageAttachment.postMultiImageRenderer.images[]` | 10 images, up to 5464×5464 |
| Video | `backstageAttachment.videoRenderer` | `cMx139eTxoc` |
| Poll | `backstageAttachment.pollRenderer` | `POLL_TYPE_TEXT`, `"1.7M votes"` |

## Links are wrapped

Every outbound URL inside `contentText` is rewritten:

```
https://www.youtube.com/redirect?event=backstage_event&redir_token=QUZZ…&q=https%3A%2F%2Fwww.themostdangerousgames.com%2F
```

The extractor reads the `q` parameter and URL-decodes it, so a record carries
`https://www.themostdangerousgames.com/`. Storing the wrapper would be useless:
`redir_token` is session-bound and the raw string tells a user nothing.

## What the surface genuinely does not hold

**Exact like counts.** `voteCount` is
`{"simpleText": "1.9M", "accessibility": {"accessibilityData": {"label": "1.9M likes"}}}`.
Both forms are abbreviated. No exact integer exists anywhere in the logged-out
payload, so `likeCountIsApprox` is hardcoded `true` rather than implied.

**Poll splits.** A `pollRenderer` logged out has exactly these keys:

```
accessibilityData, choices, totalVotes, trackingParams, type
```

and each entry in `choices` has exactly `{text, signinEndpoint}`. The
`signinEndpoint` sits where the percentage would be — YouTube reveals the
breakdown only to a signed-in account that has voted. `votesPerChoice` is
returned as `null` with a note, not as an invented number.

**Comment threads.** `commentsHeaderRenderer` appears once per page but the
threads themselves need a separate InnerTube continuation call. Out of scope.

## Pagination

Three `continuationItemRenderer` entries per page. Following them needs the
InnerTube `browse` endpoint with the token plus `INNERTUBE_API_KEY`. Not
implemented — 10 posts is one page, and the InnerTube family of endpoints is the
same one that answers `UNPLAYABLE` for captions on this source, so it is not
assumed to work until measured. `parse_continuation` already extracts the token
for whoever picks this up next.

## Adjacent surfaces, for the record

- **Transcripts** — `captionTracks` lists languages, but each signed caption URL
  answers 200 with a **zero-byte body**; InnerTube `/player` answers 400
  (ANDROID/IOS) or `UNPLAYABLE` (WEB). Closed.
- **Live chat / Superchat** — `live_chat_replay?v=<id>` answers **HTTP 400** for
  every video tested, including `isLiveContent: true` ones, and the watch page
  carries no `live_chat_replay` reference. Closed.
