# LinkedIn Smart Job Description & Recruiter Extractor

Most job scrapers give you a title, a company and a link. The interesting part of a job posting is the 5,000 words underneath that, and this actor reads them: which technologies the employer named, which certifications and clearances they demand, what they will pay, and how many people have already applied.

**No login is needed.** LinkedIn's public jobs API answers anonymous requests, paginates cleanly and carries the full description. This is the one LinkedIn surface that is genuinely open, and it is why this actor can run without putting any account at risk.

## What it pulls out of the description

```json
{
  "jobTitle": "Senior Software Engineer - Python",
  "companyName": "Venmo",
  "location": "San Jose, CA",
  "workplaceType": "HYBRID",
  "employmentType": "Full-time",
  "industries": "Financial Services",
  "techStack": ["AWS", "Azure", "CI/CD", "Django", "Flask", "GCP", "Git", "Kafka", "NoSQL", "Python"],
  "certifications": [],
  "salaryMin": 143500.0,
  "salaryMax": 212850.0,
  "salaryCurrency": "$",
  "salaryPeriod": "annually",
  "salarySource": "parsed-from-description",
  "applicants": 114,
  "descriptionLength": 8110
}
```

`techStack` is matched as whole words against a curated list, not by substring search. That distinction is the difference between a usable dataset and a noisy one: a naive matcher turns every "R&D" into a hit for **R** and every "Going to market" into a hit for **Go**. Longer terms also consume their matches first, so "React Native" is not double-counted as "React" — while "SQL and PostgreSQL" correctly reports both.

`salaryMin` / `salaryMax` handle both thousand-separator conventions, so `$120,000` and `Rp 8.000.000` parse equally well, and `salaryPeriod` is kept separately because a bare `45,000` means wildly different things per hour and per year. Where LinkedIn renders an employer-provided pay block, that wins over anything mined from the prose, and `salarySource` tells you which you got.

## The filter behaviour you need to know

This was measured, not assumed:

- **`datePosted` really filters.** It maps to LinkedIn's own `f_TPR` and is applied server-side.
- **Workplace, experience level and job type do not.** LinkedIn's public endpoint accepts those parameters and then ignores them — passing `f_WT=2` (remote) returns results identical to passing nothing, same first ten ids, every time.

Rather than offer filters that quietly do nothing, this actor applies those three **client-side**, against each posting's own criteria grid and description, after the detail page is read. They work — but a filtered run still costs one request per posting examined, so filtering does not make a run cheaper.

Pagination is ten results per page and the endpoint stops serving anything past roughly **975 postings per query** (1,000 returns HTTP 400). Coverage comes from more queries, not a bigger cap.

## The recruiter field, and when it is empty

LinkedIn does not render the "Meet the hiring team" block to logged-out visitors. Checked across eight postings: none carried it. So `recruiterName` and `recruiterProfileUrl` are filled **only** when you supply your own `li_at` cookie, and stay empty otherwise.

If you want them: sign in to LinkedIn in your browser, open DevTools → Application → Cookies → `www.linkedin.com`, copy the **value** of `li_at`, paste it into `sessionCookie`. This actor never asks for your password and never signs in on your behalf.

**The honest risk:** scraping while signed in breaches LinkedIn's User Agreement and accounts do get restricted for it. Use a residential proxy in your own country (a datacenter exit IP is the mismatch that flags sessions), keep `maxJobs` modest, and use an account you would not mind losing. Everything else in this actor works without a cookie — the recruiter field is the only thing you are trading that risk for.

## Input

```json
{
  "searchQueries": ["python developer", "data engineer"],
  "location": "United States",
  "datePosted": "pastWeek",
  "requiredTech": ["Kubernetes"],
  "onlyWithSalary": true,
  "maxJobs": 200
}
```

You can also skip search entirely and pass `jobUrls` — full `/jobs/view/` links, `?currentJobId=` links or bare numeric ids.

## Who this is for

- **Job aggregators** — structured postings without maintaining a parser.
- **Recruitment agencies** — which employers are hiring for what, and at what pay.
- **Bootcamps and course designers** — `techStack` aggregated across a few thousand postings is a direct read on what the market is actually asking for, which is a better curriculum input than a survey.
- **Candidates** — `applicants` tells you how contested a role is before you spend an hour on the application.

## Rate gating

LinkedIn answers request bursts with **HTTP 999** and a ~1.5 KB stub. It is per-IP and per-burst, not a TLS fingerprint gate — five browser fingerprints all returned 200 on the same page. The actor sleeps a random 2–8 seconds between requests, backs off exponentially when gated, and rotates fingerprints. If the log shows rate-gate warnings, raise both delay bounds first.

## No email addresses

`resolveCompanyDomain` gives you the employer's web domain. It does not invent `first.last@domain.com`. A guessed address that bounces costs you your sending domain's reputation, which is far more expensive than a missing column — put the name and domain through a verification tool that actually checks.

## Related actors

- **LinkedIn Post Engagers Scraper** — who engaged with a post, with their comments.
- **LinkedIn Top Voice & Competitor Activity Monitor** — content strategy, no cookie needed.
