"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26/27): Ghana's official business registry is now run
by the **Office of the Registrar of Companies (ORC)**, established under the
Companies Act, 2019 (Act 992). The domain named in this actor's title,
`rgd.gov.gh` (the old Registrar General's Department site), is legacy and
**partially compromised** -- its homepage HTML contains injected spam links
(`pornbox.cc`, `domifemdom.com`) mixed into the footer nav, a clear sign of
neglect. Its own "eGhana portal" link
(`egovonline.gegov.gov.gh/RGDPortalWeb/...`) is dead: intermittently a
connection timeout, and on the rare successful TLS handshake the certificate
subject is `testexp` (mismatched, self-signed leftover) and the page body is
a bare `<h3>Error. Page cannot be displayed.</h3>`.

The REAL, live, actively-maintained registry site is `orc.gov.gh` (a
WordPress marketing/info site, `robots.txt` is wide-open: `User-agents: *` /
`Allow: /`). Its "Name Search" and "Entity Information Search" service pages
are descriptive-only (no embedded form) -- the actual interactive tool lives
on a THIRD host, linked from the homepage:
`https://rgdonline.gegov.gov.gh/orc-app/` -- a small Spring Boot Java webapp
(footer literally says "v0.0.1"), templated with Thymeleaf + htmx. This is
the ONLY functioning public search feature found anywhere across the three
domains. No `robots.txt` exists on this host at all (`/robots.txt` 404s --
unmapped route falls through to the SPA's catch-all, confirmed by identical
byte-for-byte content to the home page) -- there's nothing to disallow, and
no plain-English AI/scraping prohibition anywhere in reach.

## What the tool actually does

"Name Search" is a **business-name availability / collision checker** --
built for people about to register a company to check whether their
candidate name is already taken. It returns, per matching business:
**name** and **entity type** only (`data-bizcode` + a human-readable label:
`BN`=Sole Proprietor, `CG`=Company Limited by Guarantee, `CS`=Company
Limited by Shares, `ET`=External Company, `PN`=Partnership, `SN`=Subsidiary
Business Name -- more codes may exist, unconfirmed). **It does NOT expose**
registration numbers, incorporation dates, status (active/dissolved),
registered address, or director/officer names -- those fields require a
paid certified extract requested directly from ORC (confirmed via ORC's own
published fee schedule and site copy: "processing takes 1 to 3 business
days" for certified extracts). This actor can only ever surface what this
one public endpoint exposes: name + entity type.

## No login, no CAPTCHA, but a mandatory CSRF dance

`GET /orc-app/` returns a Thymeleaf-rendered HTML form carrying a hidden
`_csrf` token and sets a `JSESSIONID` cookie. That token is consumed by
`POST /orc-app/search-for-name` (`_csrf` + `bizName` + `searchType` as
`application/x-www-form-urlencoded`). Two non-obvious requirements, found by
trial and error:

1. **The CSRF token must come from a GET made immediately before the POST,
   on the same session** -- repeated GETs on one session each mint a NEW
   token (session storage is overwritten every render), so a token grabbed
   two requests ago is already stale and the POST 403s
   (`Whitelabel Error Page`, `status=403`) or silently 302-redirects back to
   `/orc-app/` with an empty body, depending on exactly how stale.
2. **The POST must carry `HX-Request: true` AND `HX-Trigger-Name:
   saveRequest`** (matching the submit button's `id="saveRequest"`) --
   without `HX-Trigger`/`HX-Trigger-Name`, the controller silently falls
   back to treating the request as an unrecognized/non-htmx submission and
   302-redirects to the bare homepage instead of returning the results
   fragment (`HX-Request` alone is not sufficient). With both present, the
   response is `200` with response header `hx-trigger: namesFound` and an
   HTML fragment containing the actual `<table id="search-results-tbl">`
   rows.

No WAF/CDN fingerprint observed anywhere on this host (bare `server: Apache`
throughout, no `cf-ray`, no bot-challenge body, no `_abck`/`bm_sz` cookies) --
the CSRF/htmx-header friction above is ordinary Spring Security + htmx
plumbing, not anti-bot defense.

## No server-side result cap -- a real operational hazard

There is no pagination or row limit on the server side; `DataTables` only
paginates client-side in the browser. A broad "contains" query for a common
word returns EVERY match in one giant HTML response -- confirmed:
`"GHANA"` (contains) returned **37,659 rows in an 11.48 MB response**.
`maxResultsPerQuery` in this actor's input truncates client-side AFTER the
full response is downloaded and parsed (there is no way to ask the server
for fewer rows) -- so a broad query still costs the full download, it just
limits what's pushed to the dataset. Prefer specific/narrow search terms.

Server-side input validation exists (message text passed through verbatim
as `_errorDetail`): a blank `bizName` returns "Please enter name to search
for"; very short "starts with" queries return an empty validation-error
fragment (no message text observed, treated the same way).
"""

TLS_PROFILE = "chrome124"

APP_BASE = "https://rgdonline.gegov.gov.gh/orc-app"
WARMUP_URL = f"{APP_BASE}/"
SEARCH_URL = f"{APP_BASE}/search-for-name"

VALID_SEARCH_TYPES = {"eq", "sw", "ew", "cn"}  # exact / starts-with / ends-with / contains

# data-bizcode -> human label, as observed on real search responses
# (COCOA/BANK/PARTNERSHIP/EXTERNAL sample queries, 2026-08-27). Passed
# through from the page's own <span> text at parse time -- this map is
# documentation only, not used to transform output.
KNOWN_ENTITY_TYPE_CODES = {
    "BN": "Sole Proprietor",
    "CG": "Company Limited by Guarantee",
    "CS": "Company Limited by Shares",
    "ET": "External Company",
    "PN": "Partnership",
    "SN": "Subsidiary Business Name",
}

GET_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

SEARCH_HEADERS_EXTRA = {
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded",
    "HX-Request": "true",
    "HX-Trigger": "saveRequest",
    "HX-Trigger-Name": "saveRequest",
    "HX-Target": "search-results",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
