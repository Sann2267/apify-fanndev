# Crawling Method — UMUCYO (Rwanda Public Procurement Authority e-GP)

**Last verified:** 2026-08-27

## Finding the right portal

Rwanda's tender/procurement transparency portal is separate from its
business registry:

| Domain | What it is | Public without login? |
|---|---|---|
| `urs.rdb.rw` | Rwanda Development Board business registry -- covered (and skipped) in an earlier portfolio round. | No -- search API hard 401-gated, no anonymous access. |
| `www.rppa.gov.rw` | RPPA's own marketing/policy site (law text, guidelines, annual reports). | N/A -- no notice data here. |
| `www.umucyo.gov.rw` | **UMUCYO** ("transparency" in Kinyarwanda) -- Rwanda's sole official e-Government Procurement system, managed by RPPA under the Ministry of Finance and Economic Planning. **Correct target.** | **Yes -- confirmed independently, see below.** |

`umucyo.gov.rw` (bare, no `www`) 301-redirects/resolves to the same host and
serves identical content.

## robots.txt

```
HTTP 404 on both https://umucyo.gov.rw/robots.txt and
https://www.umucyo.gov.rw/robots.txt
```

There is no robots.txt file on this host at all -- not a blanket block, not
an AI-bot exclusion, nothing. Nothing to honor because nothing exists.

## No anti-bot gate found

Every endpoint this actor touches returned `HTTP 200` with real content on a
**plain, default-TLS `curl` request with no impersonation and no special
headers.** Response headers show plain `Apache/2.4.62 (Unix)
OpenSSL/3.1.7`, no Cloudflare/Akamai/DataDome/WAF markers of any kind.
`curl_cffi` (`chrome124` profile) is used here for portfolio consistency and
because a residential proxy in front of it still negotiates its own TLS
fingerprint, but it is not load-bearing for this target -- confirmed working
identically via plain `curl` and via `curl_cffi.requests.get(...,
impersonate="chrome124")`.

## No login wall for viewing -- verified independently, not assumed

This was the key risk given the RDB business-registry precedent (same
country, hard-gated search API). Verified directly and repeatedly instead
of assuming the same outcome:

- The "List of advertising (all)" listing returned **38,880 real tender
  records** (page 1/3888 at 10/page, or 1/778 at 50/page) on a completely
  fresh, unauthenticated session -- no login prompt, no redirect, no
  truncated/teaser data.
- Individual tender **detail pages** (procuring entity, brief description,
  deadline, fee, security requirements, downloadable-document metadata)
  render in full on a fresh session for both a brand-new 2026-2027 notice
  and a decade-old 2016-2017 one -- confirmed by direct fetch of both.
- A "Login" link exists in the top nav (plus separate "PE Registration" and
  "Supplier Registration" flows), but nothing in this actor's scope
  (browsing the listing, filtering it, or reading a tender's full detail)
  ever hit a login redirect or truncated response.
- One partial gap found: filtering the listing by `tendStatCd=SIG` ("Signed
  Contract") returns "No Data" -- this endpoint appears to only carry
  pre-award tender notices; contract-award/evaluation-result data (if
  published at all) lives elsewhere on the platform, not behind a login
  wall on *this* endpoint. Simply out of scope for what this actor covers.

## Platform notes: a fourth (Korean-vendor) e-GP platform in this vertical

The site's own JS carries Korean-language code comments and variable names
verbatim (e.g. `validateTokenKorean`, `화폐구분타입` = "currency separator
type", `공통메세지` = "common messages"). This is a distinct platform
lineage from "European Dynamics"/ePPS (seen on Ghana/Zambia/Jamaica) or
Perago Systems (Sierra Leone/Malawi) -- a fourth vendor fingerprint for
this tender/procurement vertical, worth recognizing if it recurs on other
countries' portals in future sessions.

Backend is classic server-rendered JSP (Java) -- no JSON REST API, no JS
SPA bundle to reverse-engineer (unlike Rwanda's own RDB business registry,
which is a Vue/webpack SPA whose reverse-engineered API endpoint 401s).

## Session handling

A single `JSESSIONID` cookie, set on the first `GET`, is sufficient for
every subsequent listing-pagination and detail-fetch `POST` within that
session -- confirmed with a completely fresh cookie jar. The site's own
HTML embeds the classic Java-EE `;jsessionid=<id>` URL-rewriting suffix in
its `<form action="...;jsessionid=...">` markup (a fallback for clients
with cookies disabled), but this is **not required**: the same requests
succeed with a plain cookie-bearing session and no jsessionid segment in
any URL at all. This actor relies purely on the cookie (one
`curl_cffi.AsyncSession` per run), which is simpler and avoids
re-parsing/tracking a session id string.

## Listing endpoint

```
GET  /eb/bav/selectListAdvertisingListForGU.do?menuId=EB01020100   (primes session, returns page 1)
POST /eb/bav/selectListAdvertisingListForGU.do?menuId=EB01020100
     Content-Type: application/x-www-form-urlencoded
     Body: currentPageNo=<n>&recordCountPerPage=<10|20|30|50>&searchConditions=
           &tendTypeCd=&tendMthodCd=&tendStatCd=&simpldYn=&peCd=&peCdNm=
           &pubcatFromDt=&pubcatToDt=&bidopenDt=&bidopenHr=&bidopenMm=
           &tendReferNo=&tendNm=
```

`recordCountPerPage=50` (the UI's own largest dropdown option) is accepted
and used as this actor's default page size to minimize request count.
Confirmed: unfiltered, results are ordered **newest-advertised-first**
(page 1 showed 2026-08-26/25 notices; the last page, 3888/3888, showed
2016-2017 notices) -- so an unfiltered `mode='list'` run naturally serves
as a "latest tenders" feed without needing a separate endpoint, unlike
portals that split "current" and "archived" into different tabs/APIs.

Each row's selection `<input type="radio" name="tenderNo" value="...">`
carries a pipe-delimited internal value:

```
<tendReferNo>|<title>|<peCode>|<deadlineDateOnly>|<tendStageCd>|<tendMthodCd>|<tendTypeCd>|<bidOpenDateTime>|<statusCode>
```

`tendReferNo` here is the row's **internal** reference (e.g.
`000001/NC/NCB/2026/2027/1207000001`, ending in the procuring entity's
internal numeric code) -- **not** the same string as the human-readable
"Tender No" column shown in the same row (e.g.
`000001/NC/NCB/2026/2027/R-CAMD`, ending in the entity's abbreviation).
Only the internal `tendReferNo` + `tendStageCd` + `tendTypeCd` trio (parsed
from the tail of this pipe-delimited value, robust against a title that
might itself contain a `|`) works to fetch the detail page -- this is
exactly what the page's own `ViewDetail(tendReferNo, tendStageCd,
tendTypeCd)` JS function submits. This actor exposes that trio joined back
together as `detail_ref` (`tendReferNo|tendStageCd|tendTypeCd`) on every
listing record, which is exactly the string `mode='detail'`'s `detailRefs`
input expects back.

## Detail endpoint

```
POST /eb/bav/selectAdvertisingDtlInfo.do?menuId=EB01020100
     Content-Type: application/x-www-form-urlencoded
     Body: tendReferNo=<internal ref>&tendStageCd=<code>&tendTypeCd=<code>&currentPageNo=1&searchConditions=
```

Confirmed working identically for tenders from FY2016-2017 through
FY2026-2027 -- the same endpoint serves any tender regardless of age.
`tendStageCd` values seen during recon: `O`, `F` (undocumented anywhere
on-site; passed through opaquely, never hardcoded to a single value).

## Detail page shape: generic label scan, not a fixed field list

The label set genuinely varies by tender type (Goods/Works/Services/
Consultant) and possibly by stage -- e.g. Services tenders show
"Examination" methodology fields that a Goods tender detail page may not.
Rather than hardcode one fixed schema, `extractor.parse_detail` scans every
`<th>` in the page's main content area (`#contents_R`) and reads its
sibling `<td>`, building a `fields` dict keyed by upstream's own labels
verbatim (`"Tender No"`, `"Procurement Plan Name"`,
`"Advertising/Procuring Entity"`, `"Brief Description"`, `"Deadline for
Bids Submission"`, `"Tender Fee"`, `"Tender Security"`, `"Local
preference"`, `"Margin of Preference"`, etc.) This correctly handles rows
with two `th`/`td` pairs side by side (e.g. "Tender Security" next to
"Tender Security (sum of LOTs)") since BeautifulSoup's
`find_next_sibling("td")` only looks among direct siblings of that specific
`th`.

A separate documents table (`No` / `Document Name` / `Upload Date` / `File`
columns) lists downloadable attachments via
`onClick="javascript:util_fileIdDownload('<fileId>')"` links -- captured as
`attachments[]` metadata (`file_id`, `file_name`, `document_name`,
`upload_date`). Actually downloading the files requires a further
JS-driven POST that was not reverse-engineered (out of scope for this
actor; metadata only).

## Gotcha: older template variants embed key fields as inline text, not a table

A 2016-2017-era "Request for Expressions of Interest" detail page was
found to render its key info (`TITLE:`, `CLIENT:`, `SOURCE OF FUNDS:`) as
plain inline paragraph text rather than in the `th`/`td` fields table used
by 2026-era tenders. Rather than special-case every template variant,
`parse_detail` also captures a whitespace-normalized `raw_text` of the
entire main-content area unconditionally, so nothing is silently lost for
a page shape the generic `th`/`td` scan doesn't fully cover -- consistent
with the "never fail silent" project principle.

## Sample refs used during recon

- `000001/NC/NCB/2026/2027/1207000001|O|NC` -- live 2026-2027 Services
  tender (Rwanda Capital Market Development), full fields + 2 attachments.
- `000001/C/ICB/2016/2017/1800000000|F|C` -- decade-old archived
  Consultant tender (Ministry of Infrastructure), confirmed the same
  detail endpoint still serves it, rendered via the older inline-text
  template.

## Known limits

- Contract-award / bid-evaluation-result data (`tendStatCd=SIG`) is not
  exposed on this listing endpoint ("No Data") -- if RPPA publishes this
  elsewhere on the platform, it was not found during recon and is not
  covered by this actor.
- Downloadable tender-document attachment *contents* are not fetched --
  only their metadata (name, upload date, internal file id). The download
  action is JS-driven (`util_fileIdDownload`) and was not reverse-engineered.
- `tendStageCd` values beyond `O`/`F` may exist and are passed through
  opaquely wherever encountered, never assumed to be a closed enum.

## Diff cadence

Quarterly smoke test recommended. Classic server-rendered JSP portals in
this portfolio tend to be low-churn, but the listing's own default sort
(newest-first) and page-count depend on live data volume, so `maxResults`
pagination logic should be re-verified if the site is redesigned.
