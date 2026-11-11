# Crawling method — Himalayas remote jobs

Recon date: **2026-09-18**. Plain HTTP, no browser, no proxy, no cookie, no login.

## Surface

| Surface | Method | Carries |
| --- | --- | --- |
| `GET himalayas.app/jobs/api` | JSON, ~15 KB per page of 20 | `comments`, `updatedAt`, `offset`, `limit`, `totalCount`, `nextCursor`, `jobs[]` |

`totalCount` read **97,007** on first probe and **100,101** three hours later, so the feed is
live and growing. The response's own `comments` field documents the cursor pagination, which
makes this a published interface rather than a private one:

> *21/08/2026: Cursor pagination is now available and is the preferred way to page through the
> feed. Pass the nextCursor value from each response back as `?cursor=`. … The offset parameter
> is deprecated and will be removed in a future release.*

Per job: title, excerpt, full HTML description, company name + slug + logo, employment type,
min/max salary with currency and period, seniority, categories, parentCategories, location and
timezone restrictions, applicationLink, guid, pubDate, expiryDate.

## Only the JSON feed is open

| Path | Result |
| --- | --- |
| `/jobs/api` | **200 JSON** |
| `/companies/api` | 403 |
| `/companies/<slug>` | 403 |
| `/jobs/<slug>` | 403 |

So a 403 on this host means *the request left the public feed*, not *we are blocked* — and the
client's error message says exactly that, because the wrong diagnosis sends the next maintainer
hunting for a WAF that is not there. Company data is therefore aggregated from the feed itself
rather than scraped from the HTML company pages.

TLS profile: `chrome124`, 200 on every probe. No WAF banner, no challenge, no cookie gate.

## The two behaviours that shaped the design

**1. `limit` is hard-capped at 20.**

| Requested | Returned |
| --- | --- |
| 1 / 5 / 20 | 1 / 5 / 20 |
| 21 / 50 / 100 / 200 / 500 | **20 every time** |

Not an error, just a silent cap. So depth comes from walking the cursor — three pages returned
60 jobs with **zero repeated guids**.

**2. Every filter parameter is accepted and ignored.**

`query`, `categories`, `seniority`, `employmentType`, `company`, `minSalary` and
`locationRestrictions` all return HTTP 200 and change nothing. The tell: `categories=Design`
returned *AI/ML engineering* roles, and `company=gitlab` returned the same first job as no
filter at all. `totalCount` even wobbles between calls (96,914 / 100,082), which looks like
filtering until you compare the guids — they are identical.

An Actor that forwarded those parameters would **look like it filtered and quietly return
unfiltered data**. All filtering here is therefore local, over records already fetched, which
in turn is why `maxScannedJobs` exists: a narrow filter over 100,000 jobs at 20 per request
would otherwise run 5,000 requests. The run stops at the scan budget and reports `scanned`,
`stopReason` and `jobsScannedInRun` so a short result is visibly a budget limit, not an empty
market.

`reference` mode **re-tests both behaviours live** and reports `jobsReturnedForLimit100` and
`serverSideFilteringWorks`, so if Himalayas ever implements real filtering it shows up as a
reference-mode diff rather than as an Actor that is needlessly slow.

## Other gotchas

3. **Salaries mix pay periods in the same numeric fields.** Of 400 jobs sampled: 352 annual,
   34 hourly, 11 monthly, 3 weekly. A raw `minSalary >= 150000` filter would silently discard a
   `30–55 hourly` USD role worth roughly $62k–$114k a year. Every record therefore also carries
   `annualizedSalaryMin`/`Max` (hourly × 2080, weekly × 52, monthly × 12) plus `annualizedFrom`
   so the conversion is auditable, and all salary filtering uses those.
4. **Salaries also mix currencies** — USD, INR, EUR, CAD, PLN, PHP, and 251 of 400 published
   none at all. Currency is deliberately **not** converted: inventing exchange rates would put
   made-up numbers into a dataset. The `currency` filter exists so a salary comparison can be
   made sound, and the input schema says to pair the two.
5. **`guid` is itself the listing URL**, not a bare id. Building `"/jobs/" + guid` produced
   `himalayas.app/jobs/https://himalayas.app/...` until it was caught; `jobUrl` now passes a
   URL-shaped guid straight through.
6. **`applicationLink` is not an employer ATS link.** Across 60 consecutive listings it was
   always a `himalayas.app` page, and always equal to `guid`. The output schema says so rather
   than implying it reaches the employer's own careers page.
7. **A job with no published salary cannot clear a salary floor**, so it is excluded from
   salary-filtered results rather than assumed to qualify — and `salariedOnly` exists because
   roughly half the feed publishes nothing.

## Cost shape

- 1 request per 20 jobs, unfiltered.
- A filtered run costs `scanned / 20` requests, and `scanned` is reported on every record.
- `companies` mode costs nothing extra — it aggregates the pages the run already fetched.
