"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): the Solomon Islands' official company/business
register is the **Solomon Islands Business Registry** ("Company Haus"),
run by the Registrar of Companies, a Division of the Ministry of Commerce,
Industries, Labour and Immigration (MCILI). The marketing/help site
(`www.solomonbusinessregistry.gov.sb`, WordPress, theme literally named
`catalystALFREDO-2.7` / footer "Powered by Foster Moore") links to the real
transactional app under the SAME origin at `/sb-master/...` (search) and
per-register app codes like `/sb-br-companies/...` (entity profile) --
**the same "Verne"/Foster Moore "Catalyst" citizen-services platform already
seen on `botswana-cipa-scraper`**, but an older webui version (`v4.4.4`,
classic server-rendered HTML + jQuery AJAX form posts, not Botswana's
JSON-command SPA wire format).

`robots.txt` is a plain HTTP 404 on `www.solomonbusinessregistry.gov.sb` --
no file exists, so nothing is disallowed and there is no Claude/AI-crawler
mention (there's nothing to mention). No WAF/CAPTCHA/challenge markers
observed on any of ~60+ requests during recon (plain `nginx` welcome, no
`cf-ray`).

**"Entity Search" is public -- no login, no account, no CAPTCHA.** The
homepage's own copy: *"...an electronic register which can be accessed 24
hours a day... searches are FREE and you don't need to log on"*. Confirmed
live: browsing straight to the search-service URL with zero cookies renders
the search form and lets you search AND open full entity profiles --
including Directors, Shareholders (with share counts), Addresses, and Filing
history -- with no auth prompt anywhere. This is richer public data than
several other actors in this portfolio (e.g. Botswana/Fiji only expose
director/shareholder detail after gating on other things or not at all in
Fiji's case).

## The flow (classic server-rendered form POST, not a JSON API)

1. `GET /sb-master/service/create.html?targetAppCode=sb-security&
   targetRegisterAppCode=<register>&service=registerItemSearch` -- renders
   the "Entity Search" page fresh (redirects to
   `/sb-master/viewInstance/view.html?id=<opaque>`). `<register>` is one of
   `sb-br-companies` / `sb-br-businessnames` / `sb-br-investments`, or the
   whole query string can be omitted for "any register".
2. Every such full-page render embeds THREE session-bound values needed for
   the next POST, harvested fresh from THAT SAME response (never
   hardcoded/reused across pages -- they rotate per page render):
   - `webuiConfig.viewInstanceKey` (`_VIKEY_` form field)
   - `webuiConfig.headers().x-catalyst-session-global` (request header)
   - the `<form id="viewInstanceForm" ... action="...update.html?id=...">`
     URL (POST target)
3. The "Search" button's fragment-callback node id (and its AJAX container
   id) are likewise parsed FRESH from the same page -- Catalyst regenerates
   short node ids (`W123` etc.) per view-instance, so nothing is a stable
   constant across sessions.
4. `POST <action>` with form-encoded body `QueryString=<query>&
   SourceAppCode=<register-or-blank>&_CBNODE_=<search button node>&
   _CBNAME_=buttonPush&_CBHTMLFRAG_=true&_CBASYNCUPDATE_=true&
   _CBHTMLFRAGNODEID_=<container>&_CBHTMLFRAGID_=<small int>&_VIKEY_=<vikey>`
   plus header `x-catalyst-session-global` (and `X-Requested-With:
   XMLHttpRequest`) -- returns an HTML **fragment** (wrapped in
   `<!--FB<id>-->...<!--FE<id>-->` markers) containing the results repeater.
5. Each matched entity is an `<a class="appItemSearchResult" onclick=
   "...catCallback('<nodeId>','invokeMenuCb',...)...">Name (RegNum)</a>`
   inside a row that also carries status/incorporation date/sector/type/
   address as `appMinimalAttr`/`appSingleLine` siblings -- all parsed
   generically (see `extractor.py`), not by hand-picking these exact labels.
6. Clicking a match (`POST` the SAME action with `_CBNODE_=<nodeId>&
   _CBNAME_=invokeMenuCb`, this time a FULL submit, not a fragment request)
   redirects (302 -> 200) to the entity's detail page -- its own fresh
   `viewInstanceKey`/session-global/form action, and its "General Details"
   tab pre-rendered. Other tabs (Addresses, Directors, Shares &
   Shareholders, Filings -- the exact set varies by register/entity) are
   each one more fragment POST (`_CBNAME_=tabSelect&_CBVALUE_=<tab index>`)
   against the tabs container's own node id, parsed from the SAME detail
   page's tab `<li>` list.

## Gotcha found during recon: `_CBHTMLFRAGID_` must look like a small integer

This is a client-generated opaque wrapper id (`webuiConfig.guid++` in the
real page's JS) used only to find the `<!--FB<id>-->`/`<!--FE<id>-->`
markers in the response. Sending a non-numeric string (`"x"`) does NOT
error immediately but reliably produces `HTTP 200` with a full-page
`<div class='appFilterError'>...unexpected system error...</div>` render
instead of the expected fragment -- and, worse, appears to leave the
view-instance in a broken state for the REST of that session (every
subsequent request on the same session then also errors, even requests that
worked moments earlier with valid ids). Always send small incrementing
integer strings ("1", "2", "3", ...), never a placeholder string.

## Zero-match signal

A deliberately nonsense query (`zzzznonexistentxyz999`) returns a clean
`HTTP 200` fragment with **zero** `a.appItemSearchResult` links and no error
marker -- used as the reliable "no results" signal (mirrors the pattern
already used for `botswana-cipa-scraper`/`fiji-roc-scraper`).

## Registers

`SourceAppCode` accepts `sb-br-companies` (Companies), `sb-br-businessnames`
(Business Names), `sb-br-investments` (Foreign Investments), or blank
(searches across all three at once -- confirmed mixed Companies/Business
Names badges in one result set for a broad query).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.solomonbusinessregistry.gov.sb"

SEARCH_START_TEMPLATE = (
    f"{BASE_URL}/sb-master/service/create.html"
    "?targetAppCode=sb-security&targetRegisterAppCode={register}&service=registerItemSearch"
)

# `SourceAppCode` dropdown values on the search form (`-- Any register --` is
# blank). Order matches the page's own <option> order.
REGISTERS = {
    "any": "",
    "companies": "sb-br-companies",
    "businessNames": "sb-br-businessnames",
    "investments": "sb-br-investments",
}

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
