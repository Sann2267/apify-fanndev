# Vox Scraper

Extract full article text or the newest headlines from Vox — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, keywords, section, and publish/update dates
- Also fetches the newest headlines from a single site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.vox.com/the-highlight/473299/is-surrogacy-ethical-or-unethical-elective-medical"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.vox.com/the-highlight/473299/is-surrogacy-ethical-or-unethical-elective-medical",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:55:41Z",
  "@type": "NewsArticle",
  "headline": "You want a baby. Is it ethical to choose surrogacy?",
  "description": "The line between medically necessary and elective surrogacy isn't as tidy as people assume.",
  "articleBody": "...",
  "articleSection": "The Highlight",
  "keywords": ["Advice", "Family", "Future Perfect", "Life", "Parenting", "Relationships", "The Highlight", "Your Mileage May Vary"],
  "author": [{ "@type": "Person", "name": "Sigal Samuel", "url": "https://www.vox.com/authors/sigal-samuel" }],
  "datePublished": "2026-01-12T11:00:00+00:00",
  "dateModified": "2026-08-23T12:33:32+00:00"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-atom",
  "_scrapedAt": "2026-08-23T19:56:29Z",
  "title": "You want a baby. Is it ethical to choose surrogacy?",
  "link": "https://www.vox.com/the-highlight/473299/is-surrogacy-ethical-or-unethical-elective-medical",
  "guid": "https://www.vox.com/?p=473299",
  "pubDate": "2026-08-23T08:33:32-04:00",
  "updated": "2026-08-23T08:33:43-04:00",
  "description": "Editor's note, August 23, 8 am ET: We're bringing you some of our best-loved Your Mileage May Vary columns while Sigal Samuel is on parental leave ...",
  "author": "Sigal Samuel",
  "categories": ["Advice", "Family", "Future Perfect", "Life", "Parenting", "Relationships", "The Highlight", "Your Mileage May Vary"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek. |
| `keywords` / `categories` | array | Topic tags (`keywords` in article mode, `categories` in latest mode). |
| `author` | array or string | Byline — array of `{name, url}` objects in article mode, a single name string in latest mode. |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` / `updated` | string | Publication/update timestamps (latest mode). |
| `link` | string | The article URL (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
