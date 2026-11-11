# Hindustan Times Scraper

Extract full article text or the newest headlines from Hindustan Times (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines from the India-news feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's India-news feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.hindustantimes.com/india-news/two-mlas-among-six-injured-in-car-crash-near-pwd-office-in-delhi-101787509910958.html"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the India-news feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.hindustantimes.com/india-news/two-mlas-among-six-injured-in-car-crash-near-pwd-office-in-delhi-101787509910958.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:58:24Z",
  "@type": "NewsArticle",
  "headline": "Two MLAs among six injured in car crash near PWD office in Delhi | India News",
  "description": "The Innova was carrying Anil Jha, the sitting MLA from Kirari, and Abhay Patil, an MLA from Karnataka. | India News",
  "articleBody": "Two MLAs were among six people who suffered minor injuries after two cars collided near the PWD office in central Delhi on Sunday night, PTI reported ...",
  "keywords": "Delhi Car Crash,Delhi Car Accident,Delhi News,Anil Jha,Abhay Patil",
  "articleSection": "india news",
  "author": [{ "@type": "Organization", "name": "HT News Desk" }],
  "datePublished": "2026-08-24T00:11:42+05:30",
  "dateModified": "2026-08-24T00:11:42+05:30"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T19:58:13Z",
  "title": "Two MLAs among six injured in car crash near PWD office in Delhi",
  "link": "https://www.hindustantimes.com/india-news/two-mlas-among-six-injured-in-car-crash-near-pwd-office-in-delhi-101787509910958.html",
  "guid": "https://www.hindustantimes.com/india-news/two-mlas-among-six-injured-in-car-crash-near-pwd-office-in-delhi-101787509910958.html",
  "pubDate": "Mon, 24 Aug 2026 00:11:42 +0530",
  "description": "The Innova was carrying Anil Jha, the sitting MLA from Kirari, and Abhay Patil, an MLA from Karnataka."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). Note: `headline`/`description` in article mode carry a `" \| <Section>"` suffix as authored by the CMS. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek. |
| `keywords` | string | Comma-separated topic tags (article mode only). |
| `author` | array | Byline (article mode only) — often a desk/organization credit rather than a named reporter. |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
