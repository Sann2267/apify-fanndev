# DNA India Scraper

Extract full article text or the newest headlines from DNA India (Daily News & Analysis) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, byline, lead image, and publish/update dates
- Also fetches the newest headlines from the Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads DNA India's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.dnaindia.com/india/report-india-sends-10-tonnes-of-relief-material-and-essential-medicines-to-nepal-amid-deadly-flash-flood-3219305"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.dnaindia.com/india/report-india-sends-10-tonnes-of-relief-material-and-essential-medicines-to-nepal-amid-deadly-flash-flood-3219305",
  "_source": "S1-flight",
  "_scrapedAt": "2026-08-26T17:21:56Z",
  "@type": "NewsArticle",
  "keywords": "Nepal, S Jaishankar, Nepal Flash Flood, Indian Air Force, PM Modi, Balen Shah, india nepal ties, india nepal relations",
  "inLanguage": "en",
  "headline": "India sends 10 tonnes of relief material to Nepal amid deadly flash flood",
  "url": "https://www.dnaindia.com/india/report-india-sends-10-tonnes-of-relief-material-and-essential-medicines-to-nepal-amid-deadly-flash-flood-3219305",
  "image": {
    "@type": "ImageObject",
    "url": "https://cdn.dnaindia.com/sites/default/files/styles/half/public/2026/08/26/2757165-india-help-to-nepal.jpg",
    "height": "720",
    "width": "1280"
  },
  "datePublished": "2026-08-26T22:32:00+05:30",
  "dateModified": "2026-08-26T22:37:43+05:30",
  "author": [{ "@type": "Person", "name": "ANI", "url": "https://www.dnaindia.com/authors/ani" }],
  "publisher": {
    "@type": "NewsMediaOrganization",
    "name": "DNA India",
    "url": "https://www.dnaindia.com/",
    "sameAs": ["https://www.facebook.com/dnaindia", "https://x.com/dna", "... 3 more"]
  },
  "description": "In a post on X, External Affairs Minister S Jaishankar said India stands with Nepal and its people in meeting the challenge.",
  "articleBody": "India has dispatched 10 tonnes of Humanitarian Assistance and Disaster Relief (HADR) along with essential medicines to support Nepal, which is dealing with devastating floods. In a post on X, External Affairs Minister S Jaishankar said India stands with Nepal and its people in meeting the challenge. ... [full text, 2,500+ characters]"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:21:27Z",
  "title": "India sends 10 tonnes of relief material to Nepal amid deadly flash flood",
  "link": "https://www.dnaindia.com/india/report-india-sends-10-tonnes-of-relief-material-and-essential-medicines-to-nepal-amid-deadly-flash-flood-3219305",
  "publication_date": "2026-08-26T22:37:43+05:30",
  "keywords": "Nepal, S Jaishankar, Nepal Flash Flood, Indian Air Force, PM Modi, Balen Shah, india nepal ties, india nepal relations"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek (article mode only). |
| `keywords` | string | Comma-separated topic tags. |
| `author` | array | Byline — a list of `Person` objects (article mode only). |
| `image` | object | Lead image URL and dimensions (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `publication_date` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
