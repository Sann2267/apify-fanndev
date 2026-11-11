# Botswana CIPA Business Registry Scraper

Search Botswana's official company register — CIPA, the Companies and Intellectual Property Authority — by name or registration number, and pull the full public profile: registration details, addresses, directors, company secretary, shareholders, auditor, and beneficial owners.

## Why use this actor

- No account, login, or API key needed — the register is open to the public
- Search by company name (even a partial one) or by registration number
- Full public profile per match: registration status and history, registered/postal/physical addresses, directors, secretary, shareholders (including their shareholding percentages), auditor, and ultimate beneficial owners
- Also works as a quick name-search tool if you just want the list of matches without opening every profile
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more company names (or registration numbers) to search for.
2. The actor searches the official register and finds every matching entity.
3. For each match, it opens the full public profile and pulls out every publicly available detail — company info, addresses, directors, shareholders, and beneficial owners.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name or registration number format — a partial name works too. You don't need to manage retries or figure out the register's internal search flow — the actor handles all of that.

## Input

```json
{
  "queries": ["Debswana", "Bank Gaborone"],
  "entityType": "any",
  "fetchDetails": true,
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company name (or partial name) or registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `entityType` | string | Restrict results to one register entity type: `any` (default), `businessName`, `private`, `public`, `external`, `close`. |
| `fetchDetails` | boolean | When on (default), opens every match to pull the full profile. When off, only returns the quick search-result summary (name, registration number). |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 200. |
| `maxConcurrency` | integer | How many searches / profile lookups to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Full profile** (`fetchDetails: true`, the default) — one record per matched entity. This is the real output for Debswana Diamond Company, Botswana's largest company (a joint venture between the Botswana government and De Beers), truncated here for readability:

```json
{
  "_input": "Debswana",
  "_source": "S1-verne-entityview",
  "_scrapedAt": "2026-08-26T17:40:48Z",
  "entityViewUrl": "https://www.cipa.co.bw/companies/ui/start/entityView/c58057d87799f8766ccf352bed288cf6?dom=Company",
  "Status": [{ "Status": "registered", "StartDate": "23 June 1969" }],
  "EntityType": "private",
  "SubType": "limitedByShares",
  "CompanyNumber": "BW00000466545",
  "OldCompanyNumber": "CO1969/660",
  "RegistrationDate": "23 June 1969",
  "ReregistrationDate": "01 August 2019",
  "LastRenewalDate": "12 June 2026",
  "TotalShare": "158393312",
  "IsExemptFromAudit": "false",
  "CompanyName": [{ "Name": "Debswana Diamond Company", "Suffix": "proprietaryLimited" }],
  "RegisteredOfficeAddress": [{
    "PhysicalAddress": [{
      "CountryCode": "BW", "CareOf": "The Board Secretary",
      "Line1": "Plot 64288", "Line2": "Airport Road, Block 8", "City": "Gaborone"
    }]
  }],
  "Director": [
    {
      "IndividualDirector": [{
        "Nationality": "BW", "StartDate": "01 January 2026",
        "IndividualName": [{ "FirstName": "Dick", "MiddleNames": "Billy", "LastName": "Bayford" }],
        "RolePostalAddress": [{ "CountryCode": "BW", "Line1": "Private Bag 009", "City": "Gaborone" }]
      }]
    },
    "... 4 more directors"
  ],
  "Shareholder": [
    {
      "OtherShareholder": [{
        "StartDate": "23 June 1969",
        "OtherEntity": [{ "CountryOfRegistration": "VG", "Name": [{ "Name": "Delibes Holdings Limited" }] }],
        "RolePhysicalAddress": [{ "CountryCode": "VG", "Line1": "Craigmuir Chambers", "City": "Road Town" }]
      }]
    },
    {
      "OtherShareholder": [{
        "StartDate": "23 June 1969",
        "OtherEntity": [{ "CountryOfRegistration": "BW", "Name": [{ "Name": "Government Of The Republic Of Botswana" }] }]
      }]
    }
  ],
  "Secretary": [ "... 1 entry, same shape as Director" ],
  "Auditor": [ "... 1 entry, same shape as Director" ],
  "BeneficialOwner": [ "... entries with name, nationality, address, and percentage interest" ],
  "ShareAllocation": [ "... per-shareholder share counts and percentages" ]
}
```

**Search summary** (`fetchDetails: false`) — one record per matched entity, without opening the full profile:

```json
{
  "_input": "Bank Gaborone",
  "_source": "S1-verne-searchresult",
  "_scrapedAt": "2026-08-26T17:40:25Z",
  "label": "Bank Gaborone Limited (BW00000015806)",
  "name": "Bank Gaborone Limited",
  "registrationNumber": "BW00000015806"
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | Which mode produced this record: `S1-verne-entityview` (full profile) or `S1-verne-searchresult` (summary only). |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `entityViewUrl` | A direct, shareable link to the entity's public profile page on the register. |
| `CompanyNumber` | The official CIPA registration number. |
| `Status` | Current and historical registration status. |
| `EntityType` / `SubType` | Type of registered entity (private/public/external/close company, business name) and share structure. |
| `RegistrationDate` / `ReregistrationDate` / `LastRenewalDate` | Key dates on file. |
| `CompanyName` | Registered name (and any prior name on file). |
| `RegisteredOfficeAddress` / `MailAddress` / `PrincipalPlaceOfBusinessAddress` | Addresses on file, each with country, care-of, street, and city. |
| `Director` / `Secretary` / `Shareholder` / `Auditor` | Lists of people (or, for shareholders, sometimes another company) holding that role, with name, nationality, and address. |
| `ShareAllocation` | Per-shareholder share counts and ownership percentages. |
| `BeneficialOwner` | Ultimate beneficial owners on file, with their percentage interest. |
| `label` / `name` / `registrationNumber` | Search-summary mode only: the raw match label and its parsed name/registration number. |

A record with `_error` instead of company fields means that query didn't produce a usable result: `"not_found"` when the search matched no entity, or `"blocked_or_transient"` / `"detail_fetch_failed"` for a temporary network issue.

Some fields (like `ShareAllocation`, `BeneficialOwner`, or a given address) may be absent for entities that don't have that data on file with CIPA — this reflects what the register itself shows, not a scraping gap.
