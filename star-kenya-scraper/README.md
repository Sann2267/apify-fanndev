# The Star (Kenya) Scraper

Extract full article text or the newest headlines from The Star (the-star.co.ke), a leading Kenyan daily newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — even articles marked "premium" on the site return their full text, not just a teaser
- Full article text included, not just a summary — headline, section, publish date, author, lead image, and the complete article body
- Also fetches the newest headlines straight from the site's own article index, without visiting each story individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads The Star's own article index and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.the-star.co.ke/news/2026-08-26-iebc-expands-diaspora-voting-to-26-countries-ahead-of-2027-polls"
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

**Article mode, ordinary article** — real captured output (truncated for readability):

```json
{
  "_input": "https://www.the-star.co.ke/news/2026-08-26-iebc-expands-diaspora-voting-to-26-countries-ahead-of-2027-polls",
  "_source": "S1-flight+html",
  "_scrapedAt": "2026-08-26T02:23:26Z",
  "headline": "IEBC expands diaspora voting to 26 countries ahead of 2027 polls",
  "description": null,
  "articleBody": "IEBC chairman Erastus Ethekon joins other leaders and the National Cohesion and Integration Commission during the launch of the 2027 Roadmap to a Violence-Free General Election on August 25, 2026\n\nThe electoral commission has expanded diaspora voter registration from 12 to 26 countries ahead of the 2027 General Election... [truncated, 4600+ chars total]",
  "section": "news",
  "subsection": null,
  "slug": "iebc-expands-diaspora-voting-to-26-countries-ahead-of-2027-polls",
  "author": { "@type": "Person", "name": "ELIUD KIBII" },
  "datePublished": "2026-08-26T04:57:00+0300",
  "image": [{ "@type": "ImageObject", "url": "https://cdn.radioafrica.digital/image/2026/08/4913993e-4c08-4ad2-8fa6-73c37185b353.webp", "author": "", "height": "", "width": "" }],
  "isAccessibleForFree": null,
  "paywallSelector": null,
  "canonicalUrl": "https://www.the-star.co.ke/news/2026-08-26-iebc-expands-diaspora-voting-to-26-countries-ahead-of-2027-polls"
}
```

**Article mode, marked "premium"** — real captured output. Note the full text is still returned in full, just like an ordinary article:

```json
{
  "_input": "https://www.the-star.co.ke/news/2026-08-26-gachagua-ill-confine-ruto-kindiki-to-their-political-backyards",
  "_source": "S1-flight+html",
  "_scrapedAt": "2026-08-26T02:23:28Z",
  "headline": "Gachagua: I'll confine Ruto, Kindiki to their political backyards",
  "description": null,
  "articleBody": "DCP leader Rigathi Gachagua has sustained his offensive against President William Ruto and Deputy President Kithure Kindiki, declaring he will confine them to their respective backyards... [truncated, 3600+ chars total]",
  "section": "news",
  "subsection": null,
  "slug": "gachagua-ill-confine-ruto-kindiki-to-their-political-backyards",
  "author": { "@type": "Person", "name": "ELIUD KIBII" },
  "datePublished": "2026-08-26T04:56:00+0300",
  "image": [{ "@type": "ImageObject", "url": "https://cdn.radioafrica.digital/image/2026/08/d7774333-e08a-4691-a51b-2f998a90a0aa.webp", "author": "", "height": "", "width": "" }],
  "isAccessibleForFree": false,
  "paywallSelector": ".premium-content",
  "canonicalUrl": "https://www.the-star.co.ke/news/2026-08-26-gachagua-ill-confine-ruto-kindiki-to-their-political-backyards"
}
```

**Latest headlines mode** — real captured output (one record per headline):

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T02:23:29Z",
  "title": "Mps Grill Ps Over Delayed Wajir Airport Land Payout",
  "link": "https://www.the-star.co.ke/news/2026-08-25-mps-grill-ps-over-delayed-wajir-airport-land-payout",
  "section": "news",
  "subsection": null,
  "date": "2026-08-25",
  "lastmod": "2026-08-25T18:50:56.000Z"
}
```

**Not-found article** — real captured output (a nonexistent story URL quietly falls back to the site's homepage template instead of a real "not found" page; the actor detects this and still emits a clean error record):

```json
{
  "_input": "https://www.the-star.co.ke/news/2026-08-26-this-article-does-not-exist-xyz123",
  "_source": "none",
  "_scrapedAt": "2026-08-26T02:23:28Z",
  "_error": "not_found",
  "_errorDetail": "generic homepage-shell template, no flight jsonLd"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record: `S1-flight+html` or `S2-sitemap`. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. `title` (latest mode) is derived from the story's own URL and is a close but not always word-for-word match to `headline`. |
| `description` | string | Short summary — observed empty on every article sampled from this source. |
| `articleBody` | string | Full plain-text article content (article mode only). Can be empty for a small number of image-only story types (e.g. editorial cartoons). |
| `section` / `subsection` | string | The site's own category, e.g. `news`, `business`, `sports`, `opinion`, and (where present) a more specific subsection like `world`, `football`, `cartoon`. |
| `slug` | string | The story's URL slug. |
| `author` | object | Byline — the writer's name. |
| `datePublished` | string | ISO-8601 publish timestamp (article mode only). |
| `image` | array | Lead image(s) for the story. |
| `isAccessibleForFree` | boolean | Whether the site itself marks this story as free (`false`/`null` = marked premium on the site's own front end — but full text is returned regardless, see above). |
| `paywallSelector` | string | Present only on stories marked premium — an internal detail of how the site visually highlights premium content on its own front end. |
| `canonicalUrl` | string | The site's own canonical URL for the article. |
| `link` | string | Article URL (latest mode). |
| `date` / `lastmod` | string | Publish date (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or non-existent article).
