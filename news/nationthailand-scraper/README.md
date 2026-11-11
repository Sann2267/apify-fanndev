# The Nation Thailand Scraper

Extract full article text or the newest headlines from The Nation Thailand (nationthailand.com), a major Thai English-language business/general daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, section, keywords, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's news sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.nationthailand.com/news/world/40070208"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. |
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL:

```json
{
  "_input": "https://www.nationthailand.com/news/world/40070208",
  "_source": "S1-html",
  "_paywalled": false,
  "headline": "Japan intensifies regional diplomacy on Hormuz and Bab el-Mandeb",
  "description": "Motegi's six-day Gulf tour and Takaichi's calls to regional leaders...",
  "articleBody": "Japan's dependence on Middle Eastern oil has moved the safety of two maritime corridors...",
  "author": "Jiji Press",
  "publisher": "Jiji Press",
  "datePublished": "...",
  "isAccessibleForFree": true
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "title": "Suzuki unveils its first electric minicar for Japan with 310km range",
  "link": "https://www.nationthailand.com/news/world/40070207",
  "publicationDate": "2026-08-24T23:05:00+07:00"
}
```

A failed URL (removed article, network issue) still produces a row instead of silently disappearing:

```json
{
  "_input": "https://www.nationthailand.com/news/world/00000000",
  "_source": "none",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- The site returns HTTP 200 for a nonexistent article (a soft-404 that renders the homepage), not a real 404 — this actor detects that case internally via the page's canonical link and still reports it as a clean `not_found` row.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
