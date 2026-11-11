"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): The Commonwealth of Dominica's Companies and
Intellectual Property Office (CIPO) runs its public marketing site on Joomla
(`cipo.gov.dm` / `www.cipo.gov.dm`). Its transactional register lives on a
SEPARATE subdomain, `efiling.cipo.gov.dm` -- an AngularJS single-page app
("OCRS", branded "E-Filing") built on the same "FM" (Foster Moore-style)
module family seen across this project's other small-country registry
actors, but an older AngularJS generation rather than the Vue3 "Verne" UI
used by e.g. `botswana-cipa-scraper`.

**Two other CIPO-branded hosts were found and ruled out during recon:**
- `registry.cipo.gov.dm` -- an even older Alfa-XP ASP.NET WebForms portal
  ("2017 (c) CaseFlow Systems Ltd."). Its `OCRS_Home` landing tab is
  login-walled ("Welcome to E-Registry. Please enter your User name and
  Password to sign in.", `ErrorCode: 2`) -- confirmed via a direct
  `ResolveTabHandler` POST. Its old public search API, `Entity.svc/GetCases`
  (JSONP, found via Wayback Machine 2017 snapshots), now 404s -- dead.
- `efileapi.cipo.gov.dm` -- referenced only in a stale JS comment
  (`Entity.js`, last modified 2019) as the default for a
  `PublicNameSearch.svc` widget; the domain itself no longer resolves
  (NXDOMAIN). Not used anywhere on the current live site.

**The current, live public search lives entirely on `efiling.cipo.gov.dm`.**
Its `ocrs.search` route (`/#/ocrs/search/:query/:option`) is explicitly
`access: {isFree: true}` in the Angular route config (`config-route.js`) --
no login needed, confirmed live with zero auth headers/cookies. The actual
data call, `servicesDataService.loadInfoProc()`
(`app/FM/Dataservice/services-data-service.js`), POSTs to:

    {config.apiUrl}/api/1.0/services/loadInfoProc

where `config.apiUrl` is ITSELF `https://efiling.cipo.gov.dm/api` (see the
inline `configSettings` block in the page's own HTML) -- so the real,
working URL has a doubled `/api/api/` segment. This was verified directly:
a single `/api/1.0/...` 404s, the doubled `/api/api/1.0/...` returns 200
with real data. This is upstream's own bug (baked into their `configSettings`
+ hardcoded service-path concatenation), not a typo introduced here.

Request body: `{"input": "key=<0|1|2>,query=<term>", "name": "EntitySearch"}`.
`key` selects which register field is searched (0=Entities by
name/registration number, 1=Directors by surname, 2=Shareholders by
surname/company name -- see the commented-out `options` array in
`app_custom/ocrs/Directives/search/search-directive.js`). No
`Authorization` header is sent for a guest lookup (`userDataService
.getSecurityHeaders()` returns just `{"showSpinner": false}` with no token
in local/session storage).

A follow-up per-entity lookup, `{"input": "entityId=<guid>",
"name": "EntityInfo"}` against the SAME endpoint, returns
`{"Directors", "Secretaries", "Schareholders"}` (note upstream's own typo on
the last key) as plain comma-joined name strings -- not structured records.
This is a much shallower data model than the Verne-based registries in this
project (Botswana, PNG, etc.): no addresses, no share allocations, no
beneficial-ownership fields are exposed anywhere on this API. Directors-mode
(`key=1`) and Shareholders-mode (`key=2`) search rows already carry
`Directors`/`Shareholders`/`Secretaries`/`Email`/`ApplicationId` inline
(joined by the search stored proc), so the detail lookup mainly adds value
for Entities-mode (`key=0`) rows, which omit those fields.

**Known upstream bugs (both return HTTP 200, not an error status):**
- An overly broad single-token query (a single letter, or a common whole
  word like "international") returns `{"message": "Number: <guid>, Divide
  by zero error encountered."}` instead of `{"rows": [...]}` -- a genuine
  backend bug (looks like an unguarded page-count division), not a block.
  Treated as `_error: "upstream_error"`.
- A literal `=` character anywhere in the query string triggers the exact
  same "Divide by zero" message.
- A literal `,` (comma) in the query string does NOT error -- it silently
  truncates the search to the text before the first comma (confirmed:
  `query=test,comma` matched "New Testament Worship Centre", i.e. only
  "test" was actually searched), because upstream naively splits the raw
  `"key=0,query=<term>"` string on comma server-side. Since this fails
  *silently* rather than loudly, this actor rejects `,`/`=` in the query
  client-side before sending (`_error: "invalid_query"`) rather than risk
  returning quietly-wrong matches.

**robots.txt: absent (HTTP/IIS 404, i.e. no file at all) on every host
checked** -- `cipo.gov.dm`, `www.cipo.gov.dm`, `efiling.cipo.gov.dm`, and
`registry.cipo.gov.dm`. No Claude/AI-crawler mention anywhere (there is
nothing to mention it in).

**No WAF observed.** `curl_cffi` impersonating `chrome124`, `chrome131`,
`safari17_0`, and `edge101` all return byte-identical `200` JSON responses
from the same IP within the same recon session. No CAPTCHA is presented on
the search/detail API itself (a reCAPTCHA script is loaded by the SPA shell
for other flows -- registration/payment -- but not for search).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://efiling.cipo.gov.dm"
# NOTE: doubled "/api/api/" is correct -- see the module docstring above.
API_URL = f"{BASE_URL}/api/api/1.0/services/loadInfoProc"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json;charset=utf-8",
    "Referer": f"{BASE_URL}/",
}

# search-directive.js's `options` array: id -> EntitySearch's `key` param.
SEARCH_TYPE_KEYS = {"entities": 0, "directors": 1, "shareholders": 2}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
