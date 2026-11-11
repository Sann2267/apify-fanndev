# Crawling Method — Samoa Business Registries (MCIL)

**Last verified:** 2026-08-26/27

Samoa's official company register is administered by the **Ministry of
Commerce, Industry and Labour (MCIL)** under the Companies Act 2001. The
public marketing/informational site is `mcil.gov.ws` (Drupal); the actual
transactional register -- the "Online Samoa Company Registry" -- lives on a
**separate domain**, `www.businessregistries.gov.ws`, described on MCIL's own
pages as: "Using the search the register option you can find details of
companies -- both Samoa and overseas companies registered in Samoa."

The app itself carries no vendor branding anywhere in its HTML/JS, but its
protocol fingerprints (cookie `x-catalyst-session-global`, JS globals
`webuiConfig`/`catCallback`/`catHtmlFragmentCallback`, per-session "view
instance" state machine) are the same "Catalyst" framework family as
Botswana's CIPA (`botswana-cipa-scraper`) -- an OLDER, jQuery-driven
generation, not the Vue3 "Verne" SPA used there. **The wire protocol is
completely different** from `botswana-cipa-scraper`'s JSON `commands` batch
API; this one is `application/x-www-form-urlencoded` POSTs with `_CBNODE_`/
`_VIKEY_`-style parameters and HTML-comment-delimited response fragments.
See "The protocol" below.

## Robots.txt

`https://www.businessregistries.gov.ws/robots.txt` returns a plain **HTTP
404** -- the file does not exist. No restriction of any kind, and therefore
no `ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/`anthropic-ai`
mention either (there's nothing to mention).

`https://mcil.gov.ws/robots.txt` (the unrelated marketing site, never
touched by this actor) is a stock Drupal block (`Disallow: /core/`,
`/profiles/`, `/admin/`, `/user/login`, etc.) -- again no AI-crawler mention
of any kind.

## WAF / anti-bot

**None observed.** Plain `nginx` + `PHP/8.2.31` fronting the WordPress-style
marketing pages, and the same plain `nginx` in front of the Catalyst app --
no Cloudflare/`cf-ray`, no CAPTCHA, no rate-limit block across the full
recon session (dozens of requests, including a deliberately-invented garbage
query and rapid sequential searches). A bare `curl` baseline with **no TLS
impersonation at all** worked for every request tried. `curl_cffi`
`chrome124` is used anyway for portfolio-wide consistency, not because a
plain baseline was observed to fail.

## Public access confirmed -- no login anywhere in the flow

`GET /samoa-br-companies/service/create.html?...&service=registerItemSearch`
renders the "Company Search" form as a **guest** session -- a "Logon /
Register" link is present in the nav but is entirely optional. Confirmed
against real, current data: searching "Bank" returns Bank South Pacific
(Samoa), ANZ Bank (Samoa), Samoa Commercial Bank, and The National Bank of
Samoa, each with real registration numbers, incorporation dates, and
addresses. Opening any match's full profile -- General Details, Addresses,
Directors, Shareholders, Share Parcels, and Filings tabs -- returns real
data with **zero login wall on any tab**, confirmed against Bank South
Pacific (Samoa) Limited's 24 directors (current and ceased, spanning Samoa,
Fiji, Papua New Guinea, Singapore) and 8 shareholders (individuals with
citizenship, and a corporate shareholder, BSP Financial Group Limited).

## The protocol

This is a per-session, server-side "view instance" state machine -- **not**
a REST API and **not** the JSON `commands` batch shape used by Botswana
CIPA's Verne app. Every interactive element (search button, pagination
link, a search result's "open detail" link, a tab switch) has a
server-generated node id (e.g. `W870`) that is **different on every fresh
session** -- there is no stable "the search button is always node X"
shortcut. `client.py` re-parses the current page/fragment for the node ids
it needs at every step, exactly as the site's own jQuery does.

### Step 1 — bootstrap a guest session

`GET https://www.businessregistries.gov.ws/samoa-br-companies/service/create.html?targetAppCode=samoa-master&targetRegisterAppCode=samoa-br-companies&service=registerItemSearch&target=samoa-br-companies`
(follow the one redirect it issues). Sets cookie `x-catalyst-session-global`
and returns the search form's HTML, from which the client extracts, by
regex (no JS execution needed -- everything is plain text in the page):

- the form's `action="…/viewInstance/update.html?id=<instance-id>"` URL --
  every subsequent POST for this session goes here
- `viewInstanceKey:'<key>'` from an inline `webuiConfig = {...}` script block
- the `x-catalyst-session-global` token value (same as the cookie, also
  required as a request HEADER on every AJAX POST)
- the "Advanced search" hidden field's name (`nodeW###-Advanced`, varies per
  session)
- the results container's id (`id="AsyncWrapperW###"`)
- the Search button's node id -- found via the class token `appSearchButton`
  (NOT `appSearchResetButton`, a decoy with an overlapping name), since the
  three buttons in the criteria pad have plain sequential node ids, not
  fixed ones

### Step 2 — search (fragment-mode POST)

`POST` to the action URL with `application/x-www-form-urlencoded` body:

```
QueryString=<query>
node<NNN>-Advanced=N
viewInstanceNamespace=
_CBASYNCUPDATE_=true
_CBHTMLFRAGNODEID_=<container id>
_CBHTMLFRAGID_=<any string, echoed back verbatim>
_CBHTMLFRAG_=true
_CBNODE_=<search button node id>
_VIKEY_=<viewInstanceKey>
_CBNAME_=buttonPush
```

and headers `x-security-token: null` (the literal string "null", not an
empty header -- this is what the guest session's own JS sends when the
`x-security-token` cookie is empty), `x-catalyst-session-global: <token>`,
`x-catalyst-async: true`, `x-catalyst-secured: true`,
`X-Requested-With: XMLHttpRequest`.

The response is a **full HTML document**, not a bare fragment -- the actual
result content is wrapped in `<!--FB<id>--> ... <!--FE<id>-->` HTML comments
(`<id>` = the `_CBHTMLFRAGID_` value sent), mirroring the site's own
client-side `catUnwrapFragment`. `extractor.unwrap_fragment` extracts the
middle.

**The single biggest recon gotcha:** the very first (correctly-working)
attempt still failed, because the search button's, container's, and
"Advanced" field's node ids were captured from a *different* page fetch
(a stale/earlier session) than the `_VIKEY_`/action URL used in the POST.
**Every one of these ids is scoped to one specific session/view-instance and
is regenerated on every fresh `GET`** -- mixing ids from two different
fetches produces an HTTP 200 response that *looks* plausible (a full,
well-formed page) but is actually just the app's generic root/dashboard
shell with an empty `app-ns-` (service/context) class, silently dropping out
of the search flow entirely. There is no error status code or message --
only that one empty CSS class distinguishes it from a real result. Always
re-parse every node id from the SAME response that produced the
`_VIKEY_`/action URL being POSTed to.

### Step 3 — result rows and pagination

Each match is one `<div class="…appRepeaterRowContent…">` sibling (10 per
page). Per row: the entity name + registration number (`"<NAME>
(<NUMBER>)"` inside an anchor whose `onclick` calls
`catCallback('<nodeId>','invokeMenuCb',...)`), a type badge (only
`"Companies"`/`COM` was ever observed -- see "Known limits"), status,
incorporation date, business activity, company type, address, and any
previous names (a nested sub-repeater).

**Second gotcha:** the naive regex for "name (number)"
(`<span>([^<(]*)\s*\((\d+)\)</span>`, excluding literal `(` from the name)
silently matched ZERO rows for names that themselves contain parentheses --
e.g. `"DIGICEL (SAMOA) FINANCIAL SERVICES LIMITED (0460)"` -- because the
regex engine stopped at the first `(` (before "SAMOA") and then failed to
find `\d+\)</span>` immediately after. Not a crash, not an exception -- it
just silently produced a 0-result page for a query with real, confirmed
matches, indistinguishable from a genuine no-match response by shape alone.
Fixed by using a *greedy* `.*` for the name (backtracking correctly lands on
the LAST `"(<digits>)"` immediately before the closing tag) instead of
excluding `(` from the character class. This is the same *class* of bug as
Fiji ROC's `SearchName` gotcha and Botswana CIPA's flag-inversion gotcha:
low-frequency queries (`"Bank"`) worked fine and gave false confidence;
broader/differently-shaped ones (`"Digicel"`, `"Samoa"`) exposed it.

Genuine zero-match queries return a **clean, unambiguous** marker:
`<div class="appSearchNoResults" id="appSearchNoResults" ...>No search
results found</div>`, with zero result rows. (Note: naively grepping for the
substring `"no results"` case-insensitively MISSES this marker, because the
actual text is `"No search results found"` -- `"search"` sits between `"No"`
and `"results"`.) Unlike Botswana CIPA's Verne app (where the analogous
`noResults` template string is present even alongside real matches), this
marker's presence is a reliable, unambiguous "genuinely zero matches"
signal.

Pagination: the pager's "Page N" links call
`catHtmlFragmentCallback('<pagerNodeId>','selectPage',N,{...})` -- same
POST shape as the initial search, just swapping `_CBNODE_`/`_CBNAME_`/
`_CBVALUE_` for the pager's node id / `selectPage` / the page number, and
resending the original `QueryString`. Confirmed working across a 25-row,
3-page fetch (10+10+5) for the query `"Samoa"` with zero duplicate rows.
The register showed as many as ~60 pages (~600 rows) for that broad query --
this actor caps at 10 pages (100 rows) per query to bound run time; see
`constants.RESULTS_PAGE_SIZE`.

### Step 4 — open a company's detail page

Clicking a result's name link is a **full page navigation** in the real
site (`catCallback`, not `catHtmlFragmentCallback` -- no `_CBHTMLFRAG_`
flags at all), which this actor replicates as a plain POST with
`allow_redirects=True`. The response chain is:
`POST update.html?id=<search-instance-id>` (body: `_CBNODE_=<row's node
id>`, `_CBNAME_=invokeMenuCb`, plus the same `QueryString`/`Advanced`/
`viewInstanceNamespace` fields as the search) → **302** to
`service/createVersion.html?service=brViewCompany&domainName=Item&
versionIdentifier=...&relator=...` → **302** to
`viewInstance/view.html?id=<NEW-instance-id>` → **200**, the full "View
...Company Details" page, titled e.g. `"View Private Company Details"`.

This new page is its OWN view instance (its own `action` URL and
`_VIKEY_`, unrelated to the search instance's) and embeds the "General
Details" tab (index 0) directly -- registered name, type, status,
incorporation/re-registration dates, rules, business activity, annual
return filing month/last-filed date, contact name/phone/fax/email, previous
name, start/end dates.

### Step 5 — the other five tabs

The tab strip (`General Details / Addresses / Directors / Shares &
Shareholders / Share Parcels / Filings`) is one `<ul class="appTabs"
id="tabul<NNN>">`; each tab's `onclick` calls
`catHtmlFragmentCallback('<NNN>','tabSelect',<index 1-5>,{asyncUpdate:true,
containerSelector:'#AsyncWrapper<NNN>'})` -- same fragment-POST shape as
search, `_CBNAME_=tabSelect`, `_CBVALUE_=<index>`, `_CBNODE_=<NNN>` (the tab
strip's OWN node id, reused for every tab in that detail view instance).
Confirmed real, current data across all five: Addresses (Registered Office
/ Postal / Address for Service, each with a Start/End Date history), Directors
(name, residential + postal address, consent date, ceased date for
historical directors), Shareholders (individual `Name`/`Citizenship` or
corporate `Entity Name`/`Place of Incorporation`, appointed/ceased dates,
whether also a director), Share Parcels (`Number of shares` per
shareholder), and Filings (form name, submitted timestamp, filed/completed
timestamp -- 20-30 filings on file for an actively-trading company).

**Third gotcha -- the row-splitting marker:** search-result rows render
`appRepeaterRowContent` as the FIRST class token
(`class="appRepeaterRowContent appRowOdd..."`), but every detail-tab row
(addresses/directors/shareholders/share parcels) renders it AFTER
`appReadOnly ` instead (`class="appReadOnly appRepeaterRowContent..."`).
Splitting on the literal `class="appRepeaterRowContent` (anchored to the
start of the attribute) silently found rows on search pages but ZERO rows
on every detail tab -- again no error, just an empty list, easy to mistake
for "this company has no directors on file." Fixed by splitting on the bare
substring `appRepeaterRowContent` instead of anchoring to `class="`.

**Fourth gotcha -- duplicated date/text values:** many field values are
rendered as a visible copy plus a screen-reader "offscreen" duplicate, e.g.
`<div class="appAttrValue">04-Mar-2003<span class="appOffScreenText">
04-Mar-2003</span></div>`. Naively stripping HTML tags turns this into
`"04-Mar-200304-Mar-2003"`. The exact markup pairing varies (sometimes
plain-text-then-span, sometimes two spans back to back), so
`extractor.clean_value` doesn't pattern-match the markup at all -- it
strips tags first, then checks whether the FLATTENED text is literally its
own first half repeated (`text == half + half`) and collapses to one copy
if so. Verified against dozens of date/name fields with no false collapses
observed (short field values like company names were never coincidentally
self-repeating in the data seen during recon).

**Residual quirk (not a bug, left as-is):** the top-level `Start Date`/`End
Date` fields (populated only when a company has a logged name-change event)
occasionally still show a doubled value, e.g. `"18-Jul-1977 00:00:0018-Jul-
1977 at 00:00:00 Apia Standard Time"`. Here the "duplicate" pair is NOT
byte-identical (a short `HH:MM:SS` rendering next to a longer `"at HH:MM:SS
<timezone>"` rendering of the SAME instant), so `clean_value`'s
half-equals-half collapse correctly does not fire (it would be wrong to
guess at general date-reformatting). Left as raw passthrough rather than
hand-rolling a timezone-aware date parser for two rarely-populated fields.

## What's NOT implemented

- **Filing document download.** Each filing row's link
  (`catCallback('<id>','openFiling','openFiling',{})`) opens the actual
  lodged document (likely a PDF, e.g. the annual return form itself). This
  actor only captures the filing's metadata (form name + two timestamps),
  not the document -- not pursued due to time, not because it looked
  gated. A future extension could follow the same "full navigation POST,
  follow redirects" pattern used for the detail page.
- **Director/Shareholder search** (a second menu link,
  `service=registerItemRoleSearch`, "find out whether a named individual is
  or has been a director/shareholder of any company") was seen in the nav
  but not built -- out of scope for this actor's company-name/number search
  focus.
- **Secured Transactions / PPSR search** (a completely separate register,
  `samoa-st-securityinterests`, for security interests over personal
  property) is a different legal register entirely and out of scope.
- Only one entity-type badge (`"Companies"` / `COM`) was ever observed
  across all queries tried (`"Bank"`, `"Digicel"`, `"Samoa"`) -- unlike
  Botswana CIPA, this register did not surface separate categories for
  business names / external companies / close corporations in results, so
  no `entityType` input filter was added (there was nothing observed to
  filter by).

## Sample entities tested

- **Bank South Pacific (Samoa) Limited** (`0650`) -- 24 directors (current
  and ceased, spanning Samoa/Fiji/PNG/Singapore), 8 shareholders (mix of
  individuals with citizenship and the corporate shareholder BSP Financial
  Group Limited), 3 address records, registered 18-Jul-1977.
- **Digicel (Samoa) Financial Services Limited** (`0460`), **Digicel
  Financial Services (Samoa) Ltd** (`0999`, status Removed), **Digicel(Samoa)
  Limited** (`0456`, 22 directors, 2 corporate shareholders -- CSL Mobile
  Ltd and Digicel Pacific Finance Limited, 30 filings) -- all three found by
  a single `"Digicel"` query, including one previous-name match
  (`"TELECOM SAMOA CELLULAR LIMITED"`).
- **Samoa Commercial Bank Limited** (`0452`) and **The National Bank of
  Samoa Limited** (`0493`) -- found by `"Bank"`, full detail + filings
  confirmed.
- `"Samoa"` (deliberately broad) -- confirmed multi-page pagination (25 rows
  across 3 pages, zero duplicates) out of roughly 600 total matches (~60
  pages) the register itself reports.
- `"zzzznonexistentxyz999"` (deliberately nonexistent) -- confirms the clean
  `_error: "not_found"` path via the `appSearchNoResults` marker.

## Diff cadence

Quarterly smoke test recommended -- this is a live, actively-developed
government citizen-services platform (the "Catalyst" framework); a version
upgrade could regenerate node ids differently or change the fragment-wrapper
marker format.
