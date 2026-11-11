"""Endpoints, TLS profiles and tuning constants for the keyword suggester.

WAF profile (recon 2026-09-01, see CRAWLING_METHOD.md)
-----------------------------------------------------
Cloudflare, `Referer` mandatory, ladder leading with `safari17_0`. Sustained
traffic from one IP draws intermittent 403s that clear on retry with a
rotated fingerprint; this actor is request-heavy when expansion is on, so
residential proxy is recommended.

Blibli does not publish search volume
-------------------------------------
Measured, not assumed: across 65 autocomplete suggestions from 10 different
prefixes, **every** volume-shaped field came back null -- `productCount`,
`count` -- and `dsScore` was `0.0` on every single row. There is no search
volume, impression count or frequency anywhere in the payload.

So this actor never invents one. What it provides instead are two figures
that are actually measured:

* `competingProducts` -- how many products Blibli returns for the keyword
  (`paging.total_item` from the search API). Real, and the number that
  actually tells a merchant how hard a keyword is to rank for. Measured
  spread is wide and meaningful: "laptop" 58,744 vs "laptop gaming" 6,639.
* `suggestPosition` -- rank within Blibli's own autocomplete ordering, which
  is produced by their relevance model. An ordinal popularity signal, not a
  volume figure, and labelled as such.
"""

ORIGIN = "https://www.blibli.com"

# The autocomplete box. Note the parameter is `searchTermPrefix` -- the
# obvious `searchTerm` / `q` / `keyword` all return
# `400 Required request parameter 'searchTermPrefix' ... is not present`.
AUTOCOMPLETE_API = f"{ORIGIN}/backend/search/autocomplete"
# "Refine your search" terms shown on a results page -- a second, different
# keyword source that returns ~10 related terms per keyword.
REFINE_API = f"{ORIGIN}/backend/search/refineSearchKeyword"
# Marketplace-wide trending searches.
TRENDING_API = f"{ORIGIN}/backend/brs-api/trendingSearchTiles"
# Editorially curated promo keywords.
CURATED_API = f"{ORIGIN}/backend/search/curatedKeywords"
# Used only to count competing products for a keyword.
SEARCH_API = f"{ORIGIN}/backend/search/products"

SEARCH_URL = f"{ORIGIN}/cari/{{keyword}}"

TLS_PROFILE_LADDER = ("safari17_0", "firefox133", "edge101", "chrome99_android", "safari18_0")

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.5
REQUEST_TIMEOUT = 45

# Suffixes appended to a seed to pull more of the suggestion index out.
# Measured on "laptop": the bare seed yields 6 suggestions, while a-j alone
# lifted that to 67 unique keywords in 1.6s.
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"

EXPANSION_MODES = ("none", "alphabet", "alphanumeric", "related", "full")

# Buckets for `competitionLevel`, derived from the measured product count.
# Thresholds are a readability aid over `competingProducts`, not a Blibli
# metric -- the raw number is always present alongside.
COMPETITION_BANDS = (
    (1_000, "LOW"),
    (10_000, "MEDIUM"),
    (50_000, "HIGH"),
)
COMPETITION_TOP = "VERY_HIGH"

SOURCE_AUTOCOMPLETE = "autocomplete"
SOURCE_EXPANSION = "autocomplete-expansion"
SOURCE_RELATED = "related-search"
SOURCE_TRENDING = "trending"
SOURCE_CURATED = "curated"
