# Guyana Government Tenders Scraper (NPTAB eProcure)

Pull currently advertised government tender/bid opportunities — and their full-text project advertisements — straight from **eprocure.gov.gy**, Guyana's official centralized procurement website run by the National Procurement and Tender Administration Board (NPTAB) under the Ministry of Finance. No account, login, or API key needed.

## Why use this actor

- No account, login, or CAPTCHA required — every currently-advertised opportunity and its full advertisement text is open to the public
- Two modes in one actor: **list** (every currently advertised bid opportunity) and **detail** (one project's full-text advertisement by ID)
- Each record carries the publishing ministry/agency, procurement method, bid opening date, region, and a direct download link for the official advertisement PDF
- Optional detail enrichment: full rich-text scope, bidding instructions, qualification criteria, and NPTAB/agency contact addresses for every listed opportunity
- Launched February 2026 — a genuinely modern, actively-maintained government data source, unlike many legacy Caribbean e-procurement portals

## How it works

1. Choose a mode: **list** (default) or **detail**.
2. In list mode, the actor calls NPTAB's own public API and returns every currently advertised bid opportunity — there's no pagination to work through, since this is a live "what's open right now" board, not a historical archive.
3. Optionally (`fetchDetail: true`), the actor also fetches each opportunity's full-text advertisement — background, bidding instructions, and contact details.
4. In detail mode, supply a `projectId` (e.g. from a previous list-mode run) to fetch just that one project's full advertisement directly.
5. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "mode": "list",
  "fetchDetail": false,
  "maxItems": 100,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `list` (every currently advertised opportunity) or `detail` (one project by ID). Default `list`. |
| `projectId` | string | Required when `mode: "detail"`. NPTAB's own id, e.g. `PROC-2026-00425`. |
| `fetchDetail` | boolean | In `list` mode, additionally fetch each opportunity's full-text advertisement (one extra request per record). Ignored in `detail` mode. Default `false`. |
| `maxItems` | integer | Safety cap on records returned in `list` mode. Default 100, max 5000. The upstream list is small and unpaginated (it reflects only currently-open opportunities), so this is a cap, not a real pagination control. |
| `maxConcurrency` | integer | How many detail lookups to fetch in parallel when `fetchDetail` is on. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (not actually required by this target — no WAF was found during recon — but kept as the portfolio default). |

## Output

### List mode (`mode: "list"`)

Real output from a live run:

```json
{
  "_source": "S1-json-api",
  "_scrapedAt": "2026-08-27T16:29:29Z",
  "project_id": "PROC-2026-00425",
  "project_name": "Rehabilitation and Upgrade of Mahaica Bridge to Abary Bridge Road Corridor",
  "agency": "31-Ministry of Public Works",
  "agency_logo": null,
  "procurement_method": "Open Tendered",
  "procurement_nature": "Works",
  "procurement_sub_nature": "",
  "estimated_value": 0.0,
  "current_state": "Bid Advertised",
  "advertisement_date": "2026-08-24",
  "actual_bid_opening_date": "2026-10-02",
  "projected_bid_opening_date": "2026-10-02",
  "regions": ["Region 04"],
  "advertisement_documents": [
    {
      "document_name": null,
      "document_file": "/files/SPN- P501759-CW-1.pdf",
      "document_url": "https://eprocure.gov.gy/files/SPN-%20P501759-CW-1.pdf"
    }
  ]
}
```

With `fetchDetail: true`, each record also carries a `_detail` object (real example — same project):

```json
"_detail": {
  "project_id": "PROC-2026-00425",
  "project_name": "Rehabilitation and Upgrade of Mahaica Bridge to Abary Bridge Road Corridor",
  "agency": "31-Ministry of Public Works",
  "procurement_method": "Open Tendered",
  "actual_bid_opening_date": "2026-10-02",
  "projected_bid_opening_date": "2026-10-02",
  "ad_header": "<div class=\"ql-editor read-mode\"><p style=\"text-align:center\"><strong>Invitation for Bids</strong></p>...",
  "ad_scope": "<div class=\"ql-editor read-mode\"><p>Employer: The Co-operative Republic of Guyana</p><p>Project: Integrated Transport Corridors Project (ITCP)</p>...",
  "ad_instruction": "<div class=\"ql-editor read-mode\"><p style=\"text-align:justify\">The Contract is expected to be completed within a period of 36 calendar months...</p>...",
  "ad_footer": "<div class=\"ql-editor read-mode\"><p style=\"text-align:justify\">All Bids must be accompanied by a: (i) Bid Security of US$2,000,000...</p><p><strong>Address 1</strong></p><p>The Permanent Secretary</p><p>Ministry of Public Works</p>...",
  "advertisement_documents": [
    {
      "document_name": null,
      "document_file": "/files/SPN- P501759-CW-1.pdf",
      "document_url": "https://eprocure.gov.gy/files/SPN-%20P501759-CW-1.pdf"
    }
  ]
}
```

### Detail mode (`mode: "detail"`, `projectId: "PROC-2026-00416"`)

```json
{
  "_source": "S1-json-api-detail",
  "_scrapedAt": "2026-08-27T16:29:43Z",
  "project_id": "PROC-2026-00416",
  "project_name": "EOI for the Design and Supervision of the National Public Health Reference Laboratory Building",
  "agency": "47-Ministry of Health",
  "procurement_method": "Open Tendered",
  "actual_bid_opening_date": null,
  "projected_bid_opening_date": "2026-08-31",
  "ad_header": "<div class=\"ql-editor read-mode\">...Invitation for Bids...</div>",
  "ad_scope": "<div class=\"ql-editor read-mode\"><p>The Government of Co-operative Republic of Guyana has received financing from the World Bank toward the cost of the One Health Project...</p></div>",
  "ad_instruction": "<div class=\"ql-editor read-mode\"><p>The detailed Terms of Reference (TOR) for the assignment can be obtained...</p></div>",
  "ad_footer": "<div class=\"ql-editor read-mode\"><p>The Address (es) referred to above are :</p>...</div>",
  "advertisement_documents": [
    {
      "document_name": "MOH (HSDU) Ad- EOI",
      "document_file": "/files/MOH(HSDU)- Request for expression of interest.pdf",
      "document_url": "https://eprocure.gov.gy/files/MOH%28HSDU%29-%20Request%20for%20expression%20of%20interest.pdf"
    }
  ]
}
```

A record with `_error` instead of the fields above means the run couldn't get usable data: `"not_found"` (zero currently advertised opportunities in list mode, or an unknown/unpublished `projectId` in detail mode) or `"blocked_or_transient"` (a temporary network/upstream issue — the actor already retries several times before giving up).

## Notes

- **This platform has no historical/awarded-contracts archive.** It's a young (launched February 2026), purpose-built "currently open opportunities" board — it surfaces only what's presently advertised, not past awards or closed notices. NPTAB's older `npta.gov.gy` site does publish a "Tenders Awarded" page, but that host is not scraped by this actor (its `robots.txt` explicitly disallows AI crawlers).
- **The current list is small and genuinely volatile by design** — it can legitimately shrink to zero records between NPTAB advertisement waves and grow again as new notices are posted. That's the source's own behavior, not a scraping gap. `maxItems` is a safety cap, not a real pagination limit.
- **Detail-mode fields are not a superset of list-mode fields** — detail drops `procurement_nature`/`estimated_value`/`current_state`/`regions` but adds four rich-text HTML fields (`ad_header`, `ad_scope`, `ad_instruction`, `ad_footer`) with the full advertisement text, including submission deadlines, qualification criteria, and NPTAB/agency contact addresses.
- `document_url` is this actor's own derived, percent-encoded, directly-downloadable link built from NPTAB's raw `document_file` path (which can contain literal unencoded spaces) — both fields are included, nothing is dropped.
- `estimated_value` and `agency_logo` were `0.0`/`null` on every record observed during testing — passed through as-is rather than omitted, since NPTAB may populate them on future notices.
