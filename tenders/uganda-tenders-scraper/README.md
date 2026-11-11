# Uganda Government Tenders Scraper (PPDA e-GP)

Pull public government tender/procurement notices straight from Uganda's official e-Government Procurement portal — EGP Uganda, run by PPDA (the Public Procurement and Disposal of Public Assets Authority). No account, login, or API key needed to read notices.

## Why use this actor

- No account or login needed — viewing tender notices is public by law; only submitting a bid requires an account
- Get currently open tenders (accepting bids right now), or search the closed/historical archive back to 2019
- Full tender reference number, procuring entity, category, subject, published date, and submission deadline for every notice
- Optionally fetches each notice's own detail page for the untruncated subject and full invitation text
- Where available, pulls the actual bid-opening result — every bidder's name, address, submission time, and bid amount (genuine public transparency data)
- Stable JSON output suitable for pipelines, spreadsheets, or market-intelligence workflows

## How it works

1. Choose a mode: `latest` (tenders open for bidding right now), `archived` (closed/historical notices, optionally filtered by financial year), or `detail` (fetch specific notice IDs directly).
2. The actor reads the official portal's live listing table (for `latest`) or its archive API (for `archived`), then — unless you turn it off — visits each notice's own page to fill in the full subject/description and any recorded bid-opening result.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "mode": "latest",
  "maxResults": 50,
  "fetchDetails": true,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `latest` (default) = currently open notices. `archived` = closed/historical notices. `detail` = fetch specific notice ID(s). |
| `noticeIds` | array | Only used with `mode: "detail"`. Notice IDs (e.g. `390594566`) or full detail URLs. |
| `financialYear` | string | Only used with `mode: "archived"`. Restrict to one Ugandan financial year, e.g. `"2025-2026"`. Leave blank for all years. |
| `maxResults` | integer | Maximum notices returned. Default 50, max 2000. Ignored by `detail` mode. |
| `fetchDetails` | boolean | Also fetch each notice's own page for the full subject/description and bid-opening result. Default `true`. |
| `maxConcurrency` | integer | How many detail pages to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. This site has no anti-bot gate, so this is mostly a formality — residential is offered for consistency with other actors in this collection. |

## Output

One record per tender notice. This is real output captured from a live run.

**`mode: "latest"`** — a currently open notice (Uganda Civil Aviation Authority, deadline 2026-09-16):

```json
{
  "_mode": "latest",
  "_source": "S1-bid-notices-live-tab",
  "_scrapedAt": "2026-08-27T04:02:15Z",
  "notice_id": "390594566",
  "detail_url": "https://egpuganda.go.ug/index/390594566_egp",
  "procurement_ref": "UCAA/NCONS/2026-2027/00001",
  "procuring_entity": "Uganda Civil Aviation Authority",
  "category": "Non Consultancy Services",
  "subject_of_procurement": "FRAMEWORK CONTRACT FOR SUPPLY OF ELECTRICAL I...",
  "published_date": "2026-08-07",
  "deadline_date": "2026-09-16",
  "notice_type": "Request for Quotation Notice",
  "procurement_ref_detail": "UCAA/NCONS/2026-2027/00001",
  "full_subject_of_procurement": "FRAMEWORK CONTRACT FOR SUPPLY OF ELECTRICAL INSTALLATION MATERIALS LOT2-FLEXIBLE CABLES FOR THREE YEARS",
  "description": "e-GP Platform - Invitation to Bid: FRAMEWORK CONTRACT FOR SUPPLY OF ELECTRICAL INSTALLATION MATERIALS LOT2-FLEXIBLE CABLES FOR TWO YEARS\r\nYou have been invited by ______UCAA______ to submit a bid for an opportunity.\r\n... (boilerplate platform instructions, truncated here)"
}
```

**`mode: "archived"`** — a closed notice from the historical archive:

```json
{
  "_mode": "archived",
  "_source": "S1-public-bids-archived-ajax",
  "_scrapedAt": "2026-08-27T04:02:26Z",
  "id": "ID: 95488",
  "bid_id": 41098,
  "procurement_ref": "NPA/CONS/2024-2025/00006",
  "procurement_name": "National Planning Authority",
  "subject_procurement": "Other - Professional Services - Pre-feasibility, Feasibility and Investment Studies",
  "bid_security": "0",
  "bid_opening_time": "15:05",
  "bid_opening_date": "2024-09-13",
  "submission_deadline": "2024-09-13",
  "body": "e-GP Platform - Invitation to Bid: Provision of CONSULTANCY SERVICES FOR THE FEASIBILITY STUDY AND DETAILED ENGINEERING DESIGN OF KITENDE- KITOVU- NSAGU(11.3KM) ROAD AND MANYANGWA- KABUBU HCIV ROAD (7.5KM). ... (boilerplate platform instructions, truncated here)",
  "financial_year": null,
  "notice_id": "193458688",
  "detail_url": "https://egpuganda.go.ug/index/193458688_egp"
}
```

**`mode: "detail"`** with `fetchDetails` bid-opening enrichment — a closed notice that already has a recorded bid opening (real bidder + amount):

```json
{
  "notice_type": "Request for Quotation Notice",
  "procurement_ref_detail": "MoES/NCONS/2023-2024/00039",
  "full_subject_of_procurement": "Repair of MV UG 2587E Under DES",
  "description": "e-GP Platform - Invitation to Bid: ... (boilerplate platform instructions, truncated here)",
  "bid_opening_result": {
    "procurement_method": "Open Domestic",
    "bid_opening_datetime": "22 Jul 2026 at 17:54",
    "bids_received": "1",
    "bidders": [
      {
        "bidder_name_address": "EWB EAST AFRICA CONSULT LTD (PLOT 36 NTINDA AVENUE RD, Minister's Village  P.O.BOX 2064)",
        "submission_date": "2026-07-16 13:07:26",
        "amount": "46,149,800.00"
      }
    ]
  }
}
```

| Field | Description |
|---|---|
| `notice_id` / `detail_url` | Internal notice ID and its public detail page. |
| `procurement_ref` / `procurement_ref_detail` | The procuring entity's own tender reference code (e.g. `UCAA/NCONS/2026-2027/00001`). |
| `procuring_entity` / `procurement_name` | The government ministry/agency running the tender — `procurement_name` is upstream's own (slightly confusing) field name on archived records, passed through as-is. |
| `category` | Procurement category, e.g. Works, Supplies, Consultancy Services, Non Consultancy Services. |
| `subject_of_procurement` / `subject_procurement` | The tender's subject/title. The listing view truncates long subjects with "..." — see `full_subject_of_procurement` when `fetchDetails` is on. |
| `published_date` / `deadline_date` / `submission_deadline` | Key dates for the tender. |
| `notice_type` | The notice-detail page's own heading, e.g. "Request for Quotation Notice". |
| `description` / `body` | Full invitation-to-bid text. |
| `bid_opening_result` | Present only once a bid-opening event has been recorded: procurement method, opening date/time, bids received, and every bidder's name/address, submission time, and bid amount. |
| `financial_year` | Ugandan government financial year (archived records, where set by upstream). |
| `_error` / `_errorDetail` | Present instead of tender fields when a fetch failed: `not_found`, `invalid_notice_id`, or `blocked_or_transient`. |

## Notes / limits

- "Latest" reflects whatever is genuinely open for bidding right now on the official portal — this can be a small number right after a new Ugandan financial year starts (each July), which is expected behavior, not a scraping gap.
- Downloadable tender-document attachments were not found on any publicly viewable page — they appear to require the supplier login/registration flow, which is outside the scope of this actor (viewing notices is public; participating in a tender requires an account directly on PPDA's own portal).
- This actor covers Bid Notices only. The same portal also lists Disposal Notices (government asset sales) under a separate section, not covered here.
