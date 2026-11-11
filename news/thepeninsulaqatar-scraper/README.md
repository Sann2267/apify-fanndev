# The Peninsula Qatar Scraper

Extract full article text or the newest headlines from The Peninsula (thepeninsulaqatar.com), Qatar's English-language national newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline/wire-source (QNA/AFP/staff), category, publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the current month's Google News sitemap shard (no RSS feed exists on this site) and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://thepeninsulaqatar.com/article/25/08/2026/qatar-museums-to-present-uzbekistan-heritage-in-motion-in-september"
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
  "_input": "https://thepeninsulaqatar.com/article/25/08/2026/canada-unveils-counter-tariffs-of-15-to-50-on-us-goods",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-25T17:51:06Z",
  "headline": "Canada unveils counter tariffs of 15% to 50% on US goods",
  "description": "Ottawa: Canada on Tuesday announced counter tariffs on US goods ranging between 15 percent and 50 percent, as a trade war intensifies between the hist...",
  "articleBody": "Ottawa: Canada on Tuesday announced counter tariffs on US goods ranging between 15 percent and 50 percent, as a trade war intensifies between the historically close allies.\n\nOttawa's retaliatory duties take effect September 8...",
  "author": "QNA",
  "publisher": "The Peninsula Newspaper",
  "category": "World",
  "subcategory": "Americas",
  "datePublished": "2026-08-25 18:41:25",
  "dateModified": "2026-08-25 18:41:25",
  "image": "https://thepeninsulaqatar.com/get/maximage/20250304_1741070034-633.jpeg?1741070034"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-25T17:50:44Z",
  "title": "Qatar Museums to present Uzbekistan: Heritage in Motion in September",
  "link": "https://thepeninsulaqatar.com/article/25/08/2026/qatar-museums-to-present-uzbekistan-heritage-in-motion-in-september",
  "pubDate": "2026-08-25T19:50:32+03:00",
  "lastmod": "2026-08-25T19:46:52+03:00"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-html` or `S2-sitemap`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode: page meta description; absent in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Per-article byline/wire-source tag — `"QNA"`, `"AFP"`, or `"The Peninsula"` for staff-written pieces (article mode only). |
| `publisher` | string | Always `"The Peninsula Newspaper"` (article mode only — this is the org name the site's own meta tags use, not a personal byline). |
| `category` | string | Main section name, e.g. `"World"`, `"Qatar"`. |
| `subcategory` | string | Subsection name, e.g. `"Americas"`, `"General"`. |
| `datePublished` / `dateModified` | string | Timestamps as given by the site's own meta tags (Doha local time, article mode only). |
| `image` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `pubDate` / `lastmod` | string | ISO-8601 publish/modified timestamps from the sitemap entry (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).
