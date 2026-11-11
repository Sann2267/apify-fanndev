# Crawling Method — Partiful Scraper

**Last verified:** 2026-08-30

## Architecture decision: one multi-mode actor, not one-per-event

Partiful's public surface splits into three distinct things a user might
want: a single event's full detail, a host/organizer's public profile
(plus their published event list, when they've opted into showing one),
and the platform-wide discover/trending feed. All three are served by
the same host (`partiful.com`), the same (no) auth, and the same
extraction technique (Next.js `__NEXT_DATA__`). Following the same
reasoning already applied to `luma-scraper` in this portfolio (a near-
identical platform shape): one actor with a `mode` input beats three
actors that would each duplicate the same Dockerfile, retry/backoff
client, and proxy wiring for zero technical benefit.

## WAF

**None, functionally.** `partiful.com` is hosted on **Vercel** (`Server:
Vercel` response header), not behind Cloudflare/Akamai/PerimeterX/
DataDome. A plain, unauthenticated `curl_cffi` request with `chrome124`
impersonation, no warmup request, and no cookie jar carried between
calls got a clean `200` on every one of dozens of manual requests during
recon — event pages, host profile pages, the discover page, and even
Next.js's own `/404` page. No challenge, no block marker, no rate-limit
seen. `chrome124` is used anyway per portfolio convention (defense-in-
depth), but was not required to get any of the recon data below.

## Primary data source: `__NEXT_DATA__` (highest-priority per `.ai/CLAUDE.md`)

Every `partiful.com` page ships its full server-rendered data inline in
a `<script id="__NEXT_DATA__" type="application/json">` tag — the exact
blob Next.js hydrates the React app from client-side. This sits above
`__APOLLO_STATE__`/HTML-scraping in this project's own extraction
priority ladder, and it's rich enough that none of this actor's 3 modes
need to fall back to CSS-selector scraping (unlike the reference
`github.com/cerebralvalley/partiful-api` project, which only scrapes an
event's `h1 span` title and `<time>` datetime via Cheerio — this actor's
`__NEXT_DATA__` approach recovers dramatically more: location, images,
guest-count breakdowns, custom fields, hosts, description, display
settings, and more).

### 1. `event` mode

`GET https://partiful.com/e/<eventId>` →
`__NEXT_DATA__.props.pageProps` = `{event, guest, hosts, similarEvents,
similarEventsRegion, passwordRequired, optimizeForFB, hostname}`. Full
upstream shape passed through verbatim. `event` alone carries ~30
fields: `title`, `startDate`/`endDate`, `timezone`, `location`/
`locationInfo` (structured address + Apple/Google Maps URLs), `image`
(poster or user upload), `description`, `customFields`, `displaySettings`
(theme/effect/font), visibility flags (`showGuestList`,
`showHostList`, `showGuestCount`, `isPublic`), and a full guest-count
breakdown (`guestStatusCounts`, `goingGuestCount`, `interestedGuestCount`,
`maybeGuestCount`, `waitlistGuestCount`, `approvedGuestCount`,
`attendedGuestCount`). `guest` is the *viewer's own* RSVP status and is
always `null` for an anonymous request (confirmed — not a bug).

Accepted input forms (see `src/extractor.py::extract_id`): a bare ID
(`S9m7mAA0avBXnFR6rgf0`), a path (`partiful.com/e/S9m7mAA0avBXnFR6rgf0`),
or a full URL with query string. A non-existent ID resolves to Next.js's
own `/404` route — detected via the SSR payload's `page` field (`"/404"`),
not status code alone, since Partiful's 404 page itself still returns a
well-formed `__NEXT_DATA__` blob (with an empty `pageProps`).

### 2. `host` mode

`GET https://partiful.com/u/<userId>` →
`pageProps` = `{hostname, user, optimizeForFB, initialPublishedEvents}`.
`user` is always present for a valid ID (`name`, `id`, `photo`, `bio`,
`socials`, `isManaged`, `onPartiful`). `initialPublishedEvents` is the
interesting field: **most personal accounts have it as `null`**
(confirmed across 25 distinct host IDs pulled from the discover feed —
the large majority were `null`), but **hosts who've opted into a public
"events on profile" feature return the full list inline** — one host in
the sample (`gKCLORBCJ02HNuasw3YI`, an organizer brand account) returned
150 events in one SSR payload, no pagination cursor needed or found.
This actor emits one `HOST_PROFILE` record per input, then one
`HOST_EVENT` record per item in `initialPublishedEvents` (capped at
`maxItems`) when the host has published a list — a real, legitimate
per-host toggle, not a bug on our end, so a `null` list gets a
`_warning: "host_has_no_public_event_list"` on the profile record
instead of being treated as an error.

### 3. `discover` mode

`GET https://partiful.com/discover` (`/explore` renders the identical
page) → `pageProps` = `{trendingSections: {NYC: {...}, LA: {...}, SF:
{...}}}`. Exactly **3 fixed editorial regions** were found — NYC, LA,
Bay Area (`SF`) — each carrying a curated `items` array of 5 event
summaries. No query params (geo coordinates, cursor, page size) were
found in the page or its markup; the region set and per-region count
appear to be fixed editorial curation rather than a paginated or
IP-personalized feed (unlike `luma-scraper`'s `discover` mode, which
*is* geo-personalized with a real cursor). Not confirmed across
multiple exit IPs/geographies — if that changes, re-probe rather than
assume. This actor exposes an optional `regions` filter and flattens all
matching sections into one record per event (`recordType:
"DISCOVER_EVENT"`), tagging each with `region` and `regionTitle`.

## Endpoints found but deliberately NOT used (require login)

Cataloged from the public `github.com/cerebralvalley/partiful-api`
project (a third-party reverse-engineering effort) and cross-checked
against this actor's own recon:

- Partiful's **authenticated Firebase Cloud Functions API**
  (`us-central1-getpartiful.cloudfunctions.net`) — `getMutuals()`,
  `getUsers()`, `getInvitableContacts()`, `getGuestsCsv()`. Every one of
  these requires a Bearer token manually extracted from a logged-in
  browser session (the token itself expires and must be periodically
  re-harvested by a human — there is no API-key or client-credential
  flow). Out of scope per this project's no-login constraint.
- **The actual guest list on an event page.** `event.showGuestList` is
  frequently `true`, but no guest array is ever present in the `event`
  mode SSR payload — Partiful renders the guest list client-side only
  after an authenticated call (this matches `getGuestsCsv()` above being
  gated). Confirmed absent across every event sampled during recon, not
  just the `passwordRequired` ones.

Both are Partiful's own access-control choice, not a bug on our end, and
are not routed around per project constraints (see `.ai/project/
CONSTRAINTS.md` and `.ai/CLAUDE.md` — no login, no auth-walled bypass).

## Data sources (all `S1-nextdata`, no fallback needed)

There is no S2 fallback because there is nothing to fall back from — the
same server-rendered blob that hydrates partiful.com's own React app is
read directly. No JSON-LD blocks were found on event pages (title/date
metadata exists only in Open Graph `<meta>` tags, which `__NEXT_DATA__`
already carries in richer form), so the extraction ladder resolves to a
single strategy for this platform.

## Known limits

- **Guest lists are unavailable HTTP-only** (see above) — Partiful's own
  access-control choice, not a bug, not routed around.
- **`host` mode's event list is opt-in per host.** Most personal
  accounts return `null`; only accounts that have enabled showing
  published events on their public profile return a list. This actor
  surfaces this honestly via `_warning` rather than treating it as a
  failure.
- **`discover` mode covers only 3 fixed regions** (NYC, LA, SF) with a
  fixed ~5-item curation each, as found live — no evidence of
  pagination, additional regions, or IP-based personalization was found
  in the page markup. If Partiful changes this feed's shape, re-probe
  rather than re-guess (their error bodies, if any, weren't observed —
  no invalid-input path was tested since the endpoint takes no params).
- **Password-protected events** (`passwordRequired: true`) were not
  captured live in a sample during recon; this actor still passes
  through whatever `pageProps` Partiful returns for one (fields may be
  partially withheld upstream) rather than special-casing it, consistent
  with the raw-passthrough convention.

## Diff cadence

Quarterly smoke test recommended: `python test_local.py event
S9m7mAA0avBXnFR6rgf0`, `python test_local.py host gKCLORBCJ02HNuasw3YI
5`, `python test_local.py discover 20`. If `__NEXT_DATA__` stops
appearing or `pageProps` keys change shape, `src/extractor.py`'s
`UnexpectedShape` will fire and crash the run loudly — investigate the
new markup rather than silently degrading.
