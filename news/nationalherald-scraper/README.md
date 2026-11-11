# National Herald Scraper

Extract full article text or the newest headlines from National Herald (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines (with full body text) from the site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's `stories.rss` feed and returns the newest stories, already including full body text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.nationalheraldindia.com/politics/bihar-govt-weaponising-police-to-evade-accountability-to-bpsc-protesters-rahul-gandhi"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the site-wide feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability; captured live on 2026-08-27):

```json
{
  "_input": "https://www.nationalheraldindia.com/politics/bihar-govt-weaponising-police-to-evade-accountability-to-bpsc-protesters-rahul-gandhi",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:15:29Z",
  "headline": "Bihar govt weaponising police to evade accountability to students: Rahul",
  "image": {
    "@type": "ImageObject",
    "url": "https://cf-images.assettype.com/nationalherald/2026-08-26/lw2mrwml/bihar-bpsc-protest.jpg?w=1200&h=675&auto=format%2Ccompress&fit=max&enlarge=true",
    "width": "1200",
    "height": "675"
  },
  "url": "https://www.nationalheraldindia.com/politics/bihar-govt-weaponising-police-to-evade-accountability-to-bpsc-protesters-rahul-gandhi",
  "datePublished": "2026-08-26T21:18:33+05:30",
  "publisher": { "@type": "Organization", "@context": "http://schema.org", "id": "" },
  "author": [
    { "@type": "Person", "givenName": "NH Political Bureau", "name": "NH Political Bureau", "url": "https://www.nationalheraldindia.com/author/nh-political-bureau" }
  ],
  "keywords": "BPSC,Rahul Gandhi,Jantar Mantar",
  "thumbnailUrl": "https://cf-images.assettype.com/nationalherald/2026-08-26/lw2mrwml/bihar-bpsc-protest.jpg?w=1200&h=675&auto=format%2Ccompress&fit=max&enlarge=true",
  "articleBody": "&lt;p&gt;Lok Sabha Leader of Opposition Rahul Gandhi on Wednesday, 26 August hit out at the BJP-led Bihar government over student protests ... (full article, ~3,300 characters on this sample -- note: HTML markup is HTML-entity-escaped by upstream, e.g. '&lt;p&gt;' instead of '<p>'; apply html.unescape() yourself for clean HTML/plain text)",
  "dateModified": "2026-08-26T21:18:33+05:30",
  "dateCreated": "2026-08-26T21:18:33+05:30",
  "name": "Bihar govt weaponising police to evade accountability to students: Rahul",
  "articleSection": "POLITICS",
  "alternativeHeadline": "",
  "description": "Lok Sabha LoP backs protesting students as Patna clashes over BPSC exams trigger fresh questions on paper leaks, transparency"
}
```

A record with `_error` instead of article fields means that URL could not be processed, for example:

```json
{
  "_input": "https://www.nationalheraldindia.com/politics/this-slug-does-not-exist-xyz-abc-123456",
  "_source": "none",
  "_scrapedAt": "2026-08-26T17:15:30Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

**Latest headlines mode** — one record per headline (truncated here for readability; captured live on 2026-08-27):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T17:15:15Z",
  "title": "Bihar govt weaponising police to evade accountability to students: Rahul",
  "link": "https://www.nationalheraldindia.com/politics/bihar-govt-weaponising-police-to-evade-accountability-to-bpsc-protesters-rahul-gandhi",
  "guid": "20a494b8-b400-4950-9091-866f102ef2c8",
  "pubDate": "Wed, 26 Aug 2026 21:18:33 +0530",
  "description": "Lok Sabha LoP backs protesting students as Patna clashes over BPSC exams trigger fresh questions on paper leaks, transparency",
  "category": "POLITICS",
  "author": "NH Political Bureau",
  "authorUrl": "/api/author/95480",
  "keywords": "Rahul Gandhi,Jantar Mantar,BPSC",
  "image": "https://cf-images.assettype.com/nationalherald/2026-08-26/lw2mrwml/bihar-bpsc-protest.jpg",
  "thumbnail": "https://cf-images.assettype.com/nationalherald/2026-08-26/lw2mrwml/bihar-bpsc-protest.jpg?w=280",
  "contentEncoded": "<p>Lok Sabha Leader of Opposition Rahul Gandhi on Wednesday, 26 August hit out at the BJP-led Bihar government over student protests, accusing it of using the police as a \"weapon\" to evade accountability.</p><p>His remarks came amid a viral video of a ... (full article as clean HTML, ~3,700 characters on this sample)"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full article content, still as upstream's HTML-entity-escaped HTML (article mode only — see note above). |
| `contentEncoded` | string | Full article body as clean HTML markup (latest mode only). |
| `description` | string | Article summary/dek. |
| `keywords` | string | Comma-separated topic tags. |
| `author` | array / string | Byline — array of Person objects in article mode (often a desk credit like "NH Political Bureau" rather than a named reporter), a plain name string in latest mode. |
| `articleSection` / `category` | string | Section name (e.g. "POLITICS", "Nation"). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `image` | object / string | Lead image — a single `{url, width, height}` object in article mode, a single URL string in latest mode. |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article slug).
