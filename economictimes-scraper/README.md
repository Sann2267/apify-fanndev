# Economic Times Scraper

Extract full article text or the newest headlines from The Economic Times (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, and publish/update dates
- Also fetches the newest headlines from a single combined feed without visiting each article individually
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
    "https://economictimes.indiatimes.com/news/india/siliguri-corridor-from-chickens-neck-to-elephants-trunk/articleshow/133445432.cms"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://economictimes.indiatimes.com/news/india/siliguri-corridor-from-chickens-neck-to-elephants-trunk/articleshow/133445432.cms",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:17:31Z",
  "@type": "NewsArticle",
  "inLanguage": "en",
  "keywords": ["Siliguri Corridor", "Chicken's Neck", "Elephant's Trunk", "northeast India", "biodiversity"],
  "headline": "Siliguri corridor: From chicken's neck to elephant's trunk",
  "description": "The Siliguri Corridor, affectionately dubbed the Elephant's Trunk, highlights its essential role in connecting northeastern India with neighboring territories...",
  "datePublished": "2026-08-24T00:09:00+05:30",
  "dateModified": "2026-08-24T00:09:00+05:30",
  "articleSection": "News",
  "articleBody": "How did the Siliguri Corridor come to be known as Chicken's Neck? While the answer t ..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T19:17:22Z",
  "title": "Market Trading Guide: Jayaswal Neco Industries among 2 stock recommendations for Monday",
  "link": "https://economictimes.indiatimes.com/markets/stocks/news/market-trading-guide-jayaswal-neco-industries-among-2-stock-recommendations-for-monday/articleshow/133438554.cms",
  "guid": "https://economictimes.indiatimes.com/markets/stocks/news/market-trading-guide-jayaswal-neco-industries-among-2-stock-recommendations-for-monday/articleshow/133438554.cms",
  "pubDate": "Sun, 23 Aug 2026 16:39:50 +0530",
  "description": "Analysts recommend Jayaswal Neco Industries and Alkyl Amines for Friday, citing bullish breakouts, strong trading volumes and improving RSI momentum."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek. |
| `keywords` | array | Topic tags (article mode only). |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
