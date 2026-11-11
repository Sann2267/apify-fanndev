# TopCV Scraper

Search Vietnamese job listings on TopCV.vn by keyword and/or city and get back full job details — description, requirements, benefits, salary, and employer info.

## Why use this actor

- No account, login, or API key required
- Full job description text (responsibilities, requirements, benefits), not just a title and a link
- Structured salary, location, and employer data straight from the job posting's own public data
- Automatic pagination up to the number of results you ask for
- Also works the other way: give it specific job links or IDs and it fetches full detail for exactly those

## How it works

Pick a `mode`:
1. **`search`** — searches by keyword and/or city and returns full job details for each match, with pagination handled automatically.
2. **`detail`** — fetches full detail for one or more specific job IDs/URLs you already have.

You don't need to manage any browsers or automatic retries — just provide a keyword, a city, or both.

## Input

**Keyword + city search (default mode):**
```json
{
  "mode": "search",
  "keyword": "python",
  "city": "Hà Nội",
  "maxResults": 50,
  "fetchFullDetails": true,
  "maxConcurrency": 4
}
```

**Job detail by URL/ID:**
```json
{
  "mode": "detail",
  "jobId": "https://www.topcv.vn/viec-lam/fullstack-software-engineer/2143657.html"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"search"` (default) or `"detail"`. |
| `keyword` | string | `search` mode — free-text search (e.g. `"python"`, `"kế toán"`, `"nhân viên bán hàng"`). Leave empty to list all currently active postings. |
| `city` | string | `search` mode — a Vietnamese province/city name or slug (e.g. `"Hà Nội"`, `"ha-noi"`, `"Hồ Chí Minh"`, `"Đà Nẵng"`). Combined with `keyword` when both are given. |
| `maxResults` | integer | `search` mode — max jobs to return, pagination followed automatically. Default 50. |
| `fetchFullDetails` | boolean | `search` mode — when on (default), each result includes full description/requirements/benefits/salary/employer data (one extra request per job). Turn off for a faster run that only needs the compact search-card fields (title, company, location, salary label, tags, posted date). |
| `jobId` / `jobIds` | string / array | `detail` mode — a job's numeric ID or its full `topcv.vn/viec-lam/...` URL. |
| `maxConcurrency` | integer | How many detail requests run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Search mode (`fetchFullDetails: true`, default)** — real output, truncated for readability:
```json
{
  "_input": "2143657",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T03:09:13Z",
  "@type": "JobPosting",
  "title": "Fullstack Software Engineer",
  "description": "<h2>Mô tả công việc</h2>\n<ul><li>Phân tích yêu cầu nghiệp vụ, phối hợp chặt chẽ với Product Owner...</li>...</ul>\n<h2>Yêu cầu ứng viên</h2>\n<ul><li>Tốt nghiệp đại học chuyên ngành Công nghệ thông tin...</li>...</ul>\n<h2>Quyền lợi được hưởng</h2>\n<ul><li>Thu nhập upto 45tr/tháng (Gross)</li>...</ul>",
  "identifier": { "name": "CÔNG TY CỔ PHẦN CMC OPENAI", "value": 239443 },
  "datePosted": "2026-08-26",
  "validThrough": "2026-09-25T23:59:59+07:00",
  "employmentType": "FULL_TIME",
  "hiringOrganization": {
    "name": "CÔNG TY CỔ PHẦN CMC OPENAI",
    "sameAs": "https://www.topcv.vn/cong-ty/cong-ty-co-phan-cmc-openai/239443.html",
    "logo": "https://cdn-new.topcv.vn/unsafe/https://static.topcv.vn/company_logos/....jpg"
  },
  "jobLocation": {
    "address": {
      "streetAddress": "Tòa nhà CMC – số 11 Duy Tân",
      "addressLocality": "Phường Cầu Giấy",
      "addressRegion": "Hà Nội",
      "addressCountry": "VN"
    }
  },
  "baseSalary": { "currency": "VND", "value": { "unitText": "MONTH", "maxValue": 45000000 } },
  "industry": "IT phần mềm",
  "occupationalCategory": "Nhân viên",
  "experienceRequirements": { "monthsOfExperience": 60 },
  "skills": "Java, OOP, Python, debug, Golang, CI/CD, RESTful API, unit test, Clean code, Design Patterns, SOLID principles, Node.js, ...",
  "totalJobOpenings": 3
}
```

**Search mode (`fetchFullDetails: false`)** — compact result, one request per page instead of one per job:
```json
{
  "_input": "keyword:python city:Hà Nội",
  "_source": "S1-html-search",
  "_scrapedAt": "2026-08-26T03:09:10Z",
  "job_id": "2277053",
  "title": "FULL-STACK AI DEVELOPER INTERN (Ruby / PHP / Python)_HCM/HN/DN",
  "url": "https://www.topcv.vn/viec-lam/full-stack-ai-developer-intern-ruby-php-python-hcm-hn-dn/2277053.html",
  "company_name": "Công ty TNHH ZIGExN VeNtura",
  "company_url": "https://www.topcv.vn/cong-ty/cong-ty-tnhh-zigexn-ventura/1036.html",
  "company_logo_url": "https://cdn-new.topcv.vn/unsafe/150x/https://static.topcv.vn/company_logos/....jpg",
  "salary_text": "Thoả thuận",
  "city": "Hà Nội & 2 nơi khác",
  "experience_text": "Không yêu cầu",
  "tags": ["AI Engineer", "IT - Phần mềm", "Tiếng Anh Đọc hiểu", "Tiếng Nhật JLPT N5", "Đại Học trở lên"],
  "posted_text": "Đăng1 tuần trước",
  "posted_updated_text": "Cập nhật 12 phút trước",
  "is_verified_employer": true
}
```

| Field | Type | Description |
|---|---|---|
| `title` | string | Job title. Both record shapes. |
| `description` | string | Full-detail records — HTML-formatted, combines description/requirements/benefits under `<h2>` sub-headings. |
| `baseSalary` | object | Full-detail records — structured `{currency, value: {unitText, maxValue?, minValue?}}`. When the employer marks salary negotiable, `value.value` holds the literal string `"Thoả thuận"` instead of a number. |
| `salary_text` | string | Compact records — the site's own displayed salary text (e.g. `"Tới 45 triệu"`, `"Thoả thuận"` = negotiable), not parsed into a number. |
| `hiringOrganization` / `company_name` | object / string | Employer name (+ profile URL, logo on full-detail records). |
| `jobLocation` / `city` | object / string | Full address (full-detail) or displayed city text (compact). |
| `skills` | string | Full-detail records — comma-separated skill/keyword list. |
| `totalJobOpenings` | integer | Full-detail records — open headcount for this posting. |
| `tags` | array | Compact records — job-function/skill/benefit tags shown on the result card. |

A record with `_error` instead means that lookup couldn't complete (e.g. `"_error": "not_found"` for an expired/nonexistent job ID, `"_error": "invalid_city"` for a city name that doesn't match TopCV's own province list).

## Known limits

- **Only two search filters are supported: `keyword` (free text) and `city` (Vietnamese province).** TopCV's search runs entirely through pretty "slug" URLs (there's no JSON search API to call) — no salary-range, experience-level, or employment-type filter could be reverse-engineered as a working combination.
- **`salary_text` on compact records is the site's own display string, not a parsed number** — many postings are marked "Thoả thuận" (negotiable) rather than disclosing a figure.
- **Result counts reflect the site's actual current job postings** — a job board naturally has fewer live postings at any moment than, say, a news archive (e.g. a narrow keyword like "python" nationwide can return well under 20 results).
