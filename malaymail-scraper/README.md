# Malay Mail Scraper

Extract full article text or the newest headlines from Malay Mail (malaymail.com), a free, digital-first Malaysian news outlet — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, real byline, section, publish/modified dates, lead image
- Also fetches the newest headlines from the site's headline feed, complete with full article text for each headline (not just a teaser)
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories, each with full article text included.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.malaymail.com/news/malaysia/2026/08/26/bmw-driver-dies-after-crashing-into-parked-cars-in-bukit-mertajam-two-others-hurt/232658"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed carries 50 items per fetch). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real capture, truncated here for readability):

```json
{
  "_input": "https://www.malaymail.com/news/malaysia/2026/08/26/bmw-driver-dies-after-crashing-into-parked-cars-in-bukit-mertajam-two-others-hurt/232658",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T02:58:30Z",
  "keywords": "Bukit Mertajam  ,Jalan Baru  ,Taman Pauh  ,Penang Fire and Rescue  ,BMW  ,Seberang Jaya Hospital",
  "headline": "BMW driver dies after crashing into parked cars in Bukit Mertajam, two others hurt",
  "description": "BUKIT MERTAJAM, Aug 26 — A man was killed and two others, including a pedestrian, were injured in an accident involving three cars on Jalan Baru in Taman Pauh here early...",
  "articleSection": "Malaysia",
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "inLanguage": "en",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://www.malaymail.com/news/malaysia/2026/08/26/bmw-driver-dies-after-crashing-into-parked-cars-in-bukit-mertajam-two-others-hurt/232658"
  },
  "image": {
    "@type": "ImageObject",
    "url": "https://www.malaymail.com/malaymail/uploads/images/2026/08/26/358828.jpg",
    "width": 800,
    "height": 400
  },
  "datePublished": "2026-08-26T10:40:47+08:00",
  "dateModified": "2026-08-26T10:40:40+08:00",
  "speakable": {
    "@type": "SpeakableSpecification",
    "cssSelector": [".article-title", ".article-body"]
  },
  "author": { "@type": "Person", "name": "Malay Mail" },
  "publisher": {
    "@type": "Organization",
    "name": "Malay Mail",
    "alternateName": "Malay Mail Online",
    "sameAs": [
      "https://www.malaymail.com",
      "https://www.facebook.com/malaymaildotcom",
      "https://twitter.com/malaymail",
      "... 2 more"
    ],
    "logo": { "@type": "ImageObject", "url": "https://www.malaymail.com/theme_malaymail/images/malaymail/logo-structured.png", "width": 238, "height": 60 }
  },
  "content": "<p>BUKIT MERTAJAM, Aug 26 — A man was killed and two others, including a pedestrian, were injured in an accident involving three cars on Jalan Baru in Taman Pauh here early today.</p><p>Penang Fire and Rescue Department assistant director of operations John Sagun Francis, in a statement today, said the department received a distress call about the crash at 2.31 am, before a team arrived at the scene nine minutes later.</p> ... (full HTML, truncated) ...",
  "articleBody": "BUKIT MERTAJAM, Aug 26 — A man was killed and two others, including a pedestrian, were injured in an accident involving three cars on Jalan Baru in Taman Pauh here early today.\n\nPenang Fire and Rescue Department assistant director of operations John Sagun Francis, in a statement today, said the department received a distress call about the crash at 2.31 am, before a team arrived at the scene nine minutes later.\n\n... (full plain-text article body, truncated)"
}
```

Note that `author` reflects the real byline where the site has one — an opinion column on the same feed came back with `"author": {"@type": "Person", "name": "Erna Mahyuni"}` instead of the generic `"Malay Mail"` placeholder used on wire/agency copy.

**Latest headlines mode** — one record per headline (real capture, truncated here for readability):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:58:31Z",
  "title": "What ‘Chiikawa’ could teach us about identity and storytelling",
  "link": "https://www.malaymail.com/news/opinion/2026/08/26/what-chiikawa-could-teach-us-about-identity-and-storytelling/232659",
  "creator": "Erna Mahyuni",
  "pubDate": "Wed, 26 Aug 2026 10:47:27 +0800",
  "guid": "https://www.malaymail.com/news/opinion/2026/08/26/what-chiikawa-could-teach-us-about-identity-and-storytelling/232659",
  "description": "AUGUST 26 &mdash; I wonder if Japanese people get tired of the way they&#39;re perceived by some, not as people but curi...",
  "categories": ["Chiikawa", "University of Hiroshima", "Kawaii", "Nagano", "Upin and Ipin", "Bangsa Malaysia"],
  "content": "<p><img src=\"https://www.malaymail.com/malaymail/uploads/images/2026/08/26/358826.jpg\" alt=\"Malay Mail\" /></p><p>AUGUST 26 — I wonder if Japanese people get tired of the way they're perceived by some, not as people but curiosities, like exotic animals.</p> ... (full HTML, truncated) ...",
  "articleBody": "AUGUST 26 — I wonder if Japanese people get tired of the way they're perceived by some, not as people but curiosities, like exotic animals.\n\nSome stereotypes are true — that there is an enduring love and adoption of cuteness in Japan.\n\n... (full plain-text article body, truncated)",
  "image": "https://www.malaymail.com/malaymail/uploads/images/2026/08/26/358826.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (article mode / latest mode respectively). |
| `content` | string | Full article body as raw HTML, ad/embed placeholders stripped out (both modes). |
| `articleBody` | string | Full article body as plain text, paragraphs joined (both modes). |
| `description` | string | Short teaser text (both modes). |
| `articleSection` | string | Site section, e.g. "Malaysia", "World", "Opinion" (article mode only). |
| `keywords` | string | Comma-separated keyword string (article mode only). |
| `datePublished` / `dateModified` | string | Publish/modified timestamps with timezone offset (article mode only). |
| `pubDate` | string | Publish timestamp (latest mode only). |
| `link` / `guid` | string | Article URL (latest mode only). |
| `author` | object | Byline details — real name where the site has one (article mode only). |
| `creator` | string | Byline name only — can be `null` on unbylined wire copy (latest mode only). |
| `categories` | array | List of keyword/tag strings (latest mode only). |
| `image` | object/string | Article mode: `{url, width, height}`. Latest mode: image URL string. |
| `publisher` | object | Publisher details — name, social links, logo (article mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).
