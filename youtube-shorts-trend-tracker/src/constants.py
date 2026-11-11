"""Surfaces and measured yields for YouTube Shorts trend tracking.

Two surfaces, and they answer different questions. Using only the first is what
makes most "Shorts scrapers" useless for ranking.

**S1 -- the hashtag grid.** ``/hashtag/<tag>/shorts``. Measured 2026-09-20,
three fetches on each of ``chrome124``, ``chrome120`` and ``safari17_0``:

| Metric | Value, every single fetch |
| --- | --- |
| Page size | 840-848 KB |
| ``shortsLockupViewModel`` | **37** |
| entries with a view figure | **36** |
| continuation tokens | 1 |

Unusually stable for YouTube -- nine fetches, no variance. That is worth stating
because the *watch* page on the same day varied wildly (see
``youtube-sponsor-affiliate-extractor``).

The catch: the grid's only engagement figure is inside ``accessibilityText``,
and it is **rounded** -- ``"Frog Eggs Time Challenge!, 3.3 million views - play
Short"``. There are no likes at all. A ranking built on the grid alone can only
sort into 3.3M-sized buckets and can never compute a views-to-likes ratio.

**S2 -- the Short's own page.** ``/shorts/<id>`` carries what the grid lacks:

| Field | Where | Example measured |
| --- | --- | --- |
| Exact views | ``"viewCount":"3396295"`` | 3,396,295 vs grid's "3.3 million" |
| Exact likes | ``accessibilityText`` "like this video along with 36,212 other people" | 36,212 |
| Sound | ``soundAttributionTitle`` | "Original Sound" |
| Hashtags | ``attributedDescription`` / keywords | #Mukbang #buldakchallenge |

Note ``"likeCountEntity":{"key":"unset_like_count_entity_key"}`` -- the obvious
like field is a placeholder that is never filled server-side. The real number is
only in the accessibility string, so that is what this Actor parses.

**Escaping.** On ``/shorts/`` pages the interesting payload is hex-escaped
inside a string: ``\\x22soundAttributionTitle\\x22:\\x7b\\x22content\\x22:\\x22Original Sound\\x22``.
Anything scanning for plain ``"soundAttributionTitle"`` finds nothing and
concludes the field does not exist. ``extractor.unescape_hex`` handles this.

**Cost.** ``detail: false`` is 1 request per hashtag and gives rounded views.
``detail: true`` is 1 + N requests and gives exact views, likes, the ratio and
the sound. The default is ``true`` because the ratio is the product.
"""

URL_HASHTAG = "https://www.youtube.com/hashtag/{tag}/shorts"
URL_SHORT = "https://www.youtube.com/shorts/{video_id}"

MARKER_DATA = "ytInitialData"
MARKER_LOCKUP = "shortsLockupViewModel"

MAX_ATTEMPTS = 5
RETRY_DELAY_BASE = 1.3
MIN_PAGE_BYTES = 120_000

TLS_LADDER = ("chrome124", "chrome120", "safari17_0", "firefox133")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MODES = ("hashtag", "video", "reference")

# Multipliers for the rounded grid figures ("3.3 million views").
SCALE_WORDS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
}

# A Short is at most 3 minutes. Anything longer that slips into a hashtag grid
# is a regular upload and is marked rather than silently mixed in.
SHORTS_MAX_SECONDS = 180
