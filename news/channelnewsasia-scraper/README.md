# Channel NewsAsia (CNA) Scraper

Extract full article text or the newest headlines from Channel NewsAsia (channelnewsasia.com), Singapore's leading English-language broadcaster news site — no account or subscription needed.

## Why use this actor

- No account or login required — CNA is fully free, ad-supported, no paywall on any sampled content
- Full article text included, not just a summary — headline, description, publish/update dates, author, image
- Handles both regular articles and longform/brand-studio features whose body is split across many separate HTML blocks
- Also fetches the newest headlines from a single site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.channelnewsasia.com/sport/uefas-ceferin-says-infantino-could-face-election-challenger-rules-out-fifa-bid-6336611"
  ],
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Latest headlines mode:**
```json
{
  "mode": "latest",
  "limit": 10,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 20. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.channelnewsasia.com/world/iran-new-gas-field-war-energy-6336561",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-23T23:28:38Z",
  "headline": "Iran says finds new gas, after war hits energy sector",
  "description": "TEHRAN: Iran said on Sunday (Aug 23) it had discovered more than 200 billion cubic metres of natural gas...",
  "articleBody": "TEHRAN: Iran said on Sunday (Aug 23) it had discovered more than 200 billion cubic metres of natural gas, months into the Middle East war...",
  "datePublished": "2026-08-24T06:37:00+08:00",
  "dateModified": "2026-08-24T06:39:36+08:00",
  "author": "CNA",
  "image": "https://dam.mediacorp.sg/image/upload/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T23:28:29Z",
  "title": "UEFA's Ceferin says Infantino could face election challenger, rules out FIFA bid",
  "link": "https://www.channelnewsasia.com/sport/uefas-ceferin-says-infantino-could-face-election-challenger-rules-out-fifa-bid-6336611",
  "guid": "https://www.channelnewsasia.com/sport/uefas-ceferin-says-infantino-could-face-election-challenger-rules-out-fifa-bid-6336611",
  "pubDate": "Mon, 24 Aug 2026 07:08:43 +0800",
  "description": null,
  "category": "Sport",
  "thumbnailUrl": "https://dam.mediacorp.sg/image/upload/..."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode only) — often just `"CNA"` for wire/desk content. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode only). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `category` | string | Section tag(s), comma-joined if multiple (latest mode only). |
| `thumbnailUrl` | string | Thumbnail image URL (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
