# UzDaily Scraper

Extract full article text or the newest headlines from UzDaily (uzdaily.uz), Uzbekistan's English-language business/news portal — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, publish/modified dates, word count
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed and returns the newest headlines with a short teaser and lead image (fetch full text separately in article mode).
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.uzdaily.uz/en/central-asia-fintech-group-calls-for-unified-financial-rails/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the RSS feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed itself carries ~20 items). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output, `articleBody` truncated here for readability):

```json
{
  "_input": "https://www.uzdaily.uz/en/central-asia-fintech-group-calls-for-unified-financial-rails/",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:14:13Z",
  "headline": "Central Asia Fintech Group Calls for Unified Financial Rails",
  "description": "The Central Asian Fintech Association has proposed four priorities to harmonize regional financial markets, including payments and digital ID.",
  "articleBody": "Tashkent, Uzbekistan (UzDaily.uz) — The Central Asian Fintech Association has proposed four priority areas for harmonizing the region's financial markets: payment interoperability, mutual recognition of digital identification, compatible open banking standards and common principles for data governance. The proposals were presented during a session at the Silk Road Finance and Technology Forum in Tashkent on 25 August.\n\n... (truncated -- full article continues for 625 words in the real output)",
  "author": "Anvar Umarov",
  "authorUrl": "https://www.uzdaily.uz/en/author/anvar-umarov/",
  "publisher": "UzDaily.uz",
  "datePublished": "2026-08-26T16:23:00+05:00",
  "dateModified": "2026-08-26T19:18:59.302382+05:00",
  "images": ["https://www.uzdaily.uz/media/filer_public/90/02/900234b5-4a98-46b9-b4af-25c618047a4d/silkroadfinance3_20260826112510.webp"],
  "articleSection": "Finance",
  "keywords": "Central Asia fintech, Central Asian Fintech Association, financial infrastructure, payment interoperability, digital identity, open banking, data governance, Uzbekistan fintech, Silk Road Finance and Technology Forum, Central Bank of Uzbekistan",
  "wordCount": 625,
  "isAccessibleForFree": true
}
```

**Latest headlines mode** — one record per headline (real output):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T17:13:08Z",
  "title": "Gold again above US$4,600, copper hits record high",
  "link": "https://www.uzdaily.uz/en/gold-again-above-us4600-copper-hits-record-high/",
  "teaser": "Gold is trading above US$4,600 while copper hits a record high as precious and industrial metals respond to macroeconomic and supply factors.",
  "guid": "117074",
  "category": "Economy",
  "thumbnail": "https://www.uzdaily.uz/media/filer_public/f5/b4/f5b4206a-91f1-4e9d-9cd9-11008a247edb/goldbullion1_20260728210127.webp",
  "pubDate": "Wed, 26 Aug 2026 19:11:00 +0500"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short article dek/summary (article mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline name (article mode). |
| `authorUrl` | string | Link to the author's profile page (article mode). |
| `publisher` | string | Publisher organization name (article mode). |
| `datePublished` / `dateModified` | string | ISO 8601 publish/modified timestamps (article mode). |
| `images` | array | Article hero image URL(s) (article mode). |
| `articleSection` | string | Site section, e.g. "Economy", "Finance", "Uzbekistan" (article mode). |
| `keywords` | string | Comma-separated keyword string (article mode). |
| `wordCount` | integer | Article word count, as reported by the site (article mode). |
| `isAccessibleForFree` | boolean | Whether the article is paywalled (article mode) — always `true` in samples seen so far. |
| `link` | string | Article URL (latest mode). |
| `teaser` | string | Short feed teaser, not the full body (latest mode). |
| `guid` | string | Feed item's internal article ID (latest mode). |
| `category` | string | Feed item's category tag (latest mode). |
| `thumbnail` | string | Lead image URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Good to know

- This actor covers **UzDaily's English edition only**, published under the `/en/` path on `uzdaily.uz` — the `/ru/`, `/uz/`, and `/uzc/` editions on the same domain are out of scope.
- Latest-headlines mode returns a short teaser, not the full article text — the RSS feed doesn't embed the complete body. Pass the article's `link` into article mode for full text.
