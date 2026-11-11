# TopJobs.lk Scraper

Search Sri Lanka's leading job board, TopJobs.lk, by keyword or category and get back full job details — location, closing date, job-type badges, description image, and employer contact info.

## Why use this actor

- No account, login, or API key required
- Search by free-text keyword or browse any of the site's 30 job categories
- Every result can be hydrated into a full job record with one extra request per job
- Automatic pagination up to the number of results you ask for
- Also works the other way: give it specific job links and it fetches full detail for exactly those

## How it works

Pick a `mode`:
1. **`search`** (default) — searches job titles by keyword, or browses one category, and returns full job details for each match, with pagination handled automatically.
2. **`detail`** — fetches full detail for one or more specific job URLs you already have.

You don't need to manage any browsers or automatic retries — just provide a keyword or a list of job links.

**Important:** on TopJobs.lk's own site, category browsing and keyword search are mutually exclusive — if you set `functionalArea`, `keyword` is ignored. Filter checkboxes (`government`, `ngo`, `partTime`, `walkIn`, `foreign`, `internship`) combine fine with `keyword`, just not with `functionalArea`.

## Input

**Keyword search (default mode):**
```json
{
  "mode": "search",
  "keyword": "accountant",
  "maxResults": 50,
  "fetchFullDetails": true,
  "maxConcurrency": 4
}
```

**Browse a category:**
```json
{
  "mode": "search",
  "functionalArea": "SDQ",
  "maxResults": 50
}
```

**Job detail by URL:**
```json
{
  "mode": "detail",
  "jobUrl": "https://topjobs.lk/employer/JobAdvertismentServlet?rid=0&ac=DEFZZZ&jc=0001541016&ec=DEFZZZ&pg=applicant/vacancybyfunctionalarea.jsp"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"search"` (default) or `"detail"`. |
| `keyword` | string | `search` mode — free-text search (e.g. `"accountant"`, `"software engineer"`). Leave empty to list all currently open vacancies. Ignored if `functionalArea` is set. |
| `functionalArea` | string | `search` mode — browse one of 30 job categories instead of a keyword search (e.g. `SDQ` = IT-Software, `ACA` = Accounting/Auditing/Finance). Overrides `keyword` when set. |
| `government` / `ngo` / `partTime` / `walkIn` / `foreign` / `internship` | boolean | `search` mode — optional filter checkboxes, combine with `keyword` (not with `functionalArea`). |
| `maxResults` | integer | `search` mode — max jobs to return, pagination followed automatically (1000/page). Default 50. |
| `fetchFullDetails` | boolean | `search` mode — when on (default), each result includes full location/closing-date/job-type/description-image/contact data (one extra request per job). Turn off for a faster run that only needs title, employer, town, and dates. |
| `jobUrl` / `jobUrls` | string / array | `detail` mode — a job's full topjobs.lk detail URL (from this actor's own `detailUrl` search-result field, or copied from the site). |
| `maxConcurrency` | integer | How many detail requests run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Search mode (`fetchFullDetails: true`, default)** — real output:
```json
{
  "_input": "keyword:accountant",
  "_source": "S1-detail-html",
  "_scrapedAt": "2026-08-26T03:11:27Z",
  "position": "Assistant Accountant / Senior Finance Executive / Finance Executive",
  "employer": "Sentab Groups",
  "location": "Piliyandala, Sri Lanka",
  "jobRefNo": "1541016",
  "closingDate": "08/09/2026",
  "jobType": ["Full Time", "Permanent", "Onsite"],
  "descriptionImageUrl": "https://topjobs.lk/logo/DEFZZZ/6044cKKKHH.png",
  "companyLogoUrl": "https://topjobs.lk/logo/defzzz_small.gif",
  "companyWebsite": null,
  "companyEmail": "careers@sentab.lk",
  "jobSpecCode": "0001541016",
  "jsonLd": {
    "@context": "http://schema.org/",
    "@type": "JobPosting",
    "description": "Please refer the full details of the job posting as given by the employer. </br>...",
    "title": "Assistant Accountant / Senior Finance Executive / Finance Executive",
    "validThrough": "2026-09-08T00:00:00+0530",
    "datePosted": "2026-08-26",
    "hiringOrganization": { "@type": "Organization", "name": "Sentab Groups" },
    "jobLocation": [{ "@type": "Place", "address": { "@type": "PostalAddress", "addressLocality": "Piliyandala", "addressCountry": "LK", "addressRegion": "Western" } }]
  },
  "jc": "0001541016",
  "ac": "DEFZZZ",
  "ec": "DEFZZZ",
  "detailUrl": "https://topjobs.lk/employer/JobAdvertismentServlet?rid=0&ac=DEFZZZ&jc=0001541016&ec=DEFZZZ&pg=applicant/vacancybyfunctionalarea.jsp"
}
```

**Search mode (`fetchFullDetails: false`)** — compact result, no extra request per job:
```json
{
  "_input": "keyword:sales",
  "_source": "S1-search-html",
  "_scrapedAt": "2026-08-26T03:11:30Z",
  "jobRefNo": "1541173",
  "position": "Sales Associate",
  "employer": "L.K.Group Holdings Pvt Ltd",
  "town": "Nugegoda",
  "openingDate": "Wed Aug 26 2026",
  "closingDate": "Wed Sep 09 2026",
  "jc": "0001541173",
  "ac": "DEFZZZ",
  "ec": "DEFZZZ",
  "detailUrl": "https://topjobs.lk/employer/JobAdvertismentServlet?rid=0&ac=DEFZZZ&jc=0001541173&ec=DEFZZZ&pg=applicant/vacancybyfunctionalarea.jsp"
}
```

| Field | Type | Description |
|---|---|---|
| `position` | string | Job title. |
| `employer` | string | Employer name — may read as "Company Name Withheld" when the employer chose to stay anonymous. |
| `town` / `location` | string | `town` on compact search records, `location` (town + country) on full-detail records. |
| `closingDate` / `openingDate` | string | Application deadline / listing date, as displayed on site (format varies by record type). |
| `jobType` | array | Full-detail records only — 0-3 dynamic badges, e.g. `["Full Time", "Permanent", "Onsite"]` or `["Part Time"]`. |
| `descriptionImageUrl` | string | Full-detail records only — see **Known limits**: TopJobs.lk publishes the actual job description as an image, not text. |
| `companyEmail` / `companyWebsite` | string | Full-detail records only — employer's public contact info, when supplied. |
| `jsonLd` | object | Full-detail records only, and only present on roughly half of jobs (a site quirk) — the raw schema.org JobPosting block. |
| `detailUrl` | string | Canonical job URL — feed this back into `detail` mode to re-fetch it directly. |

A record with `_error` instead means that lookup couldn't complete (e.g. `"_error": "not_found"` for an expired/invalid job URL).

## Known limits

- **No extractable plain-text job description.** TopJobs.lk employers upload a designed ad graphic instead of filling in a text field — every job sampled during development had its actual requirements/responsibilities rendered as an image (`descriptionImageUrl`), not text. This is the site's real publishing model, not a gap in this actor.
- **Category browsing (`functionalArea`) and `keyword` can't be combined** — a site-side limitation, confirmed live. Use one or the other; filter checkboxes work with `keyword`.
- **`detail` mode needs the full job URL**, not just a reference number — there's no shorter `job/<id>` shortcut on the site itself. Always use this actor's own `detailUrl` output field, or copy the URL directly from TopJobs.lk.
