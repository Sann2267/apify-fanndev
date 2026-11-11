# Tuổi Trẻ News Scraper

Extract full article text or the newest headlines from Tuổi Trẻ News (tuoitrenews.vn), the English-language edition of Vietnam's largest-circulation newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs (photo captions and related-article widgets automatically excluded)
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
    "https://tuoitrenews.vn/ho-chi-minh-citys-largest-vegetarian-food-fest-takes-place-with-focus-on-green-cuisine-103260824224936756.htm"
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
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL:

```json
{
  "_input": "https://tuoitrenews.vn/ho-chi-minh-citys-largest-vegetarian-food-fest...",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T17:15:30Z",
  "headline": "Ho Chi Minh City's largest vegetarian food fest takes place with focus on green cuisine",
  "description": "The Ho Chi Minh City Vegetarian Food Festival 2026...",
  "articleBody": "The event is intended to go beyond simply showcasing...",
  "author": "Hoang Le - Dong Nguyen / Tuoi Tre News",
  "publisher": "Tuoi tre news",
  "datePublished": "2026-08-24T23:42:00+07:00",
  "dateModified": "2026-08-24T23:43:00+07:00",
  "image": "https://cdn2.tuoitre.vn/zoom/1200_630/..."
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "title": "Da Nang's Dragon Bridge to stage six consecutive fire shows for National Day",
  "link": "https://news.tuoitre.vn/da-nangs-dragon-bridge-...htm",
  "description": "Dragon Bridge, a symbol of Da Nang City...",
  "author": "Van Giang - Truong Trung / Tuoi Tre News",
  "pubDate": "Mon, 24 Aug 2026 21:43:00 GMT+7",
  "image": "https://cdn2.tuoitre.vn/zoom/1200_900/..."
}
```

A failed URL (removed article, network issue) still produces a row instead of silently disappearing:

```json
{
  "_input": "https://tuoitrenews.vn/nonexistent-article-99999999.htm",
  "_source": "none",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- Every `tuoitrenews.vn` URL transparently redirects to `news.tuoitre.vn` (the same site's canonical domain) — both work identically as input.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
