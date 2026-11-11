"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): Fiji's company/business-name registry is run
by the **Registrar of Companies (ROC)**, part of Fiji's **Digital
Transformation Programme** (a whole-of-government platform, `digital.gov.fj`
family -- NOT the Reserve Bank of Fiji or FRCS directly, though ROC sits
administratively under the Fiji Financial Intelligence Unit). The public-
facing eServices site is `mobile.digital.gov.fj` (marketing/menu pages); the
actual transactional ROC application is a separate ASP.NET Core MVC + Kendo
UI app at `roc.digital.gov.fj` (cookie `CL.Fiji.Roc.Web.Public`, antiforgery
cookie `.AspNetCore.Antiforgery.*`). This is a from-scratch .NET Core build,
not the Verne/Foster Moore platform seen on Botswana CIPA.

`robots.txt` is a plain HTTP 404 (does not exist) on both `roc.digital.gov.fj`
and `mobile.digital.gov.fj` -- no restriction of any kind, no Claude/AI-
crawler mention (there's nothing to mention). Cloudflare fronts both domains
(`Server: cloudflare`, `CF-RAY` headers) but no challenge/CAPTCHA was
observed on ~40 requests during recon, all with plain `curl` (no TLS
impersonation needed to get through -- `curl_cffi chrome124` is used anyway
for portfolio-wide consistency, not because a bare baseline was seen to
fail).

## What's genuinely public (no login)

`GET/POST https://roc.digital.gov.fj/BuyInformation/Search` -- despite the
name ("Buy Information"), *searching* the register here requires no login,
no email, no payment. The page's own copy confirms this: "To use this
service, no login is required but a valid email address is needed" (email is
only needed for the paid purchase step, not the search). Flow:

1. `GET /BuyInformation/Search` (plain browser navigation, no params) --
   establishes a session (`CL.Fiji.Roc.Web.Public` + antiforgery cookies) and
   embeds a fresh `__RequestVerificationToken` in the form HTML.
2. `POST /BuyInformation/Search` (`application/x-www-form-urlencoded`,
   `X-Requested-With: XMLHttpRequest`) with `SearchNumber`, `SearchName`, and
   the antiforgery token, using the SAME cookie jar as step 1. The response
   body is a bare integer (e.g. `"10"`) -- the match count, nothing else.
3. `GET /BuyInformation/GetSearchResults?take=<n>&skip=<n>&page=<n>&pageSize=<n>`
   (same cookies, same `X-Requested-With` header) -- returns the actual
   Kendo-grid JSON: `{"Data": [{"EntityName", "EntityNumber", "Type",
   "Status", "LegalElement", "Url", ...}], "TotalRecords": <n>}`.

Step 2's count and step 3's `TotalRecords` normally agree, and the search
results genuinely reflect real, current ROC register data (confirmed against
"Vodafone Fiji" -> `EntityNumber 10658`, `Type COMPANY`, `Status ACTIVE`, and
dozens of other spot-checked names/numbers).

## What's NOT public: full entity profile / "Buy Information" purchase

Each result row's `Url` field (e.g.
`BuyInformation/Application?entityNumber=10658&isAuthChallenged=false`) is
the actual "view/buy this record" step -- fetching it returns **HTTP 302 to
`auth.digital.gov.fj/connect/authorize?...`**, i.e. a full OIDC login wall
("ROC Pass" account). This is exactly the paid "purchase of entity
information" feature mentioned on the eServices menu page
(`mobile.digital.gov.fj/EServices/Index`: "The section allows the search of
entity records and purchase of entity information"). Directors, shareholders,
registered address, filing history, incorporation date, and certificate
downloads all live behind this login+payment wall and are **out of scope**
for this actor (HTTP-only, no-login constraint) -- only the free search
summary (name, number, type, status) is scraped.

A second, narrower public endpoint exists at `/NameSearch/Search` (the
"Application for registration as a company" name-check tool, reachable from
`RocEServices/LocalCompanyMenu`) -- it returns only `{Name, Status,
SubmissionDate, LegalElement}` (a name-availability checker for people about
to register a NEW company, not a registry lookup) and was not used here: it
carries strictly less data than `/BuyInformation/Search` for the same public-
access tier.

## Two confirmed upstream gotchas (both cost real recon time)

1. **`SearchName` is NOT a substring/"contains" filter -- it's a loose
   fuzzy/phonetic match that returns huge, largely irrelevant result sets.**
   Confirmed reproducible across fresh sessions: searching the EXACT string
   `"VODAFONE FIJI"` (a real, exact company name) returns a count of
   **12413** -- nowhere near a literal-substring match. A single repeated
   garbage character (`"qqqqqqqqqqqqqq"`) returns 1311; the single letter
   `"A"` returns 239507; a nonsense string (`"zzzznonexistentxyz999"`) still
   returns 2 (real, unrelated) companies (`SENNUNG`, `SINONGKEN`). Posting an
   explicit `SearchType=CONTAINS/SIMILAR/COMBINE` param (guessed from the
   sibling `/NameSearch/Search` form, which DOES have that field) makes no
   difference -- `/BuyInformation/Search`'s HTML has no `SearchType` field at
   all, so the fuzzy-match behavior is not configurable from this endpoint.
   **Combining `SearchNumber` + `SearchName` in the same POST behaves as an
   AND filter** and usefully narrows the fuzzy name match (verified:
   `SearchNumber=10658&SearchName=VODAFONE` -> 1 result, vs thousands for
   `SearchName=VODAFONE` alone) -- worth using together when both are known,
   but there is no way to get a clean substring-only name search from this
   endpoint. `SearchNumber` alone, by contrast, IS a reliable substring
   match on `EntityNumber` (confirmed: nonexistent number -> count 0;
   `"10658"` -> exactly the entities whose `EntityNumber` contains that
   substring).
2. **Very large result sets silently return an empty grid.** When the
   `/BuyInformation/Search` POST count is small-to-moderate (tested up to
   ~30,000), `/BuyInformation/GetSearchResults` returns the real paged data
   as expected. Once the count reaches roughly six figures (tested: count
   245,549 and 275,463 both failed; count 30,653 succeeded), the SAME grid
   endpoint returns HTTP 200 with `{"Data": [], "TotalRecords": 0}` --
   looks identical to a genuine zero-match response, but the POST step's own
   count was very much nonzero. This is treated as a distinct
   `result_set_too_broad` error in this actor (not `not_found`) so it isn't
   silently swallowed as "no matches" -- see `extractor.py`.

## Diff cadence

Quarterly smoke test recommended -- this is a live, actively-developed
government .NET Core app (part of an ongoing "Digital FIJI" programme); a
redesign could change the antiforgery/session flow or close off the
currently-open `/BuyInformation/Search` search-without-login path.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://roc.digital.gov.fj"
SEARCH_PAGE_URL = f"{BASE_URL}/BuyInformation/Search"
SEARCH_RESULTS_URL = f"{BASE_URL}/BuyInformation/GetSearchResults"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

AJAX_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
}

# Confirmed empirically: below this the grid endpoint returns real paged
# data; the exact cutover point wasn't pinned tighter than this (30,653 ok /
# 245,549 & 275,463 silently empty) -- see constants.py docstring gotcha #2.
LIKELY_TOO_BROAD_THRESHOLD = 50_000

SEARCH_TOKEN_RE_TEMPLATE = r'__RequestVerificationToken" type="hidden" value="([^"]+)"'

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Kendo grid page size used per GetSearchResults call while paginating up to
# maxResultsPerQuery.
GRID_PAGE_SIZE = 50
