# Daily Mirror Scraper

Extract full article text or the newest headlines from Daily Mirror (dailymirror.lk), Sri Lanka's leading English-language daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not a summary — headline, description, byline, publish/modified dates, lead image, and the complete article body
- Also fetches the newest headlines straight from the site's Breaking News section without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups
- Correctly detects Daily Mirror's soft-404 pages (the site always answers HTTP 200, even for a removed or non-existent article) instead of returning a blank or broken record

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads Daily Mirror's own Breaking News listing and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.dailymirror.lk/breaking-news/Cabinet-approves-Rs-104-9-bn-central-expressway-road-project/108-348843"
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

**Article mode** — one record per URL. Real output from a local test run:

```json
{
  "_input": "https://www.dailymirror.lk/breaking-news/Cabinet-approves-Rs-104-9-bn-central-expressway-road-project/108-348843",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T00:57:48Z",
  "articleId": "348843",
  "categoryId": "108",
  "category": "breaking-news",
  "headline": "Cabinet approves Rs. 104.9 bn central expressway road project",
  "description": "The Cabinet has approved a proposal to develop connecting roads linking Sections I, III and IV of the Central Expressway with the existing road network in the Western, Central and North-Western provinces.",
  "articleBody": "Colombo, Aug. 25 (Daily Mirror) - The Cabinet has approved a proposal to develop connecting roads linking Sections I, III and IV of the Central Expressway with the existing road network in the Western, Central and North-Western provinces.\n\nThe project is aimed at improving connectivity, accessibility and traffic flow between the Central Expressway and the existing road network.\n\n... 4 more paragraphs",
  "author": "CHATURANGA PRADEEP SAMARAWICKRAMA",
  "datePublished": "2026-08-25T13:46:00+05:30",
  "dateModified": "2026-08-25T13:46:00+05:30",
  "image": {
    "@type": "ImageObject",
    "url": "assets/uploads/image_a177e06553.jpeg",
    "width": "200",
    "height": "200"
  }
}
```

A record where the site has no author byline (many pieces credit the generic desk instead of a named reporter) and no lead image:

```json
{
  "headline": "38 Years. ’One unforgettable team’",
  "author": "DM Editorial",
  "category": "sports",
  "image": { "@type": "ImageObject", "url": "none", "width": "200", "height": "200" }
}
```

A URL that doesn't correspond to a real article — Daily Mirror always answers HTTP 200, even for a removed or fabricated article ID, so this is detected from the page content, not the status code:

```json
{
  "_input": "https://www.dailymirror.lk/breaking-news/this-article-does-not-exist-zzz/108-99999999",
  "_source": "none",
  "_scrapedAt": "2026-08-26T00:57:48Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

**Latest headlines mode** — one record per headline. Real output from a local test run:

```json
{
  "_input": "latest",
  "_source": "S2-html-listing",
  "_scrapedAt": "2026-08-26T00:56:15Z",
  "articleId": "348860",
  "categoryId": "108",
  "category": "breaking-news",
  "title": "Parliament Committee seeks Police Proposals to Ease Prison Overcrowding",
  "link": "https://www.dailymirror.lk/breaking-news/Parliament-Committee-seeks-Police-Proposals-to-Ease-Prison-Overcrowding/108-348860"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` for articles, `S2-html-listing` for latest headlines). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `articleId` | string | Internal numeric Daily Mirror article ID, from the URL's trailing digits. |
| `categoryId` | string | Internal numeric Daily Mirror category/section ID from the URL. |
| `category` | string | URL path segment identifying the section (e.g. `breaking-news`, `sports`, `school_rugby`). |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline name — a specific reporter's name, or the generic `"DM Editorial"` on many pieces. |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `image` | object | Lead image (article mode only). `url` is the literal string `"none"` when the article has no lead image. |
| `link` | string | Article URL (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
