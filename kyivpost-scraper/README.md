# Kyiv Post Scraper

Extract full article text or the newest headlines from Kyiv Post (kyivpost.com), an English-language Ukrainian news outlet — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, category, publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.kyivpost.com/post/83007"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.kyivpost.com/post/83007",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-25T09:12:03Z",
  "headline": "At 35, Ukraine Has No More Time to Fail",
  "description": "Ukraine's path to EU membership is the greatest achievement secured by its people in their fight for survival...",
  "articleBody": "Modern Ukraine turns 35 today.\n\nFor much of its independence, Ukraine could reasonably argue that it was a young democracy...",
  "author": "Lesia Dubenko",
  "publisher": "Kyiv Post",
  "category": "World",
  "datePublished": "2026-08-24T17:03:00+03:00",
  "dateModified": "2026-08-24T17:03:00+03:00",
  "image": ["https://static.kyivpost.com/storage/2026/08/21/2ece391069ba97decb418301014a6c75.jpg?w=1200&q=90&f=jpg"],
  "isAccessibleForFree": true
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-25T09:12:10Z",
  "title": "Zelensky: There Is No Doubt — Ukraine Will Always Be Independent",
  "link": "https://www.kyivpost.com/post/83009",
  "description": "President Volodymyr Zelensky marked Ukraine's 35th Independence Day on Monday, Aug. 24...",
  "pubDate": "Mon, 24 Aug 2026 19:10:48 +0300",
  "category": "Ukraine",
  "topics": ["Ukraine", "War in Ukraine"],
  "author": "Kyiv Post",
  "guid": "83009",
  "image": "https://static.kyivpost.com/storage/2023/06/25/8546ddbb77b2c9d7f2d1107f4636ec33.jpeg?w=640&q=90&f=jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode: page meta description; latest mode: RSS teaser). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline — individual reporter name where available (article mode only). |
| `publisher` | string | Always `"Kyiv Post"` (article mode only). |
| `category` | string | Section name, e.g. `"World"`, `"Ukraine"`. |
| `topics` | array | Additional topic tags (latest mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `isAccessibleForFree` | boolean | Upstream paywall flag, passed through as-is (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `guid` | string | Internal article ID (latest mode). |
| `image` | string/array | Lead image URL(s). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
