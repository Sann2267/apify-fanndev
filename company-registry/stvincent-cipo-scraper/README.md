# St Vincent and the Grenadines CIPO Business Registry Scraper

Search Saint Vincent and the Grenadines' official company and business register — maintained by CIPO, the Commerce and Intellectual Property Office under the Attorney General's Chambers — by name or registration number.

## Why use this actor

- No account, login, or API key needed — this is CIPO's own free public "Entity search by Name or Number" facility
- Search by entity name (partial names work — real substring matching) or by registration number
- Returns registration number, incorporation date, current status, entity type, and registered address
- Stable JSON output suitable for pipelines, spreadsheets, or quick due-diligence checks
- Automatic retries on temporary network hiccups

## A warning about a lookalike site

A generic web search for "St Vincent company registry" surfaces
`saintvincentregistry.com`, which looks like an official government
portal (it even shows CIPO's real address and phone number) but is
**not real** — its "search" is a client-side script that either matches
a small list of fabricated license numbers against canned fake results,
or generates entirely random fake company data for any other input and
presents it as a verified registry hit. This actor only talks to CIPO's
genuine, government-hosted search API (`ecipo.gov.vc`) — see
`CRAWLING_METHOD.md` for the full recon trail.

## What this actor does NOT do

CIPO's free search facility is a name/status lookup, not a full
registry-detail service. It does not expose directors, shareholders, or
certified document downloads. This actor only uses the genuinely free,
public, no-login search.

## How it works

1. Give the actor one or more entity names (or partial names) or CIPO registration numbers to search for.
2. The actor queries CIPO's public search service for each one.
3. Every matching company or business name is returned as its own dataset record.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "query": "bank",
  "queries": ["109/2003", "trust"],
  "maxResultsPerQuery": 50,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single entity name (or partial name) or CIPO registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default and max 50 — the register's own search service never returns more than 50 matches for a single query, regardless of this setting. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. This is real output from a live run:

```json
{
  "_input": "bank",
  "_source": "S1-namesearchpage",
  "_scrapedAt": "2026-08-27T01:51:29Z",
  "EntityID": "7bce5394-212e-4c9d-807d-113a70401671",
  "EntityName": "ST. VINCENT & THE GRENADINES BANKER'S ASSOCIATION INC.",
  "EntityNumber": "109/2003",
  "DateOfIncorporation": "2003-12-01T00:00:00",
  "LoweredApplicationName": "stvincent",
  "StatusName": "Active",
  "TypeName": "Private Ordinary Company",
  "PrincipalOfficeAddress": "HUGHES & CUMMINGS,  EGMONT STREET,  KINGSTOWN, ST. GEORGE, SAINT VINCENT AND THE GRENADINES",
  "registry": "Commerce and Intellectual Property Office (CIPO)",
  "CaricomStatus": "Active",
  "StatusReason": null
}
```

Searching `"109/2003"` (a registration number) returns 2 matches sharing
that exact number/year — registration numbers are not always globally
unique on this register:

```json
{
  "_input": "109/2003",
  "_source": "S1-namesearchpage",
  "_scrapedAt": "2026-08-27T01:51:30Z",
  "EntityID": "cdd2e632-b64b-4f22-b2aa-be439dedde33",
  "EntityName": "HADLEY'S AUTO SERVICES",
  "EntityNumber": "109/2003",
  "DateOfIncorporation": "2003-12-09T00:00:00",
  "LoweredApplicationName": "stvincent",
  "StatusName": "Active",
  "TypeName": "Business By Individual",
  "PrincipalOfficeAddress": "BELVEDERE, ST. GEORGE, SAINT VINCENT AND THE GRENADINES",
  "registry": "Commerce and Intellectual Property Office (CIPO)",
  "CaricomStatus": "Active",
  "StatusReason": null
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | `S1-namesearchpage` for a real match, `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `EntityID` | CIPO's internal GUID for this entity. |
| `EntityName` | Registered name of the company or business name. |
| `EntityNumber` | CIPO registration/entity number (e.g. `109/2003`). |
| `DateOfIncorporation` | Date the entity was incorporated/registered, when on file. |
| `StatusName` | Current register status — e.g. `Active`, `Inactive`. |
| `StatusReason` | Reason for a non-Active status. Null when Active. |
| `TypeName` | Entity type — e.g. `Private Ordinary Company`, `Business By Individual`. |
| `PrincipalOfficeAddress` | Registered/principal office address on file, when available. |
| `registry` | Always "Commerce and Intellectual Property Office (CIPO)". |
| `CaricomStatus` | CIPO's own CARICOM classification field, passed through as-is. |

A record with `_error` instead of entity fields means that query didn't
produce a usable result:
- `"not_found"` — the search matched nothing.
- `"invalid_query"` — the query was blank, or contained an apostrophe
  (`'`) or a double hyphen (`--`), both of which the register's own
  search service cannot handle (it returns a server error instead of a
  normal result for those, so this actor rejects them before sending the
  request).
- `"blocked_or_transient"` — a temporary network issue.

Some fields (like `PrincipalOfficeAddress` or `DateOfIncorporation`) may
be `null` for older/legacy entities that don't have that data on file
with CIPO — this reflects what the register itself shows, not a scraping
gap.
