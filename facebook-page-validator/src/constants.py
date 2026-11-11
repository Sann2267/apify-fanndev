"""Tunables and the payload-tier thresholds this actor is built on."""

from __future__ import annotations

# Facebook applies no TLS-fingerprint gate to public page HTML: all 16 curl_cffi
# profiles tested returned 200. The ladder exists only as a courtesy rotation
# for transport hiccups, not because any profile is known to be blocked.
TLS_PROFILE = "chrome124"
TLS_LADDER = ["chrome124", "chrome131", "firefox133", "safari17_0", "chrome120"]

BASE_URL = "https://www.facebook.com"

NAVIGATE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
REQUEST_DELAY = 0.8

# -- payload tiers -----------------------------------------------------------
# Facebook answers 200 for every slug, real or not. What distinguishes them is
# the size of the response, and the boundaries below were measured, not guessed
# (2026-09-20, 20 pages x 3 repeats, deterministic to the kilobyte):
#
#   ~330 KB       a slug that does not resolve to a page. A known-fake control
#                 slug returned the same size as the unresolvable guesses, and
#                 three consecutive fetches were byte-stable.
#   ~0.7 - 1.4 MB REDUCED. The page exists and the header (followers, name) is
#                 present, but Facebook withholds the post feed: 0-2 posts for
#                 pages that post daily. Sticky per page, not a random throttle
#                 -- NASA came back reduced on three consecutive runs.
#   >= 1.5 MB     FULL. Header plus ~10 posts.
#
# Everything is parsed structurally rather than by position, and a field that no
# marker resolves is emitted as null -- never inferred from a nearby number.
# The tier is reported on every record so a buyer can tell "this page has no
# posts" apart from "Facebook did not send the posts", which are different facts.
HOLLOW_MAX_BYTES = 450_000
REDUCED_MAX_BYTES = 1_500_000

TIER_HOLLOW = "HOLLOW"
TIER_REDUCED = "REDUCED"
TIER_FULL = "FULL"


def classify_tier(size_bytes: int) -> str:
    if size_bytes <= HOLLOW_MAX_BYTES:
        return TIER_HOLLOW
    if size_bytes <= REDUCED_MAX_BYTES:
        return TIER_REDUCED
    return TIER_FULL


# Facebook sends no content-length and ignores Range requests on this surface
# (verified 2026-09-20: HEAD returns 200 with no length header, and a
# `Range: bytes=0-120000` request returns the entire body anyway). There is
# therefore no way to learn a page's tier without downloading the full
# response. In practice that is cheap -- ~1.0s for an 8 MB page -- which is
# why this actor fetches slugs concurrently instead of trying to be clever.
# Response sizes wobble by a few KB between fetches, so the boundaries above
# sit in the wide empty gaps between the observed clusters, not beside them.
