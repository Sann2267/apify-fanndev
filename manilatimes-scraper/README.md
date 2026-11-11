# Manila Times Scraper

Extract full article text or the newest headlines from The Manila Times (manilatimes.net), the Philippines' oldest English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, publish/update dates, lead image
- The "latest" feed itself carries full article text, not just a teaser, so you can get complete stories in bulk without visiting each page
- Handles site-specific quirks (HTML-entity-escaped punctuation, malformed JSON-LD control characters) automatically
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's site-wide "Latest News" feed and returns the newest stories, complete with full body text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.manilatimes.net/2026/08/26/news/ncda-warns-against-use-of-logo-for-solicitation/2412178"
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
| `limit` | integer | Max headlines returned in latest mode. The feed carries 50 items per fetch. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output, truncated only where noted):

```json
{
  "_input": "https://www.manilatimes.net/2026/08/26/news/ncda-warns-against-use-of-logo-for-solicitation/2412178",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T02:17:59Z",
  "headline": "NCDA warns against use of logo for solicitation",
  "description": "The National Council on Disability Affairs (NCDA) on Tuesday warned the public over the unauthorized use of its logo.",
  "articleBody": "The National Council on Disability Affairs (NCDA) on Tuesday warned the public over the unauthorized use of its logo.\n\nIn a statement, the council said they received reports regarding the use of its logo for solicitation purposes “which misleads the public and undermines the integrity of our services.”\n\n... 4 more paragraphs",
  "articleSection": "News",
  "datePublished": "2026-08-26T06:19:00+08:00",
  "dateModified": "2026-08-26T06:20:31+08:00",
  "author": "Aric John Sy Cua",
  "keywords": "",
  "image": "https://manilatimes.net/manilatimes/uploads/images/2026/08/26/1190362.jpg",
  "isAccessibleForFree": true
}
```

**Latest headlines mode** — one record per headline (the feed carries the full article body, not just a teaser):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:18:19Z",
  "title": "NCDA warns against use of logo for solicitation",
  "link": "https://www.manilatimes.net/2026/08/26/news/ncda-warns-against-use-of-logo-for-solicitation/2412178",
  "author": "Aric John Sy Cua",
  "category": "News",
  "guid": "https://www.manilatimes.net/2026/08/26/news/ncda-warns-against-use-of-logo-for-solicitation/2412178",
  "pubDate": "Wed, 26 Aug 2026 06:20:39 +0800",
  "description": "The National Council on Disability Affairs (NCDA) on Tuesday warned the public over the unauthorized use of its logo.\n\n... 5 more paragraphs",
  "imageUrl": "https://manilatimes.net/manilatimes/uploads/images/2026/08/26/1190362.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Article mode: dek/summary. Latest mode: full article body (this feed carries complete text, not a teaser). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `articleSection` / `category` | string | Section name (News, Business, Sports, World, Entertainment & Lifestyle, TMT Newswire, ...). |
| `author` | string | Byline (wire-service reprints show the agency name, e.g. "Agence France-Presse"). |
| `keywords` | string | Tag keyword(s) (article mode only; empty string on every article sampled). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `isAccessibleForFree` | boolean | Paywall marker (article mode only; always `true` on sampled articles — no paywall found). |
| `pubDate` | string | Publication timestamp (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).
