# Namibia Government Tenders Scraper (CPBN)

Scrapes Namibia's official government tender and bid notices from the Central Procurement Board of Namibia (CPBN). No account or login needed.

## Why use this actor

- Pulls from Namibia's real, official procurement authority — not a third-party tender-alert aggregator
- Eight views in one actor: **open bids**, bids **under evaluation**, **cancelled** bids, **awarded** contracts, **clarifications**, the **bid opening register**, **notices**, and the **full historical archive** (600+ records)
- Full bid detail on demand — category, institution, description, document price, closing date, bid-opening logistics, clarification contact, and pre-bid meeting info
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse a listing (`mode: "list"`), or fetch full detail for specific bids you already know (`mode: "detail"`).
2. For listings, choose which one: open bids, bids under evaluation, cancelled, awarded, clarifications, the opening register, notices, or the full archive.
3. The actor fetches the listing and returns every row it has, up to the limit you set.
4. Every bid with its own page includes an ID and link, so you can follow up with `mode: "detail"` for the full picture.
5. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage sessions or retries — the actor handles all of it.

## Input

**Browse the full archive (default):**
```json
{
  "mode": "list",
  "listType": "all",
  "maxResults": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Fetch full detail for a specific bid:**
```json
{
  "mode": "detail",
  "bidId": "109",
  "maxConcurrency": 3
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — browse a listing page. `"detail"` — fetch full detail for specific bid IDs. |
| `listType` | string | `mode: "list"` only. `"open"` — currently accepting submissions (can genuinely be empty between announcements). `"underEvaluation"` — submission closed, being evaluated. `"cancelled"`. `"awarded"` — selection notices. `"clarifications"`. `"openingRegister"`. `"notices"`. `"all"` (default) — the full historical archive, 600+ records. |
| `maxResults` | integer | `mode: "list"` only. Max rows kept from the listing. Default 100, max 2000. |
| `bidId` | string | `mode: "detail"` only. A single bid's numeric ID or full bid URL. |
| `bidIds` | array | `mode: "detail"` only. Multiple bid IDs or URLs to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many bids to fetch in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "list", "listType": "all", "maxResults": 1}`:

```json
{
  "_input": "list:all",
  "_source": "S1-all-listing",
  "_scrapedAt": "2026-08-27T05:38:20Z",
  "recordType": "BID_ALL",
  "_totalAvailable": 694,
  "bidId": "109",
  "bidUrl": "https://www.cpbn.com.na/index/bid/109",
  "title": "The Construction of the New Anti-Corruption Commission Offices in Oshakati, Oshana Region.: W/ONB/CPBN-08/2026",
  "referenceNumber": "W/ONB/CPBN-08/2026",
  "closingDateAndTime": "5th August, 2026 11:00",
  "documents": [
    { "label": "Full Advert - New Anti-Corruption Commission.pdf", "downloadUrl": "https://www.cpbn.com.na/ajax/download/469" },
    { "label": "ACC_ Bidding Document_ACC Offices Oshakati Watermarked.pdf", "downloadUrl": "https://www.cpbn.com.na/ajax/download/472" }
    // ... 2 more documents
  ]
}
```

Older PDF-only notices (no separate detail page) come back with a single `date` field instead of `referenceNumber`/`closingDateAndTime`:

```json
{
  "_input": "list:all",
  "_source": "S1-all-listing",
  "_scrapedAt": "2026-08-27T05:38:20Z",
  "recordType": "BID_ALL",
  "_totalAvailable": 694,
  "bidId": null,
  "bidUrl": null,
  "title": "Request for Proposal for the Appointment of a Consultant (Firm) to Support, Maintain and Enhance the Integrated Financial Management System (IFMS) for a Period of Five (5) Years for the Ministry of Finance",
  "date": "28th July, 2026",
  "documents": [
    { "label": "Bid Submission List.pdf", "downloadUrl": "https://www.cpbn.com.na/uploads/files/qz147nl3y50tkge.pdf" }
  ]
}
```

Real output for `{"mode": "detail", "bidId": "109"}` — full bid detail (truncated, this bid has 14 fields in total):

```json
{
  "_input": "109",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-27T05:38:42Z",
  "recordType": "BID_DETAIL",
  "bidId": "109",
  "bidUrl": "https://www.cpbn.com.na/index/bid/109",
  "pageTitle": "The Construction of the New Anti-Corruption Commission Offices in Oshakati, Oshana Region. - W/ONB/CPBN-08/2026",
  "category": "Works",
  "institution": "Anti-Corruption Commission",
  "descriptionOfTheBid": "The Construction of the New Anti-Corruption Commission Offices in Oshakati, Oshana Region.",
  "procurementReferenceNumber": "W/ONB/CPBN-08/2026",
  "dateOfIssue": "19th June, 2026",
  "closingDateAndTime": "5th August, 2026 11:00",
  "generalEnquiries": "The Central Procurement Board of Namibia Erf 8161 Julius Nyerere Street, Southern Industry, Namibia Tel: +264 61 447700 Email Address: Externalbids@cpbn.com.na"
  // ... 7 more fields, plus a "documents" array
}
```

A bid ID that doesn't exist produces one error record instead:

```json
{
  "_input": "999999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T05:38:42Z",
  "_error": "not_found_or_restricted",
  "_errorDetail": ""
}
```

| Field | Description |
|---|---|
| `_input` | What produced this record — `"list:<listType>"` for listing rows, or the bid ID/URL for detail records. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on failed/inaccessible records. |
| `recordType` | `BID_OPEN`, `BID_UNDEREVALUATION`, `BID_CANCELLED`, `BID_AWARDED`, `BID_CLARIFICATIONS`, `BID_OPENINGREGISTER`, `BID_NOTICES`, `BID_ALL`, or `BID_DETAIL`. |
| `bidId` / `bidUrl` | The bid's ID and link, when it has its own page — feed `bidId` into a `mode: "detail"` run for the full picture. `null` for older notices that predate individual bid pages. |
| `title` | The bid/notice title, usually including its own reference number. |
| `referenceNumber` / `closingDateAndTime` | Shown for bids that have their own detail page. |
| `date` | Shown instead, for older notices with no separate detail page. |
| `documents` | Attached PDFs as `{label, downloadUrl}`. Some links are direct files; others go through a short "request access" form on CPBN's own site before releasing the file — this actor records the link but does not fill in that form. |
| *(detail mode)* | Every field CPBN itself shows for that bid — the exact set varies (a Works tender includes a pre-bid meeting/site-visit field a Goods tender doesn't), always passed through using CPBN's own labels. |

## Notes

- `open` and `notices` can genuinely return 0 results — CPBN itself shows no rows for those categories between announcements, and this actor reports that honestly rather than guessing.
- The full archive (`all`) is large (600+ records) but downloads in a single request — no need to lower `maxResults` for speed, only to trim the output size.
- See `CRAWLING_METHOD.md` for the full technical writeup, including why Namibia has two different CPBN-branded websites and only one of them actually publishes live tenders.
