# Arab News Scraper

Extract full article text or the newest headlines from Arab News (arabnews.com), Saudi Arabia's leading English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, byline, section, publish/update dates, lead image
- Strong wire-service coverage (Reuters, AP, SPA) of Middle East, business, and world news from a Saudi vantage point
- Also fetches the newest headlines from the Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.arabnews.com/node/2655612/middle-east"
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
  "_input": "https://www.arabnews.com/node/2655612/middle-east",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T01:27:25Z",
  "headline": "Iran says new sanctions threatened by ‘desperate’ US will fail",
  "articleBody": "DUBAI: Iran’s foreign minister dismissed the threat of new US sanctions as a sign of desperation on Sunday and said the expected new measures would fail to defeat Tehran. US Treasury Secretary Scott Bessent... ",
  "articleSection": null,
  "datePublished": "2026-08-23T12:21:39",
  "dateModified": "2026-08-23T18:30:16",
  "author": "Reuters",
  "image": "https://www.arabnews.com/sites/default/files/styles/n_670_395/public/main-image/2026/08/23/4743656-192920700.jpg?itok=l4suudIM"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:27:17Z",
  "title": "Indonesian police arrest 72 people suspected of starting forest fires",
  "link": "https://www.arabnews.com/node/2655663/world",
  "publicationDate": "2026-08-24T01:19:45+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline — often a wire service (Reuters, AP, SPA) rather than a staff name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode). |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
