# Chicago Tribune Scraper

Extract full article text or the top headlines from the Chicago Tribune — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, section, keywords, and publish/update dates
- Also fetches the current top headlines from the homepage without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the current top headlines automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the homepage and returns the current top-story headlines.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.chicagotribune.com/2026/08/23/cps-budget-problems-back-to-school/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the current top headlines. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.chicagotribune.com/2026/08/23/cps-budget-problems-back-to-school/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-23T23:06:36Z",
  "@type": "NewsArticle",
  "headline": "CPS budget uncertainty looms as students head back to school",
  "articleBody": "When teacher assistant Jared Edwards was laid off at Curtis Elementary in Roseland this summer, it was the second consecutive year his position had been cut ...",
  "articleSection": "Education",
  "creator": ["Kate Armanini"],
  "datePublished": "2026-08-23T...",
  "isAccessibleForFree": false
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-homepage",
  "_scrapedAt": "2026-08-23T23:06:24Z",
  "title": "CPS budget uncertainty looms as students head back to school",
  "link": "https://www.chicagotribune.com/2026/08/23/cps-budget-problems-back-to-school/"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `creator` / `author` | array / object | Byline (article mode only). |
| `articleSection` | string | Section name (article mode only). |
| `isAccessibleForFree` | boolean | Publisher's own metering flag — `false` does not mean the text is truncated; full text is present regardless (see `CRAWLING_METHOD.md`). |
| `link` | string | The article URL (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Notes

Latest mode returns the current homepage's top-story headlines rather than a strict reverse-chronological feed — the Chicago Tribune's RSS/sitemap endpoints are gated behind a bot-verification challenge that isn't required to reach individual articles. See `CRAWLING_METHOD.md` for details.
