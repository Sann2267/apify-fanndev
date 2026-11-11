# Crawling Method — Trinidad and Tobago Government Tenders Scraper (ProcureTT)

**Last verified:** 2026-08-27

## What ProcureTT is

Trinidad and Tobago's official public-procurement notice board is
**ProcureTT** (`procurett.oprtt.org`), run by the **Office of Procurement
Regulation** (OPR, `oprtt.org`) under the Public Procurement and Disposal of
Public Property Act, 2015. It is a WordPress site built on the
**GravityView** plugin (Gravity Forms submissions from public bodies,
rendered by GravityView as searchable/sortable public tables) — a
completely different vendor from the "European Dynamics/ePPS" e-GP platform
found on Ghana, Zambia, and Jamaica's tender portals in the same research
round, and from any Ultimate Member/business-registry style gate.

A separate legacy channel exists too — individual ministries (Ministry of
Finance, Ministry of Works and Transport, etc.) still post ad-hoc tender
PDFs on their own sites, and the Tobago House of Assembly runs its own
Procurement Control Office (`pco.tha.gov.tt`) plus a UDeCOTT e-tender login
portal (`udecott.etenderworld.tt`) — but ProcureTT is the OPR's own
**centralised, statutory** notice board explicitly named as such by OPR
("a centralised repository for Public Bodies... to post notices"), and is
what this actor scrapes.

## robots.txt: clean, no blanket block, no Claude/anthropic mention

```
User-agent: *
Disallow: /wp-content/uploads/wpo/wpo-plugins-tables-list.json

# START YOAST BLOCK
User-agent: *
Disallow:
Sitemap: https://procurett.oprtt.org/sitemap_index.xml
# END YOAST BLOCK
```

Standard WordPress + Yoast SEO robots.txt: one disallowed static cache
manifest, then an explicit blanket-allow (`Disallow:` with no path) from the
Yoast block. Every `User-agent:` line was checked individually — no
`Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` group anywhere, no natural-language prohibition comment.

`oprtt.org` (the parent OPR site — policy pages, not the notice board) was
also checked and is likewise clean; not used by this actor regardless.

## No login wall anywhere — the strongest signal of this recon

Every one of the five listing pages, and every per-entry detail page for the
three notice types that have one, returned **full content to a plain,
cookie-less `curl_cffi` request** — confirmed across `/tenders/`,
`/awards/`, `/annual-schedule-of-planned-procurement-activities/`,
`/pre-qualification-notices/`, `/disposals/`, and their `{path}entry/<id>/`
detail permalinks, plus the underlying
`/wp-json/gravityview/v1/view/<viewId>/entry/<id>` REST endpoint the
listing's fancybox links point at (also 200, also no nonce actually
enforced despite a `_wpnonce` query param being present in the markup).

This is notably different from the ePPS platforms researched in the same
round (Ghana/Zambia/Jamaica), where the single-tender "full call-for-tenders"
detail page is gated behind a registered-bidder CAS login even though the
listing itself is public. ProcureTT has no such split — the task brief's
stop condition ("login wall required to even VIEW listings") simply does
not apply here at any level. A "Log In" link exists in the site header
(WordPress + Ultimate Member), but it's for public bodies submitting new
notices, not for browsing — never triggered on any GET request made during
recon.

## TLS profile: chrome124/safari17_0/edge101 fine; chrome131 blocked

```
chrome124   -> 200
chrome131   -> 403 (plain nginx page, no Cloudflare/Akamai/DataDome headers)
safari17_0  -> 200
edge101     -> 200
```

The chrome131 403 has none of the response-header fingerprints of a real
managed WAF (no `cf-ray`, no `server: cloudflare`, no JS challenge body) —
it reads as a blocklisted-TLS-fingerprint rule at the nginx/proxy layer, not
a bot-detection product. This matches the portfolio-wide note that
`chrome131` is widely blocklisted in 2026 across unrelated targets. This
actor defaults to `chrome124`.

## Five notice types, all GravityView table views

| Notice type | Path | View ID | Rows at recon | Page size (from "Displaying" banner) | Has detail page? |
|---|---|---|---|---|---|
| Tenders | `/tenders/` | 330 | ~400 | 50 | Yes |
| Awards | `/awards/` | 871 | ~290 | 25 | No |
| ASPPA | `/annual-schedule-of-planned-procurement-activities/` | 363 | ~150 | 50 | No |
| Pre-qualification notices | `/pre-qualification-notices/` | 268 | ~37, one page (no pagination widget) | n/a | Yes |
| Disposals | `/disposals/` | 350 | ~10, one page | 10 | Yes |

View ids are documented in `constants.py` for traceability but not needed to
build requests — GravityView routes purely by URL path.

## Pagination: plain stateless `?pagenum=N`

Confirmed: `GET /tenders/?pagenum=2` returns page 2 standalone, with no
session/cookie carried from page 1 and no per-run table-instance id to
discover first (unlike the ePPS platforms' `d-<digits>` prefix). Confirmed
combinable with `sort[...]` on the same request
(`?sort[10]=desc&pagenum=2` returned page 2 of the descending-sorted list,
`Displaying 51 - 100 of 402`). This makes concurrent multi-page fetching in
`main.py` safe.

Page size is **not hardcoded** — `extractor.extract_pagination` reads it off
each response's own "Displaying `X - Y` of `Z`" banner (`page_size = Y - X +
1`) since it differs per view (50/25/10 above). When the banner is entirely
absent — observed on `/pre-qualification-notices/`, whose view has no
pagination widget configured — the rows already returned on the single
request ARE the complete register; `main.py` does not attempt a page 2 in
that case.

## Sorting: `?sort[<fieldId>]=asc|desc` — direct, not a toggle

Confirmed empirically by requesting both directions and reading the
resulting dates back: `sort[10]=asc` returned oldest-first
(`11/09/2025, 22/09/2025, ...`), `sort[10]=desc` returned newest-first
(`22/10/2026, 22/10/2026, 20/10/2026, ...`) — a direct, literal mapping,
unlike GOJEP's reversed `o=1`/`o=2` convention found in the same research
round. Field ids are internal Gravity Forms field ids scraped from each
view's own column-header sort links (`href="...sort%5B10%5D=asc..."
aria-label="Sort by Submission Deadline Date"`) and pinned in
`constants.py` per notice type — this platform has no self-discovery
mechanism for them (no embedded id to extract fresh each run the way GOJEP's
`d-<digits>` works), so a future OPR view redesign would need a recon
refresh to update these ids.

## Row parsing: by `data-label`, not fixed column index

Every listing `<td>` carries a `data-label="<Column Name>"` attribute
(GravityView's own responsive/mobile CSS hook) — `extractor.parse_listing_page`
builds each row as `{label: value}` from that attribute rather than
assuming a fixed column order or count. This is more resilient to a column
being reordered or a new one inserted than pure positional parsing (used on
the ePPS-platform actors, which lack per-cell labels) — but a *missing*
expected column still raises `UnexpectedShape` (checked via a per-notice-type
minimum label set in `NOTICE_TYPES[...]["expected_labels"]`), so a genuine
upstream field removal fails loud rather than silently shipping partial
records.

Three cell shapes needed special handling (`extractor._cell_value`):
1. **Bulleted "Lines of Business" / "Disposal Categories" lists**
   (`<ul class="bulleted">`) → parsed into a JSON array of strings, not
   concatenated into one blob.
2. **Nested Gravity Forms "list field" table** (`<table class="gfield_list">`,
   only seen on tender detail pages' "Lines of Business (Level 4)" —
   precise UNSPSC code/name pairs) → parsed into an array of `{Code, Name}`
   objects using the nested table's own `<thead>` labels.
3. **Document download links** (`<a href>` containing `gf-download` — a
   `index.php?gf-download=...` proxy URL — or `gk-download` — a direct
   tokenized path used on detail pages) → returned as `{"text": ..., "url":
   ...}` rather than flattening to just the link text ("download"), since
   the URL is the actually useful payload.

## Detail pages: per-entry, no fixed link column

Confirmed for three notice types (tenders, pre-qualification, disposals):
each listing row links to a richer detail page at the pretty permalink
`{path}entry/<id>/`. **The column carrying that link is not consistent
across notice types** — it's the "Tender Reference No." cell for tenders,
but the "Public Body" cell for pre-qualification notices — so
`extractor._row_entry_id` searches every `<a href>` in the whole `<tr>` for
an `/entry/(\d+)` pattern rather than assuming a fixed column, matching
whichever `href="https://procurett.oprtt.org/wp-json/gravityview/v1/view/
<viewId>/entry/<id>?_wpnonce=..."` fancybox trigger is present.

Detail pages themselves are parsed generically too
(`extractor.parse_detail_page`): a `<table class="gv-table-view-content">`
with `<tr><th>Label</th><td>Value</td></tr>` rows (a different markup shape
from the listing table's `data-label` `<td>`s, but the same `_cell_value`
cell-shape handling applies). Confirmed additive over the listing row for
tenders — every listing field reappears (occasionally under a slightly
different label, e.g. "Notice Document" instead of "Tender Notice
Document") plus four new ones: "Notice Type", "Date of Issuance",
"Lines of Business (Level 4)", "Submission Deadline Time".

Awards and ASPPA were confirmed to have **no** detail page at all — zero
`/entry/<id>/` or REST entry links found anywhere in either listing's HTML
across multiple samples — so `fetchDetail` is a no-op (logged, not an
error) for those two notice types.

## Known limits

- **Awards descriptions can be `...`-truncated with no way to recover the
  full text** — confirmed on live data (2 of ~290 rows at recon time carried
  a `&hellip;` truncation marker). Genuine upstream limitation of the
  `/awards/` view (no detail page exists to link to), not a parsing gap.
- **`Award Date` renders as ISO `YYYY-MM-DD`, every other date field renders
  `DD/MM/YYYY`** — confirmed by direct inspection of live award records
  (`"Award Date": "2026-08-14"` alongside `"Posted Date": "18/08/2026"` on
  other notice types). Documented prominently in the README so downstream
  consumers don't apply one date-parsing rule to every field.
- **No full-text/keyword search reverse-engineered** — GravityView renders a
  `?gv_search=` box client-side, but its query contract (which fields it
  matches, URL-encoding quirks) was not probed for stability; this actor
  exposes `sortBy`/`sortOrder` and leaves keyword filtering to the consumer
  post-fetch, consistent with the same choice made on the ePPS-platform
  actors in this research round (which likewise skip a CAPTCHA-gated
  advanced-search form).
- **Sort-field ids are pinned, not self-discovered** — see the Sorting
  section above. A future ProcureTT view redesign changing these internal
  Gravity Forms field ids would silently make `sortBy` a no-op (the request
  would still succeed, just ignore the sort) rather than erroring — worth a
  periodic smoke-test check that sorted output actually changes order.

## Diff cadence

Quarterly smoke test recommended. ProcureTT is a fairly young platform (view
IDs and Yoast SEO v28.3 suggest an active, recently-built WordPress site) —
more likely to receive incremental plugin/theme updates than a legacy
government portal, so the `expected_labels` shape-change guard and the
runtime `extract_pagination` page-size detection are both deliberately
defensive against a future markup shuffle.
