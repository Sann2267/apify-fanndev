"""Endpoints and per-mode wiring for TikTok's public *embed* surface.

Why this actor scrapes `/embed/...` and nothing else
---------------------------------------------------
Recon on 2026-09-12 measured every obvious TikTok surface from a plain HTTP
client. The consumer web app is shut, and it does not announce it with an error
status -- which is exactly why a status-only health check would call this a pass:

    GET /@nasa                     -> 200, 1,462 bytes, `SlardarWAF` shell
    GET /@user/video/<id>          -> 200, 1,462 bytes, `SlardarWAF` shell
    GET /tag/<tag>                 -> 200, 375 KB, rehydration blob with NO data
    GET /music/<slug>              -> 200, 376 KB, same blob
    GET /search?q=...              -> 200, 369 KB, same blob
    GET /explore                   -> 200, 384 KB, same blob

The 375 KB blob is the trap. It parses, it is big, and it contains
`__UNIVERSAL_DATA_FOR_REHYDRATION__` -- but its `__DEFAULT_SCOPE__` holds only
`webapp.app-context`, `webapp.biz-context`, `seo.abtest`, `webapp.a-b` and
185 KB of `webapp.i18n-translation`. No `itemList`, no `userInfo`, no
`challengeInfo`. It is the app shell plus the UI dictionary.

The profile/video shell was byte-identical across **chrome124, chrome120,
safari17_0, firefox133 and edge101** on the same IP, so this is not a JA3 gate
that a different fingerprint reopens -- unlike the Blibli merchant endpoint in
this portfolio, where safari passed and chrome did not.

The internal JSON APIs are signature-gated:

    GET /api/user/detail/?uniqueId=nasa        -> 200, **0 bytes**
    GET /api/post/item_list/?secUid=...        -> 200, **0 bytes**
    GET /api/comment/list/?aweme_id=...        -> 200, {"status_code":5}
    GET /api/recommend/embed_playlist/?...     -> 200, {"status_msg":"url doesn't match"}

Those need the `X-Bogus`/`X-Gnarly` request signature plus an `msToken` minted by
TikTok's own JS. Reproducing either means shipping a browser or reimplementing a
deliberately obfuscated signer, so this actor does neither and does not pretend
to offer the surfaces that depend on them.

The business properties are no better for a plain client: the Creative Center
page is a 20 KB SPA shell with no `__NEXT_DATA__`, and
`creative_radar_api/v1/popular_trend/*` answers `{"code":40101,"msg":"no
permission"}` -- including after warming the page for cookies, which sets none.

What IS open
------------
TikTok's **oEmbed endpoint and its embed widget pages** are built to be consumed
by third parties, so they are served without the WAF and without signing. All
four were verified to carry real values, not shells:

    GET /oembed?url=<video url>    -> 200, JSON: title, author_name,
                                      author_unique_id, thumbnail_url
    GET /embed/v2/<videoId>        -> 200, 302 KB, FRONTITY state with
                                      diggCount/shareCount/playCount/commentCount,
                                      authorInfos, authorStats, musicInfos
    GET /embed/@<username>         -> 200, 310 KB, FRONTITY state with userInfo:
                                      followerCount, heartCount, verified, bio
    GET /embed/tag/<hashtag>       -> 200, 290 KB, playlistType=hashtag,
                                      videoList (~6 videos)
    GET /embed/music/<musicId>     -> 200, 303 KB, playlistType=music,
                                      videoList (~9 videos) + embedInfo.videoCount

Measured example (video 7626254334065511711): playCount 11000, diggCount 427,
shareCount 14, commentCount 10, author followerCount 6,300,000, heartCount
394,000,000, music "euphoria" by "inertia. & Aurenth".

Variants that do NOT exist, confirmed with 404 rather than rate-limit noise:
`/embed/v2/@user`, `/embed/v2/tag/<t>`, `/embed/hashtag/<t>`,
`/embed/user/<secUid>`, `/embed/playlist/<id>`, `/embed/@user/playlist`.

Known ceilings, stated rather than hidden
-----------------------------------------
* **A hashtag or music page ships one page of 6-9 videos.** The embed's own
  loader calls `/api/recommend/...`, which is signature-gated (above), so there
  is no deeper pagination to offer. Rows say so in `_warning`.
* **No user video list.** Listing an account's posts needs
  `/api/post/item_list/`. The profile mode therefore returns account stats only;
  to get a user's videos you must already hold their video ids or urls.
* **No comments, no search, no trending/explore.** All three are behind the
  signed APIs.
* **`playCount` on the video embed is rounded** by TikTok itself (11000, not
  11,043) and `videoMeta.duration`/`ratio` arrive as the placeholder 99 on some
  videos. Reported as served; not corrected, not hidden.
"""

ORIGIN = "https://www.tiktok.com"
OEMBED_URL = f"{ORIGIN}/oembed"

EMBED_VIDEO = f"{ORIGIN}/embed/v2/{{video_id}}"
EMBED_USER = f"{ORIGIN}/embed/@{{username}}"
EMBED_HASHTAG = f"{ORIGIN}/embed/tag/{{hashtag}}"
EMBED_MUSIC = f"{ORIGIN}/embed/music/{{music_id}}"

# The embed host applies no TLS gate (see module docstring: all five profiles
# returned byte-identical bodies), so this ladder exists to vary the fingerprint
# after a 503 rate-limit, not to defeat a fingerprint blocklist. Pairing it with
# a proxy rotation is the part that actually recovers a run.
TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "edge101", "chrome120")

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

JSON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

REQUEST_TIMEOUT = 60
MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0

# TikTok answers repeated embed requests from one IP with HTTP 503 within a
# handful of calls, so pacing keeps a run alive far longer than hammering does.
DEFAULT_DELAY_SECONDS = 2.0

# The <script> element every embed page server-renders its state into.
STATE_SCRIPT_ID = "__FRONTITY_CONNECT_STATE__"

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
MODE_PROFILE = "profile"
MODE_VIDEO = "video"
MODE_HASHTAG = "hashtag"
MODE_MUSIC = "music"
MODE_OEMBED = "oembed"

ALL_MODES = (MODE_PROFILE, MODE_VIDEO, MODE_HASHTAG, MODE_MUSIC, MODE_OEMBED)

SOURCE_EMBED = "embed-frontity-state"
SOURCE_OEMBED = "oembed-api"
SOURCE_NONE = "none"

# Error codes emitted as diagnostic rows. Every input yields at least one row.
ERR_INVALID_INPUT = "INVALID_INPUT"
ERR_NOT_FOUND = "NOT_FOUND"
ERR_PRIVATE = "PRIVATE_ACCOUNT"
ERR_BLOCKED = "BLOCKED_AFTER_RETRIES"
ERR_SHAPE = "UPSTREAM_SHAPE_CHANGED"
ERR_EMPTY = "EMPTY_RESULT"

# Warnings describing surface ceilings rather than failures.
WARN_SINGLE_PAGE = "single_page_surface_embed_playlist_is_not_paginable"
WARN_NO_VIDEO_LIST = "profile_embed_does_not_publish_a_video_list"
WARN_ROUNDED_PLAYCOUNT = "play_count_rounded_by_tiktok"
WARN_LIST_ITEM_FIELDS = "playlist_rows_carry_play_count_only_no_digg_or_comment_counts"
