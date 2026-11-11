# Crawling Method — h1bdata-scraper

**Target:** [h1bdata.info](https://h1bdata.info) — a third-party republish
of the US Department of Labor's public **LCA (Labor Condition Application)
disclosure dataset**, i.e. every H-1B sponsorship filing since 2012
(employer, job title, salary, worksite, dates, and — on the case-detail
page — wage level, employer point-of-contact, sponsoring attorney).

## WAF / anti-bot: none found

- `robots.txt` is `User-agent: * / Disallow:` (fully open) with an
  advertised `Sitemap:` — no Claude/GPTBot/AI-bot block of any kind.
- `curl_cffi` `chrome124` gets clean `200` on the homepage, every search
  query tried, and every `details.php?id=` lookup tried, with zero
  Cloudflare/DataDome/PerimeterX/Akamai/Kasada markers in headers, cookies,
  or body (checked the full known marker list from `.ai/anti-bot/`).
- No login, no API key, no rate-limit response observed across dozens of
  requests during recon.
- **Retry/backoff scaffolding is kept anyway** (`src/client.py`) per
  portfolio convention, purely as a defensive no-op in case that posture
  changes later.

## Endpoints

1. **Search** — `GET /index.php?em=<employer>&job=<jobTitle>&city=<city>&year=<year|All Years>`
   Server-rendered HTML with one `<table id="myTable">`. **No pagination —
   every matching row is rendered into the single response.** Columns:
   `EMPLOYER`, `JOB TITLE`, `BASE SALARY` (the `<a href="details.php?id=...">`
   link is the only place the case ID appears), `LOCATION` ("City, ST"),
   `SUBMIT DATE`, `START DATE`.
   - A query that matches nothing renders `<tbody></tbody>` (empty) — a
     real "no results" signal, confirmed live with a nonsense employer
     name. Anything else missing the table entirely is treated as a shape
     change (`UnexpectedShape`), not a no-match.
   - **No practical page-count limit exists server-side.** Observed a
     single employer/single year returning **21,851 rows / 11.1 MB** in one
     response (`AMAZON`, year `2024`) in ~5s. This is the actor's only real
     constraint — not a block, just raw response size — handled by (a)
     requiring at least one of `employer`/`jobTitle`/`city` in the input
     (an empty/global query was not tested and is assumed to return the
     entire multi-year dataset, likely hundreds of MB) and (b) a
     `maxResults` cap applied *after* parsing.
   - Job-title free-text search is a plain substring match against the
     filed title, and filed titles are frequently auto-generated/mangled
     by the source dataset itself (e.g. `"SoftwareEngineer 1615.47781"` —
     no space, numeric wage-code suffix). A query for `"software engineer"`
     (with a space) only matched 7 rows for this reason — **this is a data
     quirk of the DOL dataset via h1bdata.info, not a bug in this actor.**
     Short, employer-anchored searches are far more reliable than
     broad job-title-only searches.

2. **Case detail** — `GET /details.php?id=<caseId>`
   Server-rendered HTML with one `<table class="table-striped">`, a flat
   list of `<tr><td>LABEL</td><td>VALUE</td></tr>` pairs (~76 fields:
   `LCA CASE NUMBER`, `STATUS`, wage fields — `LCA CASE WAGE RATE FROM`,
   `PREVAILING WAGE`, `PW WAGE LEVEL` — full worksite address, employer
   address + point-of-contact name/email, sponsoring
   attorney/law-firm name/email, certification dates).
   - An **invalid/unknown case ID returns `200` with no `<table
     class="table-striped">` at all** (confirmed live) — this is the "not
     found" signal; there is no distinct 404.
   - Labels are used verbatim as record keys (normalized only for
     dict-key safety: uppercase, non-alphanumeric → `_`, e.g. `"LCA CASE
     EMPLOYER NAME"` → `LCA_CASE_EMPLOYER_NAME`). No field is dropped or
     semantically renamed.

## Parsing

`selectolax` (not BeautifulSoup) — chosen specifically for the search
endpoint's multi-MB unpaginated responses; parses an 11 MB page in a
fraction of a second where `bs4+lxml` would be noticeably slower at this
scale. HTML entities (`&amp;` → `&` in firm names like "Berry Appleman &
Leiden LLP") are decoded automatically by `.text()`.

## Enrichment (`fetchCaseDetails=true`)

Search results legitimately repeat the same `caseId` across rows (the
"TEXAS INSTRUMENTS" duplicate observed live during recon — same case,
listed twice). The enrichment pass dedupes by `caseId` before fetching
`details.php`, then merges the cached detail dict back onto every row
that referenced it — avoids redundant fetches without changing output
row count.

## TLS profile

`chrome124` — arbitrary but consistent choice; no profile-specific
behavior was observed (the site has no fingerprint-based gating to react
to). Not revisited unless behavior changes.

## Known limits

- No pagination metadata exists to report a "total match count" separate
  from the rows actually returned (unlike, e.g., Point2Homes' `ItemList
  numberOfItems`) — `maxResults` is a hard slice of whatever came back,
  not a server-side page size.
- `AGENT ATTORNEY *` / `EMPLOYER POC *` fields are only present when the
  filing used a representing attorney / listed a point-of-contact — absent
  keys simply don't appear in that record's dict (no field is emitted as
  an empty placeholder).
