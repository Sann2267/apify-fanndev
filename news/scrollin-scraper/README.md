# Scroll.in Scraper

Extract full article text or the newest headlines from Scroll.in (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines from Scroll.in's Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads Scroll.in's news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://scroll.in/article/1095282/how-dolly-parton-turned-self-aware-artifice-into-authentic-artistry"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the news sitemap. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://scroll.in/article/1095282/how-dolly-parton-turned-self-aware-artifice-into-authentic-artistry",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T17:16:25Z",
  "@type": "NewsArticle",
  "headline": "How Dolly Parton turned self-aware artifice into authentic artistry",
  "description": "To be fake, to push into the sentimental performative aspects of the country genre, became her true autograph – a trace of her originality.",
  "articleBody": "Scrolling through the tributes to Dolly Parton this morning – from the Grand Ole Opry, New York Mayor Zohran Mamdani, queerfluencers and others – I thought to myself: that's her real name? ...",
  "keywords": "dolly parton, dolly parton blonde, dolly parton fake, dolly parton plastic image, Country Music, United States",
  "author": { "@type": "Person", "name": "Rosemary Overell, The Conversation", "sameAs": "https://scroll.in/author/29396" },
  "publisher": { "@type": "Organization", "name": "Scroll.in", "url": "https://scroll.in" },
  "datePublished": "2026-08-26T22:00:00+05:30",
  "dateModified": "2026-08-26T22:00:00.412764+05:30"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:16:13Z",
  "title": "How Dolly Parton turned self-aware artifice into authentic artistry",
  "link": "https://scroll.in/article/1095282/how-dolly-parton-turned-self-aware-artifice-into-authentic-artistry",
  "publication_date": "2026-08-26T22:00:00+05:30",
  "keywords": "Music, dolly parton, dolly parton blonde, dolly parton fake, dolly parton plastic image, Country Music, United States",
  "image": "https://sc0.blr1.cdn.digitaloceanspaces.com/article/215205-gttnhuzxdm-1787736505.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only), assembled from the page's HTML — Scroll.in's structured data does not include the body text itself. |
| `description` | string | Article summary/dek (article mode only). |
| `keywords` | string | Comma-separated topic tags. |
| `author` | object | Byline (article mode only) — a single `{name, sameAs}` object; often "Scroll Staff" for unbylined news items. |
| `datePublished` | string | Publication timestamp (article mode). |
| `dateModified` | string | Last-modified timestamp (article mode). |
| `publication_date` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `image` | string / object | Lead image (an object in article mode, a plain URL in latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or nonexistent article).

## Good to know

- Scroll.in's article URLs embed a numeric story ID — the descriptive text after it doesn't need to be exact for the actor to fetch the right story.
- All sampled content was fully open access — no paywall or login-wall was found blocking article text.
