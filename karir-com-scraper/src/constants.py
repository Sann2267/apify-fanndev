"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-08-26): karir.com is an Indonesian job board built on
Next.js (client-rendered -- the SSR HTML for `/search-lowongan` and city
pages like `/lowongan-kerja-jakarta` carries no page data, just an empty
`__NEXT_DATA__` shell). All real data comes from a public JSON REST API on
a separate host, `gateway2-beta.karir.com` (reverse-engineered from the
webpack chunk that defines the site's axios client + endpoint map --
`s.H.search = "v2/search/opportunities"`, `s.H.opportunity =
"v1/opportunity/detail"`). No API key, session cookie, or Authorization
header of any kind is required or sent by the site's own frontend for
these two endpoints -- confirmed live with a bare `curl_cffi` POST and no
auth headers at all.

No WAF of any kind was found on `karir.com` or `gateway2-beta.karir.com`
during recon -- no Cloudflare/DataDome/PerimeterX challenge, no `cf-ray`
header, clean 200s on every profile tried. `curl_cffi chrome124` is used
per portfolio convention; retry/backoff scaffolding is kept even though
no blocking was observed.

`robots.txt` (`https://karir.com/robots.txt`) is a single flat
`User-agent: *` group with `Crawl-delay: 1` and disallows only some
legacy paths (`/karir/`, `/jobs/`, `/klasika/`, `/php/` -- all commented
"# Old site", unrelated to the current Next.js frontend) plus ONE
specific listing, `/opportunities/1061574`. Everything this actor uses
-- `/opportunities/<id>` in general, and the `gateway2-beta.karir.com`
API host (which has no robots.txt of its own -- 404) -- is not
disallowed. `DISALLOWED_OPPORTUNITY_IDS` below is honored defensively:
if a search result or direct input ever resolves to that one ID, it is
skipped rather than fetched, out of respect for that explicit exclusion.
"""

TLS_PROFILE = "chrome124"

SITE_BASE = "https://karir.com"
API_BASE = "https://gateway2-beta.karir.com"

SEARCH_URL = f"{API_BASE}/v2/search/opportunities"
DETAIL_URL = f"{API_BASE}/v1/opportunity/detail"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# The API's own page size cap -- confirmed live: requesting limit=50 or
# limit=100 still only returns 20 items/page. Larger values are silently
# clamped, not rejected, so this actor always requests the max (20) and
# paginates via `offset` rather than guessing a bigger number works.
PAGE_SIZE = 20

# Confirmed live: "Terbaru"/"Prioritas"/"Paling Populer"/"Gaji Tertinggi"
# in the site's own sort dropdown map to these values (found in the
# search-lowongan page's webpack chunk). An invalid/unrecognized value is
# silently ignored by the API (falls back to default order) rather than
# erroring, so only empirically-confirmed values are exposed here.
SORT_ORDER_VALUES = ["newest", "priority", "popular", "highest_salary"]

# robots.txt explicitly disallows this one opportunity ID (unrelated to
# the "# Old site" legacy-path group above) -- honored defensively.
DISALLOWED_OPPORTUNITY_IDS = {"1061574"}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
