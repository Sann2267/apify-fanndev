"""Endpoints and section vocabulary for the ecommerce platform report Actor.

Source: the **public** platform reports published at ``storeleads.app/reports``
(110 platforms as of 2026-09-18: Shopify, WooCommerce, BigCommerce, Wix,
Squarespace, Magento, Shopware, PrestaShop, Cafe24, Base, Demandware ...).

What is public and what is not, verified 2026-09-18:

* ``/reports`` and ``/reports/<platform>`` -- **200**, fully server-rendered,
  no login. Each report carries ~16 sections including a 2019->today quarterly
  store-count series and the platform's migration flows.
* ``/domain/<store>``, ``/apps/<app>`` -- **404** for anonymous callers. The
  per-store database is a paid product behind an account, and this Actor does
  not touch it. The store names that *do* appear here are the ones the report
  itself publishes in its "Top stores" and "New stores" tables.

No WAF: no challenge, no cookie gate, no rate-limit page during recon.
"""

BASE = "https://storeleads.app"
URL_REPORT_INDEX = BASE + "/reports"
URL_REPORT = BASE + "/reports/{platform}"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

MODES = ("platform", "growth", "breakdown", "migration", "stores", "reference")

# Section id -> the dimension name used in BREAKDOWN records. Ids come from the
# report's own anchors, so a platform that omits a section simply produces no
# rows for it instead of failing.
BREAKDOWN_SECTIONS = {
    "socialmedia": "social-media",
    "contactinfo": "contact-info",
    "topcategories": "category",
    "topcountries": "country",
    "topapps": "app",
    "employees": "employee-count",
    "products": "product-count",
    "toptechnologies": "technology",
    "shipping": "shipping-carrier",
    "themes": "theme",
    "tlds": "tld",
}

STORE_SECTIONS = {
    "topstores": "top",
    "newstores": "new",
}

MIGRATION_SECTIONS = {
    # windomains = stores that switched TO this platform, lossdomains = away
    "windomains": "switched-in",
    "lossdomains": "switched-out",
}

GROWTH_SECTION = "growth"

# The report also embeds the same numbers as JS arrays. They carry machine
# codes the visible table drops -- e.g. countryData has "US" next to "United
# States" -- so they are parsed as an enrichment, not as the primary source.
JS_VAR_DIMENSIONS = {
    "countryData": "country",
    "categoryData": "category",
    "themeData": "theme",
    "tldData": "tld",
    "employeeCountData": "employee-count",
    "productCountData": "product-count",
    "attritionData": "switched-out",
    "winsData": "switched-in",
    "createdAtData": "growth",
}
