# Haystack News Scraper

Extract video news headlines, channel directories, news polls and local events from **Haystack News (haystack.tv)** — the free streaming service carrying 400+ local and world news channels.

## Why use this actor

- **No account, no login, no API key.** Everything it returns is public.
- **400+ real newsrooms in one feed** — ABC7 Los Angeles, KHOU Houston, Bloomberg, Al Jazeera, NBC News and hundreds of local US stations, all normalised into one schema.
- **Video metadata you cannot get from an RSS feed** — captions (WebVTT), thumbnails at three sizes, duration, publish time, topic tags and a popularity score.
- **AI content classification.** The detail mode returns Haystack's own per-story classification: category, content type, urgency, editorial stance, emotional intensity, broad appeal and headline magnetism — plus view counts and viewer drop-off.
- **Eight modes in one actor**, from a single-city local news feed to the complete 483-channel directory.
- **Stable JSON output** ready for a database, spreadsheet or analysis pipeline. Every row carries the same `_input` / `_source` / `_scrapedAt` / `recordType` envelope, so mixed runs split cleanly into tables.
- **Automatic retries** and honest error rows — a bad input produces a labelled error record instead of silently disappearing.

## How it works

1. Pick a **mode** and fill in the matching input list (some modes need no input at all).
2. The actor collects the data straight from Haystack's own service, retrying automatically if the service is briefly slow.
3. Every item is written to your dataset as a flat JSON row, tagged with which input produced it.
4. Download as JSON, CSV or Excel, or run it on a schedule to track headlines over time.

You do not need to manage scrapers, browsers, accounts or blocks.

## Modes

| Mode | Reads | Returns |
|---|---|---|
| `videos` | Feed targets | Video headlines from a category, channel, topic or city |
| `video-detail` | Video URLs | One video with full metadata, AI classification and view analytics |
| `search` | Search queries | Videos matching a keyword |
| `discover` | Search queries | Channels, cities and topics matching a keyword |
| `channels` | *(nothing)* | The complete channel directory (483 channels) |
| `taxonomy` | *(nothing)* | Categories, live channels, special collections and 299 cities |
| `polls` | *(nothing)* | Every news poll with live vote counts |
| `local-events` | Locations | Concerts, sports and community events in a city |

## Input

### Videos — headlines from a category, channel, topic or city

```json
{
  "mode": "videos",
  "targets": ["news", "channel/abc7", "tag/trump", "location/houston-tx"],
  "maxItemsPerTarget": 50,
  "includeTagGroups": false,
  "maxConcurrency": 4
}
```

Targets accept a full `https://www.haystack.tv/...` URL or a short identifier, mixed freely:

| Target | Meaning |
|---|---|
| `news`, `sports`, `business`, `live`, `weather` | A category feed |
| `channel/abc7` | Everything from one channel |
| `tag/trump` | Everything on one topic |
| `location/houston-tx` | Local news for one city |

### Other modes

```json
{ "mode": "video-detail", "videoUrls": ["https://www.haystack.tv/v/trump-love-unified-ireland-6daOFLevf"] }
{ "mode": "search",       "queries": ["ukraine", "federal reserve"] }
{ "mode": "discover",     "queries": ["houston"] }
{ "mode": "channels" }
{ "mode": "taxonomy" }
{ "mode": "polls" }
{ "mode": "local-events", "locations": ["houston-tx", "san-francisco-ca"], "deepLocalEvents": true }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | Which of the eight modes to run. Default `videos`. |
| `targets` | array | `videos` mode — categories, channels, topics or cities. |
| `videoUrls` | array | `video-detail` mode — video page URLs, or the bare slug or id. |
| `queries` | array | `search` and `discover` modes — one keyword or phrase per line. |
| `locations` | array | `local-events` mode — city slugs such as `houston-tx`. |
| `maxItemsPerTarget` | integer | Caps videos returned per target or query. Default 50. |
| `includeTagGroups` | boolean | `videos` mode — also return the trending-topic counts for each feed. Default `false`. |
| `deepLocalEvents` | boolean | `local-events` mode — collect far more events per city at a higher request cost. Default `true`. |
| `maxConcurrency` | integer | How many targets to process in parallel. Default 4. |
| `proxyConfiguration` | object | Optional. Not required — see **Notes and limits**. |

## Output

### `videos` — one row per headline

```json
{
  "_input": "channel/abc7",
  "_source": "S1-playlist-channel",
  "_scrapedAt": "2026-09-14T11:43:18Z",
  "recordType": "VIDEO",
  "videoId": "MaE86JEtf",
  "webUrl": "https://www.haystack.tv/v/lapd-issues-citations-impounds-dozens-minibikes-massive-6th-street-bridge-takeover-bust-MaE86JEtf",
  "feedChannel": "abc7",
  "feedTitle": "ABC7 Los Angeles",
  "title": "LAPD issues citations, impounds dozens of minibikes in massive 6th Street Bridge takeover bust",
  "author": "abc7",
  "publishedDate": "2026-09-14T06:48:41.000Z",
  "ageLabel": "5h ago",
  "duration": 260.227,
  "lang": "en",
  "categories": ["news"],
  "topics": [{ "tag": "lapd" }],
  "popularityScore": 0.4525687061312156,
  "cc": [
    { "label": "en", "lang": "en", "type": "vtt", "url": "https://d2ufudlfb4rsg4.cloudfront.net/abc7/MaE86JEtf/adaptive/MaE86JEtf_subs0.vtt" }
  ],
  "snapshotHighUrl": "https://img.haystack.tv/v1/480x270/haystack-thumbnails/abc7/MaE86JEtf/MaE86JEtf_720.jpg",
  "mediaFiles": { "adaptive": { "url": "https://d2ufudlfb4rsg4.cloudfront.net/abc7/MaE86JEtf/adaptive/MaE86JEtf_master.m3u8", "type": "m3u8" } },
  "channel": { "name": "abc7", "title": "ABC7 Los Angeles", "tag": "abc7" }
}
```

| Field | Type | Description |
|---|---|---|
| `videoId` | string | Haystack's short video id. |
| `webUrl` | string | Permalink to watch the story. |
| `title` | string | The headline. |
| `author` | string | Publishing channel, e.g. `abc7`, `bloomberg`. |
| `publishedDate` | string | Publish time, ISO 8601 UTC. |
| `ageLabel` | string | Human-readable freshness, e.g. `5h ago`. |
| `duration` | number | Clip length in seconds. |
| `categories` | array | Every category the clip belongs to. |
| `topics` | array | Topic tags attached to the clip. |
| `popularityScore` | number | Haystack's popularity ranking for the clip. |
| `cc` | array | Caption tracks — a WebVTT file per language. |
| `snapshotUrl` / `snapshotHighUrl` / `snapshot720Url` | string | Thumbnails at 240px, 480px and 720px wide. |
| `mediaFiles` | object | Video stream manifests. |
| `feedTitle` | string | Which feed the clip was collected from. |

### `video-detail` — 51 fields per story

Everything above, plus:

```json
{
  "recordType": "VIDEO_DETAIL",
  "videoId": "6daOFLevf",
  "title": "Trump Says He'd Love to See 'Unified' Ireland",
  "author": "bloomberg",
  "views": 1942,
  "exit_ratio": 0.0394,
  "haystackTags": ["trump", "ireland", "... 3 more"],
  "downloadUrl": { "hd1080": "https://bbgvod-azure-us-east1-zenko.akamaized.net/vod/vod/m/.../34981474-1476-4249-a1f2-42a3efb3ef1a.mp4" },
  "llm": {
    "primaryCategory": "international_relations",
    "secondaryCategory": "politics",
    "contentType": "interview",
    "scope": "international",
    "urgency": "standard",
    "editorialStance": "analysis",
    "primaryUserNeed": "give-me-perspective",
    "primaryEmotion": "curiosity",
    "isWeatherAlert": false,
    "emotionalIntensity": 0.4,
    "broadAppeal": 0.65,
    "headlineMagnetism": 0.8,
    "narrativeResolution": 0.3
  }
}
```

| Field | Type | Description |
|---|---|---|
| `llm` | object | Haystack's own AI classification of the story — category, content type, scope, urgency, editorial stance, reader need, emotion, and scores for emotional intensity, broad appeal, headline magnetism and narrative resolution. |
| `views` | number | View count. |
| `exit_ratio` | number | Share of viewers who left during the clip. |
| `haystackTags` | array | Internal editorial tags. |
| `sourceUrl` | string | The publisher's own page for the story. |
| `downloadUrl` | object | Direct video file, when the publisher provides one. |

### `channels` — the directory

```json
{
  "recordType": "CHANNEL",
  "webUrl": "https://www.haystack.tv/channel/wpvi",
  "title": " 6abc Philadelphia",
  "short_title": "ABC6 Philadelphia",
  "subtitle": "Philly",
  "name": "wpvi",
  "tag": "wpvi",
  "slug": "wpvi",
  "hashtags": ["wpvi"],
  "thumbnail": "https://img.haystack.tv/v1/512x512/haystack-channel-thumbnails/large/wpvi_512x512.jpg"
}
```

### `polls` — questions with live vote counts

```json
{
  "recordType": "POLL",
  "pollId": "6aa497a8066a8911b61c07f7",
  "webUrl": "https://www.haystack.tv/poll/6aa497a8066a8911b61c07f7",
  "question": "Should the Fed raise interest rates to cool inflation?",
  "choices": ["Yes", "No", "Not sure"],
  "choiceVoteCount": [638, 414, 136],
  "totalVoteCount": 1188,
  "results": [
    { "choice": "Yes", "votes": 638, "pct": 53.7 },
    { "choice": "No", "votes": 414, "pct": 34.85 },
    { "choice": "Not sure", "votes": 136, "pct": 11.45 }
  ],
  "startDate": "2026-09-12T00:06:07.900Z",
  "endDate": "2026-09-16T00:06:07.000Z"
}
```

`results` is computed for you so you do not have to zip the choices and counts yourself.

### `local-events` — what is on in a city

```json
{
  "recordType": "LOCAL_EVENT",
  "_input": "houston-tx",
  "locationSlug": "houston-tx",
  "locationCity": "Houston",
  "locationRegion": "TX",
  "id": "Bk9EMyZCk6s7oa2ZGF",
  "title": "Artemas",
  "description": "Artemas headlines a community music night at White Oak Music Hall - Downstairs in Houston, Texas, delivering an intimate live performance...",
  "labels": [
    { "tag": "concert", "name": "General Concerts", "shortName": "Concert", "category": "music_concerts" }
  ],
  "location": {
    "lat": 29.76043, "lon": -95.3698, "venue": "",
    "address": "Bagby Street, Houston, TX 77002, United States of America",
    "city": "Houston", "state": "Texas", "country": "US", "postalCode": "77002"
  },
  "startDate": "2026-09-15T23:00:00Z",
  "endDate": "2026-09-17T02:00:00Z",
  "timezone": "America/Chicago",
  "local_rank": 55
}
```

Each city also gets one summary row telling you exactly how complete the harvest was:

```json
{
  "recordType": "LOCAL_EVENTS_SUMMARY",
  "locationSlug": "houston-tx",
  "city": "Houston",
  "eventsHarvested": 107,
  "eventsTotalUpstream": 700,
  "eventsHiddenByPaywall": 690,
  "slicesTried": 19,
  "slicesFailed": 0,
  "_warning": "premium_capped_partial_harvest"
}
```

### Error rows

Any input that cannot be resolved produces a labelled row rather than vanishing:

```json
{
  "_input": "channel/notarealchannel12345",
  "_source": "none",
  "recordType": "ERROR",
  "_error": "empty_feed",
  "_errorDetail": "kind=channel value='notarealchannel12345' returned 0 streams."
}
```

Filter on `recordType == "ERROR"` to see which inputs failed and why.

## Notes and limits

- **Feeds are a live snapshot, not an archive.** Haystack serves roughly **15–30 videos per feed** and offers no way to page further back, so `maxItemsPerTarget` above ~30 has no extra effect. To get volume, scrape **more targets** (use `channels` or `taxonomy` mode to get the full list of 483 channels and 299 cities), and re-run on a schedule to build history over time.
- **Local events are capped for free visitors.** Haystack shows anonymous visitors 10 events per request out of several hundred. With `deepLocalEvents` on, the actor issues 19 differently-filtered requests per city and de-duplicates, which typically lifts a city from 10 to **about 100 events** — verified 107 for Houston and 99 for San Francisco. The summary row always reports `eventsTotalUpstream` and `eventsHiddenByPaywall` so you know what was left behind. Turn `deepLocalEvents` off for a fast 10-event sample.
- **Search always returns results.** Haystack's search is fuzzy and never reports "no matches" — a nonsense query still returns ~20 loosely-related clips. Each query therefore gets a `SEARCH_SUMMARY` row with `termMatchRatio`, and a `_warning` of `low_relevance_no_literal_term_match` when none of the returned clips mention your terms.
- **Proxy is optional.** The actor runs fine with no proxy at all, and that is the default. Enable a US proxy only if you want the personalised *My Headlines* feed geo-located to the United States.
- **Freshness.** Category and channel feeds update continuously through the day; polls run for several days; local events look ahead weeks. Scheduling a run every few hours is a reasonable cadence for headline tracking.
