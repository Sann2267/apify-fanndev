# Philippine Star Scraper

Extract full article text or the newest headlines from The Philippine Star (philstar.com), one of the Philippines' largest national English-language newspapers — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, publish/update dates, lead image
- Handles a site-specific quirk where the article's summary field is HTML-entity-escaped markup, not plain text — cleaned up automatically
- Also fetches the newest headlines from the site-wide feed without visiting each article individually
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
    "https://www.philstar.com/headlines/2026/08/24/2551340/lacson-perpetual-public-office-ban-possible-inducing-perjury"
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
  "_input": "https://www.philstar.com/headlines/2026/08/24/2551340/lacson-perpetual-public-office-ban-possible-inducing-perjury",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-23T23:40:20Z",
  "headline": "Lacson: Perpetual public office ban possible for inducing perjury",
  "description": "Public officials who orchestrate false testimonies by inducing others to commit perjury can be prosecuted as principal perpetrators and face a lifetime ban from holding government office, Sen. Panfilo Lacson warned yesterday.",
  "articleBody": "MANILA, Philippines — Public officials who orchestrate false testimonies by inducing others to commit perjury can be prosecuted as principal perpetrators...",
  "articleSection": "Headlines",
  "datePublished": "2026-08-24T00:00:00+08:00",
  "dateModified": "2026-08-24T00:00:00+08:00",
  "author": "Neil Jayson Servallos",
  "keywords": "senator",
  "image": "https://media.philstar.com/photos/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T23:39:27Z",
  "title": "Lacson: Perpetual public office ban possible for inducing perjury",
  "link": "https://www.philstar.com/headlines/2026/08/24/2551340/lacson-perpetual-public-office-ban-possible-inducing-perjury",
  "author": "Neil Jayson Servallos",
  "guid": "https://www.philstar.com/headlines/2026/08/24/2551340/lacson-perpetual-public-office-ban-possible-inducing-perjury",
  "pubDate": "Mon, 24 Aug 2026 00:00:00 +0800",
  "description": "Public officials who orchestrate false testimonies by inducing others to commit perjury can be prosecuted as principal perpetrators and face a lifetime ban from holding government office, Sen. Panfilo Lacson warned yesterday."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary, cleaned of markup (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `articleSection` | string | Section name (article mode only). |
| `author` | string | Byline. |
| `keywords` | string | Tag keyword(s) (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode only). |
| `pubDate` | string | Publication timestamp (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
