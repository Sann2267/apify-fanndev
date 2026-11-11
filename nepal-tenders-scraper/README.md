# Nepal Government Tenders Scraper (PPMO e-GP / Bolpatra)

Scrapes Nepal's official national e-Government Procurement (e-GP) portal, `bolpatra.gov.np`, operated by the Public Procurement Monitoring Office (PPMO). No account or login needed.

## Why use this actor

- Pulls from Nepal's real, official e-GP platform — not a third-party tender-alert aggregator
- Get the latest published tenders with zero filters, or search by keyword, procurement category, procurement method, or government entity
- Full tender detail on demand — bid schedule, bid fee, procuring-entity contact person, and downloadable bid documents
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse the listing (`mode: "list"`), or fetch full detail for specific tenders you already know (`mode: "detail"`).
2. For listings, leave every filter blank for the 30 most-recently-published tenders, or set a keyword / category / method / entity name to search.
3. Every listing row includes the tender's own ID, so you can follow up with `mode: "detail"` for the full picture (bid schedule, fee, contact person, document downloads).
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage sessions or retries — the actor handles all of it.

## Input

**Latest published tenders (default):**
```json
{
  "mode": "list",
  "maxResults": 30,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Search by keyword, category, and entity:**
```json
{
  "mode": "list",
  "keyword": "road",
  "procurementCategory": "works",
  "publicEntityName": "Kathmandu Metropolitan",
  "maxResults": 20
}
```

**Fetch full detail for specific tenders:**
```json
{
  "mode": "detail",
  "tenderIds": ["324758", "325065"],
  "maxConcurrency": 4
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — browse/search the listing. `"detail"` — fetch full detail for specific tender IDs. |
| `keyword` | string | `mode: "list"` only. Free-text project-title keyword. |
| `procurementCategory` | string | `mode: "list"` only. `all` (default), `goods`, `works`, `consultancy`, `otherServices`. |
| `procurementMethod` | string | `mode: "list"` only. `all` (default), `ncb`, `icb`, `sealedQuotation`, `directPurchase`, `qcbs`, `qbs`, `fbs`, `commodityPurchase`, `ration`, `userCommittee`, `forceAccount`, `leastCostSelection`. |
| `publicEntityName` | string | `mode: "list"` only. Government office/entity name (or partial name) — resolved automatically to bolpatra's internal ID. |
| `maxResults` | integer | `mode: "list"` only. Max rows kept from the query. Default/max 30 — see Notes below on why this is a hard cap. |
| `tenderId` | string | `mode: "detail"` only. A single tender's numeric ID or full detail URL. |
| `tenderIds` | array | `mode: "detail"` only. Multiple tender IDs or URLs to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many tenders to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "list", "maxResults": 1}` (latest, no filters):

```json
{
  "_input": "latest",
  "_source": "S1-listing",
  "_scrapedAt": "2026-08-27T04:12:33Z",
  "recordType": "TENDER_LIST",
  "_totalAvailable": 207222,
  "_totalReturned": 10,
  "tenderId": "324758",
  "tenderUrl": "https://bolpatra.gov.np/egp/getTenderDetails?tenderId=324758",
  "ifbNo": "TMO/NCB/IR/01/2083/084",
  "projectTitle": "Collection of Scrap Tax on Scrap Materials generated and exported from the Tikapur Municipality Area(Tikapur Nagarpalika Chhetra bata nikashi hune kawadi samanma kawadi kar sankalan garne sambandhi Thekkha)",
  "publicEntityName": "Tikapur Municipality, Kailali",
  "procurementType": "Goods NCB",
  "status": null,
  "noticePublishedDate": "26-08-2026 00:00",
  "lastDateOfBidSubmission": "25-09-2026 12:00",
  "daysLeft": "29 days"
}
```

Real output for `{"mode": "list", "publicEntityName": "Kathmandu Metropolitan", "procurementCategory": "works", "maxResults": 1}` — note `daysLeft` reads `"Expired"` for a real closed tender rather than a number, passed through exactly as bolpatra shows it:

```json
{
  "_input": "search:title='',category=works,method=all,entity='Kathmandu Metropolitan'",
  "_source": "S1-listing",
  "_scrapedAt": "2026-08-27T04:14:21Z",
  "recordType": "TENDER_LIST",
  "_totalAvailable": 3,
  "_totalReturned": 3,
  "tenderId": "163659",
  "tenderUrl": "https://bolpatra.gov.np/egp/getTenderDetails?tenderId=163659",
  "ifbNo": "NCB/CLPP/CW/01/080_081",
  "projectTitle": "Construction of Administrative Building at Chamati Project B Block KMC 16",
  "publicEntityName": "Chamati Land Pooling Project, Kathmandu Metropolitancity",
  "procurementType": "Works NCB",
  "status": null,
  "noticePublishedDate": "08-08-2023 00:00",
  "lastDateOfBidSubmission": "07-09-2023 12:00",
  "daysLeft": "Expired"
}
```

Real output for `{"mode": "detail", "tenderId": "324758"}` — full tender detail:

```json
{
  "_input": "324758",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-27T04:15:13Z",
  "recordType": "TENDER_DETAIL",
  "tenderId": "324758",
  "tenderUrl": "https://bolpatra.gov.np/egp/getTenderDetails?tenderId=324758",
  "publicEntityName": "Tikapur Municipality, Kailali",
  "procurementCategory": "Goods",
  "procurementMethod": "NCB",
  "ifbRfpEoiPqNo": "TMO/NCB/IR/01/2083/084",
  "projectName": "Collection of Scrap Tax on Scrap Materials generated and exported from the Tikapur Municipality Area(Tikapur Nagarpalika Chhetra bata nikashi hune kawadi samanma kawadi kar sankalan garne sambandhi Thekkha)",
  "currentStatus": "Bid Published",
  "sourceOfFunds": "Government Budget",
  "noticePublicationDate": "26-08-2026 00:00",
  "briefDescriptionOfWork": "Collection of Scrap Tax on Scrap Materials generated and exported from the Tikapur Municipality Area(Tikapur Nagarpalika Chhetra bata nikashi hune kawadi samanma kawadi kar sankalan garne sambandhi Thekkha)",
  "biddingProcedure": "Pre Qualification Not Needed",
  "biddingDocumentOf": "GoN uploadable",
  "biddingType": "Open",
  "bidDocumentPublicationDate": "26-08-2026 00:00",
  "dateOfPreBidMeeting": "14-09-2026 13:00",
  "preBidMeetingAddress": "Tikapur Municipality, Kailali Tikapur Kailali Sudoor Pachism Province Nepal",
  "lastDateForBidSubmission": "25-09-2026 12:00",
  "bidOpeningDate": "25-09-2026 14:00",
  "bidOpeningAddress": "Tikapur Municipality, Kailali Tikapur Kailali Sudoor Pachism Province Nepal",
  "dateOfStartOfWorks": "06-10-2026",
  "bidDocumentFeeInNpr": "3000.00",
  "bankName": "Nepal Bank Ltd.",
  "nameOfOfficialInvitingBid": "Suman Dhital",
  "designationOfTheOfficialInvitingBid": "Authorised contact person",
  "addressOfTheOfficialInvitingBid": "Tikapur Kailali Sudoor Pachism Province",
  "contactOfTheOfficialInvitingBid": "9858434111",
  "bidDocument": [
    {
      "documentType": "Bid Document",
      "date": "25-08-2026 00:00",
      "downloadUrl": "https://bolpatra.gov.np/egp/download?alfId=cm:Bidding_Documentsnull/cm:Y2026/cm:M7@@@@@58e92a05-8f6f-44f2-8e7b-9bd660c36e0e&docId=90937315"
    }
  ],
  "addendum": [],
  "bidQueryResponse": [],
  "loi": []
}
```

A tender ID that doesn't exist produces one error record instead:

```json
{
  "_input": "999999999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T04:14:32Z",
  "_error": "not_found"
}
```

| Field | Description |
|---|---|
| `_input` | What produced this record — `"latest"` or a `"search:..."` summary for listing rows, or the tender ID/URL for detail records. |
| `_source` | `S1-listing` or `S1-detail`, or `"none"` on error. |
| `_scrapedAt` | UTC timestamp. |
| `_error` | Present only on failed/not-found records. |
| `recordType` | `TENDER_LIST` or `TENDER_DETAIL`. |
| `_totalAvailable` / `_totalReturned` | Listing only — bolpatra's total match count for your filters, and how many rows it actually returned for this one query (see Notes). |
| `tenderId` / `tenderUrl` | The tender's ID and link — feed `tenderId` into a `mode: "detail"` run for the full picture. |
| `ifbNo` / `projectTitle` / `publicEntityName` / `procurementType` | Core tender identity (listing mode). |
| `noticePublishedDate` / `lastDateOfBidSubmission` / `daysLeft` | Timing (listing mode) — `daysLeft` can read `"Expired"`. |
| *(detail mode)* | Every field bolpatra itself shows for that tender's basic info, bid schedule, fee, and contact sections, plus `bidDocument` / `addendum` / `bidQueryResponse` / `loi` document-download lists — passed through using bolpatra's own labels. |

## Notes

- **A single query returns one page, not the full match count.** bolpatra.gov.np does not support reliable page-by-page pagination via plain HTTP requests, and its own row count per query is inconsistent (10 or 30 rows depending on server-side behavior this actor cannot control) — see `CRAWLING_METHOD.md` for the full investigation. `maxResults` (max 30) only trims that one page further; if you need a specific subset of the 200,000+ historical notices, narrow your `keyword` / `procurementCategory` / `procurementMethod` / `publicEntityName` filters instead of raising `maxResults`.
- `publicEntityName` is resolved via bolpatra's own autocomplete and uses the first suggestion — if your text doesn't match anything, the search runs without that filter (check the run log for a warning).
- Dates are Gregorian `dd-mm-yyyy HH:MM` exactly as bolpatra displays them.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the real bolpatra platform was confirmed against PPMO's own site and a TLS certificate-chain gotcha found during recon.
