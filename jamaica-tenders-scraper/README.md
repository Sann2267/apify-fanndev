# Jamaica Government Tenders Scraper (GOJEP)

Pull government call-for-tenders and contract-award notices straight from GOJEP, Jamaica's official Government Electronic Procurement portal — no account, login, or API key needed.

## Why use this actor

- No account, login, or CAPTCHA required — the tender listings themselves are open to the public (only downloading the full bid documents requires a registered-bidder login, which this actor doesn't need)
- Two data sets in one actor: **opened bid details** (currently open tenders plus a multi-year historical archive — roughly 80,000 records) and **contract award notices** (already-awarded contracts, each with a downloadable PDF — roughly 13,000 records)
- Every record carries reference number, title, procuring entity (the ministry/agency running it), procurement method, and dates
- Optional bidder/supplier list per tender (who bid, and their disclosed amount) with one extra click of a switch
- Sort by deadline, procuring entity, title, or amount, ascending or descending
- Stable JSON output suitable for market-intelligence, compliance, or bid-tracking pipelines

## How it works

1. Choose a notice type: **opened bid details** (open + historical tenders) or **contract award notices** (already-awarded contracts).
2. The actor pages through GOJEP's own public listing for that notice type, up to the number of records you ask for.
3. Optionally, sort the results and/or fetch each tender's public bidder list.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "noticeType": "opened",
  "maxItems": 50,
  "sortBy": "submissionDeadline",
  "sortOrder": "desc",
  "includeBidders": false,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `noticeType` | string | `opened` (open + historical calls for tenders) or `awarded` (contract award notices). Default `opened`. |
| `maxItems` | integer | Maximum records to fetch (10 per page upstream). Default 50, max 5000. |
| `sortBy` | string | Column to sort by. Leave blank for the register's own default order. `opened` supports `title`, `referenceNumber`, `procuringEntity`, `submissionDeadline`, `procedure`, `status`, `awardDate`; `awarded` supports `procuringEntity`, `title`, `contractAmount`, `datePublished`. |
| `sortOrder` | string | `desc` (default) or `asc`. Only applies when `sortBy` is set. |
| `includeBidders` | boolean | For `opened` records, additionally fetch each tender's public bidder/supplier list (one extra request per record). Default `false`. |
| `maxConcurrency` | integer | How many pages/bidder-lookups to fetch in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

### Opened bid details (`noticeType: "opened"`)

Real output from a live run, sorted by `submissionDeadline` descending:

```json
{
  "_noticeType": "opened",
  "_source": "S1-opened-bid-details",
  "_scrapedAt": "2026-08-27T04:12:06Z",
  "resourceId": "9406343",
  "title": "Downtown Kingston Business Improvement District - EOI",
  "referenceNumber": "1360/263",
  "procuringEntity": "Jamaica Social Investment Fund",
  "description": "The Consultancy is to review and design the governance model required for a Downtown Kingston Business Improvement District, or a similar professionally managed entity, to ensure sustainable operations and maintenance (OandM) of the proposed Kingston Waterfront Park and areas within the future defined boundaries of the Bid.",
  "submissionDeadline": "03/09/2026 12:00:00",
  "procedure": "International Competitive Bidding (ICB)",
  "status": "Bid submission",
  "openedBidsUrl": "/epps/eawarding/showDetailsOpenedTender.do?resourceId=9406343",
  "tenderOpeningRecord": null,
  "awardDate": null,
  "estimatedContractValue": null,
  "listRank": "1"
}
```

With `includeBidders: true`, each record also carries a `bidders` array (real example — a Kingston waterfront consultancy EOI that drew 14 international bidders):

```json
"bidders": [
  { "envelope": "Single", "supplierName": "Trevor Hamilton and Associates", "bidId": "184332", "financialValueJMD": "-" },
  { "envelope": "Single", "supplierName": "KPMG", "bidId": "184317", "financialValueJMD": "-" },
  { "envelope": "Single", "supplierName": "A.R.S Progetti S.P.A", "bidId": "184265", "financialValueJMD": "-" }
  // ... 11 more
]
```

`financialValueJMD` is often `"-"` (sealed/undisclosed) — that's GOJEP's own data, not a parsing gap.

| Field | Description |
|---|---|
| `resourceId` | GOJEP's internal id. The full detail page it links to requires a registered-bidder login — not fetched by this actor. |
| `title` | Tender title as published. |
| `referenceNumber` | GOJEP's own tender reference number, e.g. `1360/263`. |
| `procuringEntity` | The government ministry/agency running this tender. |
| `description` | Free-text tender description; `null` when GOJEP didn't publish one. |
| `submissionDeadline` | Bid submission deadline, **DD/MM/YYYY HH:MM:SS** (day first — not U.S. month-first), Jamaica local time, as displayed by GOJEP. |
| `procedure` | Procurement method, e.g. `International Competitive Bidding (ICB)`, `Direct Bidding`, `Single Source (SS)`. |
| `status` | e.g. `Bid submission` (currently open), `Evaluation`, `For archival`. |
| `openedBidsUrl` | Link to this tender's public bidder list. Set `includeBidders: true` to fetch it inline instead. |
| `awardDate` | Date the tender was awarded, when disclosed. |
| `estimatedContractValue` | Rarely populated on the source register. |
| `listRank` | Row position in this run's result set (see Notes). |

### Contract award notices (`noticeType: "awarded"`)

```json
{
  "_noticeType": "awarded",
  "_source": "S2-contract-award-notices",
  "_scrapedAt": "2026-08-27T04:02:50Z",
  "resourceId": "3226176",
  "procurementMethod": "National Competitive Bidding (NCB)",
  "procuringEntity": "National Water Commission",
  "title": "The Supply and Delivery of 100mm and 200mm Nom. Dia Ductile Iron Pipes and Associated Fittings for NWC's In-House Priority Projects",
  "contractAmount": "22,872,982.50",
  "datePublished": "26/08/2026 18:29:13",
  "noticePdfUrl": "/epps/notices/downloadNoticeForES.do?resourceId=10324899&noticeType=prompt.f306.contract&lang=EN",
  "listRank": "1"
}
```

| Field | Description |
|---|---|
| `procurementMethod` | e.g. `National Competitive Bidding (NCB)`, `Restricted Bidding (RB)`. |
| `procuringEntity` | The government ministry/agency that awarded this contract. |
| `title` | Contract/tender title. |
| `contractAmount` | Awarded amount as published (currency not always stated by GOJEP on this column — cross-check against the PDF for large amounts). |
| `datePublished` | Publish date/time of the award notice, DD/MM/YYYY HH:MM:SS. |
| `noticePdfUrl` | Direct, no-login download link to the official Contract Award Notice PDF. Prefix with `https://www.gojep.gov.jm` to get a full URL. |

A record with `_error` instead of the fields above means the run couldn't get usable data: `"not_found"` (zero rows for the requested notice type) or `"blocked_or_transient"` (a temporary network/upstream issue — the actor already retries several times before giving up).

## Notes

- `submissionDeadline`, `awardDate`, and `datePublished` are day-first (`DD/MM/YYYY`) as GOJEP renders them for this actor's client — don't misread `03/09/2026` as March 9; it's 3 September.
- `listRank` continues incrementing across pages (1, 2, 3, ...) when you set `sortBy`; it may restart at 1 each page under the register's own default order. It's a within-run position, not a stable cross-run id — use `resourceId` for that.
- The "opened bid details" register is both a live feed of currently-open tenders (`status: "Bid submission"`) and a running historical archive going back years (`status: "For archival"`) — set `sortBy: "submissionDeadline", sortOrder: "desc"` for the newest activity, or leave it unsorted to browse the register's own order.
- `includeBidders` adds one request per tender fetched — leave it off for large `maxItems` runs unless you need the bidder detail.
- This actor does not fetch the login-walled full call-for-tenders detail page (bid documents, full evaluation criteria) — that requires a registered-bidder GOJEP account, which is out of scope.
