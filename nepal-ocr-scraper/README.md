# Nepal Company Registrar (OCR) Scraper

Search Nepal's official company registry — the Office of the Company Registrar (OCR) — by company name (English or Nepali) or registration number, and get back each match's registration record: registration number, registration date, company type, registered address, and legal-hold status.

## Why use this actor

- No account, login, or API key needed — the registry search is open to the public
- Search by company name (English or Nepali script, partial names work) or by exact registration number
- Every result includes the registration number, registration date, full company-type classification, registered address, and whether the company is currently under a legal hold ("Rokka")
- Both English and Nepali (Devanagari) name/address fields are returned side by side
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more company names (English or Nepali) or OCR registration numbers to search for.
2. The actor searches the official registry and finds every matching company.
3. Each match's public registration record is returned as one row.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name or registration number format — a partial name works too, and the actor automatically detects whether you gave it a name or a registration number.

## Input

```json
{
  "queries": ["Hotel Everest", "350011"],
  "searchBy": "auto",
  "maxResultsPerQuery": 50,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company name (English or Nepali) or registration number to search for. |
| `queries` | array | Multiple names/registration numbers to search for in one run. |
| `searchBy` | string | `auto` (default) detects a digits-only query as a registration number and anything else as a company name. Set `companyName` or `registrationNumber` to force one field. |
| `maxResultsPerQuery` | integer | Maximum matched companies kept per query. Default 50, max 2000. A broad common-word search can match thousands of companies — see Notes below. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched company. This is the real, unedited output for `"Hotel Everest"`:

```json
{
  "companyNameNepali": "होटल एभरेष्ट भ्यु स्याङ्बोचे",
  "companyNameEnglish": "Hotel Everest View Syangboche",
  "companyRegistrationNumberEn": "361171",
  "companyRegistrationNumberNp": "३६११७१",
  "registrationDateBSEn": "2081-10-30",
  "registrationDateBSNp": "२०८१-१०-३०",
  "companyType": {
    "key": "PRIVATE_MULTIPLEPROPRIETOR_JOINTVENTUREWITHFOREIGNPROMOTERS",
    "valueEnglish": "Private >> Multiple Ownership >> Joint Venture Between Nepali and Foreign Investor",
    "valueNepali": "प्राइभेट >> बहुल >> नेपाली र विदेशी बिचको संयुक्त उपक्रम (जे.भी.)",
    "baseValue": "PRIVATE"
  },
  "companyTypeNp": "नेपाली र विदेशी बिचको संयुक्त उपक्रम (जे.भी.)",
  "companyTypeEn": "Joint Venture Between Nepali and Foreign Investor",
  "companyAddressEn": "Khumbu Pasanglhamu Rural Municipality-4,Solukhumbu",
  "companyAddressNp": "खुम्बु पासाङल्हामु गाउँपालिका-४,सोलुखुम्बु",
  "isRokka": false,
  "_input": "Hotel Everest",
  "_source": "S1-camis-search-company-details",
  "_scrapedAt": "2026-08-26T18:04:25Z"
}
```

A second real match from the same search shows a company currently under legal hold:

```json
{
  "companyNameEnglish": "HOTEL EVEREST INTERNATIONAL",
  "companyRegistrationNumberEn": "98138",
  "registrationDateBSEn": "2037-01-10",
  "companyTypeEn": "All Nepali (Public)",
  "companyAddressEn": "Kathmandu Metropolitan City-10,Kathmandu",
  "isRokka": true,
  "_input": "Hotel Everest",
  "_source": "S1-camis-search-company-details",
  "_scrapedAt": "2026-08-26T18:04:25Z"
}
```

Registration-number search (`"350011"`) returns the exact same record shape:

```json
{
  "companyNameEnglish": "Nepal Green Energy Company",
  "companyRegistrationNumberEn": "350011",
  "registrationDateBSEn": "2081-03-31",
  "companyTypeEn": "All Nepali Ownership",
  "companyAddressEn": "Kathmandu Metropolitan City-31,Kathmandu",
  "isRokka": false,
  "_input": "350011",
  "_source": "S1-camis-search-company-details",
  "_scrapedAt": "2026-08-26T18:04:32Z"
}
```

A query with no matches returns a clean error record instead of company fields:

```json
{ "_input": "zzzznonexistentxyz999", "_scrapedAt": "2026-08-26T18:04:32Z", "_error": "not_found" }
```

| Field | Description |
|---|---|
| `_input` | The query (name or registration number) you requested, for traceability. |
| `_source` | `S1-camis-search-company-details` on a successful match. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `companyNameEnglish` / `companyNameNepali` | Registered company name, English and Nepali. |
| `companyRegistrationNumberEn` / `companyRegistrationNumberNp` | Official OCR registration number, Arabic and Devanagari numerals. |
| `registrationDateBSEn` / `registrationDateBSNp` | Registration date in the Bikram Sambat calendar used by the Nepali government (not Gregorian — passed through as OCR records it). |
| `companyType` | Structured company-type classification (internal key, English/Nepali labels, and a base category such as `PRIVATE` or `PUBLIC`). |
| `companyTypeEn` / `companyTypeNp` | Short English/Nepali label for the same classification. |
| `companyAddressEn` / `companyAddressNp` | Registered office address (municipality/ward, district), English and Nepali. |
| `isRokka` | Whether the company is currently under a "Rokka" order — a legal freeze/injunction recorded against it (for example due to litigation or a dispute). |

A record with `_error` instead of company fields means that query didn't match anything (`"not_found"`) or hit a temporary network issue (`"blocked_or_transient"`).

## Notes

- The registry has no result cap of its own — a broad, common-word query can match thousands of companies. `maxResultsPerQuery` (default 50) caps how many are returned per query; narrow your search terms for more precise results.
- Only the basic registration record shown above is available without an account. Nepal's registry does not offer a public director/shareholder/capital-structure lookup — that detail is only visible after logging in to the official portal.
- Dates are in the Bikram Sambat calendar as recorded by the registry, not converted to the Gregorian calendar.
