# Crawling Method — Ethiopia eGP Tenders

**Last verified:** 2026-08-27

Ethiopia's official electronic Government Procurement (eGP) portal is
`egp.gov.et`, operated by the Public Procurement and Property
Administration Agency (PPPAA/PPA). It is an Angular SPA calling a .NET
microservices backend under `/po-gw/...` (gateway path baked into the
frontend's build-time environment config: `urls.api = "/po-gw"`). The
backend is **Perago Systems'** "procure-ai"/ERP e-GP platform — the same
vendor family already seen twice elsewhere in this portfolio (Sierra
Leone's NPPA, whose backend was down for 10+ minutes at build time; and
Malawi's MANEPS, a client-rendered SPA with no working API ever found).
Ethiopia is the first deployment of this vendor in the portfolio where the
JSON API behind the SPA was successfully reverse-engineered end-to-end.
The corporate site `www.ppa.gov.et` (WordPress) is separate and unused by
this actor.

## Robots.txt

- `GET https://egp.gov.et/robots.txt` → HTTP 200, but with the **same
  4,519-byte SPA shell** returned for literally any path on this host
  (confirmed with a nonsense path, `/egp/robots.txt`, and several guessed
  static-config filenames — all identical). This is a pure client-side
  routed Angular app with no server-side `robots.txt` route configured at
  all — no restriction exists, blanket or otherwise, and no bot is named.
- `GET https://www.ppa.gov.et/robots.txt` (the separate WordPress
  corporate site, not used by this actor) → HTTP 200, clean:
  ```
  User-agent: *
  Disallow: /wp-admin/
  Allow: /wp-admin/admin-ajax.php
  Disallow: http://www.ppa.gov.et/wp-content/uploads/wpforms/
  Sitemap: https://www.ppa.gov.et/wp-sitemap.xml
  ```
  No blanket disallow, no Claude/ClaudeBot/anthropic-ai mention, no
  natural-language prohibition.

## WAF / anti-bot

**None found.** Plain `nginx/1.24.0` in front of the static Angular
bundle, and a bare `.NET`/Kestrel-style JSON API behind the `/po-gw`
gateway — no Cloudflare/DataDome/Akamai markers in headers or body, no
CAPTCHA anywhere this actor touches, no rate limiting observed across
dozens of rapid sequential requests while reverse-engineering the API.
`curl_cffi` (`chrome124`) impersonation is used anyway as this portfolio's
default posture (`.ai/CLAUDE.md` principle #2). `proxyConfiguration`
defaults to off for the same reason. One real access-control signal was
found: POSTing to the gateway triggers `{"code":"hmac_auth_failed"}` — an
HMAC-signed-request layer guards write/mutating calls, but **does not
apply to the GET endpoints this actor uses**, confirming the read-only
surface is genuinely intended to be open.

## Login wall — none for the data this actor uses

Every endpoint this actor calls returns data with **no cookie beyond a
bare session and no account**. As a direct contrast check: the *private*
sibling endpoint `tendering-int/api/packages/get-packages` (no `-public-`
in the name) returns a clean `401` for the same anonymous request that
succeeds against the public endpoints below — proving the public/private
split on this platform is a deliberate, working access-control boundary,
not an accident this actor is exploiting.

## Data source — reverse-engineering path

`egp.gov.et` ships zero data server-side (pure Angular SPA, `<egp-portal-root>`
with a loading spinner). The path to a real JSON API:

1. **Downloaded and grepped all 66 webpack chunks** referenced by the
   app's `runtime-*.js` chunk-hash manifest, looking for hardcoded
   `https://` hosts. Found `www.peragosystems.com` and
   `procure-ai.api.dev.peragosystems.com` in the bundle — first hard
   confirmation of the Perago Systems vendor for this country.
2. **Found the environment/API-gateway config as a real (not inlined)
   object literal** inside the main bundle: `urls:{api:localStorage.getItem
   ("api")?localStorage.getItem("api"):"/po-gw", auth: ...}` — i.e. the
   frontend calls same-origin `/po-gw/<service>/api/<...>` by default.
   (A plain-guess catch-all check confirmed `egp.gov.et` itself serves the
   identical SPA shell for *any* unmatched path — so blind path guessing
   against that host alone would never have found this; the gateway
   prefix had to be recovered from the bundle.)
3. **`https://egp.gov.et/po-gw/swagger/index.html` is publicly exposed** —
   full Swagger UI listing 20+ microservices (tendering, cms-v2,
   registration, auctioning, purchasing, complaint, contract-catalogs,
   commodities, etc.), each with a machine-readable OpenAPI JSON at
   `/po-gw/swagger/docs/v1.0.0/<service>`. This was the actual breakthrough
   — it gave exact query-parameter names/types instead of continuing to
   blind-guess against the minified JS.

## Known limits — the "live open tenders" endpoint is broken upstream

The endpoint that would intuitively serve this actor's purpose,
`tendering-int/api/packages/get-public-packages` (and its archived
counterpart `get-archived-public-packages`), is **reachable anonymously
but unconditionally crashes** whenever asked to actually return items:

- `Count=true` (count-only) → `HTTP 200 {"total":0,"items":[]}` — works,
  but only reports a total, no records.
- `Count=false` (fetch items), with **no** `OrderBy` → `HTTP 400
  System.ArgumentNullException` (`ParamName: "o"`) inside
  `ERP.Tendering...PackageQueryPG.GetInvitationToBidAsync`, every time.
- Supplying an explicit `OrderBy[0].field=<name>` avoids the crash **only**
  for a small set of literal DB column names, and every semantically
  obvious field name tested (`id`, `packageId`, `lotInPackageId`, `status`,
  `organizationId`, `procurementClassification`, `createdAt`, dotted
  nested paths) instead **still hits the same ArgumentNullException** — a
  handful of "special" join-backed fields the query builder can't order by
  without extra config this actor has no way to supply. Every *other*
  field name tried (`submissionDeadline`, `closingDate`, `deadline`,
  `title`, `name`, `referenceNumber`, `spdId`, dozens more) instead hits a
  genuine `Npgsql.PostgresException: 42703 column ... does not exist` —
  meaning those names pass validation but the underlying view simply
  doesn't expose a column by that name. No combination across ~40 tested
  field names ever returned an actual tender record. This reproduces
  identically for `get-archived-public-packages` too (same exception,
  different line number). This is a genuine upstream bug, not an
  access-control wall — it affects every caller of this endpoint, not
  just automated ones.

**This actor therefore does not use that endpoint.** Instead it uses the
CMS "Publication Plan Lots" register (`cms-v2/api/publication/get-
publication-lots` for list/latest, `cms-v2/api/publication-lots/get-
publication-lot/{id}` for detail) — a *different*, fully-functional public
API on the same platform, confirmed live and current (the newest record
observed during this recon was timestamped the same day the actor was
built). It holds ~29,840+ procurement lot records spanning federal
ministries, regional universities, and other public bodies — reference
numbers, procurement category/method, organization, fiscal year, status,
and (in `detail` mode) full item-level quantities, estimated unit
price/currency, UNSPSC-style commodity classification, technical
specifications, and delivery milestones with due dates. This is
procurement **plan/lot** data (what an agency is/was procuring) rather
than a live bid-countdown feed, but it is genuine, current, official
Ethiopian government procurement data reachable with zero authentication
— arguably richer than a simple open-tenders list, since it already links
each lot to its parent annual plan, organization, and fiscal year.

## Pagination / sorting quirk

`get-publication-lots` requires `Count=false` **and** a non-empty
`OrderBy` to return items (the same "always needs OrderBy" requirement
seen on the broken tendering endpoint above) — but on this endpoint,
`OrderBy[0].field=timestamp` (direction `1` = descending, confirmed live:
newest record first) works reliably, so this is the only field this actor
ever sorts by. `Skip`/`Top` (50 rows/page) walk the rest of the
pagination.

## Ethiopian fiscal year quirk

Dates run on the Ethiopian calendar convention used by this platform:
fiscal years span **July 8 – July 7** (not January–December), and the
current one at build time is `ET-FY-2019` (Gregorian 2026-07-08 to
2027-07-07) — the "2019" is *not* a typo or stale data; the Ethiopian
calendar runs roughly 7-8 years behind Gregorian. `fiscalYearId` values
are internal GUIDs (from `cms-v2/api/publication-plans/get-budget-years`,
not exposed as a mode by this actor but usable as the optional
`fiscalYearId` input filter).

## Diff cadence

Quarterly smoke test recommended, plus a periodic retry of
`get-public-packages` with `Count=false` — the upstream bug documented
above may get fixed in a future deployment, at which point that endpoint
would be a strictly better "currently open for bidding" data source to
add as a fourth mode.
