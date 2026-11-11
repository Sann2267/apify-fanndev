# Livemint Scraper

Extract full article text or the newest headlines from Livemint (Mint), one of India's leading business and financial dailies — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, author, keywords, section, and publish/update dates
- Also fetches the newest headlines (with lead image) from a single combined feed without visiting each article individually
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
    "https://www.livemint.com/market/stock-market-news/usiran-war-to-crude-oil-prices-top-five-triggers-that-may-dictate-the-indian-stock-market-this-week-11786846871492.html"
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
  "_input": "https://www.livemint.com/market/stock-market-news/usiran-war-to-crude-oil-prices-top-five-triggers-that-may-dictate-the-indian-stock-market-this-week-11786846871492.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:32:31Z",
  "@type": "NewsArticle",
  "inLanguage": "en",
  "headline": "US-Iran war to crude oil prices: Top five triggers that may dictate the Indian stock market this week",
  "description": "Indian stock market: For the week, the Sensex fell 0.62% to 78,009.25, while the Nifty declined 0.83% to 24,366. While some of the global triggers continue this week, read on to know what are the fresh factors to watch out for this week.",
  "datePublished": "2026-08-16T08:23:35+05:30",
  "dateModified": "2026-08-23T22:35:46+05:30",
  "alternativeHeadline": "US-Iran war to crude oil prices: Top five triggers that may dictate the Indian stock market this week",
  "articleBody": "Indian stock market: The Indian stock market closed the week on a weaker note, weighed down by elevated crude oil prices, renewed geopolitical tensions and mixed global signals...",
  "author": { "...": "..." },
  "publisher": { "...": "..." },
  "image": { "...": "..." },
  "keywords": ["..."],
  "mentions": ["..."]
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T19:32:30Z",
  "title": "Trump crackdown could take 200,000 immigrant truck drivers off the roads",
  "link": "https://www.livemint.com/news/us-news/trump-crackdown-could-take-200-000-immigrant-truck-drivers-off-the-roads-11787505496294.html",
  "guid": "https://www.livemint.com/news/us-news/trump-crackdown-could-take-200-000-immigrant-truck-drivers-off-the-roads-11787505496294.html",
  "pubDate": "Sun, 23 Aug 2026 23:24:16 +0530",
  "description": "Critics argue that the campaign is being driven less by public safety concerns and more by the administration's broader mass deportation and \"America First\" agenda.",
  "imageUrl": "https://www.livemint.com/lm-img/img/2026/08/23/1600x900/logo/pexels-photo-2199293_1787507447241_1787507457886_19405a92-e2ee-46c8-93de-059a7a7fb463.jpeg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek. |
| `author` | object | Byline (name, URL) (article mode only). |
| `keywords` | array | Topic tags (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `imageUrl` | string | Lead image URL (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
