# Belize BCCAR Business Registry Scraper

Search Belize's official company and business registry — BCCAR, the Belize Companies and Corporate Affairs Registry — by name, registration number, certificate number, or entity type, and get back the public registry record for every match.

## Why use this actor

- No account, login, or API key needed — BCCAR's business search is open to the public
- Search by business/company name (even a partial one), by exact registration number, or by certificate number
- Optionally filter by entity type: Company, Business Name, LLC, Foundation, or LLP
- Returns registration number, entity type and sub-type, current status, registered address, and registration date for each match
- Reliable pagination backed by BCCAR's own accurate result-count metadata — no guesswork on when a search is complete
- Automatic retries on temporary network hiccups, and automatic session refresh if BCCAR's short-lived search token expires mid-run

## How it works

1. Give the actor one or more business/company names, registration numbers, or certificate numbers to search for (and/or an entity-type filter).
2. The actor searches BCCAR's official public registry and collects every matching entity, paging through results automatically.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

A plain numeric input (e.g. `000013082`) is automatically searched as a registration number; anything else is searched as a name — you don't need to tell the actor which is which.

## Input

```json
{
  "query": "Bank",
  "queries": ["MTN"],
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single business/company name (or partial name) or exact registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `certNumbers` | array | Exact certificate numbers to search by. Only certificates issued via BCCAR's Online Business Registry System (after 28 Nov 2022) are matched — BCCAR's own limitation. |
| `entityType` | select | Optional: restrict results to one entity type (Company, Business Name, LLC, Foundation, LLP). Combine with `query`/`queries`, or leave name/registration-number fields empty to list every entity of that type. |
| `maxResultsPerQuery` | integer | Maximum matches returned per search job. Default 20, max 2000. |
| `maxConcurrency` | integer | How many search jobs to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Off by default — no anti-bot protection was found on BCCAR's public search during recon, so a direct connection works reliably. |

## Output

One record per matched entity. This is real output captured from a live run for the query `"Bank"`:

```json
{
  "_input": "Bank",
  "_source": "S1-public-business-search",
  "_scrapedAt": "2026-08-26T19:22:47Z",
  "reg_number": "000004867",
  "name": "LORDS BANK SUPERMARKET",
  "foreign_name": null,
  "business_entity_type_str": "Business Name",
  "business_entity_subtype": "Individual",
  "state": "Pending Strike off",
  "reg_address": "Belize, Belize, Lords Bank Village, 26 Lords Bank Road",
  "reg_date": "2020-12-01T00:00:00.0000000+00:00"
}
```

And for an exact registration-number search (`"000013082"`):

```json
{
  "_input": "000013082",
  "_source": "S1-public-business-search",
  "_scrapedAt": "2026-08-26T19:22:48Z",
  "reg_number": "000013082",
  "name": "BELIZE BANK INTERNATIONAL LIMITED",
  "foreign_name": "",
  "business_entity_type_str": "Company",
  "business_entity_subtype": "Private Company",
  "state": "Active",
  "reg_address": "Belize, Belize, Belize City, Suite 201, Second Floor, Belize Bank Centre, Coney Drive",
  "reg_date": "2005-07-27T00:00:00.0000000+00:00"
}
```

| Field | Description |
|---|---|
| `_input` | The query label (name, registration number, certificate number, or entity type) you requested, for traceability. |
| `_source` | Always `S1-public-business-search` for a matched entity, or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `reg_number` | BCCAR's official registration number for the entity. |
| `name` | Registered business or company name. |
| `foreign_name` | Name in a non-Latin script, where on file (empty on nearly every record). |
| `business_entity_type_str` / `business_entity_subtype` | Kind of registered entity — e.g. `Company` / `Private Company`, `Business Name` / `Individual`, or `LLP` / `Limited Liability Partnership`. |
| `state` | Current register status, e.g. `Active`, `Struck off`, `Dissolved`, `Pending Strike off`. |
| `reg_address` | Registered office/business address on file. |
| `reg_date` | Date the entity was registered. |

A record with `_error` instead of entity fields means that query didn't produce a usable result: `"not_found"` when the search matched no entity, or `"blocked_or_transient"` for a temporary network issue. For example, searching a made-up entity name:

```json
{"_input": "zzzznonexistententityxyz123", "_source": "none", "_scrapedAt": "2026-08-26T19:22:50Z", "_error": "not_found"}
```

## Notes / limits

- This is BCCAR's own public search over its full entity database — name search is a plain substring match (not fuzzy), tested against a broad query (`"LIMITED"`, 9,481 total matches) with confirmed accurate, non-duplicated pagination across pages.
- No director/shareholder/officer or document-level detail is exposed by this public search anywhere — BCCAR's own site directs deeper document/filing requests to its office by email with payment, which this actor does not automate. The fields above are BCCAR's complete free/public record shape for every entity, whether found by name, registration number, or certificate number.
- Certificate-number search (`certNumbers`) only matches certificates issued through BCCAR's Online Business Registry System after 28 Nov 2022 — this is BCCAR's own stated limitation, not a gap in this actor.
