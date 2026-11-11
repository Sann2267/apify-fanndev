# Korea Herald Scraper

Extract full article text or the newest headlines from The Korea Herald (koreaherald.com), South Korea's leading English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/update dates, lead image
- English-language coverage of South Korean politics, business, and culture, plus wire coverage of major world news
- Also fetches the newest headlines from the site's rolling news sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's rolling news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.koreaherald.com/article/10848093"
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
  "_input": "https://www.koreaherald.com/article/10848093",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T01:46:47Z",
  "headline": "Seoul light festival returns with iconic art, live music",
  "description": "Seoul Light DDP 2026 Fall will run Sept. 3-13 at Dongdaemun Design Plaza, organizers said Thursday. The event features media art installations inspired by video",
  "articleBody": "Works inspired by video artist Nam June Paik, painter Yoo Young-kuk to light up DDP in fall\n\nSeoul Light DDP 2026 Fall will run Sept. 3-13 at Dongdaemun Design Plaza, organizers said Thursday...",
  "datePublished": "2026-08-21T09:32:00+09:00",
  "dateModified": "2026-08-21T09:32:00+09:00",
  "author": "Moon Ki-hoon",
  "image": "https://res.koreaherald.com/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:46:44Z",
  "title": "Kazakhstan's ruling party wins parliamentary elections: exit polls",
  "link": "https://www.koreaherald.com/article/10849749",
  "publicationDate": "2026-08-24T10:43:41+09:00"
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
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode). |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
