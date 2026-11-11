"""Verified constants for the Amazon product / search-results scraper.

The TLS ladder and block signature here are the Amazon SEARCH ones, measured
for the sibling sponsored-ads actor and re-confirmed for this build. They are
NOT the same as the /dp/ product-page ladder used by the ASIN actors --
safari184 clears search but is rejected on /dp/.
"""

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

# Currency forced per marketplace via the `i18n-prefs` cookie. Without it
# Amazon prices from the egress IP -- an Indonesian exit returns IDR on
# amazon.com, which silently corrupts any price-distribution analysis.
CURRENCIES = {
    "com": "USD", "co.uk": "GBP", "de": "EUR", "fr": "EUR", "it": "EUR",
    "es": "EUR", "ca": "CAD", "com.au": "AUD", "co.jp": "JPY", "in": "INR",
}

LOCALES = {
    "com": "en_US", "co.uk": "en_GB", "de": "de_DE", "fr": "fr_FR", "it": "it_IT",
    "es": "es_ES", "ca": "en_CA", "com.au": "en_AU", "co.jp": "ja_JP", "in": "en_IN",
}

# ONLY the five profiles verified to clear Amazon search. chrome142/145/146
# and every firefox/tor profile return the block page consistently, so this
# is not "newest wins" -- a test asserts the list.
TLS_PROFILE_LADDER = ("chrome131", "chrome133a", "chrome136", "chrome150", "safari184")

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

MAX_RETRIES = 6
RETRY_DELAY_BASE = 2.0
REQUEST_TIMEOUT = 45
DEFAULT_DELAY_SECONDS = 3.0

# A page is only trusted above this size; Amazon's block page is ~2.7 KB.
MIN_PAGE_BYTES = 200_000

# Measured: page 7 was the last page carrying a "next" link for a broad
# query, and pages beyond it degrade to a short filler result set. Requests
# past the real end are wasted money, so the actor stops when a page reports
# no next link.
MAX_PAGES = 7

RECORD_PRODUCT = "PRODUCT"
RECORD_DIAGNOSTIC = "CAPTCHA_ESCALATION"
