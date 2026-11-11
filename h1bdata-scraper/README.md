# H1B Visa Sponsor & Salary Database Scraper

Search the US Department of Labor's public H-1B sponsorship filing history by employer, job title, city, or year — real filed salaries, and (optionally) the full case record including sponsoring attorney and employer contact details. No account, login, or API key needed.

## Why use this actor

- Look up exactly what any US employer pays H-1B sponsored workers, by job title and location, sourced from official government filings
- Optional enrichment fetches the full case record per result: prevailing wage, wage level, worksite address, the employer's own point-of-contact name and email, and the sponsoring immigration attorney/law firm name and email — useful for recruiting, immigration research, or B2B outreach
- `caseDetail` mode looks up specific filings directly if you already have a case number
- No account, login, or API key required
- Stable JSON output, ready for spreadsheets, databases, or pipelines

## How it works

Pick a `mode`:
1. **`search`** — query filings by employer name, job title, worksite city, and/or fiscal year.
2. **`caseDetail`** — fetch the full record for specific case number(s) you already have.

## Input

**Search, lightweight (one row per filing):**
```json
{
  "mode": "search",
  "employer": "Stripe",
  "jobTitle": "",
  "city": "",
  "year": "2024",
  "maxResults": 200,
  "fetchCaseDetails": false
}
```

**Search, enriched with full case detail (wage, worksite, contacts):**
```json
{
  "mode": "search",
  "employer": "Stripe",
  "jobTitle": "",
  "city": "",
  "year": "2024",
  "maxResults": 50,
  "fetchCaseDetails": true
}
```

**Case detail, by case number:**
```json
{
  "mode": "caseDetail",
  "caseIds": ["I-200-21027-037298"]
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"search"` (default) or `"caseDetail"`. |
| `employer` | string | `search` mode — partial or full sponsor company name, e.g. `"Stripe"`. Case-insensitive substring match. h1bdata.info currently withholds results for some of the largest sponsors (Google, Meta, Amazon, Apple, …); those searches return an `upstream_withheld` error record instead of rows. |
| `jobTitle` | string | `search` mode — partial or full filed job title. Filed titles are sometimes lightly mangled by the source dataset — a short, common word works best. |
| `city` | string | `search` mode — worksite city. |
| `year` | string | `search` mode — a specific fiscal year (`"2012"`–`"2026"`) or `"All Years"`. Default `"All Years"`. At least one of `employer` / `jobTitle` / `city` is required. |
| `maxResults` | integer | `search` mode — max filings to return. Default 200. |
| `fetchCaseDetails` | boolean | `search` mode — when `true`, each result is additionally fetched for its full case record. When `false` (default), only the summary row is returned — much faster for large result sets. |
| `caseIds` | array | `caseDetail` mode — case numbers to look up directly, e.g. `"I-200-21027-037298"` (found in a search result's `caseId` field). |
| `maxConcurrency` | integer | How many case-detail records to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Search mode, `fetchCaseDetails: false`** — one lightweight record per filing (real captured output):
```json
{
  "_input": "em=Google|job=|city=|year=2024",
  "_source": "S1-search-summary",
  "_scrapedAt": "2026-08-30T17:44:17Z",
  "EMPLOYER": "GOOGLE LLC",
  "JOB_TITLE": "ACCESSIBILITY ANALYST",
  "BASE_SALARY": "105,000",
  "LOCATION": "MOUNTAIN VIEW, CA",
  "SUBMIT_DATE": "01/08/2024",
  "START_DATE": "01/25/2024",
  "caseId": "I-200-24008-624300",
  "caseUrl": "https://h1bdata.info/details.php?id=I-200-24008-624300"
}
```

**Search mode with `fetchCaseDetails: true`, or `caseDetail` mode** — full case record (real captured output, truncated):
```json
{
  "_input": "I-200-21027-037298",
  "_source": "S1-detail",
  "_scrapedAt": "2026-08-30T17:43:35Z",
  "LCA_CASE_NUMBER": "I-200-21027-037298",
  "STATUS": "Certified - Withdrawn",
  "LCA_CASE_SUBMIT": "2021-01-27",
  "DECISION_DATE": "2021-03-09",
  "VISA_CLASS": "H-1B",
  "LCA_CASE_JOB_TITLE": "SoftwareEngineer 1615.47781",
  "SOC_TITLE": "Software Developers, Applications",
  "FULL_TIME_POSITION": "True",
  "LCA_CASE_EMPLOYMENT_START_DATE": "2021-07-22",
  "END_DATE": "2024-07-21",
  "LCA_CASE_EMPLOYER_NAME": "Google LLC",
  "EMPLOYER_ADDRESS1": "1600 Amphitheatre Parkway",
  "EMPLOYER_CITY": "Mountain View",
  "EMPLOYER_STATE": "CA",
  "EMPLOYER_POC_EMAIL": "GITAMER@google.com",
  "AGENT_ATTORNEY_FIRST_NAME": "Soo",
  "AGENT_ATTORNEY_LAST_NAME": "Choi",
  "AGENT_ATTORNEY_EMAIL_ADDRESS": "GoogleDOL@balglobal.com",
  "LAWFIRM_NAME_BUSINESS_NAME": "Berry Appleman & Leiden LLP",
  "LCA_CASE_WAGE_RATE_FROM": "129000",
  "LCA_CASE_WAGE_RATE_UNIT": "Year",
  "PREVAILING_WAGE": "120578",
  "PW_WAGE_LEVEL": "II"
  ,"... 40 more fields": "worksite address, additional employer point-of-contact/attorney details, willful-violator flag, etc."
}
```

A record with `_error` instead of data means that lookup couldn't
complete — `"_error": "no_results"` (nothing matched the search),
`"_error": "case_not_found"` (invalid case number in `caseDetail` mode).
A record with `"_warning": "case_detail_unavailable"` in enriched search
mode means the summary row is real but its detail-page enrichment failed
for that one row specifically — the run still continues.

## Notes / limits

- Filed job titles come from the government dataset as-is and are
  sometimes auto-generated or lightly mangled — search with a short,
  common word rather than an exact long phrase for the best match rate.
- A very broad query (a large employer across `"All Years"`) can return
  tens of thousands of filings; `maxResults` caps the output, but for
  large employers we recommend picking a specific `year` for faster runs.
- Attorney and employer point-of-contact fields are only present on
  filings that actually used a representing attorney / listed a contact —
  they're simply absent from records where the filing didn't include one.
