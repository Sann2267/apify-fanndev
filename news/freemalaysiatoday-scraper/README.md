# Free Malaysia Today Scraper

Extract full article text or the newest headlines from Free Malaysia Today (freemalaysiatoday.com), one of Malaysia's largest independent English-language news outlets — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, byline, categories, tags, lead image, publish/modified dates
- Also fetches the newest headlines from the site's headline feed, complete with full article text for each headline (not just a teaser)
- Rich category and tag detail on every article, straight from the publisher's own content system
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories, each with full article text included.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.freemalaysiatoday.com/category/nation/2026/08/26/areas-with-unhealthy-air-quality-fall-to-16-nationwide"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed carries 50 items per fetch). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.freemalaysiatoday.com/category/nation/2026/08/26/areas-with-unhealthy-air-quality-fall-to-16-nationwide",
  "_source": "S1-nextdata",
  "_scrapedAt": "2026-08-26T02:12:14Z",
  "__typename": "Post",
  "id": "cG9zdDoyNzg3NDgz",
  "databaseId": 2787483,
  "title": "Areas with unhealthy air quality fall to 16 nationwide",
  "excerpt": "<p>Sarawak and Selangor had the most areas in the unhealthy range as of 9am, with readings of up to 166.</p>\n",
  "slug": "areas-with-unhealthy-air-quality-fall-to-16-nationwide",
  "status": "publish",
  "date": "2026-08-26T10:01:17",
  "dateGmt": "2026-08-26T02:01:17",
  "modifiedGmt": "2026-08-26T02:01:17",
  "uri": "/category/nation/2026/08/26/areas-with-unhealthy-air-quality-fall-to-16-nationwide",
  "content": "<figure class=\"aligncenter wp-caption\" data-media-id=\"3009535\"><img loading=\"lazy\" src=\"https://media.freemalaysiatoday.com/v3/2026/08/0d572414-73ef-4eb4-bee5-f073509587df-jerebu-sarawak-resize-bernamapic-200826.jpg\" alt=\"jerebu sarawak\" ... (full HTML, truncated) ...",
  "featuredImage": {
    "node": {
      "databaseId": 3009535,
      "sourceUrl": "https://media.freemalaysiatoday.com/v3/2026/08/0d572414-73ef-4eb4-bee5-f073509587df-jerebu-sarawak-resize-bernamapic-200826.jpg",
      "altText": "jerebu sarawak",
      "caption": "<p>(Bernama pic)</p>\n",
      "title": "jerebu sarawak resize bernamapic 200826.jpg",
      "mediaDetails": { "height": 1000, "width": 1600 }
    }
  },
  "categories": {
    "edges": [
      { "node": { "__typename": "Category", "databaseId": 1099, "name": "Borneo+", "slug": "sabahsarawak" } },
      { "node": { "__typename": "Category", "databaseId": 45, "name": "Highlight", "slug": "highlight" } },
      "... 2 more"
    ]
  },
  "author": {
    "node": {
      "id": "dXNlcjoyMjk=",
      "databaseId": 229,
      "name": "FMT Reporters",
      "slug": "fmtreporters",
      "uri": "/category/author/fmtreporters",
      "avatar": { "url": "https://media.freemalaysiatoday.com/wp-content/uploads/2024/04/b75d430c-new-project.webp" },
      "jobTitle": null,
      "sameAs": []
    }
  },
  "tags": {
    "edges": [
      { "node": { "databaseId": 8693, "name": "air pollution", "slug": "air-pollution" } },
      "... 3 more"
    ]
  },
  "articleBody": "PETALING JAYA: The number of areas recording unhealthy air pollutant index (API) readings had fallen to 16 as of 9am today, down sharply from 30 at the same time yesterday.\n\nAccording to data from the Malaysian Air Pollutant Index Management System portal, unhealthy API readings were recorded at stations in five states and two federal territories.\n\n... (full plain-text article body, truncated)"
}
```

**Latest headlines mode** — one record per headline (truncated here for readability):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:12:14Z",
  "title": "Areas with unhealthy air quality fall to 16 nationwide",
  "link": "https://www.freemalaysiatoday.com/category/nation/2026/08/26/areas-with-unhealthy-air-quality-fall-to-16-nationwide",
  "creator": "FMT Reporters",
  "pubDate": "Wed, 26 Aug 2026 02:01:17 GMT",
  "guid": "https://www.freemalaysiatoday.com/category/nation/2026/08/26/areas-with-unhealthy-air-quality-fall-to-16-nationwide",
  "description": "Sarawak and Selangor had the most areas in the unhealthy range as of 9am, with readings of up to 166.",
  "categories": ["Highlight", "Borneo+", "Malaysia", "Top News"],
  "content": "<figure class=\"aligncenter wp-caption\" data-media-id=\"3009535\"><img src=\"https://media.freemalaysiatoday.com/...\" ... (full HTML, truncated) ...",
  "articleBody": "PETALING JAYA: The number of areas recording unhealthy air pollutant index (API) readings had fallen to 16 as of 9am today, down sharply from 30 at the same time yesterday.\n\n... (full plain-text article body, truncated)",
  "image": "https://media.freemalaysiatoday.com/v3/2026/08/0d572414-73ef-4eb4-bee5-f073509587df-jerebu-sarawak-resize-bernamapic-200826.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `title` | string | Article headline (both modes). |
| `content` | string | Full article body as raw HTML (both modes). |
| `articleBody` | string | Full article body as plain text, paragraphs joined (both modes). |
| `excerpt` | string | Short teaser as raw HTML (article mode only). |
| `description` | string | Short teaser as plain text (latest mode only). |
| `slug` / `status` / `uri` | string | WordPress slug, publish status, and site-relative path (article mode only). |
| `date` / `dateGmt` / `modifiedGmt` | string | Publish/modified timestamps (article mode only). |
| `pubDate` | string | Publish timestamp (latest mode only). |
| `link` / `guid` | string | Article URL (latest mode only). |
| `author` | object | Byline details — name, profile URL, avatar (article mode only). |
| `creator` | string | Byline name only (latest mode only). |
| `categories` | object/array | Article mode: nested category objects. Latest mode: a plain list of category names. |
| `tags` | object | Nested tag objects (article mode only). |
| `featuredImage` | object | Lead image details — URL, caption, dimensions (article mode only). |
| `image` | string | Lead image URL (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
