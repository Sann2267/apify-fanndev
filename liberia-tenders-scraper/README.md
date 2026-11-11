# Liberia Government Tenders Scraper (e-GP)

Scrapes Liberia's official electronic Government Procurement (e-GP) platform, run by the Public Procurement and Concessions Commission (PPCC) at `eprocurement.ppcc.gov.lr`. No account or login needed.

## Why use this actor

- Pulls from Liberia's real, official e-GP platform — not a third-party tender-alert aggregator (several commercial ones exist and were deliberately avoided)
- Three views in one actor: **currently open tenders**, **tenders under evaluation/awarding**, and **awarded contracts** (with supplier name and contract amount)
- Full tender detail on demand — procurement type, deadlines, bid security requirements, ISIC classification, procurement estimate, and more (40+ fields)
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse a listing (`mode: "list"`), or fetch full detail for specific tenders you already know (`mode: "detail"`).
2. For listings, choose which one: tenders still open for bidding, tenders in evaluation, or already-awarded contracts.
3. The actor fetches and paginates through the results automatically, up to the limit you set.
4. Every tender's row includes its own ID and link, so you can follow up with `mode: "detail"` for the full picture.
5. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage sessions, pagination, or retries — the actor handles all of it.

## Input

**Browse open tenders (default):**
```json
{
  "mode": "list",
  "listType": "current",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Fetch full detail for specific tenders:**
```json
{
  "mode": "detail",
  "resourceIds": ["250740", "246999"],
  "maxConcurrency": 3
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — browse a listing page. `"detail"` — fetch full detail for specific tender IDs. |
| `listType` | string | `mode: "list"` only. `"current"` (default) — open for bidding (~30 at a time). `"opened"` — bids closed, in evaluation/awarding (960+). `"awarded"` — finished contracts with supplier and amount (350+). |
| `maxResults` | integer | `mode: "list"` only. Max rows to return, across as many pages as needed. Default 50, max 5000. `opened` is a large list — raise this only as high as you need. |
| `resourceId` | string | `mode: "detail"` only. A single tender's numeric ID or full tender URL. |
| `resourceIds` | array | `mode: "detail"` only. Multiple tender IDs or URLs to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many tenders to fetch in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "list", "listType": "current", "maxResults": 1}`:

```json
{
  "_input": "list:current",
  "_source": "S1-current-listing",
  "_scrapedAt": "2026-08-27T06:30:21Z",
  "recordType": "TENDER_CURRENT",
  "_page": 1,
  "_totalAvailable": 29,
  "resourceId": "250740",
  "tenderUrl": "https://eprocurement.ppcc.gov.lr/epps/cft/prepareViewCfTWS.do?resourceId=250740",
  "title": "Vehicle Purchase",
  "procuringEntity": "MINISTRY OF GENDER CHILDREN AND SOCIAL PROTECTION",
  "description": "Vehicle Purchase",
  "bidsSubmissionDeadline": "22/09/2026 13:00:00",
  "procedure": "National Open Competitive Bidding (NOB)",
  "status": "Bid Submission",
  "noticePdfUrl": "https://eprocurement.ppcc.gov.lr/epps/cft/downloadNoticeForAdvSearch.do?resourceId=250740",
  "publicationDate": "26/08/2026 15:58:58"
}
```

Real output for `{"mode": "list", "listType": "awarded", "maxResults": 1}`:

```json
{
  "_input": "list:awarded",
  "_source": "S1-awarded-listing",
  "_scrapedAt": "2026-08-27T06:33:46Z",
  "recordType": "TENDER_AWARDED",
  "_page": 1,
  "_totalAvailable": 352,
  "resourceId": "2933",
  "tenderUrl": "https://eprocurement.ppcc.gov.lr/epps/cft/prepareViewCfTWS.do?resourceId=2933",
  "title": "Acquisition of Rice and Food Items",
  "procuringEntity": "PUBLIC PROCUREMENT AND CONCESSIONS COMMISSION",
  "supplierName": "SAKSOUK SHOPPING CENTER",
  "awardDate": "06/01/2025",
  "awardAmount": "4518.00 (USD)",
  "packageNumberCode": "IFBNO./PPCC/RFQ/004/24",
  "grantOrLoanNumber": null,
  "lotName": "N/A",
  "noticePdfUrl": "https://eprocurement.ppcc.gov.lr/epps/cft/downloadNotice.do?documentId=3961&lang=en&noticeType=813&resourceId=2933"
}
```

Real output for `{"mode": "detail", "resourceId": "250740"}` — full tender detail (truncated, this tender has 41 fields in total):

```json
{
  "_input": "250740",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-27T06:34:14Z",
  "recordType": "TENDER_DETAIL",
  "resourceId": "250740",
  "tenderUrl": "https://eprocurement.ppcc.gov.lr/epps/cft/prepareViewCfTWS.do?resourceId=250740",
  "remainingTimeDaysHoursToDeadline": "26/6",
  "nameOfProcuringEntity": "MINISTRY OF GENDER CHILDREN AND SOCIAL PROTECTION",
  "nameOfProcuringEntityUrl": "https://eprocurement.ppcc.gov.lr/epps/prepareViewCAOrganisation.do?id=1752",
  "currentStatus": "Process at bidding stage",
  "processType": "Procurement",
  "annualPlanReference": "1003/1175/10772",
  "resourceIdFromDetailPage": "procurement-250740",
  "title": "Vehicle Purchase",
  "description": "Vehicle Purchase",
  "packageNumberCode": "IFBNO#MGCSP/GOL/PSIP/NCB/CD/001/2026",
  "procurementType": "Non Consultancy Services",
  "procurementMethod": "National Open Competitive Bidding (NOB)",
  "bidSecurityBidSecuringDeclarationRequired": "Bid Security Required",
  "bidSecurityAmount": "1,300",
  "bidSecurityCurrency": "USD",
  "isicCodes": "G451-Sale of motor vehicles",
  "procurementEstimateAmount": "26,000",
  "bidSubmissionDeadlineDate": "22/09/2026 13:00:00",
  "bidOpeningDate": "22/09/2026 13:30:00"
  // ... 22 more fields
}
```

A tender ID that doesn't exist (or isn't publicly viewable) produces one error record instead:

```json
{
  "_input": "999999999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T06:34:44Z",
  "_error": "not_found_or_restricted",
  "_errorDetail": ""
}
```

| Field | Description |
|---|---|
| `_input` | What produced this record — `"list:<listType>"` for listing rows, or the tender ID/URL for detail records. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on failed/inaccessible records. |
| `recordType` | `TENDER_CURRENT`, `TENDER_OPENED`, `TENDER_AWARDED`, or `TENDER_DETAIL`. |
| `resourceId` / `tenderUrl` | The tender's ID and link — feed `resourceId` into a `mode: "detail"` run for the full picture. |
| `title` / `procuringEntity` | Tender name and the government body running it. |
| `bidsSubmissionDeadline` / `status` | Where the tender stands (listing modes). |
| `supplierName` / `awardAmount` / `lotName` / `packageNumberCode` | Winning bidder, contract value, lot/region, and reference number (`awarded` listing only). |
| *(detail mode)* | Every field the platform itself shows for that tender — the exact set varies by procurement type, always passed through using the platform's own labels. |

## Notes

- On the `current` listing, the column literally labelled "Process No" upstream actually holds the tender title (not a reference/process number) — this is a mislabeled header on the platform's own side, verified against the raw HTML. This actor exposes it as `title`, matching what it actually contains, rather than reproducing the misleading label.
- `opened` is a large list (960+ entries) — start with a small `maxResults` to preview before scraping in bulk.
- Unlike some sibling e-GP platforms (e.g. Zambia's ZPPA), Liberia's detail pages did **not** show a post-deadline login wall in testing — every `resourceId` pulled from any of the three public listings, including a 17-month-old awarded contract, rendered full detail with no login.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the platform was confirmed as the same "European Dynamics"/ePPS vendor family already used for Ghana, Zambia, and Jamaica.
