# LA Times Scraper

Extract full article text or the newest headlines from the Los Angeles Times — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline (with author bios), section, and publish/update dates
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
    "https://www.latimes.com/politics/story/2026-08-23/will-trump-interfere-in-midterms-democrats-their-allies-are-preparing"
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
  "_input": "https://www.latimes.com/politics/story/2026-08-23/will-trump-interfere-in-midterms-democrats-their-allies-are-preparing",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:54:07Z",
  "@type": "NewsArticle",
  "headline": "Will Trump interfere in the midterms? Democrats and their allies are preparing",
  "description": "Across California and the nation, Democratic leaders and voting rights advocates are ramping up coordination and gaming out responses to a raft of potential actions by the Trump administration to subvert the November vote or deny its outcome.",
  "articleBody": "Big-city mayors are giving poll workers panic buttons in case election skeptics question their work. County and state officials are gaming out responses to immigration raids near voting centers ...",
  "articleSection": "Politics",
  "datePublished": "2026-08-23T10:00:00.000Z",
  "dateModified": "2026-08-23T10:00:05.395Z",
  "author": [
    { "@type": "Person", "name": "Kevin Rector", "jobTitle": "Staff Writer" },
    { "@type": "Person", "name": "Justine McDaniel", "jobTitle": "Staff Writer" }
  ],
  "image": [ "... 2 more" ]
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T19:53:49Z",
  "title": "Will Trump interfere in the midterms? Democrats and their allies are preparing",
  "link": "https://www.latimes.com/politics/story/2026-08-23/will-trump-interfere-in-midterms-democrats-their-allies-are-preparing",
  "guid": "https://www.latimes.com/politics/story/2026-08-23/will-trump-interfere-in-midterms-democrats-their-allies-are-preparing",
  "pubDate": "Sun, 23 Aug 2026 10:00:00 GMT",
  "description": "<p>Across California and the nation, Democratic leaders and voting rights advocates are ramping up coordination and gaming out responses to a raft of potential actions by the Trump administration to subvert the November vote or deny its outcome.</p>"
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
| `author` | array | Byline (article mode only) — name and job title per writer. |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
