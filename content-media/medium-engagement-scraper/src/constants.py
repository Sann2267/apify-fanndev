"""Surfaces, yields and the one place where the obvious page is the wrong one.

Source: ``medium.com``. Two strategies, and which one a mode uses is decided by
measurement rather than by preference:

**S1 -- ``window.__APOLLO_STATE__`` in the server-rendered HTML.** A normalised
Apollo cache. It is the only surface carrying **engagement**: ``clapCount``,
``postResponses.count`` and ``isLocked`` (the paywall flag). Yields measured on
2026-09-18:

| Page | ``Post:`` entries | Usable (title + claps) |
| --- | --- | --- |
| ``/tag/<slug>`` | 35 | **35** |
| ``/tag/<slug>/archive`` | 20 | **20** |
| ``/tag/<slug>/recommended`` | 10 | **10** |
| ``/@<author>`` | 10 | **10** |
| ``/<publication>`` | **167** | **0** |

That last row is the trap. A publication page looks like the richest surface in
the whole source -- 167 post entries -- but every one of them holds only
``{"__typename": "Post", "id": "..."}``. The cache is pre-seeded with
references whose data is fetched client-side, so an Actor that counted
``Post:`` keys would report 167 articles and emit 167 empty rows.
``/<publication>/archive`` and ``/<publication>/latest`` carry **zero** post
entries at all.

**S2 -- the RSS feed** (``/feed/tag/<slug>``, ``/feed/@<author>``,
``/feed/<publication>``). Always 10 items, but it carries the **article body
HTML**, which the Apollo cache does not. It is the only path that works for
publications, which is why publication mode uses it and says so in
``_source``.

Neither surface paginates. ``?limit=50`` on RSS is accepted and ignored, and
``start``-style parameters do nothing on the HTML pages. Breadth comes from
querying more tags, authors and publications -- not deeper pages.

Recon 2026-09-18, plain HTTP, no cookie, no login. ``medium.com/_/graphql``
answers **403**, so the private API is not a route.
"""

BASE = "https://medium.com"

URL_TAG = BASE + "/tag/{slug}"
URL_TAG_SECTION = BASE + "/tag/{slug}/{section}"
URL_AUTHOR = BASE + "/@{handle}"
URL_POST = BASE + "/{path}"
URL_FEED_TAG = BASE + "/feed/tag/{slug}"
URL_FEED_AUTHOR = BASE + "/feed/@{handle}"
URL_FEED_PUBLICATION = BASE + "/feed/{slug}"

TLS_PROFILE = "chrome124"
TLS_LADDER = ("chrome124", "firefox133", "safari17_0", "edge101", "chrome99_android")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0

MODES = ("tag", "author", "publication", "post", "reference")

TAG_SECTIONS = ("top", "archive", "recommended")
# "top" is the bare /tag/<slug> page and has no path suffix.
SECTION_PATHS = {"archive": "archive", "recommended": "recommended"}

# Measured yields, used to warn when a page returns far less than it should.
EXPECTED_POSTS = {"top": 35, "archive": 20, "recommended": 10, "author": 10, "feed": 10}

# Medium pages are 100 KB+. A much smaller 200 is a challenge or an error shell.
MIN_PAGE_BYTES = 40_000
MIN_FEED_BYTES = 2_000
