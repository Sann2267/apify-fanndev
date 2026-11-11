# Jamaica Gleaner Scraper

Extract full article text or the newest headlines from The Gleaner (jamaica-gleaner.com), Jamaica's oldest and largest newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines from the homepage without visiting each article individually (the site's sitemap and RSS feed are both broken/empty, so this actor works around that automatically)
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups (this site's backend is occasionally flaky — the actor retries through it)

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the homepage and returns the newest stories in chronological order.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://jamaica-gleaner.com/article/business/20260823/fosrich-losses-double-solar-panel-prices-fall-faster-distributors-can"
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

**Article mode** — one record per URL:

```json
{
  "_input": "https://jamaica-gleaner.com/article/business/20260823/fosrich-losses-double-solar-panel-prices-fall-faster-distributors-can",
  "_source": "S1-html",
  "_paywalled": false,
  "headline": "FosRich losses double as solar panel prices fall faster than distributors can keep pace",
  "articleBody": "Solar panel prices are falling faster than distributors can adjust...",
  "postedDate": "August 23 2026",
  "datePublished": "2026-08-23T01:06:11-04:00",
  "isAccessibleForFree": true
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-html-listing",
  "title": "Celene Hall is Miss Universe Jamaica 2026",
  "link": "https://jamaica-gleaner.com/article/entertainment/20260825/celene-hall-miss-universe-jamaica-2026",
  "section": "entertainment",
  "urlDate": "2026-08-25"
}
```

A failed URL (removed article, network issue) still produces a row instead of silently disappearing:

```json
{
  "_input": "https://jamaica-gleaner.com/article/news/20260101/nonexistent-fake-article-xyz",
  "_source": "none",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- `latest` mode's `urlDate` is day-precision only (derived from the URL path) — fetch the article in `article` mode for the exact publish timestamp.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
