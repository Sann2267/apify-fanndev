# Jamaica Observer Scraper

Extract full article text or the newest headlines from the Jamaica Observer (jamaicaobserver.com), one of Jamaica's two main daily newspapers — no account or subscription needed.

This is a distinct, separate publisher from The Gleaner (jamaica-gleaner.com), already covered by this portfolio's `jamaicagleaner-scraper` — the two are direct competitors under different owners.

## Why use this actor

- No account or login required — no hard paywall was found on any sampled article (`isAccessibleForFree: true`)
- Full article text included, not just a summary — headline, publish/modified dates, section, lead image, reconstructed into clean paragraphs from the article's ld+json + HTML body
- Also fetches the newest headlines directly from the site's working WordPress RSS feed (`/feed/`) — no homepage-scrape workaround needed here (unlike `jamaicagleaner-scraper`, whose sitemap and RSS are both broken)
- `latest` mode includes the real reporter byline (name, title, email) via RSS `dc:creator` — a field not available anywhere on the article page itself
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups or block-page markers

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories from the RSS feed.
2. In article mode, the actor opens each URL, reads the `NewsArticle` JSON-LD block for metadata, and pulls the full body text from `div.content-single-wrap`.
3. In latest mode, the actor fetches `https://www.jamaicaobserver.com/feed/` and returns the newest items, including each item's full body HTML and reporter byline.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.jamaicaobserver.com/2026/08/26/unhealthy-trend-student-obesity-surges-15-3/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from RSS. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL:

```json
{
  "_input": "https://www.jamaicaobserver.com/2026/08/26/unhealthy-trend-student-obesity-surges-15-3/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T12:00:00Z",
  "headline": "Unhealthy trend: Student obesity surges 15.3%",
  "articleBody": "Full article text, reconstructed from clean paragraphs...",
  "datePublished": "2026-08-26T05:00:00-04:00",
  "dateModified": "2026-08-26T09:00:00-04:00",
  "image": "https://www.jamaicaobserver.com/wp-content/uploads/...jpg",
  "articleSection": ["News"],
  "isAccessibleForFree": true,
  "_paywalled": false
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T12:00:00Z",
  "title": "Celene Hall is Miss Universe Jamaica 2026",
  "link": "https://www.jamaicaobserver.com/2026/08/25/celene-hall-miss-universe-jamaica-2026/",
  "guid": "https://jamaicaobserver.newsmemory.com/...",
  "creator": "Arthur Hall Editor HallA@jamaicaobserver.com",
  "category": "Entertainment",
  "pubDate": "Tue, 25 Aug 2026 10:00:00 -0400",
  "contentEncoded": "<b>Lead paragraph...</b><p>Full article body HTML...</p>"
}
```

A failed URL (removed article, network issue) still produces a row instead of silently disappearing:

```json
{
  "_input": "https://www.jamaicaobserver.com/2026/01/01/nonexistent-fake-article-xyz/",
  "_source": "none",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- `author` is **not** available in `article` mode — the article page itself carries no byline anywhere (no meta tag, no rendered HTML element). Use `latest` mode's `creator` field for the real reporter byline instead.
- The RSS `guid` field is an internal `newsmemory.com` URL, not a public link — use `link` for the public article URL.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
