# The Daily Telegraph Scraper

Extract full article text or the newest headlines from The Daily Telegraph (telegraph.co.uk), a UK national newspaper — no account or subscription needed.

## Why use this actor

- No account, login, or paywall bypass required — every sampled article (news, sport, money, travel, opinion, and even a flagship signed economics column) returned full text with no server-side gate
- Full article text included, not just a summary — headline, byline, keywords, publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's sitewide RSS feed without visiting each article individually
- Honest `_paywalled` flag on every article record — never fabricated or silently faked, only set true if the upstream metering flag and a short body both indicate a stub
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
    "https://www.telegraph.co.uk/news/2026/08/25/dolly-parton-dies-aged-80/"
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
  "_input": "https://www.telegraph.co.uk/news/2026/08/25/dolly-parton-dies-aged-80/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T09:12:03Z",
  "headline": "Dolly Parton dies aged 80",
  "articleBody": "Dolly Parton, the country music star, has died at the age of 80.\n\nParton, a fixture in public life for decades...",
  "author": "Benedict Smith",
  "publisher": "The Telegraph",
  "section": "news",
  "keywords": "US content,Dolly Parton,Standard,News,Live & breaking,World News",
  "datePublished": "2026-08-25T18:03Z",
  "dateModified": "2026-08-25T19:13Z",
  "image": [{"@type": "ImageObject", "url": "https://www.telegraph.co.uk/content/dam/news/..."}],
  "isAccessibleForFree": true,
  "_paywalled": false
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T09:12:10Z",
  "title": "Palmer and Rogers show promise of star double act for Chelsea",
  "link": "https://www.telegraph.co.uk/football/2026/08/24/fulham-vs-chelsea-live-score-updates-premier-league/",
  "description": "Palmer and Rogers show promise of star double act for Chelsea",
  "pubDate": "Tue, 25 Aug 2026 10:06:10 GMT",
  "categories": ["topics:organisations/chelsea-fc", "topics:organisations/fulham-fc", "topics:events/premier-league"],
  "author": "Sam Wallace, Matt Law, Kieran Crichard",
  "guid": "edfc5b03-7227-3d04-8d13-655d015a460b",
  "image": "https://www.telegraph.co.uk/content/dam/football/..."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short teaser (latest mode only — article mode has no separate description upstream). |
| `articleBody` | string | Full plain-text article content, reconstructed from HTML (article mode only). |
| `author` | string | Comma-joined byline name(s). |
| `publisher` | string | Always `"The Telegraph"` (article mode only). |
| `section` | string | Best-effort section guessed from the URL path (article mode only — upstream's own `articleSection` field is always empty on this site). |
| `keywords` | string | Comma-separated tag string, passed through verbatim (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `isAccessibleForFree` | boolean | Upstream paywall metering flag, passed through as-is (article mode only). |
| `_paywalled` | boolean | Honest, never-fabricated flag — see "Paywall behavior" below. |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `categories` | array | Taxonomy-style tags from the RSS item, e.g. `"structure:opinion"` (latest mode). |
| `guid` | string | Opaque RSS item UUID (latest mode). |
| `image` | string/array | Lead image URL(s). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Paywall behavior

The Telegraph runs a metered subscriber paywall (Piano/Tinypass), but it's
enforced **client-side via JavaScript** — cookie-based view counting plus
a DOM overlay injected after the page loads. Since this actor reads the
server-rendered HTML directly, the meter never triggers. Across 13
articles sampled during development — spanning breaking news, sport,
money, travel, a long-form magazine interview, and a flagship signed
economics column — every single one returned `isAccessibleForFree: true`
and a full, naturally-ending article body. The actor still ships an
honest `_paywalled` flag that would flip to `true` if a future article
ever comes back with `isAccessibleForFree: false` and a suspiciously
short body — it is never fabricated, and it has not fired on any sample
seen so far. See `CRAWLING_METHOD.md` for the full recon writeup.
