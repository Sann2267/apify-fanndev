# Asharq Al-Awsat Scraper

Extract full article text or the newest headlines from the English edition of Asharq Al-Awsat (english.aawsat.com), the leading Pan-Arab daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully open-access site with no paywall found on any sampled article
- Full article text included, not just a summary — headline, byline, section, publish/modified dates, all extracted from the page itself
- Also fetches the newest headlines automatically from the homepage, no unreliable feed dependency
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and reads the page's own structured data plus its full text content, so you get the complete article, not a truncated preview.
3. In latest mode, the actor scans the homepage for the newest article listings and returns them, sorted newest first.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://english.aawsat.com/business/5310876-humain-mistral-collaborate-advance-sovereign-ai-saudi-arabia-and-regionally"
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
  "_input": "https://english.aawsat.com/business/5310876-humain-mistral-collaborate-advance-sovereign-ai-saudi-arabia-and-regionally",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T02:19:06Z",
  "headline": "HUMAIN, Mistral Collaborate to Advance Sovereign AI in Saudi Arabia and Regionally",
  "description": "Saudi Arabia's HUMAIN and French Artificial Intelligence company Mistral have announced a strategic collaboration spanning AI infrastructure, advanced model development, and the deployment of AI solutions in Saudi Arabia and across the region...",
  "about": null,
  "articleBody": "Saudi Arabia's HUMAIN and French Artificial Intelligence company Mistral have announced a strategic collaboration spanning AI infrastructure, advanced model development, and the deployment of AI solutions in Saudi Arabia and across the region.\n\n\"Together, the companies will pursue the development and localization of advanced AI models, with initial areas of focus including cybersecurity and voice,\" HUMAIN said in a statement on Monday.\n\n... 7 more paragraphs",
  "articleType": "NewsArticle",
  "category": "Business",
  "author": "Asharq Al Awsat",
  "publisher": "الشرق الأوسط",
  "datePublished": "2026-08-25T10:43:34+0100",
  "dateModified": "2026-08-25T10:43:34+0100",
  "image": "https://static.srpcdigital.com/styles/1200x600/public/2026-08/1738383_0.jpeg.webp?VersionId=t5q3luf2VYI766UYSmTj9NKOfKtUn3eu"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-html-listing",
  "_scrapedAt": "2026-08-26T02:18:27Z",
  "title": "Iraq's Ruling Coalition Discusses Arrests of Armed Faction Members",
  "link": "https://english.aawsat.com/arab-world/5311056-iraq%E2%80%99s-ruling-coalition-discusses-arrests-armed-faction-members",
  "articleId": 5311056
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld+html` or `S2-html-listing`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Article summary/lede (article mode only). |
| `about` | array | Present only on some opinion pieces; not curated tags (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `articleType` | string | `NewsArticle` for regular news, `OpinionNewsArticle` for opinion columns (article mode only). |
| `category` | string | Section name, e.g. "Business", "Opinion", "Sports" (article mode only). |
| `author` | string | Byline name — often the outlet's own staff byline, or a named columnist for opinion pieces (article mode only). |
| `publisher` | string | Publisher name, always "الشرق الأوسط" — the outlet's Arabic name, even on the English edition (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `image` | string | Lead image URL (article mode only). |
| `link` | string | Article URL (latest mode). |
| `articleId` | integer | Numeric article ID. Latest-mode results are sorted newest-first by this value. |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or invalid article URL).

## Scope

This actor covers the **English edition only** (`english.aawsat.com`). Asharq Al-Awsat also publishes an Arabic edition on a separate domain, which this actor does not scrape.
