# Zambia Government Tenders Scraper

Scrape Zambia's official government procurement portal — the Zambia Public
Procurement Authority (ZPPA) e-Government Procurement (e-GP) system. No
account, login, or API key needed to browse tenders.

## Why use this actor

- Direct access to Zambia's official government tender/procurement notices — the same portal every registered supplier uses
- **Currently-open tenders with full detail**: procuring entity, procurement method, bid submission deadline, payment terms, bid security requirements, UNSPSC classification, and more
- **A 150,000+ record historical tender/award listing** — reference numbers, procuring entities, deadlines, procurement methods, and status (evaluation/approval/awarded/cancelled) going back years
- Look up any specific tender by ID
- No login, no CAPTCHA, no paid access required for any of the above — this actor only uses ZPPA's public listings

## What this actor does NOT do

- **Keyword/date/procuring-entity search.** ZPPA's own "Current Tenders" search box is protected by a CAPTCHA this actor does not solve (no-CAPTCHA-solver policy). Use `list` mode to browse the full historical listing instead, or `latest` mode for what's open right now.
- **Full detail on already-closed tenders.** Once a tender's bid submission deadline passes, ZPPA requires a registered account to view its detail page (evaluation/award info) — the *listing* row (title, reference number, dates, status) is still returned, just not the expanded detail. See `CRAWLING_METHOD.md`.
- **Bid documents or submission.** This actor only reads public notices; it does not download tender documents or participate in bidding.

## How it works

Pick a `mode`:

1. **`latest`** (default) — the tenders currently open for bidding, each with full detail merged in.
2. **`list`** — paginates ZPPA's large historical "Opened Bid Details" table for bulk export.
3. **`detail`** — looks up one or more specific tenders by resourceId or URL.

## Input

```json
{
  "mode": "latest",
  "maxItems": 20,
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"latest"`, `"list"`, or `"detail"`. Default `"latest"`. |
| `maxItems` | integer | Max records for `latest`/`list` modes. Default 20. |
| `resourceIds` | array | `detail` mode only — numeric tender IDs, e.g. `"29201439"`. |
| `tenderUrls` | array | `detail` mode only — full tender URLs (resourceId is extracted automatically). |
| `maxConcurrency` | integer | `detail` mode only — parallel lookups. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Off by default — no anti-bot protection was found on this target. |

## Output

**`latest` mode** — one record per currently-open tender, with full detail merged in:

```json
{
  "_input": "latest",
  "_source": "S1-latest-widget-html",
  "_scrapedAt": "2026-08-27T04:00:14Z",
  "resourceId": "29201439",
  "title": "SUPPLY, DELIVERY, INSTALLATION AND COMMISSIOINING OF ICT EQUIPMENT FOR PERSONS WITH DISABILITIES",
  "publishedDateParts": ["26", "Aug", "26"],
  "detailUrl": "https://eprocure.zppa.org.zm/epps/cft/prepareViewCfTWS.do?resourceId=29201439",
  "detail": {
    "title": "SUPPLY, DELIVERY, INSTALLATION AND COMMISSIOINING OF ICT EQUIPMENT FOR PERSONS WITH DISABILITIES",
    "fields": {
      "nameOfProcuringEntity": "Zambia Information And Communications Technology Authority",
      "appReferenceNumber": "1012/16893/1552652",
      "tenderUniqueId": "5555/2/559/2026",
      "procurementType": "Goods",
      "procedure": "Open Bidding National",
      "procurementTechnique": "Invitation To Bid (ITB)",
      "evaluationMechanism": "Least Cost Selection (LCS)",
      "unspscCodes": "43210000-Computer Equipment and Accessories",
      "paymentType": "Participation Fee Required",
      "paymentAmountZmw": "1,000",
      "bidSecurityType": "Bid Securing Declaration Required",
      "deadlineForBidSubmission": "25/09/2026 10:00:00",
      "endOfClarificationPeriod": "11/09/2026 10:00:00",
      "bidOpeningDate": "25/09/2026 10:30:00",
      "dateOfPublicationInvitation": "26/08/2026 17:36:18"
      // ... more fields, varies by tender type (24-30 observed)
    },
    "rawFields": [
      {"label": "Name of Procuring Entity", "value": "Zambia Information And Communications Technology Authority"}
      // ... every field again, as exact on-site label + value pairs
    ]
  }
}
```

**`list` mode** — one record per row of ZPPA's historical tender/award table:

```json
{
  "_input": "list",
  "_source": "S1-opened-tenders-html",
  "_scrapedAt": "2026-08-27T04:00:26Z",
  "position": "1",
  "tenderTitle": "Procurement of Sc 2000 Cement with Hardener",
  "referenceNumber": "23698/2/521/2026",
  "pe": "Nitrogen Chemicals of Zambia Limited",
  "bidsSubmissionDeadline": "Wed Aug 26 16:00:00 CAT 2026",
  "procurementMethod": "Direct Bidding",
  "openedBids": "View Opened Bids",
  "openedBidsUrl": "https://eprocure.zppa.org.zm/epps/eawarding/showDetailsOpenedTender.do?resourceId=29564723",
  "awardDate": "",
  "status": "Evaluation",
  "resourceId": "29564723",
  "detailUrl": "https://eprocure.zppa.org.zm/epps/cft/prepareViewCfTWS.do?resourceId=29564723"
}
```

**`detail` mode** — same shape as `latest`'s `detail` object, one record per requested tender. A tender past its bid submission deadline returns:

```json
{
  "_input": "29564723",
  "_source": "none",
  "_scrapedAt": "2026-08-27T04:00:36Z",
  "_error": "login_required"
}
```

This is expected upstream behavior (see `CRAWLING_METHOD.md`), not a bug — ZPPA requires a registered account to view detail on tenders whose bidding has already closed.

| Field | Description |
|---|---|
| `_input` / `_source` / `_scrapedAt` | Standard envelope — see other actors in this portfolio. |
| `resourceId` | ZPPA's internal tender ID. |
| `title` / `tenderTitle` | Tender title. |
| `referenceNumber` | ZPPA's tender reference number. |
| `pe` / `fields.nameOfProcuringEntity` | The government body/parastatal running the tender. |
| `procurementMethod` / `fields.procedure` | e.g. "Direct Bidding", "Open Bidding National". |
| `status` | "Evaluation", "Approval", "Awarded", "Cancelled". |
| `fields` | Full detail-page fields (only when accessible), keyed by camelCase label. |
| `_error: "login_required"` | Detail page requires a ZPPA account — happens once bid submission has closed. |

## Data source

Zambia Public Procurement Authority (ZPPA) e-Government Procurement portal, `eprocure.zppa.org.zm`. See `CRAWLING_METHOD.md` for the full reverse-engineering writeup.
