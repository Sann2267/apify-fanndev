"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-08-26): poshmark.com is a Vue 2 SSR app. Every page
embeds a `window.__INITIAL_STATE__={...};` JSON blob (Vuex store
hydration -- same family of pattern as Next.js `__NEXT_DATA__` or
Nuxt's `__NUXT__`) carrying the full page data server-side; no separate
JSON API call is needed once that blob is parsed. `curl_cffi`
`chrome124` gets clean 200s everywhere tested, no WAF/CAPTCHA of any
kind -- the only anti-bot-adjacent signal is a Sift Science
fraud-detection tracking cookie (`esid=sift:...`) set passively on every
response, which does not block or challenge anything.

**robots.txt is the load-bearing constraint for this actor's
architecture**, not a WAF: `Disallow: /search` is a blanket rule under
`User-agent: *` (no per-bot carve-out), so this actor does NOT use
`poshmark.com/search` at all, despite it being the most obvious
"keyword search" endpoint and the one initially prototyped during recon.
`/listing/<id>` and `/closet/<username>` are NOT disallowed. Two
alternate, equally rich, NOT-disallowed discovery surfaces were found
and verified to return correctly filtered results (unlike guessed query
params on `/search`, e.g. `?brand=Nike` on `/search` silently returns
unfiltered mixed-brand results -- confirmed NOT working -- while
`/brand/Nike` as its own dedicated path correctly returns 100% Nike
items):

- `poshmark.com/brand/<Brand-Name>` -- browse by brand
- `poshmark.com/category/<Department>-<Category>` -- browse by category

Both carry the identical `gridData`/`more`/`next_max_id` pagination
shape as the (unused) search page did, and both honor a `sort_by` query
param (confirmed live: `sort_by=price_asc` on `/category/Women-Dresses`
returned genuinely ascending-priced items). See CRAWLING_METHOD.md.

Bing... er, Poshmark's own listing IDs are 24-char hex Mongo-style
ObjectIds. The URL slug preceding the ID is cosmetic and ignored
server-side -- confirmed live: `poshmark.com/listing/x-<id>` (a
deliberately wrong slug) 200s and redirects to the real canonical URL.
This means `listing` mode can accept a bare ID with no need to know or
guess the real slug.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://poshmark.com"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Confirmed working live (ascending-price ordering verified against real
# sampled prices). Not exhaustively enumerable -- Poshmark's `sort_by`
# does not error on an invalid value (unlike Civitai/Hugging Face's
# strict Zod validation elsewhere in this portfolio), it silently falls
# back to the default, so only empirically-confirmed values are
# whitelisted here rather than guessed.
SORT_BY_VALUES = ["added_desc", "price_asc", "price_desc", "like_count", "relevance"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
