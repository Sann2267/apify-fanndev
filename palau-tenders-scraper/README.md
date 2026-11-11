# Palau Government Tenders Scraper (ROP Procurement)

Scrapes the Republic of Palau's ROP Procurement page for open government
tenders and RFPs across all agencies: ministry/department, description,
reference number, direct PDF notice link, opening and closing dates. No
account or login needed.

## Why use this actor

- Pulls from the government's real, official procurement page — not a
  third-party tender-alert aggregator
- Covers all three procurement categories in one run: **BHR** (routine
  goods/services), **CIP** (Capital Improvement Projects), and **Other
  Organizations**
- Direct link to every tender's official PDF notice
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

The actor fetches Palau's ROP Procurement page and returns every currently
open tender across all three category tables, up to the limit you set.

## Input

```json
{
  "maxResults": 500,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `maxResults` | integer | Caps how many records are kept in the output. Default 500, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"maxResults": 1}`:

```json
{
  "_source": "S1-html-table-rfp-bids",
  "_scrapedAt": "2026-08-27T19:16:06Z",
  "recordType": "CURRENT_TENDER",
  "category": "BHR",
  "ministryOrDepartment": "Bureau of Aviation",
  "description": "Assist the Bureau of Aviation in the landscaping and maintenance of the Palau International Airport's exterior perimeter fence",
  "referenceNumber": "PCS-2026-59 (15 Day Public Notice)",
  "noticeUrl": "https://www.palaugov.pw/wp-content/uploads/15-Day-Notice-PCS-2026-59.pdf",
  "openingDate": "9/09/2026",
  "closingDate": "10/08/2026"
}
```

| Field | Description |
|---|---|
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | Always `CURRENT_TENDER` — this site publishes only currently-open tenders, no historical archive. |
| `category` | Which of the three upstream tables this came from: `"BHR"`, `"CIP"`, or `"Other Organizations"`. |
| `ministryOrDepartment` / `description` | The procuring government body, and what is being procured. |
| `referenceNumber` / `noticeUrl` | The government's own bid/RFP reference code, and a direct link to the official PDF notice. |
| `openingDate` / `closingDate` | Upstream free-text opening date and bid submission deadline. |

## Notes

- Palau publishes tenders on a single page with no pagination and no
  separate historical archive or contract-award page — every run returns
  what's open right now (typically under 20 records across all three
  categories, reflecting the country's small government scale, not a
  scraping limitation).
- The "Other Organizations" category is frequently empty upstream — that's
  the government's own normal state (nothing posted there right now), not
  an error; this actor simply won't emit a record for it when empty rather
  than fabricating one.
- Every field is passed through exactly as published — no reformatting, no
  translation.
- See `CRAWLING_METHOD.md` for the full technical writeup.
