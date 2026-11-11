"""Endpoints, hosts, headers, WAF/challenge constants for klikindomaret.com.

The site is a Next.js static-export SPA fronted by Cloudflare, with the real
runtime API served from the module-federation asset host `ap-mc.klikindomaret.com`
(NOT `api-klik.klikindomaret.com`, which is hard Cloudflare-bot-gated on real
routes). Most `/api/get/` endpoints there are gated only by AWS WAF (a
`NetworkBandwidth` proof-of-work we solve headlessly). The product-listing
endpoint `search/result` is *additionally* behind a Cloudflare managed challenge
and needs a `cf_clearance` cookie earned by a real browser (Camoufox).
"""

SITE = "https://www.klikindomaret.com"
AP = "https://ap-mc.klikindomaret.com"

# Module-federation asset host doubles as the API gateway; each micro-frontend
# proxies through its own asset path prefix.
MOD_ORDER = f"{AP}/assets-klikidmorder"
MOD_GROCERIES = f"{AP}/assets-klikidmgroceries"
MOD_SEARCH = f"{AP}/assets-klikidmsearch"

# --- Endpoint templates (all GET) ---------------------------------------------
EP_SEARCH_CONFIG = f"{MOD_ORDER}/api/get/catalog-xpress/api/webapp/search/configuration"
EP_STORES_SEARCH = f"{MOD_ORDER}/api/get/catalog-xpress/api/webapp/stores/search"
EP_KELURAHAN = f"{MOD_ORDER}/api/get/coverage-area/api/mobile/kelurahan-by-district"
EP_CATEGORY_META = f"{MOD_GROCERIES}/api/get/catalog-xpress/api/webapp/category/meta"
EP_SEARCH_RESULT = f"{MOD_SEARCH}/api/get/catalog-xpress/api/webapp/search/result"
EP_SUGGESTION = f"{MOD_SEARCH}/api/get/catalog-xpress/api/webapp/search/suggestion"
EP_BANNERS = f"{MOD_SEARCH}/api/get/home/xpress/api/webapp/banners"

# --- AWS WAF challenge SDK ----------------------------------------------------
# The <script src> the homepage loads for AwsWafIntegration. If klikindomaret
# rotates its WAF ACL this URL changes; it is discoverable in the homepage HTML
# as the `*.sdk.awswaf.com/.../challenge.js` script tag.
AWS_SDK_URL = (
    "https://450fb442a405.ap-southeast-3.sdk.awswaf.com"
    "/450fb442a405/e4618982a248/challenge.js"
)

# --- TLS / identity -----------------------------------------------------------
# Camoufox is Firefox; to replay its cf_clearance cookie over curl_cffi the TLS
# fingerprint and UA must match a Firefox. When no clearance is needed we still
# use a Firefox profile for consistency.
TLS_PROFILE = "firefox133"

# Default store context (Jakarta Pusat / Gambir) used when the caller does not
# supply one. Everything on this site is store-scoped (click-and-collect).
DEFAULT_DISTRICT_ID = "141100100"
DEFAULT_STORE_CODE = "TJKT"
DEFAULT_LAT = "-6.1763897"
DEFAULT_LONG = "106.82667"
DEFAULT_MODE = "DELIVERY"

# Fallback keyword for a `productSearch` run started with no `searchTerms` and no
# `categoryIds` (e.g. the platform's default input). Scraping a common staple
# beats failing the run outright; the run logs a warning when it kicks in.
DEFAULT_SEARCH_TERM = "indomie"

# --- Block markers ------------------------------------------------------------
CF_BLOCK_MARKERS = (b"Attention Required", b"Just a moment", b"cf-mitigated")
NGINX_403 = b"<title>403 Forbidden</title>"
AWS_CHALLENGE_MARKERS = (b"AwsWafIntegration", b"awswaf")

# Retry policy
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0  # exponential 1/2/4/8/16s
AWS_TOKEN_TTL = 240  # seconds; re-mint before AWS WAF rotates (~5 min window)
