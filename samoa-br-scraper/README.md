# Samoa Business Registries Company Scraper

Search Samoa's official company register — run by the Ministry of Commerce, Industry and Labour (MCIL) under the Companies Act 2001 — by name or registration number, and pull the full public profile: registration details, addresses, directors, shareholders, share parcels, and filing history.

## Why use this actor

- No account, login, or API key needed — the register is open to the public
- Search by company name (even a partial one) or by registration number
- Full public profile per match: registration status and dates, addresses (registered office, postal, service), directors (including historical/ceased ones), shareholders (individuals and corporate shareholders, with shareholding percentages via share parcels), and complete filing history
- Also works as a quick name-search tool if you just want the list of matches without opening every profile
- Automatically pages through broad searches (the register shows 10 results per page — this actor fetches up to 10 pages per query)
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more company names (or registration numbers) to search for.
2. The actor searches the official register and finds every matching company.
3. For each match, it opens the full public profile and pulls out every publicly available detail — company info, addresses, directors, shareholders, share parcels, and filings.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name or registration number format — a partial name works too. You don't need to manage retries or figure out the register's internal search flow — the actor handles all of that.

## Input

```json
{
  "queries": ["Digicel", "Bank South Pacific"],
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
| `fetchDetails` | boolean | When on (default), opens every match to pull the full profile. When off, only returns the quick search-result summary (name, registration number, status). |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 100. |
| `maxConcurrency` | integer | How many searches / profile lookups to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Full profile** (`fetchDetails: true`, the default) — one record per matched company. This is the real output for Bank South Pacific (Samoa) Limited, one of Samoa's largest banks, truncated here for readability:

```json
{
  "_input": "Bank South Pacific",
  "_source": "S1-catalyst-detail",
  "_scrapedAt": "2026-08-26T19:39:31Z",
  "name": "BANK SOUTH PACIFIC (SAMOA) LIMITED",
  "registrationNumber": "0650",
  "entityTypeLabel": "Companies",
  "Company Type": "Public Company",
  "Company Status": "Registered",
  "Incorporation Date": "18-Jul-1977",
  "Re-Registration Date": "25-May-2010",
  "Company Rules": "Rules differ from model rules",
  "Business Activity": "Financial and insurance activities- Financial service activities, except insurance and pension funding",
  "Annual Return Filing Month": "May",
  "Annual Return Last Filed on": "29-May-2026",
  "Contact Name": "Anzac VE'E",
  "Telephone": "(685) 66100",
  "Previous Name": "WESTPAC BANK SAMOA LIMITED",
  "addresses": [
    { "Start Date": "18-Jul-1977", "Registered Office Address": "Beach Road, Apia, Vaimauga Sisifo, Samoa" },
    { "Start Date": "18-Jul-1977", "Postal Address": "P.O Box 1860, Apia, Samoa" },
    { "Start Date": "18-Jul-1977", "Address for Service": "Same as Registered Office Address" }
  ],
  "directors": [
    {
      "Name": "Nuni Naye KULU",
      "Residential Address": "Sec 39 Lot 58, Bisini Parade, Boroko, National Capital District, Papua New Guinea",
      "Postal Address": "Bsp Financial Group Limited, Po Box 78, National Capital District, Papua New Guinea",
      "Director Consent": "30-Apr-2026"
    },
    {
      "Name": "Paul Alexander BLACK",
      "Residential Address": "Hilton Hotel, Wards Road, Papua New Guinea",
      "Director Consent": "16-Apr-2024",
      "Ceased": "30-Apr-2026"
    },
    "... 22 more (this register keeps historical/ceased directors on file, not just current ones)"
  ],
  "shareholders": [
    {
      "Entity Name": "BSP FINANCIAL GROUP LIMITED",
      "Registered Office Address": "Section 5, Allotments 12 & 13, Corner Of Musgrave Street And Douglas Street, Granville, Port Moresby, National Capital District, Papua New Guinea",
      "Place of Incorporation": "Papua New Guinea",
      "Appointed": "10-Jul-2015"
    },
    {
      "Name": "E & R Ltd FABRICIUS",
      "Registered Office Address": "Apia, Vaimauga Sisifo, Samoa",
      "Citizenship": "Samoa",
      "Appointed": "18-Jul-1977"
    },
    "... 6 more shareholders (individuals and corporate)"
  ],
  "shareParcels": [
    { "Number of shares": "1185980", "Entity Name": "BSP FINANCIAL GROUP LIMITED" },
    "... 4 more"
  ],
  "filings": [
    { "filingType": "Form 12 Annual return", "submittedAt": "29-May-2026 15:40:27", "filedAt": "29-May-2026 16:27:21" },
    "... 25 more filings on record, back to the 2013 name change and 1977 incorporation"
  ]
}
```

**Search summary** (`fetchDetails: false`) — one record per matched company, without opening the full profile:

```json
{
  "_input": "Digicel",
  "_source": "S1-catalyst-searchresult",
  "_scrapedAt": "2026-08-26T19:35:59Z",
  "name": "DIGICEL (SAMOA) FINANCIAL SERVICES LIMITED",
  "registrationNumber": "0460",
  "entityTypeLabel": "Companies",
  "address": "Npf Plaza, Savalalo, Apia, Vaimauga Sisifo, Samoa",
  "previousNames": ["TELECOM SAMOA CELLULAR LIMITED"],
  "Company Status": "Registered",
  "Incorporation Date": "02-Nov-1997",
  "Business Activity": "Information and communication- Telecommunications",
  "Company Type": "Private Company"
}
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | Which mode produced this record: `S1-catalyst-detail` (full profile) or `S1-catalyst-searchresult` (summary only). |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `name` / `registrationNumber` | The company's registered name and MCIL registration number. |
| `Company Status` / `Company Type` | e.g. Registered/Removed, Private/Public Company. |
| `Incorporation Date` / `Re-Registration Date` | Key dates on file. |
| `Business Activity` | MCIL's own industry classification text. |
| `addresses` | Registered office, postal, and service addresses, each with a start (and end, if superseded) date. |
| `directors` | Every director on file, including historical/ceased ones, with residential and postal addresses. |
| `shareholders` | Every shareholder on file — individuals (with citizenship) or corporate shareholders (with place of incorporation) — including ceased ones. |
| `shareParcels` | Per-shareholder share counts. |
| `filings` | Every filing lodged against the company (annual returns, notice of change of directors/shareholders, rule amendments, etc.) with submission and filed timestamps. Filing *documents* are not downloaded, only this metadata. |

A record with `_error` instead of company fields means that query didn't produce a usable result: `"not_found"` when the search matched no company, or `"blocked_or_transient"` / `"detail_fetch_failed"` for a temporary network issue.

Field names in detail-mode records are taken directly from the labels MCIL's own register page displays (e.g. `"Company Status"`, `"Director Consent"`) rather than renamed — this register doesn't expose a JSON API, so the label text is upstream's own field vocabulary.

## What's not covered

- Filing *documents* (the actual lodged PDF forms) are not downloaded — only the filing metadata (form name, submitted/filed dates).
- Director/Shareholder cross-search (finding every company a named person is linked to) and the separate Secured Transactions (PPSR) register are different tools on the same site and are out of scope for this actor.
