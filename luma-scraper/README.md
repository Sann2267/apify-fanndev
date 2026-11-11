# Luma Events Scraper

Extract event details, an organizer's full event calendar, or the
platform-wide discover/trending feed from lu.ma / luma.com — no account
or API key needed.

## Why use this actor

- One actor covers Luma's whole public surface: a single event's full
  detail, an organizer's complete upcoming/past event list, or the
  general discover/trending feed
- No account, login, or API key required — this actor talks to the same
  internal API (`api.lu.ma`) that powers the luma.com website itself for
  every logged-out visitor
- Accepts a full URL, a bare path, or just the short slug — paste
  whatever you copied from the address bar
- Automatic retries on temporary network hiccups
- Robust pagination — automatically follows Luma's cursor links up to
  the limit you set, instead of returning just one page
- Honest about limits: guest lists and Luma's own search are gated
  behind a login wall upstream and are out of scope, stated plainly
  rather than faked (see Known limits)

## How it works

Pick a `mode`:
1. **`event`** — full detail for one or more specific event URLs.
2. **`calendar`** — an organizer's own profile plus their full event
   list (upcoming or past).
3. **`discover`** — the platform-wide discover/trending feed, optionally
   filtered by latitude/longitude (no URL needed).

## Input

**Event detail:**
```json
{
  "mode": "event",
  "urls": ["https://lu.ma/sggq2oi9", "lu.ma/some-other-event"]
}
```

**Organizer calendar:**
```json
{
  "mode": "calendar",
  "url": "https://lu.ma/drupal-indonesia",
  "period": "future",
  "maxItems": 100
}
```

**Discover feed:**
```json
{ "mode": "discover", "maxItems": 50 }
```
```json
{ "mode": "discover", "latitude": "40.7128", "longitude": "-74.0060", "maxItems": 50 }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"event"` (default), `"calendar"`, or `"discover"`. |
| `url` | string | `event`/`calendar` mode — a single lu.ma URL, path, or bare slug. |
| `urls` | array | `event`/`calendar` mode — multiple URLs/slugs in one run. |
| `period` | string | `calendar` mode — `"future"` (default) or `"past"`. |
| `latitude` / `longitude` | string | `discover` mode — filter the feed around this coordinate. Leave blank to use the request's own IP-based location (Apify proxy country then steers results). |
| `maxItems` | integer | `calendar`/`discover` mode — max events to return. Pagination is followed automatically up to this cap. Default 100, max 10,000. |
| `maxConcurrency` | integer | `event`/`calendar` mode — how many URLs to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (not required for this endpoint — no WAF was found, see `CRAWLING_METHOD.md` — kept for production robustness and to steer `discover` mode's geo-personalized results). |

## Output

**`event` mode** — one record per event, full upstream shape (truncated
here for readability):
```json
{
  "_input": "https://lu.ma/sggq2oi9",
  "_source": "S1-api",
  "_scrapedAt": "2026-08-29T18:52:22Z",
  "api_id": "evt-KrtX1E0X7IdEFch",
  "event": {
    "name": "bRUNch - Run & Brunch Vol. 1",
    "start_at": "2026-08-28T23:00:00.000Z",
    "end_at": "2026-08-29T05:00:00.000Z",
    "timezone": "Asia/Jakarta",
    "location_type": "offline",
    "geo_address_info": { "city": "Kota Jakarta Pusat", "country": "Indonesia" }
  },
  "calendar": { "name": "LeadSphere" },
  "hosts": [{ "name": "...", "username": "..." }],
  "ticket_info": { "is_free": true, "spots_remaining": 71, "require_approval": true },
  "guest_count": 0
}
```

**`calendar` mode** — one `CALENDAR_PROFILE` record, then one
`CALENDAR_EVENT` record per event:
```json
{
  "_input": "drupal-indonesia",
  "_source": "S1-api",
  "recordType": "CALENDAR_PROFILE",
  "calendar": { "name": "Drupal Indonesia", "slug": "drupal-indonesia", "location": { "city": "Jakarta" } },
  "featured_items": [ "..." ]
}
```
```json
{
  "_input": "drupal-indonesia",
  "_source": "S1-api",
  "recordType": "CALENDAR_EVENT",
  "api_id": "calev-ADxrEdCdFjJVuZb",
  "event": { "name": "Drupal Drag and Drop Page Builder", "start_at": "..." }
}
```

**`discover` mode** — one record per trending event, same per-event
shape as a `CALENDAR_EVENT` record above.

A record with `_error` instead of the fields above means that input
could not be processed (for example, `"_error": "not_found"` for a URL
that doesn't resolve to any event or calendar, or `"_error":
"kind_mismatch"` if you pass a calendar URL in `event` mode).

## Pricing

Pay-per-event: **$0.005 per result** (`apify-default-dataset-item` — every
record written to the dataset, whether an `event`, `CALENDAR_PROFILE`,
`CALENDAR_EVENT`, or `discover` row), with volume discounts on paid Apify
plans: $0.0043 (Bronze) → $0.0035 (Silver) → $0.0027 (Gold) → $0.002
(Platinum) → $0.0015 (Diamond). See `CRAWLING_METHOD.md` for the
competitive analysis this price is based on (10+ existing Luma-specific
Store listings were found and compared; this actor's price sits in the
middle of the sustainable cluster, well above the unsustainable
race-to-bottom outliers and below the premium enrichment-tier listings).
Store category: Lead Generation, Social Media.

## Known limits

- **Guest lists and Luma's own search are not available.** Both
  `event/get-guest-list` and `search/get-results` require a logged-in
  session upstream (`401 "You are not signed in."`) even for fully
  public events — this is Luma's own access-control choice, not a bug,
  and is out of scope per this project's no-login policy.
- **The discover feed's ranking is Luma's own algorithm.** This actor
  exposes the geo-filter parameters Luma's own frontend uses, but the
  ranking/selection logic behind which events surface is not documented
  publicly.
