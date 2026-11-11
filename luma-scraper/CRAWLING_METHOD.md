# Crawling Method — Luma Scraper

**Last verified:** 2026-08-29

## Architecture decision: one multi-mode actor, not one-per-event

Luma's public surface splits into three distinct "events" a user might
want: a single event's full detail, an organizer's whole calendar of
events, and the platform-wide discover/trending feed. All three are
served by the same internal API (`api.lu.ma`), the same (no) auth, and
the same client. Following the reasoning already applied to
`twitch-channel-scraper` and `civitai-scraper` in this portfolio: one
actor with a `mode` input beats three actors that would each duplicate
the same Dockerfile, retry/backoff client, and proxy wiring for zero
technical benefit. Unlike this portfolio's news-outlet actors (one repo
per publisher domain, because each publisher is a genuinely separate
target with its own WAF/markup), Luma is a single platform — "1 actor =
1 event" would just be the same code copy-pasted three times.

## WAF

**None, functionally.** `api.lu.ma` sits behind Cloudflare (`Server:
cloudflare`, a `__cf_bm` cookie set on every response, and a
`window.__CF$cv$params` challenge-platform loader script present on
luma.com's own SSR HTML), but no challenge was ever triggered against
any endpoint used here. A plain, unauthenticated request with an
ordinary Chrome user-agent and **no** TLS impersonation, no warmup
request, and no cookie jar gets a clean JSON `200` every time — confirmed
across 15+ manual requests during recon, including rapid sequential
calls. `curl_cffi` `chrome124` is used anyway per portfolio convention
(defense-in-depth, smooths over any future tightening) but was not
required to get any of the recon data below.

## The `/url` universal resolver

`GET https://api.lu.ma/url?url=<slug>` is the same endpoint luma.com's
own frontend calls to resolve *any* `lu.ma/<slug>` route (found by
downloading and grepping the site's Next.js JS bundles, then confirming
live). It returns:

```json
{"kind": "event", "data": { ...full event object... }}
```
or
```json
{"kind": "calendar", "data": {"calendar": {...}, "featured_items": [...], "has_upcoming_events": bool, ...}}
```

Diffing this against a live event page's SSR `__NEXT_DATA__` payload
(`pageProps.initialData`) confirmed the `data` shape for an event is
byte-for-byte identical to `GET /event/get?event_api_id=<id>` — so a bare
slug is enough for a single event or calendar lookup; no separate
ID-resolution call is needed. A slug that doesn't exist returns a clean
`404` with `{"message":"Sorry, we could not find what you were looking
for.","code":null}`.

Accepted input forms (see `src/extractor.py::extract_slug`): a bare slug
(`sggq2oi9`), a path (`lu.ma/sggq2oi9`), or a full URL
(`https://lu.ma/sggq2oi9?query=..`). `luma.com` is also accepted (it
301-redirects to `lu.ma` for the human-facing site, but `api.lu.ma` is
the same host either way).

## Pagination

`/calendar/get-items` (an organizer's events) and
`/discover/get-paginated-events` (the platform-wide trending feed) both
use the same cursor style: a response has `"entries": [...]`, `"has_more":
bool`, and — only when `has_more` is true — `"next_cursor": "<opaque
base64 blob>"`. `src/client.py`'s `paginate_calendar`/`paginate_discover`
loop on this until `has_more` is false, `entries` comes back empty, or
the caller's `max_items` cap is hit. No page-size (`limit`) query param
was found in the frontend bundles for either endpoint — Luma controls
batch size server-side.

## Real bug found (in my own first guess, not upstream): `period=upcoming` does not exist

`/calendar/get-items` takes a `period` param to choose an organizer's
upcoming vs. past events. The obvious guess, `period=upcoming` (matching
the calendar UI's own button label), returns a generic `400 {"message":
"Invalid request.","code":null}` — Luma's error body does **not** list
valid enum values (unlike Civitai's Zod errors in this portfolio's other
actor). Candidates were probed one at a time directly against
`api.lu.ma` (not guessed a second time): omitting `period` entirely
defaults to upcoming events, and the working explicit value is
**`period=future`**. `period=past` works as expected. `src/constants.py`
documents this so nobody re-guesses `upcoming` in a future session.

## Geo-personalization on the discover feed

`/discover/get-paginated-events` with no query params returns results
personalized by the request's own IP (confirmed: a Jakarta-based request
IP returned Jakarta-area events; luma.com's own SSR `__NEXT_DATA__` also
carries a top-level `latitude`/`longitude`/`countryCode` derived from
request IP). Explicit `geo_latitude`/`geo_longitude` query params
(names found in the frontend JS bundles, confirmed live against a
New York coordinate — returned Brooklyn/Queens/Manhattan events) override
this. This actor's `discover` mode exposes both: leave `latitude`/
`longitude` blank to use the Apify proxy's exit-IP location (so proxy
country selection steers results), or set them explicitly.

## Endpoints found but deliberately NOT used (require login)

Cataloged from the frontend's own JS bundles (`grep`'d out of every
`/_next/static/.../chunks/*.js` referenced by an event page) and
confirmed live:

- `GET /search/get-results?query=...` → `401 {"message":"You are not
  signed in."}`, even for a public search term.
- `GET /event/get-guest-list?event_api_id=...` → same `401`, even for a
  fully public event with `show_guest_list: true` in its own event
  object.

Both are out of scope per this project's "No Login" constraint and are
not wired up in this actor. (`/event/get`, `/url`, `/calendar/get-items`,
`/discover/get-paginated-events` all work with zero auth.)

## Data sources (all `S1-api`, no fallback needed)

There is no S2 fallback because there is nothing to fall back from — the
same internal API that renders luma.com's own SSR pages is called
directly.

### 1. `event` mode
`GET /url?url=<slug>`, kept only if `kind == "event"`. Full upstream
event object passed through as-is: `event` (name, start_at/end_at,
timezone, location_type, geo_address_info, cover_url, virtual_info),
`calendar` (host organizer summary), `hosts` (list of user objects),
`ticket_info` (price, is_free, spots_remaining, require_approval),
`guest_count`, `registration_availability`.

### 2. `calendar` mode
`GET /url?url=<slug>`, kept only if `kind == "calendar"` → one
`CALENDAR_PROFILE` record (organizer's own profile: name, slug, social
handles, verified_at, `featured_items`). Then
`GET /calendar/get-items?calendar_api_id=<id>&period=future|past`,
paginated → one `CALENDAR_EVENT` record per event (same per-event shape
as an entry in `discover` mode). `recordType` discriminates the two
shapes within one run, per `.ai/conventions/dataset-envelope.md`'s
multi-record-type-per-run convention.

### 3. `discover` mode
`GET /discover/get-paginated-events`, optionally `geo_latitude`/
`geo_longitude`, paginated. One record per trending/upcoming event
entry, same shape as a `calendar` mode `CALENDAR_EVENT`.

## Known limits

- Guest lists and search are unavailable HTTP-only (see "require login"
  above) — this is Luma's own access-control choice, not a bug on our
  end, and not routed around per project constraints.
- `discover` mode's feed composition (which events surface, in what
  order) is Luma's own ranking algorithm — not documented publicly, not
  reverse-engineered here beyond the geo-filter params.
- No `limit`/page-size control was found for `/calendar/get-items` or
  `/discover/get-paginated-events` — `maxItems` in this actor's input
  caps total records returned, but each individual upstream page's size
  is whatever Luma's server decides.

## Store category & pricing (2026-08-29)

**Competitive analysis.** A Store search for "luma" turned up a genuinely
crowded niche — at least 10 distinct sellers already publish a
Luma-specific scraper (`api-search-actors.py --query "luma events"`),
plus large adjacent incumbents for other event platforms
(`facebook-events-scraper`: 3,820 users; `eventbrite`: 576 users) that
aren't direct competitors but confirm the event-data category has real
demand. Direct Luma competitors found, by `apify-default-dataset-item`
(or equivalent primary event) price and usage:

| Actor | Seller | Users / Runs | Primary event price (FREE tier) |
|---|---|---|---|
| luma-events | Aitor Sanchez-Mansilla | 62 / 1,047 | $0.024–$0.03 (+ $0.01 enrichment) |
| luma-com-event-scraper | Hypebridge | 102 / 1,586 | $0.08–$0.10 actor-start(!) + $0.003–$0.006/item |
| luma-event-scraper | (50 users) | 50 / 450 | $0.0025–$0.004 |
| luma-scraper | (77 users) | 77 / 1,166 | $0.0025 flat |
| meetup-luma-scraper | — | 26 / 250 | $0.003–$0.005 + $0.005 actor-start |
| luma-scraper — Events & Organizer Leads | scrapesage | 7 / 118 | $0.00125–$0.005 (event), $0.00175–$0.007 (calendar) |
| luma-events-scraper | (5 users) | 5 / 75 | $0.002 flat |
| luma-calendar-events-scraper | — | 33 / 1,619 | FREE |
| luma-event-scraper | (205 users, most-used) | 205 / 10,538 | $0.00003–$0.00007 (race-to-bottom outlier) |
| lu.ma Events Scraper | (3 users) | 3 / 160 | $0.0001 flat (outlier) |

Excluding the two extreme race-to-bottom outliers (thin per-item pricing
that doesn't cover Apify's own margin cut plausibly, and reads as
unsustainable/low-quality rather than a real target) and the one clear
premium listing (Aitor's, priced ~5-10x the rest, presumably to offset
optional enrichment cost), the sustainable cluster sits at **$0.0025 to
$0.006 per dataset item**. This actor's own compute cost is negligible
(no WAF, no proxy strictly required, sub-second per-record API calls —
see WAF section above), so any price in that cluster comfortably covers
infrastructure with margin.

**Category.** `LEAD_GENERATION` (primary — matches 8 of the 10 direct
competitors above; an organizer's calendar profile with social handles
is exactly a lead-gen use case) + `SOCIAL_MEDIA` (secondary — matches
several competitors; hosts/organizer social handles are the social
angle). Configured live via `apify api PUT actors/{id}
{"categories":[...]}`.

**Pricing configured.** `PAY_PER_EVENT`, single chargeable event
`apify-default-dataset-item` (Apify auto-charges this for every
`push_data()` call — confirmed against `docs.apify.com`, zero code
change needed). Two-step rollout (the mandatory flat-then-tiered
sequence for a brand-new actor — see
`.ai/skills/actor-store-monetization/SKILL.md` Phase 8):
1. `2026-08-28T19:04Z` — flat **$0.005/result** (`eventPriceUsd`),
   scheduled `startedAt: 2026-08-29T00:00:00Z` (an accidental
   rounded-midnight timestamp instead of real "now" — this is the
   `startedAt` gotcha now written up in that skill file — it delayed the
   tiered follow-up by ~5 hours until real time actually reached that
   point).
2. `2026-08-29T00:27Z` — tiered volume discount appended once the
   platform's timing window opened: FREE $0.005 (unchanged) → BRONZE
   $0.0043 → SILVER $0.0035 → GOLD $0.0027 → PLATINUM $0.002 → DIAMOND
   $0.0015.

FREE-tier price matches scrapesage's directly-comparable multi-mode
actor's top price exactly and sits mid-cluster against the competitor
table above — competitive but not a race-to-the-bottom price. Both
entries confirmed live via `apify api GET actors/{id}`.

Not yet published to the Store (`isPublic` still `false`) — that
toggle, and the platform's 5-publications/day limit, were left for a
separate explicit request per this portfolio's standing "ask before
account-visible actions" practice.

## Diff cadence

Quarterly smoke test recommended (`python test_local.py event sggq2oi9`,
`python test_local.py calendar drupal-indonesia future 5`,
`python test_local.py discover`). If `/calendar/get-items` starts
rejecting `period=future` again, re-run the error-probing approach above
rather than re-guessing — Luma's 400 body is generic and does not name
valid values.
