# Crawling Method — Pakistan Government Tenders (PPRA-EPMS)

**Last verified:** 2026-08-27

## Which portal, and how it was verified

Pakistan's national procurement regulator is the **Public Procurement
Regulatory Authority (PPRA)**, an autonomous body under the Cabinet
Division. Its main informational domain is **`ppra.gov.pk`**
(`www.ppra.org.pk`, the domain first guessed from the actor name, is a live
302 redirect to `ppra.gov.pk` — not a dead/decoy domain, just an older
alias). During recon, `ppra.gov.pk` was returning a **genuine
`500 Internal Server Error`** on every path tried, including `/robots.txt`
and `/` — a WAF "Web Page Blocked" page (`Attack ID 20000018`) rendered
instead of the real site. This was confirmed as a real server-side
condition (not a local/network block) by reproducing the identical failure
from two independent networks (this actor's own connection and a separate
fetch from unrelated infrastructure).

The actual tender data lives on a separate, fully functional application:
**PPRA e-Publish & Monitoring System (PPRA-EPMS)** at **`epms.ppra.gov.pk`**
— found via web search (an "Active Tenders - PPRA" result pointed directly
at `epms.ppra.gov.pk/public/tenders/active-tenders`) and independently
confirmed live: real listings dated 2026-08-27, the same day as recon, with
~1,859 active tenders across 38 pages. **This is the domain this actor
scrapes** — `ppra.gov.pk`'s outage is irrelevant to this actor's function.

## Robots.txt and login wall

- `epms.ppra.gov.pk/robots.txt` returns the application's own generic
  "Page Not Found" template (a real 404 page, not a raw web-server error) —
  there is no robots.txt file on this host at all. No Disallow, no
  AI-crawler mention of any kind.
- **No login wall for viewing.** `epms.ppra.gov.pk/` (the root) redirects to
  `/login` — but that's the back-office UI for procuring agencies to
  *publish* new tenders, not the public listing. Every path under
  **`/public/tenders/*`** — the active-tenders listing, the tender-history
  archive, per-tender detail pages, and per-tender invoice pages — returns
  full `HTTP 200` content with zero cookies/auth from a completely cold
  client. This matches the transparency-law hypothesis established across
  this vertical (Ghana, Zambia, Jamaica, Nepal, etc.): tender notices are
  legally public in Pakistan, unlike the login-gated pattern common among
  business-registry actors in this collection.

## No WAF / TLS gate on the EPMS host

Plain `curl` with a standard desktop User-Agent — no TLS impersonation at
all — got clean `200 OK` on every `/public/tenders/*` path tried, across
dozens of requests (unfiltered listing, filtered listing, pagination past
the last page, detail, invoice, a deliberately invalid tender number). No
Cloudflare/Akamai/DataDome response headers, no CAPTCHA, no challenge page.
`curl_cffi` `chrome124` is used anyway for portfolio-wide consistency, but
this specific host does not appear to require it (unlike its sibling
`ppra.gov.pk`, whose WAF is actively blocking *everything*, bot or not).

## Pagination — genuinely stateless and reliable

Unlike `nepal-tenders-scraper`'s Bolpatra (flaky row counts, broken "Next"
button in a scripted client), `epms.ppra.gov.pk`'s `?page=N` (1-indexed)
query param is plain, stateless, and reliable:

- Repeated identical requests to the same page returned identical row
  counts (50/page) every time.
- A request past the last page (`?page=999` against a 38-page listing)
  returns `HTTP 200` with an **empty `<tbody>`** and only a "Previous"
  pagination link (no "Next") — not an error, not a wraparound to page 1.
- Binary-searching the real active-tenders listing found **37 full pages of
  50 + 1 partial page of 9 = 1,859 total active tenders** at recon time.

This actor pages forward automatically, stopping at whichever comes first:
the `maxResults` cap, a page with zero rows, or a page whose own pagination
widget has no "Next" link.

## Listing filters — reverse-engineered from `#filterForm`'s own markup

`#filterForm` (`method="GET"`, action empty — i.e. submits back to the same
URL) on both `/active-tenders` and `/tenders-history` exposes, confirmed
live against the actual `<select>`/`<input>` markup:

| Query param | Confirmed behavior |
|---|---|
| `keyword` | Free-text. Confirmed live: `keyword=road` returned road-construction/road-branch-renovation tenders (matches title/description/tender_no per the input's own placeholder). |
| `tender_no` | Exact/partial PPRA tender number. |
| `procurement_category` | `1`=Goods, `2`=Works, `3`=Consultancy Services, `4`=Non-consultancy Services. Confirmed live: `procurement_category=2` returned only Works-tagged rows. |
| `sector` | 29 fixed values (ids 26/27/31 are gaps in PPRA's own numbering, not a scraping bug) — see `constants.py`'s `SECTOR_MAP`. |
| `tender_type` | `1`=Tender Notice, `2`=Pre-qualification Notice (PQ), `3`=Request for Proposal (RFP), `4`=Expression of Interest (EOI). |
| `tender_nature` | `0`=Local, `1`=International. |
| `status` | `1`=Published, `2`=Cancelled. |
| `organization` | Numeric ID from a 500+-option `<select>` of individual procuring offices — too large to enumerate in this actor's input schema, exposed as an optional free-form `organizationId` passthrough instead. |
| `country` | Numeric ID, same treatment (`countryId`). |
| `advertise_date_from` / `advertise_date_to` / `closing_date` | `YYYY-MM-DD` date filters. |
| `page` | 1-indexed page number. |

No CSRF token, no session priming, no `Referer` requirement observed for
any combination of the above across dozens of calls.

## Listing table shape

Both `/active-tenders` and `/tenders-history` render an identical 8-column
table (`Sr`, `Tender No`, `Tender Details`, `Organization Details`,
`Status`, `Advertised`, `Closing`, `Actions`) — confirmed identical `<th>`
text on both pages. `tenders-history` additionally surfaces a `Closed`
status badge not observed on `/active-tenders`. Each row's "Tender Details"
cell carries two badge-style tags: the first is the tender's PPRA sector
(e.g. "Services"), the second is the *procuring office's own* reference
number (confirmed by cross-referencing against the same value's
"Reference Number/Tender No. of procuring Agencies" column on that same
tender's invoice page) — distinct from PPRA's own `tenderNo` used
throughout this actor's URLs.

## Tender detail page

`GET /public/tenders/tender-details/<tenderNo>` renders several
`div.detail-card` sections (Organization/Office Details, Tender
Information, Important Dates, Financial Information, Procurement &
Workflow), each a `list-group` of label/value pairs. **Several fields are
conditionally rendered per-tender** depending on what the procuring office
filled in — confirmed directly in the raw HTML: a tender with no estimated
cost entered ships that entire list-group-item as an HTML comment rather
than an empty value, and Contact Person/Email/Phone are each independently
optional. This actor parses every section generically (slugifying each
visible label into a camelCase key, the convention established by
`ghana-tenders-scraper`/`nepal-tenders-scraper`) rather than hardcoding a
fixed field list, so per-tender-type field variation flows through
automatically instead of being silently dropped or crashing.

**Not-found gotcha**: an unknown/made-up tender number does **not** 404 —
it gets a `302 Found` redirect straight to `/public/tenders/active-tenders`
(confirmed on a deliberately invalid `tenderNo`, `TS9999999999X`).
`curl_cffi` follows redirects by default, so the client sees a `200 OK`
active-tenders listing page instead of a detail page. This actor's parser
checks the response's `<h1>` text and treats an exact match against
`"Active Tenders"` (the listing page's own heading) as the not-found
signal — the same shape of gotcha (a redirect/200 masquerading as success)
documented for several sibling actors in this collection that hit an
HTTP-200 "empty template" instead of a real 404.

## Invoice page (bonus data, not scraped by default)

`GET /public/tenders/invoice/<tenderNo>` is a printable PPRA
publication-fee invoice: procuring-agency address, PPRA bank details, and a
`Total Amount (PKR)` line (e.g. `15,000` observed for one real tender —
the fee PPRA itself charges to *publish* a notice, not a bid/tender
financial figure). This is a minor, distinct data point from everything
else on the detail page. This actor surfaces `invoiceUrl` as a link on
every record rather than fetching it by default — one request per tender
for `mode: "detail"` instead of two, matching this project's convention of
not adding a second request for a field that's a nice-to-have rather than
core tender data.

## Diff cadence

Quarterly smoke test recommended. This is an actively-maintained, modern
Bootstrap/PHP application (unlike the older Struts/JBoss stack seen on
Ghana/Nepal), so column headers and filter param names are reasonably
likely to stay stable, but a full page re-fetch and re-read of
`/public/tenders/active-tenders`'s own `#filterForm` markup is the right
first step if a listing/detail parse starts raising `UnexpectedShape`.
