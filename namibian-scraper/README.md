# The Namibian Scraper

Extract full article text or the newest headlines from The Namibian (namibian.com.na), Namibia's largest daily newspaper — no account or login needed.

## Why use this actor

- No account or login required — fully free site, no paywall found on any section (National, Business, Sport, Crime, or Editorial/Opinion)
- Full article text included, not just a summary — headline, byline, category, publish/modified dates, word count, lead image, and a clean paragraph-joined body
- Latest-headlines mode returns **complete article text for every item**, not just a title and link — it reads the site's RSS feed, which happens to carry the full body
- Correctly resolves bylines whether the piece is staff-written, a wire-service story (e.g. AFP), or an unsigned editorial
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads The Namibian's RSS feed (paginating automatically for larger limits) and returns the newest stories, body text included.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.namibian.com.na/lubango-survivors-still-demand-answers-from-swapo/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines with full text. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (`articleBody` truncated here for readability; real runs return the full text):

```json
{
  "_input": "https://www.namibian.com.na/lubango-survivors-still-demand-answers-from-swapo/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T00:55:49Z",
  "slug": "lubango-survivors-still-demand-answers-from-swapo",
  "headline": "Lubango survivors still demand answers from Swapo",
  "articleBody": "August is a painful reminder for Lubango dungeon survivors, who say the month reminds them of the notorious killings and torture of Swapo Party members accused of being spies of the South African colonial regime during the liberation struggle.\n\nLubango dungeons were underground dugout prisons that were allegedly used to torture and kill Swapo detainees arrested for allegedly spying for South African forces.\n\nAccording to the survivors, more than 4 200 Namibians allegedly disappeared during the time, and their families and fellow prisoners never heard from them again.\n\n... [29 more paragraphs]",
  "author": "Chris Kaukemua",
  "category": ["National", "News", "Top Story 1"],
  "wordCount": 822,
  "datePublished": "2026-08-25T17:00:00+00:00",
  "dateModified": null,
  "thumbnailUrl": "https://d4f7y6nbupj5z.cloudfront.net/wp-content/uploads/2026/08/10-5.jpg",
  "image": {
    "url": "https://d4f7y6nbupj5z.cloudfront.net/wp-content/uploads/2026/08/10-5.jpg",
    "caption": "TORTURE … Lubango dungeon survivor Phillip Shipulwa (65) says he still has scars left by beatings and torture he endured while detained by Swapo in Angola during the liberation struggle.",
    "width": 751,
    "height": 451
  }
}
```

A wire-service story instead credits the wire service directly, and an unsigned editorial credits the outlet itself:

```json
{ "headline": "Ioane stars as New Zealand recover to beat Johannesburg Lions", "author": "AFP", "category": ["Sport"] }
{ "headline": "Cabinet Overreach Can Endanger Good Governance", "author": "The Namibian", "category": ["Editorials"] }
```

**Latest headlines mode** — one record per headline, full body text included:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T00:56:20Z",
  "slug": "jet-fuel-shortage-not-related-to-vitol-fuel-supply-amutse",
  "title": "Jet fuel shortage not related to Vitol fuel supply – Amutse",
  "link": "https://www.namibian.com.na/jet-fuel-shortage-not-related-to-vitol-fuel-supply-amutse/",
  "author": "Nishi Felton",
  "category": "More Top Stories",
  "pubDate": "Tue, 25 Aug 2026 17:46:19 +0000",
  "guid": "https://www.namibian.com.na/?p=967772",
  "content": "The Ministry of Mines and Energy has defended its three-month fuel supply deal with Vitol, saying it can’t be blamed for the jet fuel shortage that has affected the country since last week.\n\nLast Monday, a consignment of jet A-1 fuel did not pass routine inspection at Walvis Bay.\n\nThis has led Lufthansa Cargo to temporarily suspend flights and Discover Airlines to divert flights to Luanda to refuel.\n\n... [17 more paragraphs]"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-html` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `slug` | string | The article's URL slug. |
| `headline` / `title` | string | Article headline. |
| `articleBody` / `content` | string | Full plain-text article content, paragraph-separated by blank lines. |
| `author` | string | Byline name — a reporter, a wire service (e.g. `"AFP"`), or `"The Namibian"` on unsigned editorials. |
| `category` | array/string | Article mode: full list of WordPress categories assigned to the post. Latest mode: the RSS feed's single category value. |
| `wordCount` | integer | Upstream-reported word count (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only; `dateModified` is `null` when the article was never edited after publishing). |
| `thumbnailUrl` / `image` | string/object | Lead image (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp (latest mode). |
| `guid` | string | WordPress's internal post ID URL, stable even if the slug changes (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).

## Known limits

- Free/open site — no paywall bypass logic needed.
- `category` in article mode includes homepage-placement labels alongside real section names (e.g. `"Top Story 1"`, `"Business Home 3"`) since that's exactly what the site's own structured data reports.
- Latest mode is capped at 50 headlines per run; the RSS feed paginates 12 items at a time and duplicate items across the pagination boundary are automatically filtered out.
