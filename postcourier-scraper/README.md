# Post Courier Scraper

Extract full article text or the newest headlines from the Post Courier (postcourier.com.pg), Papua New Guinea's leading daily newspaper — no account or API key needed.

## Why use this actor

- No account or login required to run the actor
- Full article text included, not just a summary — headline, author, publish/modified dates, section, tags, and a reconstructed clean body
- Also fetches the newest headlines automatically, with real publish timestamps and category tags for each story
- Clear paywall flag on every article record — you always know whether you got the full story or a preview
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor returns the newest stories with their publish time and categories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "url": "https://www.postcourier.com.pg/222m-pacific-games-spending-bombshell/",
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100 (the site's headline list currently returns up to 10 per run). |
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL. A freely-readable story returns the full text:

```json
{
  "_input": "https://www.postcourier.com.pg/222m-pacific-games-spending-bombshell/",
  "_source": "S1-jsonld+wpapi",
  "headline": "$222M Pacific Games spending bombshell",
  "description": "A special audit into how the Solomon Islands National Hosting Authority (NHA) spent public money for the 2023 Pacific Games has uncovered serious failures in procurement, financial controls and record-keeping.",
  "author": "postcourieronline",
  "publisher": "Post Courier",
  "articleSection": ["World", "World News"],
  "keywords": ["PacificNews", "pacnews"],
  "datePublished": "2026-08-24T22:39:29+00:00",
  "dateModified": "2026-08-24T22:39:35+00:00",
  "thumbnailUrl": "https://www.postcourier.com.pg/wp-content/uploads/2026/08/PACSPORTS-1.png",
  "wordCount": 619,
  "articleBody": "A special audit into how the Solomon Islands National Hosting Authority (NHA) spent public money for the 2023 Pacific Games has uncovered serious failures in procurement, financial controls and record-keeping. … [full text, ~619 words]",
  "_paywalled": false,
  "wpAuthor": "postcourieronline",
  "featuredMediaUrl": "https://www.postcourier.com.pg/wp-content/uploads/2026/08/PACSPORTS-1.png",
  "categories": ["World", "World News"],
  "tags": ["PacificNews", "pacnews"],
  "coauthors": [84253]
}
```

A gated story returns a short preview instead of the full text, flagged by `_paywalled`:

```json
{
  "_input": "https://www.postcourier.com.pg/air-niugini-handles-major-b747-freighter-operation-in-port-moresby/",
  "_source": "S1-jsonld+wpapi",
  "headline": "AIR NIUGINI HANDLES MAJOR B747 FREIGHTER OPERATION IN PORT MORESBY",
  "description": "Air Niugini has provided ground handling services for a National Airlines Boeing 747 Freighter (B747F), an American cargo aircraft that arrived in Port Moresby last week",
  "author": "postcourieronline",
  "publisher": "Post Courier",
  "articleSection": ["PNG News"],
  "datePublished": "2026-08-26T05:54:49+00:00",
  "wordCount": 537,
  "articleBody": "Air Niugini has provided ground handling services for a National Airlines Boeing 747 Freighter (B747F), an American cargo aircraft that arrived in Port Moresby last week, carrying more than 84 tonnes of cargo for Ok Tedi Mining Limited. … [preview only, full story is behind a subscription]",
  "_paywalled": true,
  "categories": ["PNG News"]
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "title": "Solomon Islands High Court rules 2023 Pacific Games spending illegal",
  "link": "https://www.postcourier.com.pg/solomon-islands-high-court-rules-2023-pacific-games-spending-illegal/",
  "pubDate": "Wed, 26 Aug 2026 06:21:43 +0000",
  "pubDateIso": "2026-08-26T06:21:43Z",
  "creator": "postcourieronline",
  "categories": ["PNG News", "World", "#Pacific NEWS"]
}
```

A failed URL (removed article, wrong link) still produces a row instead of silently disappearing:

```json
{
  "_input": "https://www.postcourier.com.pg/this-slug-definitely-does-not-exist-xyz123/",
  "_source": "none",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- Most PNG-local news (categories like "PNG News", "Business", "Sports") is behind a subscription and returns only a short preview with `_paywalled: true`. Pacific-region wire stories (tagged "World" / "World News") are frequently free with the full text included.
- `latest` mode currently returns up to 10 headlines per run regardless of the `limit` value you set — request a higher `limit` and it simply returns what's available.
- `latest` mode's fields don't include the paywall status — run the `link` through `article` mode to find out.

## Other actors in this collection

See the parent portfolio for other regional-daily news scrapers (e.g. `jamaicagleaner-scraper`).
