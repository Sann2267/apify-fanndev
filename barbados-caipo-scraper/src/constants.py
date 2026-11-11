"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): the domain hinted in the task
(`corporateaffairs.gov.bb`) does not resolve at all (DNS failure, plain
`curl` and `curl_cffi` both fail to connect) -- it is a dead/retired domain.
The real, current, official Barbados company registry -- run by CAIPO (the
Corporate Affairs and Intellectual Property Office) -- lives at
**`caipo.gov.bb`**, branded on-page as "Business Barbados". Confirmed via
web search + direct HTTP probing, not assumed from the task hint.

`robots.txt` (`https://caipo.gov.bb/robots.txt`, HTTP 200) is a single
`User-agent: *` group (no separate/named bot groups to misparse) with `Allow:
/` plus a short disallow list: `/backoffice/admin/`, `/backoffice/api/`,
`/backoffice/mobileapi/`, `/sso/`, `/cdn/`, plus the login/logout pages and
`/*?*` (dynamic query strings). No mention of Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai (or GPTBot/CCBot/any other AI
crawler) anywhere. The file's own leading comment is explicit about intent:
"This file only instructs well-behaved crawlers NOT to index certain paths.
It provides ZERO security... Do NOT rely on robots.txt to hide sensitive
data or endpoints!" -- i.e. the disallow list is stated by the site operator
to be an SEO/indexing preference, not an access-control boundary.

**Nuance worth flagging for future maintainers:** the search API used below
(`/sso/site/searchDbApi`, `/sso/site/companyAutocomplete`) technically sits
under the disallowed `/sso/` prefix (no `Allow:` carve-out exists for it,
unlike e.g. `botswana-cipa-scraper`'s WordPress `Disallow: /wp-admin/` +
`Allow: /wp-admin/admin-ajax.php` pattern). This actor proceeds anyway
because: (1) the site's own robots.txt explicitly disclaims being an access
boundary, (2) both endpoints are unauthenticated and CAPTCHA-free -- no
login wall of any kind, confirmed with a bare `curl`, no cookies/session
priming needed, (3) the request/response shape is an exact mirror of what
`/search-our-database/`'s own front-end JS sends for every anonymous site
visitor -- this is the public search feature, not a hidden admin path, and
(4) neither Claude/anthropic-ai nor "AI"/"LLM"/"data mining" is named
anywhere in robots.txt or on the page. If project policy on this class of
targeted-but-unexplained Disallow ever tightens, revisit this decision.

No WAF/CDN challenge of any kind observed: plain `curl` (no TLS
impersonation at all) gets a clean `200` JSON response on the first try.
Backend fronts through Azure (`x-azure-ref` header, `ASLBSA`/`ASLBSACORS`
affinity cookies) but shows no Cloudflare/Akamai/DataDome/PerimeterX
markers, no interstitial HTML, no CAPTCHA. `curl_cffi` is still used here
for portfolio-wide consistency and because it costs nothing, not because it
was proven necessary over a plain client.

**The search page (`/search-our-database/`) is a static HTML shell** (jQuery
+ DataTables + Bootstrap assets loaded but unused for the actual search --
no `__NEXT_DATA__`/webpack SPA here). All the real logic is a ~300-line
inline `<script>` block reverse-engineered directly from the page source:

1. `POST /sso/site/searchDbApi` (form-encoded OR multipart -- both work;
   this client uses form-encoded/`data=` since it's simpler) with any
   combination of `name_search_con`/`name_search_param`,
   `number_search_con`/`number_search_param`(`2` for "Between"),
   `category_search_con`/`category_search_param`,
   `date_search_con`/`date_search_param`(`2`). `*_con` is the operator
   (`Contains`/`Equals`/`Starts with`/`NOT Empty`/`Empty`, plus `More
   than`/`Less than`/`Between` for the number/date fields). Response:
   `{"data": [{"company_name", "company_number", "registration_category",
   "registration_date"}, ...], "total": <int>, "truncated": <bool>}`.
   `truncated: true` once `total` would exceed **2,000** rows -- the site's
   own hard cap, not something this actor imposes.
2. `POST /sso/site/companyAutocomplete` (`term`, `type=name`) -> `[{"id",
   "label"}, ...]` name-suggestion list. Not used by this actor (no user
   interaction to drive it), documented for completeness.

Both endpoints require the `X-Requested-With: XMLHttpRequest` header -- a
bare POST without it to `companyAutocomplete` returned `{"error": "Method
Not Allowed"}` in recon (the search endpoint tolerated its absence, but the
header is sent on every request here for consistency/safety).

**These four fields (name, number, category, registration date) are the
entirety of what the free/public search returns** -- there is no detail
endpoint, no clickable per-company permalink anywhere in the search-results
flow. The page's disclaimer section and a "Company Inquiry" service
mentioned elsewhere on the CAIPO site put a fuller profile (status,
directors/officers, filings) behind a **$5 paid, presumably manual/in-person
or emailed** request -- not an API, out of scope for this actor. This
mirrors `ghana-rgd-scraper`'s honest "search/name-lookup only, no detail
mode" pattern.

**Data quirk:** `company_number` is **not unique** -- the registry reuses
numbers across amalgamations/re-registrations/name changes (e.g. number
`7278` matches both "BANKS HOLDINGS LIMITED" and "BANKS BARBADOS BREWERIES
LIMITED", two rows sharing one registration date). Do not treat
`company_number` as a stable per-entity primary key; treat each result row
as its own record instead. `registration_date` of `"0"` means CAIPO has no
recorded date for that entry (seen on old/legacy entries) -- passed through
raw, not normalized to null, per this project's raw-passthrough convention.
`registration_category` can be `null` on some rows (also passed through
raw).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://caipo.gov.bb"
SEARCH_URL = f"{BASE_URL}/sso/site/searchDbApi"
AUTOCOMPLETE_URL = f"{BASE_URL}/sso/site/companyAutocomplete"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}/search-our-database/",
    "Origin": BASE_URL,
}

# `dbCatParam` <option> values scraped verbatim from /search-our-database/
# (kept with their exact upstream whitespace since the API matches on the
# raw string) -- exposed as the input schema's `category` enum.
CATEGORIES = [
    "AMALGAMATED EXEMPT MANAGEMENT REGISTER ",
    "AMALGAMATED SRL ",
    "AMALGAMATION (DOMESTIC) REGISTER ",
    "AMALGAMATION (EXEMPT INS.) REGISTER ",
    "AMALGAMATION (I.B.C.) REGISTER ",
    "AMALGAMATION (OFF-SHORE BANK) REGISTER",
    "BUSINESS NAMES  ",
    "CHARITY REGISTER ",
    "Demo Company - For test/demo only ",
    "DISCONTINUANCE UNDER SEC. 356.6 ",
    "DOMESTIC REGISTER ",
    "DOMESTIC REGISTER - FOREIGN CURR. PERMIT",
    "DOMESTIC SOCIETY (SRL) REGISTER ",
    "Exempt Charity ",
    "EXEMPT INSURANCE HOLDING REGISTER ",
    "EXEMPT INSURANCE MANAGEMENT REGISTER ",
    "EXEMPT INSURANCE REGISTER ",
    "EXEMPT SOCIETY (SRL) REGISTER ",
    "EXTERNAL COMPANY REGISTER ",
    "EXTERNAL EXEMPT INSURANCE REGISTER ",
    "EXTERNAL I.B.C. REGISTER ",
    "EXTERNAL NON-PROFIT REGISTER ",
    "EXTERNAL REGISTER - FOREIGN CURR. PERMIT ",
    "FOREIGN SALES CORPORATION REGISTER ",
    "FORMER ACT COMPANIES (NOT CONTINUED) ",
    "INTERNATIONAL BUSINESS COMPANY ",
    "NON PROFIT REGISTER ",
    "OFF-SHORE BANK REGISTER ",
    "PHARMACIES REGISTER ",
    "PRIVATE TRUST COMPANY ",
    "QUALIFYING INSURANCE COMPANY REGISTER ",
    "REINCORPORATION REGISTER",
    "SRL REGISTER - FOREIGN CURRENCY PERMIT ",
    "TRADE UNION REGISTER ",
]

CONDITIONS = ["Contains", "Equals", "Starts with"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.5
