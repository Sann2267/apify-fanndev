"""Fixed facts about Discord's public surface, established by recon 2026-09-21.

This actor never signs in, never carries a user token, and never opens a
gateway socket. Everything below is served to an anonymous client. That rules
out message history, member lists and ticket transcripts -- those need a bot
token that has been invited to the server, which is a per-buyer credential and
not something a scraper can supply. What IS open turns out to be the part with
commercial value: the whole Server Discovery index, every invite's live member
and online counts, and the weekly trending-games chart.

SURFACES THAT ARE OPEN (all verified anonymously, 12 TLS profiles each)
----------------------------------------------------------------------
1. `GET /api/v10/invites/{code}?with_counts=true&with_expiration=true`
   The universal resolver. Works for ANY invite -- vanity (`discord.gg/python`)
   or random (`discord.gg/B9qbPSzX`) -- and for servers that are NOT in
   Discovery at all, which is most of them. Returns guild id, name,
   description, features, verification_level, nsfw flags, vanity_url_code,
   premium_subscription_count (boosts), premium_tier, the landing channel, the
   server tag/badge, and the two numbers this actor exists for:
   approximate_member_count and approximate_presence_count. No auth, no rate
   limit headers, and a 25-request burst drew 25x HTTP 200.
   A dead code answers HTTP 404 `{"message":"Unknown Invite","code":10006}`.

2. `GET /api/v10/guilds/{id}/widget.json`
   Only when the server owner has switched the widget on -- Python has, while
   Discord Developers and Midjourney both answer
   HTTP 403 `{"message":"Widget Disabled","code":50004}`. When it is on you get
   presence_count, up to 100 currently-online members (display name, status,
   and their voice channel when they are in one), the voice channels, and a
   freshly minted instant invite. Widget members are anonymised by Discord
   itself: `id` is a per-response index ("0", "1", ...) and never the real
   snowflake, so this is a live-activity signal, not a member roster.

3. `GET /servers` and `GET /servers/{category}` (server-rendered HTML)
   The Server Discovery directory, backed by Algolia and rendered into the
   page, so no key and no XHR are needed. ~53,000 published servers, walkable
   end to end. See SSR PARSING below.

4. `GET /servers/{slug}-{guild_id}` (server-rendered HTML)
   A discoverable server's full public profile, and it carries four fields the
   search index does not: `about` (the long description), `social_links` (the
   community's own GitHub / X / Patreon / YouTube URLs), `created_at`, and
   `reasons_to_join`. That makes it the lead-generation surface.

5. `GET /trending-games`, `/trending-games/{YYYY-MM-DD}`,
   `/trending-games/category/{slug}` (server-rendered HTML)
   Discord's weekly trending-games chart: rank, total_players_pct_change,
   streaming_activity_7d_delta_pct, week_trending_streak, release date,
   IGDB artwork, genre tags, and the game's official guild with its own member
   and online counts. `prev_week_date` chains backwards through history.

6. `GET /game/{slug}-{application_id}` (server-rendered HTML) -- one game.

7. `GET /api/v10/applications/{id}/rpc`
   Public metadata for any Discord app or bot: name, description, tags,
   is_verified, is_monetized, bot_public, install scopes and permissions,
   terms-of-service and privacy-policy URLs, and the guild it belongs to.

SURFACES THAT ARE CLOSED (probed, HTTP 401/403, do not retry)
-------------------------------------------------------------
  /api/v10/guilds/{id}/preview            401 -- even for DISCOVERABLE guilds
  /api/v10/discoverable-guilds            401 -- the JSON behind /servers
  /api/v10/discovery/categories           401
  /api/v10/guilds/{id}/scheduled-events   401
  /application-directory and /application-directory/{id}
      answer HTTP 200 but ship no data: the App Directory is client-rendered
      and its fetches need a token. Use /api/v10/applications/{id}/rpc instead.
  /api/v10/guilds/templates/{code}        works only for real template codes;
      a guild id is not one, and templates are rare. Not worth a mode.

THE GATE: A RATE LIMIT, NOT A FINGERPRINT
-----------------------------------------
Only ONE surface pushes back, and only on volume. `/servers` with a `query`
answers HTTP 429 (a ~46 KB Cloudflare page, no Retry-After) after about six
requests fired back to back. It is easy to misread this as a TLS gate: running
the profile matrix in order gave 200 for all six Chrome profiles and 429 for
the six Safari/Firefox/Edge ones that followed. Re-running with Safari FIRST
after a cooldown returned 200 for Safari, Firefox, Edge and Chrome alike, and a
straight burst on Chrome alone hit 429 on request seven. The fingerprint is
irrelevant; the spacing is everything. Sixteen requests at 2.5s apart drew zero
429s, which is where REQUEST_DELAY_SECS comes from. The API endpoints under
/api/v10 are not rate limited in any way we could provoke.

DECOYS AND TRAPS
----------------
* `?q=` on /servers is silently discarded. The page answers HTTP 200 with the
  unfiltered home listing and `nbHits` for the whole index, so a run that used
  it would look successful and return generic results for every keyword. The
  real parameter is `query=`. This actor never sends `q`.
* `length=` is accepted and ignored: the echoed params always read `length=12`.
  Twelve results per request is a hard server-side page size, so item counts
  translate directly into request counts (1,000 servers = 84 requests).
* `/servers/category/{slug}` is a 404. Categories live at the bare path,
  `/servers/gaming`.
* Only FIVE of the ~50 category ids have a browsable page: gaming (1),
  music (2), entertainment (3), science & tech (5) and education (6). The other
  45 -- Cryptocurrency, Finance, Anime & Manga, Memes, Esports and the rest --
  exist as tags on server records and as facet counts, but `/servers/finance`
  is a 404. Reach them with a keyword search instead.
* `?week=` on /trending-games is discarded the same way `q` is; the historical
  week is a PATH segment, `/trending-games/2026-09-10`.
* `nbHits` drifts between requests (52,973 then 52,579 seconds apart) because
  the index is live. Treat it as an estimate, never as a loop bound.
* The slug in `/servers/{slug}-{id}` is cosmetic. A bare guild id resolves, and
  so does a wrong slug with the right id; only the trailing snowflake matters.
  A right slug with a wrong id is a 404. (Contrast Etsy, where a wrong slug is
  fatal.)
* Widget `id` fields are "0", "1", "2" ... -- a position in the response, not a
  user snowflake. Joining on them across two runs would silently pair up
  unrelated people.
* On the home listing, `nbHits` for a category facet and the count a category
  PAGE reports differ (facet says 24,579 for gaming, the page says 38,543)
  because the page filter is `primary_category_id=N OR categories.id=N` while
  the facet counts one of the two. Neither is wrong; they measure different
  things.

SSR PARSING
-----------
The HTML pages are TanStack Router SSR. The data arrives inside the largest
`<script nonce=...>` block as a seroval-style JavaScript literal, not JSON:

    $_TSR.router=($R=>$R[0]={matches:$R[1]=[$R[2]={...}]})($R["tsr"]);

Every value is prefixed by an `$R[n]=` assignment, keys are unquoted
identifiers, booleans are `!0` / `!1` and undefined is `void 0`. Across all
three page types recon found zero bare `$R[n]` back-references, so the
assignments are pure noise -- but `serialized.py` resolves them anyway, because
seroval emits back-references as soon as a payload repeats a subtree and that
is a change Discord could ship any day without telling anyone.
"""

from __future__ import annotations

SITE_ROOT = "https://discord.com"
API_ROOT = "https://discord.com/api/v10"
CDN_ROOT = "https://cdn.discordapp.com"

# Discord's own web client advertises API v9 in window.GLOBAL_ENV. v10 is the
# current documented version and answered identically on every endpoint here.
API_VERSION = 10

# No surface is fingerprint-gated (see "THE GATE" above), so this ladder exists
# only to ride out transport hiccups and the odd Cloudflare hiccup. Chrome
# leads because it is what the real web client sends.
TLS_PROFILES = (
    "chrome131",
    "chrome124",
    "safari18_0",
    "firefox133",
    "chrome120",
)

# 6 requests back to back drew a 429 on /servers; 16 at 2.5s apart drew none.
DEFAULT_REQUEST_DELAY_SECS = 2.0
# /api/v10 took a 25-request burst without complaint, so it gets its own floor.
API_REQUEST_DELAY_SECS = 0.4
DEFAULT_TIMEOUT_SECS = 45
DEFAULT_MAX_RETRIES = 4

# Server-side page size on /servers. Sending length= does not change it.
DISCOVERY_PAGE_SIZE = 12

# The only five category ids that have a browsable page, keyed by the slug the
# path actually takes. "science & tech" really does contain spaces and an
# ampersand; it is percent-encoded on the way out.
DISCOVERY_CATEGORIES: dict[str, int] = {
    "gaming": 1,
    "music": 2,
    "entertainment": 3,
    "science & tech": 5,
    "education": 6,
}

# Category ids seen on server records. Only the five above are browsable, but
# every record can carry any of these, so naming them makes the output usable
# without a lookup table on the buyer's side. Ids absent here pass through as
# their number.
CATEGORY_NAMES: dict[int, str] = {
    1: "Gaming",
    2: "Music",
    3: "Entertainment",
    4: "Creative Arts",
    5: "Science & Tech",
    6: "Education",
    12: "Finance",
    14: "General Chatting",
    15: "Esports",
    16: "Anime & Manga",
    17: "Movies & TV",
    19: "Art",
    25: "Memes",
    27: "Cryptocurrency",
    28: "Investing",
    30: "LFG",
    31: "Customer Support",
    33: "Events",
    34: "Roleplay",
    35: "Content Creator",
    38: "Collaboration",
    39: "Fandom",
    40: "Wiki & Guide",
    43: "Emoji",
    45: "Mobile",
    46: "Console",
    48: "Game Developer",
}

# Discord's documented JSON error codes that mean "this is the answer, stop
# retrying" rather than "something went wrong".
ERR_UNKNOWN_INVITE = 10006
ERR_WIDGET_DISABLED = 50004

# Guild `features` worth surfacing as plain booleans, because buyers filter on
# them and nobody wants to string-match a 50-element array. Each maps to a
# TUPLE of tokens and is true when any of them is present: Discord runs several
# spellings of the same capability at once. Monetization is the clear case --
# Midjourney carries CREATOR_MONETIZABLE and ROLE_SUBSCRIPTIONS_ENABLED while
# other monetized servers carry CREATOR_MONETIZABLE_PROVISIONAL, so matching
# one token alone reports the largest server on Discord as not monetized.
FEATURE_FLAGS: dict[str, tuple[str, ...]] = {
    "isPartnered": ("PARTNERED",),
    "isVerified": ("VERIFIED",),
    "isDiscoverable": ("DISCOVERABLE",),
    "isCommunity": ("COMMUNITY",),
    "hasVanityUrl": ("VANITY_URL",),
    "hasWelcomeScreen": ("WELCOME_SCREEN_ENABLED",),
    "hasMemberVerificationGate": ("MEMBER_VERIFICATION_GATE_ENABLED",),
    "hasAutoModeration": ("AUTO_MODERATION",),
    "isMonetizationEnabled": (
        "CREATOR_MONETIZABLE",
        "CREATOR_MONETIZABLE_PROVISIONAL",
        "CREATOR_MONETIZABLE_WHITEGLOVE",
        "ROLE_SUBSCRIPTIONS_ENABLED",
        "GUILD_PRODUCTS",
    ),
    "hasServerShop": ("GUILD_PRODUCTS",),
}

# Discord's own labels for guild.verification_level, so the number does not
# have to be looked up elsewhere.
VERIFICATION_LEVELS = {
    0: "NONE",
    1: "LOW",
    2: "MEDIUM",
    3: "HIGH",
    4: "VERY_HIGH",
}

NSFW_LEVELS = {
    0: "DEFAULT",
    1: "EXPLICIT",
    2: "SAFE",
    3: "AGE_RESTRICTED",
}
