# Eswatini Government Tenders Scraper (ESPPRA)

Scrapes Eswatini's official public procurement regulator — ESPPRA (Eswatini
Public Procurement Regulatory Agency) — for open tender invitations,
intention-to-award notices, and the suspended-supplier debarment register.
No account or login needed.

## Why use this actor

- Pulls from Eswatini's real, official procurement regulator — not a
  third-party tender-alert aggregator
- Three views in one actor: **open tenders**, **intention-to-award notices**
  (a large historical archive), and the **suspended-supplier debarment
  register**
- Optional keyword filter (by procuring entity, tender title, or
  procurement method) for the two tender listings
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

1. Pick which listing to scrape (`listType`): tenders currently open for
   bidding, historical intention-to-award notices, or the suspended-supplier
   register.
2. Optionally narrow it with a `keyword`.
3. The actor fetches and paginates through the results automatically, up to
   the `maxResults` limit you set.
4. Every record includes a direct link to the official notice PDF.
5. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

You don't need to manage sessions, pagination, or retries — the actor
handles all of it.

## Input

**Browse open tenders (default):**
```json
{
  "listType": "tenders",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Filter by keyword:**
```json
{
  "listType": "tenders",
  "keyword": "Electricity",
  "maxResults": 20
}
```

**Browse the intention-to-award archive:**
```json
{
  "listType": "award_intentions",
  "maxResults": 100
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"tenders"` (default) — open for bidding (~60 at a time). `"award_intentions"` — historical archive of intention-to-award notices (1,500+). `"suspended_suppliers"` — the debarment register (small). |
| `maxResults` | integer | Max rows to return, across as many pages as needed. Default 50, max 5000. Ignored for `suspended_suppliers`. |
| `keyword` | string | Optional server-side filter by procuring entity, tender title, or procurement method. Applies to `tenders` and `award_intentions` only. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "tenders", "maxResults": 1}`:

```json
{
  "_input": "list:tenders",
  "_source": "S1-tenders-listing",
  "_scrapedAt": "2026-08-27T05:34:32Z",
  "recordType": "TENDER_INVITATION",
  "_page": 1,
  "_totalAvailable": 61,
  "_totalPages": 7,
  "title": "Consultancy Services For The Development of the Mbabane Economic Development Strategy (EDS) 2026-2030",
  "procuringEntity": "Municipal Council of Mbabane",
  "referenceNumber": "03-2026/2027",
  "procurementMethod": "Request For Proposal",
  "tenderUploadDate": "Tuesday 28th July 2026 9:56 am",
  "submissionDeadline": "Thursday 27th August 2026 12:00 pm",
  "documentId": "28964",
  "documentUrl": "https://esppra.co.sz/sppra/documents/tenders/Municipal Council of Mbabane/1785225179.pdf"
}
```

Real output for `{"listType": "award_intentions", "maxResults": 1}`:

```json
{
  "_input": "list:award_intentions",
  "_source": "S1-award_intentions-listing",
  "_scrapedAt": "2026-08-27T05:34:44Z",
  "recordType": "TENDER_AWARD_INTENTION",
  "_page": 1,
  "_totalAvailable": 1572,
  "_totalPages": 79,
  "title": "Provision of Office Cleaning Services",
  "procuringEntity": "Municipal Council of Manzini",
  "referenceNumber": "MCMz002 of 2026/27",
  "uploadDate": "Tuesday 25th August 2026 10:27 am",
  "documentId": "MCMz002 of 2026/27",
  "documentUrl": "https://esppra.co.sz/sppra/documents/intentions/Municipal Council of Manzini/1787646475.pdf"
}
```

Real output for `{"listType": "suspended_suppliers"}` (the whole register,
currently 1 record):

```json
{
  "_input": "list:suspended_suppliers",
  "_source": "S1-suspended_suppliers-listing",
  "_scrapedAt": "2026-08-27T05:34:47Z",
  "recordType": "SUSPENDED_SUPPLIER",
  "_page": 1,
  "_totalAvailable": 1,
  "_totalPages": 1,
  "supplierId": "1",
  "tradingName": "LCC Capital Consulting",
  "companyName": "Consortium Consulting (Pty) LTD",
  "suspensionStartDate": "17th Jun 22",
  "suspensionEndDate": "17th Jun 25",
  "suspensionDocumentFile": "1655900851.pdf",
  "_actionRawPlaceholder": "1st Jan 70",
  "suspensionDocumentUrl": "https://esppra.co.sz/sppra/documents/suspended/1655900851.pdf"
}
```

A page/network failure produces one error record instead of crashing the run:

```json
{
  "_input": "list:tenders:page3",
  "_source": "none",
  "_error": "blocked_or_transient",
  "_errorDetail": "..."
}
```

| Field | Description |
|---|---|
| `_input` | `"list:<listType>"` for every record. |
| `_source` | Which listing the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on failed/inaccessible records. |
| `recordType` | `TENDER_INVITATION`, `TENDER_AWARD_INTENTION`, or `SUSPENDED_SUPPLIER`. |
| `_totalAvailable` / `_totalPages` | ESPPRA's own reported totals for this listing, before `maxResults` truncation. |
| `title` / `procuringEntity` / `referenceNumber` | Tender/intention name, the government body running it, and its reference number. |
| `procurementMethod` / `submissionDeadline` | `tenders` only. |
| `uploadDate` | `award_intentions` only. |
| `documentUrl` | Direct link to the official notice PDF (works for `tenders` and `award_intentions`; see `suspensionDocumentUrl` for `suspended_suppliers`). |
| `tradingName` / `companyName` / `suspensionStartDate` / `suspensionEndDate` | `suspended_suppliers` only. |

## Notes

- `award_intentions` is a large historical archive (1,500+ entries) — start
  with a small `maxResults` to preview before scraping in bulk.
- `award_intentions` does not include the winning supplier's name or the
  contract amount — ESPPRA's own listing doesn't publish that here, only the
  notice PDF link.
- Dates are passed through exactly as ESPPRA displays them, not normalized
  to ISO 8601 (the format differs between listing views).
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the
  real ESPPRA platform was confirmed and a documented certificate-chain
  workaround needed for every request.
