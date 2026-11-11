# Crawling Method — Botswana CIPA

**Last verified:** 2026-08-26/27

CIPA (Companies and Intellectual Property Authority, `cipa.co.bw`) is
Botswana's official company and IP registry. The public marketing site
(`www.cipa.co.bw`) is WordPress; its transactional "Online Business
Registration System" (OBRS) runs on **Verne by Foster Moore** (footer:
"Powered by Foster Moore"), a citizen-services platform used by a number of
small-country government registries. The Verne app lives at `/master/...`
(search) and `/companies/...` (entity profile), same origin as the WordPress
site.

## Robots.txt

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://www.cipa.co.bw/wp-sitemap.xml
```

Stock WordPress block. No Claude/AI-crawler mention anywhere, no disallow
for `/master/` or `/companies/` (the only two paths this actor touches
besides the root). One `User-agent: *` group total.

## WAF / anti-bot

**None observed.** Plain `nginx`, no Cloudflare/`cf-ray`/challenge markers,
no CAPTCHA, no rate-limit block, across ~25+ requests during recon
(including a deliberately-invented garbage query and rapid sequential
searches within one session). `curl_cffi` `chrome124` is used for
portfolio-wide consistency, not because a plain `requests` baseline was
observed to fail — that baseline wasn't separately re-tested since recon
started directly with `curl_cffi` per this project's default stack.

## The "Search the Register" flow (public, no login)

`GET https://www.cipa.co.bw/master/ui/start/CIPARegisterSearch` renders as a
guest (`Catalyst.usr.type == "guest"`) — **no login or account required**.
It's a Vue3 SPA ("Verne") talking to a stateful endpoint:
`POST /master/ui/<transactionId>`, body:
`{"returnRootHtmlOnChange": bool, "returnChangesOnly": bool, "commands": [...]}`.

**This is not a simple GET-with-query-param search** — it's a session/
transaction-based protocol closer to ASP.NET WebForms viewstate than a REST
API, which is exactly the pattern this project is usually wary of. It turned
out fully scriptable over plain HTTP anyway, no browser needed, because:

1. The transaction id and every interactive node's id are all embedded as
   plain, parseable text (JSON on `GET` pages, a compact custom format on
   `POST` responses — see below) — nothing is derived by executing JS.
2. The two command types needed (`view-node-set-attribute-value`,
   `view-node-button-click`) were found by reading the two vendor JS bundles
   that construct them (`catalyst.002.api.oo.js`, `catalystui.js`), not by
   guessing.
3. No CSRF/anti-automation token beyond the transaction id itself was
   encountered.

### Step-by-step

1. `GET /master/ui/start/CIPARegisterSearch` → redirects to
   `/master/ui/<transactionId>`. The response HTML embeds the entire initial
   view tree as a plain JS var — `var viewTree = {...};` — which is clean,
   directly `json.loads`-able JSON. From it, find the `NameOrNumber` field's
   node id and the `Search` button's node id (`extractor.find_by_attribute`
   / `find_button_by_label`).
2. `POST /master/ui/<transactionId>` with commands to set the field value
   and click the button (both in the same request works fine — tested).
3. Parse the delta response for `Name (REGISTRATIONNUMBER)`-labeled
   "hyperlink" buttons — one per matched entity.
4. For each match, `POST` a `view-node-button-click` on that button's node
   id → response is `{"redirect": "https://www.cipa.co.bw/companies/ui/
   start/entityView/<32-hex-id>?dom=Company"}`.
5. `GET` that `entityView` URL — **confirmed to load fine from a completely
   fresh session with zero cookies**, i.e. it's a real public permalink, not
   session-scoped. Its HTML embeds the same `var viewTree = {...}` pattern,
   this time describing the full company profile (directors, shareholders,
   addresses, beneficial owners — see below). No session affinity is needed
   between the search step and this step, so detail fetches can run
   concurrently across queries with fresh clients.

### The critical gotcha: `returnRootHtmlOnChange` / `returnChangesOnly`

The page's own inline config sets `Catalyst.returnRootHtmlOnChange = false;`
and (slightly later, in a separate `<script>` block) `Catalyst.delta =
true;`. **Every real interaction POST from the live site uses
`returnRootHtmlOnChange: false, returnChangesOnly: true`.**

Sending the opposite (`true` / `false` — which reads as "give me the more
complete response") still returns **HTTP 200 with a well-formed but silently
empty results box**, for every query tried, including guaranteed-to-match
common terms ("Bank", "Botswana", "First", the exact string "Debswana").
There is no error, no different status code, nothing in the response that
flags this as wrong — it just quietly never populates the results grid. This
cost the most recon time in this build and is not documented anywhere in the
shipped JS; it was only found by trying the delta-mode flags (matching the
page's own config) against a query with known real matches.

### A second false "no results" signal (also found the hard way)

The `searchResults`-nodetype node's `text.noResults` string ("Your search
returned no results") and the results repeater's `kv.ui-count` /
`ui-display-count` are **both present/zero in the SAME response that also
contains real, correct result rows** (confirmed: a response with 11 real
"Bank"-matching companies still carries `ui-display-count: 0` and the
`noResults` template string). Neither is a reliable "zero matches" signal.
The only reliable signal found: whether any `Name (REGNUM)`-labeled
hyperlink button actually exists in the parsed response
(`extractor.extract_search_results` raises `NoResultsFound` only when that
scan comes back empty).

### Wire format: not real XML

Delta (`POST`) responses look like XML (`<nodeId>...</nodeId>` nesting) but
are **not well-formed XML** — node-id tag names are 16-char lowercase hex
and can start with a digit, which XML forbids as an element name's first
character. `extractor.parse_delta_state` hand-parses it with regex instead
of an XML parser: each node's own wrapping tag is unique in the tree (IDs
aren't reused), so non-greedy `.*?` up to the matching closing tag is safe.
Text values in this format use HTML entity escaping (`&amp;`) and are
unescaped on parse.

`GET`-rendered pages (search start page, `entityView` detail page) instead
embed the SAME logical tree as a real `var viewTree = {...};` JS object
literal — clean JSON, no custom parsing needed.

## Data extraction — a domain-agnostic tree walker, not hardcoded fields

CIPA exposes no traditional JSON REST API — this node graph (`{node_id:
{children, nodetype, domain, attribute, attributeValue, ...}}`) *is*
upstream's own data model, for both wire formats once normalized.
`extractor.walk_record` is a single generic recursive flattener: it groups
`nodetype: record` descendants by their own `domain` string into lists
(so multiple directors/shareholders naturally become a list), and merges
`nodetype: attribute` values and pure-layout `box`/`button`/`text` nodes
into a flat dict. It does **not** hardcode "Director" or "Shareholder" as
special cases.

This mattered in practice: Debswana Diamond Company's shareholders are
`OtherShareholder` / `OtherEntity` records (a BVI holding company and the
Botswana government), a **completely different node shape** from the
`IndividualShareholder` / `IndividualName` records seen on every
individual-owned company tested. The generic walker captured both correctly
with zero special-casing, because it groups by whatever `domain` string
upstream actually used rather than a fixed field list.

## Sample entities tested

- **Bank** (11 matches: SBI, Baroda, India, Gaborone, and several
  "Bankxxx"-named companies) — mix of `registered` and `removed` status,
  `private` and `public` entity types.
- **Debswana** (1 match: Debswana Diamond Company, `BW00000466545`,
  registered 1969) — full board of directors, `OtherShareholder`-shaped
  corporate shareholders (Delibes Holdings Limited / VG, Government Of The
  Republic Of Botswana), share allocations, beneficial owners.
- **Gaborone** (19 matches) — broad substring name search.
- **`BW00000015806`** (exact registration number for "Bank Gaborone
  Limited") — confirms the same `NameOrNumber` field accepts registration
  numbers, not just names.
- A deliberately-invented garbage query (`zzzznonexistentxyz999`) — confirms
  the `NoResultsFound` path emits a clean `_error: "not_found"` record
  instead of a false match or a crash.

## Known limits

- No pagination is implemented beyond a single search response's result set
  (`maxResultsPerQuery`, capped at 200 — the largest page-size option
  observed in the repeater's own `ui-sizes` metadata). A query broader than
  that (e.g. a single common letter) may not return every match.
- Some entities have sparse data on file (e.g. an empty
  `RegisteredOfficeAddress.PhysicalAddress` object, or no `Director`/
  `Shareholder` group at all for an old/removed entity) — this reflects
  what CIPA itself has on record, not a scraping gap. `extract_entity_detail`
  only fails loud (`UnexpectedShape`) when the root record isn't a `Company`
  domain at all or is missing `CompanyNumber` entirely.
- The separate "Trademark & Patent Search" link on the homepage
  (`http://ipsearch.cipa.co.bw/wopublish-search/`) is **dead** — a plain
  Apache Tomcat 8.0.0-RC5 404 on that exact path (the bare host root is an
  unrelated default IIS placeholder page), confirmed on both `http://` and
  `https://` (the latter refuses the TCP connection outright on port 443).
  Out of scope for this actor; IP/trademark search was not pursued further
  since the linked feature is simply not currently deployed.
- `entityView` URLs are internal opaque 32-hex identifiers, not derivable
  from a registration number directly — they're only obtained by running
  the search-and-click flow, even for an exact-registration-number query.

## Diff cadence

Quarterly smoke test recommended (Verne/Foster Moore is a maintained
commercial platform; a version upgrade could change node ids' generation
scheme or the delta-mode flag behavior documented above).
