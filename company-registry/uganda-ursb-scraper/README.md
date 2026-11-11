# Uganda URSB Business Registry Scraper

Search Uganda's official company and business name register — URSB, the Uganda Registration Services Bureau — by name or registration number, and get back the public registry record for every match.

## Why use this actor

- No account, login, or API key needed — the register's name search is open to the public
- Search by business/company name (even a partial one) or by registration number (ERN)
- Returns entity type and sub-type, registration status, compliance status, and the official registration number for each match
- Works for companies and registered business names (sole proprietorships, partnerships) alike
- Stable JSON output suitable for pipelines, spreadsheets, or KYC/compliance workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more business/company names (or registration numbers) to search for.
2. The actor searches the official register and collects every matching entity, paging through results automatically.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name or registration number format — a partial name works too. You don't need to manage retries or pagination yourself — the actor handles all of that.

## Input

```json
{
  "queries": ["Stanbic", "MTN"],
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single business/company name (or partial name) or registration number (ERN) to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 2000. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched entity. This is real output captured from a live run for the query `"Stanbic"`:

```json
{
  "_input": "Stanbic",
  "_source": "S1-nir-name-search",
  "_scrapedAt": "2026-08-26T18:06:24Z",
  "id": "dee6ca5c-1dd4-4fe4-a6c7-1346390b9851",
  "ern": "80020002358032",
  "name": "STANBIC PROPERTIES LIMITED",
  "type": "Company",
  "subType": "Private Company Limited by Shares",
  "status": "REGISTERED",
  "registrationInstitution": "Uganda Registration Services Bureau",
  "duplicateAllowed": false,
  "createdAt": "2026-06-29T19:39:41.743116Z",
  "deactivatedAt": null,
  "registrationDate": null,
  "affiliations": [],
  "registrationType": "",
  "recordStatus": "",
  "complianceStatus": "COMPLIANT"
}
```

And for the query `"MTN"`, showing a registered business name (sole proprietorship-style entity) alongside companies:

```json
{
  "_input": "MTN",
  "_source": "S1-nir-name-search",
  "_scrapedAt": "2026-08-26T18:06:34Z",
  "id": "...",
  "ern": "80030815499700",
  "name": "MTSL & XEEC",
  "type": "Business Name",
  "subType": "General Partnership",
  "status": "REGISTERED",
  "registrationInstitution": "Uganda Registration Services Bureau",
  "complianceStatus": "COMPLIANT"
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | Always `S1-nir-name-search` for a matched entity, or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `ern` | The official URSB registration number (Entity Registration Number). |
| `name` | Registered business or company name. |
| `type` / `subType` | Kind of registered entity — e.g. `Company` / `Private Company Limited by Shares`, or `Business Name` / `Sole Proprietor` / `General Partnership`. |
| `status` | Current register status, e.g. `REGISTERED`. |
| `complianceStatus` | e.g. `COMPLIANT`. |
| `registrationDate` | Registration date on file — often not populated by the register's public search (this reflects what URSB itself returns, not a gap in this actor). |
| `duplicateAllowed`, `deactivatedAt`, `affiliations`, `registrationType`, `recordStatus` | Additional fields as returned by the register, passed through as-is. |

A record with `_error` instead of entity fields means that query didn't produce a usable result: `"not_found"` when the search matched no entity, or `"blocked_or_transient"` for a temporary network issue. A record with `_warning: "pagination_truncated_by_timeout"` means the register stopped responding partway through a very large result set — everything collected up to that point is still included.

## Notes / limits

- The register's own search is fuzzy by design — it's built to catch similar/conflicting names, not just exact substrings — so an unusual or very short query can occasionally return a loosely-related name alongside (or instead of) exact matches. This reflects the register's own behavior.
- Some fields (like `registrationDate`) are frequently empty in the register's public search results — this is what URSB itself returns, not missing data on this actor's side.
- This actor covers the free public name/number search only. Purchasing a certified extract or full company document requires an account and payment directly on URSB's own site, which is outside the scope of this actor.
