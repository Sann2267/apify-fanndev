# Moneycontrol Scraper

Extract full article text or the newest headlines from Moneycontrol, India's leading financial and markets news portal — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, author, and publish/update dates
- Also fetches the newest headlines from the site's news feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's news feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## A note on Moneycontrol PRO

Moneycontrol has a paid "PRO" tier (analyst research reports under
`/news/business/moneycontrol-research/...`). Those specific articles are
genuinely paywalled by Moneycontrol — only a one-sentence teaser is
publicly available, so `articleBody` will be missing for that small
subset of URLs. Regular news, markets, and business articles (the vast
majority of the site) are fully free and return complete article text.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.moneycontrol.com/news/business/companies/apple-to-ship-10-million-foldable-iphones-in-year-one-idc-says-14016311.html"
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
  "_input": "https://www.moneycontrol.com/news/business/companies/apple-to-ship-10-million-foldable-iphones-in-year-one-idc-says-14016311.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:17:24Z",
  "@type": "NewsArticle",
  "headline": "Apple to ship 10 million foldable iPhones in year one, IDC Says",
  "description": "The premium-tier phone expected to debut in September will be Apple's first foldable device and is widely seen as likely to spark a revival for a category pioneered by Samsung Electronics Co. seven years ago.",
  "keywords": "Apple, Apple new foldable iPhone, foldable iPhone, IDC, 10 million foldable iPhones",
  "articleSection": "Business",
  "url": "https://www.moneycontrol.com/news/business/companies/apple-to-ship-10-million-foldable-iphones-in-year-one-idc-says-14016311.html",
  "image": ["https://images.moneycontrol.com/static-mcnews/2026/05/20260515055328_apple-ind.jpg?impolicy=website&width=1600&height=900"],
  "datePublished": "2026-08-26T22:24:26+05:30",
  "dateModified": "2026-08-26T22:24:28+05:30",
  "articleBody": "Apple Inc.'s anticipated foldable iPhone will rescue that segment of the smartphone market from decline and deliver more than 10 million shipments in its first year, researcher IDC predicts. ... 4 more paragraphs",
  "author": {"@type": "Person", "url": "https://www.moneycontrol.com/author/bloomberg-21811/", "name": "Bloomberg"},
  "publisher": {"@type": "NewsMediaOrganization", "name": "Moneycontrol", "url": "https://www.moneycontrol.com"}
}
```

A Moneycontrol PRO article looks the same but without `articleBody` and with `"isAccessibleForFree": "False"` present:

```json
{
  "_input": "https://www.moneycontrol.com/news/business/moneycontrol-research/ceat-growth-engines-rev-up-margins-play-catch-up-14015566.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:17:25Z",
  "headline": "CEAT: Growth engines rev up, margins play catch-up",
  "description": "Strong pricing, premium products, and market-share gains strengthen outlook while Camso adds a new growth leg",
  "isAccessibleForFree": "False",
  "keywords": "CEAT, CEAT Q1, MCPro, Moneycontrol Research, Stock Recommendation, Q1 FY 2027 Earnings, Result analysis",
  "datePublished": "2026-08-26T08:55:41+05:30"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:17:14Z",
  "title": "‘Wall of water came thundering down’: Nepal labourer recounts flood horror, saved by mango tree",
  "link": "https://www.moneycontrol.com/news/world/wall-of-water-came-thundering-down-nepal-labourer-recounts-flood-horror-saved-by-mango-tree-14016316.html",
  "pubDate": "2026-08-26T22:46:52+05:30",
  "keywords": "nepal, floods, mango tree",
  "image": "https://images.moneycontrol.com/static-mcnews/2026/08/20260826073113_Nepalflood.png"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode; missing on paywalled Moneycontrol PRO articles). |
| `description` | string | Article summary/dek. |
| `keywords` | string | Comma-separated topic tags. |
| `articleSection` | string | Section name (article mode only). |
| `author` | object | Byline — wire-service name (e.g. "Bloomberg") or the generic staff byline "Moneycontrol News" (article mode only). |
| `isAccessibleForFree` | string | Only present (as the string `"False"`) on paywalled Moneycontrol PRO articles. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
