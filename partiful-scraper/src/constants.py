"""Endpoints, headers -- all in one place.

Recon summary (2026-08-30): partiful.com is a Next.js app hosted on
Vercel. No WAF challenge was ever triggered during recon -- every page
used here (event, host profile, discover) returned a clean 200 to a
plain curl_cffi request with an ordinary Chrome impersonation profile,
no warmup request, and no cookie jar carried between calls. See
CRAWLING_METHOD.md for the full recon writeup.

Every page ships its full server-rendered data inline in a
`<script id="__NEXT_DATA__" type="application/json">` tag -- the same
blob Next.js hydrates the React app from client-side. This is the
highest-priority data source per .ai/CLAUDE.md's extraction ladder
(JSON-LD > __NEXT_DATA__ > Apollo state > HTML scraping), so no HTML
CSS-selector scraping or authenticated API calls are needed for any of
this actor's 3 modes.

Two classes of Partiful surface were found and are deliberately NOT
used: (1) the authenticated Firebase Cloud Functions API
(`us-central1-getpartiful.cloudfunctions.net`) that Partiful's own
mobile/web app uses for guest lists, invitable-contacts, and mutuals --
confirmed via the public github.com/cerebralvalley/partiful-api project,
which requires a manually-extracted, expiring browser Bearer token for
every one of those calls; (2) a public guest list on the event page
itself -- `event.showGuestList` is often `true` but no guest array is
ever present in the SSR payload, meaning Partiful renders it client-side
only after an authenticated call. Both are out of scope per this
project's no-login constraint.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://partiful.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
}

# The only 3 editorial regions found on the public /discover feed as of
# recon date -- no query params were found to request a different set or
# more regions (see CRAWLING_METHOD.md). Documented so a future
# guessed-region miss isn't re-investigated from scratch.
DISCOVER_REGIONS = ["NYC", "LA", "SF"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
