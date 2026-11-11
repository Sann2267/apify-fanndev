# Crawling Method — Saint Vincent and the Grenadines CIPO Business Registry

**Last verified:** 2026-08-27

Saint Vincent and the Grenadines' company/business-name register is run by
**CIPO** — the Commerce and Intellectual Property Office, under the
Attorney General's Chambers (First Floor, Brewster's Building, McCoy
Street, Kingstown; `office.cipo@mail.gov.vc`).

## A fraudulent decoy site found during recon — ruled out, not used

A web search for "St Vincent Grenadines company registry" turns up
`https://saintvincentregistry.com/` prominently, styled almost identically
to a real government portal: title "Government of Saint Vincent and the
Grenadines", CIPO's genuine Kingstown address and phone numbers in its
footer, "Commerce and Intellectual Property Office (CIPO)" copyright line,
fronted by Cloudflare.

Inspecting its `script.js` shows it is **not a real registry** — it is a
client-side-only fraud-verification decoy:

- A small, hardcoded list of "valid" license/registration keys (e.g.
  `EU-IF/2023-L0942-ASH`, `ESG-COMP/INT-901-2024`) map to canned fake
  results — a non-existent "European Financial Authority (EFA)" investment
  license, a fabricated "ESG Certified" audit, a fake "European Government
  Projects Registry" SPV registration.
- **Any other input** falls through to a branch that generates entirely
  **random** fake company data (random company name from a fixed list,
  random director name, random capital amount, random incorporation date
  in the past 10 years) and presents it as a genuine verified registry hit
  — i.e. it will "confirm" literally anything as a registered, active
  entity.
- The result page disables copy/view-source (blocks `Ctrl+C`, `Ctrl+U`,
  `Ctrl+S`, `Ctrl+P`, `F12`) — behavior consistent with a site built to
  convince a victim a fabricated registration/license is real, not with a
  genuine public register.
- Its Cloudflare-managed `robots.txt` explicitly lists `User-agent:
  ClaudeBot` / `Disallow: /` (alongside GPTBot, CCBot, Bytespider,
  Amazonbot, Google-Extended, and others) — which alone would have been a
  hard stop under this project's rules even if the content had been
  genuine.

This actor never sends a request to `saintvincentregistry.com`. Documented
here only so a future maintainer doesn't waste time on the same
plausible-looking false lead.

## Finding the real backend

CIPO's own site, `cipo.gov.vc` (Joomla CMS), links out to two live
systems from its "One Stop Shop for Business Registration" page:

1. `https://ocrs.gov.vc/` — a **CaseFlow Systems Ltd.** "WebAsm" portal
   (`v.8.1.1.0`, footer "2026 © Caseflow Systems LTD"). Same vendor family
   as the older, login-walled `registry.cipo.gov.dm` ASP.NET WebForms
   portal ruled out during this project's Dominica-registry recon, but a
   newer generation. Its landing shell (`App.Settings.Page="Workplace"`,
   a `Login` link, `App.User.IsAuthenticated=false`) exposes no visible
   public-search route on the bare shell HTML — not pursued further once
   the Angular SPA below was confirmed to expose a genuinely
   unauthenticated search with richer, more directly accessible data.
2. `https://ecipo.gov.vc/#/ep/clientcontrol/search` — an Angular SPA
   (`<title>e-Services`, meta description "CIPO E-services"). This turned
   out to be the **same multi-tenant "DotGovServer" e-services platform**
   already used by `antiguabarbuda-abipco-scraper`
   (`eservicesapi.abipco.gov.ag`) — confirmed by an identical Angular
   bundle structure, an identical `app-search` component, and an
   identical `NameSearchPage/search` API shape, just a different runtime
   `apiUrl` host and a different `islandId` tenant GUID.

### Robots.txt

- `https://ecipo.gov.vc/robots.txt` — `User-agent: *` with **no**
  `Disallow` at all (`# Allow all URLs`). No Claude/AI-crawler mention.
- `https://ocrs.gov.vc/robots.txt` — returns a generic IIS "Error Page"
  body (i.e. the file doesn't exist), not a block.
- `https://cipo.gov.vc/robots.txt` — plain HTTP 404 (Apache), i.e. absent.
- `https://saintvincentregistry.com/robots.txt` — the one host with an
  actual restriction: a Cloudflare-managed block explicitly naming
  `ClaudeBot: Disallow: /` — irrelevant here since this actor never
  touches that domain (see above).

### Runtime config discovery

The SPA's real API host isn't in the build-time bundle default — it's
fetched at startup from `https://ecipo.gov.vc/assets/appsettings.json`:

```json
{
  "apiUrl": "https://ecipo.gov.vc/api/",
  "signUrl": "https://ocrs.gov.vc/pki",
  "reCaptchaSiteKey": "6LdtL4MUAAAAAOIV_TjrtAZzHUILhmBOGMltOmcB"
}
```

(The bundle's own build-time fallback, embedded directly in
`main.<hash>.js`, is `"https://www.cipo.gov.vc/api/"` — a stale/wrong
value carried over from the shared codebase template, exactly analogous
to the Saint Lucia config leak documented in the Antigua & Barbuda actor's
recon. Not used — the live `appsettings.json` value above is what the
deployed app actually calls, and was confirmed to serve real data;
`signUrl` pointing back at `ocrs.gov.vc` confirms the two hosts are part
of the same deployment.)

### Reverse-engineering the search API

Found by fetching every lazy-loaded chunk file listed in
`runtime.<hash>.js`'s webpack chunk map and grepping for `NameSearch`
(chunk `8.<hash>.js`, ~3.8 MB). The entire "Search" feature — component
`app-search`, on-page title "Entity search by Name or Number", a single
text box and Search button — is exactly ONE API call:

```
GET https://ecipo.gov.vc/api/NameSearchPage/search?query=<text>&app=11000000-0000-0000-0000-000000000011
```

`app` is a **fixed GUID hardcoded in the Angular component** as
`this.islandId = "11000000-0000-0000-0000-000000000011"` — Saint
Vincent's tenant id on this shared Caribbean platform (Antigua's is
`70000000-0000-0000-0000-000000000007`). Not a secret or per-session
token: a static constant baked into the publicly served JS bundle, and
hardcoded the same way here.

No cookies, no session, no auth header, no CAPTCHA required — confirmed
with one-shot stateless requests, no shared cookie jar needed between
calls.

### Response shape

A bare JSON array — max 50 items, server-capped (confirmed: single-letter
queries `"a"`/`"e"`/`"i"` and common words `"company"`/`"ltd"` all
returned exactly 50 rows) — each item shaped like:

```json
{
  "EntityID": "7bce5394-212e-4c9d-807d-113a70401671",
  "EntityName": "ST. VINCENT & THE GRENADINES BANKER'S ASSOCIATION INC.",
  "EntityNumber": "109/2003",
  "DateOfIncorporation": "2003-12-01T00:00:00",
  "LoweredApplicationName": "stvincent",
  "StatusName": "Active",
  "TypeName": "Private Ordinary Company",
  "PrincipalOfficeAddress": "HUGHES & CUMMINGS,  EGMONT STREET,  KINGSTOWN, ST. GEORGE, SAINT VINCENT AND THE GRENADINES",
  "registry": "Commerce and Intellectual Property Office (CIPO)",
  "CaricomStatus": "Active",
  "StatusReason": null
}
```

Confirmed against real, current data: name search (`"bank"`, `"trust"`,
`"international"`, `"foreign"`) and registration-number search
(`"109/2003"`, which matches two unrelated entities sharing that
number/year combination) both work through the same `query` parameter.

Unlike Antigua's deployment (where `CaricomStatus` holds a
domestic/foreign country label), this tenant's `CaricomStatus` values
observed so far are status-like (`"Active"`) rather than a country
designation — passed through verbatim either way, per this project's
raw-passthrough convention; not normalized or fabricated to match
Antigua's shape.

A genuinely non-matching query returns a clean empty array `[]` (HTTP
200) — unambiguous, no special-casing required.

## Known upstream bugs (real bugs, not a block — guarded client-side)

- **Blank/whitespace-only `query` → HTTP 500**
  (`System.Data.SqlClient.SqlException`, `"DGS Error. Please contact your
  administrator."`).
- **A literal apostrophe (`'`) anywhere in the query → HTTP 500**
  (`System.AccessViolationException`, same "DGS Error" message) — looks
  like unescaped dynamic SQL server-side. Real limitation: a legitimate
  company name containing an apostrophe (e.g. `O'Brien`) cannot be
  searched by that literal substring through this endpoint.
- **A literal `--` (double hyphen, a SQL line-comment sequence) anywhere
  in the query → the same HTTP 500** `AccessViolationException`.
- **Omitting `app` → HTTP 404** ("No HTTP resource was found..."). Always
  sent by this actor.

All three are guarded against client-side in `src/extractor.py`
(`validate_query`) — rejected before the request is sent, surfaced as
`_error: "invalid_query"` with a diagnostic `_errorDetail`, rather than
letting every such query hit the upstream 500.

Confirmed harmless, NOT restricted: a literal `,` or `=` in the query
(`"bank,trust"` → `[]`, `"a=b"` → `[]`) — unlike the different
`loadInfoProc`-based OCRS platform used by this project's Dominica/Saint
Lucia actors, where those exact characters cause a silent truncation or a
500 respectively. Different platform, different bug surface — verified
independently rather than assumed.

## What's NOT public / not used

There is no separate "detail" endpoint for an individual `EntityID`
anywhere in the shipped SPA code (`EntityID` never appears outside the
search-result JSON itself, confirmed by grepping every downloaded chunk)
— the search result row IS the full public record this facility exposes.
No directors, shareholders, or filing-history data is available through
this unauthenticated path.

## No WAF observed

`curl_cffi` impersonating `chrome124`, `chrome131`, `safari17_0`, and
`edge101` all returned byte-identical `200` JSON responses from the same
IP within the same recon session. The shipped client uses `chrome124` for
portfolio-wide consistency, not because a bare baseline was observed to
fail.

## Sample entities tested

- `"bank"` → 50 matches (server cap), including `ST. VINCENT & THE
  GRENADINES BANKER'S ASSOCIATION INC.` (`109/2003`) and `BISHOPS BANK AND
  TRUST COMPANY LIMITED` (`24/1976`).
- `"109/2003"` (registration number) → 2 matches sharing that exact
  number/year (`ST. VINCENT & THE GRENADINES BANKER'S ASSOCIATION INC.`
  and `HADLEY'S AUTO SERVICES`), confirming number-lookup works through
  the same `query` parameter and that registration numbers are not
  globally unique keys on their own.
- `"zzzznonexistentxyz999"` (nonsense) → `[]`, confirms the clean
  `not_found` path.
- `""` (blank) → HTTP 500 from upstream, confirms the client's
  `invalid_query` guard is necessary and correctly triggered.
- `"o'brien"` (apostrophe) → rejected client-side before any request was
  sent, confirming the guard against the apostrophe-500 bug.

## Diff cadence

Quarterly smoke test recommended — this is a government e-services
platform actively shared across multiple Caribbean jurisdictions (see the
Antigua & Barbuda actor's own Saint Lucia config-leak artifact); a future
redesign could rotate the `islandId` GUID, close the currently-
unauthenticated `/NameSearchPage/search` path, or move the runtime
`apiUrl` config to a different discovery mechanism.
