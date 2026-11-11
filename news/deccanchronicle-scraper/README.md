# Deccan Chronicle Scraper

Extract full article text or the newest headlines from Deccan Chronicle (South India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, topics, section, byline, and publish/update dates
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
    "https://www.deccanchronicle.com/southern-states/telangana/suryapet-road-accident-6-killed-20-severely-injured-as-private-bus-hits-stationary-dcm-near-kodad-1982345"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the site-wide feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output, truncated for readability):

```json
{
  "_input": "https://www.deccanchronicle.com/southern-states/telangana/suryapet-road-accident-6-killed-20-severely-injured-as-private-bus-hits-stationary-dcm-near-kodad-1982345",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T02:09:03Z",
  "@type": "NewsArticle",
  "headline": "Suryapet Road Accident: CM Revanth Reddy Directs Best Medical Care for Injured",
  "description": "The impact was so severe that the front portion of the bus was completely mangled, leaving several passengers trapped inside. ",
  "articleBody": "Suryapet: Telangana Chief Minister A. Revanth Reddy expressed deep condolences to the families of those who lost their lives in the Suryapet road accident.He directed the Chief Secretary to ensure that the injured receive the best possible medical treatment. ... Further details are awaited.",
  "keywords": "Kodad Road Accident, Suryapet Road Accident, Telangana, Telangana News, Telangana Special News, Road Accident, Revanth Reddy",
  "about": [
    { "@type": "Thing", "name": "Suryapet" },
    { "@type": "Thing", "name": "Telangana" },
    "... 4 more"
  ],
  "articleSection": "Telangana",
  "genre": "Telangana",
  "author": [
    {
      "@type": "Person",
      "name": "DC Correspondent",
      "url": "https://www.deccanchronicle.com/byline/dc-correspondent-1",
      "jobTitle": "Editor"
    }
  ],
  "image": {
    "@type": "ImageObject",
    "contentUrl": "https://www.deccanchronicle.com/h-upload/2026/08/26/2081237-road-accident.webp",
    "height": 900,
    "width": 1500
  },
  "datePublished": "2026-08-26T07:09:51+05:30",
  "dateModified": "2026-08-26T07:34:44+05:30",
  "url": "https://www.deccanchronicle.com/southern-states/telangana/suryapet-road-accident-6-killed-20-severely-injured-as-private-bus-hits-stationary-dcm-near-kodad-1982345"
}
```

**Latest headlines mode** — one record per headline (real output, truncated):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:08:32Z",
  "title": "Panama Declares Emergency Over El Niño",
  "link": "https://www.deccanchronicle.com/world/panama-declares-emergency-over-el-nio-1982346",
  "guid": "https://www.deccanchronicle.com/world/panama-declares-emergency-over-el-nio-1982346",
  "pubDate": "Wed, 26 Aug 2026 02:04:14 GMT",
  "description": "Interior Minister Dinoska Montalvo said the emergency status would allow authorities \"to be prepared for what may come with El Nino,\" which has fueled a severe drought that is ravaging harvests, sparking fears of famine.",
  "category": "World",
  "creator": "AFP",
  "contentEncoded": "<figure> <img width='1088' height='726' src='https://www.deccanchronicle.com/h-upload/2026/08/26/2081240-screenshot-2026-08-26-at-140348.webp'/><figcaption></figcaption></figure><p><b>Panama City</b>:Panama on Tuesday became the latest Central American country ... </p>"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek. |
| `keywords` | string | Comma-separated topic tags (article mode only). |
| `about` | array | Topic entities the article is tagged with (article mode only). |
| `author` / `creator` | array / string | Byline — a named reporter or a wire-service credit (PTI, AFP, AP, ANI). `author` in article mode, `creator` in latest mode. |
| `articleSection` / `category` | string | Section name. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `contentEncoded` | string | Full article HTML (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).
