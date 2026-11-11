# Saudi Gazette Scraper

Extract full article text or the newest headlines from Saudi Gazette (saudigazette.com.sa), Saudi Arabia's oldest English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, publish/update dates, lead image
- Works across news, opinion, and wire-service articles alike
- Automatically cleans up stray HTML entities the site embeds directly in its data
- Also fetches the newest headlines from the site's news sitemap without visiting each article individually
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
    "https://saudigazette.com.sa/article/663865/discover-saudi/ancient-stone-tombs-trace-centuries-of-human-movement-across-northwest-arabia"
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
  "_input": "https://saudigazette.com.sa/article/663865/discover-saudi/ancient-stone-tombs-trace-centuries-of-human-movement-across-northwest-arabia",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T02:09:53Z",
  "headline": "Ancient stone tombs trace centuries of human movement across northwest Arabia",
  "description": "Architectural stone pendant tombs deliberately patterned across AlUla, Khaybar and Tayma provide evidence of ancient human settlement in the northwestern Arabian Peninsula.",
  "articleBody": "KHAYBAR — Architectural stone pendant tombs deliberately patterned across AlUla, Khaybar and Tayma provide evidence of ancient human settlement in the northwestern Arabian Peninsula.\n\nDensely distributed across volcanic harrats, along valleys and near oases and water sources, the structures represent some of the region's most prominent archaeological evidence of early settlement...",
  "category": "discover saudi",
  "author": "Saudi Gazette",
  "publisher": "Saudi Gazette",
  "datePublished": "2026-08-19T13:20:22+03:00",
  "dateModified": "2026-08-19T13:20:22+03:00",
  "image": "https://saudigazette.com.sa/saudigazette/uploads/images/2026/08/19/2752766.webp",
  "keywords": "Saudi Arabia, AlUla, Khaybar and Tayma, Royal Commission for AlUla, ancient, tomb stones, Bronze Age, archeology, "
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T02:10:04Z",
  "title": "Saudi Arabia secures silver and bronze at World Masters Athletics Championships",
  "link": "https://saudigazette.com.sa/article/664069/saudi-arabia/saudi-arabia-secures-silver-and-bronze-at-world-masters-athletics-championships",
  "publicationDate": "2026-08-25T23:48:57+03:00",
  "keywords": ["SAUDI ARABIA"]
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
| `category` | string | Section/category (article mode only). |
| `author` | string | Byline — staff name, `"Agencies"` for wire copy, or the columnist's name for opinion pieces (article mode only). |
| `publisher` | string | Publisher name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode only). |
| `keywords` | string or array | Tag keyword(s). |
| `link` | string | Article URL (latest mode only). |
| `publicationDate` | string | Publication timestamp (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
