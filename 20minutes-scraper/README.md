# 20 Minutes Scraper

Extract full article text or the newest headlines from 20 Minutes (20minutes.fr), France's leading free daily — no account or subscription needed.

## Why use this actor

- No account or login required, and no paywall — 20 Minutes is a free, ad-supported newspaper, so full article text is always available
- Full article text included, not just a summary — headline, byline, section, publish/update dates, and category tags
- Also fetches the newest headlines (with full body HTML included) from a single site-wide feed without visiting each article individually
- Handles both regular articles and live "direct" blog pages (sports, breaking news)
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's front-page feed and returns the newest stories, including full body HTML.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.20minutes.fr/politique/4240413-20260823-presidentielle-2027-raphael-glucksmann-confirme-candidature-scrutin"
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
  "_input": "https://www.20minutes.fr/politique/4240413-20260823-presidentielle-2027-raphael-glucksmann-confirme-candidature-scrutin",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T22:55:10Z",
  "@type": "NewsArticle",
  "headline": "Présidentielle 2027 : Raphaël Glucksmann confirme sa candidature au scrutin",
  "articleBody": "La fin d'un faux suspense. Raphaël Glucksmann a confirmé, ce dimanche, sa candidature à l'élection présidentielle de 2027 ...",
  "description": "Ce dimanche, Raphaël Glucksmann a confirmé sa candidature à l'élection présidentielle au 20 heures de TF1",
  "datePublished": "2026-08-23T18:33:10.881Z",
  "dateModified": "2026-08-23T19:13:16.801Z",
  "publisher": { "type": "Organization", "name": "20 Minutes" }
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T22:55:04Z",
  "title": "Présidentielle 2027 : Raphaël Glucksmann confirme sa candidature au scrutin",
  "link": "https://www.20minutes.fr/politique/4240413-20260823-presidentielle-2027-raphael-glucksmann-confirme-candidature-scrutin",
  "guid": "https://www.20minutes.fr/politique/4240413-20260823-presidentielle-2027-raphael-glucksmann-confirme-candidature-scrutin",
  "pubDate": "Sun, 23 Aug 2026 18:33:10 GMT",
  "description": "Ce dimanche, Raphaël Glucksmann a confirmé sa candidature à l'élection présidentielle au 20 heures de TF1",
  "author": "Q.M. avec AFP",
  "body": "<p>La fin d'un faux suspense ...</p>",
  "categories": ["Politique", "Présidentielle 2027"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` / `body` | string | Full article content — plain text in article mode, raw HTML in latest mode. |
| `@type` | string | `"NewsArticle"` for regular stories, `"LiveBlogPosting"` for live "direct" coverage (article mode only). |
| `author` | string | Byline (latest mode). Article mode carries a full `author` object from the source page. |
| `categories` | array | Topic tags (latest mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
