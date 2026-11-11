# TikTok Scraper: Videos, Profiles, Hashtags, Sounds

Scrape public TikTok data without a login, an account, or an API key. Five modes
in one actor, all HTTP-only — no browser, no request signing, no cookies.

| Mode | Give it | You get back |
|---|---|---|
| **video** | video url, short link, or numeric id | views, likes, comments, shares, caption, upload time, cover, sound — **plus the uploader's follower / likes / video counts** |
| **profile** | username, `@handle`, or profile url | followers, following, total likes, bio, verified, private flag, avatar |
| **hashtag** | `fyp` or `#fyp` | the videos TikTok shows on that tag's page, plus the tag's total video count |
| **music** | sound url or sound id | the videos using that sound, plus the sound's artist and total video count |
| **oembed** | full video url | TikTok's official lightweight record: title, author, thumbnail |

## Quick start

```json
{
  "mode": "video",
  "targets": [
    "https://www.tiktok.com/@complex/video/7626254334065511711",
    "https://vm.tiktok.com/ZGdxxxxxx/",
    "7626254334065511711"
  ],
  "proxyConfiguration": { "useApifyProxy": true }
}
```

Every entry form above works in `video` mode. Short links cost one extra request
to resolve; bare ids cost none.

## Sample output — `video` mode

```json
{
  "_mode": "video",
  "_source": "embed-frontity-state",
  "videoId": "7626254334065511711",
  "description": "can't even lie this is fire 🔥 [🎥: @nasa ]",
  "createTimeIso": "2026-04-08T05:21:59Z",
  "playCount": 11000,
  "diggCount": 427,
  "commentCount": 10,
  "shareCount": 14,
  "authorUniqueId": "complex",
  "authorNickname": "COMPLEX",
  "authorVerified": true,
  "authorFollowerCount": 6300000,
  "authorHeartCount": 394000000,
  "authorVideoCount": 11800,
  "musicId": "7301919715965077506",
  "musicName": "euphoria",
  "musicAuthorName": "inertia. & Aurenth",
  "locationCreated": "US",
  "isAd": false,
  "videoUrl": "https://www.tiktok.com/@complex/video/7626254334065511711"
}
```

The author block is the part worth noticing: **a list of video urls doubles as a
creator dataset**, because TikTok ships the uploader's account stats inside the
video payload. No second request per account.

## Sample output — `music` mode

```json
{
  "_mode": "music",
  "playlistType": "music",
  "entityId": "7301919715965077506",
  "musicArtist": "Aurenth",
  "entityVideoCount": 91900,
  "videoId": "7584740654534642957",
  "playCount": 10200000,
  "authorUniqueId": "coastenitaa",
  "videoUrl": "https://www.tiktok.com/@coastenitaa/video/7584740654534642957",
  "_warning": "single_page_surface_embed_playlist_is_not_paginable;playlist_rows_carry_play_count_only_no_digg_or_comment_counts"
}
```

## What this actor does **not** do, and why

This is the honest part, and it is short on purpose. TikTok's consumer web pages
are behind a WAF that answers with a 1.4 KB stub, and its internal JSON APIs
require a request signature minted by TikTok's own obfuscated JavaScript. This
actor uses only the embed and oEmbed surfaces, which are published for third-party
use. That buys reliability and a tiny cost per row, and it costs the following:

* **No comments.** `/api/comment/list/` is signature-gated. You get the comment
  *count*, not the comments.
* **No search, no trending, no For You.** Same gate.
* **No "all videos by this user".** Listing an account's posts needs the signed
  `/api/post/item_list/`. `profile` mode returns account stats; to collect a
  creator's videos you need their video urls or ids.
* **Hashtag and sound listings are one page** — about 6 and 9 videos. The embed's
  own loader is the signature-gated endpoint, so `maxItemsPerTarget` cannot
  produce more. `entityVideoCount` tells you how many exist in total so you can
  see the gap rather than guess at it.
* **No Top Ads / Creative Center.** Those APIs answer
  `{"code":40101,"msg":"no permission"}` to anonymous callers.
* **Counters are rounded by TikTok**, not by this actor: `playCount` arrives as
  `11000`, not `11043`. `videoWidth`/`videoHeight`/`videoDuration` are often
  `null` outright -- TikTok omits the `videoMeta` block on many videos and ships
  the placeholder `99` on some of the rest.

Full measurements behind each of these are in
[CRAWLING_METHOD.md](CRAWLING_METHOD.md).

## Reading the output

Every row carries a small envelope so a mixed dataset stays readable:

* `_mode` — which surface produced the row.
* `_input` — the target as resolved from your entry.
* `_source` — `embed-frontity-state` or `oembed-api`.
* `_index` — position within a hashtag/music listing.
* `_warning` — a **ceiling**, not a failure (single-page listing, thin listing
  rows, rounded play counts, profile without a video list).
* `_error` + `_errorDetail` — `INVALID_INPUT`, `NOT_FOUND`, `PRIVATE_ACCOUNT`,
  `EMPTY_RESULT`, `BLOCKED_AFTER_RETRIES`, `UPSTREAM_SHAPE_CHANGED`.

**Every input produces at least one row.** A username that no longer exists
becomes a `NOT_FOUND` row, not a silent omission — so you can always reconcile
your input list against the dataset line for line.

## Proxies and pacing

TikTok throttles embed requests **per IP** and answers with `HTTP 503` after a
handful of calls. The actor handles this by rotating the TLS fingerprint *and* the
proxy session, then backing off (2s → 4s → 8s) across four attempts.

Rotating the fingerprint alone does not lift the throttle, so:

* **More than a few targets: use a proxy.** `{"useApifyProxy": true}` is the
  default; residential helps most.
* **`delaySeconds` defaults to 2.** Lower it only behind rotating residential
  proxies.
* A run that hits `BLOCKED_AFTER_RETRIES` on every target ends as a **failed**
  run rather than an empty success, so a throttled run never looks like "this
  target has no data".

## Tips

* **Engagement benchmarking:** run `hashtag` or `music` to discover video ids,
  then feed those ids into `video` mode for the full counter set.
* **Creator lists:** one `video` call per creator's recent post gives you their
  follower count, total likes and post count in the same row.
* **Bulk url validation:** `oembed` mode is 1.3 KB per target against 302 KB for
  the embed page — use it to check which of thousands of urls are still live
  before spending on the heavier mode.
* **Sound trend tracking:** `entityVideoCount` on a sound is the total number of
  videos using it. Re-run on a schedule and diff that number.

## Local development

```bash
pip install -r requirements.txt
python test_local.py            # all five modes against live TikTok
python test_local.py video      # one mode
```

The test asserts that required fields per mode are **non-null** — a mode that
returns a row full of nulls fails rather than passing on row count alone.
