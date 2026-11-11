"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-08-26): point2homes.com is a server-rendered (ASP.NET,
`.AspNet.Cafe.Au.Lait` cookie) site sitting behind Cloudflare (`cf-ray`,
`server: cloudflare`, `__cf_bm` cookie) -- but no active challenge was
observed. `curl_cffi` `chrome124` gets clean 200s on the homepage,
location-search pages, and listing/apartment-complex detail pages alike,
with no Kasada/PerimeterX/DataDome markers of any kind (checked cookies,
headers, and body for all known signatures). As of this recon, Point2Homes
operates as a Yardi/RentCafe-network rental listings aggregator -- the
homepage and every discoverable nav link are rental-only ("Houses For
Rent" / "Apartments For Rent"); no working "for sale" URL pattern was
found (several guesses -- Homes-For-Sale, Real-Estate-Listings,
Condos-For-Sale -- all 404/410). This actor is scoped to rentals only.

**robots.txt is the load-bearing constraint for this actor's
architecture**, not a WAF. The `User-agent: *` group disallows:
- `*/Search/*`, `/ListingSearch*`, `/Listings/*` (capital L, plural) --
  the site's actual search UI / API surface
- A long list of query-string filter params: `LocationGeoId=`,
  `Location=`/`location=`, `SearchType=`, `sort_by=`, `SquareFeet=`,
  `YearBuilt=`, `ListingDate=`, `ListingPrice=`, `ListingsSearch=`,
  `Price=`, `Bedrooms=`, `OpenHouse=`, `selected_view=`/`selectedView=`,
  `search_mode=`, `showSaveSearchPopup=`, `agentname=`

None of these are used by this actor. What IS clean under robots.txt and
carries full listing data:
- `point2homes.com/US/Houses-For-Rent/<STATE>/<City>.html` -- browse
  page for single-family/townhome/condo rentals in a city
- `point2homes.com/US/Apartments-For-Rent/<STATE>/<City>.html` -- browse
  page for apartment complexes in a city
- `?page=<N>` pagination on either of the above (NOT in the disallowed
  query-param list)
- `point2homes.com/US/Home-For-Rent/<STATE>/<City>/<slug>.html` -- a
  single house/townhome/condo listing's detail page (singular "Home",
  distinct from the disallowed plural "/Listings/")
- `point2homes.com/US/Apartment-Buildings/<STATE>/<City>/<slug>.html` --
  a single apartment complex's detail page

See CRAWLING_METHOD.md for full recon detail and captured examples.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.point2homes.com"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

ITEMS_PER_PAGE = 30

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
