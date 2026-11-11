# Telangana Today Scraper

Extract full article text or the newest headlines from Telangana Today (Telangana, India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, byline, and publish/update dates
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
    "https://telanganatoday.com/new-criminal-laws-to-be-fully-implemented-within-one-year-amit-shah"
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
  "_input": "https://telanganatoday.com/new-criminal-laws-to-be-fully-implemented-within-one-year-amit-shah",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T02:51:22Z",
  "@type": "NewsArticle",
  "headline": "New criminal laws to be fully implemented within one year: Amit Shah",
  "description": "Union Home Minister Amit Shah set a one-year deadline for 100 per cent implementation of India’s three new criminal laws, aiming for criminal case disposal up to the Supreme Court within three years and a 25 per cent rise in conviction rates",
  "keywords": "Amit Shah, new criminal laws, BNS, BNSS, BSA, criminal justice, conviction rate, Intelligence Bureau, national security, internal security, narcotics, infiltrators, cyber misinformation",
  "articleBody": "New Delhi: Union Home Minister Amit Shah on Tuesday set a one-year deadline for 100 per cent implementation of the three new criminal laws, saying the move will enable disposal of criminal cases up to the Supreme Court within three years and raise the conviction rate by 25 per cent. ... Further details in the full article.",
  "url": "https://telanganatoday.com/new-criminal-laws-to-be-fully-implemented-within-one-year-amit-shah",
  "datePublished": "2026-08-26 01:02:30 +05:30",
  "dateModified": "2026-08-26 00:40:47 +05:30",
  "dateCreated": "2026-08-26 01:02:30 +05:30",
  "thumbnailUrl": "https://media.telanganatoday.com/wp-content/uploads/2026/08/Amit-Shahs-1.jpg",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://telanganatoday.com/new-criminal-laws-to-be-fully-implemented-within-one-year-amit-shah",
    "image": "https://media.telanganatoday.com/wp-content/uploads/2026/08/Amit-Shahs-1.jpg"
  },
  "image": {
    "@type": "ImageObject",
    "url": "https://media.telanganatoday.com/wp-content/uploads/2026/08/Amit-Shahs-1.jpg",
    "width": "1200",
    "height": "720"
  },
  "author": {
    "@type": "Person",
    "name": "PTI",
    "url": "https://telanganatoday.com/author/PTI"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Telangana Today",
    "url": "https://telanganatoday.com/",
    "logo": { "@type": "ImageObject", "url": "https://media.telanganatoday.com/wp-content/uploads/2022/03/TTlogo-600x60-1.png", "width": 600, "height": 60 }
  }
}
```

**Latest headlines mode** — one record per headline (real output, truncated):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:51:06Z",
  "title": "Telangana HC reinstates judge, sets aside compulsory retirement order",
  "link": "https://telanganatoday.com/telangana-hc-reinstates-judge-sets-aside-compulsory-retirement-order",
  "guid": "https://telanganatoday.com/?p=1576496",
  "pubDate": "Tue, 25 Aug 2026 19:30:28 +0000",
  "description": "The Telangana High Court has set aside the compulsory retirement of a trial court judge, calling the punishment unduly harsh and disproportionate. The court sustained two misconduct charges but ordered his reinstatement without back wages or consequential benefits",
  "category": "Hyderabad",
  "creator": "Telangana Today",
  "contentEncoded": "<figure><img width='768' height='450' src='https://media.telanganatoday.com/wp-content/uploads/2026/08/High-Court-1-2-768x450.jpg' class='attachment-large size-large wp-post-image' alt='Telangana HC reinstates judge, sets aside compulsory retirement order'/></figure><p><strong>By Legal Correspondent</strong></p><p><strong>Hyderabad</strong>: A division bench of the Telangana High Court comprising Justices P Sam Koshy and Narsing Rao Nandikonda has set aside a 2018 compulsory retirement order ... </p>"
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
| `author` / `creator` | object / string | Byline — a named reporter or a wire-service credit (PTI, ANI). `author` in article mode, `creator` in latest mode. |
| `category` | string | Section name (latest mode). |
| `datePublished` / `dateModified` | string | Publication timestamps, IST (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `contentEncoded` | string | Full article HTML (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).
