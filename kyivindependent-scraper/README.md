# Kyiv Independent Scraper

Extract full article text or the newest headlines from The Kyiv Independent (kyivindependent.com), Ukraine's leading English-language news outlet — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, reader-funded nonprofit newsroom with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, publish/update dates, lead image
- Direct, on-the-ground coverage of the war in Ukraine and Ukrainian politics from a newsroom based in Kyiv
- Also fetches the newest headlines (with lead image) from the Google News sitemap without visiting each article individually
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
    "https://kyivindependent.com/russian-strike-damages-us-owned-mondelez-facility-in-sumy-oblast/"
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
  "_input": "https://kyivindependent.com/russian-strike-damages-us-owned-mondelez-facility-in-sumy-oblast/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-24T01:42:48Z",
  "headline": "Russian strike damages US-owned Mondelez facility in Sumy Oblast",
  "description": "Russia struck a factory belonging to U.S. multinational food company Mondelez International in Sumy Oblast on Aug. 23, Foreign Minister Andrii Sybiha said.",
  "articleBody": "Russia struck a factory belonging to U.S. multinational food company Mondelez International in Sumy Oblast on Aug. 23, Foreign Minister Andrii Sybiha said.\n\nTwo Russian drones hit the facility located in the city Trostianets...",
  "articleSection": null,
  "datePublished": "2026-08-23T20:51:54.000Z",
  "dateModified": "2026-08-23T20:51:54.000Z",
  "author": "Sonya Bandouil",
  "isAccessibleForFree": true,
  "keywords": ["War", "Ukraine", "United States", "Sumy Oblast", "Russia", "Drone attack"],
  "image": "https://assets.kyivindependent.com/content/images/2026/08/Sumy-Mondelez-attack_20260823-204211.webp"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:42:45Z",
  "title": "Russian strike damages US-owned Mondelez facility in Sumy Oblast",
  "link": "https://kyivindependent.com/russian-strike-damages-us-owned-mondelez-facility-in-sumy-oblast/",
  "publicationDate": "2026-08-23T20:51:54+00:00",
  "imageUrl": "https://assets.kyivindependent.com/content/images/2026/08/Sumy-Mondelez-attack_20260823-204211.webp"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode only). |
| `isAccessibleForFree` | boolean | Whether the site marks this article as free (article mode only). |
| `keywords` | array | Tag keywords (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
