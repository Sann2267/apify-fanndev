# Antigua and Barbuda ABIPCO Business Registry Scraper

Search Antigua and Barbuda's official company, business name, and friendly society register — maintained by ABIPCO, the Antigua and Barbuda Intellectual Property and Commerce Office — by name or registration number.

## Why use this actor

- No account, login, or API key needed — this is ABIPCO's own free public "Search the Register" name-check facility
- Search by entity name (even a partial name — it's a real substring match) or by registration number
- Covers all three of ABIPCO's registers in one search: companies, business names, and friendly societies
- Returns registration number, incorporation date, current status (including why an entity was struck off, when applicable), entity type, and registered address
- Stable JSON output suitable for pipelines, spreadsheets, or quick due-diligence checks
- Automatic retries on temporary network hiccups

## What this actor does NOT do

ABIPCO's free search facility is a name/status lookup, not a full registry-detail service. It does not expose directors, shareholders, or certified document downloads — those require ABIPCO's separate paid certified-extract service (a flat fee per extract, requiring an ABIPCO account). This actor only uses the genuinely free, public, no-login search — see `CRAWLING_METHOD.md` for the full recon trail.

## How it works

1. Give the actor one or more entity names (or partial names) or ABIPCO registration numbers to search for.
2. The actor queries ABIPCO's public search service for each one.
3. Every matching company, business name, or friendly society is returned as its own dataset record.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "query": "Sandals",
  "queries": ["LIAT", "C8093"],
  "maxResultsPerQuery": 50,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single entity name (or partial name) or ABIPCO registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default and max 50 — the register's own search service never returns more than 50 matches for a single query, regardless of this setting. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. This is real output from a live run:

```json
{
  "_input": "Sandals",
  "_source": "S1-namesearchpage",
  "_scrapedAt": "2026-08-26T22:40:35Z",
  "EntityID": "ed8373de-c2bb-4f23-81a8-abea215c08b0",
  "EntityName": "Sandals Foundation Incorporated",
  "EntityNumber": "C222/08",
  "DateOfIncorporation": "2008-12-10T00:00:00",
  "LoweredApplicationName": "antigua",
  "StatusName": "Inactive",
  "TypeName": "Private Ordinary Company",
  "PrincipalOfficeAddress": "Hill & Hill Chambers, Long Street, St. John's, ANTIGUA AND BARBUDA",
  "registry": "Intellectual Property & Commerce Office",
  "CaricomStatus": "non-Antigua and Barbuda",
  "StatusReason": "Ceased/Struck-off/Removed"
}
```

```json
{
  "_input": "Sandals",
  "_source": "S1-namesearchpage",
  "_scrapedAt": "2026-08-26T22:40:35Z",
  "EntityID": "58ac32a4-7929-4176-a96b-9743335b81f8",
  "EntityName": "M.G Sandals Nation",
  "EntityNumber": "B1414/2022",
  "DateOfIncorporation": "2022-11-28T13:13:02.58",
  "LoweredApplicationName": "antigua",
  "StatusName": "Active",
  "TypeName": "Business By Individual",
  "PrincipalOfficeAddress": "New Winthropes, St. George's, ANTIGUA AND BARBUDA",
  "registry": "Intellectual Property & Commerce Office",
  "CaricomStatus": "non-Antigua and Barbuda",
  "StatusReason": null
}
```

Searching `"LIAT"` (a real substring match, not just a keyword match) returns 10 entities, including:

```json
{
  "_input": "LIAT",
  "_source": "S1-namesearchpage",
  "_scrapedAt": "2026-08-26T22:40:35Z",
  "EntityID": "9897060b-5b92-44b4-ad3a-ed1741a69fc4",
  "EntityName": "LIAT (2020) LIMITED",
  "EntityNumber": "C1133/2020",
  "DateOfIncorporation": "2020-10-22T00:00:00",
  "LoweredApplicationName": "antigua",
  "StatusName": "Active",
  "TypeName": "Private Ordinary Company",
  "PrincipalOfficeAddress": "Bismark Place, LIAT Road, Coolidge, Saint George, ANTIGUA AND BARBUDA",
  "registry": "Intellectual Property & Commerce Office",
  "CaricomStatus": "non-Antigua and Barbuda",
  "StatusReason": null
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | `S1-namesearchpage` for a real match, `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `EntityID` | ABIPCO's internal GUID for this entity. |
| `EntityName` | Registered name of the company, business name, or friendly society. |
| `EntityNumber` | ABIPCO registration/entity number (e.g. `C222/08` for a company, `B1414/2022` for a business name, `FS8/2017` for a friendly society). |
| `DateOfIncorporation` | Date the entity was incorporated/registered, when on file. |
| `StatusName` | Current register status — `Active` or `Inactive`. |
| `StatusReason` | Reason for a non-Active status (e.g. `Ceased/Struck-off/Removed`). Null when Active. |
| `TypeName` | Entity type — e.g. `Private Ordinary Company`, `Private Ordinary Foreign Company`, `Business By Individual`, `Business By Corporation`, `Friendly society`. |
| `PrincipalOfficeAddress` | Registered/principal office address on file, when available. |
| `registry` | Always "Intellectual Property & Commerce Office". |
| `CaricomStatus` | `Antigua and Barbuda` for a domestic entity, `non-Antigua and Barbuda` for a foreign/external one. |

A record with `_error` instead of entity fields means that query didn't produce a usable result: `"not_found"` when the search matched nothing, `"invalid_query"` when the query was blank/whitespace-only, or `"blocked_or_transient"` for a temporary network issue.

Some fields (like `PrincipalOfficeAddress` or `DateOfIncorporation`) may be `null` for older/legacy entities that don't have that data on file with ABIPCO — this reflects what the register itself shows, not a scraping gap.
