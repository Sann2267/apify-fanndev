"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Papua New Guinea's public procurement is run by
the **National Procurement Commission (NPC)**, a statutory body created by
the National Procurement Act 2018 that replaced the old Central Supply and
Tenders Board (CSTB) on 1 April 2019. NPC's own site, **`npc.gov.pg`**, is
the official, current portal -- it explicitly self-describes as "the
information hub for Electronic Government Procurement (e-GP) initiatives".
No separate CSTB site remains; all CSTB references online are historical.

`robots.txt` (`https://npc.gov.pg/robots.txt`) is a stock WordPress +
WooCommerce + Yoast SEO block:

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

Two `User-agent: *` groups (WooCommerce block + Yoast's empty block), no
mention of Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai/GPTBot anywhere, no blanket `Disallow: /`, and no restriction on
`/wp-json/` or any of the paths this actor touches. Plain `nginx` + Plesk
hosting, no Cloudflare/WAF/CAPTCHA of any kind observed on any request during
recon. A generic `/login/` link (a site-wide "supplier portal" auth widget)
appears on every page, but it gates nothing this actor reads -- every
listing and detail page below returns full content with zero cookies and no
session.

## Three record types, three very different access patterns

NPC's site is WordPress + Elementor + the JetEngine plugin. It exposes THREE
kinds of procurement notices, discovered via `/wp-json/` route discovery and
`/wp-json/wp/v2/types`:

1. **`tender_notices`** ("Tender Advertisement" nav item, page
   `/tender-advertisement/`) -- open/current tenders. This is a JetEngine
   **Custom Content Type (CCT)**, NOT a real WordPress post type: it has no
   `wp/v2` REST route (`GET /wp-json/jet-engine/v2/get-items` -> HTTP 401
   `rest_forbidden`, admin-only), no sitemap entry, and no individual
   permalinks -- every field for every open tender is rendered directly as
   HTML cards on the one listing page. Confirmed the listing widget itself
   has pagination **disabled** (`data-nav` -> `"enabled":false`,
   `"use_load_more":""`) even though `data-pages="3"` is present in the
   markup -- i.e. NPC's own site gives visitors no way to browse past the
   newest ~6 cards rendered server-side. Reverse-engineered the JetEngine
   AJAX contract anyway (`action=jet_engine_ajax&handler=get_listing` POSTed
   to the page URL, per `JetEngineSettings.ajaxlisting`) hoping to pull
   further pages, but every request -- correctly bracket-encoded, hitting
   either `admin-ajax.php` or the page URL -- comes back
   `{"success":false,"data":"Invalid query signature"}`; JetEngine added a
   request-signing check for lazy-load/load-more specifically to stop
   exactly this kind of hijacked-request scraping, and the signature is
   never exposed client-side when the widget's own nav is disabled. This
   actor therefore surfaces exactly what a real visitor sees: the current
   open tenders rendered on the page (observed 6, all fields present: title,
   description, `NPC/YYYY-NN` reference number, closing date/time, and a
   direct PDF advert link) -- documented as a genuine site limitation, not
   patched over.
2. **`disposals-notice`** ("Disposal of State Assets" nav item, page `/dsa/`)
   -- asset-disposal tenders (selling off government vehicles/equipment by
   sealed bid). A real, registered WordPress post type with
   `show_in_rest: true`: fully paginated via `/wp-json/wp/v2/disposals-notice`
   (13 records at recon time), each with a real permalink
   (`/disposals-notice/<slug>/`) and its own sitemap.
3. **`contracts-awarded`** ("Contracts Awarded" -- post-award transparency
   register, not linked from primary nav but fully public) -- same pattern:
   `/wp-json/wp/v2/contracts-awarded` (182 records at recon time), permalink
   `/contract-awarded/<slug>/`, own sitemap.

For both (2) and (3), the `wp/v2` REST response is list-only (`id`, `title`,
`slug`, `link`, dates, `class_list`) -- WordPress's default REST fields for
these two post types do NOT include `content`/`meta`, so every substantive
field (agency, dates, contract value, supplier, PDF link, etc.) lives only
in the rendered HTML of the individual detail page, inside JetEngine
"Dynamic Field" widgets formatted as `<b>Label:</b> value`. This actor uses
REST purely for cheap, fully-paginated **discovery** of every record's URL,
then fetches each detail page's HTML to extract the labeled fields.

## Confirmed detail-page structure

Every single-item template on this site wraps its substantive content in
one `<main id="jet-theme-core-single">...</main>` element -- the header,
nav, sidebar "latest tenders" widget, and footer (which carry unrelated PDF
links like the Procurement Act or Good Procurement Manual) all live OUTSIDE
that element. Bounding extraction to this element is what keeps the correct
per-record PDF link from being confused with sitewide boilerplate links
(confirmed on both a `disposals-notice` and a `contracts-awarded` sample:
the ONLY `.pdf` href inside `<main id="jet-theme-core-single">` on the
disposal sample was that disposal's own advert PDF; the boilerplate PDFs
all sat outside it).

Sample labeled fields seen:
- `disposals-notice`: `Project Name`, `Department/Agency`, `Closing Date`,
  `Pre-Inspection Date` (label text varies slightly per notice).
- `contracts-awarded`: `Contract Name`, `Agency`, `Method for Procurement`,
  `Contract Start Date`, `Nature of Goods, Services, or Works Procured`,
  `Contract Value Inc GST (PGK Unless Specified)`, `Supplier Name`.

Because label text is upstream-authored free text (not a fixed schema), this
actor keeps every `{label: value}` pair found on the page verbatim in a
`fields` dict rather than trying to force them into fixed named columns --
per `.ai/CLAUDE.md` principle 5 (raw passthrough). A `suppliers` post type
also exists (139 records) but its detail pages carry no fields beyond the
name already in the REST title -- not worth a dedicated mode.

TLS: plain `nginx`, no WAF -- `curl_cffi` `chrome124` used per portfolio
default; no impersonation-specific behavior was needed or observed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://npc.gov.pg"

TENDER_ADVERTISEMENT_PATH = "/tender-advertisement/"

REST_TYPES = {
    "disposals": "disposals-notice",
    "contracts": "contracts-awarded",
}

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REST_HEADERS = {
    "Accept": "application/json",
}

# WordPress core REST per_page hard cap.
PER_PAGE = 100

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Safety cap on page depth per REST-backed job (disposals/contracts) -- keeps
# a mistakenly huge maxResultsPerType from paging forever if upstream ever
# stops returning a sane X-WP-Total.
MAX_PAGES_PER_JOB = 50
