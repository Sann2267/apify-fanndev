# Vietnam Government Tenders Scraper

Extracts public procurement plans, tender notices, award results, and
signed contracts from Vietnam's official **National E-Procurement System**
(VNEPS — "Hệ thống mạng đấu thầu quốc gia"), run by the Ministry of Planning
and Investment.

## Why use this actor

- No account, login, or API key required — every record here is public data.
- Covers the whole procurement lifecycle in one feed: procurement plans,
  tender notices, contractor-selection award results (winner + price), and
  signed contracts.
- **Detail mode** pulls the full award decision for a specific tender:
  decision document, per-lot contractor list, tax codes, contract period.
- Search by keyword, date range, or record type; results come back
  newest-first.
- Stable, structured JSON output ready for spreadsheets, databases, or
  reporting pipelines.

## How it works

1. Choose **List** mode to search or browse recent plans/notices/results/
   contracts, or **Detail** mode to fetch full award detail for a specific
   record you already have an `inputResultId` for (from a prior List run).
2. The actor calls VNEPS's own internal search and detail services directly
   — the same ones its public search page uses.
3. Automatic retries handle temporary hiccups; every field VNEPS returns for
   a record is included in the output, not just a flattened summary.

## Input

**List mode** — search/browse:

```json
{
  "mode": "list",
  "keyword": "",
  "dateFrom": "",
  "dateTo": "",
  "recordType": "all",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `keyword` | string | Free-text search across notice number and bid name. Blank = everything. |
| `dateFrom` / `dateTo` | string | Only return records published in this window (local Vietnam time, e.g. `2026-08-20T00:00:00`). Blank = no date filter (newest records first). |
| `recordType` | string | `all`, `es-plan-project-p` (plans only), `es-notify-contractor` (notices & results only), or `es-ct-contract` (signed contracts only). |
| `maxResults` | integer | Caps how many records this run returns (up to 10,000 per distinct filtered query — VNEPS's own search-index limit). |
| `proxyConfiguration` | object | Apify Proxy settings (Residential recommended). |

**Detail mode** — fetch full award detail:

```json
{
  "mode": "detail",
  "inputResultId": "60d9a607-b813-47ae-a09a-64f09ff9b2f9",
  "inputResultIds": [],
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `inputResultId` | string | A single record's award-result id (find one from a "list" mode run's `inputResultId` field — only present once a record has reached the award stage). |
| `inputResultIds` | array | Multiple award-result ids to fetch in one run. |
| `maxConcurrency` | integer | How many records to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run:

```json
{
  "_input": "list:keyword='' dateFrom=None dateTo=None recordType='all'",
  "_source": "S1-smart-search",
  "_scrapedAt": "2026-08-27T06:23:40Z",
  "titleDisplay": "Gói thầu số 03: Tư vấn thẩm tra thiết kế BVTC và dự toán công trình",
  "recordType": "es-notify-contractor",
  "stepCode": "notify-contractor-step-4-kqlcnt",
  "notifyNo": "IB2600491184",
  "planNo": "PL2600274353",
  "investorName": "Trung tâm Dịch vụ Tổng hợp xã Xuân Đông",
  "publicDate": "2026-08-27T13:23:07",
  "bidCloseDate": "2026-08-27T13:23:09.488",
  "decisionDate": "2026-08-22T23:59:59",
  "status": "IS_PUBLISH",
  "investField": ["TV"],
  "bidPriceDisplay": 4320000.0,
  "winningContractorDisplay": "CÔNG TY TNHH MỘT THÀNH VIÊN MÁI NGÓI ĐỎ",
  "bidWinningPriceDisplay": 4320000.0,
  "inputResultId": "60d9a607-b813-47ae-a09a-64f09ff9b2f9",
  "raw": {
    "id": "IB2600491184",
    "notifyNo": "IB2600491184",
    "bidName": ["Gói thầu số 03: Tư vấn thẩm tra thiết kế BVTC và dự toán công trình"],
    "winningCode": ["vn3602864806"],
    "contractorName": ["CÔNG TY TNHH MỘT THÀNH VIÊN MÁI NGÓI ĐỎ"],
    "bidWinningPrice": [4320000.0],
    "bidPrice": [4320000.0]
    // ... more upstream fields verbatim
  }
}
```

| Field | Type | Description |
|---|---|---|
| `titleDisplay` | string | The bid/plan title. |
| `recordType` | string | `es-plan-project-p`, `es-notify-contractor`, or `es-ct-contract`. |
| `notifyNo` / `planNo` | string | The notice/plan's own reference number. |
| `procuringEntityName` / `investorName` | string | The government body running this procurement. |
| `publicDate` / `bidCloseDate` / `decisionDate` | string | Key dates (local Vietnam time). |
| `investField` | array | Category codes, e.g. `TV` (consulting), `HH` (goods), `XL` (construction). |
| `winningContractorDisplay` / `bidWinningPriceDisplay` | string / number | Winner and winning price, once the record reaches the award stage. |
| `inputResultId` | string | Pass this into a **detail** run for full award/contract detail. |
| `raw` | object | The complete upstream search-hit object, untouched. |
| `_error` | string | Present only when a record couldn't be retrieved. |

Real sample from a **detail** run:

```json
{
  "_input": "60d9a607-b813-47ae-a09a-64f09ff9b2f9",
  "_source": "S1-contractor-input-result-detail",
  "_scrapedAt": "2026-08-27T06:23:53Z",
  "inputResultId": "60d9a607-b813-47ae-a09a-64f09ff9b2f9",
  "notifyNo": "IB2600491184",
  "bidNo": "BP2600680436",
  "bidName": "Gói thầu số 03: Tư vấn thẩm tra thiết kế BVTC và dự toán công trình",
  "decisionNo": "262/QĐ-TTDVTH",
  "decisionDate": "2026-08-22T23:59:59",
  "decisionAgency": "Trung tâm Dịch vụ Tổng hợp xã Xuân Đông",
  "lotCount": 1,
  "winningContractorOrgCodes": ["vn3602864806"],
  "winningContractorTaxCodes": ["3602864806"],
  "winningPrices": [4320000],
  "fullDetail": { "...": "the complete upstream response, including decision document ids/names, per-lot contractor list, contact email, contract period" }
}
```

## Notes

- List mode returns however many records genuinely match your filters —
  fewer than `maxResults` (including zero) simply means fewer records
  currently exist for that window; nothing is padded.
- VNEPS's search index only exposes the first 10,000 hits of any one
  filtered query. To go further back in history, narrow `dateFrom`/`dateTo`
  to a specific window rather than raising `maxResults` alone.
- The `contractor-input-result` detail endpoint returns only the winner's
  org/tax code, not its plain legal name — use a matching `list`-mode
  record's `winningContractorDisplay` field for the readable name.
- For heavier usage, Residential proxies are recommended (set by default).

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ghana
(GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP), Papua New Guinea
(NPC), Sierra Leone (NPPA), Nepal (Bolpatra), Tanzania (NeST), Eswatini
(ESPPRA), Rwanda (Umucyo), Namibia (CPBN), Trinidad & Tobago (ProcureTT),
Botswana (ministry sites), and Malawi (MANEPS/PPDA).
