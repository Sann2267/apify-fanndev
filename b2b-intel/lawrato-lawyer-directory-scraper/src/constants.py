"""URLs, facets, headers -- all in one place.

Recon summary (2026-09-08): lawrato.com is India's largest consumer-facing
lawyer directory. Everything used here is plain server-rendered HTML --
no client-side rendering, no JSON API behind it, no login.

Cloudflare fronts the site (its Rocket Loader rewrites inline handlers to
`window.__cfRLUnblockHandlers`), but no challenge was ever served: listing
and profile pages both return a clean 200 with full markup to a
`curl_cffi` chrome request. TLS impersonation is kept because Cloudflare
is present and could tighten.

Why India and not Indonesia: Babak 42 of ACTOR_MARKET_RESEARCHER_NEW.md
ranked the empty jurisdictions ID -> IN -> SG/MY for this data-type.
Indonesia was checked first and **has no scrapable lawyer directory at
all** -- hukumonline.com/pusatdata is a regulations database, /klinik is a
Q&A column, and peradi.or.id (the bar association, back up at 347 KB after
timing out during Babak 42) publishes newly-sworn advocates only as news
articles, with no member directory. That is a data-surface gap, not an
untapped market. India was the next jurisdiction on the list and does have
a real directory.

Listing pages carry schema.org `LocalBusiness` microdata per card, so the
card parse is anchored on `itemprop` attributes rather than on styling
classes wherever possible.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://lawrato.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# --- listing routes ----------------------------------------------------
# All India:            /lawyers            (+ ?page=N)
# One city:             /lawyers/<city>     (+ ?page=N)
# One practice area:    /<area>-lawyers     (+ ?page=N)
# City + area together is NOT a supported route upstream -- pick one axis.
PATH_ALL = "/lawyers"
PATH_CITY = "/lawyers/{city}"
PATH_AREA = "/{area}-lawyers"

# Profile route: /advocate-<slug>
PROFILE_PREFIX = "/advocate-"

# 20 cards per listing page, confirmed on /lawyers, /lawyers?page=2,
# ?page=50, /lawyers/delhi and /divorce-lawyers alike. A page past the end
# (?page=999) still returns 200 with a near-empty shell and 0 usable cards,
# so pagination stops on "fewer cards than PAGE_SIZE" or "no cards at all"
# rather than on any status code.
PAGE_SIZE = 20

MODES = ["directory", "profile", "reference"]

# Facets linked from /lawyers on 2026-09-08. Used to populate the input
# schema dropdowns; `reference` mode always re-reads them live.
CITIES = [
    "ahmedabad", "bangalore", "chandigarh", "chennai", "delhi", "faridabad",
    "ghaziabad", "gurgaon", "hyderabad", "jaipur", "kolkata", "lucknow",
    "mumbai", "nagpur", "noida", "pune",
]

PRACTICE_AREAS = [
    "arbitration", "armed-forces-tribunal", "banking-finance", "cheque-bounce",
    "child-custody", "civil", "consumer-court", "copyright-patent-trademark",
    "corporate", "criminal", "customs-central-excise", "cyber-crime", "divorce",
    "documentation", "family", "gst", "immigration", "insurance",
    "international-law", "labour-service", "landlordtenant", "medical-negligence",
    "motor-accident", "muslim-law", "property", "recovery", "startup",
    "supreme-court", "tax", "wills-trusts",
]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
