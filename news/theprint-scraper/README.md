# ThePrint India Scraper

Extract full article text or the newest headlines from The Print (theprint.in), an Indian digital-first news outlet covering politics, policy, defence, and world news — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publisher, section tags, keywords, publish/modified dates, thumbnail included
- Also fetches the newest headlines straight from the site's Google News sitemap
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://theprint.in/go-to-pakistan/pakistan-army-officer-student-protest-journalists/3023799/"
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

**Article mode** — one record per URL (real output, captured during testing; `articleBody` truncated here for readability):

```json
{
  "_input": "https://theprint.in/go-to-pakistan/pakistan-army-officer-student-protest-journalists/3023799/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T11:21:52Z",
  "headline": "Pakistan Army officer fires gun at student protest. Is this how it is now, journalists ask",
  "description": "Pakistanis question why an armed military officer was present at a university protest. Others portray him as a ‘Superman’.",
  "articleBody": "New Delhi: A Pakistan Army officer walked around in an Islamabad college campus brandishing his gun at protesting students . Pakistanis are calling it Army overreach , and demanding that the officer face strict action.\n\nThe incident took place at Sarhad University Monday amid student demonstrations over higher fees, departmental leadership, and a lack of regularly scheduled classes... (4455 chars total)",
  "author": "Debdutta Chakraborty",
  "publisher": "ThePrint",
  "articleSection": ["Go To Pakistan"],
  "keywords": ["Pakistan", "Pakistan Army", "Pakistan protest"],
  "datePublished": "2026-08-24T16:19:03+00:00",
  "dateModified": "2026-08-24T16:19:03+00:00",
  "thumbnailUrl": "https://staticprintenglish.theprint.in/wp-content/uploads/2026/08/pakistan-army-officer-student-protest.jpg",
  "wordCount": 738,
  "commentCount": 0
}
```

**Latest headlines mode** — one record per headline (real output):

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T11:22:01Z",
  "title": "Chirag Paswan’s LJP (RV) appoints Janardan Paswan as Jharkhand unit president",
  "link": "https://theprint.in/india/chirag-paswans-ljp-rv-appoints-janardan-paswan-as-jharkhand-unit-president/3025474/",
  "pubDate": "2026-08-26T16:48:07+05:30",
  "keywords": "PTI wire",
  "image": "https://theprint.in/wp-content/uploads/2023/06/theprint_default_image_new.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld+html` or `S2-sitemap`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary, from the page's meta description (article mode only; sometimes `null` on wire-sourced pieces with no upstream description). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline, comma-joined if multiple authors (article mode only). |
| `publisher` | string | Site name, `"ThePrint"` (article mode only). |
| `articleSection` | array | Section tags (article mode only). |
| `keywords` | array/string | Keyword tags — e.g. `"reuters wire"`/`"PTI wire"` on wire-sourced pieces (article mode: array; latest mode: string). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `thumbnailUrl` | string | Lead image URL (article mode only). |
| `wordCount` | number | Upstream-computed word count as of scrape time (article mode only). |
| `commentCount` | number | Upstream comment count as of scrape time (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | ISO-8601 publish timestamp from the news sitemap (latest mode). |
| `image` | string | Lead image URL, from the news sitemap (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed: `"not_article"` for a valid page that isn't a news article (e.g. a static page), or `"http_<code>"` / `"blocked_or_transient"` for a transient site/network issue or an invalid/never-existed article URL.

## Known limits

- ThePrint sits behind a CDN bot check that gates on whether the page is already cached at the edge, not on the requester's fingerprint. Most previously-published article URLs fetch reliably, but success genuinely depends on how much real reader traffic that specific article/edge has had — confirmed during cloud testing that a lower-traffic article can consistently fail through Apify's proxy network even while succeeding from another network path, and vice versa. Retrying a failed URL later (giving the CDN time to populate that cache) is the only fix — there's no code-side workaround. The very newest articles (published in roughly the last few minutes) are the most likely to transiently fail. `latest` mode is unaffected, since it reads the sitemap directly and never opens article pages.
- A fabricated or already-deleted article URL cannot be distinguished from a real article the CDN hasn't cached yet — both report `_error: "blocked_or_transient"` rather than a clean "not found".
- No paywall was found on any article sampled — ThePrint is a free, open-access site.
