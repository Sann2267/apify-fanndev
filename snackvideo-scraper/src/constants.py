"""Endpoints, request bodies, page sizes and retry policy for SnackVideo.

THE GATE (recon 2026-09-25): there isn't one. www.snackvideo.com sits behind
Tengine (Alibaba's nginx) with no bot manager in front of it. Plain `requests`
with no cookies, no warm-up and no browser headers got HTTP 200 on every
endpoint below, and so did curl_cffi chrome124 / safari17_0 / firefox133 /
chrome99_android. Nothing is signed either: the web app's axios interceptor
only strips the "overseaAPI::" prefix and posts JSON to the same origin.

We still impersonate a real browser (chrome124 first; chrome131 is widely
blocklisted elsewhere in 2026) and keep a profile ladder, because a Kuaishou
property can bolt a gate on without notice and rotating costs nothing.
"""

from __future__ import annotations

SITE = "https://www.snackvideo.com"

# JSON endpoints the Nuxt web app (kwai-nuxt-pwa-pc) calls. All are POST with a
# JSON body and answer {"result": 1, ...} on success.
EP_PROFILE = "/rest/o/w/pwa/profile"             # user card + counts
EP_PROFILE_FEED = "/rest/o/w/pc/feed/profile"    # a user's videos + playlists
EP_SLIDES = "/rest/o/w/pwa/feed/slides"          # For You feed / one video by id
EP_TOPIC = "/rest/o/w/pic/topic"                 # hashtag (topic) feed
EP_SEARCH = "/rest/o/w/pwa/v2/search/word/outer" # keyword discover feed
EP_ALBUM = "/rest/o/w/pwa/feed/album"            # playlist (album) videos

# API result codes. 1 = OK. 15 = "server busy": the web app itself falls back
# to a cached snapshot on it, so it is transient. 205 = the photo does not
# exist (clean negative). 11 = "Please check your Internet connection", which
# is really a rejected parameter (e.g. search count=100) - deterministic.
RESULT_OK = 1
RESULT_BUSY = 15
RESULT_BAD_PARAM = 11
RESULT_PHOTO_NOT_FOUND = 205

# Largest page each endpoint actually honours (recon). Asking for more is not
# harmless: For You silently drops to 8 items at count=100 and search answers
# result=11 with zero items.
PAGE_PROFILE_FEED = 100
PAGE_TOPIC = 100
PAGE_SLIDES = 50
PAGE_SEARCH = 50
PAGE_ALBUM = 20

# Feeds that re-serve items (topic ~5% per page, search/For You are sampled
# recommendations) stop after this many pages in a row add nothing new.
STALL_PAGES = 3
# Hard ceiling on requests per target, whatever maxItems says.
MAX_PAGES_PER_TARGET = 400

# TLS ladder: rotated on 403 / challenge markers. All four passed recon.
TLS_PROFILES = ("chrome124", "safari17_0", "firefox133", "chrome99_android")

DEFAULT_MAX_RETRIES = 6
DEFAULT_TIMEOUT_SECS = 30
BACKOFF_BASE_SECS = 1.0
BACKOFF_CAP_SECS = 30.0
RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)

# Bodies of the anti-bot pages we would expect if a gate ever appears.
BLOCK_MARKERS = (
    b"Just a moment", b"challenge-platform", b"captcha", b"_____tmd_____",
    b"baxia", b"punish", b"Access Denied",
)

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": SITE,
    "Referer": SITE + "/",
}
