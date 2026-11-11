# PNG IPA Business Registry Scraper

Search Papua New Guinea's official company registry — the Investment Promotion Authority's (IPA) Business Entities Registry (`www.ipa.gov.pg`) — by company name, or look up a specific entity by its registry ID. No account, login, or API key needed.

## Why use this actor

- Searches PNG's real, government-operated company registry — registration number, status, entity type, registered office/postal address, business activities, share info, annual return due date, and full filing history (registrations, director/secretary/shareholder changes, annual returns) with dates
- No account, login, or CAPTCHA required — the public search is free and open, exactly as the registry's own site states
- Returns every match for a name, including prior/historical names and inactive/cancelled/removed entities, not just currently-active ones
- Look up a specific entity directly by its registry ID (`corpIds`) once you know it, e.g. from a previous run
- Automatic retries on temporary network hiccups

## What this actor does NOT include

PNG IPA gates the actual **names of directors, secretaries, and shareholders** (as opposed to the dates those roles changed) behind a login-required "IPA Online" account. This actor never attempts to obtain or use such an account — per policy, no login/CAPTCHA/paid-report workaround is used. The `Officers`, `Directors`, `Secretaries`, `Shares`, `Owners`, and `BeneficialOwners` fields are included in every profile record but come back as **empty arrays** for every entity (confirmed across old and brand-new companies alike) — this is upstream's own anonymous-access behavior, passed through as-is rather than hidden.

## How it works

1. Give the actor one or more company name search terms, or one or more entity IDs (`corpIds`) if you already know them.
2. For each search term, the actor queries the registry and returns every matching entity (up to your configured cap).
3. By default it also fetches the full profile (addresses, business activities, share info, filing history) for every match — turn `fetchProfiles` off for a faster, lighter-weight name-only search.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "searchTerms": ["Air Niugini"],
  "fetchProfiles": true,
  "maxResultsPerTerm": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

Direct entity-ID lookup (skips searching):

```json
{
  "corpIds": ["40b979a6-db39-4d48-8cb3-a4f859cef9a6"],
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `searchTerms` | array | Company/business names or keywords to search for. |
| `corpIds` | array | PNG IPA entity GUIDs (from a prior run's `CorpId`, or an `EntityProfile.aspx?id=...` URL) for a direct profile lookup, bypassing search. |
| `fetchProfiles` | boolean | When on (default), also fetches the full profile for every search match. When off, returns only the lightweight search-result fields. |
| `entityTypeId` | string (select) | Optional: restrict search to one entity type (Companies, Business Names, Associations, ...). |
| `maxResultsPerTerm` | integer | Max matching entities returned per search term. Default 20, max 200 — common words can match tens of thousands of entities. |
| `maxConcurrency` | integer | How many search terms / entity IDs to process in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

At least one of `searchTerms` or `corpIds` is required.

## Output

**Search result enriched with full profile** (`fetchProfiles: true`, the default) — real output for `searchTerms: ["Oil Search"]`, `CorpFilings` truncated here for readability:

```json
{
  "_input": "Oil Search",
  "_source": "S1-searchcorp+profile",
  "_scrapedAt": "2026-08-26T17:36:40Z",
  "CorpId": "6323da00-a93b-4397-9d27-47b854990822",
  "Name": "MARKHAM VALLEY RENEWABLES LIMITED",
  "NameMatch": "OIL SEARCH (P'NYANG) LIMITED",
  "RegistrationNumber": "1-86417",
  "RegistrationDateFormatted": "21/12/2012",
  "Type": "Companies",
  "Status": "Registered",
  "PriorNames": ["OIL SEARCH (P'NYANG) LIMITED", "MARKHAM VALLEY POWER LIMITED"],
  "BusinessActivities": ["C - MINING AND QUARRYING"],
  "RegisteredOfficerAddress": "GROUND FLOOR, HARBOURSIDE EAST BUILDING STANLEY ESPLANADE, PORT MORESBY, MORESBY SOUTH DISTRICT, NATIONAL CAPITAL DISTRICT (PORT MORESBY), PAPUA NEW GUINEA",
  "ReportDueDateFormatted": "30/06/2027",
  "Corp": {
    "CompanyName": "MARKHAM VALLEY RENEWABLES LIMITED",
    "RegistrationNumber": "1-86417",
    "CompanyType": "Companies",
    "Status": "Registered",
    "TotalShares": 1,
    "AnnualReturnDueDateFormatted": "30/06/2027",
    "RegisteredOfficeAddress": {
      "AddressType": "Registered Office",
      "Street1": "GROUND FLOOR",
      "Street2": "HARBOURSIDE EAST BUILDING STANLEY ESPLANADE",
      "City": "PORT MORESBY",
      "State": "NATIONAL CAPITAL DISTRICT (PORT MORESBY)",
      "Country": "PAPUA NEW GUINEA"
    },
    "PostalAddress": { "Street1": "PO BOX 842", "City": "PORT MORESBY", "Zip": "121", "...": "..." },
    "EmailAddress": "COMPANY.SECRETARY@SANTOS.COM",
    "HasOwnConstitution": true,
    "...": "... ~60 more raw upstream fields"
  },
  "CorpFilings": [
    { "CorpFilingType": "Annual return", "ReceivedDateFormatted": "30/06/2026", "CorpFilingTypeAndFormNumber": "AR-1 - Annual return" },
    { "CorpFilingType": "Notice of change of director and change in particulars of director", "ReceivedDateFormatted": "18/11/2025", "CorpFilingTypeAndFormNumber": "D-1 - Notice of change of director and change in particulars of director" },
    { "CorpFilingType": "Registration", "ReceivedDateFormatted": "21/12/2012", "CorpFilingTypeAndFormNumber": "Registration" }
    // ... 27 more filings total (annual returns + director/secretary/shareholder/name/address changes, each dated)
  ],
  "Activities": [{ "CorpActivityType": "C - MINING AND QUARRYING", "CorpActivityTypeId": 65 }],
  "Officers": [],
  "Directors": [],
  "Secretaries": [],
  "Shares": [],
  "Owners": [],
  "BeneficialOwners": [],
  "IsAuthorized": false,
  "IsLoggedin": false
}
```

**Search-only record** (`fetchProfiles: false`) — one lightweight record per match, no extra requests:

```json
{
  "_input": "Air Niugini",
  "_source": "S1-searchcorp",
  "_scrapedAt": "2026-08-26T17:31:47Z",
  "CorpId": "1bff9611-fde0-44f9-8a9c-3d990ef67f23",
  "Name": "AIR NIUGINI",
  "RegistrationNumber": "6-60515",
  "RegistrationDateFormatted": "06/12/2006",
  "Type": "Business Names",
  "Status": "Not Yet Updated - Lapsed",
  "PriorNames": [],
  "BusinessActivities": ["OTHER"],
  "RegisteredOfficerAddress": "4TH FLOOR, AIR NIUGINI HAUS JACKSONS, 7 MILE, NATIONAL CAPITAL DISTRICT (PORT MORESBY), PAPUA NEW GUINEA"
}
```

**Not-found record** (invalid/nonexistent `corpIds` entry):

```json
{
  "_input": "00000000-0000-0000-0000-000000000000",
  "_source": "none",
  "_scrapedAt": "2026-08-26T17:34:36Z",
  "_error": "not_found"
}
```

**No-match record** (search term matched nothing):

```json
{
  "_input": "ZZZQQQNOTFOUNDXYZ123ABCDEF",
  "_source": "none",
  "_scrapedAt": "2026-08-26T17:35:00Z",
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
| `Officers` / `Directors` / `Secretaries` / `Shares` / `Owners` / `BeneficialOwners` | Always empty for anonymous access — see "What this actor does NOT include" above. |
| `_error` | Present only on failed lookups: `not_found` (invalid entity ID), `no_results` (search term matched nothing), or `blocked_or_transient` (network/token issue). |

## Notes

- Full technical write-up of the registry's internal JSON API and the anti-CSRF token mechanism is in `CRAWLING_METHOD.md`.
- The registry also hosts a Personal Property Securities Registry ("PPSR Search") on the same domain — out of scope for this actor.
