# Times of Zambia Scraper

Extract full article text or the newest headlines from Times of Zambia (times.co.zm), Zambia's oldest daily newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, real author byline, category/tags, publish/modified dates, lead image, and the full article body
- Real author names, not a generic outlet byline — pulled straight from WordPress's own author records
- Also fetches the newest headlines straight from the site's RSS feed, with pagination support for larger batches
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor queries the site's own WordPress data API for each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed (with automatic pagination) and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://times.co.zm/zesco-are-champions/"
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

**Article mode** — one record per URL, captured from a real local test run (truncated here for readability):

```json
{
  "_input": "https://times.co.zm/zesco-are-champions/",
  "_source": "S1-wpapi",
  "_scrapedAt": "2026-08-26T00:58:25Z",
  "id": 236,
  "slug": "zesco-are-champions",
  "link": "https://times.co.zm/zesco-are-champions/",
  "headline": "Zesco are champions",
  "description": "Zesco United won the four-club international pre-season tournament with a perfect record, but coach Mwenya Chipepo said his side struggled in front of goal and needed to improve their attacking play.",
  "articleBody": "Yesterday, Zesco, with new coach Mwenya Chipepo in charge, fended off the attack from Red Arrows, Zambia's representatives in the CAF Confederation Cup to end with seven points.\n\nIn earlier games at this tournament, Zesco beat AS Simba of Tanzania 1-0 before repeating that scoreline against Zambian champions Power Dynamos.\n\n... 8 more paragraphs",
  "date": "2026-08-23T13:28:43",
  "date_gmt": "2026-08-23T11:28:43",
  "modified": "2026-08-23T13:26:06",
  "modified_gmt": "2026-08-23T11:26:06",
  "author": "Shamaoma Musonda",
  "authorSlug": "shamaoma",
  "authorLink": "https://times.co.zm/author/shamaoma/",
  "categories": ["Sport"],
  "tags": ["CAF Confederation", "CAF games", "Power", "Zesco United"],
  "featuredImage": {
    "url": "https://times.co.zm/wp-content/uploads/2026/08/ZESCO-United.jpg",
    "width": 448,
    "height": 467,
    "altText": null
  },
  "guid": "https://times.co.zm/?p=236",
  "contentProtected": false
}
```

A "Video"-category article (real content is a video embed, not text) instead carries a null body with a still-populated description:

```json
{
  "headline": "Watch: Inside ZESCO's Kariba Control Room During Peak Load-Shedding",
  "description": "Our cameras gained rare access to Kariba North Bank's control room as engineers managed Zambia's worst power deficit in years. See how water levels dictate daily schedules affecting millions of households nationwide.",
  "articleBody": null,
  "categories": ["Video"],
  "author": "Times Editor"
}
```

A URL that doesn't match any article gets an error record instead of a payload:

```json
{
  "_input": "https://times.co.zm/this-article-does-not-exist-zzz123/",
  "_source": "none",
  "_scrapedAt": "2026-08-26T00:58:27Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

**Latest headlines mode** — one record per headline, captured from a real local test run:

```json
{
  "_input": "latest",
  "_source": "S3-rss",
  "_scrapedAt": "2026-08-26T00:57:38Z",
  "title": "Zambia scales up twice-yearly PrEP injections",
  "link": "https://times.co.zm/zambia-scales-up-twice-yearly-prep-injections/",
  "author": "Kali Muluzi",
  "guid": "https://times.co.zm/?p=47",
  "pubDate": "Tue, 25 Aug 2026 12:40:56 +0000",
  "description": "Zambia has expanded the rollout of long-acting injectable HIV prevention drug Lenacapavir to 106 public health clinics in 13 high-burden districts, offering an alternative to daily oral PrEP and targeting barriers such as pill fatigue and stigma.",
  "articleBody": "In a historic stride toward eliminating HIV, Zambia has successfully expanded its pioneering rollout of Lenacapavir... 12 more paragraphs",
  "categories": ["Health", "Features", "HIV", "Lenacapavir", "PrEP injections"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record: `S1-wpapi` (WordPress REST API, primary), `S2-jsonld+html` (fallback), or `S3-rss` (latest mode). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `id` / `slug` | integer/string | WordPress post ID and URL slug (article mode via `S1-wpapi` only). |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary. |
| `articleBody` | string | Full plain-text article content, paragraphs separated by a blank line. Can be `null` for video-format articles (see above). |
| `date` / `date_gmt` / `modified` / `modified_gmt` | string | Publish/modified timestamps, local (Africa/Lusaka, UTC+2) and UTC, exactly as WordPress returns them — no timezone suffix on the local pair. |
| `author` | string | Real byline name (WP-API and RSS); the generic `"TIMES OF ZAMBIA"` organization only on the rare `S2` fallback path. |
| `authorSlug` / `authorLink` | string | Author's WordPress archive slug/URL (`S1-wpapi` only). |
| `categories` / `tags` | array | Category and tag names attached to the post. |
| `featuredImage` | object | Lead image `url`/`width`/`height`/`altText`. |
| `guid` | string | WordPress-internal GUID URL. |
| `contentProtected` | boolean | WordPress's own paywall flag — always `false` in every article sampled (no paywall on this site). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC 822 publish timestamp (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a URL that doesn't match any article).
