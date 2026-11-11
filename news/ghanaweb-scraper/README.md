# GhanaWeb Scraper

Extract full article text or the newest headlines from GhanaWeb (ghanaweb.com), Ghana's largest English-language news portal — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, category, publish/modified dates, and a reconstructed clean-paragraph body
- Byline detail most scrapers miss: staff news pieces expose GhanaWeb's internal reporter/editor initials signature, while Opinions/Features pieces expose the named columnist (`bylineLabel`/`bylineName`)
- Also fetches the newest headlines straight from the site's Google News sitemap (updates in near-real-time) without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads GhanaWeb's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.ghanaweb.com/GhanaHomePage/NewsArchive/Mahama-Ayariga-Dr-Zanetor-vetting-rescheduled-to-August-27-2049369"
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
  "_input": "https://www.ghanaweb.com/GhanaHomePage/NewsArchive/Mahama-Ayariga-Dr-Zanetor-vetting-rescheduled-to-August-27-2049369",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T09:12:03Z",
  "articleId": "2049369",
  "headline": "Mahama Ayariga, Dr Zanetor vetting rescheduled to August 27",
  "description": "The Parliamentary Appointments Committee has rescheduled the vetting of Mahama Ayariga and Dr Zanetor Agyeman-Rawlings to Thursday, August 27, 2026.",
  "articleBody": "The Parliamentary Appointments Committee has rescheduled the vetting of Mahama Ayariga and Dr Zanetor Agyeman-Rawlings to Thursday, August 27, 2026.\n\nThe two nominees were originally scheduled to appear before the committee on Tuesday, August 25...",
  "reporterInitials": "MRA/MA",
  "author": "GhanaWeb",
  "bylineLabel": "Source",
  "bylineName": "www.ghanaweb.com",
  "category": "News",
  "datePublished": "2026-08-25T17:36:36+00:00",
  "dateModified": "2026-08-25T17:36:36+00:00",
  "thumbnailUrl": "https://cdn.ghanaweb.com/imagelib/src/Parliament_House-Ghana2334.jpg",
  "image": {
    "type": "ImageObject",
    "url": "https://cdn.ghanaweb.com/imagelib/src/Parliament_House-Ghana2334.jpg",
    "caption": "The committee is expected to scrutinise their qualifications for their respective portfolios",
    "width": "600",
    "height": "450"
  }
}
```

An Opinions/Features record instead carries a named columnist and no reporter-initials signature:

```json
{
  "headline": "My open advice to new Majority Leader James Agalga",
  "author": null,
  "bylineLabel": "Columnist",
  "bylineName": "Dr John-Baptist Naah",
  "reporterInitials": null,
  "category": "Opinions"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T09:12:10Z",
  "articleId": "2049369",
  "title": "Mahama Ayariga, Dr Zanetor vetting rescheduled to August 27",
  "link": "https://www.ghanaweb.com/GhanaHomePage/NewsArchive/Mahama-Ayariga-Dr-Zanetor-vetting-rescheduled-to-August-27-2049369",
  "section": "NewsArchive",
  "publicationDate": "2026-08-25T17:36:36+00:00",
  "language": "en"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `articleId` | string | Internal numeric GhanaWeb article ID, from the URL's trailing digits. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode only, from ld+json). |
| `articleBody` | string | Full plain-text article content, truncated before any trailing promo content (article mode only). |
| `reporterInitials` | string | GhanaWeb's internal 2-part reporter/editor signature (e.g. `"MRA/MA"`), staff news pieces only. |
| `author` | string | `"GhanaWeb"` on staff pieces (no individual byline policy); `null` on Opinions/Features. |
| `bylineLabel` / `bylineName` | string | `"Source"` / `"www.ghanaweb.com"` on staff pieces, or `"Columnist"` / the columnist's name on opinion pieces. |
| `category` | string | Section name, e.g. `"News"`, `"Opinions"`, `"Sports"`. |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `thumbnailUrl` / `image` | string/object | Lead image (article mode only). |
| `link` | string | Article URL (latest mode). |
| `section` | string | URL path segment (e.g. `NewsArchive`, `SportsArchive`, `business`) — latest mode only. |
| `publicationDate` | string | ISO-8601 publish timestamp from the sitemap (latest mode). |
| `language` | string | Sitemap-declared language code (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or out-of-range article).
