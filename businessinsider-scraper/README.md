# Business Insider Scraper

Extract full article details or the newest headlines from Business Insider — no account or subscription needed.

## Why use this actor

- No account or login required
- Rich article detail: headline, byline with reporter job titles and profile links, editor, publish/update dates, and publisher info
- Also fetches the newest headlines site-wide, including full article body text, without visiting each article individually
- Automatically excludes subscriber-only "Insider" premium content from the headline feed
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out every publicly available detail about the story.
3. In latest mode, the actor reads the site-wide headline feed and returns the newest stories, including full text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.businessinsider.com/fancy-new-business-class-suites-cause-headache-certification-delays-2026-8"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines site-wide. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 20. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability; the real record includes the full publisher block with masthead, ethics policy, and social links):

```json
{
  "_input": "https://www.businessinsider.com/fancy-new-business-class-suites-cause-headache-certification-delays-2026-8",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T00:00:00Z",
  "@type": "NewsArticle",
  "editor": { "@type": "Person", "name": "Will Martin" },
  "author": [
    { "@type": "Person", "name": "Pete Syme", "url": "https://www.businessinsider.com/author/pete-syme", "jobTitle": "Aviation Reporter" }
    /* ... 1 more author */
  ],
  "publisher": { "@type": "NewsMediaOrganization", "name": "Business Insider", "url": "https://www.businessinsider.com" }
  /* ... headline, description, datePublished, dateModified, image, mainEntityOfPage */
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-atom",
  "_scrapedAt": "2026-08-23T19:10:16Z",
  "title": "Hugging Face has been fielding M&A interest for a deal worth at least $13 billion",
  "link": "https://www.businessinsider.com/hugging-face-could-be-acquired-13-billion-2026-8",
  "updated": "2026-08-23T19:01:36Z",
  "content": "<figure><img src=\"https://i.insider.com/6a60930254f987526177814a?format=jpeg\" ...",
  "categories": []
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `author` | array | Reporters, with job title and profile URL (article mode only). |
| `editor` | object | Story editor (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `updated` | string | Last-updated timestamp (latest mode). |
| `content` | string | Full HTML article body (latest mode only). |
| `link` | string | The article URL (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
