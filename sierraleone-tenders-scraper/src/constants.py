"""Endpoints, headers, profile choice -- all in one place.

Recon summary (2026-08-27): Sierra Leone's public procurement regulator is
the **National Public Procurement Authority (NPPA)**, `nppa.gov.sl`. NPPA
also runs a modern e-GP (electronic Government Procurement) microservice
platform at `egp.nppa.gov.sl` -- a Next.js SPA backed by ~10 NestJS
microservices on `*-egp.nppa.gov.sl` (built by Perago Systems, the same
vendor behind Malawi's `maneps.mw` e-GP platform, confirmed via shared
strings baked into the frontend's JS bundles).

That would have been the ideal target (it even exposes an Open Contracting
Data Standard/OCDS export at `rms-egp.nppa.gov.sl/api/ocds/*`), but as of
this actor's last verification **it cannot be used**:

- `tendering-egp.nppa.gov.sl` -- the ONLY microservice backing the
  `/procurement-notice` listing page's `GET /api/tenders` call -- returns a
  bare `502 Bad Gateway` on every single path (including `/`) for
  every TLS profile tried, `curl_cffi` AND plain `requests`, across
  repeated retries over 10+ minutes. Sibling microservices on the exact
  same IP (`rms-egp`, `planning-egp`, `vendor-egp`, `administration-egp`)
  all respond normally -- this is an isolated, genuine outage of just the
  tendering service, not a WAF or a network issue on our end. The
  `/procurement-notice` page itself is 100% client-rendered (confirmed via
  its Next.js RSC payload -- zero tender data is ever embedded server-side),
  so even a real human visiting that page right now sees nothing.
- The OCDS export (`rms-egp.nppa.gov.sl/api/ocds/get-records`, POST) IS
  live and returns a well-formed response for any request body tried --
  but `{"total": 0, "items": []}` every time. This is a genuinely empty
  data store right now, not a request-shape problem (no validation errors
  are ever raised for unrecognized filter keys).

Fortunately NPPA's older WordPress "corporate" site (also `nppa.gov.sl`,
a separate CMS from the broken e-GP SPA) publishes the exact same kind of
notices by hand, on a plain server-rendered page: **`nppa.gov.sl/bid/`**
("Bids / Tenders" in the site's own nav menu), an Elementor page embedding
a **TablePress** table (`#tablepress-1`) with one row per tender:
Bidding Organization | Date Posted | Expiration Date | Description of
Bidding | Download Bid (a PDF link). This is genuinely current (newest row
verified at 2026-08-20, one week before this actor was built) and goes
back to July 2025. This is the actor's real target -- the same
"official site is broken in one specific spot but a different, older part
of the same domain still works" pattern seen on Sierra Leone's OARG
business registry (`sierraleone-oarg-scraper`).

## robots.txt / WAF

`nppa.gov.sl/robots.txt`:

    User-agent: *
    Disallow: /wp-content/uploads/wc-logs/
    Disallow: /wp-content/uploads/woocommerce_transient_files/
    Disallow: /wp-content/uploads/woocommerce_uploads/
    Disallow: /wp-admin/
    Allow: /wp-admin/admin-ajax.php
    Sitemap: https://nppa.gov.sl/wp-sitemap.xml

Wide open for `/bid/` and everything this actor touches. No mention of
`Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` anywhere, no blanket disallow. No login wall, no CAPTCHA, no
WAF challenge observed on `/bid/` -- a plain stateless GET, identical `200`
across every TLS profile tried.

## Known upstream data quality issues (not bugs in this actor)

- Date strings are inconsistently formatted by whoever maintains the
  table: `"14-08-2026"`, `"30- 04-2026"` (stray space), `"13-4-2026"`
  (no leading zero), `"23-04-26"` (2-digit year). `extractor.py` parses
  leniently and returns `None` for the ISO fields when a row genuinely
  can't be parsed, rather than raising.
- A few rows have a broken/missing "Download Bid" link -- either an
  `<a>` tag with no `href` attribute at all, or `href=""`. Both are
  treated as "no document available" (`documentUrl: null`), not an error.
- The "Bidding Organization" text sometimes has stray letter-spacing
  baked into the source HTML itself (e.g. "I N S T I T U TE OF PUBLIC
  ADMINISTRATION") -- passed through verbatim, not corrected.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No blocking of any kind was observed on this target.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://nppa.gov.sl/bid/"

TABLE_ID = "tablepress-1"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
