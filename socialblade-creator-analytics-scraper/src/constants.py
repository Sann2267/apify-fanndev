"""URLs, platforms, headers -- all in one place.

Recon summary (2026-09-08): socialblade.com is a Next.js (Pages Router)
app that **server-renders its whole data payload** into `__NEXT_DATA__` as
a hydrated tRPC cache. A profile page therefore hands over the complete
creator record and its daily history in one plain GET -- no API key, no
login, no client-side call to replay.

Two cached queries matter per profile page:

* `["<platform>", "user"]`    -> the creator object (id, createdAt,
  displayName, avatar, country, channelType, socials, subscribers, videos,
  views, banner, madeForKids, description, ranks, identifiers)
* `["<platform>", "history"]` -> daily history rows
  ({date, subscribers, views, videos})

Babak 41 of ACTOR_MARKET_RESEARCHER_NEW.md flagged the opening here as
**quality, not emptiness**: `radeance/socialblade-api` has 352 users and
1,256,465 runs (3,570 runs/user, the 8th-highest ratio in the whole
high-stats pool) but sits at **2.5 out of 10** across its reviews. It also
warned that Social Blade sells a paid API and told this build to verify the
logged-out public surface first -- which is what the payload above is:
everything read here is what an anonymous visitor's own browser receives.

Cloudflare fronts the domain; no challenge was served to a `curl_cffi`
chrome request across YouTube, TikTok, Twitch, Instagram and the top-100
list.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://socialblade.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Platforms verified live: each returned a `<platform>.user` payload.
# YouTube/TikTok/Twitch also returned `<platform>.history`; Instagram
# returned the user record only (no history in the logged-out payload).
#
# Facebook is NOT supported: /facebook/page/<x> and /facebook/user/<x> both
# returned 404 with no creator payload, so it is left out rather than
# shipped as a mode that always fails.
PLATFORMS = ["youtube", "tiktok", "twitch", "instagram"]

# YouTube profile URLs come in three shapes upstream: /user/<handle>,
# /c/<handle> and /@<handle>.
#
# They are NOT interchangeable, and assuming they were produced a real bug
# in the first build: `/youtube/@mrbeast` (516M subscribers) rewritten to
# `/youtube/user/mrbeast` resolved to a *different*, 2,100-subscriber
# channel that happens to share the name -- a plausible-looking record for
# the wrong creator, which no error would ever surface.
#
# So a URL is fetched at exactly the path the caller gave, and only a bare
# handle is expanded: one starting with "@" becomes /@<handle>, otherwise
# /user/<handle>.
PROFILE_PATH = "/{platform}/user/{handle}"
PROFILE_PATH_AT = "/{platform}/@{handle}"

# Leaderboards exist for YouTube only: /youtube/top/100 works (and
# /youtube/top/100/mostsubscribed resolves to the same payload), while
# /tiktok/top/100 and /twitch/top/100 are 404.
#
# Only two sizes are accepted: /youtube/top/100 and /youtube/top/500 return
# 200, while /youtube/top/50 and /youtube/top/250 return **400**. Both valid
# sizes ship exactly **100 creators** in the server-rendered payload plus a
# `nextCursor` -- the rest is fetched client-side from the API, which is out
# of scope here, so the honest cap for this actor is 100 per run.
TOP_PATH = "/youtube/top/{size}"
TOP_PLATFORMS = ["youtube"]
TOP_SIZES = [100, 500]
TOP_MAX_CREATORS = 100

MODES = ["profile", "top"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
