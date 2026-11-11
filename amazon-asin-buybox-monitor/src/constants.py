"""Verified constants for the Amazon ASIN lookup / Buy Box monitor."""

DOMAINS = {
    "com": "https://www.amazon.com",
    "co.uk": "https://www.amazon.co.uk",
    "de": "https://www.amazon.de",
    "fr": "https://www.amazon.fr",
    "it": "https://www.amazon.it",
    "es": "https://www.amazon.es",
    "ca": "https://www.amazon.ca",
    "com.au": "https://www.amazon.com.au",
    "co.jp": "https://www.amazon.co.jp",
    "in": "https://www.amazon.in",
}

# Currency forced per marketplace via the i18n-prefs cookie. Without it
# Amazon prices from the egress IP -- an Indonesian exit returned
# "IDR 336,939.57" for a $19.99 item, which would silently corrupt any
# price comparison across runs or proxies.
MARKETPLACE_CURRENCY = {
    "com": "USD", "co.uk": "GBP", "de": "EUR", "fr": "EUR", "it": "EUR",
    "es": "EUR", "ca": "CAD", "com.au": "AUD", "co.jp": "JPY", "in": "INR",
}

# MEASURED against /dp/ specifically -- this is a THIRD ladder, different
# from both the Best Sellers actor (which accepted everything) and the
# Sponsored Ads actor (search). Verified across 3 ASINs x repeated attempts:
#   chrome131 3/3, chrome133a 3/3, chrome150 3/3, chrome136 2/3
# Rejected here even though they work on other Amazon surfaces:
#   safari184 (works on search, fails on /dp/), safari17_0 (flaky 0/3),
#   safari180, chrome142, chrome146 (1/3).
# A test asserts this list so a well-meaning "tidy-up" cannot silently
# halve the success rate.
TLS_PROFILE_LADDER = ("chrome131", "chrome133a", "chrome150", "chrome136")

# The /dp/ block is an HTTP *200* soft wall of ~3.8 KB reading "Click the
# button below to continue shopping" -- NOT the 503 the search surface
# returns. Status code alone cannot detect it; a real product page is
# megabytes, so size is the reliable discriminator.
MIN_PRODUCT_PAGE_BYTES = 250_000

BLOCK_MARKERS = (
    "Click the button below to continue shopping",
    "Enter the characters you see below",
    "Sorry! Something went wrong",
    "api-services-support@amazon.com",
)

# Amazon's own retail merchant id, constant across marketplaces. Lets the
# actor state "sold by Amazon" definitively rather than guessing from text.
AMAZON_MERCHANT_ID = "ATVPDKIKX0DER"

RECORD_PRODUCT = "PRODUCT"
RECORD_DIAGNOSTIC = "CAPTCHA_ESCALATION"

# Change-detection verdicts, mirroring the dropshipper-sync actor so the
# two are directly comparable downstream.
CHANGE_NEW = "NEW"
CHANGE_UNCHANGED = "UNCHANGED"
CHANGE_PRICE_UP = "PRICE_INCREASED"
CHANGE_PRICE_DOWN = "PRICE_DECREASED"
CHANGE_BUYBOX_FLIP = "BUYBOX_SELLER_CHANGED"
CHANGE_BACK_IN_STOCK = "BACK_IN_STOCK"
CHANGE_OUT_OF_STOCK = "OUT_OF_STOCK"

DEFAULT_SNAPSHOT_STORE = "amazon-buybox-snapshots"
