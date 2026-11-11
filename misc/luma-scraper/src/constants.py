"""Endpoints, headers -- all in one place.

Recon summary (2026-08-29): api.lu.ma is Luma's own internal API, used by
the luma.com/lu.ma web frontend itself for every logged-out visitor.
Cloudflare fronts the domain (luma.com's own HTML loads a
`window.__CF$cv$params` challenge-platform script, and every api.lu.ma
response sets a `__cf_bm` cookie), but no challenge was ever triggered --
every endpoint below returned a clean JSON 200 to a plain, unauthenticated
`curl` request with an ordinary Chrome user-agent, no TLS impersonation
ladder needed, no warmup request, no cookie jar carried between calls.
Confirmed across 15+ manual requests during recon (see CRAWLING_METHOD.md).

`/url?url=<slug>` is the single universal resolver the frontend itself
uses for every `lu.ma/<slug>` route -- it returns `{"kind": "event" |
"calendar", "data": {...}}`, and `data` for an event is byte-identical in
shape to `GET /event/get?event_api_id=<id>` (confirmed by diffing the SSR
`__NEXT_DATA__` payload of a live event page against a direct `/url`
call). This means a bare slug is enough for a single event/calendar
lookup -- no separate ID-resolution call is needed.

Two endpoints found in the frontend's own JS bundles
(`/search/get-results`, `/event/get-guest-list`) require an authenticated
session (HTTP 401 "You are not signed in.") even for fully public
events/calendars -- confirmed live, out of scope per this project's
"No Login" constraint, and not wired up in this actor.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://api.lu.ma"

DEFAULT_HEADERS = {
    "Accept": "application/json",
}

# Confirmed live via error-probing (guessed "upcoming" first -- rejected
# with a generic 400 "Invalid request." that does not list valid values;
# tried candidates one at a time until one worked). `/calendar/get-items`
# accepts `period=future` (also the default when the param is omitted
# entirely) or `period=past`. No other values were found in the frontend
# bundles.
PERIOD_VALUES = ["future", "past"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
