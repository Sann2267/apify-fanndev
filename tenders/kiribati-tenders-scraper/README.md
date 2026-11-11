# Kiribati Government Tenders Scraper (Central Procurement Unit)

Scrapes Kiribati's Central Procurement Unit tender list for public
procurement notices: reference number, procuring entity, description,
open/close dates, and a link to each tender's detail page. Covers both
currently open and historical tenders back to at least 2021. No account or
login needed.

## Why use this actor

- Pulls from the government's real, official procurement site — not a
  third-party tender-alert aggregator
- One list, newest-first — a small `maxResults` gets you the currently
  open tenders; a larger one pulls the full historical archive (500+
  records observed going back to 2021)
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

The actor pages through Kiribati's Central Procurement Unit tender list
(10 records per page, newest first) and returns up to the limit you set.

## Input

```json
{
  "maxResults": 200,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `maxResults` | integer | Caps how many records are kept in the output. Default 200, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"maxResults": 1}`:

```json
{
  "_source": "S1-html-table-tender-list",
  "_scrapedAt": "2026-08-27T19:22:53Z",
  "recordType": "TENDER",
  "referenceNumber": "23-W004-26",
  "procuringEntity": "MOE",
  "description": "Request for Proposal (RFP) for Tebwanimaneka Primary School Fence",
  "openDate": "Mon, 08/10/2026 - 09:00",
  "closeDate": "Wednesday, September 23, 2026 - 17:00",
  "detailUrl": "https://procurement.gov.ki/-617"
}
```

| Field | Description |
|---|---|
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | Always `TENDER`. |
| `referenceNumber` / `procuringEntity` | The Central Procurement Unit's own reference code, and the ministry/agency acronym running the procurement (e.g. MOE, MFED, MCIA). |
| `description` | What is being procured. |
| `openDate` / `closeDate` | Upstream free-text dates the tender opened and its bid submission deadline. |
| `detailUrl` | The tender's own `procurement.gov.ki` page, which carries downloadable tender documents not repeated in this dataset. |

## Notes

- This list is not split into separate current/closed views upstream —
  it's one continuous chronological archive, newest first. Set a small
  `maxResults` if you only want what's open right now.
- Tender documents (PDFs, Word docs, zips) live on each tender's own
  `detailUrl` page rather than in this dataset directly — fetching every
  tender's detail page would multiply request volume against a large
  archive (500+ records observed), so this actor keeps to one request per
  page of the list and lets you open a specific tender's documents
  yourself via `detailUrl`.
- Every field is passed through exactly as published — no reformatting,
  no translation.
- See `CRAWLING_METHOD.md` for the full technical writeup.
