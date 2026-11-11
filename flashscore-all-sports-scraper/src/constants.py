"""Endpoints, sport map, headers -- all in one place.

Recon summary (2026-09-08). Flashscore's website is a JS app: the HTML at
`flashscore.com` is ~740 KB of shell + bundles and carries **no** match rows.
All data comes from a separate feed host,

    https://local-global.flashscore.ninja/2/x/feed/<feed-id>

which answers plain HTTP GETs -- no login, no cookie, no warm-up, no
challenge -- **as long as the request carries the static header
`x-fsign: SW9D1eZo`**. Without that header the same URL returns HTTP 401
with a 323-byte body (verified both ways during recon). That header value
is a constant embedded in Flashscore's own bundle, not a per-session token:
the same value works across sports, days and match IDs.

Response format is Flashscore's own delimited encoding, not JSON:

    <record> ~ <record> ~ ...            records separated by "~"
    <key>÷<value> ¬ <key>÷<value> ...    fields separated by "¬", kv by "÷"

Tournament headers (`ZA` = "COUNTRY: League") come *before* the matches they
contain, so the parser carries the last header forward as context -- there is
no tournament id on the match rows themselves.

Field mapping below was derived empirically from live feeds (see
CRAWLING_METHOD.md for the exact evidence, including which keys appear on
>90% of rows and which only appear once a match has started). Keys that were
NOT positively identified are deliberately left in the record untouched
rather than renamed or dropped.

Sport IDs were enumerated by probing `f_<id>_0_3_en_1` for ids 1-21 and
reading back the tournaments each one returned (e.g. id 10 returned
"SWEDEN: Svenska Cupen" with Broberg/Soderhamn and Sandviken = bandy;
id 11 returned Belgian Division 1 with Eisden-Dorp = futsal). IDs 8, 9,
16-20 answered 200 with an empty body on the probe day and are therefore
NOT claimed here -- `reference` mode reports what is live today instead of
trusting this table.
"""

TLS_PROFILE = "chrome131"

FEED_BASE = "https://local-global.flashscore.ninja/2/x/feed/"
SITE_BASE = "https://www.flashscore.com"

# Static bundle constant, not a session token -- see module docstring.
FSIGN = "SW9D1eZo"

DEFAULT_HEADERS = {
    "x-fsign": FSIGN,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.flashscore.com/",
    "Origin": "https://www.flashscore.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

# Day feed: f_<sportId>_<dayOffset>_<mode>_<lang>_1
#   dayOffset 0 = today, -1 = yesterday, 1 = tomorrow (upstream serves roughly -7..+7)
#   mode 3 = all matches of that day, mode 1 = live only
EP_DAY = "f_{sport}_{day}_3_en_1"
EP_LIVE = "f_{sport}_0_1_en_1"

# Detail feeds. The numeric segment after the prefix LOOKS like a sport id and
# Flashscore's own site sends the match's real sport there -- but it is
# **ignored by the server**: the same football match id fetched with sport 1,
# 2, 3 and even 99 returned byte-identical bodies (234 B / 2.800 B / 5.030 B /
# 15.116 B respectively per feed), and a tennis match fetched with sport=1
# returned its tennis stats unchanged. The match id alone selects the data.
# It is kept in the URL for fidelity with the real client, and the actor's
# `sportIds[0]` is used only to LABEL the output record -- never to select it.
EP_DETAIL = "dc_{sport}_{match}_1"       # meta: kickoff, finished-at, stage flags
EP_SUMMARY = "df_sui_{sport}_{match}_1"  # incidents: goals, cards, subs, minute + player
EP_STATS = "df_st_{sport}_{match}_1"     # statistics incl. expected goals (xG), possession
EP_LINEUPS = "df_li_{sport}_{match}_1"   # formations, starting XI, bench, player ratings
EP_H2H = "df_hh_{sport}_{match}_1"       # head-to-head + recent form for both teams

MATCH_URL = SITE_BASE + "/match/{match}/"

MODES = ("fixtures", "live", "match", "reference")

# Verified by probing each id and reading back the tournaments/competitors it
# returned on 2026-09-08. Not an exhaustive list of Flashscore's sports --
# only the ids that actually served data. `reference` mode re-checks live.
SPORTS = {
    1: "Football",
    2: "Tennis",
    3: "Basketball",
    4: "Ice Hockey",
    5: "American Football",
    6: "Baseball",
    7: "Handball",
    10: "Bandy",
    11: "Futsal",
    12: "Volleyball",
    13: "Cricket",
    14: "Darts",
    15: "Snooker",
    21: "Badminton",
}
PROBE_SPORT_IDS = tuple(range(1, 22))

# AB is the coarse status and is present on >90% of rows; AC is a
# finer-grained code whose full enumeration is NOT documented upstream and was
# NOT fully observed (values seen: 1, 3, 4, 11, 12, 13, 38, 45). AC is passed
# through as `statusCode` untouched; only AB is mapped to a name.
STATUS_BY_AB = {"1": "SCHEDULED", "2": "LIVE", "3": "FINISHED"}

# Winner code, present only once a match is decided.
WINNER_BY_AS = {"0": "DRAW", "1": "HOME", "2": "AWAY"}

# Positively identified match keys -> friendly derived names. Everything not
# listed here still ships in the record under its original key.
MATCH_FIELDS = {
    "AA": "matchId",
    "AD": "startTimestamp",
    "AB": "_statusRaw",
    "AC": "statusCode",
    "AE": "homeTeam",
    "AF": "awayTeam",
    "AG": "homeScore",
    "AH": "awayScore",
    "AS": "_winnerRaw",
    "JA": "homeTeamId",
    "JB": "awayTeamId",
    "WU": "homeTeamSlug",
    "WV": "awayTeamSlug",
    "WM": "homeTeamCode",
    "WN": "awayTeamCode",
    "OA": "homeTeamImage",
    "OB": "awayTeamImage",
    "AO": "finishedAtTimestamp",
}

TOURNAMENT_FIELDS = {
    "ZA": "tournament",
    "ZY": "country",
    "ZEE": "tournamentId",
    "ZC": "tournamentStageId",
    "ZB": "countryId",
}

MAX_DAY_OFFSET = 7
