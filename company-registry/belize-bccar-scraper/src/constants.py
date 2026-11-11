"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): BCCAR -- the Belize Companies and Corporate
Affairs Registry -- is Belize's official company/business registry. Its
public marketing site (`bccar.bz`, WordPress) links to the transactional
system, the "Online Business Registry System" (OBRS), a separate app at
`obrs.bccar.bz`. Registration/incorporation/e-filing requires an account
(Social Security ID + email), but **the business/company search itself is a
genuinely public, unauthenticated tool** -- no login, no CAPTCHA, no payment.

`robots.txt`: `bccar.bz/robots.txt` is a stock WordPress block
(`Disallow: /wp-admin/`, `Allow: /wp-admin/admin-ajax.php`, a WP Defender
honeypot path, and an explicit Yoast `Disallow:` -- i.e. an *empty* disallow,
meaning "allow everything") -- no Claude/AI-crawler mention anywhere, no
blanket `Disallow: /`. `obrs.bccar.bz/robots.txt` has no real robots.txt file
at all -- every path (including `/robots.txt`) is client-side/server-side
routed into the app itself, which for an unmatched path serves a JSON
fragment from whatever module currently owns that route (observed: the user-
management module's login-state JSON). No disallow rule exists for the API
host or path this actor uses.

A second, unrelated public search UI exists at `companysearch.bz/public_
search/` ("eData") -- its `robots.txt` is `Disallow: /` (blanket block for
all bots), so it is **not used by this actor** even though it looked
promising in initial search results. BCCAR's own `obrs.bccar.bz` search is
used instead, which has no such restriction.

## Finding the API: read the page's own inline script + JS bundle

`obrs.bccar.bz/bereg/searchbusinesspublic` is BCCAR's public "Search for a
Business Entity" page. It isn't a modern SPA framework (no React/Vue/Next) --
it's a proprietary server-rendered form framework (internal name "OSCS",
visible in an HTML comment `<!-- theme-oscs -->` and in a JS stack trace,
`Oscs.Shared.Json...`) that defines an inline `$Forms.SearchBusinessPublic`
object literal directly in the page's `<script>` tag. That object names the
list endpoint directly: `listUrl:"list/public/business.json"` (relative to
`/bereg/`, i.e. `https://obrs.bccar.bz/bereg/list/public/business.json`), and
its `filterGroup` names the four supported filter fields: `name`,
`reg_number`, `business_entity_type` (a select, options in `res/
resources.js`'s `BETYPE` array), and `cert_number`.

The framework's own AJAX wrapper (`jcall`, found in the also-shipped `js/
lib.js` bundle after `--compressed` decoding -- the raw bytes look binary
until gzip is decoded) shows exactly how a request must be built:

```js
var g = $("#csrf").children("input").val();  // NCSRF token, read from the
                                               // page's own hidden input
$.ajax({
    url: n, type: "POST", contentType: "application/json",
    data: $.toJSON(j),           // {PageSize, PageNumber, Sorting, ...filters}
    beforeSend: function(o){ if (g) o.setRequestHeader("NCSRF", g); }
});
```

So the real request is:

```
POST https://obrs.bccar.bz/bereg/list/public/business.json
Content-Type: application/json
NCSRF: <token from the search page's hidden #csrf input>
Cookie: <cookies set by the GET to /bereg/searchbusinesspublic>

{"PageSize": 100, "PageNumber": 1, "name": "bank"}
```

`reg_number`, `cert_number`, and `business_entity_type` (values like
`"BET-CM"`, `"BET-BN"`, `"BET-LLC"`, `"BET-FND"`, `"BET-FM"`) work as
alternate/additional filter keys in the same JSON body. Confirmed:
**`name` does NOT also match on `reg_number` digits** (unlike Uganda's
single-field fuzzy search) -- they are genuinely separate filters, so this
actor exposes them as separate input fields rather than one combined query.

## The gate: a lightweight CSRF header/cookie pair, no TLS/WAF gate at all

Unlike every other registry actor built in this project so far, **plain
default-TLS `curl` with no impersonation, no special headers, and no proxy
gets `HTTP 200` with real JSON on the very first try** -- there is no
Cloudflare/Akamai/DataDome/JA3 gate whatsoever (plain `nginx`, no `cf-ray` or
challenge markers). The only requirement is the app-level NCSRF token: a
request to the list endpoint missing the `NCSRF` header (or carrying a token
that doesn't match the session cookie) gets `HTTP 303 See Other` redirected
to `.../beapr/` (the app's default landing route for an unrecognized/failed
AJAX call) instead of a clean 4xx -- so this actor treats "no `Result` key /
non-200 / redirect" as "session needs a fresh bootstrap", not a hard failure.
The token is reusable across many calls within the same session (confirmed:
the same token worked for 5+ sequential calls covering different filters and
pages) -- it is not single-use, but its TTL wasn't pushed to the limit during
recon, so this actor re-bootstraps a fresh session per query rather than
sharing one token across an entire multi-query run, to stay safely inside
whatever TTL exists.

## Response shape: columnar, not one-object-per-record

```json
{
  "Map": ["reg_number", "name", "foreign_name", "business_entity_type_str",
           "business_entity_subtype", "state", "reg_address", "reg_date"],
  "Records": [["000013082", "BELIZE BANK INTERNATIONAL LIMITED", "",
                "Company", "Private Company", "Active",
                "Belize, Belize, Belize City, ...", "2005-07-27T00:00:00...+00:00"], ...],
  "Result": "OK",
  "TotalRecordCount": 9481
}
```

Each row in `Records` is positional, matching `Map`'s column order --
`build_record` zips them into a normal `{field: value}` dict per entity.
`TotalRecordCount` was cross-checked against multiple pages of the same
query (`"LIMITED"` -> 9481, stable and consistent across `PageNumber=1,2`)
and against a single-record exact `reg_number` lookup (`TotalRecordCount:
1`) -- **unlike Uganda's URSB, this pagination metadata is trustworthy** and
is used directly as this actor's stop condition, with a short-page fallback
as a second check.

## Fields available for free vs. gated

The public search returns: registration number, registered name, foreign-
character name (for non-Latin-script names, usually empty), entity type
(`Company` / `Business Name` / `LLP` / `LLC` / `Foundation`), entity sub-type
(e.g. `Private Company`, `Individual`, `Corporation`, `Limited Liability
Partnership`), current status (`Active`, `Struck off`, `Dissolved`, `Pending
Strike off`, ...), registered address, and registration date. **There is no
separate "detail" endpoint** -- no directors/shareholders/officers/document
list is exposed publicly anywhere in this flow (the page's own banner says
so explicitly: full historical records issued before 28 Nov 2022, and
presumably deeper company documents/filings, require contacting BCCAR's
office directly or purchasing a certified Full Search Report by email, which
is out of scope -- no login/payment automation). This actor's single "search"
mode already returns BCCAR's complete free/public record shape; searching by
an exact `reg_number` simply returns that same shape for one entity, so no
separate detail call is needed or possible.

## Sample queries tested

- **`bank`** (name filter, `PageSize=20`) -- 30+ matches: real banks
  (Belize Bank International Limited, The Belize Bank Limited, Atlantic
  Bank Limited, Heritage Bank Limited) alongside unrelated substring
  matches (Lords Bank Supermarket, Banana Bank Ranch Limited).
- **`000013082`** (exact `reg_number`) -- single match, `TotalRecordCount: 1`.
- **`LIMITED`** (broad name filter) -- `TotalRecordCount: 9481`, confirmed
  distinct, correctly-ordered rows across `PageNumber=1` and `PageNumber=2`.
- **`BET-FM`** (`business_entity_type` filter alone, no name) -- 79 LLPs,
  all rows confirmed `business_entity_type_str: "LLP"`.
- **`zzzznonexistententityxyz123`** (name filter) -- `TotalRecordCount: 0`,
  empty `Records`, clean `Result: "OK"` (no error thrown on zero matches).

## Known limits

- No detail/officer/document endpoint is exposed publicly -- this is a name/
  number/type search over the same public record shape BCCAR's own search
  page shows, nothing more.
- `foreign_name` is empty/null on nearly every record sampled.
- Records issued via a paper certificate before 28 Nov 2022 may not appear
  under `cert_number` lookups (per BCCAR's own on-page notice) -- this is a
  genuine registry data-migration boundary, not a scraping gap.
"""

BASE_URL = "https://obrs.bccar.bz"
BOOTSTRAP_PATH = "/bereg/searchbusinesspublic"
SEARCH_PATH = "/bereg/list/public/business.json"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}{BOOTSTRAP_PATH}",
    "X-Requested-With": "XMLHttpRequest",
}

# BETYPE select options from res/resources.js -- exposed as an optional
# entityType filter in this actor's input.
ENTITY_TYPES = {
    "BET-BN": "Business Name",
    "BET-CM": "Company",
    "BET-FND": "Foundation",
    "BET-LLC": "LLC",
    "BET-FM": "LLP",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Per-page size sent to the API. 100 was confirmed to work cleanly; kept
# well under any observed limit (no hard cap was found during recon, but
# 100 matches this project's convention for similar registry APIs).
PAGE_LIMIT = 100

# Safety cap on page depth per query -- deep pagination behavior beyond a
# few hundred rows wasn't stress-tested during recon, so this stays
# conservative. TotalRecordCount (see constants docstring) is trustworthy,
# so real over-fetching is avoided regardless.
MAX_PAGES_PER_QUERY = 50
