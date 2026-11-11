# Free Press Journal Scraper

Extract full article text or the newest headlines from Free Press Journal (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines (with full body text) from the site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's `stories.rss` feed and returns the newest stories, already including full body text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.freepressjournal.in/bhopal/mp-nursing-college-case-supreme-court-tells-students-to-ask-colleges-to-face-cbi-probe-exams-allowed-at-cleared-institutions"
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

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.freepressjournal.in/bhopal/man-set-ablaze-by-neighbour-during-eid-e-milad-preparations-in-mps-mauganj",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T02:58:20Z",
  "@type": "NewsArticle",
  "headline": "Man Set Ablaze By Neighbour During Eid-e-Milad Preparations In MPs Mauganj",
  "description": "A man was hospitalised after his neighbour allegedly poured petrol on him and set him ablaze in Madhya Pradesh's Mauganj district during Eid-e-Milad-un-Nabi preparations. The suspect remains at large. A head constable at Laur police station was suspended following allegations of negligence and failure to register the complaint earlier.",
  "articleBody": "Bhopal (Madhya Pradesh): A man was allegedly set on fire after petrol was poured on him by his neighbour ... (full plain-text article, ~900 characters on this sample)",
  "keywords": "mp news,madhya pradesh ,bhopal news,top news,Mauganj news,Eid-e-Milad Preparations,Man Set Ablaze By Neighbour ",
  "articleSection": "Bhopal News",
  "author": [
    { "@type": "Person", "name": "Staff Reporter", "url": "https://www.freepressjournal.in/author/staff-reporter" }
  ],
  "publisher": { "@type": "NewsMediaOrganization", "name": "Free Press Journal", "url": "https://www.freepressjournal.in" },
  "image": [
    "https://media.assettype.com/freepressjournal/2026-08-25/qckdgjcu/2jolPA005nMn0kCLldXDpDZwTS1gIVGhldNmU0BpqHXXhAhczmgDFC4uSqZuuCvjj-3bRvY.jpg"
  ],
  "datePublished": "2026-08-26T07:00:00+05:30",
  "dateModified": "2026-08-25T23:39:01+05:30",
  "isAccessibleForFree": true,
  "inLanguage": "en"
}
```

**Latest headlines mode** — one record per headline (truncated here for readability):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:58:11Z",
  "title": "NEET PG 2026 Admit Card Released: Download Hall Ticket For August 30 Exam; Check Timings, Result Date & Internship Deadline",
  "link": "https://www.freepressjournal.in/education/neet-pg-2026-admit-card-released-download-hall-ticket-for-august-30-exam-check-timings-result-date-internship-deadline",
  "guid": "5573b544-8fa8-4294-8682-8b9978158588",
  "pubDate": "Wed, 26 Aug 2026 02:26:27 +0000",
  "description": null,
  "category": "Education",
  "author": "Simple Vishwakarma",
  "authorUrl": "/api/author/1847445",
  "keywords": "",
  "image": "https://media.assettype.com/freepressjournal/2026-08-26/2l21b8pl/Untitled-design-2026-08-26T075322.832.jpg",
  "thumbnail": "https://media.assettype.com/freepressjournal/2026-08-26/2l21b8pl/Untitled-design-2026-08-26T075322.832.jpg?w=280",
  "contentEncoded": "<p><strong>NEET PG 2026 admit card:</strong> The National Eligibility cum Entrance Test for Postgraduate (NEET PG) 2026 admit card is available on the National Board of Examinations in Medical Sciences' (NBEMS) official website ... (full article body as HTML)</p>"
}
```

A URL that no longer exists or was mistyped returns an error record instead:

```json
{
  "_input": "https://www.freepressjournal.in/thisisnotarealslug-xyz-404-test",
  "_source": "none",
  "_scrapedAt": "2026-08-26T02:58:20Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). Note: article-mode `headline` is sometimes hard-truncated by the source site on longer titles; latest-mode `title` is always full-length. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `contentEncoded` | string | Full article body as HTML markup (latest mode only — this feed carries full text, not just headlines). |
| `description` | string | Article summary/dek (article mode; usually empty in latest mode on this feed). |
| `keywords` | string | Comma-separated topic tags. |
| `author` | array / string | Byline — array of named-reporter objects in article mode, a plain name string in latest mode. |
| `articleSection` / `category` | string | Section name (e.g. "Bhopal News", "Education"). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `image` | array / string | Lead image — list of URLs in article mode, a single URL in latest mode. |
| `isAccessibleForFree` | boolean | Paywall signal (article mode) — always `true` on this outlet's main news content. |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article slug).
