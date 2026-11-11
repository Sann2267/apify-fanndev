"""Endpoints, enums and tuning knobs for the Steam Community Market.

Everything here was verified anonymously on 2026-10-11 (see CRAWLING_METHOD.md).

The market was rebuilt as a React SSR app in 2026. Its browser bundle talks to
a small RPC layer that is open to logged-out visitors:

    GET /market/actions?q=<Method>&qp=<JSON array of args>
    GET /market/orderbook?q=Load&qp=[appid, "<market_hash_name>"]

each answering ``{"data": ..., "metrics": ...}``. That layer is what this actor
uses, because it beats the legacy JSON endpoints on every axis that matters:

* ``QueryPriceHistory`` returns the full median-price/volume series anonymously,
  while legacy ``/market/pricehistory/`` answers 400 without a login cookie.
* 80 back-to-back RPC calls from one IP drew zero 429s; legacy
  ``/market/priceoverview/`` started answering 429 after 20.
* ``Search`` honours ``count=100``; legacy ``/market/search/render/`` now caps
  every page at 10 rows.
"""

from __future__ import annotations

BASE_URL = "https://steamcommunity.com"
ACTIONS_ROUTE = "/market/actions"
ORDERBOOK_ROUTE = "/market/orderbook"
LISTING_PAGE_ROUTE = "/market/listings"
ICON_CDN = "https://community.akamai.steamstatic.com/economy/image/"

# The header the bundle sends. The server answers without it today, but it is
# part of the contract the SPA relies on, so we keep sending it.
QUERY_HEADERS = {
    "x-valve-request-type": "queryAction",
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
# SSR route loader: index 3 of /market/listings/:appid/:name is the bucket
# list (every wear / StatTrak / Souvenir variant of a skin) as 3 KB of JSON,
# instead of the 4 MB HTML page that embeds it.
ROUTE_DATA_HEADERS = {
    "x-valve-request-type": "routeData",
    "x-valve-loader-index": "3",
    "Accept": "application/json, */*",
}

# No WAF sits in front of steamcommunity.com (plain nginx; every profile below
# answers 200). The ladder exists for the day that changes and for rotating
# away from a profile a rate limiter has latched onto. chrome124 leads because
# it is the profile the whole recon ran on.
TLS_PROFILES = ["chrome124", "safari17_0", "chrome99_android", "edge101", "chrome131"]

MAX_RETRIES = 6
RETRY_DELAY_BASE = 1.5  # seconds -> 1.5, 3, 6, 12, 24 (+ jitter)
REQUEST_TIMEOUT = 45

SEARCH_PAGE_SIZE = 100  # server maximum for Search
LISTINGS_PAGE_SIZE = 20  # fixed server-side; count is ignored
MAX_SEARCH_ITEMS = 50_000
MAX_LISTINGS_PER_ITEM = 10_000

# Friendly names for the busiest market apps. Any numeric appid also works.
APP_ALIASES = {
    "cs2": 730,
    "csgo": 730,
    "counter-strike 2": 730,
    "dota2": 570,
    "dota 2": 570,
    "tf2": 440,
    "team fortress 2": 440,
    "rust": 252490,
    "pubg": 578080,
    "steam": 753,
    "banana": 2923300,
}

# Search sort: (sort, direction). Mapped empirically -- the numbers are not
# documented anywhere. sort 0/dir 0 is the default "popular" order.
SEARCH_SORTS = {
    "popular": (0, 0),
    "nameAsc": (1, 1),
    "nameDesc": (1, 0),
    "quantityDesc": (2, 0),
    "quantityAsc": (2, 1),
    "priceAsc": (3, 1),
    "priceDesc": (3, 0),
}

# Listing sort object for QueryListingsForItem. field 0 = price, field 1 = an
# asset property (assetpropertyid 2 = wear float, 1 = pattern seed);
# direction 0 = ascending (from the bundle's own label function).
LISTING_SORTS = {
    "priceAsc": {"field": 0, "direction": 0},
    "priceDesc": {"field": 0, "direction": 1},
    "floatAsc": {"field": 1, "direction": 0, "assetpropertyid": 2},
    "floatDesc": {"field": 1, "direction": 1, "assetpropertyid": 2},
    "patternAsc": {"field": 1, "direction": 0, "assetpropertyid": 1},
    "patternDesc": {"field": 1, "direction": 1, "assetpropertyid": 1},
}

# CS2 asset property schema (served to the page over protobuf WebAPI, so it is
# pinned here). Unknown ids fall back to ``property<id>``.
ASSET_PROPERTIES = {
    1: "paintSeed",  # "Pattern Template"
    2: "floatValue",  # "Wear Rating"
    3: "charmTemplate",
    4: "stickerWear",
    5: "nameTag",
    6: "itemCertificate",
    7: "finishCatalog",
}

# Steam ECurrencyCode. The market prices in the currency of the *exit IP's
# country*: cookies, ?cc=, ?currency= and extra RPC args are all ignored or
# rejected (400). The proxy country is therefore the currency switch.
CURRENCIES = {
    1: "USD", 2: "GBP", 3: "EUR", 4: "CHF", 5: "RUB", 6: "PLN", 7: "BRL",
    8: "JPY", 9: "NOK", 10: "IDR", 11: "MYR", 12: "PHP", 13: "SGD", 14: "THB",
    15: "VND", 16: "KRW", 17: "TRY", 18: "UAH", 19: "MXN", 20: "CAD", 21: "AUD",
    22: "NZD", 23: "CNY", 24: "INR", 25: "CLP", 26: "PEN", 27: "COP", 28: "ZAR",
    29: "HKD", 30: "TWD", 31: "SAR", 32: "AED", 34: "ARS", 35: "ILS", 37: "KZT",
    38: "KWD", 39: "QAR", 40: "CRC", 41: "UYU",
}

MODES = ["search", "itemOverview", "priceHistory", "orderBook", "listings", "recentSales"]
ITEM_MODES = {"itemOverview", "priceHistory", "orderBook", "listings"}
