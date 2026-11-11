"""Everything measured about trustradius.com lives here, with the date it was measured."""

BASE = "https://www.trustradius.com"

# -- TLS ------------------------------------------------------------------
# Cloudflare gates on the TLS/HTTP2 fingerprint. Recon 2026-09-25, residential
# ID line, same IP, six profiles x four pages:
#   safari17_0 / firefox133 / chrome131  -> 200 on every page
#   chrome124                            -> 200 on pages, 403 on /robots.txt
#   chrome99_android / edge101           -> 403 "Just a moment..." everywhere
# The ladder leads with the two non-Chromium profiles (least blocklisted in
# 2026) and keeps chrome131 as the third rung. The two always-challenged
# profiles are left out: they cost a request each and never answer.
TLS_LADDER = ["safari17_0", "firefox133", "chrome131", "chrome124"]
TLS_CHALLENGED = ["chrome99_android", "edge101"]

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"Attention Required",
    b"cf-chl-",
)

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}
# Asking a Next.js App Router page for ``RSC: 1`` returns the flight stream
# alone (text/x-component) instead of HTML + the same stream embedded as JS
# strings: 424 KB vs 724 KB on /categories/crm. Every byte rides a residential
# proxy, so this is the default and HTML is the fallback.
RSC_HEADERS = {"RSC": "1", "Accept": "*/*"}
HTML_HEADERS = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

REQUEST_TIMEOUT = 45
MAX_RETRIES = 4            # per profile, for network errors and 5xx/429
CHALLENGE_RETRIES = 2      # challenges tolerated on one profile before the next rung
LADDER_ROUNDS = 3          # whole-ladder passes before a URL is declared blocked
RETRY_DELAY_BASE = 1.5     # seconds, exponential with jitter
LADDER_ROUND_DELAY = 8.0

# -- category listing -----------------------------------------------------
# /categories/<slug>?f=<offset>, 25 per page. Offset is free (f=13 works), but
# f >= 1000 returns the page shell with no product list at all -- an
# Elasticsearch-style max_result_window -- while meta.total keeps saying 1500.
CATEGORY_PAGE_SIZE = 25
CATEGORY_OFFSET_CEILING = 1000
# Filters the SSR honours (param names from the category page bundle):
#   hp=true, free-pricing=true, os=windows|mac|linux, top=true  -> SLICE (total drops)
#   company-size=small-business|mid-sized|enterprise              -> REORDER only (total unchanged)
# Both kinds let a category past the 1000 ceiling be covered by fan-out.
COMPANY_SIZES = ["small-business", "mid-sized", "enterprise"]
OPERATING_SYSTEMS = ["windows", "mac", "linux"]
DEEP_FANOUT = (
    [{"company-size": v} for v in COMPANY_SIZES]
    + [{"hp": "true"}, {"free-pricing": "true"}]
    + [{"os": v} for v in OPERATING_SYSTEMS]
)

# -- reviews --------------------------------------------------------------
# /products/<slug>/reviews?page=N, 10 per page, newest first, no depth ceiling
# (hubspot-crm: 176 x 10 + 2 = all 1762, zero duplicates). Past the end the
# page answers 200 with zero reviews. p=, f=, offset=, start=, sort= are all
# silently ignored -- they return page 1 again, so only ``page`` is used.
REVIEWS_PAGE_SIZE = 10

# robots.txt (2026-09-25): Disallow /api/ /share/ /search/ /profile/ /vendoradmin/ /cdn-cgi/
ROBOTS_DISALLOWED_PREFIXES = ("/api/", "/share/", "/search/", "/profile/", "/vendoradmin/", "/cdn-cgi/")

MODES = ["categoryProducts", "products", "reviews", "alternatives", "compare", "categories"]
