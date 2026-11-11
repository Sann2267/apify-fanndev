# China Daily Scraper

Extract full article text or the newest headlines from China Daily (chinadaily.com.cn), China's official English-language state newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, byline, publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines from the homepage without visiting each article individually (the site's RSS feed and sitemap are both stale/dead artifacts, so this actor works around that automatically)
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

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
    "https://www.chinadaily.com.cn/a/202608/24/WS6a8c22eb45ce1d77cb5e1e70.html"
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
  "_input": "https://www.chinadaily.com.cn/a/202608/24/WS6a8c22eb45ce1d77cb5e1e70.html",
  "_source": "S1-html",
  "headline": "Xi congratulates Alamgir on assuming Bangladeshi presidency",
  "description": null,
  "articleBody": "BEIJING -- Chinese President Xi Jinping on Monday extended congratulations...",
  "author": null,
  "publisher": "Xinhua",
  "datePublished": "2026-08-24T18:54:46+08:00",
  "dateModified": "..."
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-html-listing",
  "title": "China, Indonesia power the next stage of development",
  "link": "https://www.chinadaily.com.cn/a/202608/24/WS6a8c110545ce1d77cb5e1e58.html",
  "urlDate": "2026-08-24"
}
```

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Notes

- `author`/`description` come back `null` on wire-service (Xinhua) content with no named byline — this is a real absence in the source, not a bug.
- `latest` mode's `urlDate` is day-precision only (derived from the URL path) — fetch the article in `article` mode for the exact publish timestamp.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
