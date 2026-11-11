# Millennium Post Scraper

Extract full article text or the newest headlines from Millennium Post (India, Delhi/Kolkata) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, section, byline, and publish/update dates
- Also fetches the newest headlines from the Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.millenniumpost.in/business/india-fastest-growing-major-economy-offers-strong-investment-opportunities-sitharaman-673644"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the Google News sitemap. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.millenniumpost.in/business/india-fastest-growing-major-economy-offers-strong-investment-opportunities-sitharaman-673644",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T06:35:21Z",
  "@type": "NewsArticle",
  "author": {
    "@type": "Person",
    "name": "MPost",
    "url": "https://www.millenniumpost.in/team.mp",
    "jobTitle": "Editor"
  },
  "datePublished": "2026-08-26T11:15:51+05:30",
  "dateModified": "2026-08-26T11:15:51+05:30",
  "keywords": "",
  "alternativeHeadline": "India fastest-growing major economy, offers strong investment opportunities: Sitharaman",
  "inLanguage": "en",
  "headline": "India fastest-growing major economy, offers strong investment opportunities: Sitharaman",
  "image": {
    "@type": "ImageObject",
    "contentUrl": "https://www.millenniumpost.in/h-upload/2026/08/26/1053295-pti08262026000024b.webp",
    "height": 900,
    "width": 1500
  },
  "articleSection": "Business",
  "articleBody": "Washington: India today stands as the fastest-growing major economy in the world and offers a combination of scale, sustained growth, a young population, expanding consumption and rapidly deepening capital markets ... [3,039 characters total]",
  "description": "Washington: India today stands as the fastest-growing major economy in the world and offers a combination of scale, sustained growth ...",
  "publisher": {
    "@type": "Organization",
    "name": "MillenniumPost",
    "url": "https://www.millenniumpost.in"
  }
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T06:35:13Z",
  "title": "India fastest-growing major economy, offers strong investment opportunities: Sitharaman",
  "link": "https://www.millenniumpost.in/business/india-fastest-growing-major-economy-offers-strong-investment-opportunities-sitharaman-673644",
  "pubDate": "2026-08-26T11:15:51+05:30",
  "image": "https://www.millenniumpost.in/h-upload/2026/08/26/1053295-pti08262026000024b.webp"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` or `S2-sitemap`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek (article mode only, sometimes truncated with `...` by the CMS). |
| `author` | object | Byline (article mode only) — always the generic `"MPost"` desk credit on this outlet, not a named reporter. |
| `articleSection` | string | Section name (article mode only), e.g. Business, Nation, Bengal. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode), IST (`+05:30`). |
| `pubDate` | string | Publication timestamp (latest mode), IST (`+05:30`). |
| `link` | string | The article URL (latest mode). |
| `image` | object / string | Lead image (full object in article mode, plain URL string in latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
