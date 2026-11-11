# Crawling Method — Solomon Islands Business Registry

**Last verified:** 2026-08-27

The Solomon Islands' official company/business register is the **Solomon
Islands Business Registry** ("Company Haus"), run by the Registrar of
Companies, a Division of the Ministry of Commerce, Industries, Labour and
Immigration (MCILI). Confirmed via web search + on-site copy: the
marketing/help site is `www.solomonbusinessregistry.gov.sb`
(WordPress, theme literally named `catalystALFREDO-2.7`, footer "Powered by
Foster Moore"), and the real transactional search/profile app lives at
`/sb-master/...` (search) and per-register app codes like
`/sb-br-companies/...` / `/sb-br-businessnames/...` / `/sb-br-investments/...`
(entity profile) on the SAME origin.

**This is the same "Verne"/Foster Moore "Catalyst" citizen-services platform
already used by `botswana-cipa-scraper`** (footer link `http://www.fostermoore.com`
on both), but a materially different, older webui version (`v4.4.4`): classic
server-rendered HTML + jQuery AJAX form posts with session-scoped node ids,
not Botswana's JSON-command SPA wire format. The two actors' wire protocols
do not share code.

## Robots.txt

`https://www.solomonbusinessregistry.gov.sb/robots.txt` is a plain HTTP
**404** — the file does not exist. No restriction of any kind, and therefore
no `ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/`anthropic-ai`
mention either (there's nothing to mention). The separate WordPress site
`commerce.gov.sb` (the ministry's own site, not used by this actor) has a
stock `Disallow: /wp-admin/` robots.txt, also with no AI-crawler mentions —
irrelevant here since this actor never touches that host.

## WAF / anti-bot

**None observed.** Plain `nginx`, no Cloudflare/`cf-ray`/challenge markers,
no CAPTCHA, across 100+ requests during recon (`curl_cffi` `chrome124`,
`chrome131`, `safari17_0`, `edge101` all returned clean `200`s on the
homepage on first try). `curl_cffi` `chrome124` is used in the shipped
client for portfolio-wide consistency.

## What's genuinely public (no login)

The homepage's own copy: *"...an electronic register which can be accessed
24 hours a day... searches are FREE and you don't need to log on."*
Confirmed live, starting from a completely fresh session with zero cookies:
searching AND opening full entity profiles — including **Directors,
individual Shareholders with their exact share counts, registered/postal
addresses, and complete filing history (every annual return on file, with
submission/filed timestamps)** — all work with no auth prompt anywhere. This
is richer free public data than several other actors in this portfolio.

### Step-by-step

1. `GET /sb-master/service/create.html?targetAppCode=sb-security&
   targetRegisterAppCode=<register>&service=registerItemSearch` — renders
   the "Entity Search" page fresh (redirects to
   `/sb-master/viewInstance/view.html?id=<opaque>`). `<register>` is one of
   `sb-br-companies` / `sb-br-businessnames` / `sb-br-investments`, or blank
   for "any register" (searches all three, confirmed mixed `Companies`/
   `Business Names`/`Foreign Investments` badges in one result set).
2. Every full-page render embeds THREE session-bound values needed for the
   next POST — `webuiConfig.viewInstanceKey` (`_VIKEY_` form field),
   `webuiConfig.headers()['x-catalyst-session-global']` (a request header,
   not just a cookie), and the `<form id="viewInstanceForm" action="...
   update.html?id=...">` POST target — **harvested fresh from that SAME
   response every time**, never hardcoded or reused across pages/sessions.
3. Interactive control node ids (the Search button, each tab) are likewise
   parsed fresh from the same page/response — Catalyst regenerates short
   node ids (`W123` etc.) per view-instance; nothing is a stable constant.
4. `POST <action>` (form-urlencoded) with `QueryString=<query>&
   SourceAppCode=<register-or-blank>&_CBNODE_=<search button node>&
   _CBNAME_=buttonPush&_CBHTMLFRAG_=true&_CBASYNCUPDATE_=true&
   _CBHTMLFRAGNODEID_=<container>&_CBHTMLFRAGID_=<small int>&
   _VIKEY_=<vikey>` + header `x-catalyst-session-global` — returns an HTML
   **fragment** (wrapped in `<!--FB<id>-->...<!--FE<id>-->` markers, though
   the fragment content itself is what's parsed — the markers aren't needed
   since a full HTML parse of the response body finds the same content
   either way) containing the results repeater.
5. Each matched entity is `<a class="appItemSearchResult" onclick="...
   catCallback('<nodeId>','invokeMenuCb',...)...">Name (RegNum)</a>` inside
   a row that also carries status/date/sector/address as sibling
   `appMinimalAttr` (label/value) and `appSingleLine` (address) widgets.
6. Clicking a match — `POST` the SAME action with `_CBNODE_=<nodeId>&
   _CBNAME_=invokeMenuCb` as a **FULL form submit** (all current form field
   values included, `_CBHTMLFRAG_` NOT set — matches the real page's
   `catCallback`, which does `form.submit()`, unlike the async
   `catHtmlFragmentCallback` used for search/tabs) — redirects (302→200) to
   the entity's own detail page, with its own fresh `viewInstanceKey`/
   session-global/action, and the "General Details" tab pre-rendered.
7. Every other tab (Addresses, Directors, Shares & Shareholders, Filings for
   Companies; Addresses, Owners, Filings for Business Names — the exact set
   is read from the page, never hardcoded) is one more fragment POST
   (`_CBNAME_=tabSelect&_CBVALUE_=<tab index>`) against the tabs container's
   own node id.

## Two gotchas found during recon

### 1. `_CBHTMLFRAGID_` must look like a small integer

This is a client-generated opaque wrapper id (`webuiConfig.guid++` in the
real page's JS), used only so the server can wrap the fragment in matching
`<!--FB<id>-->`/`<!--FE<id>-->` markers. Sending a non-numeric placeholder
(`"x"`) does **not** error immediately — it returns `HTTP 200` with a
full-page `<div class='appFilterError'>...unexpected system error, code
239-xxxxxxxx...</div>` render instead of the fragment. Worse: this appeared
to leave the view-instance broken for the **rest of that session** — every
subsequent request on the same session then also failed with the same
error, even tab requests that had worked moments earlier with valid ids, in
a fresh-session A/B retest. The shipped client always sends small
incrementing integer strings (`"1"`, `"2"`, `"3"`, ...).

### 2. Search-result rows and detail-page tabs use TWO different label/value widget classes

The detail page (and its tabs) label fields with `appAttrLabelBox` (wrapping
an `appLabelText` span) + a sibling `appAttrValue` div. Search-result rows
use a **completely different** widget for the same kind of data:
`appMinimalAttr` wrapping `appMinimalLabel` + `appMinimalValue` spans. A
version of the generic extractor that only handled the first pattern
silently produced summary rows with only `label`/`name`/`registrationNumber`
and no status/date/sector fields — caught by comparing extracted output
against a raw HTML dump of a real "Bank" search before shipping. Both
patterns are now extracted (see `extractor.extract_search_results`).

## Generic, domain-agnostic detail extraction — not hardcoded fields

The registry exposes no traditional JSON REST API, and each register
(Companies/Business Names/Foreign Investments) uses **different tab sets and
field labels** for conceptually similar data (e.g. Companies' `Company
Status` vs Business Names' `Business Name Status`; Companies' `director`/
`shareholderInd` vs Business Names' `ownerind`). Rather than hand-picking
field names per register, `extractor.py` walks the HTML generically:

- **Flat fields**: every `appAttrLabelBox`/`appAttrValue` pair not inside a
  nested repeater's row becomes `{label_text: value_text}`, using the
  registry's own exact label text as the key (including its own spacing —
  raw passthrough, not normalized).
- **Repeated records** (directors, shareholders, addresses, filings, ...):
  Catalyst renders these as `appRepeater` (older widget) or `appRepeaterNew`
  (newer widget, seen on the Directors tab) wrappers. The group's name is
  taken from the longest dash-joined CSS class on the repeater itself, or —
  when the repeater's own class doesn't carry one (the `appRepeaterNew`
  case) — from its first row's `appRecord*` wrapper class instead (e.g.
  `...-directorRepeater-director` → `director`). Each row is recursively
  walked the same way, so a nested sub-repeater (e.g. a contact's separate
  phone/email repeaters) becomes a nested list under its own name.
- **One more widget family**: the Filings tab doesn't use
  `appAttrLabelBox`/`appAttrValue` at all — it has bespoke
  `appFilingName`/`appFilingSubmitted`/`appFilingEnd` divs. Generalized by
  stripping the shared `appFiling` class prefix rather than hardcoding those
  three names, so a future addition to that widget (if any) would still be
  captured under whatever name Catalyst gives it.

**Critical implementation detail**: repeater rows must be selected with
`:scope > .appRepeaterContent > .appRepeaterRowContent`, not a bare
`.select('.appRepeaterContent > .appRepeaterRowContent')`. The latter
matches **any** descendant, including a nested sub-repeater's own rows deep
inside the current repeater's row — silently duplicating those rows into the
outer group as well as the (correct) nested location. Caught by comparing
output against a hand-traced fixture (a director's nested phone/email
contact repeaters) before shipping.

## Zero-match signal

A deliberately nonsense query (`zzzznonexistentxyz999`) returns a clean
`HTTP 200` fragment with **zero** `a.appItemSearchResult` result links and no
error marker — the only reliable "no results" signal found (mirrors the
pattern already used for `botswana-cipa-scraper`/`fiji-roc-scraper`).

## Sample entities tested

- **3N Solomons Limited** (`20111873`, Companies) — full profile: 3
  directors, 3 individual shareholders (with share counts totaling the
  50,000 total shares on file), registered office + postal address, 20
  filings (2007–2026 annual returns).
- **"Bank"** (broad name search, any register) — 10 matches spanning
  `Companies`/`Business Names`/`Foreign Investments` badges in one result
  set, including duplicate legal names registered under different
  register types (e.g. "Australia and New Zealand Banking Group Limited"
  as both a Company and a Foreign Investment).
- **AJW Banking Agent** (`BN20251334`, Business Names) — confirms the
  generic extractor adapts cleanly to a different tab set (`General
  Details`, `Addresses`, `Owners`, `Filings` — no Directors/Shareholders)
  and different field labels (`Business Name Number`, `Primary Business
  Activity`) with zero register-specific code.
- **`zzzznonexistentxyz999`** — confirms the clean `not_found` path.

## Known limits

- No pagination is implemented beyond a single search response's result
  set — `maxResultsPerQuery` (default 20, max 200) caps how many are pulled
  per query, not a registry limitation; a very broad single-letter query may
  not surface every match.
- Field labels and available tabs genuinely differ by register/entity type
  (see above) — this is upstream's own design, passed through as-is rather
  than forced into one fixed schema.
- A "Request Extract or Certificate" action is visible on the detail page
  but not pursued — it's a paid document-generation feature, not additional
  free public data, and out of scope for a read-only scraper.

## Diff cadence

Quarterly smoke test recommended (Foster Moore/Catalyst is a maintained
commercial platform; a version upgrade could change node-id generation,
widget class names, or the fragment-callback field requirements documented
above).
