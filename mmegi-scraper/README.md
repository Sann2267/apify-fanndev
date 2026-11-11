# Mmegi (Botswana) Scraper

Extract full article text or the newest headlines from Mmegi Online (mmegi.bw), Botswana's leading independent newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — no paywall was found anywhere on the site
- Full article text included, not just a summary — headline, dates, author, keywords, lead image, publisher info, and the complete article body
- Also fetches the newest headlines straight from Mmegi's News RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story from the page's structured data.
3. In latest mode, the actor reads Mmegi's News RSS feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.mmegi.bw/news/south-africa-builds-africas-healthcare-supply-chains-as-usd-2-billion-flows-into-the-sector/news"
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

**Article mode** — real captured output (`_source: "S1-jsonld"`):

```json
{
  "_input": "https://www.mmegi.bw/sports/new-fnb-premiership-season-starts-next-week/news",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T03:01:44Z",
  "headline": "New FNB Premiership season starts next week",
  "description": "The FNB Premiership season is scheduled to kick off next weekend, defying recent boardroom wrangles that had cast doubt over the start of the new campaign...",
  "articleBody": "\"The BFL Board of Directors has approved the fixtures for the upcoming season, paving the way for the commencement of the new season,\" Moinisi said. The season will kick off on August 28, with the festive season break scheduled to run from December 19, 2026, to January 8 2027... [truncated, 906 chars total]",
  "keywords": ["New", "FNB", "Premiership", "season", "starts", "next", "week"],
  "inLanguage": "en-US",
  "author": "staff writer",
  "dateCreated": "2026-08-19T14:37:00+02:00",
  "datePublished": "2026-08-19T14:37:00+02:00",
  "dateModified": "2026-08-19T14:36:09+02:00",
  "thumbnailUrl": "https://www.mmegi.bw/mmegi/uploads/images/2026/08/19/178093.jpg",
  "image": "https://www.mmegi.bw/mmegi/uploads/images/2026/08/19/178093.jpg",
  "publisher": {
    "@type": "Organization",
    "name": "Mmegi",
    "url": "https://mmegi.bw",
    "sameAs": ["https://www.facebook.com/MmegiOnline", "https://twitter.com/MmegiOnline", "https://www.youtube.com/user/Mmegionline"],
    "logo": { "@type": "ImageObject", "url": "https://www.mmegi.bw/theme_mmegi/images/schema_image.jpg", "width": 180, "height": 96 }
  },
  "copyrightHolder": { "@type": "Organization", "name": "Mmegi", "url": "https://mmegi.bw" },
  "canonicalUrl": "https://www.mmegi.bw/sports/new-fnb-premiership-season-starts-next-week/news"
}
```

**Latest headlines mode** — real captured output (one record per headline):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T03:01:45Z",
  "title": "South Africa builds Africa's healthcare supply chains as USD 2 billion flows into the sector",
  "link": "https://www.mmegi.bw/news/south-africa-builds-africas-healthcare-supply-chains-as-usd-2-billion-flows-into-the-sector/news",
  "description": "In February 2026, African Union (AU) leaders committed to fully operationalising APPM as a strategic \"Buy African\" initiative through demand aggregation , market shaping...",
  "author": "correspondent",
  "pubDate": "Tue, 25 Aug 2026 12:40:00 +0200",
  "thumbnailUrl": "https://www.mmegi.bw/mmegi/uploads/images/2026/08/25/178553.jpg",
  "imageUrl": "https://www.mmegi.bw/mmegi/uploads/images/2026/08/25/178553.jpg"
}
```

**Not-found article** — real captured output (a nonexistent article slug returns a real 404 page, mapped to a clean error record):

```json
{
  "_input": "https://www.mmegi.bw/news/this-slug-does-not-exist-xyz123/news",
  "_source": "none",
  "_scrapedAt": "2026-08-26T03:01:45Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record: `S1-jsonld` or `S2-rss`. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `keywords` | array | Comma-separated tag list from the page (article mode only — observed to just repeat the headline's words, not curated topics). |
| `author` | string | Byline — often a generic "correspondent"/"staff writer", but real reporter names also appear. |
| `datePublished` / `dateModified` / `dateCreated` | string | ISO-8601 timestamps (article mode only). |
| `image` / `thumbnailUrl` | string | Lead image URL(s). |
| `publisher` / `copyrightHolder` | object | Raw publisher metadata (article mode only). |
| `canonicalUrl` | string | The site's own canonical URL for the article (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | Publish date from the RSS feed (latest mode). |
| `imageUrl` | string | Lead image URL from the RSS feed (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or nonexistent article).
