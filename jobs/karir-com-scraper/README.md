# Karir.com Scraper

Search Indonesian job listings on Karir.com by keyword and get back full job details — requirements, responsibilities, salary range, and company info.

## Why use this actor

- No account, login, or API key required
- Full job requirements and responsibilities text, not just a title and a link
- Salary range when the employer discloses it
- Company profile (industry, description, subscriber count) included with every job
- Automatic pagination up to the number of results you ask for
- Also works the other way: give it specific job links or IDs and it fetches full detail for exactly those

## How it works

Pick a `mode`:
1. **`search`** — searches job titles by keyword and returns full job details for each match, with pagination handled automatically.
2. **`detail`** — fetches full detail for one or more specific job IDs/URLs you already have.

You don't need to manage any browsers or automatic retries — just provide a keyword or a list of job links.

## Input

**Keyword search (default mode):**
```json
{
  "mode": "search",
  "keyword": "marketing",
  "sortOrder": "newest",
  "maxResults": 50,
  "fetchFullDetails": true,
  "maxConcurrency": 4
}
```

**Job detail by URL/ID:**
```json
{
  "mode": "detail",
  "opportunityId": "https://karir.com/opportunities/1401468"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"search"` (default) or `"detail"`. |
| `keyword` | string | `search` mode — searches job titles (e.g. `"marketing"`, `"sales"`, `"programmer"`). Leave empty to list all currently active jobs. |
| `sortOrder` | string | `search` mode — `newest` (default), `priority`, `popular`, or `highest_salary`. |
| `maxResults` | integer | `search` mode — max jobs to return, pagination followed automatically. Default 50. |
| `fetchFullDetails` | boolean | `search` mode — when on (default), each result includes full requirements/responsibilities/salary/company data (one extra request per job). Turn off for a faster run that only needs title, company, location, salary range, and posted date. |
| `minSalary` / `maxSalary` | integer | `search` mode — optional salary filter (IDR). |
| `level` / `workplace` | string | `search` mode — optional filters, as shown in Karir.com's own search filters. |
| `locationIds` / `jobFunctionIds` / `industryIds` / `degreeIds` / `companyIds` | array | `search` mode — optional advanced filters using Karir.com's own numeric filter IDs. |
| `opportunityId` / `opportunityIds` | string / array | `detail` mode — a job's numeric ID or its full `karir.com/opportunities/...` URL. |
| `maxConcurrency` | integer | How many detail requests run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Search mode (`fetchFullDetails: true`, default)** — real output, truncated for readability:
```json
{
  "_input": "keyword:marketing",
  "_source": "S1-detail-api",
  "_scrapedAt": "2026-08-26T02:28:09Z",
  "id": 1401222,
  "job_position": "Venture Capital Officer (Marketing)",
  "location": "Denpasar",
  "address": "Jl. Tukad Badung No 126A, Renon Denpasar Selatan, Bali 80226",
  "requirements": "<ul><li>Pendidikan Minimal D3 Semua Jurusan</li><li>Memiliki Pengalaman Bekerja Minimal 2 Tahun sebagai Account Officer...</li></ul>",
  "responsibilities": "<p></p><ul><li>Membuat rencana pemasaran pembiayaan harian untuk pencapaian target</li>...</ul>",
  "salary_info": "LABEL_COMPETITIVE_SALARY",
  "salary_lower": 4000000,
  "salary_upper": 5500000,
  "degrees": ["Bachelor's Degree", "Associate Degree"],
  "job_functions": ["Sales and Marketing", "Banking Operations"],
  "job_levels": ["Entry Level / Staff"],
  "work_experience": 2,
  "company_name": "PT PNM Venture Capital",
  "confidential": false,
  "posted_at": "2026-08-30T03:30:00Z",
  "expires_at": "2026-09-08T00:00:00Z",
  "visited_count": 1266,
  "opportunities_link": "https://karir.com//opportunities/1401222",
  "company": {
    "id": 8920,
    "name": "PT PNM Venture Capital",
    "industry_name": "Keuangan / Bank",
    "description": "PT PNM Venture Capital adalah badan usaha Perseroan Terbatas yang melakukan kegiatan usaha Modal Ventura...",
    "subscribers": 8,
    "benefits": []
  }
}
```

**Search mode (`fetchFullDetails: false`)** — compact result, one extra field per job saved:
```json
{
  "_input": "keyword:sales",
  "_source": "S1-search-api",
  "id": 1401465,
  "job_position": "Field Sales Force",
  "description": "Prov. DKI-Jakarta",
  "company_name": "PT Bina Talenta",
  "company_logo_url": "https://karir-production.nos.jkt-1.neo.id/logos/....png",
  "salary_lower": 4500000,
  "salary_upper": 6000000,
  "salary_info": "LABEL_FULL_SALARY",
  "is_urgent": false,
  "posted_at": "2026-08-24T04:28:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `job_position` | string | Job title. |
| `location` / `description` | string | City/province — `location` on full-detail records, `description` on compact search records. |
| `requirements` / `responsibilities` | string | HTML-formatted job details (full-detail records only). |
| `salary_lower` / `salary_upper` | integer | Monthly salary range in IDR — may be missing when the employer doesn't disclose it. |
| `salary_info` | string | A label such as "competitive salary" when no figure is disclosed. |
| `company_name` | string | Employer name — may read as a placeholder when the employer chose to stay anonymous. |
| `company` | object | Full-detail records — employer profile: industry, description, subscriber count, benefits. |
| `posted_at` / `updated_at` / `expires_at` | string | ISO 8601 timestamps. |
| `opportunities_link` | string | Canonical job URL. |

A record with `_error` instead means that lookup couldn't complete (e.g. `"_error": "not_found"` for an expired/nonexistent job ID).

## Known limits

- **Location/industry/job-function filters need numeric IDs, not city or industry names.** Free-text `keyword` search (which matches job titles) works for everything else and is the primary way to narrow results.
- **Result counts reflect the site's actual current job postings** — a job board naturally has fewer live postings at any moment than, say, a news archive.
- **Salary is frequently undisclosed** by the employer — `salary_lower`/`salary_upper` will be missing in that case, with `salary_info` carrying a "competitive salary"-style label instead.
