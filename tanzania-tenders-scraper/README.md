# Tanzania Government Tenders Scraper

Extracts public tender, award, and contract records from Tanzania's official
National e-Procurement System (NeST), run by the Public Procurement
Regulatory Authority (PPRA).

## Why use this actor

- No account, login, or API key required — every record here is public data.
- Full detail in one record: line items, buyer/procuring entity, award
  amount and winning supplier, and contract status and value — not just a
  summary row.
- Covers the whole lifecycle of a procurement process under one stable ID
  (tender → award → contract), so you don't need to cross-reference separate
  pages.
- Stable, structured JSON output ready for spreadsheets, databases, or
  reporting pipelines.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## How it works

1. Choose **List** mode to browse recent tender/award/contract records
   starting from a date you pick, or **Detail** mode to fetch one or more
   specific records you already know the ID for.
2. The actor pulls each record directly from NeST's own procurement data
   feed — the same data that powers NeST's public transparency portal.
3. Every field NeST publishes for that record — tender items, awards,
   contracts, the parties involved — is included in the output.
4. Automatic retries handle temporary hiccups on NeST's end, so you don't
   have to babysit failed requests.

## Input

**List mode** — browse recent records:

```json
{
  "mode": "list",
  "since": "2026-06-01T00:00:00Z",
  "maxResults": 25,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `since` | string | Only return records dated on/after this date (ISO 8601). Leave blank for the last 90 days. NeST's published data currently runs a couple of months behind today, so very recent dates may return nothing. |
| `maxResults` | integer | Caps how many records this run returns. |
| `proxyConfiguration` | object | Apify Proxy settings (Residential recommended). |

**Detail mode** — fetch specific records by ID:

```json
{
  "mode": "detail",
  "ocid": "ocds-mv5oob-S6990-2025-2026-G-03-S001",
  "ocids": [],
  "maxConcurrency": 2,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `ocid` | string | A single record's ID (find one from a "list" mode run's `ocid` field). |
| `ocids` | array | Multiple record IDs to fetch in one run. |
| `maxConcurrency` | integer | How many records to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run (truncated —
the full record also includes every line item, the full bid history, and
the release-by-release timeline):

```json
{
  "_input": "list:since=2026-05-01T00:00:00Z",
  "_source": "S1-records-list",
  "_scrapedAt": "2026-08-27T05:48:30Z",
  "tenderId": "80L1/2025/2026/G/327-S001",
  "tenderTitle": "SUPPLY OF FURNITURE FOR NAMANJELE DISPENSARY",
  "tenderStatus": "complete",
  "procurementMethod": "direct",
  "procurementMethodDetails": "Minor Value Procurement",
  "buyerName": "MTWARA DISTRICT COUNCIL",
  "procuringEntityName": "MTWARA DISTRICT COUNCIL",
  "tenderPeriodStartDate": "2026-05-04T00:00:00Z",
  "tenderPeriodEndDate": "2026-05-05T10:00:00Z",
  "recordDate": "2026-05-05T16:29:47Z",
  "awardsCount": 1,
  "contractsCount": 1,
  "totalAwardAmount": 14935000.0,
  "awardCurrency": "TZS",
  "ocid": "ocds-mv5oob-80L1-2025-2026-G-327-S001",
  "compiledRelease": {
    "buyer": { "name": "MTWARA DISTRICT COUNCIL" },
    "tender": {
      "id": "80L1/2025/2026/G/327-S001",
      "status": "complete",
      "items": [
        { "description": "VISITORS CHAIR", "quantity": 15.0, "unit": { "name": "PCS" } },
        { "description": "EXECUTIVE CHAIR", "quantity": 4.0, "unit": { "name": "PCS" } }
        // ... 5 more items
      ]
    },
    "awards": [
      {
        "description": "SUPPLY OF FURNITURE FOR NAMANJELE DISPENSARY",
        "value": { "currency": "TZS", "amount": 14935000.0 },
        "suppliers": [{ "name": "A and Y INVESTMENT" }]
      }
    ],
    "contracts": [
      {
        "status": "pending",
        "value": { "currency": "TZS", "amount": 14935000.0 },
        "period": { "startDate": "2026-05-07T00:00:00Z", "endDate": "2026-06-07T00:00:00Z" }
      }
    ]
  },
  "releases": [
    { "date": "2026-05-01T00:26:58Z", "tag": ["tender"] },
    { "date": "2026-05-04T00:00:00Z", "tag": ["tenderUpdate"] }
    // ... 8 more release events
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `ocid` | string | Stable ID for this procurement process, unchanged from tender through award and contract. |
| `tenderId` / `tenderTitle` / `tenderStatus` | string | The tender's own reference number, title, and status. |
| `buyerName` / `procuringEntityName` | string | The government body running this procurement. |
| `tenderPeriodStartDate` / `tenderPeriodEndDate` | string | Bid submission window. |
| `awardsCount` / `contractsCount` | integer | How many award/contract entries exist on this record. |
| `totalAwardAmount` / `awardCurrency` | number / string | Combined award value and its currency. |
| `compiledRelease` | object | The full record: line items, parties, awards (with winning supplier), contracts, and bid details. |
| `releases` | array | The timeline of individual events (tender published, updated, awarded, contracted) that make up this record. |
| `_error` | string | Present only when a record couldn't be retrieved. |

A record fetched in **detail** mode has the identical shape (`_source` reads
`"S1-records-detail"` instead).

## Notes

- List mode returns however many records genuinely match your date range —
  fewer than `maxResults` (including zero, for a very recent date) simply
  means fewer records currently exist for that window; nothing is padded.
- For heavier usage, Residential proxies are recommended (set by default).

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ghana
(GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP), Papua New Guinea
(NPC), Sierra Leone (NPPA), and Nepal (Bolpatra).
