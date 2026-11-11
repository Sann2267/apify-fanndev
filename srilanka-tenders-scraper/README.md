# Sri Lanka Government Tenders Scraper (Treasury / Ministry of Finance)

Scrapes official Sri Lanka government procurement notices published by the Ministry of Finance, Planning and Economic Development — currently open tenders from government departments (Customs, Excise, State Accounts, IT Management, and more), plus a full historical archive going back to 2018. No account or login needed.

## Why use this actor

- Pulls from Sri Lanka's real, official Treasury procurement notice board — not a third-party tender-alert aggregator
- Two views in one actor: **currently open notices** (updated multiple times a week) and a **historical archive** of 460+ past notices
- Every notice includes its bidding documents, addenda, and other attachments as direct download links
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: `latest` for what's open right now, or `archive` to browse historical notices.
2. Set how many results you want (`maxResults`) — for `archive`, the actor automatically works through as many pages as needed.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage pagination or retries — the actor handles all of it.

## Input

**Latest open notices (default):**
```json
{
  "mode": "latest",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Browse the historical archive:**
```json
{
  "mode": "archive",
  "maxResults": 50,
  "archiveStartPage": 1,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"latest"` (default) — notices currently open. `"archive"` — historical notices. |
| `maxResults` | integer | Max notices to return. Default 50, max 5000. `latest` is naturally capped at whatever is currently posted (~20); `archive` will fetch as many pages as needed to reach this count. |
| `archiveStartPage` | integer | `mode: "archive"` only. Which archive page to start from — page 1 is the most recent historical notices, working backwards in time. Default 1. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "latest", "maxResults": 1}`:

```json
{
  "_input": "latest",
  "_source": "S1-current-notices",
  "_scrapedAt": "2026-08-27T06:22:59Z",
  "recordType": "TENDER_CURRENT",
  "_totalAvailable": 144,
  "id": 179,
  "title": "Department of Management Services",
  "subtitle": "Procurement of 02 Motor Car under Operational Leasing Method",
  "description": "<p>Contract No: DMS/AD/02/Vehicle Ope. Lea. /2026</p>",
  "status": true,
  "publishedOn": "Aug 24 2026, 08:40 AM",
  "updatedOn": "Aug 24 2026, 08:40 AM",
  "descriptionText": "Contract No: DMS/AD/02/Vehicle Ope. Lea. /2026",
  "attachments": [
    {
      "title": "PROCUREMENT DOCUMENT ( Volume  I ).pdf",
      "linkText": "Download Attachment",
      "downloadUrl": "https://www.treasury.gov.lk/api/file/2c909e22-bb01-4494-a0a0-a8da42700c9b"
    },
    {
      "title": "PROCUREMENT DOCUMENT (VOLUME II).pdf",
      "linkText": "Download Attachment",
      "downloadUrl": "https://www.treasury.gov.lk/api/file/8e36c7eb-0831-42ee-9506-8c33dfb4ba16"
    }
  ]
}
```

Real output for `{"mode": "archive", "maxResults": 1}`:

```json
{
  "_input": "archive:page1",
  "_source": "S1-archive",
  "_scrapedAt": "2026-08-27T06:23:16Z",
  "recordType": "TENDER_ARCHIVE",
  "_page": 1,
  "_totalAvailable": 460,
  "id": "20210610004",
  "label": "Ministry of Health",
  "descriptionHtml": "<h3>State Pharmaceuticals Corporation of Sri Lanka</h3><h4>PFD Ref. ProcuNotice20210610004</h4>... 4 more paragraphs",
  "descriptionText": "State Pharmaceuticals Corporation of Sri Lanka PFD Ref. ProcuNotice20210610004 04 Separate Procurements 1. Colibri Battery Operated power Drill... Closing Date & Time: 16.07.2021 At 9.00 am",
  "attachments": [
    {
      "title": "Notice",
      "linkText": "Download Archive",
      "downloadUrl": "https://www.treasury.gov.lk/documents/procurement/notices/1/0-1/ProcuNotice20210610004.zip"
    }
  ]
}
```

A blocked or failed request produces one error record instead:

```json
{
  "_input": "latest",
  "_source": "none",
  "_scrapedAt": "2026-08-27T03:57:28Z",
  "_error": "blocked_or_transient",
  "_errorDetail": ""
}
```

| Field | Description |
|---|---|
| `_input` | `"latest"` for current notices, or `"archive:page<N>"` for archive records/errors. |
| `_source` | Which view the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on failed records. |
| `recordType` | `TENDER_CURRENT` or `TENDER_ARCHIVE`. |
| `_totalAvailable` | Total notices the site reports for this view. |
| `_page` | Archive mode only — which archive page this record came from. |
| `title` / `label` | The government department or ministry that posted the notice. |
| `subtitle` / `descriptionText` | The notice's title and full text content. |
| `attachments` | Bidding documents, addenda, and notices — each with a direct download link. |

## Notes

- The historical archive is large (460+ entries back to January 2019) — start with a small `maxResults` to preview before scraping in bulk.
- A handful of the oldest archive attachments (2021 and earlier) are no longer hosted and their download link may return a not-found error — the notice details themselves are still accurate and complete.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how this was confirmed as a genuine official government source.
