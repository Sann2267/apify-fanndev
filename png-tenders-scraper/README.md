# Papua New Guinea Government Tenders Scraper

Get Papua New Guinea's official government tenders, asset-disposal notices, and awarded-contract records straight from the National Procurement Commission (NPC) — reference numbers, closing dates, procuring agencies, contract values, suppliers, and PDF advert links.

## Why use this actor

- No account, login, or API key needed — every record this actor reads is public
- Three record types in one run: currently **open tenders**, **disposal-of-state-assets** notices (government selling vehicles/equipment by sealed bid), and **awarded contracts** (who won, for how much)
- Disposals and awarded contracts are pulled from NPC's full historical register, not just the latest page
- Direct PDF links to the original tender advert / disposal notice, where NPC publishes one
- Stable JSON output suitable for pipelines, spreadsheets, or market-intelligence workflows
- Automatic retries on temporary network hiccups

## How it works

1. Pick which record type(s) you want — or leave it on "All" to get open tenders, disposals, and contracts together.
2. For disposals and contracts, the actor pages through NPC's full public register, then visits each record's own page to pull the details (agency, dates, contract value, supplier, PDF link).
3. For open tenders, the actor reads NPC's tender advertisement page directly — this is the entire list of currently open tenders NPC itself shows (see "Known limits" below).
4. Everything streams into your dataset as it's found.

## Input

```json
{
  "mode": "all",
  "maxResultsPerType": 100,
  "fetchDetails": true,
  "maxConcurrency": 5,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `all` (default), `tenders`, `disposals`, or `contracts`. |
| `maxResultsPerType` | integer | Applies to `disposals`/`contracts` only (both fully paginated on the source). Default 100, max 500. Open tenders always return everything the source page currently shows. |
| `fetchDetails` | boolean | For `disposals`/`contracts`, fetch each record's own page for agency/dates/value/supplier/PDF. Turn off for a faster run returning just title/link/date. Default `true`. |
| `maxConcurrency` | integer | How many detail pages to fetch in parallel per type. Default 5. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Open tender** (`mode: "tenders"` or `"all"`) — one record per currently open tender. Real output, 2026-08-27:

```json
{
  "_input": "(open tenders)",
  "_source": "S1-tender-advertisement-html",
  "_scrapedAt": "2026-08-27T04:04:24Z",
  "record_type": "tender_notice",
  "source_url": "https://npc.gov.pg/tender-advertisement/",
  "post_id": "265",
  "reference_number": "NPC/2026-26",
  "title": "Electronic Government Procurement (e-GP)",
  "description": "Supply, Installation and Support of Electronic Government Procurement System for Tendering, Contract Lifecycle Management, Marketplace and Catalogues, Data Warehouse and Reporting System for the Government of the Independent State of Papua New Guinea",
  "closing_date": "June 30, 2026 5:00 pm",
  "pdf_url": "https://npc.gov.pg/wp-content/uploads/2026/06/NPC-2026-26.pdf"
}
```

**Disposal notice** (`mode: "disposals"` or `"all"`) — real output:

```json
{
  "_input": "disposals-notice",
  "_source": "S2-detail-html",
  "_scrapedAt": "2026-08-27T04:06:53Z",
  "id": 3596,
  "record_type": "disposals-notice",
  "title": "Disposal of Vehicles for National Judicial Staff Services (NJSS)",
  "slug": "disposal-of-vehicles-for-national-judicial-staff-services-njss",
  "link": "https://npc.gov.pg/disposals-notice/disposal-of-vehicles-for-national-judicial-staff-services-njss/",
  "date": "2026-06-10T11:04:48",
  "fields": {
    "Project Name": "Disposal of Vehicles for National Judicial Staff Services (NJSS)",
    "Department/Agency": "National Judicial Staff Services (NJSS)",
    "Closing Date": "June 5, 2026",
    "Pre-Inspection Date": "5th June, 2026 (10:00 am – 2:00 pm)"
  },
  "pdf_url": "https://npc.gov.pg/wp-content/uploads/2026/06/DSA-2026-08.pdf"
}
```

**Awarded contract** (`mode: "contracts"` or `"all"`) — real output:

```json
{
  "_input": "contracts-awarded",
  "_source": "S2-detail-html",
  "_scrapedAt": "2026-08-27T04:05:36Z",
  "id": 1513,
  "record_type": "contracts-awarded",
  "title": "Short Form – Motor Vehicles, parts and buses",
  "slug": "short-form-motor-vehicles-parts-and-buses-12",
  "link": "https://npc.gov.pg/contract-awarded/short-form-motor-vehicles-parts-and-buses-12/",
  "date": "2024-04-08T04:50:21",
  "fields": {
    "Contract Name": "Short Form - Motor Vehicles, parts and buses",
    "Agency": "Department of Police",
    "Method for Procurement": "Direct Selection",
    "Contract Start Date": "Not Available",
    "Nature of Goods, Services, or Works Procured": "Motor Vehicles including parts  - passender vehicles, water police boats and buses",
    "Contract Value Inc GST (PGK Unless Specified)": "9,674,293.69",
    "Supplier Name": "Boroko Motors"
  },
  "pdf_url": null
}
```

`fields` holds every labeled field NPC published on that record's own page, kept exactly as written (label text and formatting vary slightly between records — this actor doesn't force them into fixed columns).

## Known limits

- **Open tenders are capped at whatever NPC currently shows on its tender-advertisement page** (observed: 6 at any given time). NPC's own site gives visitors no way to browse tenders it has already taken down — this actor can't retrieve what NPC itself doesn't expose. See `CRAWLING_METHOD.md` for the full investigation.
- `contracts-awarded` records never carry a PDF — NPC doesn't publish one for awarded contracts.
- Field labels (e.g. `Closing Date` vs `CLOSING DATE & TIME`) are kept exactly as NPC wrote them and differ slightly between record types.

## Support

Found an issue or have a request? Reach out and it'll get fixed.
