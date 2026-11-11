# Zimbabwe Government Tenders Scraper

Scrape Zimbabwe's official government procurement portal — the Procurement
Regulatory Authority of Zimbabwe (PRAZ) electronic Government Procurement
(eGP) System. No account, login, or API key needed to browse tenders or
award notices.

## Why use this actor

- Direct access to Zimbabwe's official government tender/procurement notices — the same portal every registered supplier uses
- **Currently-open tenders with full detail**: procurement method, funding source, bid security amounts, delivery location, line-item breakdown, and more
- **A 64,000+ record historical tender archive** going back to 2024 — reference numbers, procuring entities, deadlines, and status (closed/awarded/cancelled)
- **Recent award notices with real contract values** — awardee name, address, contact person, contract amount, and line-item breakdown
- Look up any specific tender or award by ID
- No login, no CAPTCHA, no paid access required for any of the above — this actor only uses PRAZ's public listings

## What this actor does NOT do

- **Keyword/date/procuring-entity search.** All three listings have a search form on the site, but it submits via POST and this actor does not replicate it (see `CRAWLING_METHOD.md`). Use `former` mode to browse/export the full historical archive instead.
- **Full historical Award Notices.** The Award Notices board's own pagination is a confirmed no-op on PRAZ's side — only the ~100 most recent awards are reachable (see `CRAWLING_METHOD.md`). This is a site limitation, not something this actor can work around without solving a POST-based search.
- **Document downloads.** This actor reads the structured notice/award data; it does not download attached PDF/DOCX tender documents or participate in bidding.

## How it works

Pick a `mode`:

1. **`latest`** (default) — tenders currently open for bidding, from the "Live Tenders" bulletin board.
2. **`former`** — PRAZ's large "Former Opportunities" (Past Tenders) archive, for bulk export.
3. **`awards`** — recent "Award Notices" (awardee + contract amount), capped at the site's own most-recent ~100.
4. **`detail`** — looks up one or more specific tenders and/or award notices by ID or URL.

For `latest`/`former`/`awards`, set `fetchDetails: true` (default) to merge in each item's full detail page (all labeled fields plus any line-item breakdown table).

## Input

```json
{
  "mode": "latest",
  "maxItems": 20,
  "fetchDetails": true,
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"latest"`, `"former"`, `"awards"`, or `"detail"`. Default `"latest"`. |
| `maxItems` | integer | Max records for `latest`/`former`/`awards` modes. Default 20. |
| `fetchDetails` | boolean | For `latest`/`former`/`awards`: also fetch each item's full detail page. Default `true`. |
| `tenderIds` | array | `detail` mode only — numeric tender IDs (e.g. `"46190"`) or full `viewLiveTenderDetails` URLs. |
| `awardIds` | array | `detail` mode only — numeric award notice IDs (e.g. `"8501"`) or full `viewAwardNotice` URLs. |
| `maxConcurrency` | integer | Parallel detail-page lookups. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Off by default — no anti-bot protection was found on this target. |

## Output

**`latest` mode** — one record per currently-open tender, with full detail merged in:

```json
{
  "_input": "latest",
  "_source": "S1-live-tenders-html",
  "_scrapedAt": "2026-08-27T06:30:23Z",
  "tenderId": "46190",
  "tenderReferenceNumber": "ZETDC/INTER/28/2025",
  "tenderTitle": "Supply, Delivery, Installation and Commissioning of Filabusi 30MVA 88/11 KV Transformer and Associated Bay Equipment",
  "requiredSupplierCategoryCode": "GE001",
  "requiredSupplierCategoryName": "Electrical Products: Cables and Materials, Power Back-Up Equipment, Transformers, Standby Generators, Consumables & Accessories",
  "procuringEntity": "ZIMBABWE ELECTRICITY TRANSMISSION AND DISTRIBUTION COMPANY",
  "scope": "Open",
  "publishDate": "13-Dec-2025 06:00 AM",
  "closingDate": "08-Sep-2026 10:00 AM",
  "detail": {
    "fields": {
      "procurementMethod": "Competitive Bidding Method",
      "classOfProcurement": "Goods",
      "fundingSource": "Internally Generated Funds",
      "deliveryProjectLocation": "ZETDC FILABUSI 88KV SUBSTATION",
      "bidSecurityAmountDomestic": "25000",
      "bidSecurityAmountInternational": "25000",
      "tenderAddendums": "6",
      "numberOfDownloads": "53"
      // ... 20+ more fields, varies by tender type
    },
    "rawFields": [
      {"label": "Procurement Method", "value": "Competitive Bidding Method"}
      // ... every field again, as exact on-site label + value pairs
    ]
  }
}
```

**`former` mode** — one record per row of PRAZ's historical tender archive:

```json
{
  "_input": "former",
  "_source": "S1-former-tenders-html",
  "_scrapedAt": "2026-08-27T06:35:02Z",
  "tenderId": "1",
  "tenderReferenceNumber": "PRAZ/DOM/01/2024",
  "tenderTitle": "Supply and delivery of corporate gifts",
  "procuringEntity": "PROCUREMENT REGULATORY AUTHORITY OF ZIMBABWE",
  "publishDate": "02-Mar-2024 05:15 PM",
  "closingDate": "26-Mar-2024 10:00 AM",
  "status": "Closed",
  "summaryReportUrl": "https://egp.praz.org.zw/Indexes/viewSummaryReport/1"
}
```

**`awards` mode** — one record per recent award notice, with awardee and contract amount:

```json
{
  "_input": "awards",
  "_source": "S1-award-notices-html",
  "_scrapedAt": "2026-08-27T06:35:36Z",
  "awardNoticeNumber": "8501",
  "tenderId": "94214",
  "awardTitle": "PHARMACY SURGICALS CRP AUGUST",
  "awardee": "AGVITO INVESTMENT (PRIVATE) LIMITED",
  "awardDate": "26-Aug-2026",
  "detail": {
    "fields": {
      "contractAmount": "US$ 4,090.00",
      "address": "13 Tredgold Drive Lincoln Green Belvedere Harare, Harare, Harare, Zimbabwe",
      "awardeeContactPerson": "KAUSHAAL VORA",
      "reasonForAward": "Compliance with RFQ requirements"
    },
    "lineItems": [
      {"itemNo": "1", "unspscCode": "42292301", "lotName": "Surgical bending instruments", "lotDescription": "LATEX GLOVES B/100", "quantity": "500", "uom": "Box"}
      // ... 5 more line items
    ]
  }
}
```

**`detail` mode** — same `{fields, rawFields, lineItems}` shape as the `detail` object above, one record per requested ID:

```json
{
  "_input": "99999999999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T06:41:22Z",
  "_error": "not_found",
  "_errorDetail": "No record found for id '99999999999'"
}
```

This is expected: PRAZ returns HTTP 200 with a near-empty template for a nonexistent id rather than a 404 — this actor detects that case explicitly (see `CRAWLING_METHOD.md`) instead of surfacing a confusingly blank "success".

| Field | Description |
|---|---|
| `_input` / `_source` / `_scrapedAt` | Standard envelope — see other actors in this portfolio. |
| `tenderId` / `awardNoticeNumber` | PRAZ's internal numeric identifier. |
| `tenderTitle` / `awardTitle` | Title of the tender or awarded contract. |
| `procuringEntity` / `awardee` | The government body running the tender, or the winning supplier. |
| `status` | (`former` mode) e.g. "Closed", "Awarded", "Cancelled". |
| `detail.fields` | Full detail-page fields (only when `fetchDetails=true`), keyed by camelCase label. |
| `detail.lineItems` | Item-by-item breakdown (UNSPSC code, quantity, unit of measure), when present. |
| `detailError` / `_error` | Present only on failed/degraded records — see `CRAWLING_METHOD.md` for the error-kind list. |

## Data source

Procurement Regulatory Authority of Zimbabwe (PRAZ) electronic Government Procurement System, `egp.praz.org.zw`. See `CRAWLING_METHOD.md` for the full reverse-engineering writeup.
