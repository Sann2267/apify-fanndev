"""Surfaces, yields and the two hosts that disagree about how to write a date.

Source: ESPN's public sports APIs. Nothing here needs a cookie, a key or a
login, and no WAF answered during recon (2026-09-18, plain HTTP from a
residential IP and from Apify datacenter both reached 200).

**Two hosts, two contracts.** This matters more than anything else in the file.

``sports.core.api.espn.com`` (CORE) is the only host that publishes **betting
lines**. It is a HATEOAS API: list endpoints return ``{"$ref": ...}`` pointers,
not objects, so every list costs one extra request per item you actually want.

``site.api.espn.com`` (SITE) returns whole objects in one shot -- a scoreboard
is 16 full NFL events in 276 KB -- but ``competition.odds`` on it is **null**.
It is the cheap path for schedules and the wrong path for odds.

Measured yields, 2026-09-18:

| Surface | Result |
| --- | --- |
| CORE ``/events?dates=2026`` (NFL) | 320 event refs, one page |
| CORE ``/events`` (no ``dates``) | **16** -- the current week only |
| CORE ``.../odds`` (NFL, game day) | 2 providers (Draft Kings, DK Live Odds) |
| CORE ``.../odds/<p>/propBets?limit=1000`` | **659 player props**, one page, 47 distinct athletes |
| CORE ``/seasons/2026/futures`` | 18 markets, 543 book lines (MVP, Super Bowl, divisions) |
| CORE ``.../predictor`` | ESPN BPI win projection per side |
| SITE ``/scoreboard`` | 16 full events, ``odds`` **null** |
| SITE ``/teams`` | all 32 teams inline, one request -- the team-name cache |

**Date grammar is not shared between the hosts.** CORE accepts
``dates=20260920``, ``dates=2026`` *and* the range ``dates=20260901-20261001``
(49 events). SITE accepts the first two and **rejects the range**: NFL answers
HTTP 400, and English Premier League answers **200 with zero events** -- a
silent wrong answer, which is why every date window in this Actor is resolved
on CORE. See ``CRAWLING_METHOD.md`` gotcha 1.

**``$ref`` pointers are not always fetchable as printed.** They are written
with the ``http://`` scheme, and the ones embedded in SITE's
``summary?event=`` response point at ``sports.core.api.espn.pvt`` -- ESPN's
internal hostname, which does not resolve. In that one response 436 of 436
pointers carry ``.pvt`` and none carry the public host, so an Actor that
followed them verbatim would fail on every single one. ``normalize_ref()``
rewrites both.

**An empty odds list is an answer, not a failure.** Books post lines close to
kick-off: NFL and MLB fixtures on the day returned providers, while NBA and NHL
fixtures six weeks out returned ``count: 0`` over HTTP 200. Records for those
say ``hasOdds: false`` rather than going missing, so a caller can tell "not
priced yet" from "we could not fetch it".
"""

CORE_BASE = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}"
CORE_SPORTS = "https://sports.core.api.espn.com/v2/sports?limit=50"
CORE_LEAGUES = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues?limit=300"
SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}"

MODES = ("odds", "props", "futures", "events", "predictor", "providers", "reference")

# Friendly keys -> ESPN's own (sport, league) pair. Anything not listed can be
# passed through as "sport/league" (e.g. "soccer/ned.1"); all 219 soccer
# competitions and 17 sports are reachable that way, and mode "providers"
# prints the catalogue.
LEAGUES = {
    "nfl": ("football", "nfl"),
    "college-football": ("football", "college-football"),
    "nba": ("basketball", "nba"),
    "wnba": ("basketball", "wnba"),
    "ncaab": ("basketball", "mens-college-basketball"),
    "ncaaw": ("basketball", "womens-college-basketball"),
    "mlb": ("baseball", "mlb"),
    "nhl": ("hockey", "nhl"),
    "epl": ("soccer", "eng.1"),
    "laliga": ("soccer", "esp.1"),
    "seriea": ("soccer", "ita.1"),
    "bundesliga": ("soccer", "ger.1"),
    "ligue1": ("soccer", "fra.1"),
    "ucl": ("soccer", "uefa.champions"),
    "mls": ("soccer", "usa.1"),
    "ufc": ("mma", "ufc"),
    "pga": ("golf", "pga"),
    "atp": ("tennis", "atp"),
    "wta": ("tennis", "wta"),
    "f1": ("racing", "f1"),
}

# Leagues confirmed to carry betting lines during recon. Used only to warn --
# never to refuse -- because coverage follows the season, not the league.
LEAGUES_WITH_ODDS_SEEN = ("nfl", "college-football", "mlb", "epl", "mls", "ufc")

TLS_LADDER = ("chrome124", "firefox133", "safari17_0", "chrome99_android", "edge101")

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.5

# propBets pages at whatever `limit` you send: limit=3 reported pageCount 220
# for one game. 1000 returns all 659 in a single response.
PAGE_LIMIT = 1000

# How many `$ref` lookups a run may spend turning ids into names. 659 props
# resolve from 47 distinct athletes, so the cache does most of the work; futures
# are the expensive case at ~360 distinct refs per league.
DEFAULT_REF_BUDGET = 400

EXPECTED = {
    "nflEventsInSeason": 320,
    "nflPropsPerGame": 659,
    "nflPropAthletes": 47,
    "nflFuturesMarkets": 18,
    "providersInCatalogue": 71,
}
