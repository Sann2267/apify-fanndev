# Social Blade Creator Analytics Scraper

Extract creator statistics from **Social Blade** for YouTube, TikTok, Twitch and Instagram — audience size, ranks, and 15 days of daily history. No account, login, or API key needed.

## Why use this actor

- **Four platforms, one output shape** — YouTube, TikTok, Twitch and Instagram creators through the same input
- **Daily history, not just a snapshot** — up to 15 days of subscriber/follower, view, like and video counts per creator, so you can chart growth without waiting to accumulate it yourself
- **Every Social Blade rank** — overall rank plus per-metric ranks (subscribers, views, country, category on YouTube; followers, likes, videos on TikTok; engagement rate on Instagram)
- **Creator context** — account creation date, country, content category, channel description, and the creator's links to their other platforms
- **YouTube leaderboard** in one call — the top creators with subscribers, views and country
- **Exact-address handling** — a Social Blade address is fetched exactly as given, because `/user/x`, `/c/x` and `/@x` are *different* YouTube channels; guessing between them silently returns the wrong creator
- Stable JSON output with automatic retries — no scrapers or browsers to babysit

## How it works

Pick a `mode`:

1. **`profile`** — statistics, ranks and daily history for one or more handles on the platform you choose (or full Social Blade addresses, which carry their own platform).
2. **`top`** — the YouTube top-creator leaderboard.

## Input

**One creator:**

```json
{
  "mode": "profile",
  "platform": "youtube",
  "handle": "pewdiepie",
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**A batch across platforms** (addresses override the default platform):

```json
{
  "mode": "profile",
  "platform": "tiktok",
  "handles": [
    "charlidamelio",
    "https://socialblade.com/youtube/@MrBeast",
    "https://socialblade.com/twitch/user/ninja"
  ],
  "maxConcurrency": 4
}
```

**Leaderboard:**

```json
{ "mode": "top", "topSize": 100, "maxItems": 100 }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `profile` or `top`. |
| `platform` | string | `youtube`, `tiktok`, `twitch`, or `instagram`. |
| `handle` / `handles` | string / array | Creator handle(s) or full Social Blade addresses. |
| `topSize` | integer | `top` mode: `100` or `500` (both return 100 rows). |
| `maxItems` | integer | `top` mode: rows to keep (max 100). |
| `maxConcurrency` | integer | Creators fetched in parallel (default 4). |
| `proxyConfiguration` | object | Apify Proxy settings; Residential on by default. |

## Output

**`profile` mode, YouTube** — real output, arrays truncated:

```json
{
  "_input": "pewdiepie",
  "_source": "S1-ssr",
  "_scrapedAt": "2026-09-08T07:10:00Z",
  "recordType": "CREATOR_PROFILE",
  "platform": "youtube",
  "id": "UC-lHJZR3Gqxm24_Vd_AJ5Yw",
  "displayName": "PewDiePie",
  "createdAt": "2010-04-29T00:00:00.000Z",
  "country": "JP",
  "channelType": "entertainment",
  "subscribers": 109000000,
  "views": "29519305767",
  "videos": 4665,
  "ranks": { "sb": 124024, "subscribers": 16, "views": 179, "country": 1, "category": 7 },
  "socials": [{ "url": "https://instagram.com/pewdiepie", "title": "IG" }, "… 2 more"],
  "history": [
    { "date": "2026-08-25T00:00:00.000Z", "subscribers": 110000000, "views": 29514832850, "videos": 4665 },
    "… 14 more"
  ],
  "historyDays": 15
}
```

**`profile` mode, TikTok** — the metric set follows the platform:

```json
{
  "platform": "tiktok",
  "displayName": "charli d’amelio",
  "videos": 3242,
  "ranks": { "sb": 9965, "followers": 2, "likes": 2, "videos": 7206 },
  "history": [{ "date": "2026-08-25T00:00:00.000Z", "followers": 159200000, "following": 1439, "likes": 12300000000, "videos": 3229 }],
  "historyDays": 15
}
```

**`top` mode:**

```json
{ "recordType": "TOP_CREATOR", "listRank": 1, "displayName": "MrBeast", "subscribers": 516000000, "country": "US" }
```

| Field | Type | Description |
|---|---|---|
| `recordType` | string | `CREATOR_PROFILE` or `TOP_CREATOR`. |
| `platform` | string | Which platform the record is from. |
| `id` / `displayName` | string | Native platform ID and creator name. |
| `createdAt` / `country` / `channelType` | string | Account age, country, content category. |
| `subscribers` / `views` / `videos` | integer / string | Audience and output counts (present per platform). |
| `ranks` | object | Overall Social Blade rank plus per-metric ranks. |
| `socials` | array | The creator's links to other platforms. |
| `history` / `historyDays` | array / integer | Up to 15 daily rows. |
| `listRank` | integer | `top` mode position. |
| `_error` / `_errorDetail` | string | Present only when a creator could not be fetched. |

## Notes & limits

- **Metrics differ by platform, deliberately.** YouTube gives subscribers/views/videos, TikTok gives followers/likes/videos, Twitch gives followers, Instagram gives followers and engagement rate. Fields are passed through as published rather than forced into one shape.
- **Instagram profiles carry no daily history** in the public page — the account record comes through, `history` is empty.
- **Facebook is not supported**: those profile addresses return 404 upstream, so it is left out rather than shipped as a mode that always fails.
- **Audience counts are rounded** by the source (109,000,000 rather than an exact figure); the daily history rows are the finer-grained series.
- **The leaderboard returns 100 rows per run.** `topSize: 500` is accepted upstream but still serves 100 creators per request.
- Counts are point-in-time; schedule the actor if you want a longer series than the 15 days each run carries.
