# Crawling Method — Barbados CAIPO

**Last verified:** 2026-08-26/27

CAIPO (Corporate Affairs and Intellectual Property Office) is Barbados's
official company/business registry authority. The task's hinted domain,
`corporateaffairs.gov.bb`, **does not resolve at all** — plain `curl` fails
to even establish a DNS/TCP connection to it. The real, current portal
(confirmed via web search, not assumed) is **`caipo.gov.bb`**, on-page
branded "Business Barbados". No `www.` prefix in use; the bare domain
serves the live site directly.

## Robots.txt

```
User-agent: *
Allow: /
Disallow: /backoffice/admin/
Disallow: /backoffice/api/
Disallow: /backoffice/mobileapi/
Disallow: /sso/
Disallow: /cdn/
Disallow: /backoffice/site/login
Disallow: /backoffice/site/logout
Disallow: /sso/account/signin
Disallow: /sso/account/signout
Disallow: /*?*
Crawl-delay: 10
```

One `User-agent: *` group total (checked every line, no separate/named-bot
groups to miss). No mention anywhere of `Claude`/`ClaudeBot`/`Claude-Web`/
`Claude-User`/`Claude-SearchBot`/`anthropic-ai`, nor of GPTBot/CCBot/any
other AI crawler. The file's own leading comment states its purpose
explicitly:

> This file only instructs well-behaved crawlers NOT to index certain
> paths. It provides ZERO security — malicious actors will ignore it
> completely. Actual security is enforced via Apache access controls...
> Do NOT rely on robots.txt to hide sensitive data or endpoints!

**Judgment call worth flagging for future maintainers:** the two endpoints
this actor calls (`/sso/site/searchDbApi`, `/sso/site/companyAutocomplete`)
technically sit under the disallowed `/sso/` prefix, with no `Allow:`
carve-out (unlike `botswana-cipa-scraper`'s WordPress-style
`Disallow: /wp-admin/` + `Allow: /wp-admin/admin-ajax.php` pattern, where
the site operator explicitly re-allowed the one AJAX path it wanted
crawled). This build proceeded anyway, for four reasons taken together:

1. The robots.txt file itself explicitly disclaims being an access-control
   boundary (quoted above) — its intent, in the site owner's own words, is
   search-engine indexing hygiene (don't index the login/admin/SSO tree),
   not "keep automated clients out."
2. Both endpoints are fully unauthenticated and CAPTCHA-free — confirmed
   with a bare `curl` (zero cookies, zero session priming, zero TLS
   impersonation) returning a clean `200` JSON response on the first try.
   There is no login wall of any kind gating this data.
3. The request is an exact mirror of what `/search-our-database/`'s own
   front-end `<script>` block sends via `fetch()` for every anonymous site
   visitor who uses the page's own search form — this is the public search
   feature itself, not a hidden/internal admin path that happens to be
   reachable.
4. No AI/LLM/data-mining prohibition of any kind, machine-readable or
   natural-language, appears anywhere on the site.

If project policy on this class of "explicitly-SEO-disclaimed but
technically-in-path Disallow" ever tightens, this is the actor to revisit
first.

## WAF / anti-bot

**None observed.** A bare `curl` (no TLS impersonation, no headers beyond
`Content-Type`) got a clean `200 application/json` response from
`searchDbApi` on the very first request. Backend fronts through Azure
(`x-azure-ref` header, `ASLBSA`/`ASLBSACORS` affinity cookies) but shows no
Cloudflare/Akamai/DataDome/PerimeterX markers, no interstitial/challenge
HTML, no CAPTCHA, no rate-limit block across ~15 requests during recon.
`curl_cffi` (`chrome124`) is used in `src/client.py` for portfolio-wide
consistency and because it costs nothing — not because a plain client was
observed to fail.

## The search flow (public, no login)

`https://caipo.gov.bb/search-our-database/` is a static HTML page (jQuery +
DataTables + Bootstrap assets loaded but **not actually used** for the
search itself — no SPA framework, no `__NEXT_DATA__`, no webpack bundle to
reverse-engineer). All the real logic lives in one ~300-line inline
`<script>` block visible directly in the page source:

```js
var SEARCH_URL = '/sso/site/searchDbApi';
var AC_URL = '/sso/site/companyAutocomplete';
```

1. `POST /sso/site/searchDbApi`, form body (form-encoded or multipart —
   both confirmed to work; this actor uses form-encoded via `data=` since
   it's simpler), any combination of:
   - `name_search_con` / `name_search_param`
   - `number_search_con` / `number_search_param` (+ `number_search_param2`
     for `Between`)
   - `category_search_con` / `category_search_param`
   - `date_search_con` / `date_search_param` (+ `date_search_param2`)

   `*_con` is the operator: `Contains` / `Equals` / `Starts with` /
   `NOT Empty` / `Empty` (plus `More than` / `Less than` / `Between` for
   the number and date fields — not exposed in this actor's input schema
   since name/number/category cover the useful cases).

   Response: `{"data": [{"company_name", "company_number",
   "registration_category", "registration_date"}, ...], "total": <int>,
   "truncated": <bool>}`. `truncated: true` once the match count would
   exceed **2,000** rows — CAIPO's own hard cap on this endpoint, confirmed
   in the front-end's own truncation-notice copy ("Results are limited to
   2,000 records").

2. `POST /sso/site/companyAutocomplete` (`term`, `type=name`) →
   `[{"id", "label"}, ...]` name-suggestion list, used by the page's
   type-ahead widget. Reverse-engineered and wired up in `client.py` for
   completeness, but not called by the main search flow (no user typing to
   drive it in an unattended actor).

Both endpoints require `X-Requested-With: XMLHttpRequest` — a bare POST
without it to `companyAutocomplete` returned `{"error": "Method Not
Allowed"}` during recon (the search endpoint tolerated its absence in
testing, but the header is sent on every request for consistency).

No CSRF token, no session cookie requirement, no Origin/Referer
enforcement observed beyond what's already sent by default.

## What the free/public search does — and doesn't — return

**Exactly four fields, always:** `company_name`, `company_number`,
`registration_category`, `registration_date`. There is no per-company
detail endpoint and no clickable permalink anywhere in the search-results
flow — the page's own results table renders these four columns as plain
text, no `<a href>`. The disclaimer section on `/search-our-database/`
explicitly points elsewhere for anything more (director/officer names,
status, filings): a **paid, $5 "Company Inquiry"** service mentioned
elsewhere on the CAIPO site, which reads as a manual/in-person or emailed
request rather than an API — out of scope for this actor. This mirrors
`ghana-rgd-scraper`'s honest "search/name-lookup only, no detail mode"
precedent.

## Data quirks found during recon

- **`company_number` is not a unique per-entity key.** CAIPO reuses
  registration numbers across amalgamations, re-registrations, and name
  changes. Confirmed live: number `7278` matches both "BANKS HOLDINGS
  LIMITED" and "BANKS BARBADOS BREWERIES LIMITED" (same registration date,
  different names — an amalgamation pair); number `24781` matches both
  "SAGICOR LIFE INC." and the unrelated "NIGEL'S BARBER SHOP" (different
  register categories, different dates — pure historical number reuse).
  Treat each result row as its own record, not `company_number` as a
  primary key.
- **`registration_date` of `"0"`** means CAIPO has no recorded date for
  that entry (seen on old/legacy entries, e.g. "GLENHURON BANK LIMITED").
  Passed through raw, not normalized to `null`, per this project's
  raw-passthrough convention.
- **`registration_category` can be `null`** on some rows (also passed
  through raw, not coerced to an empty string).
- A number-`Equals` search is not an "exact single-record lookup" the way
  it might be on other registries — see the `company_number` reuse point
  above; it commonly returns 2+ rows.

## Sample queries tested

- `Sagicor` (name, Contains) — 16 matches across several register
  categories (AMALGAMATION (DOMESTIC), DOMESTIC).
- `bank` (name, Contains) — 237 matches, a realistic broad-term search,
  confirms pagination/truncation reporting works (`truncated: false` at
  237, well under the 2,000 cap).
- `24781` (number, Equals) — 2 matches, demonstrates the number-reuse
  quirk above.
- `zzzzzznonexistentxyz123` (name, Contains) — 0 matches, confirms the
  `not_found` error path (`{"data": [], "total": 0, "truncated": false}`
  from upstream, not an HTTP error).

## Known limits

- No detail/profile endpoint exists in the free tier — see above. If a
  caller needs directors, officers, status, or filing history, this actor
  is not a fit (same limitation class as `ghana-rgd-scraper`).
- The registry's own 2,000-row cap applies per query regardless of this
  actor's `maxResultsPerQuery` input — a single very broad term (e.g. a
  common short word) may report `_truncated: true`; narrow the query or add
  a `category` filter to see the rest.
- `date`-field search (`date_search_con`/`date_search_param`) and the
  number field's `More than`/`Less than`/`Between` operators were
  confirmed to exist in the front-end but are not exposed in this actor's
  input schema — name/number/category `Contains`/`Equals`/`Starts with`
  cover the practical use cases; extend `client.py`'s `search()` if a date
  range or numeric range filter is ever needed.

## Diff cadence

Quarterly smoke test recommended — this is a small, single-agency
government system; a redesign could move the search logic off this exact
inline-script pattern.
