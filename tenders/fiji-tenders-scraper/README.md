# Fiji Government Tenders Scraper (Ministry of Finance)

Scrapes Fiji's Ministry of Finance e-tendering site for public
procurement: currently open tenders, and tenders awarded within the past
36 months with the winning company's name where published. No account or
login needed.

## Why use this actor

- Pulls from the government's real, official e-tendering site — not a
  third-party tender-alert aggregator
- Two views in one actor: **Current tenders** (open now, ~17 at a time)
  and **Awards** (past 36 months, ~369 records, with winning bidder names)
- No account, no API key, no CAPTCHA to solve — the tender list itself is
  public, even though the site requires registration to view full
  documents or respond
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

1. Pick a list type: `current` for what's open for submission right now,
   or `awards` for the 36-month award history.
2. The actor fetches the matching listing page and returns up to the limit
   you set.
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

**Tender awards (past 36 months, with winning bidders):**
```json
{
  "listType": "awards",
  "maxResults": 500
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"current"` (default) — tenders open for submission right now (~17 at a time). `"awards"` — tenders awarded within the past 36 months (~369 at a time), with the winning company's name where published. |
| `maxResults` | integer | Caps how many records are kept in the output. Default 500, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "current", "maxResults": 1}`:

```json
{
  "_input": "list:current",
  "_source": "S1-tenderlink-html-table-alltenders",
  "_scrapedAt": "2026-08-27T19:32:37Z",
  "recordType": "CURRENT_TENDER",
  "referenceNumber": "ECONFJ-1169356",
  "summary": "RFT No. 6/2026-2027: Supply of 3 x New 4 x 4 Twin Cab Pickup Vehicle with Specialized Accessories",
  "awardedTo": null,
  "dateTime": "2/9/2026 2:30 PM FJT"
}
```

Real output for `{"listType": "awards", "maxResults": 1}`:

```json
{
  "_input": "list:awards",
  "_source": "S1-tenderlink-html-table-awards",
  "_scrapedAt": "2026-08-27T19:32:51Z",
  "recordType": "TENDER_AWARD",
  "referenceNumber": "ECONFJ-1160710",
  "summary": "RFT No. 138/2025 - 2026 – Supply and Implementation of Two-Bin Waste Management System",
  "awardedTo": "Waste Clear Fiji Pte Ltd",
  "dateTime": "10/6/2026 2:30 PM FJT"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:current"` or `"list:awards"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `CURRENT_TENDER` or `TENDER_AWARD`. |
| `referenceNumber` / `summary` | TenderLink's own notice code, and what is being procured (usually including the RFT number and sometimes the procuring entity). |
| `awardedTo` | The winning company's name, parsed out of the upstream text (`awards` only — not every awarded tender has this published). |
| `dateTime` | Upstream free-text close/closed date and time, in Fiji local time (FJT). |

## Notes

- The tender *list* is public — viewing full tender documents or
  responding to a tender requires TenderLink registration, which this
  actor does not attempt or require.
- `awardedTo` is `null` for roughly 12% of award records — the government
  didn't publish a winning-bidder name for every awarded tender; reported
  honestly as missing rather than guessed.
- Every field is passed through exactly as published — no reformatting,
  no translation.
- See `CRAWLING_METHOD.md` for the full technical writeup.
