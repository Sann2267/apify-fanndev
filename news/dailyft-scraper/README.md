# Daily FT Scraper

Extract full article text or the newest headlines from Daily FT (ft.lk), Sri Lanka's leading business newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, deck, description, publish/modified dates, reconstructed into clean paragraphs from a legacy hand-formatted CMS
- Also fetches the newest headlines straight from the site's RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups (including the site's own occasional server-side slowdowns)

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
    "https://www.ft.lk/news/VFS-Global-launches-Republic-of-Korea-visa-services-in-Sri-Lanka/56-796442"
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
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL:

```json
{
  "_input": "https://www.ft.lk/news/VFS-Global-launches-Republic-of-Korea-visa-services-in-Sri-Lanka/56-796442",
  "_source": "S1-html",
  "headline": "VFS Global launches Republic of Korea visa services in Sri Lanka",
  "deck": "Opens modern and easily accessible centre in Colombo",
  "description": "Starting 21 August 2026, Korea visa applicants can visit our centrally located visa application centre...",
  "articleBody": "Starting 21 August 2026, Korea visa applicants can visit our centrally located visa application centre...",
  "datePublished": "2026-08-24 06:04:41",
  "dateModified": "2026-08-24 06:03:00"
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "title": "IMF test looms as Sri Lanka's economic stability meets public pain: Ravi K",
  "link": "https://www.ft.lk/top-story/IMF-test-looms-as-Sri-Lanka-s-economic-stability-meets-public-pain--Ravi-K/26-796380",
  "description": "THE New Democratic Front (NDF) MP and former Finance Minister Ravi Karunanayake yesterday said...",
  "pubDate": "Saturday, 22 August 2026 01:23"
}
```

A failed URL (removed article, network issue) still produces a row instead of silently disappearing:

```json
{
  "_input": "https://www.ft.lk/news/nonexistent-fake-article-xyz/56-00000000",
  "_source": "none",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- This site doesn't publish a structured author field — no `author` field is included rather than guessing at one. Some articles embed a byline as plain text at the start of the body.
- The `deck` field (a one-line subheading) is present on hard-news articles and `null` on opinion/column pieces.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
