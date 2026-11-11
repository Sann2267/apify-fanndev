"""Surface, measured yields, and two limits worth knowing before you buy.

Source: ``youtube.com``. One surface.

**The path matters, and the obvious one is wrong.**
``/@handle/community`` answers 200 with a full 761 KB page that says
*"This Community isn't available"* and contains **zero** posts — measured on
``@MrBeast`` and ``@veritasium``, both with and without ``CONSENT``/``SOCS``
cookies. The working path is ``/@handle/posts``:

| Handle | Page | ``backstagePostRenderer`` | ``pollRenderer`` | continuations |
| --- | --- | --- | --- | --- |
| ``@MrBeast`` | 960-965 KB | **10** | 2 | 3 |
| ``@veritasium`` | 934 KB | **10** | 1 | 3 |

Each post carries ``postId``, ``authorText``, ``contentText``,
``publishedTimeText``, ``voteCount`` and usually a ``backstageAttachment``
(9 of 10 on both channels).

**Limit 1 — like counts are abbreviated, never exact.**
``voteCount`` is ``{"simpleText": "1.9M", "accessibility": {... "1.9M likes"}}``.
There is no exact figure anywhere in the payload for a logged-out client. This
Actor returns both the text and a parsed integer, and flags the integer as
approximate, rather than presenting ``1900000`` as if it were counted.

**Limit 2 — polls give the choices and the total, not the split.**
A ``pollRenderer`` logged out contains ``choices[].text``, ``totalVotes``
("1.7M votes") and ``type``. Each choice carries a ``signinEndpoint`` where the
percentage would be: YouTube only reveals the breakdown to a signed-in voter.
So "what did the audience pick" is **not** available from this surface, and any
Actor claiming otherwise is either logged in or making it up. What you do get:
the exact wording of every option and how many people voted in total.

**Links are wrapped.** URLs inside ``contentText`` are rewritten to
``youtube.com/redirect?...&q=<real url>``. The extractor unwraps ``q`` so a
record carries the destination, not the tracker.
"""

URL_POSTS = "https://www.youtube.com/{handle}/posts"
URL_POST_PERMALINK = "https://www.youtube.com/post/{post_id}"

MARKER_DATA = "ytInitialData"
MARKER_POST = "backstagePostRenderer"

MAX_ATTEMPTS = 5
RETRY_DELAY_BASE = 1.3
MIN_PAGE_BYTES = 120_000

TLS_LADDER = ("chrome124", "chrome120", "safari17_0", "firefox133")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MODES = ("channel", "reference")

# "1.9M" -> 1_900_000. Abbreviations only; see Limit 1 above.
SCALE_SUFFIXES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

# The page that says the community is unavailable, so the Actor can name the
# problem instead of reporting an empty channel.
UNAVAILABLE_MARKER = "This Community isn't available"
