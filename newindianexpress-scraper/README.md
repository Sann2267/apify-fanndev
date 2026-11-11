# New Indian Express Scraper

Extract full article text or the newest headlines from The New Indian Express (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines (with full body text) from the site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's `stories.rss` feed and returns the newest stories, already including full body text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.newindianexpress.com/states/karnataka/2026/Aug/26/autopsy-report-reveals-two-dead-in-karnatakas-hanur-incident-shot-at-close-range"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the site-wide feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.newindianexpress.com/states/karnataka/2026/Aug/26/autopsy-report-reveals-two-dead-in-karnatakas-hanur-incident-shot-at-close-range",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T02:14:50Z",
  "@type": "NewsArticle",
  "headline": "Autopsy report reveals two dead in Karnataka's Hanur incident shot at close range",
  "description": "The autopsy report of Anthonyswamy also recorded a shotgun entry wound deep in the abdominal cavity. ",
  "articleBody": "MYSURU: Two of the three victims in the Hanur shooting incident were shot from close range, stated the postmortem reports, raising fresh questions over the circumstances surrounding the firing and their deaths. ... (full plain-text article, ~1,850 characters on this sample)",
  "keywords": "",
  "articleSection": "Karnataka",
  "author": [
    { "@type": "Person", "givenName": "BK Lakshmikantha", "name": "BK Lakshmikantha", "url": "https://www.newindianexpress.com/author/bk-lakshmikantha" }
  ],
  "publisher": { "@type": "NewsMediaOrganization", "name": "The New Indian Express", "url": "https://www.newindianexpress.com" },
  "image": [
    { "@type": "ImageObject", "url": "https://cf-images.assettype.com/newindianexpress/2026-08-26/c80yx02b/ANI_20260618052733.png?w=1200&h=675&auto=format%2Ccompress&fit=max&enlarge=true", "width": "1200", "height": "675" },
    "... 2 more crops"
  ],
  "datePublished": "2026-08-26T02:02:29Z",
  "dateModified": "2026-08-26T02:02:24Z",
  "inLanguage": "en"
}
```

**Latest headlines mode** — one record per headline (truncated here for readability):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:14:50Z",
  "title": "TN govt to retain, repurpose Parandur land",
  "link": "https://www.newindianexpress.com/states/tamil-nadu/2026/Aug/26/tn-govt-to-retain-repurpose-parandur-land",
  "guid": "e1a2555a-b15f-46d3-b9ae-edc6a6617c9f",
  "pubDate": "Wed, 26 Aug 2026 02:07:43 +0000",
  "description": null,
  "category": "Tamil Nadu",
  "author": "C Shivakumar",
  "authorUrl": "/api/author/1872808",
  "keywords": "Industries Minister S Keerthana,Parandur airport project",
  "image": "https://cf-images.assettype.com/newindianexpress/2026-08-25/av08ueio/Govt-to-retain-repurpose.jpg",
  "thumbnail": "https://cf-images.assettype.com/newindianexpress/2026-08-25/av08ueio/Govt-to-retain-repurpose.jpg?w=280",
  "contentEncoded": "<p>CHENNAI: The fate of 1,802 acres acquired for the now-scrapped Parandur airport project emerged as a fresh flashpoint in the Tamil Nadu Assembly on Tuesday ... (full article body as HTML, ~3,600 characters on this sample)</p>"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `contentEncoded` | string | Full article body as HTML markup (latest mode only — this feed carries full text, not just headlines). |
| `description` | string | Article summary/dek (article mode; usually empty in latest mode on this feed). |
| `keywords` | string | Comma-separated topic tags. Often empty in article mode; more reliably populated in latest mode. |
| `author` | array / string | Byline — array of named-reporter objects in article mode, a plain name string in latest mode. |
| `articleSection` / `category` | string | Section name (e.g. "Karnataka", "Tamil Nadu"). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `image` | array / string | Lead image — list of crop variants in article mode, a single URL in latest mode. |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article slug).
