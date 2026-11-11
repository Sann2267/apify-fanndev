# RT Scraper

Extract full article text or the newest headlines (with full text included) from RT (rt.com), a Russian state-funded international news broadcaster, English edition — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs
- Latest-headlines mode returns **full article text for every item**, not just titles — the RSS feed embeds the complete body, so you often don't need to fetch individual article pages at all
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed, which already embeds full article HTML, and returns the newest stories with full text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.rt.com/news/644593-ukraine-west-dependence-day/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines with full text. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.rt.com/news/644593-ukraine-west-dependence-day/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T16:36:44Z",
  "headline": "Dependence Day: A generation after the Soviet Union fell, Ukraine is a ruined proxy of the West",
  "description": "After the USSR, Ukraine could have bridged East and West...",
  "articleBody": "There is one feeling I often recall from having lived and worked in Ukraine...",
  "author": "RT",
  "publisher": "RT",
  "datePublished": "2026-08-24T15:56:49+00:00",
  "dateModified": "2026-08-24T15:56:49+00:00",
  "images": ["https://mf.b37mrtl.ru/files/2026.08/article/6a8c68cc203027667e42b41e.jpg"]
}
```

**Latest headlines mode** — one record per headline, with full text already included:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-24T16:36:51Z",
  "title": "Dependence Day: A generation after the Soviet Union fell, Ukraine is a ruined proxy of the West",
  "link": "https://www.rt.com/news/644593-ukraine-west-dependence-day/",
  "teaser": "<img alt=\"Preview\" ...> After the USSR, Ukraine could have bridged East and West... <a href=\"...\">Read Full Article at RT.com</a>",
  "articleBody": "Ukraine could have bridged East and West. Instead, corruption, nationalism, and Western meddling left it broken\n\nThere is one feeling I often recall...",
  "pubDate": "Mon, 24 Aug 2026 18:56:49 +0300"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content, present in both modes. |
| `author` / `publisher` | string | Almost always `"RT"` (Organization-level byline; article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `images` | array | Article hero image URL(s) (article mode only). |
| `link` | string | Article URL, stripped of `?utm_...` tracking params (latest mode). |
| `teaser` | string | Raw RSS teaser HTML with embedded thumbnail — kept unparsed for reference (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
