# Ethiopia Government Tenders Scraper

Scrape Ethiopia's official electronic Government Procurement (eGP) portal —
the system the Public Procurement and Property Administration Agency
(PPPAA) and 70+ federal agencies use to publish what they're buying. No
account, login, or API key needed.

## Why use this actor

- Direct access to Ethiopia's official government procurement register — the same data every registered supplier sees
- **The newest lots published across all agencies**, refreshed continuously (today's entries are already there)
- **A 29,000+ record register** going back years — reference numbers, procuring agencies, procurement categories/methods, fiscal years, and status
- **Item-level detail on request**: quantities, estimated unit price and currency, technical specifications, and delivery milestones with due dates
- Bilingual data (Amharic + English) passed through as-is
- No login, no CAPTCHA, no paid access required for any of the above

## What this actor does NOT do

- **Keyword search.** This actor browses and paginates; it does not offer free-text search across titles or agencies.
- **Bid documents or submission.** This actor only reads public procurement records; it does not download tender documents or participate in bidding.

## How it works

Pick a `mode`:

1. **`latest`** (default) — the most recently published procurement lots, newest first.
2. **`list`** — paginates the full register for bulk export, optionally scoped to one fiscal year.
3. **`detail`** — looks up full item-level information for one or more specific lots.

## Input

```json
{
  "mode": "latest",
  "maxItems": 20,
  "fiscalYearId": "",
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"latest"`, `"list"`, or `"detail"`. Default `"latest"`. |
| `maxItems` | integer | Max records for `latest`/`list` modes. Default 20. |
| `fiscalYearId` | string | Optional. Restricts `latest`/`list` to one Ethiopian fiscal year (runs July 8 – July 7) by its ID. Leave blank for all fiscal years. |
| `lotIds` | array | `detail` mode only — lot ID(s) from the `id` field of a `latest`/`list` record. |
| `maxConcurrency` | integer | `detail` mode only — parallel lookups. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Off by default — no anti-bot protection was found on this target. |

## Output

**`latest` / `list` mode** — one record per procurement lot:

```json
{
  "_input": "latest",
  "_source": "S1-cms-publication-lots-api",
  "_scrapedAt": "2026-08-27T07:53:48Z",
  "title": "Procurement of Hotel Service",
  "description": {
    "am": "Procurement of Hotel Service 5 star At Bishoftu Town ( MOR Adama )",
    "en": "Procurement of Hotel Service 5 star At Bishoftu Town ( MOR Adama )"
  },
  "organization": "Ministry of Revenue",
  "fiscalYear": "ET-FY-2019",
  "procurementCategory": "NonConsultancyServices",
  "procurementMethod": "Open",
  "id": "38874c68-7306-4698-b083-97e6b9415866",
  "referenceNumber": "MOR-NCB -G-0012-2019/Bid",
  "status": "done",
  "publicationPlan": {
    "name": { "am": "MOR Annual Procurement Plan for 2019 ET-FY", "en": "MOR Annual Procurement Plan for 2019 ET-FY" },
    "organizationName": { "am": "የገቢዎች ሚኒስቴር", "en": "Ministry of Revenue" },
    "budgetYearName": { "am": "ET-FY-2019", "en": "ET-FY-2019" },
    "status": "approved"
    // ... full parent-plan object
  }
  // ... every field the portal returns, passed through as-is
}
```

**`detail` mode** — item-level information for one requested lot:

```json
{
  "_input": "29208ca2-a834-4bb5-80cf-95d2dc62a057",
  "_source": "S1-cms-publication-lot-detail-api",
  "_scrapedAt": "2026-08-27T07:54:23Z",
  "lotId": "29208ca2-a834-4bb5-80cf-95d2dc62a057",
  "items": [
    {
      "name": { "am": "other service", "en": "other service" },
      "description": { "am": "", "en": "Building Maintenance" },
      "commodity": { "code": "200102102", "name": { "en": "other service" } },
      "quantity": 1.0,
      "unitOfMeasure": { "code": "Each", "name": { "en": "Each" } },
      "estimatedUnitPrice": 50000000.0,
      "currency": { "code": "ETB", "shortName": { "en": "Birr" } },
      "specifications": [
        { "key": "Technical Detail", "value": "Building Maintenance" }
        // ... 1 more
      ]
      // ... more item fields
    }
  ],
  "milestones": [
    { "milestoneType": "Inspection, acceptance and contract closeout", "leadTime": 25, "dueDate": "2024-10-01T00:00:00" }
    // ... more milestones
  ]
}
```

| Field | Description |
|---|---|
| `_input` / `_source` / `_scrapedAt` | Standard envelope — see other actors in this portfolio. |
| `id` | Procurement lot ID — pass into `detail` mode's `lotIds` for full item-level data. |
| `title` / `description` | Lot name/description (English shown as a convenience field; full bilingual object also included). |
| `organization` | The government agency running this procurement. |
| `referenceNumber` | The agency's own tender/bid reference number. |
| `fiscalYear` | Ethiopian fiscal year (July 8 – July 7). |
| `procurementCategory` / `procurementMethod` | e.g. "Goods"/"Works"/"NonConsultancyServices", "Open". |
| `status` | Lot status, e.g. "done". |
| `items` / `milestones` | (`detail` mode) Full item-level quantities, pricing, specifications, and delivery schedule. |

## Data source

Ethiopia's official electronic Government Procurement (eGP) portal,
`egp.gov.et`, operated by the Public Procurement and Property
Administration Agency. See `CRAWLING_METHOD.md` for the full
reverse-engineering writeup.
