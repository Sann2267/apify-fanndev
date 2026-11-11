"""Endpoints, TLS profiles and tuning constants for Amazon ad monitoring.

Access profile (recon 2026-09-01, see CRAWLING_METHOD.md)
--------------------------------------------------------
Amazon **search** is defended far more tightly than its Best Sellers pages,
and the difference is a specific JA3 allowlist rather than rate limiting.
Measured on `/s?k=`:

    chrome131   200      chrome142   503        firefox135  503
    chrome133a  200      chrome145   503        firefox144  503
    chrome136   200      chrome146   503        safari180   503
    chrome150   200      chrome124   503 (4/4)  safari260   503
    safari184   200      chrome123   503        tor145      503

The failures are Amazon's "Sorry! Something went wrong!" page -- a constant
2,671-byte body, returned consistently rather than intermittently, so it is
a fingerprint block and not a throttle. Notably it is **not** "newest wins":
chrome142/145/146 fail while chrome131/133a/136/150 pass.

Only the five verified-good profiles are in the ladder below. Adding an
untested profile will silently halve the success rate, so re-run the ladder
before touching this list.

Currency
--------
Amazon prices the page from the request's geo-IP: from an Indonesian egress
the same search returned `IDR 336,939.57`. Sending the **`i18n-prefs`
cookie** forces the marketplace currency regardless of egress IP -- verified
flipping IDR to `$19.99` on an otherwise identical request. That cookie is
always sent, so prices are comparable no matter where the actor runs.

Ad density is genuinely variable
--------------------------------
Sponsored placements are auctioned per impression. Measured across seven
keywords in one session: 0%, 0%, 2.1%, 2.1%, 6.2%, 6.2%, 21.7% -- 17 of 252
page-one slots overall. **Zero sponsored results for a keyword is a normal
outcome, not a failure**, which is why the actor supports sampling a keyword
several times and always emits a summary row even when nothing was
sponsored.
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

# Currency forced per marketplace via the `i18n-prefs` cookie.
CURRENCIES = {
    "com": "USD", "co.uk": "GBP", "de": "EUR", "fr": "EUR", "it": "EUR",
    "es": "EUR", "ca": "CAD", "com.au": "AUD", "co.jp": "JPY", "in": "INR",
}

LOCALES = {
    "com": "en_US", "co.uk": "en_GB", "de": "de_DE", "fr": "fr_FR", "it": "it_IT",
    "es": "es_ES", "ca": "en_CA", "com.au": "en_AU", "co.jp": "ja_JP", "in": "en_IN",
}

# ONLY profiles verified to clear Amazon search. See the module docstring.
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

# Ad slot bands, from the observed layout (a typical sponsored block sits at
# positions 1-4, another around 11-14).
SLOT_TOP = 4
SLOT_MID = 20

RECORD_AD = "SPONSORED_AD"
RECORD_ORGANIC = "ORGANIC"
RECORD_SUMMARY = "KEYWORD_SUMMARY"
