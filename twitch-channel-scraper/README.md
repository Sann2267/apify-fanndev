# Twitch Channel Scraper

Extract Twitch channel profiles, live stream status, VODs, clips, and stream schedules — no account, login, or API key needed.

## Why use this actor

- One actor covers a channel's full public footprint: profile + live status, past broadcasts (VODs), top/trending clips, and upcoming schedule
- No Twitch account, OAuth app, or API key required — works exactly like an anonymous visit to twitch.tv
- Structured, stable JSON output suitable for pipelines, spreadsheets, or dashboards
- Automatic retries on temporary network hiccups
- Honest about limits: if a channel has more videos/clips than fit in one page, every row is flagged so you know more exist (see Known limits below) — nothing is silently dropped

## How it works

Pick a `mode` and one or more channel logins:
1. **`channel`** — profile info (bio, followers, creation date) plus live status (is it live right now, viewer count, current game, stream title).
2. **`videos`** — the channel's past broadcasts, highlights, or uploads.
3. **`clips`** — the channel's top or trending community-made clips.
4. **`schedule`** — upcoming scheduled streams.

## Input

**Channel profile + live status** (default mode):
```json
{
  "mode": "channel",
  "logins": ["shroud", "xqc"],
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Videos:**
```json
{
  "mode": "videos",
  "login": "shroud",
  "limit": 20,
  "videoType": "ARCHIVE",
  "videoSort": "TIME"
}
```

**Clips:**
```json
{
  "mode": "clips",
  "login": "shroud",
  "limit": 20,
  "clipsPeriod": "ALL_TIME",
  "clipsSort": "VIEWS_DESC"
}
```

**Schedule:**
```json
{
  "mode": "schedule",
  "login": "shroud"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"channel"` (default), `"videos"`, `"clips"`, or `"schedule"`. |
| `login` | string | A single channel login (the part after `twitch.tv/` in the URL). |
| `logins` | array | Multiple channel logins to process in one run. |
| `limit` | integer | Max videos/clips returned per channel. Default 20, max 100 — see Known limits. |
| `videoType` | string | `videos` mode: `ARCHIVE` (past broadcasts, default), `HIGHLIGHT`, `UPLOAD`, `PAST_PREMIERE`, `PREMIERE_UPLOAD`. |
| `videoSort` | string | `videos` mode: `TIME` (newest first, default) or `VIEWS` (most viewed first). |
| `clipsPeriod` | string | `clips` mode: `LAST_DAY`, `LAST_WEEK`, `LAST_MONTH`, or `ALL_TIME` (default). |
| `clipsSort` | string | `clips` mode: `VIEWS_DESC` (default) or `TRENDING`. |
| `maxConcurrency` | integer | How many channels to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (not required for this endpoint, kept for production robustness). |

## Output

**Channel mode** — one record per login:
```json
{
  "_input": "xqc",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T18:43:19Z",
  "id": "71092938",
  "login": "xqc",
  "displayName": "xQc",
  "description": "THE BEST AT ABSOLUTELY EVERYTHING...",
  "createdAt": "2014-09-12T23:50:05.989719Z",
  "profileImageURL": "https://static-cdn.jtvnw.net/jtv_user_pictures/xqc-profile_image-...-300x300.jpeg",
  "bannerImageURL": "https://static-cdn.jtvnw.net/jtv_user_pictures/....jpeg",
  "primaryColorHex": "FFBF00",
  "followersCount": 12537124,
  "isLive": true,
  "streamId": "319959993950",
  "streamTitle": "...",
  "streamType": "live",
  "viewersCount": 26109,
  "streamStartedAt": "2026-08-25T17:34:35Z",
  "gameName": "Special Events",
  "gameBoxArtURL": "https://static-cdn.jtvnw.net/ttv-boxart/509663-{width}x{height}.jpg",
  "tags": null,
  "lastBroadcastStartedAt": "2026-08-25T17:34:40.483789Z",
  "lastBroadcastTitle": "..."
}
```

**Videos mode** — one record per VOD:
```json
{
  "_input": "shroud",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T18:43:02Z",
  "channelLogin": "shroud",
  "channelTotalVideoCount": 1551,
  "_truncatedToFirstPage": true,
  "videoId": "2854436054",
  "title": "stream stops when my bank account hits 0$",
  "publishedAt": "2026-08-23T17:44:06Z",
  "viewCount": 489694,
  "lengthSeconds": 29261,
  "previewThumbnailURL": "https://static-cdn.jtvnw.net/.../thumb0-{width}x{height}.jpg",
  "gameName": "WARDOGS",
  "url": "https://www.twitch.tv/videos/2854436054"
}
```

**Clips mode** — one record per clip:
```json
{
  "_input": "shroud",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T18:43:03Z",
  "channelLogin": "shroud",
  "_truncatedToFirstPage": true,
  "clipId": "2358589597",
  "slug": "TangentialBillowingJalapenoYee-ccA2oB1pEYh4CHWJ",
  "title": "F Shroud",
  "viewCount": 562406,
  "createdAt": "2023-06-02T11:41:50Z",
  "durationSeconds": 28,
  "url": "https://www.twitch.tv/shroud/clip/TangentialBillowingJalapenoYee-ccA2oB1pEYh4CHWJ",
  "thumbnailURL": "https://static-cdn.jtvnw.net/.../thumb-0000000000-1920x1080.jpg",
  "curatorLogin": "pato_bolado"
}
```

**Schedule mode** — one record per upcoming stream segment:
```json
{
  "_input": "shroud",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T18:43:04Z",
  "channelLogin": "shroud",
  "segmentId": "eyJzZWdtZW50SUQi...",
  "title": null,
  "startAt": "2026-08-27T18:00:00Z",
  "endAt": "2026-08-28T02:00:00Z",
  "isCancelled": false,
  "hasReminder": false,
  "categories": null,
  "isNextSegment": true
}
```

A record with `_error` instead of the fields above means that channel could not be processed (for example, `"_error": "channel_not_found"` for a username that doesn't exist).

## Known limits

- **Deep pagination is not available.** Twitch enforces a device-integrity check for any page beyond the first, which an HTTP-only client cannot satisfy. `videos`/`clips` modes return at most 100 items — the most recent (or most-viewed, depending on sort) — never the full archive on channels with more than 100. Every row is flagged with `_truncatedToFirstPage: true` when more exist, so this is never silent.
- Chat messages, follower/following lists, and raw stream video (HLS) are out of scope — this actor covers public channel metadata only.
- `schedule` mode returns the near-term window Twitch itself exposes (roughly 1–2 weeks out), not an arbitrarily long future schedule.
