# Tonga Business Registry Scraper

Search the Kingdom of Tonga's official company registry — the **Business
Entities Registry** run by the Ministry of Commerce, Consumer, Trade,
Innovation and Labour (MCCTIL) at `businessregistries.gov.to` — by company
name, or look up a specific entity by its registry ID. No account, login,
or API key needed.

## Why use this actor

- Searches Tonga's real, government-operated company registry — registration
  number, status, entity type (Company, Overseas Company, Business Name,
  Business Licence, Foreign Certificate), registered office/postal address,
  and business activities
- **Also returns real directors, shareholders, share allotments, and full
  filing history for free, with no login** — including each director's and
  shareholder's own residential address. This registry is notably more open
  than some peers in this portfolio running the same underlying platform
  (e.g. PNG's IPA registry keeps that layer behind a paid account)
- No account, login, or CAPTCHA required — the public search is free and
  open, exactly as the registry's own site states
- Look up a specific entity directly by its registry ID (`corpIds`) once you
  know it, e.g. from a previous run
- Automatic retries on temporary network hiccups

## What this actor does NOT include

`Officers`, `Secretaries`, `Owners`, and `BeneficialOwners` came back as
**empty arrays** on every entity tested during development — this may
reflect a stricter gate on those specific role types, or simply no data on
file for the sample entities checked; it wasn't possible to tell without a
login this actor deliberately never attempts (no-login policy). These
fields are still included on every profile record, passed through exactly
as upstream returns them, rather than hidden.

## How it works

1. Give the actor one or more company name search terms, or one or more
   entity IDs (`corpIds`) if you already know them.
2. For each search term, the actor queries the registry and returns every
   matching entity (up to your configured cap).
3. By default it also fetches the full profile (addresses, directors,
   shareholders, filing history) for every match — turn `fetchProfiles` off
   for a faster, lighter-weight name-only search.
4. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

```json
{
  "searchTerms": ["Bank"],
  "fetchProfiles": true,
  "maxResultsPerTerm": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

Direct entity-ID lookup (skips searching):

```json
{
  "corpIds": ["98cc1dee-6fe9-462d-a617-7e1b7262c156"],
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `searchTerms` | array | Company/business names or keywords to search for. |
| `corpIds` | array | Tonga Registry entity GUIDs (from a prior run's `CorpId`, or an `EntityProfile.aspx?id=...` URL) for a direct profile lookup, bypassing search. |
| `fetchProfiles` | boolean | When on (default), also fetches the full profile for every search match. When off, returns only the lightweight search-result fields. |
| `entityTypeId` | string (select) | Optional: restrict search to one entity type (Company, Overseas Company, Business Name, Business Licence, Foreign Certificate variants). |
| `maxResultsPerTerm` | integer | Max matching entities returned per search term. Default 20, max 200. |
| `maxConcurrency` | integer | How many search terms / entity IDs to process in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

At least one of `searchTerms` or `corpIds` is required.

## Output

**Direct entity-ID lookup, full profile** (real output for `corpIds:
["98cc1dee-6fe9-462d-a617-7e1b7262c156"]` — "A & A CONSULTANTS (TONGA)
LIMITED" — `CorpFilings`/`Members`/`ShareAllotments` truncated here for
readability):

```json
{
  "Corp": {
    "CorpId": "98cc1dee-6fe9-462d-a617-7e1b7262c156",
    "CompanyName": "A & A CONSULTANTS (TONGA) LIMITED",
    "RegistrationNumber": "LC9005612",
    "TaxId": "508120",
    "CompanyType": "Company",
    "Status": "Registered",
    "RegistrationDateFormatted": "03/03/2014",
    "TotalShares": 100,
    "AnnualReturnDueDateFormatted": "28/02/2027",
    "LastReportFiledDateFormatted": "17/02/2026",
    "RegisteredOfficeAddress": {
      "AddressType": "Address of Registered Office",
      "Street1": "BYPASS ROAD,PAHU,NUKU'ALOFA",
      "Village": "PAHU",
      "District": "TONGATAPU 3",
      "State": "TONGATAPU",
      "Country": "TONGA"
    },
    "PostalAddress": { "Street1": "P O BOX 385, BYPASS RD", "...": "..." },
    "...": "... ~40 more raw upstream fields"
  },
  "CorpFilings": [
    { "...": "... 16 filings total, e.g. registration, annual returns, director/shareholder changes, each dated" }
  ],
  "Directors": [
    {
      "OfficerType": "Director",
      "FullName": "Lafitani 'inoke AFU",
      "Nationality": "Tonga",
      "Gender": "Male",
      "AppointmentDateFormatted": "03/03/2014",
      "Address": {
        "AddressType": "Residential Address",
        "Street1": "14 TUPOULAHI RD",
        "Village": "FASI-MOE-AFI",
        "District": "TONGATAPU 3",
        "State": "TONGATAPU",
        "Country": "TONGA"
      }
    }
  ],
  "Members": [
    { "OfficerType": "Shareholder", "FullName": "Lafitani 'inoke AFU", "...": "... same shape as Directors" }
  ],
  "ShareAllotments": [ { "Shareholders": [ "... same shareholder records" ] } ],
  "Officers": [],
  "Secretaries": [],
  "Owners": [],
  "BeneficialOwners": [],
  "IsAuthorized": false,
  "IsLoggedin": false,
  "_input": "98cc1dee-6fe9-462d-a617-7e1b7262c156",
  "_source": "S2-profile-direct",
  "_scrapedAt": "2026-08-26T22:31:47Z"
}
```

**Search-only record** (`fetchProfiles: false`) — one lightweight record per
match, no extra requests; real output for `searchTerms: ["Air Pacific"]`:

```json
{
  "_input": "Air Pacific",
  "_source": "S1-searchcorp",
  "_scrapedAt": "2026-08-26T22:33:40Z",
  "CorpId": "326ad306-d794-4381-96d6-25951459fa72",
  "Name": "AIR PACIFIC LIMITED",
  "RegistrationNumber": "BL537",
  "RegistrationDateFormatted": "22/12/2011",
  "Type": "Business Licence",
  "Status": "Registered",
  "PriorNames": [],
  "BusinessActivities": ["511 - Passenger air transport", "512 - Freight air transport"],
  "RegisteredOfficerAddress": "TONGA POST BUILDING, TAUFA'AHAU RD, NUKU'ALOFA, KOLOMOTU'A, TONGATAPU 1, TONGATAPU, TONGA"
}
```

**Not-found record** (invalid/nonexistent `corpIds` entry):

```json
{
  "_input": "00000000-0000-0000-0000-000000000000",
  "_source": "none",
  "_scrapedAt": "2026-08-26T22:31:53Z",
  "_error": "not_found"
}
```

**No-match record** (search term matched nothing):

```json
{
  "_input": "zzzznonexistentxyz999",
  "_source": "none",
  "_scrapedAt": "2026-08-26T22:32:02Z",
  "_error": "no_results"
}
```

| Field | Description |
|---|---|
| `_input` | The search term or entity ID you provided, for traceability. |
| `_source` | `S1-searchcorp` (search result only), `S1-searchcorp+profile` (search result + full profile), `S2-profile-direct` (from `corpIds`), or `none` (error). |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `CorpId` / `Name` / `RegistrationNumber` / `Type` / `Status` / `RegistrationDateFormatted` | Core identity fields, present on every non-error record. |
| `PriorNames` | Previous registered names, if any. |
| `BusinessActivities` | Declared business activity categories. |
| `Corp` / `Addresses` / `Activities` / `CorpFilings` | Full profile detail — only on `S1-searchcorp+profile` / `S2-profile-direct` records. |
| `Directors` / `Members` / `ShareAllotments` | Real director/shareholder names, nationality, appointment dates, and residential addresses — populated with no login required. |
| `Officers` / `Secretaries` / `Owners` / `BeneficialOwners` | Empty on every entity tested for anonymous access — see "What this actor does NOT include" above. |
| `_error` | Present only on failed lookups: `not_found` (invalid entity ID), `no_results` (search term matched nothing), or `blocked_or_transient` (network/token issue). |

## Notes

- Full technical write-up of the registry's internal JSON API and the
  anti-CSRF token mechanism is in `CRAWLING_METHOD.md`.
- The registry also hosts a Personal Property Securities Registry ("PPSA
  Search") and separate Name Availability / Name Reservation search pages on
  the same domain — out of scope for this actor.
