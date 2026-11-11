# Saint Vincent and the Grenadines Government Tenders Scraper

Scrapes the Central Procurement Board's official eProcurement portal,
`procurement.gov.vc`, for Saint Vincent and the Grenadines: currently open
bids, the historical archive of recently closed bids, and yearly contract
award notice documents. No account or login needed.

## Why use this actor

- Pulls from the government's real, official eProcurement microsite — not a
  third-party tender-alert aggregator
- Three views in one actor: **Current bids** (open now), **Closed bids**
  (400+ record historical archive), and **Contract award notices** (yearly
  PDF documents)
- Every bid links directly to its official bid/Terms-of-Reference PDF
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

1. Pick a list type: `current` for what's open for submission right now,
   `closed` for the historical archive, or `awards` for yearly
   award-of-contracts PDF documents.
2. The actor fetches the matching listing page and returns up to the limit
   you set.
3. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

**Currently open bids (default):**
```json
{
  "listType": "current",
  "maxResults": 500,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Historical archive of closed bids:**
```json
{
  "listType": "closed",
  "maxResults": 500
}
```

**Yearly contract award documents:**
```json
{
  "listType": "awards",
  "maxResults": 100
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"current"` (default) — bids open for submission right now (~20 at a time). `"closed"` — the historical archive of the same table (400+ records). `"awards"` — one row per calendar year (2017-2025) linking to the Central Procurement Board's quarterly "Award of Contracts" PDF bundles. |
| `maxResults` | integer | Caps how many records are kept in the output. Default 500, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "current", "maxResults": 1}`:

```json
{
  "_input": "list:current",
  "_source": "S1-html-table-current-bids",
  "_scrapedAt": "2026-08-27T18:40:57Z",
  "recordType": "CURRENT_BID",
  "no": "1",
  "referenceNumber": "SVGSFD1-W-RFB-1",
  "title": "Construction of Paget Farm Community Health Clinic",
  "pdfUrl": "https://procurement.gov.vc/eprocure/images/pdf/CurrentBids/SPN%20Paget%20Farm%20works.pdf",
  "procuringEntity": "Ministry of Finance and Economic Planning",
  "procurementType": "Services",
  "tenderType": "Invitation to Bid",
  "submissionDeadline": "October 30, 2026 @ 2:00 p.m."
}
```

Real output for `{"listType": "awards", "maxResults": 1}`:

```json
{
  "_input": "list:awards",
  "_source": "S1-html-table-contract-award-notices",
  "_scrapedAt": "2026-08-27T18:41:11Z",
  "recordType": "AWARD_DOCUMENT",
  "year": "2025",
  "documentLabel": "1st Quarter to 4th Quarter",
  "pdfUrl": "https://procurement.gov.vc/eprocure/images/pdf/contracts/CPB%20Award%20of%20Contracts%202025.pdf"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:current"`, `"list:closed"`, or `"list:awards"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `CURRENT_BID`, `CLOSED_BID`, or `AWARD_DOCUMENT`. |
| `no` / `referenceNumber` | The portal's row number and the procuring entity's own bid reference code (`current`/`closed` only). |
| `title` / `pdfUrl` | What is being procured and the direct bid/ToR PDF link (`current`/`closed`), or the document's quarter label (`awards` uses `documentLabel` instead). |
| `procuringEntity` / `procurementType` / `tenderType` | The government body running it, and whether it's Goods/Services/Works and what kind of solicitation (`current`/`closed` only). |
| `submissionDeadline` | Upstream free-text deadline; sometimes blank on a linked Terms-of-Reference row that shares its parent bid's deadline (`current`/`closed` only). |
| `year` / `documentLabel` | Which calendar year and quarter this award document covers (`awards` only). |

## Notes

- Every field is passed through exactly as published by the Central
  Procurement Board — no reformatting, no translation, no fabricated
  historical data.
- `awards` mode returns document-level records (one per PDF bundle), not
  individual contract-level records — the government only publishes these
  as periodic quarterly/yearly PDFs, not as a structured per-contract table.
- `submissionDeadline` is occasionally blank upstream on a row that's really
  the linked Terms of Reference for the row above it, sharing the same
  deadline — reported as-is rather than guessed/copied across rows.
- See `CRAWLING_METHOD.md` for the full technical writeup.
