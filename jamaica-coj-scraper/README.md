# Jamaica COJ Business Registry Scraper

Search Jamaica's official company register — the Companies Office of Jamaica (COJ) — by company/business name or registration number, and pull each matching entity's registration record: status, entity type, registration date, registered address, and the officer on file.

## Why use this actor

- No account, login, or API key needed — the register is open to the public
- Search by company/business name (a partial name works too) or by registration number
- Returns registration number, current status, entity type, registration date, registered address, and one officer (director/proprietor/secretary) per match
- Covers both incorporated companies and registered business names (sole proprietorships)
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC workflows
- Automatic retries on temporary rate limits, so a run doesn't fail outright if the register briefly slows things down

## How it works

1. Give the actor one or more company/business names (or registration numbers) to search for.
2. The actor runs each search against the official register and collects every matching entity.
3. Each match's registration details — status, type, date, address, officer — are pulled straight from the register's own search results.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name or registration number format — a partial name or number works too. You don't need to manage retries or figure out the register's own search mechanics — the actor handles all of that.

## Input

```json
{
  "queries": ["GraceKennedy", "Digicel"],
  "maxResultsPerQuery": 20,
  "maxConcurrency": 2,
  "requestDelaySecs": 10,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company/business name (or partial name) or registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 200 (the register's own cap on a single search). |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 2 — keep this low, see Notes below. |
| `requestDelaySecs` | integer | Pause before each additional query starts. Default 10 seconds. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. This is real output from a live search for `GraceKennedy` (Jamaica's largest food and financial-services conglomerate), truncated to the first three of nine matches:

```json
{
  "_input": "GraceKennedy",
  "_source": "S1-companysearch",
  "_scrapedAt": "2026-08-26T18:10:51Z",
  "link": "",
  "rank": 0,
  "id": "7921-L",
  "name": "GraceKennedy Currency Trading Services Limited.",
  "office": "Kerry-Ann Heavens - Secretary",
  "status": "ACTIVE",
  "type": "COMPANY",
  "date": "26 May 1970",
  "address": " 64 Harbour Street, Kingston, Kingston, JAMAICA",
  "number": "7921 (Local)",
  "documentCount": "422"
}
```

```json
{
  "_input": "GraceKennedy",
  "_source": "S1-companysearch",
  "_scrapedAt": "2026-08-26T18:10:51Z",
  "link": "",
  "rank": 1,
  "id": "71537-L",
  "name": "GraceKennedy Financial Group Limited",
  "office": "Kerry-Ann Heavens - Secretary",
  "status": "ACTIVE",
  "type": "COMPANY",
  "date": "06 Jan 2006",
  "address": " 73 Harbour Street, , Kingston, JAMAICA",
  "number": "71537 (Local)",
  "documentCount": "449"
}
```

A registered business name (sole proprietorship) looks the same, just with a different `id`/`number` format and no `office` on file — real output for the query `Digicel`:

```json
{
  "_input": "Digicel",
  "_source": "S1-companysearch",
  "_scrapedAt": "2026-08-26T18:03:12Z",
  "link": "",
  "rank": 6,
  "id": "7874_2015-",
  "name": "DIGICEL PLAY",
  "office": "",
  "status": "Registered",
  "type": "BUSINESS",
  "date": "17 Nov 2015",
  "address": "14 Ocean Boulevard, Kingston , , Jamaica",
  "number": "7874/2015",
  "documentCount": "7"
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | `S1-companysearch` for a matched entity, or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `id` | The register's internal record id, e.g. `61230-L` (company) or `7874_2015-` (business name). |
| `name` | Registered company or business name, as filed. |
| `number` | Formatted registration number, e.g. `61230 (Local)`, `1057 (Overseas)`, or `7874/2015` for a business name. |
| `status` | Current register status, e.g. `ACTIVE`, `REMOVED`, `Registered`, `In BO Sanction Process`. |
| `type` | `COMPANY` or `BUSINESS` (a registered business name). |
| `date` | Registration/incorporation date, as shown by the register. |
| `address` | Registered office / business address on file. |
| `office` | A single director/proprietor/secretary name and role, when one is on file — empty otherwise. |
| `documentCount` | Number of documents on file for this entity (not fetched by this actor). |
| `rank` | The register's own result ordering. |

A record with `_error` instead of the fields above means that query didn't produce a usable result: `"not_found"` when the search matched no entity, or `"blocked_or_transient"` for a temporary rate-limit/network issue (the actor already retries several times before giving up and reporting this).

## Notes

- A short or common query — a single common word, or a short numeric registration-number fragment — can match up to 200 entities (the register's own cap per search). Use the full registration number, or a more specific name, for a precise lookup.
- The register applies a brief slowdown to bursts of rapid searches; the actor retries automatically when that happens, but keeping `maxConcurrency` low (1-2) and `requestDelaySecs` at its default or higher makes that far less likely and keeps the run smooth.
- This actor returns the registration record shown in the register's own search results (status, type, date, address, one officer). It does not purchase or download certified documents/full ownership filings, which require a paid account on the register's own site.
