# Crawling Method — Papua New Guinea NPC Tenders

**Last verified:** 2026-08-27

## Portal discovery

Papua New Guinea's central procurement authority used to be the **Central
Supply and Tenders Board (CSTB)**, but the National Procurement Act 2018
abolished it and replaced it with the **National Procurement Commission
(NPC)**, operational since 1 April 2019. NPC's own site, **`npc.gov.pg`**,
is the current official portal — it self-describes on-page as "the
information hub for Electronic Government Procurement (e-GP) initiatives".
No live CSTB site remains; every CSTB reference found online is historical
context, not a redirect or a still-active portal. A commercial domain,
`procurement.gov.pg`, is mentioned by some secondary sources but was not
needed — `npc.gov.pg` is what NPC itself operates and publishes to.

## Robots.txt

```
User-agent: *
Disallow: /wp-content/uploads/wc-logs/
Disallow: /wp-content/uploads/woocommerce_transient_files/
Disallow: /wp-content/uploads/woocommerce_uploads/
Disallow: /*?add-to-cart=
Disallow: /*?*add-to-cart=
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

# START YOAST BLOCK
User-agent: *
Disallow:
Sitemap: https://npc.gov.pg/sitemap_index.xml
# END YOAST BLOCK
```

Two `User-agent: *` groups (a WooCommerce block, and Yoast SEO's own empty
block) — checked every line in both, no mention of
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai/GPTBot
anywhere, no blanket `Disallow: /`, and nothing restricting `/wp-json/` or
any path this actor touches.

## WAF / anti-bot

**None observed.** Plain `nginx` + Plesk hosting (`X-Powered-By: PleskLin`),
no Cloudflare/`cf-ray`/challenge markers, no CAPTCHA, no rate limiting
noticed across dozens of requests during recon. A generic `/login/` link
(a sitewide "supplier portal" widget) appears in the header on every page,
but it gates nothing this actor reads — no cookie, session, or account was
ever needed to fetch any listing or detail page below.

## Three record types, three very different access patterns

Route discovery via `GET /wp-json/` and `GET /wp-json/wp/v2/types` revealed
NPC's site runs WordPress + Elementor + the JetEngine plugin, exposing:

### 1. `tender_notices` — open tenders (`/tender-advertisement/`)

This is a JetEngine **Custom Content Type (CCT)**, not a real WordPress post
type:

- `GET /wp-json/jet-engine/v2/get-items` → HTTP 401 `rest_forbidden`
  (admin-only; confirmed with and without query params).
- No entry in `/sitemap_index.xml` (compare with `press-releases-sitemap.xml`,
  `suppliers-sitemap.xml`, `contracts-awarded-sitemap.xml`,
  `disposals-notice-sitemap.xml`, which all exist).
- No individual permalinks — the listing page itself is the only place any
  open tender's data appears.

**The listing widget's own pagination is disabled.** The page HTML embeds a
`data-nav` JSON blob:

```json
{"enabled": false, "type": null, "more_el": null, "query": [], "widget_settings": {...}}
```

`"enabled": false` and `"use_load_more": ""` inside `widget_settings` mean
the "load more"/pagination UI was never wired up on this widget, even
though the same markup carries `data-pages="3"` — a stale artifact of how
many pages of 6 exist server-side, not a working, clickable control. **A
real site visitor cannot browse past the ~6 cards rendered in the initial
HTML.**

Reverse-engineered the underlying AJAX contract anyway, in case a
signed/whitelisted request could recover the remaining pages:

- `JetEngineSettings.ajaxlisting` (inline page JS) points requests at the
  **page URL itself** (`https://npc.gov.pg/tender-advertisement/?nocache=<ts>`),
  not `admin-ajax.php` as JetEngine's generic frontend code elsewhere
  suggests — confirmed both endpoints accept the POST and reach the same
  handler.
- Correct payload shape required jQuery-style bracket-encoded nested form
  fields (`widget_settings[...]=...`, `page_settings[page]=2`, etc.) — a
  naive JSON-string `widget_settings` value causes a PHP fatal
  (`HTTP 500`, "critical error").
- With correctly bracket-encoded params (`action=jet_engine_ajax&
  handler=get_listing&page_settings[page]=2&...`), the server replies
  `HTTP 200 {"success":false,"data":"Invalid query signature"}`. JetEngine
  added a request-signing check specifically for lazy-load/load-more to
  block exactly this kind of scripted request; the signature is generated
  server-side per rendered widget and is never exposed anywhere in the
  page's HTML or inline JS when (as here) the widget's own nav is disabled.

**Conclusion: there is no way to retrieve tenders NPC has already taken off
this page** (closed/withdrawn ones) through any public, unauthenticated
mechanism. This actor therefore surfaces exactly what npc.gov.pg itself
shows a visitor: the current open tenders, in full. This is a genuine
limitation of NPC's own site, documented here rather than worked around
with a fabricated or partial "full archive" claim.

Confirmed card structure (consistent across all 6 samples, 2026-08-27):
one long-form description field, one short title field, an
`NPC/YYYY-NN`-style reference-number button, a "CLOSING DATE & TIME: ..."
line, and a "Download Tender Advert" button linking a PDF. Each card is
bounded in the HTML by `jet-listing-grid__item jet-listing-dynamic-post-<id>`
markers; the last card's bound is additionally clamped to the next
`<footer` tag so sitewide footer PDF links (Procurement Act, Good
Procurement Manual, etc.) never leak into the last tender's `pdf_url`.

### 2. `disposals-notice` — asset disposal notices (`/dsa/`)

A real, registered post type (`show_in_rest: true`). Fully paginated:

```
GET https://npc.gov.pg/wp-json/wp/v2/disposals-notice
    ?page=<1-based>&per_page=<1-100>&orderby=date&order=desc
```

13 records at recon time (`X-WP-Total` header). Each has a real permalink
(`/disposals-notice/<slug>/`) and appears in `disposals-notice-sitemap.xml`.

### 3. `contracts-awarded` — awarded-contract transparency register

Not linked from primary nav, but fully public, same pattern:

```
GET https://npc.gov.pg/wp-json/wp/v2/contracts-awarded
    ?page=<1-based>&per_page=<1-100>&orderby=date&order=desc
```

182 records at recon time. Permalink `/contract-awarded/<slug>/`, own
sitemap.

## REST responses are list-only — detail pages carry the real data

For both `disposals-notice` and `contracts-awarded`, the default `wp/v2`
response fields are `id`, `date`/`date_gmt`, `guid`, `modified`/
`modified_gmt`, `slug`, `status`, `type`, `link`, `title`, `template`,
`class_list`, `yoast_head`/`yoast_head_json`, `_links` — **no `content`,
`excerpt`, or `meta`**. Confirmed by printing the full key list of a sample
row from each type. All substantive fields (agency, dates, contract value,
supplier name, PDF link) live only in the rendered HTML of each individual
detail page, as JetEngine "Dynamic Field" widgets.

This actor uses the REST route purely for cheap, fully-paginated
**discovery** (every record's id/title/slug/link/date, in one request per
100 rows), then fetches each detail page's HTML for the labeled fields.

## Detail-page structure: bounded to `<main id="jet-theme-core-single">`

Every single-item template on this site wraps its substantive content in
one `<main id="jet-theme-core-single">...</main>` element. Header, nav,
sidebar widgets, and footer — which carry unrelated PDF links (Procurement
Act, Good Procurement Manual, Background Information/Eligibility
Requirements, and in some cases even the "latest tenders" carousel) — all
live OUTSIDE that element. Confirmed on both a `disposals-notice` sample
(4 sitewide PDF links appeared in the raw page; exactly 1 — the notice's
own advert — sat inside `<main id="jet-theme-core-single">`) and a
`contracts-awarded` sample (0 PDF links inside the bound, correctly — no
PDF is published for awarded contracts). Bounding extraction to this
element is what keeps a record's own PDF link (or lack of one) from being
confused with sitewide boilerplate.

Within that bound, every labeled field follows the pattern
`<TAG class="...jet-listing-dynamic-field__content...">`
`<b>Label</b>` `[<br>]` `value` `</TAG>` (`TAG` is `h4`, `p`, or `div`
depending on the field). This actor's regex uses a backreference to the
opening tag name so a lazy match can't stop early at an unrelated inner
closing tag of a *different* tag type appearing before the real close
(a real bug caught during development: the tender-card description field
wraps multiple `<p>` paragraphs inside one outer `<h4>`, and a naive
`.*?</(?:h4|p|div)>` pattern truncated the description at the first inner
`</p>` instead of the real `</h4>`).

Sample labeled fields seen (label text is upstream-authored free text, kept
verbatim — not split into a fixed schema, per `.ai/CLAUDE.md` principle 5):

- `disposals-notice`: `Project Name`, `Department/Agency`, `Closing Date`,
  `Pre-Inspection Date`.
- `contracts-awarded`: `Contract Name`, `Agency`, `Method for Procurement`,
  `Contract Start Date`, `Nature of Goods, Services, or Works Procured`,
  `Contract Value Inc GST (PGK Unless Specified)`, `Supplier Name`.

A `suppliers` post type also exists (139 records, own sitemap) but its
detail pages carry no field beyond the name already in the REST title — not
worth a dedicated mode.

## Title unescaping

WordPress's REST API always HTML-entity-escapes `title.rendered` (e.g.
`"Short Form &#8211; Fuel"` for an en dash). This actor unescapes it to
`"Short Form – Fuel"` — the same normalization this portfolio's other
WordPress-backed actors already apply to `title.rendered`.

## Pagination strategy

`page=<n>` (1-based), `per_page` up to WordPress's standard 100 cap, walked
forward until a page returns zero rows, the running total reaches the
caller's `maxResultsPerType`, the upstream `X-WP-Total` count for that type
is reached, or a `MAX_PAGES_PER_JOB` (50 pages) safety cap is hit. The open
tenders (`tenders` mode) have no pagination parameter at all — the single
listing-page fetch returns everything the site exposes.

## Known limits

- **Open tenders are capped at whatever NPC currently shows** (observed: 6)
  — there is no way to retrieve tenders NPC has already removed from
  `/tender-advertisement/`, for the reasons detailed above. This is a real
  limitation of NPC's own site.
- `contracts-awarded` never carries a PDF — confirmed by design (no
  document is published alongside an award record), not a scraping gap.
- Labeled-field label text and formatting vary slightly between records
  (e.g. `Closing Date` vs `CLOSING DATE & TIME`) — kept verbatim rather than
  normalized into one canonical field name.
- No historical archive of closed/withdrawn tenders exists on this site at
  all (distinct from the disposals/contracts registers, which are proper
  paginated archives).

## Diff cadence

Quarterly smoke test recommended — this is a live government WordPress
site; a plugin/theme migration could change the JetEngine markup, the REST
field set, or re-enable the tender-listing pagination this actor currently
cannot use.
