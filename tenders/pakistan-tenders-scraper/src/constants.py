"""Endpoints, headers, enum mappings, and recon summary -- all in one place.

Recon summary (2026-08-27): Pakistan's national procurement regulator is the
**Public Procurement Regulatory Authority (PPRA)**, an autonomous body under
the Cabinet Division. Its main informational domain, `ppra.gov.pk` (the
`www.ppra.org.pk` domain 302-redirects here), was returning a genuine
`500 Internal Server Error` -- a WAF "Web Page Blocked" page (Attack ID
20000018) on EVERY path including `/robots.txt` -- confirmed from two
independent networks (this actor's own connection and a second, unrelated
fetch), so it is a real server-side condition, not a local block. **Not used
by this actor.**

The actual tender data lives on a separate, fully functional application:
**PPRA e-Publish & Monitoring System (PPRA-EPMS)** at **`epms.ppra.gov.pk`**
(found via web search -- "Active Tenders - PPRA" result pointed directly at
`epms.ppra.gov.pk/public/tenders/active-tenders`, independently confirmed
live with real, current listings dated 2026-08-27, the same day as recon).
This is the domain this actor scrapes. The EPMS root (`/`) redirects to
`/login` (an authenticated back-office for procuring agencies to publish
new tenders) -- but every path under **`/public/tenders/*`** is served with
zero auth, zero cookies-required, from a completely cold client.

## robots.txt

`epms.ppra.gov.pk/robots.txt` returns the app's own generic 404 page
(a real "Page Not Found" template, not a raw web-server 404) -- there is no
robots.txt file on this host at all. No Disallow, no AI-crawler mention of
any kind.

## No login wall for viewing

`GET /public/tenders/active-tenders` and `GET /public/tenders/tenders-history`
both return full, real, server-rendered HTML tables (50 rows/page, ~1,859
active tenders / 37 pages observed during recon) with zero auth. Per-tender
`GET /public/tenders/tender-details/<tenderNo>` and
`GET /public/tenders/invoice/<tenderNo>` are equally open. Only the back-office
publishing UI at EPMS's root is login-gated -- confirmed the transparency-law
hypothesis established across this vertical (tender notices are legally
public in Pakistan, same as Ghana/Zambia/Jamaica/Nepal/etc.).

## No WAF / TLS gate observed

Plain `curl` with a standard desktop User-Agent (no TLS impersonation at all)
got clean `200 OK` on every path tried, across dozens of requests (listing,
filtered listing, pagination past the last page, detail, invoice). No
Cloudflare/Akamai/DataDome headers, no CAPTCHA, no challenge page. `curl_cffi`
`chrome124` is used anyway for portfolio-wide consistency, but this host does
not appear to require it.

## Pagination -- genuinely stateless and reliable (unlike Nepal/Bolpatra)

`?page=N` (1-indexed) is a plain GET query param with NO session/cookie
dependency -- confirmed identical row counts on repeated cold requests to the
same page, and a request past the last page (`?page=999`) returns
`HTTP 200` with an EMPTY `<tbody>` and only a "Previous" pagination link (no
"Next") rather than erroring or wrapping around. This actor pages forward
until it sees either a `<tbody>` with zero rows, or a rendered row count
below the page size (50), or the `maxResults` cap is reached -- whichever
comes first.

## Listing filters -- reverse-engineered from `#filterForm`'s own markup

`#filterForm` (`method="GET"`) on both `/active-tenders` and
`/tenders-history` exposes, confirmed against the live `<select>`/`<input>`
markup:

| Query param | Meaning |
|---|---|
| `keyword` | Free-text, matched against title/description/tender_no per the input's own placeholder -- confirmed live (a `keyword=road` query returned road-construction/road-branch-renovation tenders). |
| `tender_no` | Exact/partial PPRA tender number, e.g. `TS0000012236E`. |
| `closing_date` | Single date (`YYYY-MM-DD`), tenders closing on that day. |
| `tender_type` | `1`=Tender Notice, `2`=Pre-qualification Notice (PQ), `3`=Request for Proposal (RFP), `4`=Expression of Interest (EOI). |
| `procurement_category` | `1`=Goods, `2`=Works, `3`=Consultancy Services, `4`=Non-consultancy Services -- confirmed live (`procurement_category=2` returned only Works-tagged rows). |
| `sector` | 29 fixed values, see `SECTOR_MAP` below. |
| `tender_nature` | `0`=Local, `1`=International. |
| `organization` | Numeric ID from a huge (500+) `<select>` of individual procuring offices -- not enumerable in this actor's input schema; exposed as a free-form optional `organizationId` passthrough for callers who already know an ID (e.g. from a previous run's `organizationName` field). |
| `country` | Numeric ID, mostly relevant to international tenders -- same treatment as `organization`, exposed as an optional passthrough. |
| `status` | `1`=Published, `2`=Cancelled. |
| `advertise_date_from` / `advertise_date_to` | Date range (`YYYY-MM-DD`) on the advertisement date. |
| `page` | 1-indexed page number (see Pagination above). |

No CSRF token, no session priming, no `Referer` requirement observed for any
of the above across dozens of calls.

## Listing table shape

Both `/active-tenders` and `/tenders-history` render the identical 8-column
table (`Sr`, `Tender No`, `Tender Details`, `Organization Details`, `Status`,
`Advertised`, `Closing`, `Actions`) -- confirmed identical `<th>` text on
both pages. `tenders-history` additionally surfaces a `Closed` status badge
not seen on `/active-tenders`.

## Tender detail page

`GET /public/tenders/tender-details/<tenderNo>` renders several
`div.detail-card` sections (Organization/Office Details, Tender Information,
Important Dates, Financial Information, Procurement & Workflow), each a
`list-group` of label/value pairs. Optional fields (Contact Person/Email/
Phone, Estimated Cost, Tender Document Cost, Opening Time, etc.) are
conditionally rendered per-tender depending on what the procuring office
filled in -- confirmed by a commented-out "Estimated Cost" block on a tender
where that field was left blank. This actor parses every section generically
(slugifying each visible label into a camelCase key, the same convention
established by `nepal-tenders-scraper`/`ghana-tenders-scraper`) rather than
hardcoding a fixed field list, so upstream additions/renames on a
per-tender-type basis flow through automatically instead of being silently
dropped.

## Invoice page (bonus, not scraped by default)

`GET /public/tenders/invoice/<tenderNo>` is a printable PPRA publication-fee
invoice (bank details, procuring-agency address, and a `Total Amount (PKR)`
line -- e.g. `15,000` observed for one real tender). This is a genuinely
different, minor data point (the fee PPRA itself charges to publish, not a
tender/bid financial figure) -- this actor surfaces `invoiceUrl` as a link on
every record rather than fetching it by default, keeping one request per
tender for `mode=detail` instead of two.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://epms.ppra.gov.pk"
ACTIVE_TENDERS_URL = f"{BASE_URL}/public/tenders/active-tenders"
TENDERS_HISTORY_URL = f"{BASE_URL}/public/tenders/tenders-history"
DETAIL_URL = f"{BASE_URL}/public/tenders/tender-details"
INVOICE_URL = f"{BASE_URL}/public/tenders/invoice"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 45
PAGE_SIZE = 50

LISTING_HEADERS = [
    "Sr",
    "Tender No",
    "Tender Details",
    "Organization Details",
    "Status",
    "Advertised",
    "Closing",
    "Actions",
]

# procurement_category query param, from #filterForm's own <select>.
PROCUREMENT_CATEGORY_MAP = {
    "all": "",
    "goods": "1",
    "works": "2",
    "consultancyServices": "3",
    "nonConsultancyServices": "4",
}

# tender_type query param.
TENDER_TYPE_MAP = {
    "all": "",
    "tenderNotice": "1",
    "prequalificationNotice": "2",
    "requestForProposal": "3",
    "expressionOfInterest": "4",
}

# tender_nature query param.
TENDER_NATURE_MAP = {
    "all": "",
    "local": "0",
    "international": "1",
}

# status query param.
STATUS_MAP = {
    "all": "",
    "published": "1",
    "cancelled": "2",
}

# sector query param, from #filterForm's own <select> (ids 26/27/31 do not
# exist in the live markup -- not a typo, just gaps in PPRA's own numbering).
SECTOR_MAP = {
    "all": "",
    "ammunition": "1",
    "appliances": "2",
    "booksJournalsManualsTechnicalLiterature": "3",
    "chemicalItems": "4",
    "civilGoods": "5",
    "civilWorks": "6",
    "clothingUniform": "7",
    "consumableItems": "8",
    "electricalItems": "9",
    "equipments": "10",
    "foodItems": "11",
    "furnitureFixture": "12",
    "healthMedicines": "13",
    "infoAndCommTech": "14",
    "leasing": "15",
    "petroleumOilLubricants": "16",
    "mechanicalMachinery": "17",
    "mining": "18",
    "miscellaneous": "19",
    "printing": "20",
    "repairMaintenance": "21",
    "researchDevelopment": "22",
    "services": "23",
    "stationery": "24",
    "vehicles": "25",
    "agriculturalProducts": "28",
    "petroleumProducts": "29",
    "coalSubBituminous": "30",
    "lngLpg": "32",
}
