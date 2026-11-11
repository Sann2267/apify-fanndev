# Trinidad and Tobago Government Tenders Scraper (ProcureTT)

Pull government tenders, contract awards, pre-qualification notices, disposal notices, and annual procurement schedules straight from ProcureTT — Trinidad and Tobago's official public procurement notice board, run by the Office of Procurement Regulation (OPR) — no account, login, or API key needed.

## Why use this actor

- No account, login, or CAPTCHA required — every listing and every per-entry detail page is open to the public
- Five registers in one actor: **tenders** (open calls for bids, ~400 records), **awards** (already-awarded contracts with supplier name and value, ~290), **ASPPA** (annual planned-procurement schedules per public body, ~150), **pre-qualification notices** (~40), and **disposals** (surplus/asset sales, ~10)
- Every tender record carries the public body, reference number, status, submission deadline, and a direct PDF download link
- Optional detail-page enrichment for tenders/pre-qualification/disposals: precise UNSPSC "Lines of Business" codes, notice type, date of issuance, and exact submission time
- Sort by date, public body, status, value, or category, ascending or descending
- Stable JSON output suitable for market-intelligence, compliance, or bid-tracking pipelines

## How it works

1. Choose a notice type: **tenders**, **awards**, **asppa**, **prequalification**, or **disposals**.
2. The actor pages through ProcureTT's own public listing for that notice type, up to the number of records you ask for.
3. Optionally, sort the results and/or fetch each record's public detail page (tenders/prequalification/disposals only).
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "noticeType": "tenders",
  "maxItems": 50,
  "sortBy": "postedDate",
  "sortOrder": "desc",
  "fetchDetail": false,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `noticeType` | string | `tenders`, `awards`, `asppa`, `prequalification`, or `disposals`. Default `tenders`. |
| `maxItems` | integer | Maximum records to fetch. Default 50, max 5000. |
| `sortBy` | string | Column to sort by. Leave blank for the register's own default order. Valid options differ by notice type — see the input editor's dropdown for the full list; an invalid combination raises a clear error naming the valid options for your chosen `noticeType`. |
| `sortOrder` | string | `desc` (default) or `asc`. Only applies when `sortBy` is set. |
| `fetchDetail` | boolean | For `tenders`/`prequalification`/`disposals`, additionally fetch each record's public detail page (one extra request per record). Ignored for `awards`/`asppa`, which have no separate detail page upstream. Default `false`. |
| `maxConcurrency` | integer | How many pages/detail-lookups to fetch in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

### Tenders (`noticeType: "tenders"`)

Real output from a live run:

```json
{
  "_noticeType": "tenders",
  "_source": "S1-html-table",
  "_scrapedAt": "2026-08-27T05:33:25Z",
  "Public Body": "OFFICE OF THE ATTORNEY GENERAL",
  "Tender Reference No.": "ITB#5/2026",
  "Status": "Open",
  "Submission Deadline Date": "11/09/2026",
  "Description": "Supply and delivery of network switches and access points",
  "Lines of Business (Level 3)": ["43222600 Network service equipment"],
  "Tender Notice Document": {
    "text": "download",
    "url": "https://procurett.oprtt.org/index.php?gf-download=2026%2F08%2FITB-Supply-of-network-switches.pdf&form-id=5&field-id=14&entry-id=2285&hash=..."
  },
  "_entryId": "2285"
}
```

With `fetchDetail: true`, each record also carries a `_detail` object (real example — same tender):

```json
"_detail": {
  "Public Body": "OFFICE OF THE ATTORNEY GENERAL",
  "Tender Reference No.": "ITB#5/2026",
  "Notice Type": "Invitation to Bid",
  "Date of Issuance": "26/08/2026",
  "Status": "Open",
  "Notice Document": { "text": "ITB-Supply-of-network-switches.pdf", "url": "https://procurett.oprtt.org/gk-download/..." },
  "Description": "Supply and delivery of network switches and access points",
  "Lines of Business (Level 3)": ["43222600 Network service equipment"],
  "Lines of Business (Level 4)": [{ "Code": "43222612", "Name": "Network switches" }],
  "Submission Deadline Date": "11/09/2026",
  "Submission Deadline Time": "10:00 AM"
}
```

### Awards (`noticeType: "awards"`)

```json
{
  "_noticeType": "awards",
  "_source": "S1-html-table",
  "_scrapedAt": "2026-08-27T05:33:33Z",
  "Public Body": "SAN FERNANDO CITY CORPORATION",
  "Reference No.": "2460",
  "Description": "To construct reinforced concrete roadside open box drain (160m x 0.45m x 0.6m) and seven (7) driveways, each being (4m x 1m x 0.15m) (LxWxD)",
  "Supplier or Contractor Awarded": "ECO-STONE ENGINEERING & CONSTRUCTION LTD",
  "Award Value (TTD)": "254,131.88",
  "Award Date": "2026-08-14",
  "_entryId": null
}
```

### ASPPA (`noticeType: "asppa"`)

```json
{
  "_noticeType": "asppa",
  "_source": "S1-html-table",
  "_scrapedAt": "2026-08-27T05:33:35Z",
  "Public Body": "TOBAGO REGIONAL HEALTH AUTHORITY",
  "Fiscal Year": "2025/2026",
  "Posted Date": "20/08/2026",
  "ASPPA Document": { "text": "download", "url": "https://procurett.oprtt.org/index.php?gf-download=2026%2F08%2FANNUAL-SCHEDULE-OF-PLANNED-PROCUREMENT-ACTIVITIES-2026-006.pdf&..." },
  "_entryId": null
}
```

### Pre-qualification notices (`noticeType: "prequalification"`)

```json
{
  "_noticeType": "prequalification",
  "_source": "S1-html-table",
  "_scrapedAt": "2026-08-27T05:33:41Z",
  "Public Body": "CARIBBEAN AIRLINES LIMITED",
  "Posted Date": "20/08/2026",
  "Lines of Business (Level 3)": ["78111800 Passenger road transportation"],
  "Deadline Date": "28/08/2026",
  "Pre-Qualification Notice Document": { "text": "download", "url": "https://procurett.oprtt.org/index.php?gf-download=2026%2F08%2FInvitation-to-Pre-Qualify-Vehicle-Rental.pdf&..." },
  "_entryId": "2245"
}
```

### Disposals (`noticeType: "disposals"`)

```json
{
  "_noticeType": "disposals",
  "_source": "S1-html-table",
  "_scrapedAt": "2026-08-27T05:33:45Z",
  "Public Body": "TRINIDAD AND TOBAGO ELECTRICITY COMMISSION (T&TEC)",
  "Disposal Reference No.": "07_26",
  "Posted Date": "18/08/2026",
  "Closing Deadline Date": "22/09/2026",
  "Disposal Categories": ["26121500 Electrical wire", "26121600 Electrical cable and accessories"],
  "Disposal Notice Document": { "text": "download", "url": "https://procurett.oprtt.org/index.php?gf-download=2026%2F08%2FSale-Advert-07_26.pdf&..." },
  "_entryId": "2246"
}
```

A record with `_error` instead of the fields above means the run couldn't get usable data: `"not_found"` (zero rows for the requested notice type) or `"blocked_or_transient"` (a temporary network/upstream issue — the actor already retries several times before giving up).

## Notes

- All date fields are `DD/MM/YYYY` **except** `Award Date` on `awards` records, which ProcureTT renders as ISO `YYYY-MM-DD` — don't apply one date-parsing rule across every field.
- Every listing and detail page is genuinely public — there is no login-walled tier on this platform (unlike some other Caribbean/Commonwealth e-procurement systems, where a single-tender "full detail" page requires a registered-bidder account).
- On `awards`, long descriptions are occasionally `...`-truncated by ProcureTT itself with no detail page to recover the full text — that's the source's own limitation, not a parsing gap.
- `fetchDetail` only applies to `tenders`, `prequalification`, and `disposals` — `awards` and `asppa` have no separate detail page upstream, and the flag is silently ignored (with a log warning) for those.
- `_entryId` is ProcureTT's own internal Gravity Forms record id — present (and stable across runs) for `tenders`/`prequalification`/`disposals`, and `null` for `awards`/`asppa` since those two views render no entry-detail link at all.
