# TASS Scraper

Extract full article text or the newest headlines from TASS (tass.com), Russia's state news agency, English edition — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs
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
    "https://tass.com/economy/2177103"
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
  "_input": "https://tass.com/economy/2177103",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T16:34:50Z",
  "headline": "Bank of Russia raises dollar rate to 83.29 rubles for August 25",
  "description": "The official euro exchange rate was raised by 57.83 kopecks to 97.4384 rubles",
  "articleBody": "MOSCOW, August 24. /TASS/. The Bank of Russia set the official dollar exchange rate...",
  "author": "TASS",
  "publisher": "TASS",
  "datePublished": "2026-08-24T16:24:48.000Z",
  "dateModified": "2026-08-24T16:24:48.000Z",
  "image": ["https://tass.com/img/blocks/common/tass_logo_share_eng.png"]
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-24T16:34:56Z",
  "title": "Bank of Russia raises dollar rate to 83.29 rubles for August 25",
  "link": "https://tass.com/economy/2177103",
  "description": "The official euro exchange rate was raised by 57.83 kopecks to 97.4384 rubles",
  "pubDate": "Mon, 24 Aug 2026 19:24:48 +0300",
  "category": "Business & Economy"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline — always `"TASS"` since bylines are agency-attributed, not individual (article mode only). |
| `publisher` | string | Always `"TASS"` (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `category` | string | Section name, e.g. `"World"`, `"Business & Economy"` (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
