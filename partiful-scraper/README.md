# Partiful Events Scraper

Extract public event details, a host's public profile and published
event list, or Partiful's discover/trending feed from partiful.com — no
account or login needed.

## Why use this actor

- One actor covers Partiful's whole public surface: a single event's
  full detail, a host/organizer's public profile (plus their published
  event list, when they've made one public), or the platform's
  discover/trending feed
- No account, login, or API key required — this actor reads the same
  server-rendered data (`__NEXT_DATA__`) that powers the partiful.com
  website itself for every logged-out visitor
- Recovers far more than a basic HTML scrape: full location/address,
  guest-count breakdowns, images, custom fields, display theme, and more
  — not just a title and a date
- Accepts a full URL, a path, or just the bare ID — paste whatever you
  copied from the address bar
- Automatic retries on temporary network hiccups
- Honest about limits: guest lists are gated behind a login wall
  upstream and are out of scope, stated plainly rather than faked (see
  Known limits)

## How it works

Pick a `mode`:
1. **`event`** — full public detail for one or more specific event URLs.
2. **`host`** — a host/organizer's public profile, plus their published
   event list (only present for hosts who've opted into showing one).
3. **`discover`** — Partiful's public discover/trending feed (NYC, LA,
   Bay Area), optionally filtered by region (no URL needed).

## Input

**Event detail:**
```json
{
  "mode": "event",
  "urls": ["https://partiful.com/e/S9m7mAA0avBXnFR6rgf0", "hfqCb3JYBBGZ7d90ojHb"]
}
```

**Host / organizer profile:**
```json
{
  "mode": "host",
  "url": "https://partiful.com/u/gKCLORBCJ02HNuasw3YI",
  "maxItems": 50
}
```

**Discover feed:**
```json
{ "mode": "discover" }
```
```json
{ "mode": "discover", "regions": ["NYC", "LA"], "maxItems": 20 }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"event"` (default), `"host"`, or `"discover"`. |
| `url` | string | `event`/`host` mode — a single partiful.com URL, path, or bare ID. |
| `urls` | array | `event`/`host` mode — multiple URLs/IDs in one run. |
| `regions` | array | `discover` mode — subset of `["NYC", "LA", "SF"]`. Leave empty for all. |
| `maxItems` | integer | `host` mode — max events from a host's public list. `discover` mode — max trending events returned. Default 100, max 10,000. |
| `maxConcurrency` | integer | `event`/`host` mode — how many URLs to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (not required for this target — no WAF was found, see `CRAWLING_METHOD.md` — kept for production robustness). |

## Output

**`event` mode** — one record per event, full upstream shape (truncated
here for readability; real output captured 2026-08-30):
```json
{
  "_input": "https://partiful.com/e/hfqCb3JYBBGZ7d90ojHb",
  "_source": "S1-nextdata",
  "_scrapedAt": "2026-08-30T17:00:45Z",
  "event": {
    "title": "Comedy night",
    "startDate": "2026-05-17T04:00:00.000Z",
    "timezone": "America/Los_Angeles",
    "status": "PUBLISHED",
    "locationInfo": {
      "type": "structured",
      "mapsInfo": {
        "name": "The Ice House Comedy",
        "addressLines": ["24 N Mentor Ave", "Pasadena, CA 91106"]
      }
    },
    "maxCapacity": 80,
    "guestStatusCounts": { "GOING": 11, "INTERESTED": 9, "MAYBE": 2, "...": "..." },
    "goingGuestCount": 11
  },
  "guest": null,
  "hosts": [{ "name": "...", "id": "..." }],
  "passwordRequired": false
}
```

**`host` mode** — one `HOST_PROFILE` record, then one `HOST_EVENT`
record per published event (real output, truncated):
```json
{
  "_input": "gKCLORBCJ02HNuasw3YI",
  "_source": "S1-nextdata",
  "recordType": "HOST_PROFILE",
  "user": { "name": "OC Cuties", "id": "gKCLORBCJ02HNuasw3YI", "bio": {"...": "..."} }
}
```
```json
{
  "_input": "gKCLORBCJ02HNuasw3YI",
  "_source": "S1-nextdata",
  "recordType": "HOST_EVENT",
  "id": "0dVvDJw8076h04QVBVnl",
  "title": "Cuties Go AYCE",
  "startDate": "2025-04-09T00:30:00.000Z"
}
```
A `HOST_PROFILE` record carries `"_warning": "host_has_no_public_event_list"`
instead of any `HOST_EVENT` rows when that host hasn't opted into showing
a public event list — most personal accounts.

**`discover` mode** — one `DISCOVER_EVENT` record per trending event
(real output, truncated):
```json
{
  "_input": "discover:NYC,LA",
  "_source": "S1-nextdata",
  "recordType": "DISCOVER_EVENT",
  "region": "NYC",
  "regionTitle": "Trending in NYC",
  "id": "G5T1visd0LOmscq9n7pA",
  "title": "Guinness world record attempt: DUCK DUCK GOOSE",
  "locationInfo": { "mapsInfo": { "name": "Central Park", "approximateLocation": "New York, NY" } },
  "interestedGuestCount": 523,
  "goingGuestCount": 286
}
```

A record with `_error` instead of the fields above means that input
could not be processed (for example, `"_error": "not_found"` for an ID
that doesn't resolve to any event or host).

## Pricing

Pay-per-event: **$0.005 per result** (`apify-default-dataset-item` — every
record written to the dataset, whether an `event` row, `HOST_PROFILE`,
`HOST_EVENT`, or `DISCOVER_EVENT`), with volume discounts on paid Apify
plans: $0.0043 (Bronze) → $0.0035 (Silver) → $0.0027 (Gold) → $0.002
(Platinum) → $0.0015 (Diamond). See `CRAWLING_METHOD.md` for the
competitive analysis this price is based on: 7 direct Partiful-specific
Store listings were found (`heliostech/partiful-event-scraper` at $0.003
flat is the market leader by users; `hypebridge/partiful-events-scraper`
prices its closest feature-equivalent event/host-profile events at
$0.006→$0.003 tiered), plus one strong adjacent-platform comparator
(`posh-vip-scraper`, 28 users, at $0.003 flat). This actor's price sits
just above the $0.003 incumbent floor — justified by recovering
materially more fields per record (full address, guest-count breakdown,
images, custom fields) than the cheaper competitors capture — while its
Gold tier and below already beat every competitor's own best discount
price. Store category: Lead Generation, Social Media.

## Known limits

- **Guest lists are not available.** Partiful only renders the actual
  guest list client-side after a logged-in session — every event page's
  server-rendered payload omits it even when `showGuestList: true`. This
  is Partiful's own access-control choice, not a bug on our end, and is
  out of scope per this project's no-login policy.
- **`host` mode's published-event list is opt-in per host.** Most
  personal accounts have not enabled it; brand/organizer accounts more
  often have. A `null` list is flagged with `_warning`, not treated as
  an error.
- **`discover` mode covers 3 fixed regions** (NYC, LA, Bay Area) with a
  small curated list each — this is Partiful's own editorial feed, not
  a full paginated or searchable index of every public event on the
  platform.

See `CRAWLING_METHOD.md` for the full recon writeup, including what was
tried and deliberately not used.
