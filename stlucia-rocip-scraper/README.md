# Saint Lucia ROCIP Business Registry Scraper

Search Saint Lucia's official company/business registry — the Registry of Companies and Intellectual Property (ROCIP), under the Attorney General's Chambers — by company/business name, registration number, or director/shareholder surname.

## Why use this actor

- No account, login, or API key needed — the public search is open to anyone
- Search by company/business name (even a partial one) or by registration number
- Search by a director's surname to find every entity they're listed on
- Returns registration status, legal form, key dates, registered address, directors, and secretaries for every match
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC screening
- Automatic retries on temporary network hiccups

## What this actor does NOT do

ROCIP's search API has no pagination and caps a broad query at **50 rows** — narrowing your search text (e.g. adding a suffix like "Limited" or a year) is the only way to see more of a large result set; this actor cannot page past that server-side limit. Shareholder search (`searchMode: "shareholders"`) is exposed because it's a real option on the public search page, but during testing every query tried — common Saint Lucian surnames, generic company words — returned zero matches; ROCIP's `Shareholders` field is also `null` on almost every entity/director search result observed. Shareholder data does not appear to be populated in this search index at all. This is a limitation of what ROCIP's free public search exposes, not a gap in this actor.

## How it works

1. Give the actor one or more company/business names, registration numbers, or (in Directors mode) surnames to search for.
2. The actor queries ROCIP's public search API directly (no browser needed).
3. Every matching record streams into your dataset — one row per match.

## Input

```json
{
  "queries": ["Bank of Saint Lucia", "2001/C135"],
  "searchMode": "entities",
  "maxResultsPerQuery": 50,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company/business name (or partial name), registration number, or surname to search for. |
| `queries` | array | Multiple names/numbers/surnames to search for in one run. |
| `searchMode` | string | `entities` (default, name or registration number), `directors` (surname), or `shareholders` (surname/name — see limitation above). |
| `maxResultsPerQuery` | integer | Maximum matched records returned per query. Default and max 50 — the registry's own API does not return more than 50 rows per query, with no pagination. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. Real output for an entity-name search:

```json
{
  "_input": "Bank of Saint Lucia",
  "_searchMode": "entities",
  "_source": "S1-ocrs-entitysearch",
  "_scrapedAt": "2026-08-26T22:31:01Z",
  "EntityID": "c1060220-36b1-467c-908a-d0915ffc6a75",
  "EntityName": "Bank of Saint Lucia Limited",
  "EntityNumber": "2001/C135",
  "DateOfIncorporation": "2001-06-30T00:00:00",
  "TypeName": "Private Ordinary Company",
  "ApplicationId": "10000000-0000-0000-0000-000000000001",
  "LoweredApplicationName": "stlucia",
  "PrincipalOfficeAddress": " SAINT LUCIA",
  "Email": null,
  "StatusName": "Amalgamated",
  "Directors": "Stewart Haynes,Frank V. Myers,Llewellyn Gill,Matthew Anthony Cotter Beaubrun, ... 13 more",
  "Shareholders": null,
  "Secretaries": null,
  "ProfitStatus": null
}
```

And for a directors-mode search (`searchMode: "directors"`, query `"Charles"`):

```json
{
  "_input": "Charles",
  "_searchMode": "directors",
  "_source": "S1-ocrs-entitysearch",
  "_scrapedAt": "2026-08-26T22:31:11Z",
  "EntityID": "e123cb1e-5c65-4ac5-b8b3-00ab7fcb7471",
  "EntityName": "Caribbean Architects & Property Group (St. Lucia) Ltd.",
  "EntityNumber": "2010/C035",
  "DateOfIncorporation": "2010-02-03T16:19:11.843",
  "TypeName": "Private Ordinary Company",
  "ApplicationId": "10000000-0000-0000-0000-000000000001",
  "LoweredApplicationName": "stlucia",
  "PrincipalOfficeAddress": "Apartment Espoir, Labrelotte Bay, Gros Islet, SAINT LUCIA",
  "Email": null,
  "StatusName": "Active",
  "Directors": "Lucia Charles,Lucia Charles",
  "Shareholders": null,
  "Secretaries": null,
  "ProfitStatus": null
}
```

| Field | Description |
|---|---|
| `_input` | The query (name, number, or surname) you requested, for traceability. |
| `_searchMode` | `entities`, `directors`, or `shareholders` — which index the query ran against. |
| `_source` | `S1-ocrs-entitysearch` for a real match, `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `EntityName` / `EntityNumber` | Registered name and registration number, e.g. `2001/C135`. |
| `TypeName` | Legal form, e.g. `Private Ordinary Company`, `Private Ordinary Foreign Company`, `Business By Firm`. |
| `StatusName` | Current registry status: `Active`, `Inactive`, `Amalgamated`, `LRA-Review`. |
| `DateOfIncorporation` | Date of incorporation/registration, where on file. |
| `PrincipalOfficeAddress` | Registered address, where recorded. |
| `Directors` / `Secretaries` / `Shareholders` | Comma-separated names on file (Shareholders is almost always `null` — see limitation above). |
| `ProfitStatus` | `Profit` or `null`, where indicated. |
| `EntityID` | ROCIP's internal database GUID — useful for de-duplication, not a public-facing identifier. |
| `ApplicationId` / `LoweredApplicationName` | Internal identifiers for the shared multi-country e-filing platform tenant (always `stlucia` here). |

A record with `_error: "not_found"` means that query matched no entity in ROCIP's search index. `_error: "blocked_or_transient"` means a temporary network issue — safe to retry.
