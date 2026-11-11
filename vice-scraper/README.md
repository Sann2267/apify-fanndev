# VICE Scraper

Extract full article text or the newest headlines from VICE (vice.com), the digital-native journalism outlet known for culture, science, and human-interest coverage — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, publish/update dates, lead image
- Ad-slot and video-embed placeholders are automatically excluded from the article body
- Also fetches the newest headlines from the site-wide feed — including full body HTML — without visiting each article individually
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
    "https://www.vice.com/en/article/scientists-have-some-bad-news-about-your-favorite-viral-cat-videos/"
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
| `limit` | integer | Max headlines returned in latest mode. The feed carries 10 items per fetch. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.vice.com/en/article/scientists-have-some-bad-news-about-your-favorite-viral-cat-videos/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-23T23:54:48Z",
  "headline": "Scientists Have Some Bad News About Your Favorite Viral Cat Videos",
  "description": "Cat content is its own corner of the internet, and the primary rule is that everything is either hilarious or adorable, but scientists disagree.",
  "articleBody": "Cat content is its own corner of the internet, and the primary rule is that everything a cat does is either hilarious or adorable...",
  "articleSection": "Science",
  "datePublished": "2026-08-23T21:56:17Z",
  "dateModified": "2026-08-23T21:56:22Z",
  "author": "Ashley Fike",
  "keywords": ["cats", "pet owners", "scientific study"],
  "image": "https://www.vice.com/wp-content/uploads/sites/2/2026/08/..."
}
```

**Latest headlines mode** — one record per headline (includes full body HTML):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T23:54:45Z",
  "title": "Scientists Have Some Bad News About Your Favorite Viral Cat Videos",
  "link": "https://www.vice.com/en/article/scientists-have-some-bad-news-about-your-favorite-viral-cat-videos/",
  "author": "Ashley Fike",
  "guid": "https://www.vice.com/en/?p=2083997",
  "pubDate": "Sun, 23 Aug 2026 21:56:17 +0000",
  "description": "Cat content is its own corner of the internet, and the primary rule is that everything a cat does is either hilarious or adorable...",
  "contentHtml": "<p class=\"wp-block-paragraph\">Cat content is its own corner of the internet...</p>",
  "categories": ["Life", "Science", "cats", "pet owners", "scientific study"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary, cleaned of markup. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `contentHtml` | string | Full article body as HTML (latest mode only). |
| `articleSection` | string | Section name (article mode only). |
| `author` | string | Byline. |
| `keywords` | array | Tag keywords (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode only). |
| `categories` | array | Section/topic tags (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
