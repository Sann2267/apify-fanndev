# Free Press Kashmir Scraper

Extract full article text or the newest headlines from Free Press Kashmir (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, publisher, section, and publish/update dates
- Also fetches the newest headlines from the site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

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
    "https://freepresskashmir.news/2026/08/26/jk-accelerates-digital-land-records-integration-with-agristack-for-smarter-farmer-services/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the site-wide RSS feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://freepresskashmir.news/2026/08/25/kashmirs-cancer-care-chapter-2-the-waiting-ward/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T06:37:24Z",
  "headline": "Kashmir's cancer care: chapter 2 — the waiting ward",
  "description": "Families describe delayed scans, shifting surgery dates and chemotherapy that never came as they struggled to understand how their loved ones' treatment had changed. ...",
  "articleBody": "Families describe delayed scans, shifting surgery dates and chemotherapy that never came as they struggled to understand how their loved ones' treatment had changed.\n\nSabia's father looked healthy again. His liver, once riddled with tumours, had healed. ...",
  "author": "Al-Misda Masoom",
  "publisher": "Free Press Kashmir",
  "articleSection": "Health, In Depth, Special Report, cancer patients Kashmir, cancer treatment delays, healthcare in Kashmir, Kashmir cancer care, medical transparency, SKIMS Srinagar",
  "image": "https://cdn.freepresskashmir.news/wp-content/uploads/2026/08/hospital-ward-waiting-patient-ICU.jpg",
  "datePublished": "2026-08-25T18:53:16+05:30",
  "dateModified": "2026-08-25T22:10:33+05:30"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T06:37:08Z",
  "title": "Mamdani opposes New York event featuring Hindu nationalist RSS leader",
  "link": "https://freepresskashmir.news/2026/08/26/mamdani-opposes-new-york-event-featuring-hindu-nationalist-rss-leader/",
  "guid": "https://freepresskashmir.news/?p=139947",
  "pubDate": "Wed, 26 Aug 2026 06:19:00 +0000",
  "description": "<div><img width=\"300\" height=\"169\" src=\"https://cdn.freepresskashmir.news/wp-content/uploads/2026/08/Mamdani-300x169.jpg\" ... /></div><p>New York City Mayor Zohran Mamdani said he opposes an upcoming Manhattan rally planned for Mohan Bhagwat, leader of the Rashtriya Swayamsevak Sangh (RSS) ...",
  "author": "News Desk",
  "category": "International"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary (article mode: plain-text meta description; latest mode: an HTML fragment with a lead image and teaser paragraph, as published in the feed). |
| `author` | string | Byline — a named reporter or the "News Desk" credit. |
| `publisher` | string | Publisher name (article mode only). |
| `articleSection` | string | Comma-separated categories and tags (article mode only). |
| `image` | string | Lead image URL (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `category` | string | Section/category (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
