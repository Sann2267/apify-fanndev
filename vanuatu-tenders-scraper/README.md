# Vanuatu Government Tenders Scraper (Central Tender Board)

Scrapes Vanuatu's Central Tender Board (CTB) official e-tendering site,
`ctb.gov.vu`, for public procurement: currently open tenders and the
historical archive of tender results, with reference number, title,
purchaser, category, submission/expiry dates, and full description. No
account or login needed.

## Why use this actor

- Pulls from the government's real, official e-tendering site — not a
  third-party tender-alert aggregator
- Two views in one actor: **Current tenders** (open now, ~58 at a time) and
  **Tenders results** (historical archive, ~140 records)
- Rich fields already inline — no extra request per record needed: type of
  solicitation, reference number, purchaser, category, both dates, and the
  full description text
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

1. Pick a list type: `current` for what's open for submission right now, or
   `results` for the historical archive.
2. The actor pages through the listing (Vanuatu's site returns 20 records
   per page) and returns up to the limit you set.
3. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

**Currently open tenders (default):**
```json
{
  "listType": "current",
  "maxResults": 500,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Historical archive of tender results:**
```json
{
  "listType": "results",
  "maxResults": 500
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"current"` (default) — tenders open for submission right now (~58 at a time). `"results"` — the historical archive of the same card shape (~140 records). |
| `maxResults` | integer | Caps how many records are kept in the output. Default 500, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "current", "maxResults": 1}`:

```json
{
  "_input": "list:current",
  "_source": "S1-joomla-finder-actual-tenders",
  "_scrapedAt": "2026-08-27T18:58:10Z",
  "recordType": "CURRENT_TENDER",
  "tenderType": "Request For Tender",
  "referenceNumber": "No.RFT MFEM MALAMPA 01/25",
  "title": "Construction Works of the MFEM Malampa Office Extension Building, Lakatoro, Malekula, MALAMPA Province",
  "purchaser": "Ministry of Finance and Economic Management",
  "category": "Construction Work",
  "submissionDate": "01 Jul 2025 08:00",
  "expiryDate": "29 Aug 2025",
  "description": "The Government of the Republic of Vanuatu represented by the Ministry of Finance and Economic Management (the Employer) seeks Tender for the Construction of MFEM building Extension in Lakatoro, Malekula Island, MALAMPA Province. ...",
  "detailUrl": "https://ctb.gov.vu/en/tenders-category/221-construction-works-of-the-mfem-malampa-office-extension-building-lakatoro-malekula-malampa-province"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:current"` or `"list:results"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `CURRENT_TENDER` or `TENDER_RESULT`. |
| `tenderType` | The solicitation type, e.g. "Request For Tender", "Request For Proposal". |
| `referenceNumber` / `title` | The Central Tender Board's own reference code, and what is being procured. |
| `purchaser` / `category` | The procuring ministry/department/project, and its category (e.g. "Construction Work", "Road Works"). |
| `submissionDate` / `expiryDate` | Upstream free-text bid submission deadline and tender expiry date. |
| `description` | The full description text as published. |
| `detailUrl` | The tender's own `ctb.gov.vu` page — carries a few extra fields not repeated here (Date Issued, Completion Date, Opening date/time, Contact Person/Email). |

## Notes

- Every field is passed through exactly as published by the Central Tender
  Board — no reformatting, no translation, no fabricated historical data.
- The listing pages already carry a full description, so this actor does
  not fetch each tender's own detail page (which would add one extra
  request per record) — `detailUrl` is included so you can open it
  yourself for the few extra fields it carries (issue date, completion
  date, opening time, contact person/email).
- See `CRAWLING_METHOD.md` for the full technical writeup.
