# Solomon Islands Business Registry Scraper

Search the Solomon Islands' official company, business name, and foreign investment register — the **Solomon Islands Business Registry** ("Company Haus"), run by the Registrar of Companies under the Ministry of Commerce, Industries, Labour and Immigration — by name or registration number, and pull the full public profile: registration details, addresses, directors/owners, shareholders (with share counts), and filing history.

## Why use this actor

- No account, login, or API key needed — the register is open to the public, free of charge
- Search by company/business name (even a partial one) or by registration number
- Search across Companies, Business Names, and Foreign Investments at once, or restrict to one register
- Full public profile per match: status, registration/incorporation date, addresses, directors or owners, shareholders (with individual share counts), and complete filing history (annual returns and other lodgements, with dates)
- Also works as a quick name-search tool if you just want the list of matches without opening every profile
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more company/business names (or registration numbers) to search for.
2. The actor searches the official register and finds every matching entity.
3. For each match, it opens the full public profile and pulls out every publicly available detail across every tab the registry shows for that entity type — general details, addresses, directors/owners, shareholders, and filing history.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name or registration number format — a partial name works too. You don't need to manage retries or figure out the register's internal search flow — the actor handles all of that.

## Input

```json
{
  "queries": ["Solomon", "Bank"],
  "register": "any",
  "fetchDetails": true,
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company/business name (or partial name) or registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `register` | string | Restrict the search to one register: `any` (default), `companies`, `businessNames`, `investments`. |
| `fetchDetails` | boolean | When on (default), opens every match to pull the full profile. When off, only returns the quick search-result summary (name, registration number, status, address). |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 200. The register returns a single results page per search (no pagination), so a very broad query may not surface every match. |
| `maxConcurrency` | integer | How many search sessions to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Full profile** (`fetchDetails: true`, the default) — one record per matched entity. This is the real output for 3N Solomons Limited, a private company registered in Honiara:

```json
{
  "_input": "3N Solomons",
  "_source": "S1-catalyst-entityview",
  "_scrapedAt": "2026-08-26T19:36:55Z",
  "entityViewUrl": "https://www.solomonbusinessregistry.gov.sb/sb-br-companies/viewInstance/view.html?id=1816ea9fbff8fb61226660606bce1f682567ff726666685a&_timestamp=1334513092089383",
  "Company Type": "Private Company",
  "Company Status": "Registered",
  "Incorporation Date": "06-Mar-2007 March 06 2007",
  "Re-Registration Date": "06-Apr-2011 April 06 2011",
  "Main Business Sector": "Retail & Wholesale",
  "Annual Return Filing Month": "March",
  "Annual Return Last Filed on": "24-Feb-2026 February 24 2026",
  "currentEntityNames": [
    { "Company Name": "3N SOLOMONS LIMITED", "Date Name First Used": "06-Mar-2007 March 06 2007" }
  ],
  "contactRepeater": [
    {
      "Full Name": "Ms  Nancy DONES",
      "phoneRepeater": [{ "Telephone": "(+677)-7470310" }],
      "emailRepeater": [{ "Email": "3nminimall@gmail.com" }]
    }
  ],
  "_tabs": ["General Details", "Addresses", "Directors", "Shares & Shareholders", "Filings"],
  "physicalAddress": [
    { "Registered Office Address": "Unit 2, Komi Fera Pako Building, Commonwealth Street, Poin Cruz, Honiara, Solomon Islands" }
  ],
  "postalAddress": [{ "Postal Address": "P. O. Box 2066, Honiara, Honiara, Solomon Islands" }],
  "director": [
    { "Name": "Charles A VAVE", "Nationality": "Solomon Islands", "Director Consent": "This person has consented to act as a director for this company", "Appointed Date": "06-Mar-2007 March 06 2007" },
    "... 2 more directors"
  ],
  "Total Shares": "50000",
  "shareholderInd": [
    { "Shareholder is also a director": "Yes", "Name": "Annabella C DONES", "Number of shares": "22500", "Nationality": "Solomon Islands", "Appointed Date": "14-Jul-2011 July 14 2011" },
    "... 2 more shareholders"
  ],
  "filingsRepeater": [
    { "Name": "Form 13 - Annual Return of Public or Private Company", "Submitted": "24-Feb-2026 14:07:17", "End": "24-Feb-2026 14:07:16" },
    "... 19 more filings"
  ]
}
```

Business Names and Foreign Investments use the **same generic extraction**, but the registry labels their fields and tabs differently — the actor passes through whatever the registry itself calls each field rather than forcing everything into one fixed schema. For example, a Business Name profile has `_tabs: ["General Details", "Addresses", "Owners", "Filings"]` (no Directors/Shareholders) and fields like `Business Name Number`, `ownerind` (list of owners), `Primary Business Activity`.

**Search summary** (`fetchDetails: false`) — one record per matched entity, without opening the full profile:

```json
{
  "_input": "Bank",
  "_source": "S1-catalyst-searchresult",
  "_scrapedAt": "2026-08-26T19:37:27Z",
  "label": "AJW BANKING AGENT (BN20251334)",
  "name": "AJW BANKING AGENT",
  "registrationNumber": "BN20251334",
  "entityTypeBadge": "BN",
  "ItemAddress": "Auki, Ward 1, Aoke Langa Langa, Malaita, Solomon Islands",
  "Business Name Status": "Registered",
  "Registered Date": "02-Apr-2025",
  "Primary Business Sector": "Financial Institutions",
  "Principal Location": "Malaita"
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | Which mode produced this record: `S1-catalyst-entityview` (full profile) or `S1-catalyst-searchresult` (summary only). |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `entityViewUrl` | A direct link to the entity's public profile page on the register. |
| `_tabs` | Detail mode only: the exact profile tabs this entity had (varies by register). |
| `entityTypeBadge` | `COM` (Companies), `BN` (Business Names), or `INV` (Foreign Investments). |
| `director` / `shareholderInd` / `ownerind` | Lists of people holding that role, with name, nationality, and (for shareholders) individual share count — field names and presence depend on the register/entity type, exactly as the registry itself labels them. |
| `filingsRepeater` | Full filing history on record (annual returns and other lodgements) with submission/filing dates. |
| `label` / `name` / `registrationNumber` | Search-summary mode only: the raw match label and its parsed name/registration number. |

A record with `_error` instead of entity fields means that query didn't produce a usable result: `"not_found"` when the search matched no entity, or `"click_failed"` / `"detail_fetch_failed"` / `"blocked_or_transient"` for a temporary network issue.

This actor uses **raw passthrough**: field names and groupings mirror exactly what the Solomon Islands Business Registry itself displays and labels (including its own spacing/capitalization, e.g. `"Company Type"`), rather than forcing every register into one fixed schema. Some fields may be absent for entities that don't have that data on file — this reflects what the register itself shows, not a scraping gap.
