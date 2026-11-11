# Aftenposten Scraper

Extract full article details or the newest headlines from Aftenposten, Norway's largest newspaper — no account or subscription needed.

## Why use this actor

- No account or login required
- Rich article detail: headline, description, byline, publish/update dates, section, topic keywords, word count, and lead image
- Also fetches the newest headlines site-wide without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

**Note on paid articles:** Aftenposten limits some articles to subscribers. This actor returns everything that's publicly visible and flags such records with `_paywalled: true`.

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode.
2. In article mode, the actor opens each URL and pulls out every publicly available detail about the story.
3. In latest mode, the actor reads the site-wide newest-articles feed and returns the freshest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.aftenposten.no/okonomi/i/3pXKAq/flygelederstreiken-norwegian-kansellerer-seks-flyginger-wideroee-tre"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability — the real record includes full author and image details):

```json
{
  "_input": "https://www.aftenposten.no/okonomi/i/3pXKAq/flygelederstreiken-norwegian-kansellerer-seks-flyginger-wideroee-tre",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T00:40:00Z",
  "_paywalled": false,
  "headline": "Flygelederstreiken: Norwegian kansellerer seks flyginger, Widerøe tre",
  "datePublished": "2026-08-24T...",
  "wordCount": 119,
  "articleSection": "Økonomi",
  "description": "Streiken blant franske flygeledere fører til kanselleringer for norske flyselskap.",
  "isAccessibleForFree": true,
  "publisher": { "@type": "NewsMediaOrganization", "name": "Aftenposten" },
  "articleBody": "Flygelederstreiken i Frankrike fører til at Norwegian kansellerer seks flyginger... /* full text, 1013 chars total */"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest:aftenposten.no",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-24T00:40:00Z",
  "title": "Flygelederstreiken: Norwegian kansellerer seks flyginger, Widerøe tre",
  "link": "https://www.aftenposten.no/okonomi/i/3pXKAq/flygelederstreiken-norwegian-kansellerer-seks-flyginger-wideroee-tre",
  "pubDate": "Mon, 24 Aug 2026 ...",
  "description": "Streiken blant franske flygeledere fører til kanselleringer for norske flyselskap."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest:aftenposten.no"` in latest mode. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `_paywalled` | boolean | `true` if the article is behind Aftenposten's paid tier (article mode only). |
| `headline` / `title` | string | Article headline. |
| `description` | string | Article summary/dek. |
| `wordCount` | integer | Word count as reported by the source (article mode). |
| `articleSection` | string | Section/category the article belongs to (article mode). |
| `articleBody` | string | Full article text where publicly available. |
| `link` | string | The article URL. |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
