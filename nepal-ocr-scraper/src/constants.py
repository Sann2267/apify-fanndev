"""Endpoint, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Nepal's Office of the Company Registrar (OCR)
has THREE distinct web properties on gov.np infrastructure:

1. `ocr.gov.np` -- the public marketing/informational site (news, forms,
   contact info). `robots.txt` is a plain `User-agent: * / Crawl-delay: 10`,
   no AI-crawler mentions, no disallow.
2. `camis.ocr.gov.np` -- "CAMIS" (Company Administration & Management
   Information System), OCR's current citizen-facing portal: a Vite/React
   single-page app used both for authenticated e-filing (registration,
   annual returns, amendments -- all auth-walled) AND a small set of public,
   no-login pages, one of which is a company search. Its `/robots.txt` path
   actually returns the SPA's own `index.html` (a client-side-router catch-
   all with no dedicated robots.txt file at all) -- i.e. no crawl rules are
   declared here either.
3. `application.ocr.gov.np` -- a legacy JSF/RichFaces (Java Server Faces)
   application from an older system generation. Its `CompanyDetails.jsp`
   page renders a bare, session/ViewState-bound "Search Company by
   Registration Number" form with no login wall on the page itself, but
   RichFaces JSF postbacks are stateful (server-side ViewState tied to a
   `jsessionid`) and comparatively brittle to script. **Not used by this
   actor** -- superseded by the CAMIS API below, which returns the same
   category of information (and more fields) as a clean stateless JSON call.

A prior recon attempt reportedly timed out. The likely cause: `www.ocr.gov.np`
(with the `www.` prefix) does not resolve/respond at all (connection times
out at 20s+ with zero bytes), and `nepal.gov.np:8080` -- the "National
Portal" OCR service listing that ranks highly in search -- serves a
`robots.txt` of `Disallow: /`, i.e. blocked outright. **Neither of those is
the real site.** `ocr.gov.np` (no `www`) and `camis.ocr.gov.np` both respond
in under 2 seconds; the timeout was very likely a wrong-domain dead end, not
a real reachability problem with OCR itself.

**The public search this actor uses**: CAMIS ships a `/search-company` page
(`whiteList: true` in its router config -- i.e. explicitly reachable without
a login token) that calls a single stateless JSON endpoint:

    POST https://camis.ocr.gov.np/gateway/external/api/company-registration/search-company-details
    Content-Type: application/json
    {"companyNameEnglish": "...", "companyNameNepali": "...", "companyRegistrationNumber": "..."}

Confirmed with zero cookies, zero auth header, from a cold client, across
dozens of calls: registration-number lookup, English-name substring search,
a garbage query (clean `"data": []`, not an error), and a broad common-word
query. This is a genuine public REST endpoint reached by reading the SPA's
lazily-loaded `SearchCompany-*.js` bundle -- the endpoint path and request
body shape are not documented anywhere, only present as literal strings in
the shipped JS.

**Gotcha found during recon**: there is no server-side result cap or
pagination on this endpoint. A single common-word query (`"nepal"`) returned
10,652 matched companies in one ~8.6 MB response; querying with all three
fields blank returns the ENTIRE public registry in one response (~53 MB,
tens of seconds). This actor never sends a blank query and truncates the
returned list to `maxResultsPerQuery` before writing to the dataset -- see
`main.py`.

The response only ever carries this "basic information" record shape
(name EN/NP, registration number EN/NP, registration date in the Bikram
Sambat calendar, company type, address EN/NP, and an `isRokka` legal-hold
flag) -- there is no publicly reachable "full profile" endpoint with
directors/shareholders/capital structure the way some other registries in
this collection expose; that data lives behind the CAMIS login wall.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://camis.ocr.gov.np"
SEARCH_URL = f"{BASE_URL}/gateway/external/api/company-registration/search-company-details"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/search-company",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 60  # broad queries can carry multi-MB payloads; OCR itself
# responds in well under a second for a specific query, but this project's
# CLAUDE.md calls for generous timeouts on government sites before
# concluding a genuine failure.
