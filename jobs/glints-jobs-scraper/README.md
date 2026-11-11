# Glints Jobs & Company Scraper

Extract job postings, employer profiles and hiring-market structure from **Glints**, the Southeast Asian job platform — across Indonesia, Singapore, Vietnam, Malaysia, the Philippines and Taiwan.

## Why use this actor

- **No account, no login, no API key** — every mode runs on public data
- **Salary data on most postings**, with the currency and pay period, not just a vague band
- **Full job descriptions**, required skills, benefits, interview process, workplace address and coordinates
- **Employer profiles with every open vacancy** in a single request
- **Reaches past the site's own 50-result search limit** via a whole-corpus crawl mode
- **Market intelligence built in** — which employers, cities and roles actually have postings for a keyword
- **Six markets from one actor**, with automatic retries and clean, stable JSON

## How it works

1. Pick a **mode** — search by keyword, pull full detail for specific jobs, profile an employer, or crawl the whole corpus.
2. Pick a **market** (Indonesia, Singapore, Vietnam, Malaysia, the Philippines or Taiwan) and, if you like, narrow with filters: salary, employment type, remote/hybrid/on-site, experience, education or how recently the job was posted.
3. The actor collects the data, retrying automatically on any hiccup.
4. Results stream into your dataset, ready to download as JSON, CSV or Excel.

You never manage scrapers, browsers, logins or accounts.

## Modes

| Mode | What you get | Good for |
| --- | --- | --- |
| `search` | Job cards matching your keywords and filters | Job boards, lead lists, daily new-vacancy alerts |
| `jobDetail` | Everything about specific postings: description, benefits, interview process, address | Enriching a shortlist |
| `company` | Employer profile **plus every open vacancy there** | Competitor hiring tracking |
| `similarJobs` | Glints' own related-jobs recommendations | Expanding a seed list |
| `sitemapCrawl` | The whole public corpus for a market | Full datasets, market-wide analysis |
| `filters` | Top employers, cities and roles for a keyword | Market research, talent mapping |
| `suggestions` | Autocomplete job titles and company names | Keyword research, discovering employers |
| `skills` | Glints' skill catalogue with the ids the search filter accepts | Building precise skill-filtered searches |

### Getting more than 50 results

Glints itself only shows the first page of search results to visitors who are not signed in, so **any one search returns at most 50 jobs**. Two ways around it, both built in:

- **Run several narrow searches.** Each keyword and filter combination is its own query. In testing, eight different slices of the same market returned **326 unique jobs** where a single search returned 50. The actor removes duplicates for you.
- **Use `sitemapCrawl`.** It works from the site's own public index and is not subject to the limit, so it reaches the full corpus — roughly 73,000 Indonesian postings plus around 54,000 aggregated ones.

## Input

```json
{
  "mode": "search",
  "countryCode": "ID",
  "searchTerms": ["data analyst", "software engineer"],
  "jobTypes": ["FULL_TIME"],
  "workArrangements": ["ONSITE", "HYBRID"],
  "lastUpdatedRange": "PAST_WEEK",
  "salaryMin": 8000000,
  "salaryCurrency": "IDR",
  "sortBy": "LATEST",
  "maxItems": 200,
  "pageSize": 50
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `search`, `jobDetail`, `company`, `similarJobs`, `sitemapCrawl`, `filters`, `suggestions` or `skills`. Default `search`. |
| `countryCode` | string | Market: `ID`, `SG`, `VN`, `MY`, `PH` or `TW`. Default `ID`. |
| `searchTerms` | array | Keywords. Used by `search`, `filters`, `suggestions` and `skills`. Each is a separate query; duplicates are removed across all of them. |
| `jobUrlsOrIds` | array | Job links or ids for `jobDetail` and `similarJobs`. Any public job link works. |
| `companyUrlsOrIds` | array | Company links or ids for `company`. |
| `maxItems` | integer | Stop after this many records. Default 100. Use 0 in `search` for no cap. |
| `pageSize` | integer | Results per search. Glints caps this at 50. Default 50. |
| `sortBy` | string | `RELEVANCY`, `LATEST` or `SALARY`. Switching this surfaces a different 50 jobs for the same keyword. |
| `jobTypes` | array | `FULL_TIME`, `PART_TIME`, `INTERNSHIP`, `CONTRACT`, `TEMPORARY`, `FREELANCE`, `DAILY`, `PROJECT_BASED`. |
| `workArrangements` | array | `ONSITE`, `HYBRID`, `REMOTE`. |
| `educationLevels` | array | From `PRIMARY_SCHOOL` through `DOCTORATE`. |
| `lastUpdatedRange` | string | `ANY_TIME`, `PAST_24_HOURS`, `PAST_WEEK`, `PAST_MONTH`. |
| `salaryMin` / `salaryMax` | integer | Pay band, in `salaryCurrency`. See the note below. |
| `salaryCurrency` | string | Must match the market — `IDR`, `SGD`, `VND`. Default `IDR`. |
| `minYearsOfExperience` / `maxYearsOfExperience` | integer | Required experience, in years. |
| `locationIds` / `categoryIds` / `companyIds` / `skillIds` | array | Filter by id. Run `filters` or `skills` first to discover them. |
| `includeExternalJobs` | boolean | Include postings Glints aggregates from other job boards. Default `true`. |
| `includeCompanyJobs` | boolean | In `company` mode, also emit each open vacancy. Default `true`. |
| `sitemapFetchDetails` | boolean | In `sitemapCrawl`, fetch full detail per job. Turn off for ids and links only. Default `true`. |
| `maxConcurrency` | integer | Parallel requests for the detail, company and sitemap modes. Default 5. |
| `proxyConfiguration` | object | Optional. Off by default — this actor does not need a proxy. |

> **Note on the salary filter:** Glints matches any posting whose advertised range *overlaps* your band, not one whose floor clears it. A job advertised at 3,500,000–5,000,000 will match `salaryMin: 5000000` because its ceiling touches your figure. Setting any salary filter also excludes postings that hide their pay. This matches what the Glints website itself shows.

## Output

### `search` mode

```json
{
  "_input": "data analyst",
  "_source": "S1-gql-searchJobsV3",
  "_scrapedAt": "2026-09-20T17:50:46Z",
  "recordType": "JOB",
  "id": "14ba92ef-c8bd-4224-b074-094b798d61b5",
  "title": "Data Analyst",
  "jobUrl": "https://glints.com/id/opportunities/jobs/data-analyst/14ba92ef-c8bd-4224-b074-094b798d61b5",
  "status": "OPEN",
  "type": "CONTRACT",
  "workArrangementOption": "ONSITE",
  "educationLevel": "BACHELOR_DEGREE",
  "minYearsOfExperience": 1,
  "maxYearsOfExperience": 3,
  "salaryMin": 6000000,
  "salaryMax": 11000000,
  "salaryCurrency": "IDR",
  "salaryMode": "MONTH",
  "shouldShowSalary": true,
  "companyName": "PT Abhimantra Sistem Solusindo",
  "companyUrl": "https://glints.com/id/companies/pt-abhimantra-sistem-solusindo/9eccff28-ba74-40db-9c94-19240809158f",
  "companyLogoUrl": "https://images.glints.com/unsafe/glints-dashboard/5def3a2317c48c882e611fdd45a19f1f.png",
  "companyIsVerified": true,
  "locationName": "Tebet",
  "countryCode": "ID",
  "categoryName": "Data Analyst",
  "categoryPath": "Computer & Software > Data > Data Analyst",
  "skillNames": ["Microsoft SQL Server", "Tableau", "Data Visualization", "Data Analysis"],
  "createdAt": "2025-11-05T10:48:39.76Z",
  "updatedAt": "2026-09-18T18:09:37.918Z",
  "jobSource": "EMPLOYER",
  "searchTerm": "data analyst",
  "_warning": "anon_page_1_only",
  "country": { "code": "ID", "name": "Indonesia" },
  "location": { "...": "full district / city / province / country chain with coordinates" },
  "company":  { "...": "full employer object" },
  "salaries": { "...": "every salary row, including allowances" },
  "skills":   { "...": "each skill with its id and whether it is mandatory" }
}
```

### `jobDetail` mode

Adds, on top of every field above:

```json
{
  "recordType": "JOB_DETAIL",
  "title": "Barista Toko Kopi: Area Depok",
  "descriptionText": "Kisaran Gaji 2,5jt\n\nDeskripsi Pekerjaan:\nMelakukan segala aktivitas dalam persiapan dan pembuatan minuman.\nMelayani customer dengan ramah baik driver online maupun customer dine-in.\n...\n\nPersyaratan:\nDisiplin, Jujur dan Berperilaku Baik\nBersedia Bekerja Dalam Shift\nDomisili Sekitar Depok Margonda",
  "interviewProcessText": null,
  "benefitTitles": ["Free Wi-Fi", "Perform Bonus"],
  "metadata": {
    "workingDaysPerWeek": 6,
    "requiresWeekendHolidays": false,
    "workShifts": ["REGULAR"]
  },
  "companyAddress": {
    "poi": {
      "addressLabel": "Jalan Kartini, Depok Kel., Pancoran Mas, Depok, 16431, Indonesia"
    }
  },
  "salaryEstimate": null,
  "expiryDate": "2026-10-21",
  "isActivelyHiring": false,
  "acceptsForeignApplications": false,
  "isCoverLetterMandatory": false,
  "screeningQuestionsEnabled": false,
  "externalApplyURL": null,
  "isHighResponseRate": false
}
```

### `filters` mode

```json
{
  "recordType": "SEARCH_FACETS",
  "searchTerm": "perawat",
  "countryCode": "ID",
  "topCompanyNames": ["Hydro Medical", "IMMODERMA Skin Clinic", "PT Citramed Indonesia", "... 7 more"],
  "topJobRoleNames": ["Dental Assistant", "Physiotherapist", "Midwife", "Nurse", "Doctor", "... 5 more"],
  "topLocationNames": ["Kuta", "Tebet", "Dukuh Pakis", "Menteng", "Grogol Petamburan", "... 15 more"],
  "currencies": ["IDR"],
  "hasRemoteJobs": true,
  "jobTypes": ["FULL_TIME", "CONTRACT", "INTERNSHIP", "PROJECT_BASED", "PART_TIME"],
  "yearsOfExperienceRanges": ["NO_EXPERIENCE", "FRESH_GRAD", "LESS_THAN_A_YEAR", "... 4 more"]
}
```

A keyword search for nurses returns clinics, medical roles and the districts hiring them — the facets are scoped to your keyword, not a global top list.

### Output fields

| Field | Type | Description |
|---|---|---|
| `_input` | string | The search term, link or id this row came from. |
| `_source` | string | Which call produced the row. |
| `_scrapedAt` | string | UTC timestamp for this row. |
| `recordType` | string | `JOB`, `JOB_DETAIL`, `COMPANY`, `SEARCH_FACETS`, `SUGGESTION`, `SKILL` or `ERROR`. |
| `_warning` | string | `anon_page_1_only` means more results exist than one search can reach. |
| `id`, `title`, `jobUrl` | string | Posting identity and public link. |
| `status`, `type`, `workArrangementOption` | string | Lifecycle state, employment type, on-site/hybrid/remote. |
| `salaryMin`, `salaryMax`, `salaryCurrency`, `salaryMode` | number / string | Headline pay, flattened for spreadsheets. `salaryMode` is the period — compare figures only within one period. |
| `shouldShowSalary` | boolean | `false` means the employer hid the pay; empty salary fields are their choice, not a gap in the data. |
| `companyName`, `companyUrl`, `companyLogoUrl`, `companyIsVerified` | string / boolean | Employer identity. |
| `locationName`, `countryCode`, `location` | string / object | Workplace location, down to district with coordinates. |
| `categoryName`, `categoryPath` | string | Job category and its full chain. |
| `skillNames`, `skills` | array | Required and preferred skills. |
| `minYearsOfExperience`, `maxYearsOfExperience`, `educationLevel` | number / string | Candidate requirements. |
| `createdAt`, `updatedAt`, `expiryDate` | string | Posting timeline. |
| `jobSource` | string | `EMPLOYER` for postings made on Glints, `SOURCED` for ones aggregated from other boards. |
| `externalApplyURL` | string | For aggregated postings, where the application actually goes. |
| `descriptionText` | string | Full job description as readable text (detail modes). |
| `benefitTitles`, `benefits` | array | Benefits offered (detail modes). |
| `jobCount`, `size`, `website`, `tagline`, `cultureText` | mixed | Employer fields on `COMPANY` rows. |
| `_error`, `_errorDetail` | string | On failure rows only — see below. |

## Error rows

Every input produces a row. If something cannot be fetched you get a row saying so, rather than a silent gap:

| `_error` | Meaning |
|---|---|
| `not_found` | The job or company id is valid but the posting no longer exists. |
| `unparsable_input` | No Glints id could be read from the value you supplied. |
| `no_results` | The query was valid and returned nothing. |
| `login_required` | Glints walls this slice behind an account. |
| `*_failed` | The request could not be completed after all retries. |

## Good to know

- Indonesia carries by far the largest corpus; Taiwan and the Philippines are much smaller.
- Around 40% of search results publish a salary with no filter applied. Adding a salary filter raises that to nearly all results, because postings that hide pay are excluded.
- Aggregated (`SOURCED`) postings are a large share of the corpus and link out to the original board.
- Recruiters' personal names and activity are deliberately not collected. Hiring responsiveness is reported as posting-level signals instead.

## Other actors

Browse the full collection of job-board, marketplace and social scrapers on the publisher's Apify Store page.
