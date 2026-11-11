# Crawling method — YouTube Shorts Viral Trend Tracker

All figures measured 2026-09-20 from a single residential IP, `curl_cffi` with
TLS impersonation, no login and no cookies.

## S1 — the hashtag grid

`GET https://www.youtube.com/hashtag/<tag>/shorts`

Nine fetches — three each on `chrome124`, `chrome120`, `safari17_0`:

| Metric | Every fetch |
| --- | --- |
| Page size | 840–848 KB |
| `shortsLockupViewModel` | 37 |
| `accessibilityText` entries containing a view figure | 36 |
| Continuation tokens | 1 |

No variance at all, which is unusual for YouTube and worth relying on.

What it carries per entry: title and a **rounded** view figure, both inside one
accessibility string:

```
"Frog Eggs Time Challenge! ⏱️🐸🧪, 3.3 million views - play Short"
```

No likes, no duration, no channel, no sound. A tracker built on this surface
alone can only bucket by "3.3 million" and can never compute engagement.

Video IDs are read from the raw text starting at the `ytInitialData` assignment.
The Nth ID pairs with the Nth accessibility entry, which is what preserves rank.

## S2 — the Short's own page

`GET https://www.youtube.com/shorts/<id>`, 1.4 MB.

| Field | Pattern | Measured |
| --- | --- | --- |
| Exact views | `"viewCount":"3397251"` | 3,397,251 (grid said "3.3 million") |
| Likes | `accessibilityText` "like this video along with **36 thousand** other people" | rounded |
| Sound | `soundAttributionTitle` → `content` | "Original Sound", "Never Ending Nerf" |
| Duration | `"lengthSeconds":"52"` | 52 |
| Hashtags | `"shortDescription"` | `#Mukbang #buldakchallenge …` |

`GET https://www.youtube.com/watch?v=<id>` for the same video returns the same
exact `viewCount` but the like string is **exact**: "like this video along with
**36,212** other people". So the URL you choose decides the like precision.
Measured pairs:

| Video | `/shorts/` likes | `/watch` likes |
| --- | --- | --- |
| `FX4RT1cp7Rs` | 36,000 | **36,218** |
| `M3dWcoxohPs` | 18,000 | **18,623** |

The watch page carries no sound attribution, hence the optional second request.

## Three traps, all of which produced wrong output first

**1. `likeCountEntity` is a decoy.** The obvious field reads
`"likeCountEntity":{"key":"unset_like_count_entity_key"}` on every Short
measured — a placeholder that is never filled server-side. The real number
exists only in the accessibility string.

**2. The payload is hex-escaped.** On `/shorts/` pages the sound data appears as
`\x22soundAttributionTitle\x22:\x7b\x22content\x22:\x22Original Sound\x22`.
A scan for the plain key finds nothing and concludes the field does not exist.
`extractor.unescape_hex` decodes `\xNN` before matching.

**3. Anchoring at `ytInitialData` drops the engagement data here.** That anchor
is correct for a channel grid, where IDs from earlier prefetch scripts would
otherwise leak in. On a `/shorts/` page the assignment sits at roughly byte
1,342,000 while the like button is at 900,000 — anchoring silently removed the
likes. `parse_short_detail` therefore scans the whole document and
`parse_hashtag_grid` anchors; they are deliberately asymmetric.

**Multiple like buttons.** A Shorts page renders a like button for each clip in
the carousel. `parse_short_detail` matches them all and keeps the last one whose
value does not exceed this video's view count, since likes never exceed views
and the neighbours are unrelated videos.

## Pagination

The grid returns one continuation token. Following it requires the InnerTube
`browse` endpoint with the token plus `INNERTUBE_API_KEY` from the page. Not
implemented: 36 ranked Shorts is the useful part of a hashtag trend, and the
InnerTube path is the same family of endpoint that answers `UNPLAYABLE` for
captions on this source, so it is not assumed to work until measured.

## Adjacent surfaces, for the record

Probed the same day while scoping sibling Actors:

- **Transcripts** — `captionTracks` lists languages, but every signed caption
  URL answers 200 with a **zero-byte body**, and InnerTube `/player` answers 400
  (ANDROID/IOS) or `UNPLAYABLE` (WEB). Closed.
- **Live chat** — `live_chat_replay?v=<id>` answers **HTTP 400** for every video
  tested, including `isLiveContent: true` ones. Closed.
- **Community posts** — `/@handle/community` says *"This Community isn't
  available"*; `/@handle/posts` works and yields 10 posts per page. Covered by
  `youtube-community-posts-scraper`.

## Not to be confused with

`youtube-shorts-scraper` (same portfolio) lists the Shorts **of a given
channel**. This Actor ranks Shorts **across a hashtag** and adds the engagement
ratio and sound. Different entry point, different question.
