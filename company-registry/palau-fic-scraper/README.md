# Palau Business Registry Scraper

Search the Republic of Palau's official company registry — the **Business
Entities Registry** run by the Financial Institutions Commission (FIC) at
`palauregistries.pw` — by company name, or look up a specific entity by its
registry ID. No account, login, or API key needed.

## Why use this actor

- Searches Palau's real, government-operated company registry — registration
  number, status, entity type (Palau For Profit Corporation, Foreign For
  Profit Corporation, Palau Nonprofit Corporation, Foreign Nonprofit
  Corporation), registered office/postal address, and business activities
- **Also returns real directors, officers, shareholders, share allotments,
  and filing history for free, with no login** — including each director's
  and officer's own residential address
- No account, login, or CAPTCHA required — the public search is free and
  open, exactly as the registry's own site states
- Look up a specific entity directly by its registry ID (`corpIds`) once you
  know it, e.g. from a previous run
- Automatic retries on temporary network hiccups
- Palau's registry launched brand-new in January 2025 alongside a new
  Corporations Act — one of the newest online business registries in the
  Pacific

## What this actor does NOT include

`Secretaries`, `Owners`, `BeneficialOwners`, `Mortgages`, and `Documents`
came back as **empty arrays** on the entity tested during development — this
may reflect a stricter gate on those specific record types, or simply no
data on file for the sample checked; it wasn't possible to tell without a
login this actor deliberately never attempts (no-login policy). These
fields are still included on every profile record, passed through exactly
as upstream returns them, rather than hidden.

## How it works

1. Give the actor one or more company name search terms, or one or more
   entity IDs (`corpIds`) if you already know them.
2. For each search term, the actor queries the registry and returns every
   matching entity (up to your configured cap).
3. By default it also fetches the full profile (addresses, directors,
   officers, shareholders, filing history) for every match — turn
   `fetchProfiles` off for a faster, lighter-weight name-only search.
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
  "corpIds": ["0668ffe3-79c4-4d9e-866c-48c385ed97f6"],
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `searchTerms` | array | Company/business names or keywords to search for. |
| `corpIds` | array | Palau Registry entity GUIDs (from a prior run's `CorpId`, or an `EntityProfile.aspx?id=...` URL) for a direct profile lookup, bypassing search. |
| `fetchProfiles` | boolean | When on (default), also fetches the full profile for every search match. When off, returns only the lightweight search-result fields. |
| `entityTypeId` | string (select) | Optional: restrict search to one entity type (Palau/Foreign For Profit Corporation, Palau/Foreign Nonprofit Corporation). |
| `maxResultsPerTerm` | integer | Max matching entities returned per search term. Default 20, max 200. |
| `maxConcurrency` | integer | How many search terms / entity IDs to process in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

At least one of `searchTerms` or `corpIds` is required.

## Output

**Direct entity-ID lookup, full profile** (real output for `corpIds:
["0668ffe3-79c4-4d9e-866c-48c385ed97f6"]` — "ASIA PACIFIC COMMERCIAL BANK,
INC." — arrays truncated here for readability):

```json
{
  "Corp": {
    "CorpId": "0668ffe3-79c4-4d9e-866c-48c385ed97f6",
    "CompanyName": "ASIA PACIFIC COMMERCIAL BANK, INC.",
    "RegistrationNumber": "10000895",
    "CompanyType": "Palau For Profit Corporation",
    "Status": "Active",
    "RegistrationDateFormatted": "11/02/1999",
    "TotalShares": 1380000,
    "AnnualReturnDueDateFormatted": "11/30/2026",
    "RegisteredOfficeAddress": {
      "AddressType": "Registered Office",
      "State": "KOROR",
      "Village": "NGERBECHED HAMLET",
      "Zip": "96940",
      "Country": "PALAU",
      "Name": "FLORENCIA RIROU"
    },
    "PostalAddress": { "Street1": "P.O. BOX 600", "State": "KOROR", "Country": "PALAU" },
    "...": "... ~40 more raw upstream fields"
  },
  "Directors": [
    {
      "OfficerType": "Director",
      "FullName": "MR. LIM THIAM HUAT",
      "Nationality": "Malaysia",
      "AppointmentDateFormatted": "11/02/1999",
      "Address": {
        "AddressType": "Residential Address",
        "Street1": "LEVEL 6-02 MENARA LGB",
        "Street2": "NO. 1 JALAN WAN KADIR",
        "State": "TAMAN TUN DR ISMAIL",
        "Village": "KUALA LUMPUR",
        "Country": "MALAYSIA"
      }
    },
    { "...": "... 3 more directors" }
  ],
  "Officers": [
    { "OfficerType": "Officer", "OfficerTitles": [{ "CorpOfficerTitle": "President" }], "FullName": "MR. LIM THIAM HUAT", "...": "... same address richness as Directors" }
  ],
  "Members": [
    { "OfficerType": "Shareholder", "FullName": "MS. LIM KAH YEN", "Nationality": "Malaysia", "...": "... 2 more shareholders" }
  ],
  "ShareAllotments": [ { "Shareholders": [ "... same shareholder records" ] } ],
  "Addresses": [ { "AddressType": "Principal Place Of Business", "Street1": "UNIT 1A-105", "Street2": "TSUNEO PROFESSIONAL BUILDING", "...": "... 1 more" } ],
  "CorpFilings": [ { "DocumentNumber": "60490015", "ReceivedDateFormatted": "02/25/2025", "ProcessedDateFormatted": "03/03/2025" } ],
  "Secretaries": [],
  "Owners": [],
  "BeneficialOwners": [],
  "IsAuthorized": false,
  "IsLoggedin": false,
  "_input": "0668ffe3-79c4-4d9e-866c-48c385ed97f6",
  "_source": "S2-profile-direct",
  "_scrapedAt": "2026-08-27T01:47:39Z"
}
```

**Search-only record** (`fetchProfiles: false`) — one lightweight record per
match, no extra requests; real output for `searchTerms: ["Bank"]`:

```json
{
  "_input": "Bank",
  "_source": "S1-searchcorp",
  "_scrapedAt": "2026-08-27T01:47:18Z",
  "CorpId": "0668ffe3-79c4-4d9e-866c-48c385ed97f6",
  "Name": "ASIA PACIFIC COMMERCIAL BANK, INC.",
  "RegistrationNumber": "10000895",
  "RegistrationDateFormatted": "11/02/1999",
  "Type": "Palau For Profit Corporation",
  "Status": "Active",
  "PriorNames": [],
  "BusinessActivities": ["Financial Institution"]
}
```

**Not-found record** (invalid/nonexistent `corpIds` entry):

```json
{
  "_input": "00000000-0000-0000-0000-000000000000",
  "_source": "none",
  "_scrapedAt": "2026-08-27T01:47:39Z",
  "_error": "not_found"
}
```

**No-match record** (search term matched nothing):

```json
{
  "_input": "zzzznonexistentxyz999",
  "_source": "none",
  "_scrapedAt": "2026-08-27T01:47:45Z",
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
| `Directors` / `Officers` / `Members` / `ShareAllotments` | Real director/officer/shareholder names, nationality, appointment dates, and residential addresses — populated with no login required. |
| `Secretaries` / `Owners` / `BeneficialOwners` / `Mortgages` / `Documents` | Empty on the entity tested for anonymous access — see "What this actor does NOT include" above. |
| `_error` | Present only on failed lookups: `not_found` (invalid entity ID), `no_results` (search term matched nothing), or `blocked_or_transient` (network/token issue). |

## Notes

- Full technical write-up of the registry's internal JSON API and the
  anti-CSRF token mechanism is in `CRAWLING_METHOD.md`.
- The registry also hosts a Personal Property Securities Registry and
  separate Name Availability / Name Reservation search pages on the same
  domain — out of scope for this actor.
- This is the same Foster-Moore-derived platform already in this portfolio
  as `png-ipa-scraper`, `tonga-mcctil-scraper`, `fiji-roc-scraper`, and
  `solomonislands-sbr-scraper`.
