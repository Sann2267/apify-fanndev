"""Fixed facts about Etsy, established by recon on 2026-09-21.

Etsy is behind DataDome (`server: DataDome`, `x-datadome: protected`). A block
is not a plain 403 page: it is a ~780-byte HTML stub carrying an inline `dd`
object with `'rt':'i'` and a script from `ct.captcha-delivery.com`. That is an
*interstitial* challenge, solvable only by running DataDome's JavaScript, so an
HTTP-only client cannot clear it -- the only workable strategy is not to
trigger it. Three independent gates decide whether it fires:

1. TLS fingerprint.  Plain `requests` is blocked everywhere. Under curl_cffi
   impersonation the Safari profiles are by far the most reliable; Chrome
   passes on the grid surfaces but is weaker on shop and listing pages, and
   safari260 / edge101 draw the interstitial almost everywhere. See
   TLS_PROFILES for the ladder that recon actually measured.

2. Path shape.  `/shop/<name>` is challenged from every IP and profile we
   tried, while the locale-prefixed `/uk/shop/<name>` is served 200 -- verified
   on four different shops back to back, and the same holds for
   `/<locale>/shop/<name>/reviews`. DataDome's rule for the shop class is
   registered on the bare prefix only, so every shop URL this actor builds
   carries a locale prefix. See SHOP_LOCALE.

3. Slug exactness.  `/listing/<id>/<exact-slug>` is served 200, but
   `/listing/<id>`, `/listing/<id>/x` and `/listing/<id>/<any-wrong-slug>` are
   all challenged: a wrong slug makes Etsy answer 301 to the canonical URL and
   DataDome blocks the redirect rather than the page. A bare listing ID is
   therefore NOT resolvable on its own -- product URLs must come in whole, or
   be discovered from a grid or shop page, both of which emit the full href.

robots.txt (checked 2026-09-21, no Claude/anthropic-ai/CCBot rule anywhere)
shapes the surface map as much as DataDome does:

  Disallowed for every user-agent, so this actor never requests them:
    /search?*q=  /search/?*q=  /search/*?*q=   keyword PRODUCT search
    /api/                                      every internal AJAX endpoint
    */shop/*/sold*                             a shop's sold-items feed
    */shop/*/favoriters*  */listing/*/favoriters*
    */shop/*/rss_shop.php                      the per-shop RSS feed
    /*?order=*                                 every explicit sort order
    /c/*attr_*=*  /c/*price_bucket=*  /c/*ship_to=*  /c/*search_type=*

  Explicitly allowed, and the reason this actor has a keyword entry point:
    /search/shops   (an `Allow:` line per locale, overriding /search/*?*q=)

Two surfaces look like keyword search and are not. `/c?q=<kw>` and
`/c/<path>?q=<kw>` both answer 200 with a full 64-card grid, but the grid is
byte-for-byte the same for "vintage ring", "leather journal", "crochet pattern
dinosaur" and "zzzqqqxyznotathing" -- `q` is parsed and discarded. `/market/<kw>`
is a real keyword page but carries only an 8-card promotional strip, not a
result grid. Neither is used.
"""

from __future__ import annotations

SITE_ROOT = "https://www.etsy.com"

# Recon 2026-09-21, measured per surface rather than assumed. safari184 was the
# single strongest profile (3/3 on listing pages when chrome was 0/3, and the
# only profile to clear a category page on one degraded IP), so it leads. The
# Chrome entries earn their place on /c/ and /search/shops, where they pass
# often enough to be worth rotating onto. safari260 and edge101 are left out on
# purpose: both drew the DataDome interstitial on surfaces the others passed,
# and rotating onto a profile that is itself challenge-prone turns one bad
# request into two.
TLS_PROFILES = (
    "safari184",
    "safari17_0",
    "chrome150",
    "chrome131",
    "safari180",
    "firefox147",
)

# DataDome's interstitial stub. The header is authoritative and cheap; the body
# markers catch a stub served without it. Status is deliberately not used on its
# own -- Etsy answers a genuinely missing shop with 404 through the same edge.
DATADOME_SERVER = "datadome"
DATADOME_HEADER = "x-datadome"
BLOCK_MARKERS = (
    "captcha-delivery.com",
    "please enable js and disable any ad blocker",
    "geo.captcha-delivery",
)

# Etsy's locale prefixes. Two jobs: they are the gate bypass for shop URLs, and
# they pin the currency, which otherwise follows the proxy's exit IP (the same
# ring came back in IDR, EUR, GBP, AUD and CAD purely by changing the exit).
# "" is Etsy's unprefixed US-default site and is what a US exit IP should use.
LOCALES = {
    "": "follows the exit IP (USD from a US exit)",
    "uk": "GBP",
    "de-en": "EUR (German site, English copy)",
    "au": "AUD",
    "ca": "CAD",
    "ie": "EUR",
    "nz": "NZD",
    "in-en": "INR",
    "sg-en": "SGD",
    "hk-en": "HKD",
    "il-en": "ILS",
    "dk-en": "DKK",
    "fi-en": "EUR",
    "no-en": "NOK",
    "se-en": "SEK",
}

# The bare /shop/ prefix is always challenged, so shop URLs get a locale. uk is
# the default because it is English-language and was 200 on every shop tried.
SHOP_LOCALE_DEFAULT = "uk"

# /c/<path>?page=N serves 64 cards per page and stops at 250: page 250 is full,
# page 251 and beyond return the "Try searching for something else instead?"
# empty-results page. That is ~16,000 listings per category.
CATEGORY_MAX_PAGE = 250
CATEGORY_PAGE_SIZE = 64

# /search/shops?q=<kw>&page=N serves 12 shop cards per page.
SHOPS_SEARCH_PAGE_SIZE = 12

# An empty grid is NOT a reliable end-of-results signal: page 25 of
# /c/jewelry/rings came back empty while pages 50, 100 and 250 were full, on
# the same profile minutes apart. Paging therefore tolerates this many empty
# pages in a row before it accepts that a target is exhausted.
EMPTY_PAGE_TOLERANCE = 2

TOP_CATEGORIES = (
    "accessories",
    "art-and-collectibles",
    "bags-and-purses",
    "bath-and-beauty",
    "books-movies-and-music",
    "clothing",
    "craft-supplies-and-tools",
    "electronics-and-accessories",
    "gifts",
    "home-and-living",
    "jewelry",
    "kids-and-baby",
    "paper-and-party-supplies",
    "pet-supplies",
    "shoes",
    "toys-and-games",
    "weddings",
)

DEFAULT_MAX_RETRIES = 6
DEFAULT_TIMEOUT_SECS = 60
DEFAULT_REQUEST_DELAY_SECS = 2.0
