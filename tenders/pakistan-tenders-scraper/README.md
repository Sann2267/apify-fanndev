# Pakistan Government Tenders Scraper (PPRA-EPMS)

Scrapes Pakistan's official Public Procurement Regulatory Authority e-Publish & Monitoring System, `epms.ppra.gov.pk`. No account or login needed.

## Why use this actor

- Pulls from Pakistan's real, official e-procurement platform — not a third-party tender-alert aggregator
- Get active tenders or the full closed-tender history, with zero filters or a targeted search (keyword, tender number, category, sector, type, nature, status, date range)
- Full tender detail on demand — procuring office contact, financial terms (bid security, bid validity), and workflow
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse the listing (`mode: "list"`), or fetch full detail for specific tenders you already know (`mode: "detail"`).
2. For listings, leave every filter blank for the latest active tenders, or set a keyword/category/sector/type/nature/status/date filter to search. Switch `listingType` to `"history"` to include closed tenders.
3. Every listing row includes the tender's own number, so you can follow up with `mode: "detail"` for the full picture (contact person, financial terms, workflow).
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

Pagination is handled for you — this actor pages forward automatically (50 rows/page) until your `maxResults` cap or the last page, whichever comes first.

## Input

**Latest active tenders (default):**
```json
{
  "mode": "list",
  "listingType": "active",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Search by keyword and category:**
```json
{
  "mode": "list",
  "keyword": "road",
  "procurementCategory": "works",
  "maxResults": 100
}
```

**Fetch full detail for specific tenders:**
```json
{
  "mode": "detail",
  "tenderNos": ["TS0000012236E", "TS0000011394E"],
  "maxConcurrency": 4
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — browse/search the listing. `"detail"` — fetch full detail for specific tender numbers. |
| `listingType` | string | `mode: "list"` only. `"active"` (default) — currently open tenders. `"history"` — includes closed tenders too. |
| `keyword` | string | `mode: "list"` only. Free-text, matched against title/description/tender number. |
| `tenderNoFilter` | string | `mode: "list"` only. Restrict search to one specific PPRA tender number. |
| `procurementCategory` | string | `mode: "list"` only. `all` (default), `goods`, `works`, `consultancyServices`, `nonConsultancyServices`. |
| `tenderType` | string | `mode: "list"` only. `all` (default), `tenderNotice`, `prequalificationNotice`, `requestForProposal`, `expressionOfInterest`. |
| `sector` | string | `mode: "list"` only. `all` (default) or one of 29 fixed sectors (see input schema for the full list). |
| `tenderNature` | string | `mode: "list"` only. `all` (default), `local`, `international`. |
| `status` | string | `mode: "list"` only. `all` (default), `published`, `cancelled`. |
| `organizationId` / `countryId` | string | `mode: "list"` only, advanced. PPRA's own internal numeric IDs (500+ organizations, not enumerable here) — leave blank unless you already have one. |
| `advertiseDateFrom` / `advertiseDateTo` / `closingDate` | string | `mode: "list"` only. `YYYY-MM-DD` date filters. |
| `startPage` | integer | `mode: "list"` only. Which page to start from (50 rows/page). Default 1. |
| `maxResults` | integer | `mode: "list"` only. Max rows collected across pages. Default 50, max 2000. |
| `tenderNo` | string | `mode: "detail"` only. A single tender's number or full detail URL. |
| `tenderNos` | array | `mode: "detail"` only. Multiple tender numbers or URLs to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many tenders to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default, though this target has no anti-bot gate. |

## Output

Real output for `{"mode": "list", "maxResults": 1}` (latest active tender):

```json
{
  "_input": "latest",
  "_source": "S1-listing",
  "_scrapedAt": "2026-08-27T06:27:34Z",
  "recordType": "TENDER_LIST",
  "listingType": "active",
  "page": 1,
  "tenderNo": "TS0000012236E",
  "title": "OUTSOURCING SERVICES OF OFFICE BOYS, PLUMBER , GARDENER,ELECTRICIAN AND JANITORIAL STAFF FOR NAB (BALOCHISTAN)",
  "description": null,
  "tags": ["Services", "NAB (B)/Hiring / Outsouring the office Boys etc /2026-27he serivices of"],
  "organizationName": "National Accountability Bureau (NAB)",
  "officeName": "National Accountability Bureau (NAB) Quetta",
  "location": "Quetta - Pakistan",
  "status": ["Published"],
  "advertisedDate": "Aug 27, 2026",
  "closingDate": "Sep 14, 2026",
  "closingTime": "11:00 AM",
  "detailUrl": "https://epms.ppra.gov.pk/public/tenders/tender-details/TS0000012236E",
  "invoiceUrl": "https://epms.ppra.gov.pk/public/tenders/invoice/TS0000012236E"
}
```

Real output for `{"mode": "detail", "tenderNo": "TS0000012236E"}` — full tender detail:

```json
{
  "_input": "TS0000012236E",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-27T06:34:17Z",
  "recordType": "TENDER_DETAIL",
  "tenderNo": "TS0000012236E",
  "detailUrl": "https://epms.ppra.gov.pk/public/tenders/tender-details/TS0000012236E",
  "invoiceUrl": "https://epms.ppra.gov.pk/public/tenders/invoice/TS0000012236E",
  "title": "OUTSOURCING SERVICES OF OFFICE BOYS, PLUMBER , GARDENER,ELECTRICIAN AND JANITORIAL STAFF FOR NAB (BALOCHISTAN)",
  "organizationName": "National Accountability Bureau (NAB)",
  "officeName": "National Accountability Bureau (NAB) Quetta",
  "officeAddress": "NAB Office, Shahrah-e-Gulistan, Quetta Cantt.",
  "city": "Quetta",
  "contactPerson": "Asif Mahmood Raja",
  "contactEmail": "asifmahmoodraja@gmail.com",
  "contactPhone": "+92-819-203466",
  "tenderType": "Request for Proposal (RFP)",
  "tenderNoReferenceNoTenderInquiryNo": "NAB (B)/Hiring / Outsouring the office Boys etc /2026-27he serivices of",
  "procurementCategory": "Non-consultancy Services",
  "procurementProcedure": "Single Stage-Two Envelope",
  "sector": "Services",
  "tenderNature": "Local",
  "advertisementDate": "August 27, 2026",
  "closingDateAndTime": "September 14, 2026 at 11:00 AM",
  "openingTime": "11:30 AM",
  "bidSecurity": "216,000.00",
  "bidValidity": "90 days",
  "method": "Competitive Bidding",
  "workflowType": "Standard Evaluation Process"
}
```

An unknown tender number produces one error record instead:

```json
{
  "_input": "TS9999999999X",
  "_source": "none",
  "_scrapedAt": "2026-08-27T06:34:37Z",
  "_error": "not_found"
}
```

| Field | Description |
|---|---|
| `_input` | What produced this record — `"latest"` or a `"search:..."` summary for listing rows, or the tender number/URL for detail records. |
| `_source` | `S1-listing` or `S1-detail`, or `"none"` on error. |
| `_scrapedAt` | UTC timestamp. |
| `_error` | Present only on failed/not-found records. |
| `recordType` | `TENDER_LIST` or `TENDER_DETAIL`. |
| `listingType` / `page` | Listing only — which listing (`active`/`history`) and page this row came from. |
| `tenderNo` / `detailUrl` / `invoiceUrl` | The tender's PPRA number and links — feed `tenderNo` into a `mode: "detail"` run for the full picture. `invoiceUrl` is PPRA's own publication-fee invoice, not fetched by this actor. |
| `title` / `organizationName` / `officeName` | Core tender identity. |
| `status` / `advertisedDate` / `closingDate` / `closingTime` | Timing (listing mode). |
| *(detail mode)* | Every field PPRA itself shows for that tender's organization/contact, tender info, dates, financial terms, and workflow sections — passed through using PPRA's own labels. Some fields (contact person/email/phone, estimated cost, opening time) only appear when the procuring office filled them in. |

## Notes

- `epms.ppra.gov.pk` is a completely separate, working application from PPRA's main informational site (`ppra.gov.pk`), which was returning a server error during recon — see `CRAWLING_METHOD.md`.
- `organizationId`/`countryId` filters accept PPRA's raw internal numeric IDs (there are 500+ organizations) — not enumerable in this actor's input schema. Use `keyword` or `procurementCategory`/`sector` instead unless you already have a specific ID.
- Dates are shown exactly as PPRA displays them (e.g. `Aug 27, 2026` on listings, `August 27, 2026` on detail pages) — passed through unconverted.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the real EPMS platform was found and confirmed, and PPRA's own pagination/not-found behavior.
