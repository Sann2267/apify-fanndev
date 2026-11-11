# Crawling Method — Belize BCCAR

**Last verified:** 2026-08-27

BCCAR (Belize Companies and Corporate Affairs Registry, `bccar.bz`) is
Belize's official company/business registry. The public marketing site
(`bccar.bz`) is WordPress; the transactional registry -- branded "Online
Business Registry System" (OBRS) -- is a separate app at `obrs.bccar.bz`.
Registration, incorporation, and e-filing require an account (a valid Social
Security ID + email), but **the business/company search itself is fully
public and unauthenticated** -- no login, no CAPTCHA, no payment.

A second, unrelated public search UI turned up in initial web search results
-- `companysearch.bz/public_search/` ("eData") -- but its `robots.txt` is a
blanket `Disallow: /`, so it was **not used**. BCCAR's own `obrs.bccar.bz`
search has no such restriction and is what this actor uses instead.

## Robots.txt

`bccar.bz/robots.txt`:
```
User-agent: *
Disallow: /f56836b63e8e61ee     (WP Defender honeypot path)
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

User-agent: *
Disallow:                        (Yoast block -- explicitly empty, i.e. allow all)

Sitemap: https://bccar.bz/sitemap_index.xml
```
Stock WordPress block. No Claude/AI-crawler mention anywhere, no blanket
`Disallow: /`, no natural-language AI/data-mining prohibition in the file's
comments.

`obrs.bccar.bz/robots.txt` has **no real file at all** -- the app's own
router catches the unmatched `/robots.txt` path and returns a JSON fragment
from whichever module currently owns routing (observed: the user-management
module's login-state JSON, e.g. `{"ModuleNameHumanReadable":"User
management", ...}`). No disallow rule exists for the host or path this actor
touches.

`companysearch.bz/robots.txt` is `Disallow: /` -- confirmed, and this domain
is not used by this actor as a result.

## Finding the API: the page's own inline script names it directly

`obrs.bccar.bz/bereg/searchbusinesspublic` ("Search for a Business Entity")
is not a modern SPA framework (no React/Vue/Next bundle to reverse-engineer)
-- it's a proprietary server-rendered form framework (internal name "OSCS",
visible in an HTML comment `<!-- theme-oscs -->` and in a server error's
stack trace, `Oscs.Shared.Json...`). The page defines its search form
directly in an inline `<script>` tag:

```js
$Forms.SearchBusinessPublic = $t.frm.Search("SearchBusinessPublic", "Search for a Business Entity").extend({
  filterGroup: function(){ return $t.grp.group("filterCtl", [
    ...,
    $t.grp.horz("g1", null, [
      $t.grp.group("c1", [{id:"name", type:"text", ...}, {id:"reg_number", type:"text", ...}]),
      $t.grp.group("c2", [$t.fld.select("business_entity_type", ..., $res.BETYPE), {id:"cert_number", type:"text", ...}])
    ])
  ])},
  listCtrl: function(){ return { type:"jtable", table:{ actions:{ listUrl:"list/public/business.json" }, columns:{...} } } }
});
```

That names the endpoint directly -- `list/public/business.json`, relative to
`/bereg/` -- and the four filter fields: `name`, `reg_number`,
`business_entity_type` (options from `res/resources.js`'s `BETYPE` array),
and `cert_number`.

The framework's own AJAX call builder (`jcall`, in `js/lib.js` -- the raw
bytes look binary until requested with `curl --compressed`, since the server
gzips it) shows exactly how a valid request is built:

```js
jcall: function(n, j, m, k) {
    var g = $("#csrf").children("input").val();   // NCSRF token from the page's own hidden input
    ...
    $.ajax({
        url: n, type: "POST", contentType: "application/json",
        data: $.toJSON(j),
        beforeSend: function(o){ if (g) o.setRequestHeader("NCSRF", g); }
    });
}
```

So the real request:

```
GET  https://obrs.bccar.bz/bereg/searchbusinesspublic          (bootstrap: sets cookies, page has <input name="NCSRF" value="...">)
POST https://obrs.bccar.bz/bereg/list/public/business.json
     Content-Type: application/json
     NCSRF: <token from the hidden #csrf input on the bootstrap page>
     Cookie: <cookies set by the bootstrap GET>
     Body: {"PageSize": 100, "PageNumber": 1, "name": "bank"}
```

Confirmed working with plain `curl` (no browser, no JS execution) once these
two steps are chained.

## The gate: a lightweight CSRF header/cookie pair — no TLS/WAF gate at all

Unlike every other registry actor built in this project so far, **plain
default-TLS `curl` (no impersonation, no special headers, no proxy) got
`HTTP 200` with real JSON on the very first try.** Response headers show
plain `nginx`, no Cloudflare/Akamai/DataDome/`cf-ray`/challenge markers of
any kind. There is no JA3/TLS-fingerprint gate to defeat here.

The only thing that has to be right is the app-level NCSRF token:

- **Missing/stale/mismatched `NCSRF` header** -> `HTTP 303 See Other`
  redirecting to `https://obrs.bccar.bz/beapr/` (the app's fallback route
  for an AJAX call it doesn't recognize as valid) -- not a clean 4xx. This
  actor's client treats "non-200, or a 200 body missing the expected
  `Result`/`Map` keys" as "session needs a fresh bootstrap" and retries once
  with a brand-new session before giving up.
- **Body sent as form-encoded instead of raw JSON** -> `HTTP 200` with a
  `.NET`-style deserialization error body (`System.Runtime.Serialization.
  SerializationException: Invalid JSON string`) -- confirms the endpoint
  requires `Content-Type: application/json` with a genuine JSON object body,
  not `application/x-www-form-urlencoded`.
- The same NCSRF token was confirmed reusable across 5+ sequential calls in
  one recon session (different filters, different pages) -- it is not
  single-use -- but its TTL wasn't pushed to the limit during recon. This
  actor re-bootstraps a fresh session per search job rather than sharing one
  token across an entire multi-query run, to stay safely inside whatever TTL
  exists (the extra GET is cheap and this endpoint has no rate-limit signal
  observed).

No CAPTCHA anywhere in this flow (the `RecaptchaSiteKey` seen in the
user-management module's JSON is used for account registration/login, not
for the public search).

## Response shape: columnar, not one-object-per-record

```json
{
  "Map": ["reg_number", "name", "foreign_name", "business_entity_type_str",
           "business_entity_subtype", "state", "reg_address", "reg_date"],
  "Records": [
    ["000013082", "BELIZE BANK INTERNATIONAL LIMITED", "", "Company",
     "Private Company", "Active",
     "Belize, Belize, Belize City, Suite 201, Second Floor, Belize Bank Centre, Coney Drive",
     "2005-07-27T00:00:00.0000000+00:00"]
  ],
  "Result": "OK",
  "TotalRecordCount": 9481
}
```

Each row in `Records` is positional, matching `Map`'s column order.
`src/client.py` zips them into a normal `{field: value}` dict per entity
before handing off to `src/extractor.py`.

**`TotalRecordCount` is trustworthy** -- cross-checked across pages of the
same broad query (`"LIMITED"` -> `9481`, stable and consistent across
`PageNumber=1,2,3`) and against exact single-record lookups (`reg_number`
lookup -> `TotalRecordCount: 1`). This is used directly as the pagination
stop condition, with a short-page fallback as a second check. (Unlike
`uganda-ursb-scraper`, where the equivalent metadata was observed to always
report `0` and had to be ignored entirely -- see that actor's own
`CRAWLING_METHOD.md` for the contrast.)

## Gotcha: `name` and `reg_number` are genuinely separate filters

Searching `name` with a registration number's digits (e.g. `name:
"000013082"`) returns zero matches -- confirmed reproducible. This is unlike
Uganda's URSB, where a single fuzzy `name` param matched both names and exact
registration numbers. Because of this, `src/main.py`'s `_build_job` routes a
plain string query to `reg_number` when it's all-digits and to `name`
otherwise, rather than sending everything through one field.

## Sample queries tested

- **`name: "bank"`** (`PageSize=20`) -- 31 total matches: real banks
  (Belize Bank International Limited, The Belize Bank Limited, Atlantic Bank
  Limited, Heritage Bank Limited, National Bank of Belize Limited) alongside
  unrelated substring matches (Lords Bank Supermarket, Banana Bank Ranch
  Limited) -- BCCAR's search is a plain substring match, not fuzzy.
- **`reg_number: "000013082"`** (exact) -- 1 match, `TotalRecordCount: 1`.
- **`name: "LIMITED"`** (broad, `max_results=250`) -- `TotalRecordCount:
  9481`; fetched 250 records across 3 pages with zero duplicate
  `reg_number`s across the page boundary, confirming pagination correctness.
- **`business_entity_type: "BET-FM"`** (LLP filter alone, no name) -- 79
  total, every returned row confirmed `business_entity_type_str: "LLP"`.
- **`name: "zzzznonexistententityxyz123"`** (garbage) -- `TotalRecordCount:
  0`, empty `Records`, clean `Result: "OK"` -- no error thrown on zero
  matches (unlike URSB, this endpoint did not fuzzy-match a garbage string
  to something unrelated).
- **Missing `NCSRF` header entirely** -- `HTTP 303` redirect to
  `.../beapr/`, confirmed the client's re-bootstrap-and-retry path handles
  this correctly.
- **Form-urlencoded body instead of JSON** -- `HTTP 200` with a
  deserialization error body, confirmed `Content-Type: application/json` +
  raw JSON body is required.

## Known limits

- No detail/officer/document endpoint is exposed publicly anywhere in this
  flow. The public search page's own on-page notice states registrations
  with certificates issued before 28 Nov 2022 may not be found via
  `cert_number` lookup, and deeper company documents/filings require
  contacting BCCAR's office directly or purchasing a Full Search Report by
  email/payment -- out of scope (no login/payment automation in this
  project). This actor's single search mode already returns BCCAR's full
  free/public record shape for every match; an exact `reg_number` search
  just returns that same shape for one entity, so there is no separate
  "detail" call to make.
- `foreign_name` is empty/null on nearly every record sampled.
- The search is a plain substring match (not fuzzy) as far as recon could
  tell -- unlike Uganda's URSB, a garbage query returned zero results rather
  than an unrelated near-match.

## Diff cadence

Quarterly smoke test recommended. This is a bespoke proprietary framework
("OSCS"), not a widely-used open-source stack, so there's no public changelog
to watch -- a redeploy could change the NCSRF handshake, the endpoint path,
or the response column set without notice.
