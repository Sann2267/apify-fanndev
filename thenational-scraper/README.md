# The National (UAE) Scraper

Extract full article text or the newest headlines from The National (thenationalnews.com), a leading UAE English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline(s), section, keywords, publish/update dates, lead image
- Strong UAE and wider Gulf coverage alongside US/international news and sport
- Also fetches the newest headlines (with lead image) from the site's news sitemap without visiting each article individually
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
    "https://www.thenationalnews.com/news/uae/2026/08/23/bidders-swoop-in-to-make-bids-on-prized-falcons-at-abu-dhabis-adihex-auction/"
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
  "_input": "https://www.thenationalnews.com/news/uae/2026/08/23/bidders-swoop-in-to-make-bids-on-prized-falcons-at-abu-dhabis-adihex-auction/",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T01:31:33Z",
  "headline": "Bidders swoop in to make bids on prized falcons at Abu Dhabi's Adihex auction",
  "description": "Birds sell for big money at event held before Abu Dhabi International Hunting and Equestrian Exhibition",
  "articleBody": "Falcon merchants and breeders were bidding huge sums at an auction in Abu Dhabi on Sunday evening, with birds of prey being bought for hundreds of thousands of dirhams...",
  "articleSection": null,
  "datePublished": "2026-08-23T17:45:58.967Z",
  "dateModified": "2026-08-23T17:45:58.967Z",
  "author": "The National",
  "keywords": ["story", "standard", "UAE", "Abu Dhabi"],
  "image": "https://www.thenationalnews.com/resizer/v2/XJLDKG4235FE7LRTL7FYUICDKI.jpg?auth=..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:31:14Z",
  "title": "Bidders swoop in to make bids on prized falcons at Abu Dhabi's Adihex auction",
  "link": "https://www.thenationalnews.com/news/uae/2026/08/23/bidders-swoop-in-to-make-bids-on-prized-falcons-at-abu-dhabis-adihex-auction/",
  "publicationDate": "2026-08-23T17:45:58.967Z",
  "imageUrl": "https://www.thenationalnews.com/resizer/v2/XJLDKG4235FE7LRTL7FYUICDKI.jpg?auth=..."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary, when the site provides one (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline(s), comma-joined when multiple contributors are credited (article mode only). |
| `keywords` | array | Tag keywords (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
