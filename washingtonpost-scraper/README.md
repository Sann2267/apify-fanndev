# Washington Post Scraper

Extract full article details or the newest headlines from The Washington Post — no account or subscription needed.

## Why use this actor

- No account or login required
- Rich article detail: headline, byline with author bios, publish/update dates, section tags, topic keywords, and lead images
- Also fetches the newest headlines from any section (Politics, World, Business, and more) without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

**Note on paid articles:** The Washington Post limits full article text to subscribers. This actor returns everything that's publicly visible — headline, summary, author, dates, tags, images, and the free preview paragraphs — but not the full body text of a metered article.

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode and pick a section.
2. In article mode, the actor opens each URL and pulls out every publicly available detail about the story.
3. In latest mode, the actor reads that section's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.washingtonpost.com/politics/2026/08/09/trump-picks-longtime-aide-will-scharf-new-top-white-house-lawyer/"
  ],
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Latest headlines mode:**
```json
{
  "mode": "latest",
  "section": "politics",
  "limit": 10,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from a section. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `section` | string | One of `politics`, `national`, `world`, `business`, `entertainment`, `opinions`, `lifestyle`, `local`. Used in latest mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 12. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability; the real record includes the full topic-tag list and lead-image variants):

```json
{
  "_input": "https://www.washingtonpost.com/politics/2026/08/09/trump-picks-longtime-aide-will-scharf-new-top-white-house-lawyer/",
  "_source": "S1-nextdata",
  "_scrapedAt": "2026-08-10T06:48:52Z",
  "_id": "ZPMTJNKXZJDL5GVIGPT7GYXMYE",
  "canonical_url": "https://www.washingtonpost.com/politics/2026/08/09/trump-picks-longtime-aide-will-scharf-new-top-white-house-lawyer/",
  "headlines": { "basic": "Trump picks longtime aide Will Scharf as new top White House lawyer", "meta_title": "" },
  "description": "The White House staff secretary replaces David Warrington, who is leaving for the private sector.",
  "publish_date": "2026-08-09T23:19:35.338Z",
  "first_publish_date": "2026-08-09T23:19:35.338Z",
  "last_updated_date": "2026-08-09T23:19:35.464Z",
  "credits": {
    "by": [
      {
        "_id": "allisonn",
        "name": "Natalie Allison",
        "org": "Washington, D.C.",
        "description": "Natalie Allison is a White House reporter for the Washington Post...",
        "image": { "url": "https://author-service-images-prod-us-east-1.publishing.aws.arc.pub/washpost/8f83902d-7cf6-4522-84a9-3eb71b16a23a.png" }
      }
      /* ... 1 more author */
    ]
  },
  "content_elements": [
    { "type": "image", "...": "... lead image details" },
    { "type": "text", "content": "President Donald Trump has named Will Scharf as the next top White House lawyer..." }
    /* ... 1 more free-preview paragraph */
  ],
  "restricted": true,
  "content_restrictions": { "content_code": "default" },
  "taxonomy": { "...": "... full section/topic/keyword tree" }
  /* ... additional_properties, promo_items, websites, and other fields */
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest:politics",
  "_source": "S3-rss",
  "_scrapedAt": "2026-08-10T06:48:19Z",
  "title": "Trump picks longtime aide Will Scharf as new top White House lawyer",
  "link": "https://www.washingtonpost.com/politics/2026/08/09/trump-picks-longtime-aide-will-scharf-new-top-white-house-lawyer/",
  "guid": "https://www.washingtonpost.com/politics/2026/08/09/trump-picks-longtime-aide-will-scharf-new-top-white-house-lawyer/",
  "creator": "Natalie Allison, Dan Diamond",
  "pubDate": "Sun, 09 Aug 2026 23:19:35 +0000",
  "description": "The White House staff secretary replaces David Warrington, who is leaving for the private sector.",
  "section": "politics"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL or section you requested, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headlines.basic` | string | Article headline (article mode). |
| `title` | string | Article headline (latest mode). |
| `description` | string | Article summary/dek. |
| `credits.by` | array | Authors, with bio and photo. |
| `publish_date` / `first_publish_date` / `last_updated_date` | string | Publication timestamps. |
| `content_elements` | array | The free-preview content blocks (text paragraphs and images) available without a subscription. |
| `restricted` | boolean | Whether the full article requires a subscription. |
| `taxonomy` | object | Section, topics, and keyword tags. |
| `link` / `canonical_url` | string | The article URL. |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
