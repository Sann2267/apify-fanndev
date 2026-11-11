"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Jamaica's official government e-procurement
platform is **GOJEP** (Government of Jamaica Electronic Procurement),
`www.gojep.gov.jm`, built on European Dynamics' "ePPS" (eTendering System)
-- the same commercial platform family used by several other governments
(Cyprus, Malta, etc.) under different branding. A separate body, the
Public Procurement Commission (`ppc.gov.jm`), regulates supplier
registration/licensing but is NOT the tender-listing site -- and its
`robots.txt` is a blanket `Disallow: /` for `User-agent: *`, ruling it out
entirely as a scrape target (not used by this actor at all).

`robots.txt` at `www.gojep.gov.jm/robots.txt` **does not exist** -- the
request 302-redirects to the site's own homepage (`/epps/home.do`, HTTP
200) rather than returning a 404 or a text file, which is this
application's generic "unknown path" handler. No robots.txt means no
declared crawl restriction at all: no blanket block, no `Claude`/
`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/`anthropic-ai`
mention (there is nothing to mention it in).

## Login wall: real, but narrow -- does NOT cover browsing

Visiting `/epps/cft/prepareViewCfTWS.do?resourceId=<id>` (the "View this
CFT" / full call-for-tenders detail page linked from every listing row's
title) redirects to `/cas/login?service=...` -- a genuine login wall. This
matches the task brief's warning that GOJEP-style systems sometimes gate
*viewing* to registered bidders, not just bidding. **However, this gate
sits only in front of the single-tender "full detail" page** (presumably
because it holds downloadable bid documents reserved for registered
bidders) -- it does NOT cover the tender *listing* pages themselves, which
return full, rich rows with no login and no CAPTCHA:

- `/epps/notices/viewPublishedNotices.do?formId=301` ("Bidding
  advertisements") -- 71 records at recon time, mostly bare notice-PDF
  links with little metadata. Not used by this actor (see below).
- `/epps/viewCFTSAction.do?viewMode=searchOpened&isFTS=true` ("Opened bid
  details") -- **81,157 records** at recon time. This is GOJEP's own
  running historical register of every call-for-tenders that has reached
  the bid-opening stage, spanning `status` values `Bid submission`
  (currently open), `Evaluation`, `For archival`, and presumably others --
  i.e. it is simultaneously the "currently open tenders" feed AND a
  multi-year historical archive, filterable purely by column sort. This is
  the primary data source for this actor (`noticeType="opened"`).
- `/epps/viewCaNotices.do` ("Contract Award Notices") -- **13,330 records**
  at recon time. One row per awarded contract, each linking a public,
  no-login PDF ("Contract Award Notice") via
  `/epps/notices/downloadNoticeForES.do?resourceId=...`. Secondary data
  source (`noticeType="awarded"`).
- `/epps/eawarding/showDetailsOpenedTender.do?resourceId=<id>` (linked from
  every "opened" row as "View opened bids") -- public, no login, lists each
  bidder/supplier name and their bid's internal ID + financial value (often
  blank/sealed) for that tender. Used for the optional `includeBidders`
  enrichment.

The one page that DOES require a CAPTCHA is
`/epps/prepareCurrentOpportunities.do?currentType=cft` ("Current
competitions" advanced search form) -- but it is redundant with the
CAPTCHA-free "opened" listing above (same underlying tender population,
narrower fields), so this actor simply doesn't use it.

## No WAF / TLS challenge observed

Every listing/detail/PDF endpoint above returned a normal HTTP 200 to a
plain, un-impersonated `curl/8.x` request with no cookies -- no Cloudflare/
Akamai/PerimeterX/DataDome challenge page, no 403, no JS check. `curl_cffi`
with a Chrome TLS profile is used here anyway as this portfolio's standard
baseline, not because a challenge was detected.

## Pagination: stateless GET, self-discovering the table id

Each of the two listing tables used here renders its "next page"/sort links
with a table-instance id embedded in the query string, e.g.
`?d-3680175-p=2` (page 2) or `?d-3680175-s=submissionDeadline&d-3680175-o=2`
(sort). This id was empirically stable across many independent, cookie-less
fetches during recon -- but rather than hard-coding it (it is an internal
component id that could change on the next GOJEP deployment), this actor
extracts it fresh from page 1's own HTML each run (`extract_pager_prefix`)
and reuses it for subsequent `-p=<n>` page requests. 10 rows per page is a
server-side fixed page size -- a `<tableId>_ps=50` query param exists in
the client-side JS for changing it but was confirmed NOT to change the
actual response (still 10 rows), so pagination always advances by 10.

Default sort order (no explicit `-s=`/`-o=` given) reflects each table's
own natural order, which was NOT reliably confirmed to be strictly
newest-first for the "opened" table (mixed old/new deadlines observed on
page 1) -- users who want a specific order should not assume default order
is chronological; `sortBy`/`sortOrder` inputs are exposed for that.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.gojep.gov.jm"
EPPS = f"{BASE_URL}/epps"

OPENED_URL = f"{EPPS}/viewCFTSAction.do"
OPENED_FIXED_PARAMS = {"viewMode": "searchOpened", "isFTS": "true"}

AWARDED_URL = f"{EPPS}/viewCaNotices.do"

OPENED_BIDS_URL = f"{EPPS}/eawarding/showDetailsOpenedTender.do"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Server-side fixed page size (confirmed: the `<id>_ps=` override does not
# change it).
PAGE_SIZE = 10

MAX_RETRIES = 5
RETRY_DELAY_BASE_SECS = 5.0

# Safety cap on page depth per job -- keeps a very high maxItems from paging
# through the entire 81k-row "opened" register in one run by accident.
MAX_PAGES_PER_JOB = 500

# Sort-column name maps exposed to actor input -> upstream's own internal
# field names (from the `-s=` query param values observed on each table's
# column-header sort links during recon).
OPENED_SORT_FIELDS = {
    "title": "title.keyword",
    "referenceNumber": "caUniqueCfTNumber.keyword",
    "procuringEntity": "caName.keyword",
    "submissionDeadline": "submissionDeadline",
    "procedure": "procedure",
    "status": "status",
    "awardDate": "awardDate",
}

AWARDED_SORT_FIELDS = {
    "procurementMethod": "procedure",
    "procuringEntity": "caName.keyword",
    "title": "cftTitle.keyword",
    "contractAmount": "contractValue",
    "datePublished": "datePublished",
}
