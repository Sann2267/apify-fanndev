# Crawling Method — Jamaica Government Tenders Scraper (GOJEP)

**Last verified:** 2026-08-27

## What GOJEP is, and what it isn't

Jamaica's official government e-procurement portal is **GOJEP**
(Government of Jamaica Electronic Procurement), `www.gojep.gov.jm`, built
on **European Dynamics' "ePPS"** (eTendering System) -- the same commercial
platform family used, under different branding, by several other national
procurement portals (e.g. Cyprus, Malta). "GOJEP 2.0" was publicly
announced as a relaunch in mid-2026 per Jamaica Information Service
coverage; the site as scraped here is that current version.

A separate body, the **Public Procurement Commission** (`ppc.gov.jm`),
regulates supplier registration/licensing and publishes policy -- it is
**not** the tender-listing site and was ruled out immediately:
`ppc.gov.jm/robots.txt` is a blanket

```
User-agent:     *
Disallow: /
```

This actor does not touch `ppc.gov.jm` at all.

## robots.txt

`https://www.gojep.gov.jm/robots.txt` **does not exist**. The request
302-redirects to `/epps/home.do` (the site's own homepage, HTTP 200) --
this is the application's generic "unknown path" handler, not a
served text file. No robots.txt means no declared crawl restriction:
no blanket disallow, and (since there is no file) no
`Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` mention either.

## Login wall: real, but scoped to one page -- not the listings

`GET /epps/cft/prepareViewCfTWS.do?resourceId=<id>` -- the "view full
tender" page linked from every listing row's title -- redirects to
`/cas/login?service=...`. This is a genuine login wall, confirmed with a
fresh cookie jar (visit the listing first to get a session, then hit this
URL: still redirects to CAS login). This matches the task brief's warning
that GOJEP-style systems sometimes gate *viewing* to registered bidders.

**Critically, this gate does not extend to the listing pages themselves.**
Three separate public, table-based listings return full rows with no
login and no CAPTCHA:

| Endpoint | Rows at recon time | Used by this actor? |
|---|---|---|
| `/epps/notices/viewPublishedNotices.do?formId=301` ("Bidding advertisements") | 71 | No -- mostly bare PDF links, little structured metadata, redundant with the endpoint below |
| `/epps/viewCFTSAction.do?viewMode=searchOpened&isFTS=true` ("Opened bid details") | 81,157 | **Yes** -- `noticeType=opened` |
| `/epps/viewCaNotices.do` ("Contract Award Notices") | 13,330 | **Yes** -- `noticeType=awarded` |
| `/epps/eawarding/showDetailsOpenedTender.do?resourceId=<id>` ("View opened bids", linked from every opened row) | per-tender bidder list | Optional -- `includeBidders=true` |

The one page that DOES require solving a CAPTCHA is
`/epps/prepareCurrentOpportunities.do?currentType=cft` ("Current
competitions" advanced search form, and its `currentType=notice` sibling).
This actor doesn't use it -- the CAPTCHA-free "Opened bid details" listing
above already carries the same population of currently-open tenders
(`status: "Bid submission"`) plus far more history, with richer columns.

## No WAF / TLS challenge

Every listing/detail/PDF endpoint above returned a plain HTTP 200 to an
un-impersonated `curl/8.x` request with zero cookies -- no Cloudflare/
Akamai/PerimeterX/DataDome challenge page, no 403, no JS check, on either
the bare domain or `www`. `curl_cffi` with `impersonate="chrome124"` is
used anyway as this portfolio's standard baseline, not because a real
challenge was found.

One concrete quirk found *because* of TLS/client-profile differences: the
exact same date field renders in two different textual formats depending
on the requesting client's fingerprint --

- A plain, un-impersonated `curl` request gets Java's default
  `Date.toString()` format: `"Thu Sep 03 12:00:00 EST 2026"`.
- A `curl_cffi impersonate="chrome124"` request (this actor's client, any
  `Accept-Language` value, with or without a session cookie) consistently
  gets `"03/09/2026 12:00:00"` -- day-first, no timezone.

Confirmed which convention `03/09/2026` uses by checking an unambiguous
case: the same tender's deadline rendered as `26/08/2026` for a date known
independently (from the plain-`curl` fetch) to be **26 August** -- so it is
**DD/MM/YYYY**, not U.S. MM/DD/YYYY. Documented prominently in the README
and the output schema so downstream consumers don't misread it.

## Pagination: stateless GET, self-discovering the table id

Both tables used here render their sort/page links with a table-instance
id embedded in the query string, e.g. `?d-3680175-p=2` (page 2) or
`?d-3680175-s=submissionDeadline&d-3680175-o=1` (sort). This id was
empirically stable across many independent, cookie-less fetches during
recon for a given table -- but since it's an internal component id that
could change on a future GOJEP deployment, `client.py` extracts it fresh
from page 1 of each table it touches (`extract_pager_prefix`) rather than
hard-coding it, then reuses it for that run.

- **Page size is a fixed 10 rows.** The client-side JS references a
  `<tableId>_ps=<10|20|50|100>` page-size override, but sending it
  (`d-16531_ps=50`) was confirmed to have **no effect** -- still 10 rows
  back. Pagination always advances 10 at a time.
- **Sort direction is the reverse of what the UI arrow icons would
  suggest.** Confirmed empirically by sorting `title.keyword` both ways
  and reading the actual titles back: `-o=2` returns ascending order
  (A-Z / oldest-first), `-o=1` returns descending (Z-A / newest-first).
  `client.py` encodes this explicitly with a comment, since it is the
  opposite of the "1=asc, 2=desc" a naive reading of the ascending/
  descending sort-arrow image order in the header markup would imply.
- Query param order doesn't matter (confirmed: `?d-X-p=2&viewMode=...` and
  `?viewMode=...&d-X-p=2` return identical pages) and no session/cookie is
  required across page requests -- each page fetch is a fully independent,
  stateless GET, which is what makes concurrent multi-page fetching in
  `main.py` safe.

## Column layout (fixed-index parsing, not header-text matching)

Both tables' `<th>` cells carry sort-link markup rather than clean text,
so `extractor.py` maps columns by **position**, not by reading header
labels -- but it checks the actual column count of every row against the
count observed during recon (12 for "opened", 7 for "awarded") and raises
`UnexpectedShape` on a mismatch, so a real upstream layout change fails
loud instead of silently shifting every field over by one.

**"Opened bid details" (12 columns):** `#`, Title (link, `resourceId` in
the `href`), Reference number, PE (procuring entity), Info (an `<img
title="...">` tooltip -- the actual tender description text lives in the
`title` HTML attribute, not as visible cell text), Bids submission
deadline, Procedure, Status, Opened bids (link to the bidder-list page),
Tender opening record (observed empty on every sampled row), Award date,
Estimated total contract value (also observed empty on nearly every
row -- GOJEP simply doesn't populate this column for most tenders).

**"Contract Award Notices" (7 columns):** `#`, Procurement Method, PE,
Title (link, same `resourceId` pattern -- links to the same login-walled
detail page, not fetched), Contract amount, Date, Notice PDF (a direct,
no-login download link via `/epps/notices/downloadNoticeForES.do`,
confirmed with a plain `HEAD` request returning `Content-Type:
application/pdf` with no redirect to login).

**"View opened bids" bidder list (per-tender enrichment):** a separate,
simpler 4-column table -- Envelope, Supplier name, Bid ID, Financial Value
(JMD). `financialValueJMD` was `"-"` on every sampled row (sealed/
undisclosed bids), which `parse_bidders_page` passes through verbatim
rather than converting to `null` -- it's GOJEP's own literal display value.
An empty/missing bidder table (a tender that hasn't reached bid opening
yet) returns an empty list, not an error -- that's a normal, expected
state, not a shape change.

## Known limits

- **`estimatedContractValue` and `tenderOpeningRecord` are rarely/never
  populated** on the "opened" table in practice -- not a parsing gap,
  confirmed by checking dozens of rows across old and recent tenders during
  recon. Included in the schema for completeness/future-proofing, will
  read `null` on almost every record today.
- **`listRank` is not a stable cross-run identifier.** It reflects GOJEP's
  own numbering for the specific sort/page sequence requested this run
  (see README "Notes" for its exact behavior) -- use `resourceId` if you
  need a stable per-tender key.
- **No keyword/full-text search exposed without a CAPTCHA.** The only
  narrowing this actor offers is `sortBy`/`sortOrder`; filtering by
  procuring entity, date range, or keyword would require either the
  CAPTCHA-gated advanced search form (out of scope, no CAPTCHA-solver
  policy) or client-side post-filtering of the fetched rows.
- **`contractAmount`/`estimatedContractValue` carry no currency symbol** in
  the source markup -- assume Jamaican dollars (JMD) unless a linked PDF
  states otherwise; not verified for every historical record.

## Diff cadence

Quarterly smoke test recommended. GOJEP 2.0 was a fairly recent relaunch
(mid-2026) built on a modern component framework (htmx/PrimeFaces-style
table widgets, per the JS asset names) -- more likely to receive incremental
UI updates than a legacy ASP.NET site, so the fixed-column-count check and
the `extract_pager_prefix` auto-discovery are both deliberately defensive
against a future markup shuffle.
