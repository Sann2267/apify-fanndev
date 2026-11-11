"""URLs, routes, headers -- all in one place.

Recon summary (2026-09-08): indonesiayp.com is a national business
directory ("Indonesia Yellow Pages" style) with ~13,900 listings in the
Restaurants category alone (696 pages at 20 per page). Everything used
here is plain server-rendered HTML: no client-side rendering, no login,
no WAF challenge, and no `Server:` header worth fingerprinting.

Why this target and not the one Babak 41 proposed: Babak 41 named
Sarisayfalar (TR) as the first jurisdiction for the "national business
directory" candidate, on the strength of a 111 KB / Apache / no-WAF probe.
**That probe measured the wrong kind of page.** Re-checked here,
`sarisayfalar.com` is a small classified-ads portal, not a business
directory: its homepage links are listing ads (`/N/vasita-atv`,
`/N/emlak-turistik-tesis`, `/N/is-ilanlari-*`), its search box asks for
"kelime, ilan no veya magaza adi" (keyword, ad number or shop name), and a
search for `avukat` (lawyer) returns an effectively empty 20 KB page. The
classified-ads vein was separately proven saturated in Babak 42 (9 of 9
countries, 32-42 sellers each), so that target is dead twice over.

Of the remaining jurisdictions Babak 41 listed for this candidate,
IndonesiaYP was picked because it is (a) a real directory with counts in
the thousands, (b) the home market, and (c) the emptiest per Babak 41's own
numbers (ID: 3 sellers / 7 users total). Live alternatives confirmed
reachable if this one is ever exhausted: `hitta.se` (SE, 2,453 hits for
"advokat"), `guiamais.com.br` (BR, 160 KB), `pai.pt` (PT, 54 KB).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.indonesiayp.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
}

# --- routes ------------------------------------------------------------
# Category listing:      /category/<slug>
# Page N of a category:  /category/<slug>/<N>          (NOT ?page=N)
# City-scoped listing:   /category/<slug>/city:<City>  (colon is literal)
# Company detail:        /company/<id>/<name_slug>
PATH_CATEGORY = "/category/{slug}"
PATH_CATEGORY_PAGE = "/category/{slug}/{page}"
PATH_CATEGORY_CITY = "/category/{slug}/city:{city}"
PATH_CATEGORY_CITY_PAGE = "/category/{slug}/city:{city}/{page}"

MODES = ["category", "company", "reference"]

# 20 listings per page, confirmed on /category/restaurants (13,904 listings
# spread over 696 pages).
PAGE_SIZE = 20

# The nine top-level categories linked from the homepage. Sub-categories
# exist too (e.g. /category/italian, /category/japanese) and any slug can be
# passed; `reference` mode reads the live list rather than trusting this one.
TOP_CATEGORIES = [
    "restaurants",
    "doctors_and_clinics",
    "lawyers",
    "estate_agents",
    "construction_services",
    "employment_agencies",
    "schools",
    "shopping_centres",
    "vehicle_services",
]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
