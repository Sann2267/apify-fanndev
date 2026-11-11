# The Statesman (India) Scraper

Extract full article text or the newest headlines from The Statesman — the New Delhi-based national English-language Indian daily — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, section, byline, keywords, and publish/update dates
- Also fetches the newest headlines from the site directly, without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's list of newest stories and returns them directly.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.thestatesman.com/india/bihar-on-alert-amid-possibility-of-flash-flood-in-gandak-river-1503631581.html"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.thestatesman.com/india/bihar-on-alert-amid-possibility-of-flash-flood-in-gandak-river-1503631581.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:59:09Z",
  "@type": "newsarticle",
  "inLanguage": "en",
  "url": "https://www.thestatesman.com/india/bihar-on-alert-amid-possibility-of-flash-flood-in-gandak-river-1503631581.html",
  "articleBody": "Bihar has been put on high alert following the possibility of a flash flood in the Gandak River after a sudden surge in water flow is expected from its upper catchment area in Nepal. Authorities have been warned of a possible flash-flood wave of up to three metres and have stepped up preparedness measures in districts along the river. ... (full article text, 356 words)",
  "articleSection": "India",
  "headline": "Bihar on alert amid possibility of flash flood in Gandak river",
  "description": "Bihar has been put on high alert following the possibility of a flash flood in the Gandak River after a sudden surge in water flow is expected from its upper catchment area in Nepal.",
  "datePublished": "2026-08-26T23:09:59+05:30",
  "dateModified": "2026-08-26T23:09:59+05:30",
  "publisher": { "@type": "Organization", "name": "thestatesman", "logo": { "@type": "ImageObject", "url": "https://www.thestatesman.com/wp-content/themes/statesmantheme/images/the-statesman-logo-new.png", "width": "280", "height": "64" } },
  "author": { "@type": "Person", "name": "Statesman News Service", "url": "https://www.thestatesman.com/author/authorthestatesman-com" },
  "image": { "@type": "ImageObject", "url": "https://www.thestatesman.com/wp-content/uploads/2026/08/IMG_4695.webp", "width": "1200", "height": "800" },
  "keywords": ["Bihar", "Gandak river", "Nepal floods"],
  "wordCount": 356,
  "commentCount": 0
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:59:01Z",
  "title": "Bihar on alert amid possibility of flash flood in Gandak river",
  "link": "https://www.thestatesman.com/india/bihar-on-alert-amid-possibility-of-flash-flood-in-gandak-river-1503631581.html",
  "publicationDate": "2026-08-26T23:09:59+05:30",
  "keywords": ["Bihar", "Gandak river", "Nepal floods"]
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
| `keywords` | array | Topic tags. |
| `author` | object | Byline — a single person object (article mode only). Every article seen so far carries the newsroom byline "Statesman News Service" rather than an individual reporter's name. |
| `publisher` | object | Publisher organization object (article mode only). |
| `articleSection` | string | Section name, e.g. "India", "Sports", "Bollywood" (article mode only). |
| `wordCount` / `commentCount` | number | Article word count / comment count as reported by the site (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or invalid article).

## Notes

- Latest mode returns up to 100 of the newest published stories site-wide (not filtered by section).
- No paywall was observed on any sampled article — full text was available every time.
