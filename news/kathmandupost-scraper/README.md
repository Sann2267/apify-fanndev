# The Kathmandu Post Scraper

Extract full article text or the newest headlines from The Kathmandu Post (kathmandupost.com), Nepal's leading English-language national newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, category, publish/update dates, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's `/rss` feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://kathmandupost.com/national/2026/08/25/nepal-us-plan-high-level-visits-and-other-engagements-next-year"
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
  "_input": "https://kathmandupost.com/national/2026/08/25/nepal-us-plan-high-level-visits-and-other-engagements-next-year",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-25T17:55:02Z",
  "headline": "Nepal, US plan high-level visits and other engagements next year",
  "description": "After 80 years, Nepal seeks to foster its US partnership on three strategic pillars—digital transformation, clean energy and widespread human capital.",
  "articleBody": "Nepal and the United States are planning high-level visits and a series of other engagements next year as the two countries mark the 80th anniversary...",
  "author": "Anil Giri",
  "publisher": "The Kathmandu Post",
  "category": "national",
  "publishedAt": "August 25, 2026",
  "updatedAt": "August 25, 2026 20:48",
  "location": "Kathmandu",
  "image": {
    "@type": "ImageObject",
    "url": "https://assets-cdn.kathmandupost.com/uploads/source/news/2026/third-party/HHOx6S3aMAAtp8H-1787668692.jpg",
    "height": 800,
    "width": 800
  }
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-25T17:51:49Z",
  "title": "Nepal, US plan high-level visits and other engagements next year",
  "link": "https://kathmandupost.com/national/2026/08/25/nepal-us-plan-high-level-visits-and-other-engagements-next-year",
  "description": "After 80 years, Nepal seeks to foster its US partnership on three strategic pillars—digital transformation, clean energy and widespread human capital."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-html`, `S2-rss`, or `none` on failures). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary/deck (article mode: ld+json description; latest mode: RSS teaser). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline name, when signed (article mode only; `null` on unsigned/editorial pieces). |
| `publisher` | string | Always `"The Kathmandu Post"` (article mode only). |
| `category` | string | Section name taken from the URL, e.g. `"national"`, `"world"`, `"money"`, `"opinion"`. |
| `publishedAt` / `updatedAt` | string | Raw upstream date strings as shown on the page (no machine-parseable ISO date is available upstream). |
| `location` | string | Dateline city (e.g. `"Kathmandu"`), when present. |
| `image` | object | Lead image object (article mode). |
| `link` | string | Article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or nonexistent article — this site returns HTTP 200 for missing articles, not a real 404, so the actor detects it from the page content instead).
