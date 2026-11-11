# Motley Fool Scraper

Extract full article text or the newest headlines (with full text included) from The Motley Fool (fool.com), a major investing and stock-analysis media outlet — no account or subscription needed for its free articles.

## Why use this actor

- No account or login required — the free articles (the vast majority of fool.com's news/analysis content) have no paywall
- Full article text included, not just a summary — headline, description, author, publish date, reconstructed into clean paragraphs
- Latest-headlines mode returns **full article text for every item**, not just titles — the RSS feed embeds the complete body
- Automatically strips image-caption clutter ("Image source: The Motley Fool.") that would otherwise pollute the article body
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed, which already embeds full article HTML, and returns the newest stories with full text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.fool.com/investing/2026/08/24/time-sensitive-should-you-buy-marvell-technology-s/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines with full text. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.fool.com/investing/2026/08/24/time-sensitive-should-you-buy-marvell-technology-s/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T16:42:56Z",
  "headline": "Should You Buy Marvell Technology Stock Before Aug. 27?",
  "description": "The chip designer and optical networking maker reports second quarter earnings on Thursday...",
  "articleBody": "Marvell Technology ( MRVL -3.30% ) has delivered a standout performance among semiconductor stocks...",
  "author": "Adam Spatacco",
  "datePublished": "2026-08-24T15:16:21Z",
  "image": "https://g.foolcdn.com/editorial/images/..."
}
```

**Latest headlines mode** — one record per headline, with full text already included:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-24T16:45:19Z",
  "title": "Prediction: 1 Cryptocurrency That Will Be Worth More Than Bitcoin and Ethereum Combined",
  "link": "https://www.fool.com/investing/2026/08/24/prediction-1-cryptocurrency-that-will-be-worth-mor/",
  "description": "If there's one cryptocurrency with a chance of outpacing Bitcoin and Ethereum over the next five years, it's Solana.",
  "author": "Dominic Basulto",
  "articleBody": "It's remarkable how dominant Bitcoin (CRYPTO: BTC) and Ethereum (CRYPTO: ETH) have been over the past decade...",
  "pubDate": "Mon, 24 Aug 2026 12:15:00 -0400"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content, present in both modes. |
| `author` | string | Author display name. |
| `datePublished` | string | ISO-8601 timestamp (article mode only). |
| `image` | string | Hero image URL (article mode only). |
| `link` | string | Article URL, stripped of `?source=...` tracking params (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## A note on paid content

The Motley Fool sells premium stock-recommendation newsletters (separate from fool.com's free articles) whose content lives behind `/premium` paths that are excluded by `robots.txt` and were never targeted by this actor. Every URL this actor was built and tested against is free, public content.
