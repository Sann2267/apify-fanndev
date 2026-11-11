"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Saint Vincent and the Grenadines' company/
business-name register is run by **CIPO** -- the Commerce and Intellectual
Property Office, under the Attorney General's Chambers (office address:
First Floor, Brewster's Building, McCoy Street, Kingstown; `office.cipo@
mail.gov.vc`). CIPO's own marketing site, `cipo.gov.vc`, is a Joomla CMS
(the classic pattern seen across this project's small-country registries).

## A fraudulent decoy site found during recon -- NOT used, NOT trusted

A web search surfaced `saintvincentregistry.com`, styled almost identically
to an official government portal ("Government of Saint Vincent and the
Grenadines", CIPO's real Kingstown address and phone numbers in its
footer, Cloudflare-fronted, `.com` not `.gov.vc`). Inspecting its
`script.js` proved it is **a scam/fraud-verification decoy, not a real
registry**: every "search" is client-side-only against a hardcoded list of
fabricated license/registration keys tied to canned fake results (e.g. a
non-existent "European Financial Authority (EFA)" license, a fake ESG
certificate), and any *other* input triggers a fallback branch that
generates **entirely random fake company data** (random company name,
random director name, random capital amount, random incorporation date)
and presents it as a genuine verified registry hit. The result page also
disables copy/view-source (blocks Ctrl+C/Ctrl+U/Ctrl+S/Ctrl+P/F12) --
consistent with a site designed to convince a victim a fabricated
entity/license is real, not with a real public register. Its Cloudflare-
managed `robots.txt` also explicitly names `ClaudeBot: Disallow: /` (among
several other AI crawlers), which would have been a hard stop on its own
even if the content had been genuine. This actor never sends a single
request to `saintvincentregistry.com` -- it is documented here only so a
future maintainer doesn't waste time on the same false lead.

## Finding the real backend

CIPO's own Joomla site links out to two other live systems:
- `https://ocrs.gov.vc/` -- a **CaseFlow Systems Ltd.** "WebAsm" portal
  (`v.8.1.1.0`), the same vendor family as the old, login-walled
  `registry.cipo.gov.dm` ASP.NET WebForms portal ruled out during the
  Dominica actor's recon -- but a newer generation. Its landing page is a
  bare shell (`App.Settings.Page="Workplace"`, a `Login` link, no visible
  public-search route) -- not pursued further as the primary target once
  the Angular SPA below was confirmed to expose a genuinely unauthenticated
  search.
- `https://ecipo.gov.vc/#/ep/clientcontrol/search` -- an Angular SPA
  titled "e-Services" (meta description "CIPO E-services"), linked
  directly from `cipo.gov.vc`'s "One Stop Shop for Business Registration"
  page. This is the SAME multi-tenant "DotGovServer" e-services platform
  already confirmed for `antiguabarbuda-abipco-scraper`
  (`eservicesapi.abipco.gov.ag`) -- same Angular bundle structure, same
  `NameSearchPage/search` component, same `islandId`-as-tenant-GUID
  pattern, just a different runtime `apiUrl` and GUID.

The SPA's runtime config (`https://ecipo.gov.vc/assets/appsettings.json`,
fetched by an Angular `APP_INITIALIZER`, NOT the build-time bundle
default) gives the real, live API host:

    {"apiUrl": "https://ecipo.gov.vc/api/", "signUrl": "https://ocrs.gov.vc/pki", ...}

(The bundle's own build-time fallback default, embedded in `main.<hash>.js`,
is `"https://www.cipo.gov.vc/api/"` -- a stale/wrong value from the shared
codebase template, exactly analogous to the Saint Lucia config leak noted in
Antigua & Barbuda's recon. Not used -- the runtime `appsettings.json` value
is authoritative and was the one confirmed live.)

Reverse-engineered directly from the shipped Angular bundle (lazy chunk
`8.<hash>.js`, found by fetching every chunk listed in `runtime.<hash>.js`'s
webpack chunk map and grepping for `NameSearch`), the entire "Search"
feature (component `app-search`, template "Entity search by Name or
Number") is exactly ONE API call:

    GET https://ecipo.gov.vc/api/NameSearchPage/search?query=<text>&app=11000000-0000-0000-0000-000000000011

`app` is a fixed GUID hardcoded in the component as `this.islandId` --
Saint Vincent's tenant id on this shared Caribbean platform (Antigua's is
`70000000-0000-0000-0000-000000000007`). Not a secret or per-session
token -- a static, public, build-time constant baked into the publicly
served JS bundle.

No cookies, no session, no auth header, no CAPTCHA -- confirmed with
one-shot stateless requests. `ecipo.gov.vc/robots.txt` is a plain
allow-all (`User-agent: * ` with no `Disallow`), unlike the decoy site
above, and unlike nothing at all on `ocrs.gov.vc` (a generic IIS error
page for a missing `robots.txt`, i.e. absent, not a block).

### Response shape

A bare JSON array -- max 50 items, server-capped (confirmed with
single-letter queries "a"/"e"/"i" and common words "company"/"ltd", all
returning exactly 50 rows) -- each item shaped like:

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

Confirmed against real, current data: search by name (`"bank"`, `"trust"`,
`"international"`) and by registration number (`"109/2003"`) both work
through the same `query` parameter. Unlike Antigua's deployment, this
tenant's `CaricomStatus` values observed so far are status-like
("Active") rather than a country-domestic/foreign label -- passed through
verbatim either way, per this project's raw-passthrough convention; not
fabricated or normalized.

A genuinely non-matching query returns a clean empty array `[]` (HTTP 200).

## Known upstream bugs (real bugs, not a block -- guarded client-side)

- A **blank/whitespace-only query** returns HTTP 500
  (`System.Data.SqlClient.SqlException`, `"DGS Error. Please contact your
  administrator."`).
- A literal **apostrophe (`'`)** anywhere in the query returns HTTP 500
  (`System.AccessViolationException`, same "DGS Error" message) -- looks
  like unescaped dynamic SQL on the backend. This is a real limitation:
  legitimate company names containing an apostrophe (e.g. "O'Brien") cannot
  be searched by that exact substring through this endpoint. Rejected
  client-side rather than let every such query 500.
- A literal **`--` (double hyphen, a SQL line-comment sequence)** anywhere
  in the query triggers the same `AccessViolationException`/500. Also
  rejected client-side.
- Omitting the **`app`** parameter entirely returns HTTP 404. Always sent.
- A single `,` (comma) or `=` (equals) in the query does NOT error --
  confirmed harmless (`"bank,trust"` -> `[]`, `"a=b"` -> `[]`), unlike the
  OCRS/`loadInfoProc` platform used by Dominica/Saint Lucia where those
  characters silently truncate or 500 the query. Not restricted here.

## What's NOT public / not used

There is no separate "detail" endpoint for an individual `EntityID`
anywhere in the shipped SPA code (`EntityID` never appears outside the
search-result JSON itself) -- the search result row IS the full public
record this facility exposes. No directors/shareholders/filing-history
data is available through this unauthenticated path.

## No WAF observed

`curl_cffi` impersonating `chrome124`, `chrome131`, `safari17_0`, and
`edge101` all returned byte-identical `200` JSON responses from the same
IP within the same recon session.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://ecipo.gov.vc"
SEARCH_URL = f"{BASE_URL}/api/NameSearchPage/search"

# Fixed, public, build-time tenant GUID for Saint Vincent and the Grenadines
# on this shared multi-country "DotGovServer" e-services platform -- see
# constants.py module docstring for how this was found and confirmed
# not-secret (same platform/pattern as antiguabarbuda-abipco-scraper).
ISLAND_ID = "11000000-0000-0000-0000-000000000011"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Confirmed empirically: the server always returns at most this many rows
# regardless of how broad the query is (tested with single-letter queries
# and common whole words).
SERVER_RESULT_CAP = 50

# Characters confirmed to trigger an upstream HTTP 500 ("DGS Error") rather
# than a normal empty/matched result -- rejected client-side. See
# constants.py module docstring.
_INVALID_QUERY_SUBSTRINGS = ("'", "--")

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
