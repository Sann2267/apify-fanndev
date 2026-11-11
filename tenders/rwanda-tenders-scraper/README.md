# Rwanda Government Tenders Scraper (UMUCYO e-GP)

Pull public government tender/procurement notices straight from Rwanda's official e-Government Procurement portal — UMUCYO, run by the Rwanda Public Procurement Authority (RPPA). No account, login, or API key needed to read notices.

## Why use this actor

- No account or login needed — viewing and searching tender notices is fully public; only submitting a bid or registering as a supplier/procuring entity requires an account
- Search or browse 38,000+ tender notices, from brand-new to over a decade old (back to the 2016-2017 financial year)
- Filter by tender type (Goods/Works/Services/Consultant), method (national/international), status, procuring entity, tender name/number, or date range
- Optionally fetches each tender's own detail page for the full field set — procuring entity, brief description, deadline, opening date/place, tender fee, security requirements, local-preference margin, and downloadable-document metadata
- Unfiltered results are newest-first, so a plain run already works as a "latest tenders" feed
- Stable JSON output suitable for pipelines, spreadsheets, or market-intelligence workflows

## How it works

1. Choose a mode: `list` (browse/search the notice listing) or `detail` (fetch specific tenders directly by their `detail_ref`).
2. Optionally narrow `list` mode with filters (tender type, method, status, entity name, tender name/number, date range).
3. Unless you turn it off, the actor also visits each tender's own detail page to fill in the full field set and attachment list.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "mode": "list",
  "maxResults": 50,
  "fetchDetails": true,
  "tenderType": "",
  "tenderMethod": "",
  "tenderStatus": "",
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `list` (default) = browse/search notices. `detail` = fetch specific tender(s) by `detail_ref`. |
| `detailRefs` | array | Only used with `mode: "detail"`. One or more `"tendReferNo\|tendStageCd\|tendTypeCd"` strings, exactly as emitted in the `detail_ref` field of `mode: "list"` output. |
| `maxResults` | integer | Maximum notices returned. Default 50, max 2000. Ignored by `detail` mode. |
| `fetchDetails` | boolean | Also fetch each notice's own detail page (full field set + attachments). Default `true`. |
| `tenderType` | string | Filter: `G` Goods, `C` Consultant Services, `NC` Non Consultant Services, `W` Works. Blank = all. |
| `tenderMethod` | string | Filter: `NCB` National Competitive Bidding, `ICB` International Competitive Bidding. Blank = all. |
| `tenderStatus` | string | Filter: `ADV`/`OPE`/`EVA`/`SIG`/`CAN`/`A`. Blank = all. Note: `SIG` (Signed Contract) returns no data — award/evaluation results aren't exposed on this endpoint. |
| `procuringEntityName` | string | Free-text filter on the procuring entity name. |
| `tenderName` | string | Free-text filter on the tender name/title. |
| `tenderNo` | string | Filter by tender reference number. |
| `invitationDateFrom` / `invitationDateTo` | string | Restrict to notices advertised within a date range, format `dd/MM/yyyy`. |
| `maxConcurrency` | integer | How many detail pages to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. This site has no anti-bot gate, so this is mostly a formality — residential is offered for consistency with other actors in this collection. |

## Output

One record per tender notice. This is real output captured from a live run (`mode: "list"`, `fetchDetails: true`) — a currently-open tender from Rwanda Capital Market Development, deadline 2026-09-30:

```json
{
  "_mode": "list",
  "_source": "S1-advertising-list-gu",
  "_scrapedAt": "2026-08-27T05:35:26Z",
  "tender_name": "Framework contract for Technical support to implement CMA's Investor Education strategy",
  "tender_no": "000001/NC/NCB/2026/2027/R-CAMD",
  "tend_refer_no": "000001/NC/NCB/2026/2027/1207000001",
  "tend_stage_cd": "O",
  "tend_mthod_cd": "NCB",
  "tend_type_cd": "NC",
  "status_cd": "P",
  "status": "Published",
  "advertising_date": "26/08/2026",
  "deadline_of_submitting": "30/09/2026 15:00",
  "planned_open_date": "30/09/2026 15:30",
  "stage_type": "one stage",
  "detail_ref": "000001/NC/NCB/2026/2027/1207000001|O|NC",
  "detail_page_heading": "View Details of One Stage Advertising (Services)",
  "fields": {
    "Tender No": "000001/NC/NCB/2026/2027/R-CAMD",
    "Procurement Plan Name": "Technical support to implement CMA's Investor Education strategy",
    "Advertising/Procuring Entity": "Rwanda Capital Market development",
    "Tender Name": "Framework contract for Technical support to implement CMA's Investor Education strategy",
    "Tender Type": "Non Consultant Services",
    "Tender Method": "National Competitive Bidding",
    "International/National": "NATIONAL",
    "Bid Validity Period": "120 Days",
    "Brief Description": "Framework contract for technical support to implement CMA's Investor Education strategy",
    "Deadline for Bids Submission": "30/09/2026 15:00 (local time)",
    "Opening Date": "30/09/2026 15:30 (local time)",
    "Opening Place": "e-Procurement system",
    "How to Obtain Tender Document": "Downloadable Online",
    "Tender Fee": "10,000",
    "Tender Security": "Yes",
    "Tender Security (sum of LOTs)": "7,091,985.6",
    "Local preference": "Yes",
    "Margin of Preference": "15%",
    "... 3 more fields": "..."
  },
  "attachments": [
    {
      "file_id": "082026114339140-7fb9",
      "file_name": "TENDER CMA Support to strategy education.doc",
      "document_name": "Tender Document",
      "upload_date": "25/08/2026 11:43"
    },
    {
      "file_id": "082026115403709-7fb4",
      "file_name": "Beneficial Ownership Disclosure Declarationform (2) (1).xlsx",
      "document_name": "Beneficial ownership form",
      "upload_date": "25/08/2026 11:54"
    }
  ],
  "raw_text": "View Details of One Stage Advertising (Services) General Information Tender No 000001/NC/NCB/2026/2027/R-CAMD ... (full page text, truncated here)"
}
```

| Field | Description |
|---|---|
| `tender_name` / `tender_no` | Tender title and its human-readable reference number (as shown in the listing). |
| `tend_refer_no` / `tend_stage_cd` / `tend_type_cd` | Internal codes needed to fetch this tender's detail page — combined into `detail_ref`. |
| `status` / `status_cd` | Human-readable status (e.g. "Published") and its one-letter internal code. |
| `advertising_date` / `deadline_of_submitting` / `planned_open_date` | Key dates for the tender. |
| `stage_type` | "one stage" or "two stage" procurement process. |
| `detail_ref` | Pass this exact string back in `detailRefs` under `mode: "detail"` to re-fetch this tender's full detail directly. |
| `detail_page_heading` | The detail page's own heading, e.g. "View Details of One Stage Advertising (Services)". |
| `fields` | Every upstream label/value pair from the detail page (varies by tender type — Goods/Works/Services/Consultant each expose a slightly different field set). |
| `attachments` | Downloadable tender-document metadata (name, upload date, internal file id) — file contents are not downloaded. |
| `raw_text` | Full plain-text dump of the detail page, as a fallback for older template variants whose key info isn't in the labeled `fields` table. |
| `_error` / `_errorDetail` | Present instead of tender fields when a fetch failed: `invalid_detail_ref` or `blocked_or_transient`. |

## Notes / limits

- Unfiltered `mode: "list"` runs are ordered newest-advertised-first, so this actor doubles as a "latest tenders" feed without needing a separate mode.
- Contract-award / bid-evaluation-result data (status "Signed Contract") returns no data on this listing endpoint — not covered by this actor.
- Attachment *file contents* are not downloaded, only their metadata (name, upload date, id) — the download action is JS-driven and outside the scope of a login-free HTTP scraper.
