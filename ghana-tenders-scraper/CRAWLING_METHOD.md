# Crawling Method — Ghana Government Tenders (GHANEPS)

**Last verified:** 2026-08-27

## Target discovery — GHANEPS is genuinely the official platform

The brief pointed at "GHANEPS" as a likely candidate, and this was confirmed
independently, not just taken at face value:

- Ghana's Public Procurement Authority (PPA, `ppa.gov.gh` — the statutory
  regulator under the Public Procurement Act, 2003 / Act 663) publishes its
  own page titled *"Implementation of the Ghana's Electronic Procurement
  System (GHANEPS)"* naming `ghaneps.gov.gh` as the mandatory e-procurement
  platform for all 869+ public entities.
- A World Bank blog post on Ghana's regulatory-service digitisation
  independently corroborates the same domain and rollout.
- The site itself (`www.ghaneps.gov.gh`) carries `<meta name="Creator"
  content="European Dynamics"/>` and a footer `© European Dynamics` — a real,
  known EU e-procurement software vendor that builds UNCITRAL/World-Bank-model
  e-GP platforms for multiple governments. This is a legitimate commercial
  procurement-software deployment, not a scraped-together or abandoned site
  (contrast with `ghana-rgd-scraper`'s finding that `rgd.gov.gh` itself is
  neglected/compromised — that finding does NOT apply to this separate
  platform).

No decoy or lookalike domain was found for this target (unlike the
`saintvincentregistry.com` scam site documented for St. Vincent's registry).

## robots.txt / WAF

`https://www.ghaneps.gov.gh/robots.txt` does not exist as a real file — the
app's own request router (this is a server-rendered Struts/JSP-era Java
webapp) 302-redirects **any** unmapped path straight to
`/epps/home.do`, the real homepage (confirmed by following the redirect and
diffing the body against a direct homepage fetch — byte-identical). Since
there's no file at all, there's no `Disallow` rule of any kind and no
plain-English AI/bot prohibition to find, on either the `www` or apex
hostname.

No WAF/CDN fingerprint was observed anywhere on this host: responses carry
`Server: Apache` (redirects) or no distinctive `Server` header at all on the
app responses, no `cf-ray`, no bot-challenge HTML, no `_abck`/`bm_sz`/`__cf_bm`
cookies. `curl_cffi` `chrome124`, `chrome99_android`, and `safari17_0` all get
clean `200`s with identical content on every page tested. (One early
`curl_cffi` attempt at `www.ghaneps.gov.gh/robots.txt` specifically returned a
`curl: (56) Connection closed abruptly` a few times in a row — retrying against
the apex domain `ghaneps.gov.gh/robots.txt` succeeded immediately, and repeat
attempts against `www` also later succeeded; this reads as ordinary
transient/rate-adjacent flakiness on that one bare-redirect endpoint, not a
fingerprint-based block — every other path was rock solid across dozens of
requests.)

## No login required to view listings or tender detail

This was the key stop/go condition, checked directly against real IDs found
from the site's own public listings — not assumed:

- `GET /epps/quickSearchAction.do?searchSelect=6` ("Current Tenders") → `200`,
  real live data, zero cookies/auth needed.
- `GET /epps/common/viewOpenedTenders.do` ("Opened Bids") → same.
- `GET /epps/viewAllAwardedContracts.do` ("Awarded Contracts") → same.
- `GET /epps/cft/prepareViewCfTWS.do?resourceId=<id-from-a-listing>` (full
  tender detail) → same, `200` with the complete `dl.Grid` of fields.

A **login wall does exist**, but only for two things this actor deliberately
does not touch: (1) actually bidding/registering as a supplier (`Log In` /
`Register as a Supplier` links on the homepage), and (2) `resourceId` values
that are invalid or reference records outside what the public listings ever
surface — those redirect to a CAS (`/cas/...`) login page titled *"Welcome to
e-PPS"* instead of a `404`. Confirmed empirically: `resourceId=3463468` and
`resourceId=3448475` (both pulled straight from the public listing pages)
render fully; `resourceId=1`, `resourceId=100`, and `resourceId=9999999` (none
ever surfaced by any listing) all bounce to the CAS login page. The actor
treats this as a per-record `not_found_or_restricted` error, not a general
"login wall on viewing" stop condition — because every ID that real users can
actually discover through the site's own navigation works with zero auth.

## Data source — three listing views + one detail view, all server-rendered HTML

No JSON API or SPA bundle was found — this is entirely `.do`-action,
server-rendered HTML (JSP/Struts-era Java, DisplayTag-style paginated
tables), consistent with the "European Dynamics" footer credit.

### List views (`mode: "list"`)

| `listType` | URL | Total rows (2026-08-27) | Notes |
|---|---|---|---|
| `current` | `/epps/quickSearchAction.do?searchSelect=6` | 65 | Bids still open for submission. Columns: Tender Title, Procuring Entity, Info (hover tooltip = description), Bids Submission Deadline, Procedure, Status, Notice PDF, Publication Date. |
| `opened` | `/epps/common/viewOpenedTenders.do` | 12,077 | Submission closed, in evaluation/awarding. Columns: CfT Title, Reference number, PE, Bids Submission Deadline, Procurement Method, Opened Bids (link), Award Date, Status. |
| `awarded` | `/epps/viewAllAwardedContracts.do` | 15,910 | Finished contracts. Columns: Tender Title, Procuring Entity, Supplier Name, Award Date, Award amount (+currency, or literal `N/A`), Lot Name (or `N/A`), Notice PDF. |

All three share the same table shell (`<table id="T01">`), so the parser
matches each required column **by its exact header label text**, not by
fixed index — a future column reorder degrades gracefully (order-independent)
while a genuinely missing/renamed column raises `UnexpectedShape` (fail
loud) instead of silently mis-mapping data.

### Pagination — a numeric "widget id", discovered fresh each run

Every listing page's sort/page-nav links look like
`?d-3680175-p=2&searchSelect=6` — `3680175` is an internal DisplayTag/table
component id. It was observed to be **stable** across repeat requests, fresh
sessions, and different TLS profiles for a given view (`current` always
`3680175`, `opened` always `3680181`, `awarded` always `3998960` in this
survey) — but since nothing guarantees it stays fixed across a future
redeploy, the client extracts it fresh from page 1 of each run
(`d-(\d+)-(?:s|p|n|o)=` regex) rather than hardcoding it, and builds
subsequent page URLs from that discovered value. The server always returns
10 rows per page; no query parameter was found that changes this (tried
`&d-<id>-n=100`, no effect).

**No server-side result cap beyond pagination** — `opened` and `awarded` can
run to 12,000–16,000 total rows. `maxResults` in this actor's input only
caps how many pages get fetched (each page is a fresh HTTP request, unlike
`ghana-rgd-scraper` where the whole result set downloads in one response) —
so a low cap here actually saves bandwidth/requests, not just output size.

### Detail view (`mode: "detail"`)

`GET /epps/cft/prepareViewCfTWS.do?resourceId=<id>` renders a `<dl
class="Grid">` of label/value pairs. The field set genuinely varies by
procurement type — an RFQ (Request for Quotation) tender has ~20 fields, a
National Competitive Tendering (NCT) one with a participation fee and bid
security has ~27, and a multi-lot tender adds one `Lot Name (N):` pair per
lot. Rather than declare a fixed schema, the parser walks the `dl` generically:
each `<dt>` label is slugified into a camelCase key (`"Bid submission
deadline date:"` → `bidSubmissionDeadlineDate`, `"Payment Amount
(GHS):"` → `paymentAmountGhs`) and paired with its `<dd>` text; if a `<dd>`
contains a link (e.g. the procuring entity's name links to its organisation
profile), the href is captured too as `<key>Url`. This is the raw-passthrough
convention applied to an HTML definition list instead of a JSON object — new
upstream fields flow through automatically instead of being silently dropped.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was ever observed — every response across `chrome124`,
`chrome99_android`, and `safari17_0` was identical modulo cosmetic
whitespace.
