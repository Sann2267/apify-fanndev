# Crawling Method — Nepal Government Tenders (PPMO e-GP / Bolpatra)

**Last verified:** 2026-08-27

## Which portal, and how it was verified

Nepal's national e-Government Procurement (e-GP) system is operated by the
**Public Procurement Monitoring Office (PPMO)**, an apex body under the
Office of the Prime Minister and Council of Ministers, at
**`bolpatra.gov.np`** (all data endpoints live under the `/egp` context
path). This was cross-checked two ways before building anything:

- PPMO's own informational site, `ppmo.gov.np`, explicitly documents
  `www.bolpatra.gov.np` as "the e-GP system" in its own published content.
- Independent web search results (procurement-consulting blogs, a
  third-party tender-search aggregator) consistently describe
  `bolpatra.gov.np` as Nepal's live, current e-GP portal for 2026 -- not a
  decommissioned or superseded domain.

A separate, older open-data initiative — the **Public Procurement
Transparency Initiative in Nepal (PPTIN)**, published via
`ppip.gov.np` — released bulk OCDS (Open Contracting Data Standard)
exports (JSON/CSV/XLSX) covering May 2016–August 2018, but **that domain
no longer resolves and the dataset was never updated past 2018** (per its
own listing on the Open Contracting Partnership's public data registry).
**Not used by this actor** — everything here is scraped live from
`bolpatra.gov.np` itself, which has 200,000+ tenders spanning far more
recent activity (tenders published today, 2026-08-27, were live during
recon).

## Robots.txt and login wall

- `bolpatra.gov.np/robots.txt` and `bolpatra.gov.np/egp/robots.txt` both
  return a **plain JBoss 404 error page** — there is no robots.txt file on
  this host at all. No Disallow, no AI-crawler mention of any kind (the
  same "no robots.txt exists" situation independently confirmed for
  `ghana-tenders-scraper`'s GHANEPS, this vertical's first actor — possibly
  common among older Struts/JBoss-era government e-GP deployments).
- `ppmo.gov.np/robots.txt` (not used for data, only cross-referenced during
  recon) is a plain `User-agent: * / Crawl-delay: 10`.
- **No login wall for viewing.** The public "Search Opportunities" page
  (`/egp/searchOpportunity`), both of its AJAX result endpoints, the
  public-entity autocomplete, and the per-tender detail popup are all
  reachable with zero cookies/auth from a cold client. A login is required
  only to submit a bid or register as a vendor — confirmed by the site's
  own top navigation, which lists "Published Bids", "Annual Procurement
  Plans", "Blacklisting Info", "e-Contracts", and "Contract Records" as
  plain, unauthenticated links alongside a separate login form. This
  matches the transparency-law hypothesis established by this vertical's
  first actor (Ghana GHANEPS): tender notices are legally public, unlike
  the login-gated pattern common among business-registry actors in this
  collection.

## TLS gotcha: incomplete certificate chain

`bolpatra.gov.np` serves only its own leaf certificate
(`CN=*.bolpatra.gov.np`, issued by `DigiCert Global G2 TLS RSA SHA256 2020
CA1`) without the DigiCert intermediate certificate needed to complete the
chain. A client that does OS-level chain building/AIA-fetching (Windows's
`schannel`-backed `curl`, browsers) accepts this silently; `curl_cffi`'s
bundled OpenSSL cert store does not and fails every request with
`CertificateVerifyError: unable to get local issuer certificate` until
`verify=False` is set explicitly (see `src/client.py`). This is the exact
same class of bug independently found and documented for
`nepal-ocr-scraper`'s `camis.ocr.gov.np` — apparently not uncommon on
Nepali government TLS deployments. Confirmed as a real server
misconfiguration (not a local/proxy artifact) by reproducing the identical
failure from a clean residential connection with no proxy in the loop, and
by independently inspecting the certificate chain with `openssl s_client
-showcerts`, which shows only one certificate in the chain.

Separately: a request with **no `User-Agent` header at all** gets a flat
`403 Forbidden` from the front-end `nginx` reverse proxy — unrelated to
TLS, and not observed with any of the several UA strings tried (this is
just a bare-UA block, not a fingerprint/WAF gate; every profile tried with
a normal desktop UA string succeeded).

## The listing search — reverse-engineered from the search page's own markup

`/egp/searchOpportunity` (a plain GET, no params) renders a full,
server-side HTML page containing:

1. A "recent opportunities" widget, populated on page-load via an AJAX
   `POST` to `searchBidDashboardHomePage` with **no body/filters at all**
   — this call works fully cold, no session/cookie needed, and always
   surfaces bolpatra's own idea of "recent". Used for this actor's
   unfiltered ("latest") listing.
2. A "Search Opportunities" form (`id="searchBidForm"`) whose fields map
   directly to a second AJAX endpoint, `SearchOpportunitiesResultHomePage`
   (`POST`, `application/x-www-form-urlencoded`):

   | Form field | Meaning |
   |---|---|
   | `bidSearchTO.title` | Free-text keyword matched against the project title |
   | `bidSearchTO.ifbNO` | Exact/partial IFB-RFP-EOI-PQ reference number |
   | `bidSearchTO.procurementCategory` | `-1`=all, `1`=Goods, `2`=Works, `3`=Consultancy, `4`=Other Services |
   | `bidSearchTO.procurementMethod` | `-1`=all, `1`=NCB, `2`=ICB, `3`=Sealed Quotation, `4`=Direct Purchase, `5`=QCBS, `6`=QBS, `9`=FBS, `11`=Commodity Purchase, `12`=Ration, `13`=User Committee, `14`=Force Account, `15`=Least Cost Selection |
   | `bidSearchTO.publicEntity` | Numeric ID of the procuring entity (see below — NOT the free-text name) |
   | `bidSearchTO.contractType` | Contract-type enum (not exposed by this actor's input, minor scope cut) |
   | `bidSearchTO.NoticePubDateText` / `bidSearchTO.lastBidSubmissionDateText` | `dd-mm-yyyy` date filters (not exposed by this actor's input) |

   Both endpoints return the same server-rendered fragment: a
   `<table id="dashBoardBidResult">` with a fixed 9-column header (Sl. No.,
   IFB/RFP/EOI/PQ No., Project Title, Public Entity Name, Procurement
   Type, Status, Notice Published Date, Last Date of Bid Submission, No of
   Days Left) plus a hidden `totalRecords` field giving the true match
   count across bolpatra's whole history (207,222 total tenders observed
   during recon, unfiltered).

3. `getSimilarPENames?term=<text>` — a clean, public, unauthenticated JSON
   autocomplete endpoint returning `[{"id": "...", "name": "..."}, ...]`.
   **Confirmed that filtering by `bidSearchTO.publicEntityTitle` (the raw
   free-text name) alone, with no ID set, matches ZERO records** — the
   real filter field is the numeric `bidSearchTO.publicEntity` ID. This
   actor calls the autocomplete endpoint first and uses the first
   suggestion's ID whenever a `publicEntityName` input is given.

No cookies, no CSRF token, and no `Authorization` header of any kind were
required for any of the above — confirmed across dozens of calls
(unfiltered, keyword-only, category-only, entity-ID-only, and combined
filters, from a completely cold client).

## Critical gotcha: page size is flaky and NOT a controllable parameter

The listing fragment also carries hidden pagination-state fields
(`currentPageIndex`, `pageSize`, `totalRecords`, `startIndex`,
`numberOfPages`, `isNextAvailable`, `isPreviousAvailable`) and the search
page's own `pager.js` posts `currentPageIndexInput` /
`pageSizeInput` / `pageActionInput` back to request a different page or
page size. **Extensive testing (this actor's recon) could not get this to
work reliably**:

- Sending `pageSizeInput` with any value (10, 30, 50, 100, 500, 1000) had
  **no observed effect** on the actual row count returned, in any
  combination of session-priming and filter fields tried.
- Resending `currentPageIndexInput`/`pageActionInput=next` — including a
  full round-trip of every hidden state field exactly as `pager.js` itself
  would send them, with the session cookie carried along — **always reset
  to page 1** in a scripted client. The real "Next" button's actual
  behavior likely depends on additional in-page JavaScript state this
  client does not execute/reproduce.
- **The row count itself is non-deterministic**: repeated, identical
  requests (same filters, same fresh-session priming, minutes apart) were
  observed returning **10 rows on some calls and 30 on others**, with no
  request-side variable found that reliably predicted which. This is most
  plausibly a server-side inconsistency (e.g. a load-balanced cluster with
  mixed node config/cache) rather than anything client-controllable.

Given this, **this actor does not claim exhaustive pagination it cannot
actually deliver.** It performs one query, parses however many rows that
one response actually contains, and reports the real count as
`_totalReturned` on every record (alongside `_totalAvailable`, bolpatra's
own reported total match count for the filters used) — so a caller who
needs broader coverage than one page should narrow their `keyword` /
`procurementCategory` / `procurementMethod` / `publicEntityName` filters
to shrink `_totalAvailable` down to something a single page can cover,
the same guidance given by other per-query-capped actors in this
collection.

## Tender detail page

`GET /egp/getTenderDetails?tenderId=<id>` (no auth) returns a small HTML
fragment with several sections, each its own `<table cellpadding="10">` of
label/`<td>` value pairs: basic info (public entity, category, method, IFB
number, project name, current status, source of funds, notice publication
date), bid information, funding information, bid schedule (pre-bid
meeting, bid opening, submission deadlines and addresses), bid fee
details, and procurement-entity contact details. This actor parses these
generically — slugifying each visible label into a camelCase key (per the
convention established by this vertical's first actor,
`ghana-tenders-scraper`, which does the same for its `<dl class="Grid">`
detail page) rather than hardcoding a fixed field list, so upstream label
additions/renames flow through automatically instead of being silently
dropped.

Four more sections (Bid Document, Addendum, Bid Query Response, LOI) list
downloadable documents in their own tables. **A markup quirk**: bolpatra's
own HTML leaves each of these tables' header `<tr>` unclosed, so the
actual data row ends up nested *inside* it (via a lenient parser) rather
than as a sibling. Recursing to find every `<tr>` but restricting `<td>`
lookup to *direct* children of each `<tr>` (not recursive) is what avoids
triple-counting the same document row through each of its accidental
ancestor `<tr>` elements — see `_parse_documents` in `src/extractor.py`.

**Not-found gotcha**: an unknown/out-of-range `tenderId` returns
**`HTTP 200` with the exact same template, every value blank** — not a
404, not an error status. Confirmed on a deliberately out-of-range id
(`999999999`). This actor treats a blank "Public Entity Name" field as the
not-found signal, the same shape of gotcha documented for several other
actors in this collection (an HTTP-200 "empty template" instead of a real
404).

## Data quirk: dates and "days left"

Dates throughout (`noticePublishedDate`, `lastDateOfBidSubmission`,
`noticePublicationDate`, bid schedule dates, etc.) are Gregorian
`dd-mm-yyyy HH:MM` as displayed by bolpatra itself — passed through
unconverted. The listing's `daysLeft` column is free text and can read
`"N days"` for an open tender or **`"Expired"`** for one whose submission
deadline has passed (confirmed on a real closed 2023 tender still
reachable via a public-entity-filtered search) — not a numeric field,
passed through as-is per this project's raw-passthrough convention.

## Diff cadence

Quarterly smoke test recommended. This is an older, actively-used
government Struts2/JBoss application (not a modern SPA), so the two AJAX
action names and the `dashBoardBidResult` table id are reasonably likely
to stay stable across small deploys, but a full page re-fetch and re-read
of `/egp/searchOpportunity`'s form field names is the right first step if
`SearchOpportunitiesResultHomePage` or `getTenderDetails` start returning
unexpected shapes.
