# Instagram Public Content Scraper

Scrape public Instagram data without a login and without a browser: **account
profiles**, the **profile grid**, the **reels tab with play counts**, **single
posts with engagement and comments**, and **location pages** with the media
posted there.

Pure HTTP. No Playwright, no Selenium, no cookies to supply, no account.

---

## Modes

Pick a `mode`, then give `targets` that match it.

| Mode | Targets | One row per | Paginates |
| --- | --- | --- | --- |
| `profile` | usernames or profile URLs | account | — |
| `posts` | usernames or profile URLs | post | ✅ unlimited |
| `reels` | usernames or profile URLs | reel | ✅ unlimited |
| `post_detail` | post/reel URLs or shortcodes | post | comments capped (below) |
| `location` | location ids or `/explore/locations/` URLs | media | ❌ one page |

```json
{
  "mode": "reels",
  "targets": ["nasa", "https://www.instagram.com/natgeo/"],
  "maxItemsPerTarget": 60,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

---

## Read this before you pick a mode: the surfaces publish different fields

Instagram serves the same post with different fields depending on which page it
came from. This is the most important thing to know about the output:

| | `posts` | `reels` | `post_detail` | `location` |
| --- | --- | --- | --- | --- |
| Likes / comments | ❌ | ✅ | ✅ | ✅ |
| **Play count** | ❌ | ✅ | ❌ | ❌ |
| Caption, hashtags | ✅ | ❌ | ✅ | ✅ |
| Publish date | ❌ | ❌ | ✅ | ✅ |
| Video file URL | ❌ | ❌ | ✅ | ✅ |
| Comments | ❌ | ❌ | ✅ | ❌ |

**A field this actor could not get is `null`, never `0`.** A zero would silently
wreck any average you compute. Rows affected by a surface limit also carry a
`_warning` naming it and pointing at the mode that does publish the field.

The usual pattern: run `posts` or `reels` to enumerate an account cheaply, then
feed the shortcodes you care about into `post_detail` for full engagement,
timestamps and comments.

---

## What it cannot do

Stated plainly, because these are platform limits, not bugs, and no setting
works around them:

- **Hashtag scraping.** `/explore/tags/<tag>/` serves a sign-in page to
  logged-out visitors.
- **Search.** Both the search page and the search API require a login.
- **Tagged-posts tab**, followers/following lists, stories, and the contents of
  story highlights — all login-walled. (Highlight *titles and covers* do come
  through in `profile`.)
- **Deep comments.** Instagram ships only the first ~13–15 comments to a
  logged-out viewer, whatever the post's real total. Its comment pagination
  endpoint requires a login. `commentCount` is the true total; `commentsScraped`
  is how many you actually got.
- **Location pagination.** A location page serves one batch — about 63 media on
  the `recent` tab, 27 on `ranked` — and ignores any cursor. That is the whole
  harvest for a place, however large `maxItemsPerTarget` is.
- **Private accounts.** Profile metadata is public; media is not. You get a
  `profile` row, and a `PRIVATE_ACCOUNT` diagnostic row from the media modes.

Also: Instagram Shop / product-catalog data does not exist on any public
surface any more, so no mode here returns it. Note that `productType` values
(`feed`, `clips`, `igtv`) are **media formats, not shopping products** — an
easy field to misread.

---

## Output

Every row carries the same envelope, so a mixed dataset stays queryable:

| Field | Meaning |
| --- | --- |
| `_mode` | which surface produced the row |
| `_input` | the target it belongs to |
| `_source` | `ssr-relay-island` (page 1, from the page itself) or `api-graphql-replay` (a paginated request) |
| `_page` | which page of the connection |
| `_scrapedAt` | UTC ISO 8601 |
| `_warning` | a surface limit affecting this row |
| `_error` / `_errorDetail` | set only on failure rows |

**Every input produces at least one row.** A target that fails yields a
diagnostic row rather than vanishing, so downstream joins stay idempotent:
`INVALID_INPUT`, `NOT_FOUND`, `PRIVATE_ACCOUNT`, `GATED_FOR_LOGGED_OUT`,
`BLOCKED_AFTER_RETRIES`, `EMPTY_RESULT`, `UPSTREAM_SHAPE_CHANGED`.

A `reels` row:

```json
{
  "_mode": "reels", "_input": "nasa", "_source": "ssr-relay-island", "_page": 1,
  "shortcode": "DdEsW1ItqpI",
  "url": "https://www.instagram.com/p/DdEsW1ItqpI/",
  "mediaType": "VIDEO", "productType": "clips",
  "likeCount": 94368, "commentCount": 1039, "playCount": 3992126,
  "imageUrl": "https://scontent.cdninstagram.com/...",
  "ownerUsername": "nasa", "ownerId": "4092263381",
  "_warning": "caption_and_timestamp_not_published_on_this_surface: ..."
}
```

Instagram CDN URLs (`imageUrl`, `videoUrl`, `profilePicUrl`) are **signed and
expire** — download anything you need to keep, promptly.

---

## How it works, and why it keeps working

Instagram's public REST API (`/api/v1/...`) returns **HTTP 401
`require_login`** to anonymous callers as of September 2026 — identically
across five TLS fingerprints, so it is an auth rollout rather than a bot
defence. This actor does not use it.

Instead it reads the **logged-out server-rendered Relay payload**: warm the
entity page, harvest the query id Instagram ships inline next to the data, and
replay it against `/api/graphql/` for pagination.

Because the query id is read from the page being scraped rather than pinned in
the source, **the usual persisted-query rot does not apply** — when Meta
rotates its ids, the next request picks up the new one automatically.

Full evidence, the measurements behind every limit above, and the traps worth
knowing (`/graphql/query` returns `200 OK` with null data; `"404"` appears in
healthy pages) are in [CRAWLING_METHOD.md](CRAWLING_METHOD.md).

---

## Proxy and pacing

Instagram throttles anonymous traffic **per IP** and signals it with a 200
carrying a login wall rather than a 429. **Residential proxy is strongly
recommended.** Without one, expect a handful of targets to succeed and then
login walls; datacenter ranges are throttled sooner. On a block the actor
rotates both the TLS profile and the proxy session, then retries with
exponential backoff.

`delaySeconds` (default 2) paces targets. Lower it only behind rotating
residential proxy — pacing keeps a run alive considerably longer than
hammering does.

---

## Legal

Scrapes only data Instagram serves to a logged-out visitor. No login, no
credential use, no access to private accounts or restricted content. You are
responsible for how you use the output, including under the GDPR/CCPA where
personal data is involved.
