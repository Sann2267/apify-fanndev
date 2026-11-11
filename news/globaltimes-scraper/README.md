# Global Times Scraper

Extract full article text or the newest headlines from Global Times (globaltimes.cn), the English-language edition of a major Chinese state media outlet — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, byline, publish date, reconstructed into clean paragraphs
- Automatically removes duplicate image-caption text that would otherwise pollute the article body
- English-language coverage of China's economy, technology, foreign policy, and society from an official state-media perspective
- Also fetches the newest headlines (with keywords) from the Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.globaltimes.cn/page/202608/1368841.shtml"
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
  "_input": "https://www.globaltimes.cn/page/202608/1368841.shtml",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T02:07:07Z",
  "headline": "Chinese electric forklift exports boom, orders extend into Q4",
  "articleBody": "Chinese electric forklifts are riding a powerful export wave, the Global Times learned from manufacturers and exporters...",
  "author": "Zhang Weilan and Qi Xijia",
  "publishedRaw": "Published: Aug 23, 2026 09:59 PM"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T02:07:07Z",
  "title": "China's global initiatives offer new opportunities for cooperation, says Italian business leader",
  "link": "https://www.globaltimes.cn/page/202608/1368864.shtml",
  "publicationDate": "2026-08-24T12:50:59+08:00",
  "keywords": ["cooperation", "global", "italy", "dialogue", "china"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode only). |
| `publishedRaw` | string | Publish date/time exactly as shown on the page — not machine-parsed (article mode only). |
| `keywords` | array | Tag keywords (latest mode). |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Machine-readable publication timestamp, ISO-8601 with timezone (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
