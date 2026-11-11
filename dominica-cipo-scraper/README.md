# Dominica CIPO Business Registry Scraper

Search the Commonwealth of Dominica's official company register — CIPO, the
Companies and Intellectual Property Office — by entity name/registration
number, director surname, or shareholder name. Pulls registration details
plus the directors, secretary, and shareholders CIPO has on file.

## Why use this actor

- No account, login, or API key needed — the register's search is open to
  the public
- Search by entity name (even partial), registration number, director
  surname, or shareholder name
- Optional follow-up lookup adds directors/secretary/shareholders on file
  for each match
- Covers both incorporated companies (including Dominica's large offshore/
  international-business-company sector) and local sole-proprietor business
  names
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC
  workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more search terms.
2. Choose what they should match: entity names/numbers (default), director
   surnames, or shareholder names.
3. The actor searches the official register and returns every match.
4. When "Fetch director/secretary/shareholder detail" is on (default), each
   match gets a follow-up lookup adding whatever director/secretary/
   shareholder names CIPO has on file for it.
5. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

```json
{
  "queries": ["Paxum Bank", "MIGOM BANK"],
  "searchType": "entities",
  "fetchDetails": true,
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single search term. Must not contain a comma or `=` (see Known limits). |
| `queries` | array | Multiple search terms to run in one job. |
| `searchType` | string | `entities` (name/registration number, default), `directors` (surname), or `shareholders` (surname/company name). |
| `fetchDetails` | boolean | When on (default), each match gets a follow-up lookup for directors/secretary/shareholders on file. When off, only the raw search row is returned. |
| `maxResultsPerQuery` | integer | Maximum matches kept per search term. Default 20, max 200. The register itself returns everything in one response (no server paging) — this only caps what the actor keeps. |
| `maxConcurrency` | integer | How many searches/lookups run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Entity-name search, with detail fetch on** (the default) — one record per
matched entity. Real output for "Paxum Bank":

```json
{
  "_input": "Paxum Bank",
  "_searchType": "entities",
  "_source": "S1-ocrs-entitysearch+entityinfo",
  "_scrapedAt": "2026-08-26T22:38:21Z",
  "EntityID": "3e66c50c-398d-47b2-8b77-33364f15e466",
  "EntityName": "Paxum Bank Limited",
  "EntityNumber": "2015/C3218",
  "DateOfIncorporation": "2015-05-08T08:02:00",
  "LoweredApplicationName": "dominica",
  "StatusName": "Active",
  "TypeName": "Private Ordinary Company",
  "PrincipalOfficeAddress": "Centre Cross Lane, Roseau, DOMINICA",
  "registry": "COMPANIES & INTELLECTUAL PROPERTY OFFICE",
  "CaricomStatus": "non-CARICOM",
  "Directors": "Anton Postolnikov, Angel Pacheco",
  "Secretaries": "Galeine Gordon",
  "Schareholders": null
}
```

**Director/shareholder search** — these modes already return
directors/shareholders/secretary/email inline, so the detail lookup adds
the same data again under upstream's own typo'd field name
(`Schareholders`, kept verbatim rather than "corrected"). Real output for a
director-surname search ("Brito", `searchType: "directors"`):

```json
{
  "_input": "Brito",
  "_searchType": "directors",
  "_source": "S1-ocrs-entitysearch+entityinfo",
  "_scrapedAt": "2026-08-26T22:38:30Z",
  "EntityID": "aeaf3e35-a742-4d5f-9402-09ae2d22ac64",
  "EntityName": "CIBAmericas Bank Inc.",
  "EntityNumber": "2015/C3170",
  "DateOfIncorporation": "2015-02-11T14:27:00",
  "TypeName": "Private Ordinary Company",
  "ApplicationId": "20000000-0000-0000-0000-000000000002",
  "LoweredApplicationName": "dominica",
  "registry": "COMPANIES & INTELLECTUAL PROPERTY OFFICE",
  "PrincipalOfficeAddress": "38 Great George Street, Roseau, DOMINICA",
  "Email": null,
  "StatusName": "Active",
  "Directors": "Ricardo Brito Robles, Orlando Moise, Marcelo Zarco Legorreta",
  "Shareholders": " Ricardo Brito Robles, Jorge Alberto Valdes Padilla",
  "Secretaries": "Targhe Jno Lewis",
  "CaricomStatus": "non-CARICOM",
  "Schareholders": "Ricardo Brito Robles, Jorge Alberto Valdes Padilla"
}
```

| Field | Description |
|---|---|
| `_input` | The search term you requested, for traceability. |
| `_searchType` | Which register field `_input` was matched against. |
| `_source` | `S1-ocrs-entitysearch` (search row only) or `S1-ocrs-entitysearch+entityinfo` (enriched with the follow-up lookup). |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `EntityID` | CIPO's internal ID for the entity. |
| `EntityName` / `EntityNumber` | Registered name and official registration number. |
| `DateOfIncorporation` | Registration/incorporation date on file. |
| `StatusName` | Current register status. |
| `TypeName` | e.g. Private Ordinary Company, Business By Firm (a local sole-proprietor business name). |
| `PrincipalOfficeAddress` | Registered/principal office address, as a single free-text string. |
| `CaricomStatus` | CARICOM / non-CARICOM classification on file. |
| `Directors` / `Secretaries` / `Shareholders` / `Schareholders` | Comma-joined name strings on file (not structured per-person records) — `Shareholders` on director/shareholder-mode rows, `Schareholders` (upstream's own typo) from the detail lookup. |
| `Email` / `ApplicationId` | Director/shareholder search mode only. |

A record with `_error` instead of company fields means that search term
didn't produce a usable result:

- `"not_found"` — the search matched no entity.
- `"invalid_query"` — the term contains a `,` or `=` character, which
  CIPO's own search endpoint mishandles (a comma silently truncates the
  search instead of erroring; see Known limits).
- `"upstream_error"` — CIPO's own API returned an error, most often its
  "Divide by zero" bug on an overly broad single-word query (e.g. a single
  letter, or a common word like "international" that matches very many
  entities) — try a more specific term.
- `"blocked_or_transient"` — a temporary network issue.

## Known limits

- **This is a shallower data model than some of this project's other
  small-country registry actors.** CIPO's public API exposes no structured
  addresses, no share-allocation/ownership-percentage data, and no
  beneficial-ownership disclosure — directors/secretary/shareholders come
  back only as plain joined name strings, with no nationality, address, or
  appointment date per person. This is what CIPO itself publishes, not a
  scraping gap.
- **No server-side pagination.** A search returns every match in one
  response (or errors on an overly broad one) — `maxResultsPerQuery` is
  enforced by this actor, not the register.
- **Don't put a comma or `=` in a search term.** CIPO's search endpoint
  parses its own request body naively; a comma silently truncates the
  query and `=` triggers a server error. This actor rejects both up front
  with a clear `invalid_query` error rather than risk a silently-wrong
  match.
- A very broad single-word query (a single letter, or a common whole word)
  can trip CIPO's own "Divide by zero" bug — narrow the term and retry.
