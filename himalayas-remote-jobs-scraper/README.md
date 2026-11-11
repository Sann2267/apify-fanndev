# Himalayas Remote Jobs Scraper

Pull remote job listings from Himalayas with the full description, the salary range and pay
period, the seniority levels, the countries the role is open to, and the timezones it expects
you to work in. Over 100,000 live listings, filterable by title, skill, category, level,
location, currency or salary.

## Why use this actor

- **Salaries you can actually compare.** The source mixes hourly, weekly, monthly and annual
  pay in the same fields. Every record also gets a yearly-equivalent figure, so a `$55/hour`
  role and a `$140,000/year` role sort against each other correctly — and the salary filter
  uses those figures, not the raw ones.
- **Real filtering.** Filter by job title, words in the description (handy for skills like
  Kubernetes or Figma), category, seniority, employment type, location, currency and salary.
- **Full job descriptions** in both HTML and plain text, ready for search or a language model.
- **A "who is hiring" view** that collapses listings into one row per company, with how many
  roles each is advertising and the salary band across them.
- **No account, no login and no API key**, and no proxy needed.
- **Honest counts.** Every record says how many listings the run read to find it, so a short
  result is never a mystery.

## How it works

1. You choose a mode and, if you want, some filters.
2. The actor reads the newest listings from the source and keeps the ones matching your filters.
3. Results stream into your dataset — download as JSON, CSV or Excel, or load into a database.

Run it on a schedule to build a history of who is hiring for what, and at what pay.

## Modes

| Mode | What it does |
| --- | --- |
| `jobs` | The newest remote jobs, straight from the feed |
| `search` | The same feed, narrowed by your filters |
| `companies` | One row per employer: how many roles, which levels, what salary band |
| `reference` | Check the source is live and report what it returns |

## Input

```json
{
  "mode": "search",
  "titleContains": ["engineer"],
  "parentCategories": ["Developer"],
  "seniority": ["Senior"],
  "locationRestrictions": ["United States"],
  "currency": ["USD"],
  "minSalary": 120000,
  "salariedOnly": true,
  "maxItems": 100,
  "maxScannedJobs": 2000,
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `jobs` (default), `search`, `companies` or `reference`. |
| `titleContains` | array | Keep jobs whose title contains any of these words. |
| `companyContains` | array | Keep jobs from companies whose name contains any of these words. |
| `descriptionContains` | array | Keep jobs whose description mentions any of these words — good for skills and tools. |
| `categories` | array | Detailed role tags, e.g. `Machine-Learning`. |
| `parentCategories` | array | Broad families, e.g. `Developer`, `Data Science`, `Sales`, `Design`. |
| `seniority` | array | `Entry-level`, `Mid-level`, `Senior`, `Manager`, `Lead`. |
| `locationRestrictions` | array | Keep roles restricted to these places. Roles open worldwide list no restriction and will not match. |
| `employmentType` | array | `Full Time`, `Contractor`, `Part Time`. |
| `salaryPeriod` | array | `annual`, `hourly`, `monthly`, `weekly`. |
| `currency` | array | `USD`, `EUR`, `INR`, `CAD`, `PLN`, `PHP`. Worth setting whenever you filter by salary. |
| `minSalary` / `maxSalary` | integer | Yearly pay bounds. Hourly, weekly and monthly rates are converted to a yearly equivalent first. Not converted between currencies. |
| `salariedOnly` | boolean | About half the feed publishes no salary. Turn this on to drop those. |
| `maxItems` | integer | Maximum records per run. Default 100. |
| `maxScannedJobs` | integer | How deep into the feed to go. Raise it when a narrow search comes back short. Default 2000. |
| `proxyConfiguration` | object | Off by default — the source needs no proxy. |

## Output

Real output from `mode: "search"` (description and long arrays truncated):

```json
{
  "title": "Cybersecurity Engineer- Junior level",
  "companyName": "CACI International Inc",
  "companySlug": "caci-international-inc",
  "companyLogo": "https://cdn-images.himalayas.app/3dlhn0q4j5q3ax2oqnoh9nstwpza",
  "companyUrl": "https://himalayas.app/companies/caci-international-inc",
  "employmentType": "Full Time",
  "seniority": ["Entry-level"],
  "minSalary": 63300,
  "maxSalary": 129700,
  "salaryPeriod": "annual",
  "currency": "USD",
  "salaryText": "USD 63,300 - 129,700 annual",
  "annualizedSalaryMin": 63300.0,
  "annualizedSalaryMax": 129700.0,
  "annualizedFrom": "annual",
  "locationRestrictions": ["United States"],
  "timezoneRestrictions": [-10, -9, -8, -7, "... 7 more"],
  "categories": ["Cybersecurity-Engineering", "Network-Security", "Information-Assurance", "... 5 more"],
  "parentCategories": [],
  "excerpt": "Job Title: Cybersecurity Engineer- Junior levelJob Category: Information TechnologyTime Type: Full timeMinimum Clearance Required to Start: Secret...",
  "description": "Job Title: Cybersecurity Engineer- Junior levelJob Category: Information Technology... (truncated)",
  "descriptionText": "Job Title: Cybersecurity Engineer- Junior levelJob Category: Information Technology... (truncated)",
  "pubDate": 1789677507,
  "pubDateIso": "2026-09-17T20:38:27Z",
  "expiryDate": 1794620187,
  "expiryDateIso": "2026-11-14T01:36:27Z",
  "applicationLink": "https://himalayas.app/companies/caci-international-inc/jobs/cybersecurity-engineer-junior-level",
  "jobUrl": "https://himalayas.app/companies/caci-international-inc/jobs/cybersecurity-engineer-junior-level",
  "guid": "https://himalayas.app/companies/caci-international-inc/jobs/cybersecurity-engineer-junior-level",
  "jobsScannedInRun": 29,
  "recordType": "JOB",
  "_input": "search",
  "_source": "himalayas-jobs-api",
  "_scrapedAt": "2026-09-18T05:17:22Z"
}
```

Real output from `mode: "companies"`:

```json
{
  "companySlug": "minfy-technologies",
  "companyName": "Minfy Technologies",
  "companyUrl": "https://himalayas.app/companies/minfy-technologies",
  "jobsSeen": 8,
  "jobTitles": [
    "Cloud Enterprise Architecture",
    "ANGULAR JS DEVELOPER",
    "Management Trainee",
    "Migration Engagement Manager",
    "Senior AWS  Engineer",
    "Cloud Solution Architect",
    "Devops Engineer",
    "Application Architect"
  ],
  "categories": ["Developer", "Management", "Sales"],
  "seniority": ["Entry-level", "Manager", "Mid-level", "Senior"],
  "locationRestrictions": ["United States"],
  "newestPubDateIso": "2026-09-17T20:38:20Z",
  "lowestAnnualizedSalarySeen": null,
  "highestAnnualizedSalarySeen": null,
  "jobsScannedInRun": 100,
  "recordType": "COMPANY",
  "_input": "companies",
  "_source": "himalayas-jobs-api",
  "_scrapedAt": "2026-09-18T05:18:37Z"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `title` / `excerpt` / `description` / `descriptionText` | string | The role, summarised and in full, as HTML and as plain text. |
| `companyName` / `companySlug` / `companyLogo` / `companyUrl` | string | The employer. |
| `employmentType` / `seniority` | string / array | Contract shape and the levels the role is open to. |
| `minSalary` / `maxSalary` / `salaryPeriod` / `currency` | number / string | Pay exactly as published. Read the numbers together with the period — they can be hourly. |
| `salaryText` | string | The salary as one readable line, e.g. `USD 63,300 - 129,700 annual`. |
| `annualizedSalaryMin` / `annualizedSalaryMax` / `annualizedFrom` | number / string | Yearly-equivalent pay, and which period it was derived from. |
| `locationRestrictions` / `timezoneRestrictions` | array | Where you may live, and which UTC offsets are expected. |
| `categories` / `parentCategories` | array | Detailed and broad role tags. |
| `pubDate` / `pubDateIso` / `expiryDate` / `expiryDateIso` | number / string | When it was posted and when it expires, as epoch seconds and ISO 8601. |
| `applicationLink` / `jobUrl` / `guid` | string | Where to apply and the listing page. On this source all three are the same URL. |
| `jobsScannedInRun` | integer | How many listings the run read — the denominator behind your matches. |
| `jobsSeen` / `jobTitles` | integer / array | Companies mode: how many of this employer's roles appeared in the scanned slice, and which. |
| `lowestAnnualizedSalarySeen` / `highestAnnualizedSalarySeen` | number | Companies mode: the yearly-equivalent salary band across those roles. `null` when none published pay. |
| `recordType` | string | `JOB`, `COMPANY`, `SURFACE` or `ERROR`. |

## Limits worth knowing before you run it

- **Filtering happens after fetching**, because the source ignores filter parameters. The
  actor reads listings 20 at a time and keeps the matches, so a narrow filter costs more
  requests than a broad one. `maxScannedJobs` is your budget, and `jobsScannedInRun` tells you
  what it spent. If a search returns fewer results than you expected, raise the budget.
- **Salary numbers are never converted between currencies.** Pair a salary filter with the
  `currency` filter, or you will be comparing rupees with dollars.
- **Roughly half the listings publish no salary at all.** Those are excluded from any
  salary-filtered result, because a missing salary can't be shown to clear a floor. Use
  `salariedOnly` to drop them everywhere.
- **`jobsSeen` in companies mode counts the scanned slice**, not the employer's total openings.
  Scan deeper for a fuller picture.
- **Only the public job feed is available.** The source's company and job web pages are closed
  to automated access, so company details here are assembled from the listings themselves.
