"""Endpoints, TLS profile and static tables for the Snapchat scraper.

Recon (2026-09-18, plain HTTP, no cookie, no login, no proxy):

* ``https://www.snapchat.com/add/<username>`` redirects to ``/@<username>`` and
  answers 200 with a full Next.js SSR document. NASA = 660 KB, Netflix = 1.4 MB.
  The whole payload sits in ``<script id="__NEXT_DATA__">`` -- profile, lenses,
  highlights and spotlight metadata all arrive in that ONE request, which is why
  four of this Actor's modes cost a single request per username.
* No WAF was observed on any request: no Cloudflare challenge, no captcha, no
  ``__cf`` cookie. ``chrome124`` is used because ``chrome131`` is widely
  blocklisted in 2026 (see .ai/CLAUDE.md), not because Snapchat demanded it.
* Unknown usernames answer **404** with a small body (6 KB) -- a clean
  not-found signal, so this Actor never has to guess.
* Locale follows the exit IP, not ``Accept-Language``. ``?locale=en-US`` is the
  only lever that works; the path form ``/en-US/add/<user>`` returns 404.
* ``_next/data/<buildId>/...`` returns 404, so the cursors the page exposes
  (``curatedHighlightsCursor`` and friends) have no reachable public endpoint.
  What the document carries is what this Actor can return -- documented as a
  limit in the README rather than faked.
"""

BASE = "https://www.snapchat.com"

# Profile page. The /add/ form is the one Snapchat itself links to; it 301s to
# the /@ form and both carry an identical payload.
URL_PROFILE = BASE + "/add/{username}?locale={locale}"

# Hub pages -- no username, one request each.
URL_SPOTLIGHT_HUB = BASE + "/spotlight?locale={locale}"
URL_LENS_HUB = BASE + "/lens?locale={locale}"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

MODES = (
    "profile",
    "spotlight",
    "highlights",
    "lenses",
    "related",
    "trending",
    "top-lenses",
    "reference",
)

# Snapchat ships these as opaque integers. Only the values actually observed
# during recon are named; anything else passes through as the raw integer so a
# new badge type is visible instead of being silently mapped to "none".
BADGE_NAMES = {
    0: "none",
    1: "official",
}

# storyType seen on highlight objects. Same rule: unknown ids ship raw.
STORY_TYPE_NAMES = {
    3: "CURATED_HIGHLIGHT",
    15: "SPOTLIGHT_HIGHLIGHT",
}

# Category strings arrive as localisation keys such as
# "public-profile-category-v3-business-group". The prefix carries no
# information, so it is stripped for the friendly field while the original
# key is kept in the raw payload.
CATEGORY_PREFIXES = (
    "public-profile-category-v3-",
    "public-profile-subcategory-v3-",
    "public-profile-category-",
    "public-profile-subcategory-",
)

DEFAULT_LOCALE = "en-US"
