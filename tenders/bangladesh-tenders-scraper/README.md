# Bangladesh Government Tenders Scraper (CPTU/BPPA e-GP)

Scrapes Bangladesh's official national e-Government Procurement (e-GP) portal, `eprocure.gov.bd`, operated by the Central Procurement Technical Unit (CPTU) / Bangladesh Public Procurement Authority (BPPA). No account or login needed.

## Why use this actor

- Pulls from Bangladesh's real, official e-GP platform — not a third-party tender-alert aggregator
- Three modes: live open tenders, awarded contracts (with winning supplier + contract value), and full per-tender detail
- Full tender detail on demand — bid schedule, procurement method, tenderer eligibility criteria, per-lot breakdown, and inviting-official contact
- Awarded-contract rows already include the supplier name and contract value — no extra fetch needed
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse live tenders (`mode: "list"`), browse awarded contracts (`mode: "awarded"`), or fetch full detail for specific tenders you already know (`mode: "detail"`).
2. For `list`/`awarded`, leave `keyword` blank for the latest entries, or set a keyword to search.
3. Every list/awarded row includes the tender's own ID, so you can follow up with `mode: "detail"` for the full picture.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage sessions or retries — the actor handles all of it.

## Input

**Latest live tenders (default):**
```json
{
  "mode": "list",
  "maxResults": 30,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Search live tenders by keyword, or filter by procurement nature:**
```json
{
  "mode": "list",
  "keyword": "hospital",
  "maxResults": 20
}
```

**Latest awarded contracts (with supplier and value):**
```json
{
  "mode": "awarded",
  "maxResults": 20
}
```

**Fetch full detail for specific tenders:**
```json
{
  "mode": "detail",
  "tenderIds": ["1324093", "1318248"],
  "maxConcurrency": 4
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — live/open tenders. `"awarded"` — awarded contracts (Notice of Award). `"detail"` — fetch full detail for specific tender IDs. |
| `keyword` | string | `mode: "list"`/`"awarded"` only. Free-text keyword matched against the title/description. |
| `procurementNature` | string | `mode: "list"` only. `all` (default), `goods`, `works`, `service`, `physicalServices`. **Ignored by the site itself whenever `keyword` is also set** — see Notes below. |
| `maxResults` | integer | `mode: "list"`/`"awarded"` only. Rows to fetch from the first page. Default 30, max 100. |
| `tenderId` | string | `mode: "detail"` only. A single tender's numeric ID or full detail URL. |
| `tenderIds` | array | `mode: "detail"` only. Multiple tender IDs or URLs to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many tenders to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "list", "maxResults": 1}` (latest, no filters):

```json
{
  "_input": "latest",
  "_source": "S1-list",
  "_scrapedAt": "2026-08-27T06:36:45Z",
  "recordType": "TENDER_LIST",
  "_totalPages": 622008,
  "tenderId": "1318248",
  "tenderUrl": "https://www.eprocure.gov.bd/resources/common/ViewTender.jsp?id=1318248&h=t",
  "referenceNo": "27.21.6944.738.02.118.26.440",
  "referenceDate": "16-08-26",
  "status": "Live",
  "procurementNature": "Works",
  "projectTitle": "Construction of Property Line Guide wall at Bonpara Grid Sub-Station under GMD, Power Grid, ishwardi.",
  "procuringEntity": "Ministry of Energy, Power and Mineral Resources / Power Division / Power Grid Bangladesh PLC / Grid Maintenance Division, Ishwardi",
  "procurementType": "NCT / OTM",
  "noticePublishDate": "27-Aug-2026 12:30",
  "bidClosingDate": "21-Sep-2026 12:00"
}
```

Real output for `{"mode": "awarded", "maxResults": 1}` (latest awarded contract):

```json
{
  "_input": "latest",
  "_source": "S1-awarded",
  "_scrapedAt": "2026-08-27T06:37:06Z",
  "recordType": "TENDER_AWARDED",
  "_totalPages": 873168,
  "tenderId": "1316418",
  "pkgLotId": "2110752",
  "awardedContractUrl": "https://www.eprocure.gov.bd/resources/common/ViewAwardedContracts.jsp?pkgLotId=2110752&tenderid=1316418",
  "ministry": "Ministry of Education and / Secondary and Higher Education Division",
  "referenceNo": "common/ Sthanio Bazar hote Kroy Nothi3/5/page178",
  "packageDescription": "Tender for purchasing 5 ply corrugated Board size=11.2 inch x 8.8 inch Quantity=50000PCS",
  "awardNoticeDate": "09-Aug-2026 17:00",
  "procuringOffice": "Office of the Secretary",
  "procurementMethod": "RFQ",
  "location": "Jashore",
  "publishDate": "27-Aug-2026",
  "supplierName": "M/s Bhai Bhai Engineering traders",
  "contractValueCroreBdt": "0.025"
}
```

Real output for `{"mode": "detail", "tenderId": "1324093"}` — full tender detail (truncated, `eligibilityOfTenderer` and `category` are long real text kept in full by the actor):

```json
{
  "_input": "1324093",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-27T06:37:24Z",
  "recordType": "TENDER_DETAIL",
  "tenderId": "1324093",
  "tenderUrl": "https://www.eprocure.gov.bd/resources/common/ViewTender.jsp?id=1324093&h=t",
  "ministry": "Ministry of Education",
  "division": "Secondary and Higher Education Division",
  "organization": "National University",
  "procuringEntityName": "Engineering Department",
  "procuringEntityCode": "03",
  "procuringEntityDistrict": "Gazipur",
  "procurementNature": "Goods",
  "procurementType": "NCT",
  "eventType": "TENDER",
  "invitationFor": "Tender - Single Lot",
  "invitationReferenceNo": "ENGG17-0/00304/2025(1)/1/1506, Dated: 27-Aug-2026",
  "tenderProposalStatus": "Live",
  "appId": "227165",
  "tenderProposalId": "1324093",
  "procurementMethod": "Open Tendering Method (OTM)",
  "budgetType": "Own Fund",
  "sourceOfFunds": "Own Fund",
  "projectCode": "Not applicable",
  "projectName": "Not applicable",
  "tenderProposalPackageNoAndDescription": "NU-ENGG-2026-001 Supply, Installation, Testing, and Commissioning of Video Surveillance System for National University Bangladesh",
  "category": "Computer and related services;Hardware consultancy services;... (26 CPV categories total)",
  "scheduledTenderProposalPublicationDateAndTime": "27-Aug-2026 12:05",
  "tenderProposalDocumentLastSellingDownloadingDateAndTime": "20-Sep-2026 16:00",
  "preTenderProposalMeetingStartDateAndTime": "27-Aug-2026 12:06",
  "preTenderProposalMeetingEndDateAndTime": "03-Sep-2026 17:00",
  "tenderProposalClosingDateAndTime": "21-Sep-2026 12:00",
  "tenderProposalOpeningDateAndTime": "21-Sep-2026 12:00",
  "lastDateAndTimeForTenderProposalSecuritySubmission": "20-Sep-2026 18:00",
  "eligibilityOfTenderer": "• The Tenderer shall have a minimum of 10 years of experience... (full real eligibility text, several paragraphs)",
  "briefDescriptionOfGoodsAndRelatedService": "Supply, Installation, Testing, and Commissioning of Video Surveillance System for National University, Gazipur",
  "evaluationType": "Lot wise",
  "documentAvailable": "Package wise",
  "documentFees": "Package wise",
  "tenderProposalDocumentPriceInBdt": "4000",
  "modeOfPayment": "Payment through Bank",
  "tenderProposalSecurityValidUpTo": "16-Feb-2027",
  "tenderProposalValidUpTo": "19-Jan-2027",
  "nameOfOfficialInvitingTenderProposal": "Md. Mizanoor Rahman",
  "designationOfOfficialInvitingTenderProposal": "Chief Engineer",
  "addressOfOfficialInvitingTenderProposal": "Address : National University Boardbazar, Gazipur-1704 City : Gazipur Thana : Gazipur City Corporation District : Gazipur - 1704 Country : Bangladesh",
  "contactDetailsOfOfficialInvitingTenderProposal": "Phone No : 02-996691534 Fax No :",
  "lots": [
    {
      "lotNo": "1",
      "identificationOfLot": "Supply, Installation, Testing, and Commissioning of Video Surveillance System for National University Bangladesh",
      "location": "National University, Gazipur",
      "tenderProposalSecurityAmountInBdt": "1875000",
      "tentativeStartDate": "01-Oct-2026",
      "tentativeCompletionDate": "29-Apr-2027"
    }
  ],
  "documentsUrl": "https://www.eprocure.gov.bd/LotPckDocs.jsp?tenderId=1324093"
}
```

A tender ID that doesn't exist produces one error record instead:

```json
{
  "_input": "999999999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T06:35:02Z",
  "_error": "not_found"
}
```

| Field | Description |
|---|---|
| `_input` | What produced this record — `"latest"` or a `"search:..."` summary for list/awarded rows, or the tender ID/URL for detail records. |
| `_source` | `S1-list`, `S1-awarded`, or `S1-detail`, or `"none"` on error. |
| `_scrapedAt` | UTC timestamp. |
| `_error` | Present only on failed/not-found records. |
| `recordType` | `TENDER_LIST`, `TENDER_AWARDED`, or `TENDER_DETAIL`. |
| `_totalPages` | List/awarded only — eprocure.gov.bd's own reported page count for your query (see Notes — unreliable at very small `maxResults`). |
| `tenderId` / `tenderUrl` | The tender's ID and link — feed `tenderId` into a `mode: "detail"` run for the full picture. |
| `procuringEntity` / `ministry` / `supplierName` / `contractValueCroreBdt` | Core identity — who's buying, and (awarded mode) who won and for how much. |
| *(detail mode)* | Every field eprocure.gov.bd itself shows for that tender's basic info, bid schedule, tenderer eligibility, and inviting-official contact, plus a `lots` array and a `documentsUrl` link — passed through using eprocure's own labels. |

## Notes

- **`procurementNature` and `keyword` cannot be combined.** Confirmed during recon: eprocure.gov.bd's own search endpoint silently ignores `procurementNature` whenever `keyword` is also set (keyword takes priority). Use one or the other. The actor logs a warning if both are set. See `CRAWLING_METHOD.md` for the full investigation.
- **`_totalPages` is only reliable at the page sizes this actor actually requests (10–100).** eprocure.gov.bd's own page-count calculation becomes inconsistent at very small sizes (see `CRAWLING_METHOD.md`) — this actor reports the value exactly as returned rather than guessing a "true" total.
- Contract values on awarded-contract rows are in **BDT crore** (1 crore = 10,000,000 Bangladeshi Taka), exactly as eprocure.gov.bd displays them.
- Reference-number/date formatting on live-tender rows is hand-typed per procuring entity and varies (three different shapes observed) — see `CRAWLING_METHOD.md`.
- This actor does not follow the `documentsUrl` link to list/download individual bid documents (minor scope cut, same convention as sibling actors in this collection).
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the real e-GP platform was confirmed and every gotcha found during recon.
