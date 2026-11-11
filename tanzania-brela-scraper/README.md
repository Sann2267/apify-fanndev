# Tanzania BRELA Business Registry Scraper

Search Tanzania's official business and company register — BRELA (Business Registrations and Licensing Agency)'s Online Registration System (ORS) — by name or by registration/incorporation number.

## Why use this actor

- No account, login, or API key needed — the public search is open to anyone
- Search by business/company name (even a partial one) or by registration/incorporation number
- Search across business names (sole proprietorships) and companies in one call, or filter to just one type
- Returns registration status, key dates, registered address, and entity subtype for every match
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC screening
- Automatic retries on temporary network/WAF hiccups

## What this actor does NOT do

BRELA's public search only covers what its own search page calls "companies and business names which are registered in the ORS or which already completed data update / filing of annual return." A small share of very old records may not show up. More importantly: **directors, shareholders, and beneficial ownership are not exposed by the free public search at all** — BRELA gates that behind a paid "Request for a custom search result" e-service that requires a registered ORS account. This actor only uses the free, public, anonymous path, so those fields are simply not available here — that's a limitation of what BRELA publishes for free, not a gap in this actor.

## How it works

1. Give the actor one or more business/company names (or registration numbers) to search for.
2. The actor queries BRELA's public search API directly (no browser needed).
3. Every matching record streams into your dataset — one row per match.

## Input

```json
{
  "queries": ["Vodacom", "Tanzania Breweries", "632660"],
  "entityType": "any",
  "maxResultsPerQuery": 50,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single business/company name (or partial name) or registration/incorporation number to search for. |
| `queries` | array | Multiple names/numbers to search for in one run. |
| `entityType` | string | Restrict results to `business` (sole proprietorship), `company`, or `any` (default, searches both). |
| `maxResultsPerQuery` | integer | Maximum matched records returned per query. Default 50, max 500. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. Real output for a company search:

```json
{
  "_input": "Vodacom",
  "_source": "S1-ors-searchresult",
  "_scrapedAt": "2026-08-26T19:27:55Z",
  "id": 262227,
  "last_change_tracking_no": "G260410-4893",
  "cert_number": "38501",
  "reg_date": "1999-12-15",
  "incorporation_date": "1999-12-15",
  "legal_name": "VODACOM TANZANIA PUBLIC LIMITED COMPANY",
  "subtype_name": "Public company Limited by shares",
  "company_subtype": "CMP_PUB_SHR",
  "object_type": "ET-COMPANY",
  "ba_category": "BA1-489",
  "reg_status": "LES-RGC",
  "reg_status_name": "Registered",
  "address": "Dar Es Salaam, Kinondoni, Kinondoni, 14110, Ursino, Bagamoyo, 23, 23, 23",
  "cess_date": null,
  "update_date": "2026-05-18T09:46:36.25",
  "has_charges": 0
}
```

And for a business-name / registration-number search:

```json
{
  "_input": "632660",
  "_source": "S1-ors-searchresult",
  "_scrapedAt": "2026-08-26T19:25:54Z",
  "id": 653218,
  "last_change_tracking_no": "G260324-0601",
  "cert_number": "632660",
  "reg_date": "2026-02-17",
  "incorporation_date": null,
  "legal_name": "KILIMANJARO VISTA SAFARIS",
  "subtype_name": "Individual ",
  "company_subtype": "BNT-IND",
  "object_type": "ET-BUSINESS",
  "ba_category": "BA1-707",
  "reg_status": "LES-DIS",
  "reg_status_name": "Ceased",
  "address": "Arusha, Arusha CBD, Kaloleni, 23103, KALOLENI STREET NEAR BY KALOLENI HEALTH CENTRE",
  "cess_date": "2026-03-26T15:46:18.767",
  "update_date": "2026-03-26T15:46:18.767",
  "has_charges": null
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or number) you requested, for traceability. |
| `_source` | `S1-ors-searchresult` for a real match, `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `cert_number` | The public registration number (business names) or incorporation/compliance number (companies) — the number on the certificate. |
| `legal_name` | The full registered legal name on file. |
| `object_type` | `ET-BUSINESS` (business name / sole proprietorship) or `ET-COMPANY`. |
| `subtype_name` / `company_subtype` | Entity subtype, e.g. Individual, Corporation, Public/Private company Limited by shares/guarantee, Foreign company. |
| `reg_status_name` / `reg_status` | Current status (`Registered`, `Ceased`) and its internal code. |
| `reg_date` / `incorporation_date` / `cess_date` / `update_date` | Key dates on file. |
| `address` | Registered address as a single free-text string (region, district, ward, postcode, street). |
| `ba_category` | Business activity classification code, where on file. |
| `has_charges` | Whether the entity has registered charges/liens on file, where indicated. |
| `id` / `last_change_tracking_no` | BRELA's internal database ID and filing/transaction tracking code — useful for de-duplication, not public-facing identifiers. |

A record with `_error: "not_found"` means that query matched no entity in BRELA's public ORS index (it may still be a real, older registration not yet migrated to ORS). `_error: "blocked_or_transient"` means a temporary network issue — safe to retry.
