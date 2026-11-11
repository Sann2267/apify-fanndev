"""Endpoints, TLS profile and enum vocabularies for the Chiliz/Socios API.

Everything here was verified open and unauthenticated on 2026-09-20.

Surface notes
-------------
``www.socios.com`` is a WordPress marketing site (Yoast/WP-Rocket/WPML) whose
REST API is closed -- ``/wp-json/`` answers 401 ``socios_rc_rest_authentication
_required`` on every route. The real product lives at ``app.socios.com``, a
Next.js App Router application whose routes all sit under an ``(authenticated)``
group, and it talks to the Kong gateway at ``api.chiliz.com``.

That gateway applies an ACL per route rather than a blanket auth check, and a
useful slice of it answers an anonymous caller: the fan vote catalogue, the
partner (club) directory, the currency/fan-token catalogue and the reference
tables below. The rest -- marketplace prices, the fan shop, collectibles,
leaderboards, pledge campaigns, token quests, fan token offerings and anything
under ``/me`` -- answers ``403 {"message": "You cannot consume this service"}``.
That 403 is an ACL verdict, not a WAF block: it is instant, identical from every
IP and every TLS profile, and ``POST /front/session/auth-token`` (the endpoint
that would widen the anonymous role) is itself behind the same 403. There is no
HTTP-only path to those routes, so this actor does not pretend to offer them.
"""

from __future__ import annotations

BASE_URL = "https://api.chiliz.com"
ACL = f"{BASE_URL}/api/acl-service"

SURVEYS_URL = f"{ACL}/v1/front/surveys"
PARTNERS_URL = f"{ACL}/v1/front/partners"
CURRENCIES_URL = f"{ACL}/v2/front/currencies"
VOTE_TOKENS_URL = f"{ACL}/v1/front/vote-token/vote-tokens"
LEAGUES_URL = f"{ACL}/v1/front/leagues"
SPORTS_URL = f"{ACL}/v1/front/sports"
COUNTRIES_URL = f"{ACL}/v1/front/countries"
HEALTH_URL = f"{ACL}/v1/front/maintenance/status"

# Cloudflare fronts api.chiliz.com but runs no challenge on it. The full ladder
# -- chrome124, chrome131, chrome136, safari17_0, firefox133, edge101 and
# chrome99_android -- returned a byte-identical 200 on the same IP, so this
# choice is about blending in with app.socios.com's real traffic rather than
# about getting through anything. Rotation on block would be theatre here: the
# only 403 this API emits is the ACL verdict, which no fingerprint changes.
TLS_PROFILE = "chrome131"

# The gateway does not inspect these, but app.socios.com sends them on every
# call and an API that suddenly sees requests without them is an API whose
# owners start looking. Accept-Encoding and the UA come from impersonate=.
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://app.socios.com",
    "Referer": "https://app.socios.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# The gateway accepts limit up to 1000 ("This value should be less than or
# equal to 1000." above that), but a 1000-row page of polls serialises to 5-8 MB
# and the gateway itself then answers 500 on the heavier ones -- page 7 of the
# poll catalogue fails identically on every attempt, from every IP. 250 keeps a
# page near 3 MB, and all 40 pages of the catalogue return 200 at that size.
# Requests cost nothing here, so the smaller page is strictly the better trade.
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 250

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_DELAY = 0.15

# Sending status[]=zzz makes the gateway list its choices in a 400 -- but that
# list is of PHP enum constant names (SCHEDULED, CLOSED_PENDING, ...), not of
# the values the parameter accepts. Every one of those is rejected verbatim.
# The values that actually work are lower-case, with hyphens where the constant
# has underscores, and they are what the payload echoes back. Row counts below
# were measured on 2026-09-20 against a catalogue of 9,825 polls.
POLL_STATUSES = [
    "closed",                       # 8,119 -- settled, with final results
    "cancelled",                    # 1,686
    "error",                        #    13
    "suspended",                    #     5
    "opened",                       #     1 -- live right now
    "cancelling",                   #     1
    "scheduled",                    #     0
    "created",                      #     0
    "processing",                   #     0
    "closed-pending",               #     0
    "closed-release-wallet-limit",  #     0
    "closed-blockchain-pending",    #     0
]

# Observed over the catalogue: engagement is the bulk, integrity roughly a
# quarter, prediction rare. The API accepts type[] without complaining and then
# ignores it, so this filter is applied client-side -- see the decoy note in
# client.py.
POLL_TYPES = ["engagement", "integrity", "prediction"]

# orderBy rejects anything outside this set with an explicit 400. There is no
# direction parameter: sortOrder, direction, order and sort are all accepted
# and ignored, and what comes back is descending.
POLL_ORDER_BY = ["createdAt", "openAt", "closeAt", "publicationDate", "status"]

MODES = ["polls", "partners", "fanTokens", "voteTokens", "reference", "all"]
