# Fiji Registrar of Companies (ROC) Search Scraper

Search Fiji's official company and business-name register — run by the Registrar of Companies (ROC) — by entity number or entity name, and get back the entity name, legal suffix, registration number, entity type, and current status for every match.

## Why use this actor

- No account, login, or API key needed — the register's search is open to the public
- Search by ROC entity number (precise) or by entity/business name
- Covers both registered companies and registered business names (sole traders / partnerships)
- Returns current status (e.g. active, ceased, de-registered) so you can quickly check whether an entity is still in good standing
- Useful for due diligence, KYC checks, or bulk-verifying whether a business name is registered
- Stable JSON output suitable for pipelines, spreadsheets, or compliance workflows
- Automatic retries on temporary hiccups

## How it works

1. Give the actor one or more ROC entity numbers or entity/business names.
2. The actor searches Fiji's official company register for matches.
3. Each match's entity name, registration number, type, and status streams into your dataset.
4. Results download as JSON, CSV, or Excel — no manual searching or accounts to manage.

**A note on searching by name:** the register's own name search is broad, not an exact or "contains" match — even an exact, real company name can return a very large number of loosely related results. Searching by entity number is precise and is the recommended mode whenever you know it (for example, from a business card, invoice, or prior search). Combining an entity number with a name in the same search also narrows broad name results, but that combination isn't exposed as a separate input in this actor — see the input table below.

## Input

```json
{
  "queries": ["10658", "Vodafone Fiji"],
  "searchBy": "entityNumber",
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single entity number (e.g. `10658`) or entity/business name (e.g. `Vodafone Fiji`) to search for. |
| `queries` | array | Multiple entity numbers/names to search for in one run. |
| `searchBy` | string | `entityNumber` (default, recommended — precise match) or `entityName` (broad match — see note above). |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 500. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. This is real output from a live search for entity number `10658`:

```json
{
  "_input": "10658",
  "_searchBy": "entityNumber",
  "_source": "S1-buyinformation-search",
  "_scrapedAt": "2026-08-26T18:10:29Z",
  "EntityName": "VODAFONE FIJI",
  "LegalElement": "PTE LIMITED",
  "EntityNumber": "10658",
  "Type": "COMPANY",
  "Status": "ACTIVE",
  "entityDetailUrl": "https://roc.digital.gov.fj/BuyInformation/Application?entityNumber=10658&isAuthChallenged=false"
}
```

The same search also matched a registered business name sharing the substring `10658` in its own registration number, showing the two entity types side by side:

```json
{
  "_input": "10658",
  "_searchBy": "entityNumber",
  "_source": "S1-buyinformation-search",
  "_scrapedAt": "2026-08-26T18:10:29Z",
  "EntityName": "GAUNAVINAKANIVEISAU CANTEEN",
  "LegalElement": "",
  "EntityNumber": "RCBS2015I10658",
  "Type": "BUSINESS NAME",
  "Status": "CEASED",
  "entityDetailUrl": "https://roc.digital.gov.fj/BuyInformation/Application?entityNumber=RCBS2015I10658&isAuthChallenged=false"
}
```

| Field | Description |
|---|---|
| `_input` | The query (entity number or name) you requested, for traceability. |
| `_searchBy` | Which mode produced this record: `entityNumber` or `entityName`. |
| `_source` | `S1-buyinformation-search` for a real match, or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `EntityName` | Registered name of the company or business name. |
| `LegalElement` | Company suffix (e.g. `LIMITED`, `PTE LIMITED`, `LTD`). Empty for business names. |
| `EntityNumber` | ROC registration number — numeric for companies (e.g. `10658`), alphanumeric for business names (e.g. `RCBS2015I10658`, `2026RB010658`). |
| `Type` | `COMPANY` or `BUSINESS NAME`. |
| `Status` | Current register status, e.g. `ACTIVE`, `CEASED`, `DE-REGISTERED`. |
| `entityDetailUrl` | A reference link to the entity's full record on the register. Opening it requires a separate account login on the register's own site — see Notes below. |

A record with `_error` instead of entity fields means that query didn't produce a usable result:

```json
{
  "_input": "999999999",
  "_searchBy": "entityNumber",
  "_source": "none",
  "_scrapedAt": "2026-08-26T18:10:35Z",
  "_error": "not_found"
}
```

- `not_found` — the search matched no entity.
- `result_set_too_broad` — the query matched an extremely large number of entities (typically a very short or very common name search) and the register itself declined to return them; narrow the search (ideally switch to an entity number, or add more of the name).
- `blocked_or_transient` — a temporary network issue; re-run the query.

## Notes / limits

- This actor covers **search only** — entity name, registration number, type, and status. Fiji's register keeps deeper filing details (directors, shareholders, registered address, incorporation date, document downloads) behind a separate paid account login on the register's own site, which this actor does not use. The `entityDetailUrl` field is included as a reference pointer only.
- Searching by name (`searchBy: "entityName"`) uses the register's own broad matching, not a "contains" search — expect large result sets even for specific names. Entity number search does not have this limitation.
- Residential proxy is recommended (on by default) for reliable access at volume.
