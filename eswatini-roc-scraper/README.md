# Eswatini Company Registry Scraper

Search Eswatini's official government Company Name Search register and get every matching company's registered name, status, and registration date. No account, login, or API key needed.

## Why use this actor

- No account, login, or API key needed — the search is open to the public
- Search by company name (even a partial one)
- Returns registered name, current status (registered vs. reserved-but-not-yet-incorporated), and the date on file
- Handles Eswatini's registry quirks for you: session cookies, the ASP.NET form tokens the search requires, and a generous timeout for broad searches that can legitimately return thousands of matches
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more company names (or partial names, at least 3 characters) to search for.
2. The actor searches the official government register (`online.gov.sz`) and collects every matching row.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "queries": ["MTN", "Eswatini Bank"],
  "maxResultsPerQuery": 50,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company name (or partial name, at least 3 characters) to search for. |
| `queries` | array | Multiple names to search for in one run. Combined with `query` if both are set. |
| `maxResultsPerQuery` | integer | Maximum matched rows returned per query. Default 50, max 1000. The register has no server-side pagination — a broad query can return thousands of rows, so this caps how many are kept. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 3 — keep this low, since a broad query can take the register's own server 20-30 seconds to render. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched company. This is real output for `"MTN"`:

```json
{
  "_input": "MTN",
  "_source": "S1-aspnet-gridview",
  "_scrapedAt": "2026-08-26T22:38:05Z",
  "companyName": "MTN FINTECH SERVICES (PROPRIETARY) LIMITED",
  "companyStatus": "RESERVED",
  "dateRegistered": "03/04/2020"
}
```

And for `"Eswatini Bank"`:

```json
{
  "_input": "Eswatini Bank",
  "_source": "S1-aspnet-gridview",
  "_scrapedAt": "2026-08-26T22:38:05Z",
  "companyName": "ANGLO ESWATINI BANK (PROPRIETARY) LIMITED",
  "companyStatus": "COMPANY REGISTERED",
  "dateRegistered": "06/07/2019"
}
```

| Field | Description |
|---|---|
| `_input` | The query (company name) you requested, for traceability. |
| `_source` | `S1-aspnet-gridview` for a real result row, or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `companyName` | Registered (or reserved) entity name exactly as shown on the register. |
| `companyStatus` | Current status as displayed — `COMPANY REGISTERED` or `RESERVED` (a reserved name that hasn't yet completed incorporation). |
| `dateRegistered` | Registration (or name-reservation) date on file, as the register itself displays it (not reformatted). |

A record with `_error` instead of company fields means that query didn't produce a usable result:

```json
{ "_input": "Debswana", "_source": "none", "_scrapedAt": "2026-08-26T22:36:15Z", "_error": "not_found" }
```

- `not_found` — the search matched no entity on Eswatini's register.
- `query_too_short` — fewer than 3 characters were given.
- `blocked_or_transient` — a temporary network or session issue; safe to retry.

## What this actor does NOT do

Eswatini's public register only exposes three fields per match: name, status, and registration date. There is no free public "click into a company" detail page — full profiles (registration number, directors, addresses, annual returns) require a login-gated account on the same government portal, which this actor does not use (no login automation, per this project's policy). If you only need to confirm whether a business name exists, when it was registered, and whether it's live, this actor covers exactly that.
