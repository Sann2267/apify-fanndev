# NDTV Scraper

Extract full article text or the newest headlines from NDTV, India's leading news broadcaster and news portal — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines across all of NDTV's sections in one call, without visiting each article individually
- Works across NDTV's different story formats — plain news articles, video stories, and live-updates blogs
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads NDTV's site-wide news feed and returns the newest stories from across all sections.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.ndtv.com/india-news/kerala-is-now-officially-keralam-centre-notifies-new-name-11958629"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from across NDTV's sections. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.ndtv.com/india-news/kerala-is-now-officially-keralam-centre-notifies-new-name-11958629",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T02:10:23Z",
  "@type": "NewsArticle",
  "headline": "Kerala Is Now Officially &amp;quot;Keralam&amp;quot;, Centre Notifies New Name",
  "description": "The Union Home Ministry has notified the new name for the southern state, effective from August 25, 2026, in line with a law passed by Parliament.",
  "articleBody": "The Union Home Ministry has notified &amp;#039;Keralam&amp;#039; as the new name for the southern state effective Tuesday.In a gazette notification issued on Tuesday, the home ministry said, &amp;ldquo;In exercise of the powers conferred by sub-section (2) of Section 1 of the Kerala (Alteration of Name) Act, 2026 ... [full article continues]",
  "keywords": "Keralam,Kerala name change,Kerala Alteration of Name Act",
  "articleSection": "India News",
  "author": [{ "@type": "Person", "name": "Press Trust Of India", "url": "https://www.ndtv.com/agencies/press-trust-of-india-21" }],
  "datePublished": "2026-08-25T23:42:10+05:30",
  "dateModified": "2026-08-25T23:42:10+05:30",
  "isAccessibleForFree": true
}
```

A video-story page returns the same shape but without `articleBody` (video pages carry a short caption in `description` instead of full article text). A live-updates blog returns a rollup summary in `articleBody` rather than a play-by-play of every individual update.

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:11:15Z",
  "title": "Man Kills Two Sisters In Uttarakhand Days Before Raksha Bandhan",
  "link": "https://www.ndtv.com/india-news/man-kills-two-sisters-in-uttarakhand-days-before-raksha-bandhan-11959122#publisher=newsstand",
  "guid": "https://www.ndtv.com/india-news/man-kills-two-sisters-in-uttarakhand-days-before-raksha-bandhan-11959122#publisher=newsstand",
  "pubDate": "Wed, 26 Aug 2026 05:09:37 +0530",
  "description": "Both sisters died on the spot from their gunshot wounds. (Representational)"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode; absent on video-story pages). |
| `description` | string | Article summary/dek or caption. |
| `keywords` | string | Comma-separated topic tags (article mode only). |
| `author` | array | Byline (article mode only) — often a wire-service credit such as Press Trust Of India. |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article).

## Notes

- Latest mode returns headlines from across all of NDTV's sections in one feed (India, World, Business, and more), most no more than a few minutes old.
- Article text and metadata occasionally contain the site's own text-formatting artifacts (for example `&amp;quot;` appearing instead of a plain quotation mark) — this is carried through exactly as published rather than cleaned up, so you always get the source-of-truth text.
- For best results, use Residential proxies (on by default).
