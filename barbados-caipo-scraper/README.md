# Barbados CAIPO Business Registry Scraper

Search Barbados's official company/business registry — CAIPO (the
Corporate Affairs and Intellectual Property Office, on-page branded
"Business Barbados") — by company name, registration number, or register
category. Automates the same public "Search Our Database" tool available at
`caipo.gov.bb/search-our-database/`. No account, login, or API key needed.

## What this actor returns — and what it doesn't

This is a **registry search / lookup tool**, the same free tool CAIPO
provides on its own website. For each matching entity it returns:

- **Company name** — exactly as registered
- **Registration number**
- **Register category** — e.g. Domestic Register, Business Names,
  International Business Company, Charity Register, Off-Shore Bank
  Register (34 categories in total)
- **Registration date**

It does **not** return status (active/dissolved), registered address, or
director/officer names — CAIPO's public search tool does not expose those
fields. A fuller profile is only available through a paid, $5 "Company
Inquiry" service handled directly by CAIPO (not an API — out of scope for
this actor). If your use case needs directors, officers, or filing status,
this actor is not a fit — but if you need to check whether a name is
registered, find every entity matching a keyword, or pull an entire
register category, this gives you exactly what CAIPO's own website gives a
human visitor, at scale.

**Data quirk worth knowing:** CAIPO's registration numbers are **reused**
across amalgamations, re-registrations, and historical name changes — the
same number can legitimately appear on multiple rows with different company
names. Don't treat `company_number` as a unique per-company key; treat each
result row as its own record.

## Why use this actor

- Searches Barbados's real, current registry — not the dead
  `corporateaffairs.gov.bb` domain sometimes cited elsewhere, which no
  longer resolves at all
- No login or CAPTCHA — every request mirrors CAIPO's own public search
  page exactly
- Three match modes on name/number: `Contains`, `Equals`, `Starts with`
- Optional register-category filter, usable alone to list an entire
  category
- Truncation-aware output: every record reports how many matches actually
  exist upstream (`_totalAvailable`), even when `maxResultsPerQuery` caps
  what gets pushed to your dataset

## Input

```json
{
  "query": "Sagicor",
  "searchField": "name",
  "condition": "Contains",
  "category": "",
  "maxResultsPerQuery": 100,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company name (or fragment) or CAIPO registration number to search for. |
| `queries` | array | Multiple names/numbers to search for in one run. Combined with `query` if both are set. |
| `searchField` | string | `"name"` (default) or `"number"` — which field `query`/`queries` values are matched against. |
| `condition` | string | `"Contains"` (default), `"Equals"`, or `"Starts with"`. |
| `category` | string | Optional register-category filter (34 options, e.g. `"DOMESTIC REGISTER "`, `"BUSINESS NAMES  "`). Leave blank for all categories. Can be used alone, without a name/number query, to list an entire category. |
| `maxResultsPerQuery` | integer | Caps how many matches are pushed to the dataset per query (default 100, max 2000). CAIPO itself caps any single search at 2,000 rows and reports `_truncated: true` beyond that. |
| `maxConcurrency` | integer | Parallel search requests (default 3, max 10) — kept modest since this is a small government web app. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matching entity. Real output for
`{"query": "Sagicor", "maxResultsPerQuery": 5}`:

```json
{
  "_input": "Sagicor",
  "_source": "S1-searchDbApi",
  "_scrapedAt": "2026-08-26T19:19:38Z",
  "_totalAvailable": 16,
  "_truncated": false,
  "company_name": "SAGICOR GENERAL INSURANCE INC.",
  "company_number": "11569",
  "registration_category": "AMALGAMATION (DOMESTIC) REGISTER ",
  "registration_date": "1995-12-29"
}
```

Real output demonstrating the registration-number reuse quirk, for
`{"query": "24781", "searchField": "number", "condition": "Equals"}`:

```json
{
  "_input": "24781",
  "_source": "S1-searchDbApi",
  "_scrapedAt": "2026-08-26T19:19:12Z",
  "_totalAvailable": 2,
  "_truncated": false,
  "company_name": "SAGICOR LIFE INC.",
  "company_number": "24781",
  "registration_category": "AMALGAMATION (DOMESTIC) REGISTER ",
  "registration_date": "2005-02-01"
}
```

```json
{
  "_input": "24781",
  "_source": "S1-searchDbApi",
  "_scrapedAt": "2026-08-26T19:19:12Z",
  "_totalAvailable": 2,
  "_truncated": false,
  "company_name": "NIGEL'S BARBER SHOP",
  "company_number": "24781",
  "registration_category": "BUSINESS NAMES  ",
  "registration_date": "2002-04-04"
}
```

A no-match query returns a single error record instead of an empty dataset:

```json
{
  "_input": "zzzzzznonexistentxyz123",
  "_source": "none",
  "_scrapedAt": "2026-08-26T19:19:14Z",
  "_error": "not_found"
}
```

See `CRAWLING_METHOD.md` for the full technical writeup (robots.txt
findings, endpoint reverse-engineering, and known limits).
