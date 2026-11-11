# Jerusalem Post Scraper

Extract full article text or the newest headlines from The Jerusalem Post (jpost.com), an English-language Israeli news outlet — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, description, byline(s), publish/modified dates, section, keywords, and a paywall flag
- Also fetches the newest headlines straight from the site's Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls the full text and every publicly available detail about the story straight out of the page's structured data (JSON-LD).
3. In latest mode, the actor reads the site's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.jpost.com/opinion/article-906309"
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
  "_input": "https://www.jpost.com/opinion/article-906309",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-25T10:12:03Z",
  "_paywalled": false,
  "headline": "Developments of the last week that could affect the approaching elections - opinion",
  "description": "His goal was to put unattractive candidates out of realistic places on the list...",
  "articleBody": "Though we are no closer today than we were last week to guessing the outcome of the October 27 elections for the 26th Knesset...",
  "author": ["SUSAN HATTIS ROLEF"],
  "publisher": "The Jerusalem Post",
  "datePublished": "2026-08-24T20:00:00.000+00:00",
  "dateModified": "2026-08-24T20:00:00.000+00:00",
  "articleSection": ["Opinion"],
  "keywords": ["Benjamin Netanyahu", "Elections", "Likud", "Israel Elections"],
  "image": [{"url": "https://images.jpost.com/image/upload/...", "width": "1280", "height": "720"}]
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-25T10:12:10Z",
  "title": "Bennett: Next gov't will declare national education emergency, address teacher shortage",
  "link": "https://www.jpost.com/israel-election-2026/article-906457",
  "pubDate": "2026-08-24T20:04:44+00:00",
  "lastmod": "2026-08-24T20:04:44+00:00",
  "keywords": ["2026 Israeli Elections", "Elections", "Israel", "Naftali Bennett"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `_paywalled` | boolean | `true` if JPost's own `isAccessibleForFree` flag says this article is premium content (article mode only). No paywalled example was found during testing, but the field is always present so downstream consumers can filter on it. |
| `headline` | string | Article headline (article mode only). |
| `articleBody` | string | Full plain-text article content, straight from the page's own JSON-LD (article mode only). |
| `author` | array | Byline(s) — individual reporter name(s), not agency-attributed (article mode only). |
| `publisher` | string | Always `"The Jerusalem Post"` (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `articleSection` | array | Section name(s), e.g. `["Opinion"]` (article mode only). |
| `keywords` | array | Tags associated with the article. |
| `title` / `link` | string | Headline / article URL (latest mode). |
| `pubDate` / `lastmod` | string | ISO-8601 publish/modified timestamps as given by the sitemap (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Notes

- `robots.txt` explicitly allows AI/agentic crawlers (`Claude-User`, `GPTBot`, `ChatGPT-User`, `OAI-SearchBot`, `Perplexity-User`) with `Allow: /`.
- See `CRAWLING_METHOD.md` for full recon notes (WAF status, JSON-LD shape, sitemap discovery, paywall verdict).
