# Fox News Scraper

Extract full article text or the newest headlines from Fox News (foxnews.com), one of the most-visited news websites in the United States — no account or subscription needed.

## Why use this actor

- No account or login required — Fox News Digital is fully free, ad-supported, no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, word count, publish/update dates, lead image
- Latest headlines mode returns the full article HTML body inline, not just teasers
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's Google Publisher feed and returns the newest stories, including full body HTML.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.foxnews.com/media/tom-homan-fires-back-florida-democrat-ridiculous-ice-racial-profiling-claim"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 25. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.foxnews.com/media/tom-homan-fires-back-florida-democrat-ridiculous-ice-racial-profiling-claim",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T23:50:40Z",
  "headline": "Tom Homan fires back at Florida Democrat over 'ridiculous' ICE racial profiling claim",
  "description": "Tom Homan calls himself an \"equal opportunity deporter\" while rejecting Angie Nixon's claims that ICE agents racially profile Black Americans.",
  "articleBody": "Border czar Tom Homan rejected Florida Democratic Senate nominee Angie Nixon's warning that Immigration and Customs Enforcement (ICE) agents would racially profile Black Americans...",
  "articleSection": "media",
  "datePublished": "2026-08-24T00:00:00Z",
  "dateModified": "2026-08-24T00:00:00Z",
  "author": "Nora Moriarty",
  "keywords": "...",
  "wordCount": 517,
  "isAccessibleForFree": true,
  "image": "https://static.foxnews.com/..."
}
```

**Latest headlines mode** — one record per headline (includes full body HTML):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T23:50:39Z",
  "title": "Enes Kanter Freedom met with hostile WNBA fans en route to Fever-Sky matchup",
  "link": "https://www.foxnews.com/outkick-sports/enes-kanter-freedom-hostile-wnba-fans-fever-sky-matchup",
  "guid": "https://www.foxnews.com/outkick-sports/enes-kanter-freedom-hostile-wnba-fans-fever-sky-matchup",
  "pubDate": "Sun, 23 Aug 2026 19:37:35 -0400",
  "description": "Video shows Enes Kanter Freedom being swarmed by a hostile crowd outside the sold-out Indiana Fever-Chicago Sky WNBA game at Wintrust Arena.",
  "contentHtml": "<p>Ex-NBA center <a href=\"...\">Enes Kanter Freedom</a> was met by a hostile crowd outside Chicago's Wintrust Arena on Sunday...</p>",
  "categories": ["fnc", "Fox News", "fox-news/outkick/outkick-sports", "..."]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `contentHtml` | string | Full article body as HTML, including inline links (latest mode only). |
| `articleSection` | string | Section name (article mode only). |
| `author` | string | Byline (article mode only). |
| `keywords` | string | Tag keyword(s) (article mode only). |
| `wordCount` | integer | Site-reported word count (article mode only). |
| `isAccessibleForFree` | boolean | Whether the site flags this as free content — always `true` on sampled articles. |
| `image` | string | Lead image URL (article mode only). |
| `categories` | array | Section/topic tags, mix of internal IDs and labels (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
