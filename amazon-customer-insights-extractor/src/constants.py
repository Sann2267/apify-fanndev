"""Verified constants for the Amazon customer-insights extractor."""

DOMAINS = {
    "com": "https://www.amazon.com",
    "ca": "https://www.amazon.ca",
    "co.uk": "https://www.amazon.co.uk",
    "de": "https://www.amazon.de",
    "fr": "https://www.amazon.fr",
    "it": "https://www.amazon.it",
    "es": "https://www.amazon.es",
    "com.au": "https://www.amazon.com.au",
    "in": "https://www.amazon.in",
}

# Only .com and .ca were verifiable from the development IP; every other
# marketplace returned the bot wall on all 10 TLS profiles tried, which is an
# IP block rather than evidence the feature is absent. They are offered, but
# the README says plainly that they are unverified and want a
# country-matched residential proxy.
VERIFIED_MARKETPLACES = ("com", "ca")

MARKETPLACE_CURRENCY = {
    "com": "USD", "ca": "CAD", "co.uk": "GBP", "de": "EUR", "fr": "EUR",
    "it": "EUR", "es": "EUR", "com.au": "AUD", "in": "INR",
}

# Same /dp/ surface as the sibling Buy Box actor, so the same measured
# ladder applies. NOT the search ladder -- safari184 passes on search and
# fails here. A test asserts this list.
TLS_PROFILE_LADDER = ("chrome131", "chrome133a", "chrome150", "chrome136")

# The /dp/ block is an HTTP 200 of ~3.8 KB; a real product page is ~2.5 MB.
MIN_PRODUCT_PAGE_BYTES = 250_000

BLOCK_MARKERS = (
    "Click the button below to continue shopping",
    "Enter the characters you see below",
    "Sorry! Something went wrong",
    "api-services-support@amazon.com",
)

SENTIMENT_POSITIVE = "POSITIVE"
SENTIMENT_MIXED = "MIXED"
SENTIMENT_NEGATIVE = "NEGATIVE"

# Mixed and negative aspects are what a copywriter acts on: they mark the
# claims a listing fails to make convincingly.
GAP_SENTIMENTS = (SENTIMENT_MIXED, SENTIMENT_NEGATIVE)

# A product page that parses cleanly but carries no insight widget is
# ambiguous: Amazon serves a reduced page to some exit IPs. Above this many
# ratings, "no opinions published" stops being a credible reading and the
# exit IP is the likelier explanation -- verified on 0061120081, which
# returned 149,157 ratings and zero aspects on one residential exit and all
# 8 aspects on the next. Below it, few-reviews really is the usual answer.
INSIGHT_RETRY_MIN_REVIEWS = 100

RECORD_ASPECT = "ASPECT"
RECORD_PRODUCT = "PRODUCT_INSIGHT"
RECORD_DIAGNOSTIC = "CAPTCHA_ESCALATION"
