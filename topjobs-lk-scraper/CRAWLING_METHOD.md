# Crawling Method — TopJobs.lk Scraper

**Last verified:** 2026-08-26

## Target

[topjobs.lk](https://topjobs.lk) — Sri Lanka's leading job board ("topjobs
Sri Lanka Job Network"). A job search/listing site, not a news outlet, so
the recon and architecture differ from this portfolio's news-scraper
actors (no article text, no RSS/sitemap-of-articles pattern — this one is
search + structured job postings, closer in shape to `karir-com-scraper`).

Unlike `karir-com-scraper` (a Next.js SPA with a discoverable JSON REST
API), topjobs.lk is a genuinely **old-generation server-rendered app** —
`Server: Apache-Coyote/1.1`, `X-Powered-By: JSP/2.2` (Java Servlet/JSP on
Tomcat, `.jsp` page extensions throughout, `JSESSIONID` cookies). There is
no JSON API to reverse-engineer; every page is full server-rendered HTML,
parsed with BeautifulSoup selectors instead of a JSON walker.

## robots.txt — independently re-verified

`https://topjobs.lk/robots.txt` **does not exist as a file at all.** A bare
`curl_cffi` GET with `allow_redirects=False` returns:

```
GET /robots.txt -> 302 Location: https://topjobs.lk/index.jsp?ErrorURL=y
```

This is the site's generic "page not found" handler — the exact same 302
happens for other nonexistent paths tested (`/sitemap_index.xml`,
`/Robots.txt`). `/sitemap.xml` (no underscore) does exist and returns a
real sitemap. With no robots.txt file present, there is nothing to parse
and no restriction declared for any user agent — Claude included. Nothing
to honor or violate.

## No WAF found — HTTP-only, no impersonation even required

Checked with a bare `requests.get()` (no TLS impersonation, no custom
headers at all) against the homepage, the search/browse page, and an
individual job detail page: clean 200s everywhere, `Server:
Apache-Coyote/1.1`, no Cloudflare/Akamai/PerimeterX/DataDome markers, no
challenge page, no `cf-ray` header. `curl_cffi chrome124` is still used per
portfolio convention (cheap insurance), and retry/backoff scaffolding
(`src/client.py`) is kept in case that changes later.

## No login required — every field this actor extracts is public

**Critical check passed.** The search/browse page, and every individual job
detail page (including the description image), returns full content with
**no session cookie, no Authorization header, no API key** sent at all —
confirmed live with a bare `curl_cffi` GET carrying no cookies. The site
does have applicant/employer login flows (`applicant/login.jsp`,
`ApplicantLoginRegServlet`), but they gate account features (saving/
applying/tracking applications), not the vacancy content itself — a
"Sign Up / Login" prompt is shown *alongside* the fully-rendered job ad,
not instead of it.

## Architecture: server-rendered HTML, no JSON API

### Search / browse

```
GET https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp
    ?FA=<code>          -- functional-area code (category browse), see FUNCTIONAL_AREAS
    &jst=OPEN            -- job status; always sent, matches the site's own links
    &txtKeyWord=<kw>      -- free-text keyword search
    &chkGovt=Y            -- optional checkbox filters (any combination), all confirmed live
    &chkNGO=Y
    &chkParttime=Y
    &chkWalkin=Y
    &chkForeign=Y
    &chkInternship=Y
    &pageNo=<n>           -- 1-indexed
```

This single endpoint is *both* the homepage's category-browse links
(`?FA=SDQ`) *and* the homepage's own keyword-search form target (which
POSTs to the same JSP; a plain GET with the same params works identically
and was used throughout this actor for cacheability/simplicity — confirmed
live, same result count and rows either way).

**Confirmed quirk #1 — `FA` and `txtKeyWord` are mutually exclusive, `FA`
wins.** Live-tested `FA=SDQ&txtKeyWord=zzznonexistentxyz123` (a
guaranteed-zero-match keyword) still returned the full unfiltered 176-job
SDQ category count — identical to `FA=SDQ` with no keyword at all. When
`FA` is non-empty, `txtKeyWord` is silently ignored server-side. This
actor's input schema documents this directly rather than trying to work
around it (there is no known way to combine category + keyword server-side).

**Confirmed quirk #2 — the checkbox filters DO combine correctly with
`txtKeyWord`** (unlike `FA`). `txtKeyWord=accountant&chkWalkin=Y` returned
a genuine empty result (no accountant jobs with a walk-in-interview flag
at recon time) — verified this wasn't a bug by testing `chkWalkin=Y` alone
(11 results) and `txtKeyWord=accountant` alone (151 results) separately,
both non-empty, so the combined empty set is a real (if narrow)
intersection, not a broken query.

**Page size is 1000 rows/page**, confirmed via the page's own HTML comment
(`<!-- 1 - 1000 of 5865 job(s) -->` on an unfiltered browse returning 5865
total). The `blockSize` hidden form field the site's own UI sets (18) has
**no effect on the server response** — tested explicitly, still got
hundreds of rows back regardless of what `blockSize` was sent. This actor
does not send `blockSize` at all and paginates via `pageNo`.

**Functional-area codes** (30 total) were scraped directly from the
homepage's own category panel (`applicant/vacancybyfunctionalarea.jsp?FA=<code>`
links) — see `FUNCTIONAL_AREAS` in `src/constants.py` for the full
code → label mapping (e.g. `SDQ` = "IT-Sware/DB/QA/Web/Graphics/GIS",
`ACA` = "Accounting/Auditing/Finance").

Each result row is parsed via a regex over its `onclick="createAlert('idx',
'ac','jc','ec','sessionid')"` attribute (this is far more robust to markup
reshuffling than relying on `<td>` column position for the identifiers,
though column position is still used defensively for the non-identifier
fields — job ref no., opening/closing date, town — since those aren't
duplicated elsewhere in the row). A row with no `<h2>` title is treated as
a non-job row (banner/promo slot) and skipped, not an error.

### Job detail

```
GET https://topjobs.lk/employer/JobAdvertismentServlet
    ?rid=<row-index>      -- cosmetic; confirmed rid=0 works against every jc regardless
                              of its original row position
    &jc=<job-code>         -- e.g. 0001541024
    &ac=<agent-code>       -- e.g. DEFZZZ or 0000000375
    &ec=<employer-code>    -- e.g. DEFZZZ or 0000000492
    &pg=applicant/vacancybyfunctionalarea.jsp
```

**`jc` alone is not sufficient — `ac` and `ec` must be the exact triple
that came with it.** Confirmed live two ways: (1) `jc` with no `ac`/`ec` at
all, and (2) `jc` with a *mismatched* `ac`/`ec` pair (`DEFZZZ`/`DEFZZZ`
against a `jc` that actually belongs to `ac=0000000385`/`ec=0000000505`) —
both cases 302-redirect to `util/errorPage.jsp?errCode=601` rather than
returning the job or a plain 404. There is no shorter canonical per-job URL
anywhere on the site (no `og:url`, no `<link rel="canonical">` pointing at
it) — this `JobAdvertismentServlet?...` URL *is* the canonical link, i.e.
exactly what a person would copy out of their browser's address bar. This
actor's `detail` mode input is therefore that exact URL (or the
`jc`/`ac`/`ec` triple embedded in it), and `search` mode's own output
includes a ready-to-reuse `detailUrl` field on every record.

**The "job description" is a raster image, not text.** All 6+ detail pages
sampled during recon, across different employers, categories, and
anonymous/named companies, rendered the actual job ad as
`<img src="/logo/<employer-code>/<file>.png|jpg">` inside `#remark` — e.g.
`/logo/DEFZZZ/6044cKKKHH.png` or `/logo/0000000385/1620cODOO ERP
FUNCTIONAL.jpg`. This is topjobs.lk's real publishing model: employers
upload a designed ad graphic instead of filling in a requirements/
responsibilities text field. **This is not a login gate or paywall** — the
image is fully public, fetchable with a plain unauthenticated GET, exactly
like the surrounding page. `descriptionImageUrl` is passed through as a
field on every full-detail record; there is no extractable plain-text job
description on this site, full stop.

**JSON-LD is present on only about half of sampled pages, and even then
carries no real description text.** A `<script type="application/ld+json">`
`JobPosting` block is emitted on *some* detail pages (confirmed: present on
3 of 6 samples, absent — the `<script>` tag doesn't exist at all, not just
empty — on the other 3, with no discernible pattern tied to employer
anonymity or category). When present, its own `description` field is a
placeholder string ("Please refer the full details of the job posting as
given by the employer...", bilingual English/Sinhala) pointing back at the
same image, not real description text. Because of this unreliability, this
actor treats the HTML `#position`/`#employer`/etc. fields as the *primary*
and *only-required* source, and includes the JSON-LD block as a bonus
`jsonLd` field only when present — `UnexpectedShape` is only raised if the
HTML fields themselves are missing, never for a missing JSON-LD block.

**Confirmed structured fields on every detail page** (BeautifulSoup id/class
selectors, no JSON needed): `#position` (title), `#employer` (company
name, readable both as text and its `title` attribute), `#endDate`
(closing date), `#jobRefNum`, `#adview-job-location` (town + country, e.g.
"Kottawa, Sri Lanka"), `.lbl_fulltime` (0–3 *dynamic* badges — confirmed
varies genuinely per job: a part-time listing showed only `["Part Time"]`
while most full-time ones show `["Full Time", "Permanent", "Onsite"]`),
`#remark img[src]` (description image), `#logo[src]` (employer logo, a
generic `defzzz_small.gif` placeholder for anonymous employers),
`#url[href]` (employer website — frequently empty), `#txtAVECompanyEmail`
value attribute (employer's own "Apply by email" contact address — public,
present on the page even though it sits inside an authenticated-looking
"Apply" form panel; the panel itself needs no login to view, only to
submit).

**Not-found behavior:** an invalid or mismatched `jc`+`ac`+`ec` triple
302-redirects to `util/errorPage.jsp?errCode=601` — `src/main.py` detects
this by checking whether `"errorPage.jsp"` appears in the *final* response
URL after redirects (`extractor.is_not_found`), and reports it as a normal
`not_found` record rather than a generic HTTP error.

## Encoding note

The search/browse JSP occasionally declares `charset=iso-8859-1` in its
`Content-Type` header while the job detail servlet declares `charset=UTF-8`
— inconsistent across the site's own pages, and neither can actually
represent the Sinhala text sometimes present (e.g. in JSON-LD
descriptions) if truly Latin-1. `curl_cffi`'s own encoding auto-detection
(and BeautifulSoup's `html.parser` on top of it) handled every sample
correctly during recon without any manual override — flagged here in case
a future page sample decodes garbled and needs an explicit UTF-8 override.

## Pagination stop conditions

`run_search()` in `src/main.py` stops when any of: the requested
`maxResults` cap is reached, an empty page is returned, `pageNo * 1000 >=
total` (the site's own reported total), or a page comes back with fewer
than 1000 rows (defends against `total` disagreeing with the actual row
count, not observed live but handled defensively, same pattern as
`karir-com-scraper`).

## Known limits

- **`FA` (category) and `keyword` cannot be combined** — see quirk #1
  above. This is a genuine site limitation, not a gap in this actor.
- **No extractable plain-text job description** — every "vacancy" on the
  site is an employer-uploaded image ad. `descriptionImageUrl` is the only
  way to get at the actual requirements/responsibilities text, and would
  need OCR downstream if plain text is required. This is topjobs.lk's
  actual publishing model, observed with 100% consistency across recon
  samples, not a scraping gap.
- **`detail` mode needs the full `jc`+`ac`+`ec` triple**, not just a job
  reference number — there is no working "job/<ref-number>" shortcut URL
  on the site. Always source the URL from this actor's own `detailUrl`
  field (from a prior `search` run) or copy it directly from the site.
- **Result volume reflects the site's actual current live inventory**
  (~5,865 open vacancies site-wide at recon time) — a real property of the
  target, not a pagination bug.

## Diff cadence

Quarterly smoke test recommended.
