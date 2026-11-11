# The Tribune (India) Scraper

Extract full article text or the newest headlines from The Tribune — the major North India English daily based in Chandigarh — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines from the site's recent-articles sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's recent-articles sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.tribuneindia.com/news/india/bjp-leaders-son-accused-of-abetting-wifes-suicide-in-surat/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the recent-articles sitemap. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.tribuneindia.com/news/world/nepal-floods-rsps-kharel-thanks-india-says-assistance-from-neighbours-significant-essential/",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:13:41Z",
  "@type": "NewsArticle",
  "inLanguage": "en",
  "keywords": [
    "#Nuwakot",
    "Flash Floods",
    "Glacial lake outburst",
    "international assistance",
    "Jagdish Kharel",
    "Nepal Floods",
    "pm modi",
    "Rasuwa",
    "Relief action",
    "Rsp spokesperson"
  ],
  "headline": "Nepal Floods: RSPs Kharel thanks India, says assistance from neighbours significant, essential - The Tribune",
  "datePublished": "2026-08-26T22:43:01+05:30",
  "dateModified": "2026-08-26T22:43:01+05:30",
  "description": "Nepal's RSP spokesperson Jagdish Kharel on Wednesday thanked India and Prime Minister Narendra Modi for extending support to the flood-hit country, saying assistance from India and other neighbouring countries would be 'very significant and essential' at this critical juncture.",
  "articleBody": "Kathmandu [Nepal], August 26 (ANI): Nepal's RSP spokesperson Jagdish Kharel on Wednesday thanked India and Prime Minister Naren ... (full article text)",
  "author": { "@type": "Person", "name": "PTI", "url": "https://www.tribuneindia.com/author/pti/7" },
  "publisher": { "@type": "NewsMediaOrganization", "name": "The Tribune", "logo": { "@type": "ImageObject", "url": "...", "width": 600, "height": 60 } },
  "image": { "@type": "ImageObject", "url": "...", "height": 675, "width": 1200 },
  "articleSection": "World",
  "isAccessibleForFree": true
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:13:21Z",
  "title": "Nepal Floods: RSP's Kharel thanks India, says assistance from neighbours 'significant, essential'",
  "link": "https://www.tribuneindia.com/news/world/nepal-floods-rsps-kharel-thanks-india-says-assistance-from-neighbours-significant-essential/",
  "lastmod": "2026-08-26T22:43:01+05:30"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode carries a `" - The Tribune"` SEO title-tail; `title` in latest mode does not). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek (article mode only). |
| `keywords` | array | Topic tags (article mode only). On some articles this is a single-item array duplicating the headline rather than real tags — a CMS quirk. |
| `author` | object | Byline — a single `Person` object (article mode only), often a wire-service credit like "PTI" or "ANI" rather than a staff reporter. |
| `publisher` | object | Publisher `NewsMediaOrganization` object (article mode only). |
| `articleSection` | string | Section name, e.g. "India", "World" (article mode only). |
| `isAccessibleForFree` | boolean | Paywall metering flag — observed `true` on every sampled article (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `lastmod` | string | Publication/update timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
