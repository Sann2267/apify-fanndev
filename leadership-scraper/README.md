# Leadership Nigeria Scraper

Extract full article text or the newest headlines from Leadership (leadership.ng), a Nigerian national daily newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords (when available), publish date, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's RSS feed, automatically paginating to get up to 50 at once — and unusually, each headline already comes with the **full article text**, not just a teaser
- Byline and publisher names resolved from Leadership's cross-referenced structured-data metadata, not left as opaque IDs
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed (paginating automatically for larger limits) and returns the newest stories, full text included.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://leadership.ng/davido-wizkid-burna-boy-lead-2026-headies-nominations/"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (auto-paginates the RSS feed). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real captured output):

```json
{
  "_input": "https://leadership.ng/davido-wizkid-burna-boy-lead-2026-headies-nominations/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T03:04:59Z",
  "headline": "Davido, Wizkid, Burna Boy Lead 2026 Headies Nominations",
  "description": "Popular Nigerian music stars Davido, Wizkid, and Burna Boy have secured multiple nominations for the 18th Headies Awards, scheduled to take place in Canada.",
  "articleBody": "Popular Nigerian music stars Davido, Wizkid, and Burna Boy have secured multiple nominations for the 18th Headies Awards, scheduled to take place in Canada.\n\nOrganisers unveiled the nominees for the 2026 edition, with the three major Afrobeats stars competing across top categories including Afrobeats Album of the Year, Best Male Artiste, Song of the Year, and Afrobeats Single of the Year.\n\n... 3 more paragraphs",
  "author": "Zuleihat Chatta",
  "publisher": "Leadership Newspapers",
  "articleSection": "News",
  "keywords": "Davido",
  "datePublished": "2026-08-25T23:50:14+01:00",
  "dateModified": "2026-08-25T23:50:14+01:00",
  "image": "https://leadership.ng/wp-content/uploads/2026/08/Untitled-design-61.jpg"
}
```

**Latest headlines mode** — one record per headline, already including the full story text:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T03:05:56Z",
  "title": "Reno Omokri Urges NBC To Mandate Made-In-Nigeria Clothes, Accents For Newscasters",
  "link": "https://leadership.ng/reno-omokri-urges-nbc-to-mandate-made-in-nigeria-clothes-accents-for-newscasters/",
  "description": "Nigerian author and social commentator Reno Omokri has called on the National Broadcasting Commission (NBC) to mandate Nigerian newscasters and on-air personalities to wear locally made clothing and speak with Nigerian accents. Omokri made the call in a social media post while advocating greater promotion of Nigerian culture and locally produced goods through the country's […]",
  "content": "<p>Nigerian author and social commentator Reno Omokri has called on the National Broadcasting Commission (NBC) to mandate Nigerian newscasters and on-air personalities to wear locally made clothing and speak with Nigerian accents.</p>\n<p>Omokri made the call in a social media post while advocating greater promotion of Nigerian culture and locally produced goods through the country's broadcasting industry.</p>\n... 8 more paragraphs of raw HTML",
  "articleBody": "Nigerian author and social commentator Reno Omokri has called on the National Broadcasting Commission (NBC) to mandate Nigerian newscasters and on-air personalities to wear locally made clothing and speak with Nigerian accents.\n\nOmokri made the call in a social media post while advocating greater promotion of Nigerian culture and locally produced goods through the country's broadcasting industry.\n\n... 8 more paragraphs",
  "pubDate": "Tue, 25 Aug 2026 22:44:02 +0000",
  "categories": ["Entertainment"],
  "author": "Ngozi Ibe",
  "guid": "https://leadership.ng/?p=683301"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode: meta description; latest mode: RSS teaser, truncated with "…"). |
| `articleBody` | string | Full plain-text article content, joined into paragraphs (both modes). |
| `content` | string | Full raw article HTML from the RSS `content:encoded` field (latest mode only). |
| `author` | string | Byline — resolved from the site's structured-data metadata (article mode) or the RSS `dc:creator` (latest mode) — both are real per-article bylines. |
| `publisher` | string | Always `"Leadership Newspapers"` (article mode only). |
| `articleSection` | string | Section, e.g. `"News"`, `"Business"`, `"Entertainment"` (article mode only). |
| `keywords` | string | Keyword tag, when present upstream — not every article has one (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 publish/last-modified timestamps (article mode only). |
| `image` | string | Lead image URL (article mode only — the RSS feed carries no per-item image). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `categories` | array | Category tag(s) from the feed (latest mode). |
| `guid` | string | Internal article ID URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed. This site returns a **soft-404** (HTTP 200 with the homepage's own content) for deleted/never-existed article slugs rather than a real 404 — the actor detects this and reports it as `"_error": "not_found"` just like a real 404 would be.
