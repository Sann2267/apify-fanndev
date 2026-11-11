# Crawling Method — Tanzania Government Tenders (NeST)

**Last verified:** 2026-08-27

## Target discovery — NeST is the official platform, `nest.co.tz` is a decoy

Tanzania's Public Procurement Regulatory Authority (PPRA, statutory regulator
under the Public Procurement Act) operates **NeST — the National
e-Procurement System of Tanzania** at `https://nest.go.tz` (a `.go.tz`
government domain, hosted/operated for PPRA). Confirmed independently:

- `nest.go.tz`'s own homepage `<meta name="author" content="PPRA">`,
  `schema.org` Organization JSON-LD naming PPRA, and links out to PPRA's
  official social accounts (`facebook.com/PPRA_Tanzania-...`,
  `twitter.com/PpraTanzania`).
- An official "NeST Tenderer" mobile app on Google Play
  (`com.tz.go.ppra.nest`).
- A companion open-data site, `data.nest.go.tz` ("NeST Data Portal"),
  explicitly describing itself as publishing **OCDS-compliant** (Open
  Contracting Data Standard) procurement data "to empower analysis and
  accountability."

**`nest.co.tz`** ("NEST — Gateway to Tanzania's Tenders", `.co.tz` not
`.go.tz`) is a **separate, third-party commercial site** — its own copy
states "© 2024 NEST — New Electronic System for Tendering" and it hands
visitors off to yet another third party, `Tendersoko.com`, rather than
hosting any listings itself. It is not used by this actor. This matches the
project's now-familiar pattern of a lookalike commercial domain sitting next
to the real `.go.tz`/`.gov.tz` platform.

## robots.txt

`nest.go.tz/robots.txt` (identical on `www.nest.go.tz`):

```
User-agent: *

Disallow: /tender-details
Disallow: /tender-details?tender=*

Allow: /tenders/published-tenders
Allow: /tenders/published-tenders?*
Allow: /tenderers
Allow: /procuring-entities

Disallow: /tenders/
Allow: /tenders/published-tenders
Allow: /tenders/published-tenders?*
```

One flat `User-agent: *` group, no blanket `Disallow: /`, and no
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
mention anywhere. The only disallowed paths are the SPA's own client-side
routes for individual tender detail pages (`/tender-details`) and the
generic `/tenders/` prefix (with the summary listing page itself carved back
out via `Allow`). This actor never touches any of those HTML routes at all —
see below — so it doesn't even brush up against the one real restriction
here. `data.nest.go.tz` has no `robots.txt` file (the request falls through
to the Angular app's own index page, a normal SPA catch-all, not a
disallow).

## No login required to view listings, awards, or contracts

Both the SPA's own public listing page (`/tenders/published-tenders`,
explicitly `Allow`-ed above) and the JSON API this actor actually uses
(below) are reachable anonymously — confirmed with a fresh, cookie-less
client, no session, no API key. NeST does have a "Register as Tenderer" /
"Login" flow, but it's only for entities that want to actually **submit**
bids, matching the pattern seen across this project's tender-vertical actors
(Ghana/Zambia/Jamaica/Uganda/PNG/Sierra Leone/Nepal) — never a wall on
viewing.

## The real find: a genuinely public OCDS JSON API, no HTML scraping needed

`nest.go.tz` and `data.nest.go.tz` are both client-rendered Angular SPAs — no
data is present in the initial HTML. Rather than scrape the rendered
`/tenders/published-tenders` table (which robots.txt's own comments suggest
the site owners would rather bots avoid drilling into per-tender pages for),
the SPA's own JS bundle (`data.nest.go.tz`'s `main-*.js`) was read directly
and yields a small, self-contained "API playground" component with the real
base URL and endpoint paths hard-coded:

```js
this.baseUrl = "https://nest.go.tz/gateway/nest-data-portal-api/api/"
...
tryEndpoint("releases?cursor={cursor}&since={since}")
tryEndpoint("releases/{ocid}/{releaseId}")
tryEndpoint("records?cursor={cursor}&since={since}")
tryEndpoint("records/{ocid}")
```

All four confirmed live and public with zero auth:

```
GET https://nest.go.tz/gateway/nest-data-portal-api/api/records?cursor=0&since=2022-01-01T00:00:00Z
GET https://nest.go.tz/gateway/nest-data-portal-api/api/records/{ocid}
GET https://nest.go.tz/gateway/nest-data-portal-api/api/releases?cursor=0&since=2022-01-01T00:00:00Z
GET https://nest.go.tz/gateway/nest-data-portal-api/api/releases/{ocid}
```

This actor uses only `records` / `records/{ocid}` — the "compiled record"
view already merges every release (tender, tenderUpdate, award, contract)
for an OCID into one object (`compiledRelease`), so a single call gets full
detail; there is no need for a separate list-then-detail round trip the way
most HTML-scraped tender portals in this project require. A response looks
like:

```json
{
  "license": "https://data.nest.go.tz/license",
  "publisher": {"name": "Public Procurement Regulatory Authority (PPRA)", "uri": "https://www.ppra.go.tz"},
  "links": {"next": "...records?cursor=5&since=...", "prev": null},
  "records": [
    {
      "ocid": "ocds-mv5oob-S6990-2025-2026-G-03-S001",
      "compiledRelease": {
        "buyer": {"name": "IGIMA WARD SECONDARY SCHOOL"},
        "date": "2026-06-09T11:20:03Z",
        "tender": {"id": "S.6990/2025/2026/G/03-S001", "status": "complete", "items": [...], "tenderPeriod": {...}},
        "awards": [{"value": {"amount": 21092000, "currency": "TZS"}, "suppliers": [...]}]
      },
      "releases": [{"url": "...", "date": "2026-06-02T00:00:00Z", "tag": ["tenderUpdate"]}, ...]
    }
  ]
}
```

Also tried and rejected: the SPA's prettier per-table endpoints
(`records/tenders`, `records/awards`, referenced by the site's own "browse"
UI components) return an inconsistent mix of bare 403/404/405 with no body —
unlike the raw `records`/`records/{ocid}` paths, which returned clean 200
JSON on every attempt. The raw OCDS paths are used exclusively; the
prettier table endpoints were not pursued further once the raw ones proved
reliable and already richer (full `compiledRelease`, not a flattened table
row).

### Confirmed quirks

- **The `cursor` query parameter is accepted but not actually honoured
  server-side.** Sending `cursor=0`, `cursor=5`, `cursor=10`, ... for the
  *same* `since` value returns the identical first 5 records and an
  identical `next` link (`cursor=5`) every time — confirmed by comparing
  OCIDs across repeated calls. Real pagination is done differently: this
  actor advances the `since` parameter itself, using the maximum
  `compiledRelease.date` seen in a page as the next page's floor
  (`+1 second`, to avoid re-fetching the same boundary record), and
  de-duplicates by `ocid` across the resulting overlap. `limit`/`pageSize`/
  `size` query parameters were also tried to raise the fixed 5-per-page
  server-side size — all three cause a `500`, so the actor doesn't send them.
- **NeST's own compiled-record data currently runs a couple of months
  behind the calendar** — as of this writing (2026-08-27), `since` floors
  from roughly late June 2026 onward return zero records, while floors from
  mid-June and earlier return real data. This is reported honestly: `list`
  mode returns however many records genuinely exist for the requested date
  range (which may be fewer than `maxResults`, including zero for a very
  recent `since`), rather than padding or pretending completeness — the
  same convention used by this project's other government tender actors
  (e.g. `nepal-tenders-scraper`'s honest non-deterministic pagination
  reporting).
- **The host rate-limits noticeably harder than most targets in this
  project** — a bare `403` (or occasionally `500`) with an empty/short body
  after a burst of requests in quick succession, recovering after roughly
  a minute of backing off. This looks like a generic edge/WAF appliance
  (an F5 BIG-IP load balancer sits in front — `BIGipServerNEW-NEST-POOL-443`
  session-persistence cookie observed on every response — most likely with
  a basic request-rate anomaly rule, not a bot/TLS fingerprint gate: the
  exact same `curl_cffi chrome124` client that gets rate-limited after many
  quick calls succeeds cleanly again once paced out). This actor paces
  sequential list-page requests (`LIST_PAGE_DELAY` in `constants.py`) and
  retries with exponential backoff on failure; production runs should also
  lean on Apify's residential proxy pool (this actor's default
  `proxyConfiguration`) so successive requests aren't all attributed to one
  IP.
- **A single-OCID detail lookup for an unknown/invalid OCID returns a clean
  `404` with no body** — treated as a `not_found` per-record error, not a
  retryable failure.
- **No server/CDN bot-challenge fingerprint observed** beyond the rate
  limiting above — no CAPTCHA page, no JS challenge, no `cf-ray`/DataDome/
  PerimeterX markers on any response.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default. No
profile-specific blocking was observed — the rate limiting above triggers
identically regardless of TLS profile (it's a request-volume signal, not a
fingerprint check), so no fallback profile was needed.
