# Crawling Method — Malawi CRIPC/MBRS

**Last verified:** 2026-08-26/27

Malawi's official business registrar was the "Registrar General's
Department" (`registrargeneral.gov.mw`, under the Ministry of Trade).
Effective 1 April 2026 its functions transferred to a new statutory agency,
the **Companies, Registrations and Intellectual Property Centre (CRIPC)**
(`cripc.gov.mw`). The actual transactional registry system — **MBRS, the
Malawi Business Registration System** — lives on its own host,
`mbrs.gov.mw`. `mbrs.gov.mw/` (root) 302-redirects to `cripc.gov.mw/` (the
agency's marketing/info site), but every other path on `mbrs.gov.mw`,
including `/search`, serves directly with no redirect — this actor talks to
`mbrs.gov.mw` directly.

## Robots.txt

All three hosts checked (`mbrs.gov.mw`, `registrargeneral.gov.mw`,
`cripc.gov.mw`) serve the exact same stock unmodified placeholder template:

```
# See http://www.robotstxt.org/robotstxt.html for documentation on how to use the robots.txt file
#
# To ban all spiders from the entire site uncomment the next two lines:
# User-agent: *
# Disallow: /
```

Every directive is commented out — **no active `Disallow` rule exists on
any of the three hosts**, and no mention of Claude/ClaudeBot/anthropic-ai/
GPTBot/any AI crawler anywhere in the literal text (checked all three files
in full, not just parsed directives).

## The public search: no login, no CAPTCHA, no WAF

`mbrs.gov.mw/search` is CRIPC's own public "Search for Individuals or
Entities" tool, linked from CRIPC's homepage (`cripc.gov.mw`) under "Quick
Actions" → "Public Search". It is a server-rendered page (backend:
Elixir/Phoenix — `server: Cowboy` response header) with a thin Vue
"global-lookup" component for interactivity, but the **search results are
rendered server-side in the initial HTML response** — there is no separate
JSON/XHR endpoint to call. A plain `GET` with query params is enough:

```
GET https://mbrs.gov.mw/search?type=<entity|individual>&q=<query>&page=<1-based>
```

Sending `Accept: application/json` does nothing — the server always returns
the full HTML page regardless of the Accept header.

Confirmed with a bare `curl` (default TLS, generic UA, no cookies/session)
on the first try — 200 OK with real data. All four `curl_cffi` impersonation
profiles tried (`chrome124`, `chrome131`, `safari17_0`, `edge101`) also
returned 200 with identical content on the first try. No Cloudflare/Akamai/
DataDome markers in headers or body, no CAPTCHA anywhere in this flow, no
rate-limiting seen across a burst of 5 rapid sequential requests. `curl_cffi`
(`chrome124`) is used anyway per this portfolio's default posture, not
because any block was ever observed.

`Signin`/`Signup` links (`/auth/sso-login`, `/auth/register`) exist on the
page but are **not** required to search or read search-result rows — login
is only needed to actually file something (name reservation, new
registration, applying for a certified extract, etc.). Confirmed by paging
through thousands of real entity and individual records with zero
authentication.

## Response shape (HTML, not JSON)

Because the page is server-rendered but its Vue overlay never executes in
this actor (no JS engine), a couple of date fields arrive as literal
unrendered Vue mustache expressions in the raw HTML:

```html
<p class="text-sm font-semibold text-black">{{formatDate('MMM D, YYYY',"2024-11-25" )}}</p>
```

The real ISO date (`2024-11-25`) is still a plain string inside that
expression — `extractor.py`'s `DATE_RE` regex pulls it out directly; no JS
execution needed.

**Entity search** (`type=entity` — covers both incorporated companies and
registered business names/sole-trader names) renders each match as a
"business card" div (`class="mb-3 mt-2 p-4 bg-white rounded-lg ..."`)
containing a registration number (`COY-<code>` for companies, `BRN-<code>`
for business names — **both prefixes appear mixed in the same `type=entity`
result set**, confirmed by searching a generic sole-trader-style term and
getting both), name, registered date, and status.

**Individual search** (`type=individual` — registered business
owners/proprietors) renders each match as an "owner card" div
(`class="cursor-pointer p-4 bg-white border border-gray-100 rounded-lg ..."`)
containing name, status, and — unlike the entity list — a working `View`
link: `<a href='/search/<uuid>?type=owner'>View</a>`.

## Gotcha: entities have NO public detail page; individuals do

Anonymous entity-search result rows carry **no click-through/detail link at
all** — the per-row "Services" dropdown renders as an empty `<ul>` for a
logged-out visitor, on every one of dozens of companies sampled (including
common broad terms like `"Limited"` across 650+ result pages). There is no
`/entities/<id>` or `/companies/<id>` style page reachable without an MBRS
account. **Full company detail — directors, shareholders, share capital,
registered office address, filing history — is genuinely gated behind
login.** This is a real product limitation of the public site, not a
scraping gap, and this actor does not attempt to bypass it (no login
automation or CAPTCHA-solving, per this portfolio's constraints). See the
README's "Notes / limits" for how this is disclosed to users.

Individual ("owner") rows **do** have a real public detail page at
`/search/<uuid>?type=owner`, server-rendering the owner's name, ID type
(e.g. `citizen`), and every business/company they are a registered
proprietor/owner of (same "business card" markup as the entity list, plus
an extra "Owner Type" field, e.g. `Proprietor`). This actor's
`includeOwnerDetails` input (default on) fetches this page for every
matched individual and merges the result in — this is the actor's `detail`
mode, in the only form the site actually supports publicly.

## Pagination

`page=<n>` (1-based) is a plain query param; the results page also renders
an explicit numbered pagination bar (first few pages, an ellipsis, then the
true last page — e.g. `1 2 3 4 ... 653 654 655 656` for one 653-page result
set), confirming the site itself knows the true last page. This actor does
not rely on parsing that number, though — it uses the simpler, more robust
stop condition of this portfolio's general pagination convention: keep
requesting increasing `page` values until a page's card count is zero,
`maxResultsPerQuery` is reached, or `MAX_PAGES_PER_QUERY` (50, a safety cap)
is hit.

## Sample queries tested during recon

- `type=entity&q=Limited` — 653+ pages, ~11 results/page, real companies
  with `COY-` registration numbers (e.g. `COY-QDUKYGD` / "JISA CONSTRUCTION
  LIMITED AND NDABO CONSTRUCTION LIMITED JOINT VENTURE LIMITED").
- `type=entity&q=Chikondi` — a mixed result set of `COY-`/`BRN-` prefixes.
- `type=individual&q=John` — real registered proprietors (e.g. "JOHN
  PETER", "BICKIEL JOHN"), each with a working owner-detail page returning
  their linked businesses (e.g. "MAPANGA BUSINESS TRAINING AND INFORMATION
  CENTER", `BRN-EGSANRE`).
- `type=entity&q=stanbic` — zero exact/substring matches under that literal
  string (the bank is registered under a longer legal name) — correctly
  renders CRIPC's own "name available to reserve" empty state, treated by
  this actor as a `not_found` result, not an error.
- `type=entity&q=zzzzznonexistentqueryxyz123` — genuine zero-match case,
  confirmed same `not_found` handling.

## Known limits

- Company/entity detail (directors, shareholders, capital, registered
  address, filings) requires an MBRS account and is out of scope — this
  actor covers the free public name search plus, for individuals, the
  public owner-detail page. See README "Notes / limits".
- Status has only been observed as `active` across all samples pulled
  during recon; the parser reads whatever text is in the status badge
  verbatim, so other values (e.g. an inactive/deregistered status) would
  pass through correctly if encountered, just weren't seen in samples.
- The entity search matches on literal substring, not fuzzy matching (e.g.
  `"stanbic"` correctly returns zero results since no registered name
  contains that literal substring) — unlike some other registries in this
  portfolio (e.g. Uganda URSB) whose public search is deliberately fuzzy.

## Diff cadence

Quarterly smoke test recommended. CRIPC is a newly-formed agency (effective
1 April 2026) actively consolidating systems from the old Registrar
General's Department — markup/CSS class names on the Vue overlay could
change on a redesign, though the underlying server-rendered HTML structure
this actor depends on has no reason to change independently of a full
front-end rewrite.
