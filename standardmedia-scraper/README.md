# The Standard (Kenya) Scraper

Extract full article text or the newest headlines from The Standard (standardmedia.co.ke), one of Kenya's oldest daily newspapers — no account or subscription needed.

## Why use this actor

- No account or login required — no hard paywall was found for HTTP access (see `CRAWLING_METHOD.md` for the full paywall-metadata-vs-enforcement finding)
- Full article text included, not just a summary — headline, category, publish/modified dates, author, lead image, and the complete article body
- Handles two different site templates automatically: most sections embed the full body directly in the page's structured data; the `evewoman` lifestyle section needs an HTML fallback, and this actor detects and switches between them per article
- Also fetches the newest headlines straight from the site's Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads The Standard's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.standardmedia.co.ke/crime-and-justice/article/2001554718/eacc-arrests-kitui-county-chief-officer-over-sh1748m-procurement-fraud"
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

**Article mode, main template** — real captured output (`_source: "S1-jsonld"`, truncated for readability):

```json
{
  "_input": "https://www.standardmedia.co.ke/crime-and-justice/article/2001554718/eacc-arrests-kitui-county-chief-officer-over-sh1748m-procurement-fraud",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T00:55:00Z",
  "articleId": "2001554718",
  "headline": "EACC arrests Kitui County Chief Officer over Sh17.48m procurement fraud",
  "description": null,
  "articleBody": "Kitui County Chief Officer Gladys Mami Kivoto and five company directors arrested by EACC. [Joh Muia, Standard]\r\n\r\nThe Ethics and Anti-Corruption Commission (EACC) has arrested Kitui County Chief Officer Gladys Mami Kivoto and five company directors over alleged conflict of interest and procurement irregularities involving Sh17.48 million contracts.\r\nIn a statement on Thursday, EACC CEO Abdi Mohamud said investigations found that Kivoto... [truncated, 1903 chars total]",
  "articleSection": ["Crime and Justice"],
  "category": "Crime and Justice",
  "author": [{ "@type": "Person", "name": "John Muia", "url": "https://www.standardmedia.co.ke/author/john-muia" }],
  "datePublished": "2026-08-06T16:49:15+03:00",
  "dateModified": "2026-08-06T16:49:15+03:00",
  "image": ["https://cdn.standardmedia.co.ke/images/articles/thumbnails/ulmpbewPzGX5PZvCV9rcSH6lDuHYrUJQorBatu3I.jpg"],
  "isAccessibleForFree": true,
  "canonicalUrl": "https://www.standardmedia.co.ke/crime-and-justice/article/2001554718/eacc-arrests-kitui-county-chief-officer-over-sh1748m-procurement-fraud"
}
```

**Article mode, evewoman template** — real captured output (`_source: "S2-html"`, HTML fallback since this section's structured data has no article text field):

```json
{
  "_input": "https://www.standardmedia.co.ke/evewoman/article/2001555613/are-you-wearing-the-right-panties",
  "_source": "S2-html",
  "_scrapedAt": "2026-08-26T00:55:00Z",
  "articleId": "2001555613",
  "headline": "Are you wearing the right panties",
  "description": "But style isnt the only thing to consider Did you know that the fabric of your panties can affect both comfort and health",
  "articleBody": "We all know the feeling: your favourite dress is on; your shoes are perfect and your hair is exactly how you want it. You're ready to go, until something feels off.\n\nMaybe it's a visible panty line, a little chafing, or simply the nagging discomfort of underwear that doesn't quite feel right... [truncated, 3070 chars total]",
  "articleSection": ["Wellness"],
  "category": "Wellness",
  "author": { "@type": "Person", "name": "Jael Wakesho ", "url": "https://www.standardmedia.co.ke/evewoman/author/5402/jael-wakesho" },
  "datePublished": "2026-08-18T00:00:00+03:00",
  "dateModified": "2026-08-18T00:00:00+03:00",
  "image": { "@type": "ImageObject", "url": "https://cdn.standardmedia.co.ke/images/articles/thumbnails/TLSdXEr4tTuD3mI6dw8wAljPpQnfyf724oDGICH4.jpg", "height": 500, "width": 800 },
  "isAccessibleForFree": null,
  "canonicalUrl": "https://www.standardmedia.co.ke/evewoman/wellness/article/2001555613/are-you-wearing-the-right-panties"
}
```

**Latest headlines mode** — real captured output (one record per headline):

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T00:54:50Z",
  "articleId": "2001556152",
  "title": "Inside Sh1b NCIC strategy to ensure peaceful elections",
  "link": "https://www.standardmedia.co.ke/national/article/2001556152/inside-sh1b-ncic-strategy-to-ensure-peaceful-elections",
  "section": "national",
  "publicationDate": "2026-08-26",
  "language": "en",
  "lastmod": "2026-08-26",
  "imageUrl": "https://cdn.standardmedia.co.ke/images/articles/thumbnails/v20n61nlW8AtwuiwV46EZ7O5WpiIvjnoSEmXfoHC.jpg",
  "imageCaption": "NCIC's Sh1 billion \"Uchaguzi Bila Noma\" strategy seeks to prevent violence in Kenya's 2027 elections by rebuilding public trust, engaging vulnerable groups and countering digital misinformation."
}
```

**Not-found article** — real captured output (an out-of-range numeric article ID redirects to the homepage instead of returning a real 404; the actor detects this and still emits a clean error record):

```json
{
  "_input": "https://www.standardmedia.co.ke/national/article/2001999999/this-article-does-not-exist-xyz",
  "_source": "none",
  "_scrapedAt": "2026-08-26T00:55:01Z",
  "_error": "not_found",
  "_errorDetail": "redirected to homepage"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record: `S1-jsonld`, `S2-html`, or `S2-sitemap`. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `articleId` | string | Internal numeric article ID, from the URL's `/article/<id>/` segment. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary — present on some sections (e.g. evewoman), null on others. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `articleSection` / `category` | array / string | Raw section list from the site, and a plain-string convenience field (first entry). |
| `author` | object/array | Byline — shape varies by template (list of Person objects on most sections, a single Person object on evewoman). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `image` | array/object | Lead image — shape varies by template (list of URL strings on most sections, an ImageObject on evewoman). |
| `isAccessibleForFree` | boolean | Paywall-metadata flag — observed both `true` and `false` but did not affect whether the full body was returned (see `CRAWLING_METHOD.md`). |
| `canonicalUrl` | string | The site's own canonical URL for the article — sometimes differs from the input URL. |
| `link` | string | Article URL (latest mode). |
| `section` | string | First URL path segment, e.g. `national`, `opinion` (latest mode). |
| `publicationDate` / `lastmod` | string | Publish date from the sitemap (latest mode). |
| `language` | string | Sitemap-declared language code (latest mode). |
| `imageUrl` / `imageCaption` | string | Lead image from the sitemap entry (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or out-of-range article).
