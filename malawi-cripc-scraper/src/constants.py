"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): Malawi's official business registrar was the
"Registrar General's Department" (`registrargeneral.gov.mw`); effective
1 April 2026 its functions transferred to a new statutory agency, the
**Companies, Registrations and Intellectual Property Centre (CRIPC)**
(`cripc.gov.mw`). The actual transactional registry system --
**MBRS, the Malawi Business Registration System** -- lives on its own host,
`mbrs.gov.mw`, and is what this actor scrapes. `mbrs.gov.mw/` (root) 302s to
`cripc.gov.mw/` (the new agency's marketing/info site), but every other path
on `mbrs.gov.mw`, including `/search`, serves directly with no redirect.

`robots.txt`: `mbrs.gov.mw/robots.txt`, `registrargeneral.gov.mw/robots.txt`,
and `cripc.gov.mw/robots.txt` are all the stock unmodified Phoenix/Rails-
style placeholder template ("# To ban all spiders from the entire site
uncomment the next two lines: # User-agent: * # Disallow: /") -- every
directive is commented out, so there is NO active Disallow rule on any of
the three hosts, and no mention of Claude/ClaudeBot/anthropic-ai/GPTBot/AI
crawlers anywhere in the file (checked the literal text, not just parsed
directives).

## The public search: no login, no CAPTCHA, no WAF

`mbrs.gov.mw/search` is CRIPC's own public "Search for Individuals or
Entities" tool (linked from CRIPC's homepage under "Quick Actions" ->
"Public Search"). It is a classic server-rendered page (backend: Elixir/
Phoenix, `server: Cowboy` header) with a thin Vue "global-lookup" component
sprinkled on top for interactivity -- but critically, **the search results
themselves are rendered server-side in the initial HTML response**, not
fetched via a separate XHR/JSON call. A plain `GET` with query params is
enough:

    GET https://mbrs.gov.mw/search?type=<entity|individual>&q=<query>&page=<1-based>

No `Accept: application/json` trick exposes a cleaner JSON payload (the
server ignores the Accept header and always returns the full HTML page).

Confirmed with a bare `curl` (default TLS, generic UA, no cookies/session)
on the first try -- 200 OK with real data. All four `curl_cffi` impersonation
profiles tried (`chrome124`, `chrome131`, `safari17_0`, `edge101`) also
return 200 with byte-identical content on the first try. No Cloudflare/
Akamai/DataDome markers in headers or body, no CAPTCHA anywhere in this
flow, no rate-limiting observed across a burst of 5 rapid sequential
requests. `curl_cffi` is used anyway per this portfolio's default posture,
not because any block was ever seen.

Signup/Sign-in links (`/auth/register`, `/auth/sso-login`) exist on the page
but are NOT required to search or to view search-result rows -- login is
only needed to actually *file* something (name reservation, new
registration, etc.), confirmed by successfully paging through thousands of
real entity/individual records with zero auth.

## Response shape (HTML, not JSON)

Because the page is server-rendered but the Vue component hasn't executed
(no JS engine in this actor), a few date fields arrive as literal unrendered
Vue mustache expressions in the raw HTML, e.g.:

    <p class="text-sm font-semibold text-black">{{formatDate('MMM D, YYYY',"2024-11-25" )}}</p>

The actual ISO date (`2024-11-25`) is still present as a plain string inside
that expression -- `extractor.py` pulls it out with a small regex instead of
needing a JS engine.

Each matched **entity** (`type=entity` -- covers both incorporated companies
and registered business names/sole-trader names) renders as a "business
card" div (`class="mb-3 mt-2 p-4 bg-white rounded-lg ..."`) containing:
- registration number, prefixed `COY-<code>` for companies or
  `BRN-<code>` for business names (both prefixes appear in the same
  `type=entity` result set -- confirmed by searching a generic sole-trader-
  style term and seeing both prefixes mixed together)
- entity name
- registered date (see mustache note above)
- status (`active` / other -- only `active` observed in samples pulled)

Each matched **individual** (`type=individual` -- registered business
owners/proprietors) renders as an "owner card" div
(`class="cursor-pointer p-4 bg-white border border-gray-100 rounded-lg ..."`)
containing: name, status, and (unlike the entity list) a `View` link:

    <a href='/search/<uuid>?type=owner'>View</a>

## Gotcha: entities have NO public detail page; individuals do

Anonymous entity-search result rows carry **no click-through/detail link at
all** -- the per-row "Services" dropdown renders as an empty `<ul>` for a
logged-out visitor. This was checked across dozens of sampled companies:
there is no `/entities/<id>` or `/companies/<id>` style page reachable
without an MBRS account. Company-level detail (directors, shareholders,
share capital, registered office address, full filing history) is
genuinely gated behind login -- this is a real product limitation, not a
scraping gap, and this actor does not attempt to bypass it (no login
automation, per this portfolio's constraints).

Individual ("owner") rows DO have a real public detail page at
`/search/<uuid>?type=owner`, which server-renders the owner's name, ID type
(e.g. `citizen`), and every business/company they are a registered
proprietor/owner of (same "business card" markup as the entity list, plus
an extra "Owner Type" field, e.g. `Proprietor`). This actor uses that page
as its `includeOwnerDetails` enrichment step for `individual`-type searches.

## Pagination

`page=<n>` (1-based) is a plain query param on `/search`; the results page
also renders an explicit numbered pagination bar (first few pages, an
ellipsis, then the true last page number, e.g. `... 653 654 655 656` for a
653-page result set), confirming the site itself knows the true last page --
but this actor does not rely on parsing that number. The simplest, most
robust stop condition (matching this portfolio's general pagination
convention) is used instead: keep requesting increasing `page` values until
a page's result-card count is zero, `max_results` is reached, or
`MAX_PAGES_PER_QUERY` (safety cap) is hit.

## Sample queries tested during recon

- `type=entity&q=Limited` -- 653+ pages, ~11 results/page, real companies
  with `COY-` registration numbers (e.g. `COY-QDUKYGD` / "JISA CONSTRUCTION
  LIMITED AND NDABO CONSTRUCTION LIMITED JOINT VENTURE LIMITED").
- `type=entity&q=Chikondi` -- mixed `COY-`/`BRN-` prefixes in one result set.
- `type=individual&q=John` -- real registered proprietors (e.g. "JOHN
  PETER", "BICKIEL JOHN"), each with a working `/search/<uuid>?type=owner`
  detail link.
- `type=entity&q=stanbic` -- zero exact/substring matches under that literal
  string (the bank is registered under a longer legal name) -- correctly
  renders CRIPC's own "name available to reserve" empty-state, treated by
  this actor as a `not_found` result, not an error.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://mbrs.gov.mw"
SEARCH_PATH = "/search"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/search",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Safety cap on page depth per query -- keeps a runaway broad query (e.g. a
# single common letter) from paging forever; combined with maxResultsPerQuery
# as the primary stop condition.
MAX_PAGES_PER_QUERY = 50
