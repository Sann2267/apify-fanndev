# Euronews Scraper

Extract full article text or the newest headlines from Euronews (euronews.com), the pan-European English-language news outlet — no account or subscription needed.

## Why use this actor

- No account or login required — fully open-access editorial site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, section, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.euronews.com/my-europe/2026/08/24/victims-of-abuse-at-youth-care-home-to-be-compensated-by-danish-government"
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
  "_input": "https://www.euronews.com/my-europe/2026/08/24/victims-of-abuse-at-youth-care-home-to-be-compensated-by-danish-government",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-25T10:12:03Z",
  "headline": "Victims of abuse at youth care home to be compensated by Danish government",
  "description": "According to the Ministry of Social Affairs, between 1949 and 1976, personal accounts and its files showed \"serious and systemic failings during the stay of the 13 former residents in this home, which was under state supervision.\"",
  "articleBody": "The Danish government will compensate 13 people who were victims of abuse at a care home during their youth, Denmark's Ministry of Social Affairs said on Monday.\n\nThe 13 individuals, whose identities have not been disclosed, filed a complaint in March against the state over the abuse they suffered at Solgarden, which included sexual abuse. ...",
  "author": "Nathan Rennolds",
  "publisher": "Euronews",
  "datePublished": "2026-08-24T18:18:34+02:00",
  "dateModified": "2026-08-24T18:18:34+02:00",
  "image": "https://images.euronews.com/articles/stories/09/88/69/45/1440x810_cmsv2_a3a0dc36-6b3a-5d02-816e-814a9c11a1e2-9886945.jpg",
  "articleSection": "Europe News"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-25T10:12:10Z",
  "title": "Victims of abuse at youth care home to be compensated by Danish government",
  "link": "http://www.euronews.com/my-europe/2026/08/24/victims-of-abuse-at-youth-care-home-to-be-compensated-by-danish-government",
  "description": "According to the Ministry of Social Affairs, between 1949 and 1976, personal accounts and its files showed \"serious and systemic failings during the stay of the 13 former residents in this home, which was under state supervision.\"",
  "pubDate": "Mon, 24 Aug 2026 18:18:34 +0200"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content, paragraphs separated by blank lines (article mode only). |
| `author` | string | Byline — the journalist's full name(s), comma-separated if there are several (article mode only). |
| `publisher` | string | Always `"Euronews"` (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `articleSection` | string | Section name, e.g. `"World"`, `"Business"`, `"Europe News"` (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Known limits

- The RSS feed mixes text articles with `/video/...` video-bulletin items. Video pages don't carry article text — feeding a video URL into `article` mode intentionally fails loud rather than returning an empty body (see `CRAWLING_METHOD.md`).
- `description` in `latest` mode is a teaser, not the full article body — use `article` mode against the `link` for full text.
