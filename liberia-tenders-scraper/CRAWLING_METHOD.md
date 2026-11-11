# Crawling Method — Liberia Government Tenders (e-GP / PPCC)

**Last verified:** 2026-08-27

## Target discovery — official portal confirmed, third-party aggregators avoided

Liberia's public procurement regulator is the **Public Procurement and
Concessions Commission (PPCC)**, domain `ppcc.gov.lr` (a Drupal site,
Executive Mansion Grounds, Capitol Hill, Monrovia). Its **E-Services** page
links out to a dedicated Electronic Government Procurement (e-GP) platform
at `eprocurement.ppcc.gov.lr` -- this actor targets that platform, not
`ppcc.gov.lr` itself.

Several commercial tender-aggregator sites came up in search results
(`liberiatenders.com`, `tendersontime.com`, `tendersinfo.com`,
`biddetail.com`) -- these are third-party paid-subscription services, not
official government sources, and were deliberately not used.

### The e-GP platform is the "European Dynamics"/ePPS family, confirmed by URL fingerprint

`eprocurement.ppcc.gov.lr`'s homepage (`/epps/home.do`) exposes the exact
same `.do`-action URL scheme already documented for
`ghana-tenders-scraper` (GHANEPS), `zambia-tenders-scraper` (ZPPA), and
`jamaica-tenders-scraper` (GOJEP) -- all built on the "European Dynamics"
e-Public Procurement System ("ePPS"). Confirming details:

- Listing links: `/epps/prepareCurrentOpportunities.do?currentType=cft`,
  `/epps/common/viewOpenedTenders.do`, `/epps/viewAllAwardedContracts.do` --
  the last two are **byte-identical path names** to GHANEPS's.
- Tender detail: `/epps/cft/prepareViewCfTWS.do?resourceId=<id>` -- same
  action name as GHANEPS.
- Listing tables all use `<table id="T01">`, a DisplayTag-style shell, and
  the pagination "widget id" query params found in Liberia's pages
  (`d-3680175-p=` for "current", `d-3680181-p=` for "opened",
  `d-3998960-p=` for "awarded") are the **exact same numeric ids** already
  documented for GHANEPS in `ghana-tenders-scraper/CRAWLING_METHOD.md` --
  strong confirmation this is the same underlying multi-tenant deployment,
  just with a newer Bootstrap-themed skin and Liberia's own data.
- An OCDS (Open Contracting Data Standard) portal is also linked
  (`/ocds/report/home.action`), but it's a client-driven "Report Creation
  Form" (Angular-style report builder), not a simple JSON endpoint like
  Tanzania's NeST -- not pursued further given the HTML-table approach
  below already works well and is a proven pattern across three sibling
  countries.

Liberia's deployment is a **newer UI version** than Ghana's: the
tender-detail page uses `<dl class="row no-gutters">` (Bootstrap grid
markup) rather than Ghana's `<dl class="Grid">` -- same dt/dd label/value
structure underneath, just different CSS classes.

## robots.txt / WAF

`ppcc.gov.lr/robots.txt` is a standard Drupal-generated file: only disallows
`/core/`, `/profiles/`, `/admin/`, `/user/login` etc. (framework internals
and admin routes) -- nothing under `/opportunities/` or anywhere this actor
touches, no blanket `Disallow: /`, no mention of `Claude`/`ClaudeBot`/
`anthropic-ai` anywhere.

**`eprocurement.ppcc.gov.lr/robots.txt` does not exist as a real file** --
same finding as GHANEPS: the Struts app 302-redirects any unmapped path
(including bare `/` and `/robots.txt`) straight to `/epps/home.do`.
Confirmed directly with plain `curl -v`: `HTTP/1.0 302 Moved Temporarily`,
`Location: https://eprocurement.ppcc.gov.lr/epps/home.do`. Since no robots
file is ever actually served, there is no `Disallow` rule of any kind and
no plain-English AI/bot prohibition to find on this host either.

**Quirk:** `curl_cffi` (any impersonation profile) reliably raises
`curl: (56) Connection closed abruptly` specifically on that bare-redirect
response for `/` and `/robots.txt` -- while plain `curl`/`requests` follow
it fine. Every real `.do` action URL this actor touches (`home.do`,
`prepareCurrentOpportunities.do`, `viewOpenedTenders.do`,
`viewAllAwardedContracts.do`, `prepareViewCfTWS.do`) was rock solid across
dozens of `curl_cffi chrome124` requests with zero retries needed -- this
actor simply never requests `/` or `/robots.txt` directly, matching the
precedent already documented in `ghana-tenders-scraper/CRAWLING_METHOD.md`
for the identical symptom on the identical platform family.

No other WAF/CDN fingerprint was observed anywhere on this host: no
`cf-ray`, no bot-challenge HTML, no `_abck`/`bm_sz`/`__cf_bm` cookies.

## No login required to view listings or tender detail

This was the key stop/go condition, checked directly against real data --
not assumed:

- `GET /epps/prepareCurrentOpportunities.do?currentType=cft` ("Current
  Opportunities") → `200`, real live data (a tender published the day
  before this actor was built), zero cookies/auth needed.
- `GET /epps/common/viewOpenedTenders.do` ("Opened Bids") → same.
- `GET /epps/viewAllAwardedContracts.do` ("Awarded Contracts") → same.
- `GET /epps/cft/prepareViewCfTWS.do?resourceId=<id-from-a-listing>` (full
  tender detail) → same, `200` with the complete field set, for ids pulled
  from **all three** listings including a 17-month-old awarded contract
  (`resourceId=2933`, awarded 2025-01-06) and an in-evaluation opened bid
  (`resourceId=246999`) -- i.e. this platform does **not** gate detail
  pages behind a post-deadline login wall the way `zambia-tenders-scraper`
  found for ZPPA.

A **login wall does exist**, but only for: (1) actually bidding/registering
as a supplier, and (2) `resourceId` values invalid or outside what the
public listings ever surface. Confirmed empirically: `resourceId=1` and
`resourceId=999999999` (neither ever surfaced by any listing) both
302-redirect to `/cas/login?service=...` (a CAS single-sign-on login page
titled for the e-GP platform), while every id pulled from an actual listing
renders fully with zero auth. Detected in code via the final (post-redirect)
response URL containing `/cas/login` -- more robust than matching page
title text, since this platform's login page is a full CAS redirect (host
+ path change) rather than an in-app "Welcome to e-PPS" page like GHANEPS.
Treated as a per-record `not_found_or_restricted` error, never a
general stop condition.

## No session/cookie warm-up needed

Unlike some e-GP deployments, a completely fresh, cookie-less `curl_cffi`
GET straight at any listing or detail URL returns identical, fully-populated
content to one issued after first visiting `/epps/home.do` to establish a
session. Verified directly by comparing response byte-lengths for both
approaches on all three listing views and the detail view. This actor
therefore issues one stateless GET per page/tender, exactly like
`ghana-tenders-scraper`, rather than maintaining a warm session.

## Data source — three listing views + one detail view, all server-rendered HTML

No JSON API or SPA bundle was found for the listing/detail data itself --
entirely `.do`-action, server-rendered HTML (JSP/Struts-era Java,
DisplayTag-style paginated tables), consistent with the "European Dynamics"
platform family.

### List views (`mode: "list"`)

| `listType` | URL | Total rows (2026-08-27) | Notes |
|---|---|---|---|
| `current` | `/epps/prepareCurrentOpportunities.do?currentType=cft` | 29 | Bids still open for submission. Columns: `#`, **Process No** (mislabeled -- actually holds the tender title + detail link, not a reference number; verified against raw HTML), PE, Info (hover tooltip = description), Bids Submission Deadline, Procedure, Status, Notice PDF, Publication Date. |
| `opened` | `/epps/common/viewOpenedTenders.do` | 961 | Submission closed, in evaluation/awarding. Columns: `#`, Subject of Process, PE, Bids Submission Deadline, Procurement method, Opened Bids (link), Award Date (usually blank), Status. No separate reference-number column exists on this platform's "opened" view (unlike Ghana's). |
| `awarded` | `/epps/viewAllAwardedContracts.do` | 352 | Finished contracts. Columns: Title, Procuring Entity, Provider Name, Award Date, Award amount (+currency, e.g. "4518.00 (USD)"), Package Number Code (the real tender reference), Grant or Loan Number (usually blank), Lot Name ("N/A" or a region list), Notice PDF. |

All three share the same table shell (`<table id="T01">`), so the parser
matches each required column **by its exact header label text**, not by
fixed index -- a future column reorder degrades gracefully (order-independent)
while a genuinely missing/renamed column raises `UnexpectedShape` (fail
loud) instead of silently mis-mapping data.

### Pagination — a numeric "widget id", discovered fresh each run

Every listing page's sort/page-nav links look like
`?d-3998960-p=2` -- `3998960` is an internal DisplayTag/table component id.
Observed stable per view (`current` = `3680175`, `opened` = `3680181`,
`awarded` = `3998960` -- coincidentally identical to GHANEPS's own ids for
the same three views) but, per the same reasoning documented for Ghana,
extracted fresh from page 1 of each run rather than hardcoded. The server
always returns 10 rows per page; no query parameter was found to change
this.

### Detail view (`mode: "detail"`)

`GET /epps/cft/prepareViewCfTWS.do?resourceId=<id>` renders a `<dl
class="row no-gutters">` (Bootstrap grid) of label/value pairs -- 41 fields
observed on a National Open Competitive Bidding tender (`resourceId=250740`):
procuring entity (+ org profile link), status, procurement type/method/
technique, evaluation mechanism, bid security requirements and amount,
tax clearance requirement, ISIC classification code, procurement estimate
amount, and the full submission/clarification/opening date timeline. The
field set genuinely varies by procurement type -- the parser walks the `dl`
generically: each `<dt>` label is slugified into a camelCase key (`"Bid
submission deadline date:"` → `bidSubmissionDeadlineDate`) and paired with
its `<dd>` text; if a `<dd>` contains a link, the href is captured too as
`<key>Url`. This is the raw-passthrough convention applied to an HTML
definition list -- new upstream fields flow through automatically instead
of being silently dropped.

**Field-name collision handled explicitly:** the detail page's own dt/dd
pair `"Resource ID:" → "procurement-250740"` would otherwise silently
overwrite this actor's own numeric `resourceId` key (used for URL
construction and as `_input` elsewhere in the dataset). `build_detail_record`
renames any parsed field whose slugified key collides with a reserved
output key to `<key>FromDetailPage` instead of dropping or silently
overwriting it.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was ever observed on real data endpoints -- the only friction found
anywhere on this domain was the bare-redirect quirk on `/` and `/robots.txt`
documented above, not anti-bot defense.
