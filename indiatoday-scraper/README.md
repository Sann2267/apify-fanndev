# India Today Scraper

Extract full article text, video-story details, or the newest headlines from India Today (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also works on India Today's video-story pages
- Also fetches the newest headlines from India Today's site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article or video URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text (or, for video pages, the video's caption/recap) and every publicly available detail about the story.
3. In latest mode, the actor reads India Today's site-wide "Latest Stories" feed and returns the newest headlines across every section — news, business, sports, entertainment, and more.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.indiatoday.in/business/story/are-banks-closed-today-for-id-e-milad-2980132-2026-08-26"
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
| `mode` | string | `"article"` (default) — extract one or more article/video URLs. `"latest"` — fetch the newest headlines from the site-wide feed. |
| `url` | string | A single article or video URL. Used in article mode. |
| `urls` | array | Multiple article/video URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many pages to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.indiatoday.in/business/story/are-banks-closed-today-for-id-e-milad-2980132-2026-08-26",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T06:41:06Z",
  "@type": "NewsArticle",
  "headline": "Are banks closed today for Id-E-Milad?",
  "articleSection": "Business",
  "description": "Bank holidays are not uniform across India A branch may be closed in one city while remaining open in another on the same day",
  "keywords": "bank holiday August 26 2026, RBI holiday calendar, Onam bank holiday, Id-E-Milad bank holiday, ...",
  "datePublished": "2026-08-26T12:01:17+05:30",
  "dateModified": "2026-08-26T12:01:17+05:30",
  "articleBody": "Planning a quick trip to the bank today? It may be worth checking the holiday calendar before stepping out. Several bank branches across India are closed on Wednesday, August 26, due to regional festivals ... - EndsPublished By: Jasmine anandPublished On: Aug 26, 2026 12:01 IST",
  "publisher": { "@type": "Organization", "name": "India Today", "sameAs": "https://www.indiatoday.in/", "logo": { "url": "https://akm-img-a-in.tosshub.com/indiatoday/images/mediamanager/itlogo.png" } },
  "author": { "@type": "Person", "name": "India Today Business Desk", "url": "https://www.indiatoday.in/author/india-today-business-desk" },
  "image": { "@type": "ImageObject", "url": "https://akm-img-a-in.tosshub.com/indiatoday/images/story/202608/bank-holiday-263012130-16x9_0.png?VersionId=tKmwXSCW7ozQNpISkV6iIUbnd5puqES4&size=1280:720", "width": "1280", "height": "720" }
}
```

**Article mode — video-story URL** (e.g. `.../india/video/...`): same `NewsArticle` shape, but no `articleBody` — only a `description` recap:

```json
{
  "_input": "https://www.indiatoday.in/india/video/iit-delhi-msc-student-suicide-police-file-abetment-case-as-campus-protests-intensify-ytvd-2980037-2026-08-26",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T06:41:06Z",
  "@type": "NewsArticle",
  "headline": "IIT Delhi MSc Student Suicide: Police File Abetment Case As Campus Protests Intensify - India Today",
  "articleSection": "India",
  "datePublished": "2026-08-26T07:58:52+05:30",
  "author": { "@type": "Person", "name": "India Today Video Desk", "url": "https://www.indiatoday.in/author/india-today-video-desk" },
  "description": "Delhi Police have registered a case of abetment to suicide against unknown persons following the death by suicide of a thirty-one-year-old Master of Science physics student at the Indian Institute of Technology Delhi campus. ..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T06:41:07Z",
  "title": "No more full Vande Mataram in Karnataka: CM Shivakumar stands by Congress stance",
  "link": "https://www.indiatoday.in/india/karnataka/story/will-only-sing-two-stanzas-of-vande-mataram-karnataka-cm-dk-shivakumar-says-will-stand-by-congress-party-stan-2980127-2026-08-26?utm_source=rss",
  "pubDate": "Wed, 26 Aug 2026 11:42:51 +0530",
  "description": "<a href=\"...\"> <img ... src=\"https://akm-img-a-in.tosshub.com/indiatoday/images/story/202608/dk-shivakumar-at-india-today-roundtable-261642286-16x9_0.jpeg\"> </a> No more full Vande Mataram in Karnataka CM Shivakumar stands by Congress stance"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld`, `S1b-jsonld-video`, or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article/video headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content — present on plain article pages only. Video-story pages have no `articleBody`, just a `description` recap. Ends with a CMS-appended `"- EndsPublished By: ... Published On: ..."` boilerplate tail. |
| `description` | string | Article summary/dek (article mode), video recap (video mode), or raw HTML-wrapped recap (latest mode — contains an `<a><img>...</a>` fragment, not plain text). |
| `keywords` | string | Comma-separated topic tags (article mode only). |
| `author` | object | Byline — usually a desk credit (e.g. "India Today Business Desk") rather than a named reporter. |
| `articleSection` | string | Section/vertical name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps with `+05:30` IST offset (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL, with a trailing `?utm_source=rss` tracking parameter (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
