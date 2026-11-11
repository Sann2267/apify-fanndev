# Ghana Government Tenders Scraper (GHANEPS)

Scrapes Ghana's official government tenders and procurement notices from GHANEPS, the Ghana Electronic Procurement System used by 869+ public entities. No account or login needed.

## Why use this actor

- Pulls from Ghana's real, official procurement platform — not a third-party tender-alert aggregator
- Three views in one actor: **currently open tenders**, **tenders under evaluation/awarding**, and **awarded contracts** (with supplier name and contract amount)
- Full tender detail on demand — procurement type, deadlines, bid security requirements, lots, UNSPSC classification codes, and more
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse a listing (`mode: "list"`), or fetch full detail for specific tenders you already know (`mode: "detail"`).
2. For listings, choose which one: tenders still open for bidding, tenders in evaluation, or already-awarded contracts.
3. The actor fetches and paginates through the results automatically, up to the limit you set.
4. Every tender's page includes its own ID and link, so you can follow up with `mode: "detail"` for the full picture.
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
  "resourceIds": ["3463468", "3448475"],
  "maxConcurrency": 3
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — browse a listing page. `"detail"` — fetch full detail for specific tender IDs. |
| `listType` | string | `mode: "list"` only. `"current"` (default) — open for bidding (~65 at a time). `"opened"` — bids closed, in evaluation/awarding (12,000+). `"awarded"` — finished contracts with supplier and amount (15,000+). |
| `maxResults` | integer | `mode: "list"` only. Max rows to return, across as many pages as needed. Default 50, max 5000. `opened` and `awarded` are very large lists — raise this only as high as you need. |
| `resourceId` | string | `mode: "detail"` only. A single tender's numeric ID or full tender URL. |
| `resourceIds` | array | `mode: "detail"` only. Multiple tender IDs or URLs to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many tenders to fetch in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "list", "listType": "current", "maxResults": 2}`:

```json
{
  "_input": "list:current",
  "_source": "S1-current-listing",
  "_scrapedAt": "2026-08-27T03:57:05Z",
  "recordType": "TENDER_CURRENT",
  "_page": 1,
  "_totalAvailable": 65,
  "resourceId": "3463468",
  "tenderUrl": "/epps/cft/prepareViewCfTWS.do?resourceId=3463468",
  "title": "Procure 1000 No. Mono desks and tables for schools within the kumasi metro",
  "procuringEntity": "KUMASI METROPOLITAN ASSEMBLY",
  "description": "Procure 1000 No. Mono desks and tables for schools within the kumasi metro",
  "bidsSubmissionDeadline": "10/09/2026 10:00:00",
  "procedure": "National Competitive Tendering",
  "status": "Bid Submission",
  "noticePdfUrl": "/epps/cft/downloadNoticeForAdvSearch.do?resourceId=3463468",
  "publicationDate": "26/08/2026 17:45:56"
}
```

Real output for `{"mode": "list", "listType": "awarded", "maxResults": 1}` — note contract amounts are only disclosed for some awards (`"N/A"` otherwise, passed through exactly as GHANEPS shows it):

```json
{
  "_input": "list:awarded",
  "_source": "S1-awarded-listing",
  "_scrapedAt": "2026-08-27T03:58:05Z",
  "recordType": "TENDER_AWARDED",
  "resourceId": "3431820",
  "title": "Procurement of Food items for the Ga Community during Homowo festivities",
  "procuringEntity": "GA NORTH MUNICIPAL ASSEMBLY",
  "supplierName": "OBUOBA PRESTIGE VENTURES",
  "awardDate": "2026/08/26 12:42:55",
  "awardAmount": "160920.00 (GHS)",
  "lotName": "Drinks and beverages, Food items",
  "noticePdfUrl": "/epps/cft/downloadNotice.do?resourceId=3431820&lang=en&documentId=3459698&noticeType=430"
}
```

Real output for `{"mode": "detail", "resourceId": "3463468"}` — full tender detail (truncated, this tender has 25 fields in total):

```json
{
  "_input": "3463468",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-27T03:57:27Z",
  "recordType": "TENDER_DETAIL",
  "resourceId": "3463468",
  "tenderUrl": "https://www.ghaneps.gov.gh/epps/cft/prepareViewCfTWS.do?resourceId=3463468",
  "nameOfProcuringEntity": "KUMASI METROPOLITAN ASSEMBLY",
  "appReferenceNumber": "AR/KMA/GDs/NCT/DACF/003/A/2026",
  "tenderTitle": "Procure 1000 No. Mono desks and tables for schools within the kumasi metro",
  "procurementType": "Goods",
  "procurementMethod": "National Competitive Tendering",
  "tenderParticipationFees": "Participation Fee Required",
  "paymentAmountGhs": "500",
  "bidSecurityType": "Bid Security Required",
  "bidSubmissionDeadlineDate": "10/09/2026 10:00:00",
  "bidOpeningDate": "10/09/2026 10:30:00",
  "dateOfPublicationInvitation": "26/08/2026 17:45:56"
  // ... 13 more fields
}
```

A tender ID that doesn't exist (or isn't publicly viewable) produces one error record instead:

```json
{
  "_input": "9999999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T03:57:28Z",
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
| `supplierName` / `awardAmount` / `lotName` | Winning bidder and contract value (`awarded` listing only). |
| *(detail mode)* | Every field GHANEPS itself shows for that tender — the exact set varies by procurement type (a simple quotation has ~20 fields, a multi-lot tender with bid security can have 25+), always passed through using GHANEPS's own labels. |

## Notes

- `opened` and `awarded` listings are large (12,000+ and 15,000+ entries) — start with a small `maxResults` to preview before scraping in bulk.
- Contract award amounts are only published for some awards; GHANEPS itself shows `"N/A"` for the rest, and this actor passes that through unchanged rather than guessing a value.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the real GHANEPS platform was confirmed against Ghana's Public Procurement Authority's own site.
