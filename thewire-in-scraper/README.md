# The Wire (India) Scraper

Extract full article text or the newest headlines from The Wire (India) — the independent digital-native investigative/analysis outlet at thewire.in — no account or subscription needed.

> Note: this is The Wire, India (`thewire.in`) — an independent Indian news and analysis publication. Not related to any similarly-named outlet in another country.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, byline, publisher, and publish/update dates
- Also fetches the newest headlines from The Wire's sitemap without visiting each article individually
- Accepts either the public `thewire.in` article URL or the `m.thewire.in` URL directly
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads The Wire's sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://thewire.in/politics/bjp-leaders-stance-pellet-gun-use-delhi"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the sitemap. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://thewire.in/politics/bjp-leaders-stance-pellet-gun-use-delhi",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:20:34Z",
  "@type": "NewsArticle",
  "mainEntityOfPage": "https://thewire.in/politics/bjp-leaders-stance-pellet-gun-use-delhi",
  "url": "https://m.thewire.in/article/politics/bjp-leaders-stance-pellet-gun-use-delhi",
  "keywords": "cjp,Cockroach Janata Party,Jantar Mantar,JP Nadda,Kiren Rijiju,pellet guns,Rahul Gandhi",
  "headline": "'No Shots Fired' to 'SC Committee Probing': BJP Ministers Fine Tune Remarks on Pellet Gun Use in Delhi",
  "datePublished": "2026-08-22T08:33:08+05:30",
  "dateModified": "2026-08-22T08:33:08+05:30",
  "description": "While Union minister J.P. Nadda along with his cabinet colleagues had denied both inside and outside parliament that shots were fired on protesters...",
  "articleBody": "New Delhi: As leader of opposition in the Lok Sabha Rahul Gandhi on Friday (August 21) staged a dharna outside the New Delhi Deputy Commissioner of Police's office to get the police to register an FIR against the use of pellet guns...",
  "author": { "@type": "Person", "name": "Sravasti Dasgupta", "url": "https://m.thewire.in/author/sravasti-dasgupta" },
  "publisher": { "@type": "Organization", "name": "The Wire", "logo": { "@type": "ImageObject", "url": "https://m.thewire.in/..." } },
  "image": { "@type": "ImageObject", "url": "https://cms.thewire.in/wp-content/uploads/2026/08/PTI08_21_2026_000445B-scaled.jpg", "height": 675, "width": 1200 }
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:20:19Z",
  "title": "The Youth Movement Has Amply Shown that the Modi-Shah Regime Has Lost the Popular Mandate",
  "link": "https://m.thewire.in/article/politics/the-youth-movement-has-amply-shown-that-the-modi-shah-regime-has-lost-the-popular-mandate",
  "pubDate": "2026-08-21T12:32:00+05:30",
  "image": "https://cms.thewire.in/wp-content/uploads/2024/03/Screenshot-2024-03-12-at-5.55.44-PM.png"
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
| `keywords` | string | Comma-separated topic tags (article mode only). |
| `author` | object | Byline (article mode only) — a Person object with name and profile URL. |
| `publisher` | object | Publisher organization (article mode only). |
| `mainEntityOfPage` | string | The canonical public `thewire.in` URL (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `image` | object / string | Lead image (a full object in article mode, a plain URL string in latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
