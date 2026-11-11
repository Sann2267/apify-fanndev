# Oman Observer Scraper

Extract full article text or the newest headlines from Oman Observer (omanobserver.om), Oman's English-language national newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully open-access site with no paywall found on any sampled article
- Full article text included, not just a summary — headline, description, byline, keywords, publish/modified/created dates, all pulled straight from the page's own structured data
- Also fetches the newest headlines by scanning the homepage, no unreliable RSS/sitemap dependency (the site doesn't have a working one)
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and reads the page's `NewsArticle` structured-data block, which carries the full article body directly — no fragile HTML-selector scraping needed for the text itself.
3. In latest mode, the actor scans the homepage for article links and returns the newest ones, sorted by article ID (which correlates with publish order).
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.omanobserver.om/article/1195068/oman/community/oman-iran-discuss-temporary-strait-of-hormuz-corridor"
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
  "_input": "https://www.omanobserver.om/article/1195068/oman/community/oman-iran-discuss-temporary-strait-of-hormuz-corridor",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-25T17:53:47Z",
  "headline": "Oman, Iran discuss temporary Strait of Hormuz corridor",
  "description": "Muscat: Sayyid Badr bin Hamad al Busaidi, Foreign Minister paid a working visit to the Islamic Republic of Iran on Tuesday...",
  "articleBody": "Muscat: Sayyid Badr bin Hamad al Busaidi, Foreign Minister paid a working visit to the Islamic Republic of Iran on Tuesday, where he held constructive consultations with his Iranian counterpart Dr Seyed Abbas Araghchi...",
  "keywords": "Oman,,Iran,discuss,temporary,Strait,of,Hormuz,corridor",
  "author": "Observer Web Team",
  "publisher": "Oman Observer",
  "copyrightHolder": "Oman Observer",
  "datePublished": "2026-08-25T15:50:24+04:00",
  "dateModified": "2026-08-25T20:31:34+04:00",
  "dateCreated": "2026-08-25T15:50:24+04:00",
  "image": { "@type": "ImageObject", "url": "https://www.omanobserver.om/omanobserver/uploads/images/2026/08/25/thumbs/600x600/3492684.jpg", "height": 600, "width": 600 },
  "thumbnailUrl": "https://www.omanobserver.om/omanobserver/uploads/images/2026/08/25/thumbs/600x600/3492684.jpg",
  "inLanguage": "en",
  "url": "https://www.omanobserver.om/article/1195068/oman/community/oman-iran-discuss-temporary-strait-of-hormuz-corridor",
  "urlCategoryPath": ["oman", "community"]
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-html-listing",
  "_scrapedAt": "2026-08-25T17:54:09Z",
  "title": "Al Hamra records Oman's highest rainfall at 28mm",
  "link": "https://www.omanobserver.om/article/1195101/oman/weather/al-hamra-records-omans-highest-rainfall-at-28mm",
  "articleId": 1195101,
  "urlCategoryPath": ["oman", "weather"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` or `S2-html-listing`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Article summary/lede (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `keywords` | string | CMS-autogenerated comma-joined keyword string — the headline's words, not curated tags (article mode only). |
| `author` | string | Byline name, often the generic "Observer Web Team" (article mode only). |
| `publisher` / `copyrightHolder` | string | Always `"Oman Observer"` (article mode only). |
| `datePublished` / `dateModified` / `dateCreated` | string | ISO-8601 timestamps (article mode only). |
| `image` | object | Lead image `{ url, width, height }` (article mode only). |
| `thumbnailUrl` | string | Thumbnail image URL (article mode only). |
| `url` | string | The article's true canonical URL, resolved by numeric ID (article mode only). |
| `urlCategoryPath` | array | Best-effort category/subcategory path segments parsed from the URL, e.g. `["business", "energy"]`. |
| `link` | string | Article URL (latest mode). |
| `articleId` | integer | Numeric article ID — the only part of the URL the server uses for routing. Latest-mode results are sorted newest-first by this value. |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or invalid article ID).
