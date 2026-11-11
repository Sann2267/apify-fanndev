"""Fixed facts about indotrading.com, established by recon on 2026-09-21."""

from __future__ import annotations

SITE_ROOT = "https://www.indotrading.com"
WEBAPI_ROOT = "https://webapi.indotrading.com"

# Recon 2026-09-21: Cloudflare sits in front of the whole origin and gates on
# the TLS fingerprint alone -- plain `requests` is answered 403 "Attention
# Required", while every curl_cffi impersonation profile tried (chrome124,
# chrome131, safari17_0, firefox133, edge101, chrome99_android) returned 200
# on the same IP within the same minute. There is no JS challenge, no
# clearance cookie and no token to harvest.
#
# But that was measured from a residential address. The first cloud run
# (2026-09-21, run hZg8O6ETXuwffaUj7) showed Cloudflare scoring the SAME paths
# differently from an Apify datacenter ASN: chrome124 was challenged on
# /jual-pressure-washer and firefox133 served it immediately on retry. So
# firefox133 leads -- it is the profile that works from both kinds of address,
# and leading with it saves every cloud run one wasted request and one backoff.
# The rest of the ladder is the recovery path: a challenge body or an
# unexpected 403 rotates and rebuilds the session rather than failing the run.
TLS_PROFILES = (
    "firefox133",
    "chrome124",
    "safari17_0",
    "chrome131",
    "edge101",
    "chrome99_android",
)

# Cloudflare's interstitials answer 403 with these in the body. They are
# checked against the body because a challenge can arrive with any status.
BLOCK_MARKERS = (
    "attention required",
    "just a moment",
    "cf-error-details",
    "cdn-cgi/styles/cf.errors.css",
    "checking your browser",
    "enable javascript and cookies to continue",
)

# Any unrecognised path is answered with the homepage at HTTP 200 instead of a
# 404 -- /rfqlist/pompa, /sitemap.xml and /supplier all return the identical
# 451,428-byte document. Size alone is too brittle to key on (the homepage
# changes daily), so a page is treated as this fallback when it carries the
# homepage's <title> while the caller expected something else.
HOME_TITLE_MARKER = "b2b marketplace, direktori bisnis supplier"

# A category or search page with no results is a *different* document: ~175 KB,
# no product cards and no "Halaman X dari Y" counter. That is a real empty
# result, not a block, and it is how pagination terminates.

# 40 product cards per listing page, fixed and not overridable -- pageSize,
# limit, take and count are all ignored.
PRODUCTS_PER_PAGE = 40

# The "(Halaman 1 dari N)" counter OVERSTATES the reachable inventory.
# /jual-pressure-washer advertises 640 products across 16 pages but runs dry at
# page 12; /jual-mesin-las advertises 79 pages and is empty by page 50. So the
# advertised total is recorded as metadata and never used as a stop condition:
# paging stops on the first page that yields zero cards.
MAX_PAGE_HARD_CAP = 500

# Pagination parameter. `?page=N` and the bare suffix `/N` both work; `hal`,
# `p`, `pg` and `PageNumber` are accepted with 200 and silently ignored,
# returning page 1 every time -- a decoy that looks like success.
PAGE_PARAM = "page"

SEARCH_PRODUCTS_PATH = "/searchkeyword.aspx"
SEARCH_COMPANY_PATH = "/searchcompany.aspx"
CATALOG_PATH = "/productcatalog"

# webapi.indotrading.com. Open to anonymous callers -- no Authorization, no
# cookie, no origin check. Harvested from the Astro bundle
# CategoryInteractions.astro_*.js, where the host comes from
# `window.storefrontApiHost`.
WA_LEADS_PATH = "/api/Product/GetWhatsappLeadsData"
LAST_LOGIN_PATH = "/api/Company/GetListCompanyLastLogin"
LIST_BY_COMPANY_PATH = "/api/Product/ListByCompany"

# GetListCompanyLastLogin answers with minutes-since-last-login as a string,
# or the literal "failed" for an id it cannot resolve.
LAST_LOGIN_FAILED = "failed"

DEFAULT_MAX_PAGES = 5
DEFAULT_TIMEOUT_SECS = 45
DEFAULT_MAX_RETRIES = 4
DEFAULT_CONCURRENCY = 4
