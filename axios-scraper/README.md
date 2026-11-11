# Axios Scraper

Extract full article details or the newest headlines from Axios — no account or subscription needed.

## Why use this actor

- No account or login required
- Rich article detail: headline, summary, section, publish/update dates, and lead image
- Also fetches the newest headlines site-wide, including full article body text and co-bylines, without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out every publicly available detail about the story.
3. In latest mode, the actor reads the site-wide headline feed and returns the newest stories, including full text and bylines.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.axios.com/2026/08/23/greg-abbott-texas-data-centers-ai-backlash"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines site-wide. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability; the real record includes the full breadcrumb trail):

```json
{
  "_input": "https://www.axios.com/2026/08/23/greg-abbott-texas-data-centers-ai-backlash",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:14:12Z",
  "@type": "NewsArticle",
  "articleSection": "Energy & Climate",
  "datePublished": "2026-08-23T16:24:43.527523Z",
  "description": "The backlash has become a political threat.",
  "headline": "Data centers \"dug their own grave,\" says Texas Gov. Greg Abbott",
  "image": { "@type": "ImageObject", "contentUrl": "https://images.axios.com/p50GH8bp0KMNSoEqZnJ0i38fbPk=/2026/08/23/1787494410129.jpeg" },
  "dateModified": "2026-08-23T16:24:43.527523Z"
  /* ... mainEntityOfPage / breadcrumb trail */
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T19:13:46Z",
  "title": "Texas welcomed the AI boom. Now Abbott says data centers \"dug their own grave\"",
  "link": "https://www.axios.com/2026/08/23/greg-abbott-texas-data-centers-ai-backlash",
  "guid": "https://www.axios.com/2026/08/23/greg-abbott-texas-data-centers-ai-backlash",
  "pubDate": "Sun, 23 Aug 2026 16:38:19 +0000",
  "description": "<p>Texas Gov. Greg Abbott delivered one of the starkest warnings yet ...",
  "content": "<p>Texas Gov. Greg Abbott delivered one of the starkest warnings yet ... (full article body)",
  "creators": ["Andrew Pantazi", "Ben Geman"],
  "categories": ["top"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `description` | string | Article summary/dek. |
| `articleSection` | string | Section/vertical name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `content` | string | Full HTML article body (latest mode only). |
| `creators` | array | Byline authors (latest mode; can be empty). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
