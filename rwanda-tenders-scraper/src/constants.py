"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Rwanda's public tender/procurement transparency
portal is UMUCYO ("transparency" in Kinyarwanda), Rwanda's sole official
e-Government Procurement system at `https://www.umucyo.gov.rw`, run by the
Rwanda Public Procurement Authority (RPPA, under the Ministry of Finance and
Economic Planning). This is a **different** agency/system from
`urs.rdb.rw` (Rwanda Development Board's business registry, correctly
skipped in an earlier portfolio round -- its search API is hard 401-gated
with no anonymous access at all). Tender notices here are genuinely public:
confirmed listing AND detail pages both return full real data with zero
authentication, including notices back to the 2016-2017 financial year.

## robots.txt

```
HTTP 404 on both https://umucyo.gov.rw/robots.txt and
https://www.umucyo.gov.rw/robots.txt -- no robots.txt file exists at all.
```

No blanket block, no bot names, nothing to honor or violate -- there is
simply no robots.txt on this host.

## No WAF / no TLS-fingerprint gate at all

Every endpoint used by this actor returns HTTP 200 with real content on a
plain, default-TLS `curl` request -- no impersonation, no special headers,
no cookies pre-seeded. Response headers show plain `Apache/2.4.62 (Unix)
OpenSSL/3.1.7`, no Cloudflare/Akamai/DataDome/WAF markers of any kind.
`curl_cffi` (`chrome124` profile) is still used here for portfolio
consistency and graceful behavior behind a residential proxy, but it is not
load-bearing for this specific target.

## No login wall for viewing

Confirmed directly and repeatedly: the "List of advertising (all)" listing
(38,880+ real tender records at recon time, back to FY2016-2017) and the
per-tender detail page both render full real content -- title, procuring
entity, dates, fee, security requirements, brief description, downloadable
document links -- with **no auth check whatsoever**, tested on both a
freshly-published 2026-2027 notice and a decade-old 2016-2017 one. A
"Login" link exists in the top nav (and separate "PE Registration" /
"Supplier Registration" flows), but these gate only bid *submission* and
supplier/PE account management -- never confirmed to gate viewing anywhere
in this actor's scope. Note: querying the listing with `tendStatCd=SIG`
("Signed Contract") returned "No Data" -- contract-award/evaluation-result
data appears to live in a separate (not publicly exposed in this nav)
section of the platform, not a login wall on this endpoint; simply out of
scope for what this actor covers (open/advertised tender notices).

## Platform notes

The site's own JS carries Korean-language code comments and variable names
(e.g. `validateTokenKorean`, `화폐구분타입`) -- this looks like a Korean
e-GP platform vendor (distinct from the "European Dynamics"/ePPS platform
seen on Ghana/Zambia/Jamaica, or Perago Systems on Sierra Leone/Malawi).
Backend is classic server-rendered JSP (Java), not a JSON REST API and not
a JS SPA -- no bundle to reverse-engineer, unlike Rwanda's own business
registry (RDB). Session is tracked via a plain `JSESSIONID` cookie;
confirmed the classic `;jsessionid=<id>` URL-rewriting suffix seen embedded
in the page's own `<form action="...;jsessionid=...">` markup is NOT
required -- a single `curl_cffi.AsyncSession` carrying just the cookie
across requests is sufficient for both listing pagination and detail
fetches (verified with a completely fresh cookie jar, no jsessionid in any
URL).

## Site structure

`GET /eb/bav/selectListAdvertisingListForGU.do?menuId=EB01020100` --
"List of advertising (all)", the public tender-notice listing. A first GET
here (with no POST body) establishes the session (`JSESSIONID` cookie) and
returns page 1 with default filters. Pagination and filtering are then
driven by POSTing the same URL with a small filter form + `currentPageNo`
+ `recordCountPerPage` (10/20/30/50 -- 50 accepted even though the UI only
exposes it as a dropdown option, not a hard server cap in practice).

Each listing row's selection `<input type="radio" name="tenderNo" value="...">`
carries a pipe-delimited internal value:

    <tendReferNo>|<title>|<peCode>|<deadlineDateOnly>|<tendStageCd>|<tendMthodCd>|<tendTypeCd>|<bidOpenDateTime>|<statusCode>

`tendReferNo` here is the *internal* reference (e.g.
`000001/NC/NCB/2026/2027/1207000001`, ending in the procuring entity's
internal numeric code) -- this differs from the human-readable "Tender No"
shown in the listing table's own column (e.g.
`000001/NC/NCB/2026/2027/R-CAMD`, ending in the entity's abbreviation).
Only the internal `tendReferNo` (plus `tendStageCd` and `tendTypeCd`) can
be used to fetch the detail page -- this is exactly the trio the page's own
`ViewDetail(tendReferNo, tendStageCd, tendTypeCd)` JS function submits.

    POST /eb/bav/selectAdvertisingDtlInfo.do?menuId=EB01020100
    Content-Type: application/x-www-form-urlencoded
    Body: tendReferNo=<internal ref>&tendStageCd=<O|F|...>&tendTypeCd=<G|C|NC|W>&currentPageNo=<n>&searchConditions=

Confirmed working for tenders from FY2016-2017 through FY2026-2027 alike --
the same detail endpoint serves any tender regardless of age or stage code
(`tendStageCd` values seen during recon: `O`, `F` -- not documented
anywhere on-site, passed through opaquely).

## Response shape (listing)

Server-rendered HTML `<table>` inside `#contents_R`, columns (confirmed via
the page's own `<thead>`): Tender Name, Tender No, Status, Advertising
Date, Deadline of Submitting, Planed Open Date [sic -- upstream's own
spelling], Stage Type. Total record count and page count are shown in a
"<n> Results (page <p>/<total>)" footer string, parsed directly rather than
computed, since `recordCountPerPage` affects total page count.

## Response shape (detail)

Server-rendered HTML with generic `<th>`/`<td>` label-value pairs (Tender
No, Procurement Plan Name, Advertising/Procuring Entity, Tender Name,
Brief Description, Deadline for Bids Submission, Opening Date, Opening
Place, How to Obtain Tender Document, Tender Fee, Tender Security, Local
preference, Margin of Preference, and more depending on tender type/stage)
-- extracted generically by scanning every `<th>` for a label and reading
its sibling `<td>`(s), rather than hardcoding a fixed field list, since the
label set genuinely varies by tender type (Goods/Works/Services/Consultant)
and stage. Downloadable attachment links exist
(`util_fileIdDownload('<fileId>')`) but actually downloading the files
requires a further JS-driven POST not reverse-engineered here -- out of
scope for this actor; attachment file names/ids are captured as metadata
only.
"""

BASE_URL = "https://www.umucyo.gov.rw"
TLS_PROFILE = "chrome124"

MENU_ID = "EB01020100"
LIST_PATH = "/eb/bav/selectListAdvertisingListForGU.do"
DETAIL_PATH = "/eb/bav/selectAdvertisingDtlInfo.do"

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

FORM_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": f"{BASE_URL}{LIST_PATH}?menuId={MENU_ID}",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0

# Server-accepted page sizes are 10/20/30/50 per the UI's own dropdown; 50
# used as the default fetch size to minimize request count.
LIST_PAGE_SIZE = 50

# Empty filter template for the listing POST form -- overridden per-field by
# `fetch_list_page`'s `filters` kwarg.
EMPTY_FILTERS = {
    "tendTypeCd": "",
    "tendMthodCd": "",
    "tendStatCd": "",
    "simpldYn": "",
    "peCd": "",
    "peCdNm": "",
    "pubcatFromDt": "",
    "pubcatToDt": "",
    "bidopenDt": "",
    "bidopenHr": "",
    "bidopenMm": "",
    "tendReferNo": "",
    "tendNm": "",
}
