# The Atlantic Scraper

Extract full article text or the newest headlines from The Atlantic — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, dek, byline (with co-authors), tags, and publish/update dates
- Also fetches the newest headlines from a single site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.theatlantic.com/ideas/2026/08/a-year-of-troops-in-washington/688317/"
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
  "_input": "https://www.theatlantic.com/ideas/2026/08/a-year-of-troops-in-washington/688317/",
  "_source": "S1-urql",
  "_scrapedAt": "2026-08-23T20:06:18Z",
  "headline": "An American City, With Troops on Its Streets",
  "description": "Since the country's founding, deployments of soldiers to U.S. soil have been exceedingly rare. But residents of Washington, D.C., are living in a new normal.",
  "articleBody": "The sight of military troops patrolling in a peaceful American city would once have been strange, if not outright alarming ...",
  "author": [
    { "name": "Quinta Jurecic", "url": "https://www.theatlantic.com/author/quinta-jurecic/" },
    { "name": "Marie-Rose Sheinerman", "url": "..." }
  ],
  "tags": ["Politics", "Washington D.C.", "National Guard"],
  "primaryCategory": "Politics",
  "hasMeter": true,
  "datePublished": "2026-08-23T07:52:11-04:00",
  "dateModified": "2026-08-23T11:26:55-04:00"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-atom",
  "_scrapedAt": "2026-08-23T20:07:22Z",
  "title": "An American City, With Troops on Its Streets",
  "link": "https://www.theatlantic.com/ideas/2026/08/a-year-of-troops-in-washington/688317/?utm_source=feed",
  "guid": "tag:theatlantic.com,2026:50-688317",
  "pubDate": "2026-08-23T07:52:11-04:00",
  "updated": "2026-08-23T11:26:55-04:00",
  "description": "Since the country's founding, deployments of soldiers to U.S. soil have been exceedingly rare. But residents of Washington, D.C., are living in a new normal.",
  "authors": ["Quinta Jurecic", "Marie-Rose Sheinerman"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article dek/summary. |
| `author` / `authors` | array | Byline — array of `{name, url}` objects in article mode, an array of name strings in latest mode. Co-bylines supported. |
| `tags` / `primaryCategory` | array / string | Topic tags and section (article mode only). |
| `hasMeter` | boolean | Whether The Atlantic's metered-subscription flag is set on this article (full text is still returned regardless — see the actor's technical notes). |
| `datePublished` / `dateModified` | string | Publication timestamps. |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
