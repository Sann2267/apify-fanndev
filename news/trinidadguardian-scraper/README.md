# Trinidad Guardian Scraper

Extract full article text or the newest headlines from the Trinidad Guardian (guardian.co.tt), Trinidad and Tobago's major English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — every sampled article was freely accessible, no paywall enforced
- Full article text included, not just a summary — headline, description, byline (where available), category, and publish/modified dates, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the homepage without visiting each article individually (the site has no RSS feed or sitemap at all)
- Cleans up an invisible text-formatting artifact this site's CMS injects mid-word (soft hyphens) so headlines and body text read normally
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the homepage and returns the newest stories, newest first.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.guardian.co.tt/business/shell-stalls-aphrodite-talks-with-ngc-6.2.2652875.3d3fca7ccb"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the homepage typically carries ~35-40 unique article links at once). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.guardian.co.tt/business/shell-stalls-aphrodite-talks-with-ngc-6.2.2652875.3d3fca7ccb",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-25T17:57:04Z",
  "headline": "Shell stalls Aphrodite talks with NGC",
  "description": "Chairman of the National Gas Company Gerald Ramdeen yesterday said negotiations with Shell are ongoing amid international reports that suggest Shell's Aphrodite natural gas project in Trinidad and Tobago is in doubt.",
  "articleBody": "PETER CHRISTOPHER\n\nSenior Multimedia Reporter\n\npeter.christopher@guardian.co.tt\n\nChairman of the National Gas Company Gerald Ramdeen yesterday said negotiations with Shell are ongoing...",
  "author": "PETER CHRISTOPHER",
  "category": "business",
  "datePublished": "2026-08-25T07:41:43-04:00",
  "dateModified": "Tue, 25 Aug 2026 07:44:17 -0400",
  "createdTimeRaw": "20260825074143",
  "publishDateRaw": "20260825",
  "image": {
    "@type": "ImageObject",
    "url": "http://www.guardian.co.tt/image-3.7570916.928065.20260825114430.283f48354a",
    "width": "1523",
    "height": "1630",
    "caption": "NGC chairman Gerald Ramdeen"
  },
  "isAccessibleForFree": "true"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-html-listing",
  "_scrapedAt": "2026-08-25T17:56:53Z",
  "title": "Police seek public's help to find missing 16-year-old",
  "link": "https://www.guardian.co.tt/news/police-seek-publics-help-to-find-missing-16yearold-6.2.2653026.2fe49e14b2",
  "category": "news",
  "articleId": "2653026"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary from the page's ld+json block (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline name where available — legitimately absent on some opinion columns and wire/desk pieces (article mode only). |
| `category` | string | Section slug parsed from the URL, e.g. `"news"`, `"business"`, `"sports"`, `"opinion"`. |
| `datePublished` | string | ISO-8601 publish timestamp, derived from an HTML field since it isn't in the page's structured data at all (article mode only). |
| `dateModified` | string | Last-modified timestamp exactly as the site emits it (article mode only). |
| `createdTimeRaw` / `publishDateRaw` | string | Raw underlying HTML date strings `datePublished` is derived from, kept for verification (article mode only). |
| `image` | object/string | Lead image (article mode: full object with URL/dimensions/caption; latest mode: not included). |
| `isAccessibleForFree` | string | Upstream paywall metering flag, passed through exactly as the site emits it — a string, not a boolean (article mode only). |
| `link` | string | Article URL (latest mode). |
| `articleId` | string | Numeric content ID parsed from the URL — latest mode sorts by this descending as a best-effort recency proxy, since the site has no publish date in its URLs or any feed to source one from (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or malformed article URL).

## Notes

- This site has no RSS feed or sitemap.xml at all — `latest` mode works by reading the homepage directly.
- Malformed article URLs typically come back as HTTP 400 rather than 404 (the site validates a signed ID/hash pair at the CDN edge) — the actor treats both the same way, as `_error: "not_found"`.
- See `CRAWLING_METHOD.md` for full technical recon notes.
