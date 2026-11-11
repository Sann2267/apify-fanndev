# Zambia Daily Mail Scraper

Extract full article text or the newest headlines from Zambia Daily Mail (daily-mail.co.zm), Zambia's state-owned national daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, category/tags, publish/modified dates, lead image, and the full article body
- Also fetches the newest headlines from the site's "Headlines" section, with pagination support for larger batches
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor reads the story page once to find the site's own internal article ID, then queries the site's structured data API for that ID to pull out the full text and every publicly available detail about the story. If that fails, it falls back to reading the story page directly.
3. In latest mode, the actor reads the site's "Headlines" section (with automatic pagination) and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.daily-mail.co.zm/2026/08/21/more-congratulate-hichilema/"
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
  "_input": "https://www.daily-mail.co.zm/2026/08/21/more-congratulate-hichilema/",
  "_source": "S1-wpapi-by-id",
  "_scrapedAt": "2026-08-26T03:12:53Z",
  "id": 5159,
  "slug": "more-congratulate-hichilema",
  "link": "https://www.daily-mail.co.zm/2026/08/21/more-congratulate-hichilema/",
  "headline": "More congratulate Hichilema",
  "description": "MARY LEMBA Lusaka MORE world leaders and prominent Zambians have congratulated President Hakainde Hichilema on his reelection, describing the outcome of the August 13 general election as a demonstration of Zambia's democratic maturity, political stability and commitment to peace. Angolan President João Lourenço has congratulated President Hichilema on his victory, saying the election reflects the […]",
  "articleBody": "MARY LEMBA Lusaka\n\nMORE world leaders and prominent Zambians have congratulated President Hakainde Hichilema on his reelection, describing the outcome of the August 13 general election as a demonstration of Zambia's democratic maturity, political stability and commitment to peace. Angolan President João Lourenço has congratulated President Hichilema on his victory... 8 more paragraphs",
  "date": "2026-08-21T19:57:04",
  "date_gmt": "2026-08-21T19:57:04",
  "modified": "2026-08-21T19:57:04",
  "modified_gmt": "2026-08-21T19:57:04",
  "author": "Website Editor",
  "authorId": 2,
  "authorSlug": "webeditor",
  "authorLink": "https://www.daily-mail.co.zm/author/webeditor/",
  "categories": ["Headlines", "News"],
  "tags": [],
  "featuredImage": {
    "url": "https://www.daily-mail.co.zm/wp-content/uploads/2026/08/HH-COMMISSION.jpg",
    "width": 1620,
    "height": 1080,
    "altText": null
  },
  "guid": "https://www.daily-mail.co.zm/?p=5159",
  "contentProtected": false
}
```

A URL that doesn't match any article gets an error record instead of a payload:

```json
{
  "_input": "https://www.daily-mail.co.zm/2026/01/01/this-article-does-not-exist-zzz123/",
  "_source": "none",
  "_scrapedAt": "2026-08-26T03:12:55Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

**Latest headlines mode** — one record per headline, captured from a real local test run:

```json
{
  "_input": "latest",
  "_source": "S3-archive",
  "_scrapedAt": "2026-08-26T03:12:58Z",
  "postId": 5159,
  "title": "More congratulate Hichilema",
  "link": "https://www.daily-mail.co.zm/2026/08/21/more-congratulate-hichilema/",
  "author": "Website Editor",
  "authorLink": "https://www.daily-mail.co.zm/author/webeditor/",
  "pubDate": "August 21, 2026",
  "categories": ["Headlines", "News"],
  "description": "MARY LEMBA Lusaka MORE world leaders and prominent Zambians have congratulated President Hakainde Hichilema on his reelection, describing the outcome of the August 13 general election as a demonstration of…",
  "thumbnail": "https://www.daily-mail.co.zm/wp-content/uploads/2026/08/HH-COMMISSION.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record: `S1-wpapi-by-id` (structured data API, primary), `S2-html` (fallback), or `S3-archive` (latest mode). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `id` / `slug` | integer/string | Internal post ID and URL slug (article mode via `S1-wpapi-by-id` only). |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (not available on the rare `S2-html` fallback path). |
| `articleBody` | string | Full plain-text article content, paragraphs separated by a blank line. Not included in latest mode — use article mode on the `link` for full text. |
| `date` / `date_gmt` / `modified` / `modified_gmt` | string | Publish/modified timestamps. This site's clock is set to UTC, so `date` and `date_gmt` are identical. |
| `author` | string | Byline name — almost always the generic "Website Editor" account; the real reporter's name (e.g. "MARY LEMBA, Lusaka") is written into the first line of the article body instead, not exposed as separate structured data on this site. |
| `authorSlug` / `authorLink` | string | Author's site archive slug/URL. |
| `categories` / `tags` | array | Category and tag names attached to the post. |
| `featuredImage` | object | Lead image `url`/`width`/`height`/`altText` (article mode). |
| `thumbnail` | string | Lead image URL (latest mode). |
| `guid` | string | Internal GUID URL. |
| `contentProtected` | boolean | Site's own paywall flag — always `false` in every article sampled (no paywall on this site). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | Plain-text publish date, e.g. "August 21, 2026" (latest mode; no time-of-day shown on the listing page). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a URL that doesn't match any article).

## Known limits

- Byline data is thin: the site only has two generic author accounts ("Website Editor", "webmaster"). Real reporter names appear as free text inside the article body, not as structured author metadata.
- `latest` mode returns headlines + summaries, not full article text (fetching full text for every headline would multiply the request count). Use `article` mode on the returned `link` for the complete story.
- No paywall was found anywhere on this site during testing.
