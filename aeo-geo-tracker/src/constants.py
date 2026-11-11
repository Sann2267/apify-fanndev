"""Endpoints, headers, constants -- all in one place.

## What this actor is

"AEO/GEO Tracker" (Answer-Engine-Optimization / Generative-Engine-
Optimization tracking) is a marketing-tooling category, not a single
website — it answers "does my brand/domain show up when someone asks an
answer engine about my product category?" Three candidate answer
surfaces were investigated for this actor; only one, Bing's organic
search results, was HTTP-only reachable end to end without requiring
real JavaScript execution. The other two were thoroughly investigated
and conclusively ruled out -- see CRAWLING_METHOD.md for the full
evidence trail on each:

- **Google AI Overview**: even via Apify's RESIDENTIAL proxy (which
  clears Google's CAPTCHA), the response body is an explicit
  `<noscript>` "JavaScript required" gate with zero server-rendered
  result content of any kind -- not just no AI Overview, no organic
  results either. Confirmed invariant across 7 build/test iterations,
  two opposite header/fingerprint strategies, and 3 different proxy
  configurations.
- **DuckDuckGo AI Chat**: the well-documented anonymous `x-vqd-4`
  session-token handshake used by many open-source wrappers has been
  replaced (as of this recon) with an `x-vqd-hash-1` proof-of-work-style
  JS challenge. The challenge script itself contains no DOM references
  (confirmed by decoding and scanning it for `document.`/`window.`/
  `navigator.` etc.) so it's theoretically solvable with a lightweight
  JS engine rather than a full browser -- but the wire protocol for
  submitting the computed result back is undocumented and very recent,
  and reverse-engineering it blind (with no real client to observe)
  was judged out of scope for this build.

## Bing organic SERP -- fully verified, no proxy needed

`www.bing.com/search?q=<query>` -- clean 200, no CAPTCHA, confirmed
across many queries with a plain `curl_cffi` `chrome124` session and no
proxy, both locally and via `apify call` on the deployed Actor.

**Real, mapped anti-bot behavior (not a header/token gap):** a query
whose FIRST WORD is a bare superlative ("best ...", "top ...") returns
a completely irrelevant decoy result set (e.g. "best crm software for
small business" returned only pages about the standalone word "best" --
a Cambridge Dictionary definition, BestBuy, an Indonesian electronics
retailer named "Best Indonesia") while the page's own `<title>` tag
correctly echoes the full query -- a clear sign the title and the body
content are computed via different paths that diverge for this query
shape. Confirmed reproducible across 3 separate "best X for Y" / "top X"
queries, and confirmed FIXED by rephrasing the exact same intent as a
natural question instead: "which crm software is best for small
business" and "crm software for small business" (dropping the leading
superlative) both returned genuinely relevant results (Salesforce, IBM,
real CRM comparison pages). **This actor requires/encourages
natural-question phrasing for exactly this reason** -- not a stylistic
preference, a measured anti-bot workaround. See CRAWLING_METHOD.md.

**Also confirmed:** `count` (10/30/50) and page-2 pagination (`first=11`
combined with the real session `FPIG` token scraped from the next-page
link -- not a guess, extracted from actual page-1 HTML) both return the
exact same 10 results as page 1, every time. This actor caps at the
first 10 organic results per query and does not claim to paginate
further.
"""

TLS_PROFILE = "chrome124"

BING_SEARCH_URL = "https://www.bing.com/search"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
