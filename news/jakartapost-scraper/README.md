# The Jakarta Post Scraper

Extract full article text or the newest headlines from The Jakarta Post (thejakartapost.com), Indonesia's leading English-language newspaper for expats, business, and international audiences — no account or subscription needed.

## Why use this actor

- No account or login required — the full article body is present in the page even on nominally "premium" articles (soft, client-side paywall only)
- Full article text included, not just a summary — headline, description, byline, publish/update dates, lead image
- Also fetches the newest headlines from the Google News sitemap without visiting each article individually
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
    "https://www.thejakartapost.com/indonesia/2026/08/24/police-crack-down-on-land-burning-in-kalimantan"
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
  "_input": "https://www.thejakartapost.com/indonesia/2026/08/24/police-crack-down-on-land-burning-in-kalimantan",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-23T23:32:50Z",
  "headline": "Police crack down on land burning in Kalimantan",
  "description": "Police have named 72 suspects in their crackdown on deliberate land burning...",
  "articleBody": "Police have named 72 suspects in their crackdown on deliberate land burning after President Prabowo Subianto ordered over the weekend a rapid response...",
  "datePublished": "2026-08-23T19:41:43+07:00",
  "dateModified": "2026-08-23T21:24:47+07:00",
  "author": "Radhiyya Indra",
  "image": "https://img.jakpost.net/c/2026/08/18/2026_08_18_178783_1787040910._medium.jpg",
  "_paywalled": true
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-23T23:32:49Z",
  "title": "Police crack down on land burning in Kalimantan",
  "link": "https://www.thejakartapost.com/indonesia/2026/08/24/police-crack-down-on-land-burning-in-kalimantan",
  "publicationDate": "2026-08-24T06:23:32+07:00"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode only). |
| `_paywalled` | boolean | `true` when the site flags the article as premium. **Full text is still returned** — this site's paywall is enforced client-side, not server-side. |
| `publicationDate` | string | Publication timestamp (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
