# Business Recorder Scraper

Extract full article text or the newest headlines from Business Recorder (brecorder.com), Pakistan's leading financial/business daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.brecorder.com/news/40436274/psx-kse-100-closes-in-red-loses-200-points"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. |
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL, raw-passthrough of the site's own article metadata plus:

```json
{
  "_input": "https://www.brecorder.com/news/40436274/psx-kse-100-closes-in-red-loses-200-points",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T17:15:20Z",
  "headline": "PSX: KSE-100 closes in red, loses 200 points",
  "description": "Benchmark index settles at 176,966.68",
  "articleBody": "A volatile trading session was observed...",
  "author": [{ "name": "BR Web Desk", "url": "..." }],
  "publisher": { "name": "Brecorder", "url": "..." },
  "datePublished": "2026-08-24T10:04:31+05:00",
  "dateModified": "2026-08-24T18:27:25+05:00",
  "image": [{ "url": "...", "width": "1024", "height": "768" }]
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "title": "Govt increases petrol price by Re0.39, diesel by Rs2.40 per litre",
  "link": "https://www.brecorder.com/news/40436329/govt-increases-petrol-price-by-re039-diesel-by-rs240-per-litre",
  "publicationDate": "2026-08-25",
  "language": "en"
}
```

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

```json
[
  {
    "url": "https://www.brecorder.com/news/99999999999/nonexistent-article",
    "error": "not_found",
    "detail": ""
  }
]
```

## Notes

- Business Recorder has no RSS/Atom feed — latest mode uses the site's Google News XML sitemap instead, which carries roughly the 100 most recent articles.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
