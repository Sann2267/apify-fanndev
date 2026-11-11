# Berlingske Scraper

Extract full article details or the newest headlines from Berlingske, one of Denmark's largest and oldest newspapers — no account or subscription needed.

## Why use this actor

- No account or login required
- Rich article detail: headline, subheadline, byline, publish/update dates, category, tags, and full body text
- Also fetches the newest headlines site-wide without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

**Note on paid articles:** Berlingske limits some articles to subscribers. This actor returns everything that's publicly visible and flags such records with `_paywalled: true`.

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
    "https://www.berlingske.dk/internationalt/to-boern-meldes-draebt-efter-droneangreb-i-rusland"
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

**Article mode** — one record per URL (truncated here for readability — the real record includes the full category/tag list and lead image variants):

```json
{
  "_input": "https://www.berlingske.dk/internationalt/to-boern-meldes-draebt-efter-droneangreb-i-rusland",
  "_source": "S1-nextdata",
  "_scrapedAt": "2026-08-24T00:42:43Z",
  "_paywalled": false,
  "id": "...",
  "title": "To børn meldes dræbt efter droneangreb i Rusland",
  "headline": "To børn meldes dræbt efter droneangreb i Rusland",
  "articleType": "NewsArticle",
  "categories": [{ "title": "Internationalt" }],
  "publicationDate": "2026-08-24T...",
  "payWall": null,
  "body": [
    { "type": "ParagraphNode", "children": [{ "type": "TextNode", "value": "To børn er blevet dræbt, og yderligere ni personer..." }] }
    /* ... 12 more paragraph blocks */
  ],
  "articleText": "To børn er blevet dræbt, og yderligere ni personer, herunder syv børn, er blevet såret i et droneangreb... /* full text, 1784 chars total */"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest:berlingske.dk",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T00:42:43Z",
  "title": "To børn meldes dræbt efter droneangreb i Rusland",
  "link": "https://www.berlingske.dk/internationalt/to-boern-meldes-draebt-efter-droneangreb-i-rusland",
  "publicationDate": "2026-08-24T00:12:46.000Z"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest:berlingske.dk"` in latest mode. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `_paywalled` | boolean | `true` if the article is behind Berlingske's paid tier (article mode only). |
| `title` / `headline` | string | Article headline. |
| `categories` | array | Section/category the article belongs to (article mode). |
| `body` | array | The raw paragraph blocks as published (article mode). |
| `articleText` | string | Full article text, flattened into plain text for convenience (article mode). |
| `link` | string | The article URL. |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
