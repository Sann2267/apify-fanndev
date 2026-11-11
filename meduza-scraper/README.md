# Meduza Scraper

Extract full article text or the newest headlines from Meduza (meduza.io), an independent Russian-language press outlet now operating in exile from Latvia — covers both the original Russian edition and the English edition, no account or subscription needed.

## Why use this actor

- No account or login required — fully free, donation-funded site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs
- Works on both editions with the same input — point it at a `meduza.io/...` (Russian) or `meduza.io/en/...` (English) URL and get the same output shape
- Latest-headlines mode lets you pick which edition's feed to read
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest headlines automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads Meduza's RSS feed (English by default, Russian optional) and returns the newest headlines with a short teaser.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://meduza.io/en/feature/2026/08/25/cia-director-john-ratcliffe-made-an-unannounced-visit-to-moscow-here-s-what-we-know"
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
  "language": "en",
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines. |
| `url` | string | A single article URL. Works for both editions. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `language` | string | `"en"` (default) or `"ru"` — which edition's RSS feed to read in latest mode. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output from a local test run, `articleBody` truncated here for readability):

```json
{
  "_input": "https://meduza.io/en/feature/2026/08/25/cia-director-john-ratcliffe-made-an-unannounced-visit-to-moscow-here-s-what-we-know",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T01:02:42Z",
  "headline": "CIA Director John Ratcliffe made an unannounced visit to Moscow. Here's what we know.",
  "description": "CIA Director John Ratcliffe made an unannounced visit to Moscow. He flew in from Riga aboard a U.S. Air Force Boeing C-17 military transport plane that landed at Vnukovo Airport on the morning of Aug. 25...",
  "articleBody": "CIA Director John Ratcliffe made an unannounced visit to Moscow. He flew in from Riga aboard a U.S. Air Force Boeing C-17 military transport plane that landed at Vnukovo Airport on the morning of Aug. 25. Around 7 p.m., it emerged that the American plane that had brought Ratcliffe had departed Moscow.\n\nRatcliffe is the first CIA director to visit Moscow since 2021. His predecessor, William Burns, traveled there that year amid a Russian military buildup near Ukraine's borders...\n\n[... 7 more paragraphs, AI-translation disclosure notice automatically stripped ...]",
  "author": "Meduza",
  "publisher": "Meduza",
  "datePublished": "2026-08-25T16:59:16Z",
  "dateModified": "2026-08-25T21:31:02Z",
  "image": {
    "@type": "ImageObject",
    "url": "https://meduza.io/imgly/share/1787684047/en/feature/2026/08/25/cia-director-john-ratcliffe-made-an-unannounced-visit-to-moscow-here-s-what-we-know",
    "height": 675,
    "width": 1200
  },
  "inLanguage": "en-US",
  "contentType": "Article"
}
```

Russian-edition articles come back in the same shape (`inLanguage: "ru-RU"`, `contentType: "NewsArticle"` or `"Article"` depending on section):

```json
{
  "_input": "https://meduza.io/news/2026/08/25/umerla-dolli-parton",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T01:02:42Z",
  "headline": "Умерла Долли Партон ",
  "description": "Американская кантри-исполнительница Долли Партон умерла в возрасте 80 лет...",
  "articleBody": "Американская кантри-исполнительница Долли Партон умерла в возрасте 80 лет. О ее смерти сообщил ее племянник Брайан Сивер, пишет The New York Times.\n\nЗа свою более чем 50-летнюю карьеру Долли Партон выпустила 49 альбомов, получила 11 премий «Грэмми»...\n\n[... 3 more paragraphs ...]",
  "author": "Meduza",
  "publisher": "Meduza",
  "datePublished": "2026-08-25T18:09:42Z",
  "dateModified": "2026-08-25T18:35:14Z",
  "image": { "@type": "ImageObject", "url": "https://meduza.io/imgly/share/1787682914/news/2026/08/25/umerla-dolli-parton", "height": 675, "width": 1200 },
  "inLanguage": "ru-RU",
  "contentType": "NewsArticle"
}
```

A `/video/` page (no textual body on the page) degrades gracefully instead of failing:

```json
{
  "_input": "https://meduza.io/video/2026/08/25/ukraina-hochet-razrushit-ekonomiku-rossii-s-pomoschyu-udarov-po-ozon-i-wildberries-eto-realno",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T01:02:11Z",
  "headline": "Украина хочет разрушить экономику России с помощью ударов по Ozon и Wildberries. Это реально?",
  "articleBody": null,
  "contentType": "VideoObject",
  "_warning": "no_body_extracted_non_article_layout"
}
```

**Latest headlines mode** — one record per headline (real output, English edition):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T01:00:33Z",
  "title": "Ousted Ukrainian Defense Minister Mykhailo Fedorov says Ukraine is 'slowly losing' the war against Russia",
  "link": "https://meduza.io/en/news/2026/08/25/ousted-ukrainian-defense-minister-mykhailo-fedorov-says-ukraine-is-slowly-losing-the-war-against-russia",
  "guid": "https://meduza.io/en/news/2026/08/25/ousted-ukrainian-defense-minister-mykhailo-fedorov-says-ukraine-is-slowly-losing-the-war-against-russia",
  "teaser": "<p>Ukraine's leadership has no overall vision for how to win the war against Russia, former Ukrainian Defense Minister Mykhailo Fedorov told Reuters. Corruption and the slow adoption of new technology are also holding the country back, he said.<p>",
  "pubDate": "Tue, 25 Aug 2026 22:12:44 +0300"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-html` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string \| null | Full plain-text article content (article mode). `null` for `/video/`/`/short/` pages that carry no `<p>`-based body. |
| `author` / `publisher` | string | Almost always `"Meduza"` (organization-level byline; article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `image` | object | Lead image as a raw ld+json `ImageObject` (article mode only). |
| `inLanguage` | string | `ru-RU` or `en-US` — which edition the article came from (article mode only). |
| `contentType` | string | The page's schema.org `@type`: `NewsArticle`, `Article`, or `VideoObject` (article mode only). |
| `link` | string | Article URL (latest mode). |
| `teaser` | string | Short RSS `<description>` summary, HTML-wrapped — not the full article (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL). A record with `_warning` was reached and parsed successfully but has no full-text body because of its content type (video, short-form card) — its metadata fields are still filled in.
