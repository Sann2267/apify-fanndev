# Crawling Method — Uganda EGP (PPDA e-Government Procurement)

**Last verified:** 2026-08-27

## Finding the right portal

Three Uganda government procurement domains surface in search results;
only one is live:

| Domain | Status | Notes |
|---|---|---|
| `www.ppda.go.ug` | Live, but wrong system | PPDA's own WordPress marketing/policy site -- law text, guidelines, press releases. No notice data. |
| `gpp.ppda.go.ug` | **Dead** | "Government Procurement Portal" -- an older system. Every connection attempt during recon timed out (TCP connect timeout, not a 4xx/5xx) -- decommissioned, not merely slow. |
| `egpuganda.go.ug` | **Live, correct target** | "EGP Uganda" -- the actual e-Government Procurement system. Confirmed current via PPDA's own April 2026 press statement (hosted on `ppda.go.ug`) announcing e-GP rolling out to *all* procuring entities from 1 July 2026 -- this is that system. |

## robots.txt

```
User-agent: *
Disallow:
```

Blanket-allow. No Claude/AI-crawler mention anywhere. No `Crawl-delay`.

## No anti-bot gate found

Every endpoint this actor touches -- the homepage, `/bid-notices`, the
archived-notices AJAX endpoint, and both notice-detail page patterns --
returned `HTTP 200` with real content on a **plain, default-TLS `curl`
request with no impersonation and no special headers.** Response headers
show plain `Apache`, standard Laravel session/CSRF cookies
(`egp_uganda_session`, `XSRF-TOKEN`), no Cloudflare/Akamai/DataDome/WAF
markers of any kind. This actor still uses `curl_cffi` (`chrome124`
profile) for portfolio consistency and because a residential proxy in front
of it still negotiates its own TLS fingerprint, but it is not load-bearing
here -- unlike `uganda-ursb-scraper`'s API host, which 403s on plain `curl`
and needs a Chrome-impersonating TLS profile to clear a fingerprint-only
gate. Same country, same government, genuinely different infrastructure
tier between agencies.

## No login wall for viewing

Confirmed directly: a notice's full title, reference number, procuring
entity, and description text render in plain HTML with **no auth check** on
`GET /index/<notice_id>_egp`. The only login-gated action found is
*applying* -- the detail page's own call-to-action button reads "Click here
To Apply" and links to `/login`. This matches Uganda's Public Procurement
Act requirement that notices be openly published, and the portal's own
copy stating the public can view notices without registering.

## Site structure: six tabs hiding behind three visible labels

`/bid-notices` looks at first glance like it has three tabs ("Bid Notices",
"Disposal Notices", "Announcements" from the homepage's mini-preview
widgets, or "Archived Procurement/Disposal/bid opening Notices" from the
`/bid-notices` page's own `<h6>` titles) but its actual `tab-pane` markup
has **six** ids: `procurement`, `disposal`, `opening` (all *currently open*,
fully server-rendered plain `<table>`s, no AJAX) and `bid_archives`,
`disposal_archives`, `opening_archives` (all *archived/closed*, empty
`<tbody>` in the initial HTML, populated client-side by a `POST` AJAX call
each). It is easy to only notice the archived set (their `<h6>` headers are
much more prominent in the markup) and wrongly conclude the live/open tab
doesn't exist or is JS-only -- it doesn't need JS at all, it's just further
up the page.

This actor's `mode="latest"` scrapes `#procurement` directly (small list --
at recon time, Uganda's FY2026-2027 had only just started, so single
digits). `mode="archived"` drives the `bid_archives` AJAX endpoint:

```
POST https://egpuganda.go.ug/public-bids/api-archived-notices/ajax
Content-Type: application/x-www-form-urlencoded
_token=<csrf>&draw=1&start=<offset>&length=<page size>[&is_category=<financial year>]
```

`_token` is a standard Laravel CSRF token, read from the hidden
`<input name="_token">` on any normal page (e.g. `/bid-notices` itself,
fetched once per client session and cached) alongside the matching
`egp_uganda_session` cookie curl_cffi's `AsyncSession` carries
automatically. This is CSRF protection tied to an anonymous session, not
authentication -- no login, username, or password involved.

`is_category` (an odd but confirmed-correct parameter name for what the
site's own UI calls "Filter By Financial Year") narrows results to one
Ugandan financial year, e.g. `"2025-2026"`; omitted or blank returns all
years (500 total bid notices at recon time, back to at least 2019-2020
per the UI's own year dropdown).

## Universal notice-detail page works regardless of notice age/status

```
GET https://egpuganda.go.ug/index/<notice_id>_egp
```

Confirmed working (`HTTP 200`, full content, no login) for both a live
2026-2027 open notice and a 2024-2025 archived one -- **the same URL
pattern serves every notice ID regardless of status.** It carries the
notice-type heading (e.g. "Request for Quotation Notice"), the reference
number, the full untruncated subject, and a boilerplate-wrapped description
body -- but **no dates**. Published/deadline dates only exist on whichever
listing surfaced the notice ID; this actor merges listing fields with
detail-page fields rather than treating either as the sole source.

## Gotcha: listing subjects are truncated by upstream, not by this actor

Both `#procurement`'s live table and the archived-notices AJAX response
truncate long subjects with a literal `"..."` (e.g. "FRAMEWORK CONTRACT FOR
SUPPLY OF ELECTRICAL I..."). This is upstream's own listing-view behavior,
confirmed by comparing against the same notice's detail page, which carries
the untruncated string. `fetchDetails=true` (default) fetches the detail
page specifically to recover this; with it off, `subject_of_procurement` /
`subject_procurement` may be truncated.

## Gotcha: dropped HTML-rendering fields (archived AJAX)

The archived-notices AJAX response mixes clean upstream fields
(`procurement_ref`, `procurement_name` [entity], `subject_procurement`,
`submission_deadline`, `bid_opening_date`/`bid_opening_time`, `body`,
`financial_year`, `procurement_method`, `procurement_type`, `notice_type`,
etc. -- all passed through verbatim) with **six** fields that are
pre-rendered HTML fragments meant for the site's own DataTables UI:
`procuring_entity`, `type`, `procurement_subject`, `published_date`,
`deadline_date`, `action_links`. Each one duplicates data that's already
present cleanly elsewhere in the same record (e.g. the HTML-fragment
`procuring_entity` field contains the same entity name as the clean
`procurement_name` field, wrapped in `<div>`/`<a>`/`<span>` markup plus an
embedded court-of-arms `<img>`). This actor drops those six and replaces
them with one derived `notice_id` (regex-parsed from the embedded
`<a href="/index/<id>_egp">`), rather than shipping raw HTML soup into the
dataset. This is a deliberate exception to strict raw-passthrough --
documented here per the project's "never fail silent, never fabricate"
principle: nothing is invented, redundant markup is just not duplicated.

`procurement_name` (upstream's own field name for what is actually the
**procuring entity**) is passed through unrenamed despite being a
confusing label -- it's upstream's own naming, not a mistake in this actor.

## Gotcha: HTML-entity-escaped raw string fields

Several of the archived-notices AJAX endpoint's own clean string fields
(e.g. `procurement_name`, `body`) come back HTML-entity-escaped from
upstream itself (`"Ministry of Finance, Planning &amp; Economic
Development"`, `&#039;` for apostrophes) -- the same escaping their Blade
templates apply, leaking into the JSON API. This actor decodes entities
(`html.unescape`) on every string value in an archived record for
readability; this is not a rename or reshaping, just decoding characters
upstream itself encoded.

## Opportunistic enrichment: bid-opening results

```
GET https://egpuganda.go.ug/bid/notice/<notice_id>/opening/details
```

A second, richer detail page -- "RECORD OF BID OPENING" -- exists once a
notice has reached that stage: procurement method, bid-opening date/time,
number of bids received, and (genuinely valuable public-transparency data)
a table of every bidder's name, address, submission timestamp, and bid
amount. Confirmed this reliably returns **HTTP 500** (not 404) for a notice
that hasn't reached this stage yet (e.g. any currently-open notice) --
treated by this actor as "not available yet," not a fatal error; the
notice's other fields are still returned.

## Sample IDs used during recon

- `390594566` (`UCAA/NCONS/2026-2027/00001`) -- live open notice, confirmed
  no bid-opening record yet (`HTTP 500` on that endpoint, as expected).
- `135377320` (`MoES/NCONS/2023-2024/00039`) -- archived notice with a full
  bid-opening result: 1 bidder, "EWB EAST AFRICA CONSULT LTD", amount
  `46,149,800.00` UGX.
- Financial-year filter `is_category=2025-2026` confirmed narrowing 500
  total archived bid notices down to 400.

## Known limits

- `mode="latest"` reflects whatever is genuinely open for bidding right
  now -- this can be a small number (single digits, seen at recon time
  right after Uganda's FY2026-2027 started) rather than a bug.
- Downloadable tender-document attachments were not found on any publicly
  viewable page -- likely gated behind the supplier login/registration
  flow (consistent with "viewing is public, applying requires an account"),
  out of scope for this actor per the no-login-flow policy.
- Disposal notices (asset sales) and pending bid-opening notices exist on
  the same site (`#disposal`/`#opening` tabs, `disposal_archives`/
  `opening_archives` AJAX endpoints) but are not covered by this actor's
  input modes -- documented here as a straightforward future extension
  using the same client/extractor patterns.

## Diff cadence

Quarterly smoke test recommended. PPDA's own April 2026 press statement
about e-GP rolling out to all entities from 1 July 2026 suggests active
development on this system through 2026 -- route/response shapes could
shift on a redeploy.
