"""Surfaces, measured yields, and the one gate that shapes this whole Actor.

Source: ``youtube.com``. One strategy only, because only one surface carries
the data this Actor sells.

**S1 -- ``ytInitialPlayerResponse`` in the watch page HTML.** A JSON blob
assigned inline. ``videoDetails.shortDescription`` is the *full* description,
newlines and all, which is where creators put sponsor mentions, promo codes and
affiliate links. Measured 2026-09-20 on six videos:

| Video | desc bytes | URLs found |
| --- | --- | --- |
| ``dQw4w9WgXcQ`` | 2431 | 11 |
| ``kJQP7kiw5Fk`` | 848 | 10 |
| ``9bZkp7q19f0`` | 508 | 11 (2 shorteners) |
| ``jNQXAC9IVRw`` | 272 | 0 |
| ``M3HKLzjvKPc`` | 1083 | - |
| ``3PFJ9SETS4M`` | 1539 | - |

**THE GATE, and why this Actor retries instead of reporting "no description".**
The watch page does *not* always carry ``shortDescription``. Measured over three
attempts per video from one IP on 2026-09-20:

| Video | attempts with a description |
| --- | --- |
| ``dQw4w9WgXcQ`` | 3/3 |
| ``jNQXAC9IVRw`` | 2/3 |
| ``9bZkp7q19f0`` | 1/3 |
| ``M3HKLzjvKPc`` | 1/3 |
| ``3PFJ9SETS4M`` | 1/3 |
| ``kJQP7kiw5Fk`` | 0/3 |

The page is 1.1-1.3 MB and returns 200 every single time -- it simply omits the
player response. This is not a WAF and not a dead surface: it is a reduced page,
the same shape already recorded for Amazon detail pages in this portfolio. None
of ``CONSENT``/``SOCS`` cookies, ``bpctr=9999999999&has_verified=1``, or
``m.youtube.com`` improved the hit rate (each 1/5 vs 2/5 plain).

So ``MAX_ATTEMPTS`` below is a *data* parameter, not a network-politeness one:
five of six videos yielded within three attempts, and the Actor keeps asking
until the marker appears. A record is only emitted as ``REDUCED`` after the
whole ladder is exhausted, so a caller can tell "this video has no description"
apart from "YouTube would not serve it to us".

**What is deliberately NOT here: the transcript.** The obvious second source for
sponsor mentions is the auto-caption track, and ``captionTracks`` (the language
list) *is* in the player response. But the signed ``baseUrl`` for each track
answers **200 with a zero-byte body** on every variant tested -- ``fmt=json3``,
``fmt=srv3``, plain, with ``Referer``, with ``CONSENT``, with ``xorp=true`` --
and the InnerTube ``/player`` endpoint answers 400 for ANDROID/IOS and
``UNPLAYABLE`` for WEB. See ``CRAWLING_METHOD.md``. This Actor therefore reports
which caption languages exist (useful on its own) and does not pretend to read
them.
"""

URL_WATCH = "https://www.youtube.com/watch?v={video_id}"
URL_CHANNEL_VIDEOS = "https://www.youtube.com/{handle}/videos"

MARKER_PLAYER = "ytInitialPlayerResponse"
MARKER_DATA = "ytInitialData"
MARKER_DESCRIPTION = '"shortDescription"'

# The reduced-page ladder. See the module docstring: this is about the page
# omitting its payload, not about being blocked.
MAX_ATTEMPTS = 6
RETRY_DELAY_BASE = 1.4
MIN_PAGE_BYTES = 40_000

TLS_LADDER = ("chrome124", "chrome120", "safari17_0", "firefox133")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MODES = ("video", "channel", "reference")

# --- classification tables -------------------------------------------------
# Three tables, not one, because collapsing them produces false positives that
# destroy the Actor's only real output. Measured on 2026-09-20: the first
# version of this table treated ``lnk.to`` and ``smarturl.it`` as affiliate
# networks, and consequently flagged Rick Astley, PSY and Luis Fonsi as running
# sponsored content. They are not -- those are *smart links*, a label's own
# routing/pre-save service for its own release. An agency filtering on
# "monetised" would have got three music videos and no brand deals.

# S1 -- genuine affiliate networks. A link here pays a commission per sale or
# per click, so its presence is real evidence of a commercial relationship.
AFFILIATE_HOSTS = {
    "amzn.to": "amazon-associates",
    "amzn.eu": "amazon-associates",
    "geni.us": "genius-link",
    "shareasale.com": "shareasale",
    "awin1.com": "awin",
    "impact.com": "impact",
    "sjv.io": "impact",
    "pxf.io": "impact",
    "cj.com": "commission-junction",
    "anrdoezrs.net": "commission-junction",
    "dpbolg.net": "commission-junction",
    "clickbank.net": "clickbank",
    "hop.clickbank.net": "clickbank",
    "shopmy.us": "shopmy",
    "ltk.app.link": "liketoknowit",
    "liketk.it": "liketoknowit",
    "howl.link": "howl",
    "collabs.shop": "collabs",
    "magiclinks.org": "magiclinks",
    "go.magik.ly": "magiclinks",
    "prf.hn": "partnerize",
    "tidd.ly": "partnerize",
    "skimresources.com": "skimlinks",
    "linksynergy.com": "rakuten",
    "click.linksynergy.com": "rakuten",
}

# S2 -- smart links / link hubs. Routing for the creator's OWN content
# (a release, a pre-save, a bio page). Reported, never counted as sponsorship.
SMART_LINK_HOSTS = {
    "lnk.to": "linkfire",
    "smarturl.it": "smarturl",
    "linktr.ee": "linktree",
    "ffm.to": "feature-fm",
    "orcd.co": "orchard",
    "found.ee": "foundee",
    "backl.ink": "backlink",
    "bio.link": "biolink",
    "beacons.ai": "beacons",
    "komi.io": "komi",
}

# S3 -- plain shorteners. The destination is unknown until resolved, so these
# are flagged for follow-up rather than counted either way.
SHORTENER_HOSTS = {
    "bit.ly": "bitly",
    "tinyurl.com": "tinyurl",
    "shorturl.at": "shorturl",
    "rb.gy": "rebrandly",
    "cutt.ly": "cuttly",
    "t.co": "twitter-shortener",
    "goo.gl": "google-shortener",
    "ow.ly": "hootsuite",
    "buff.ly": "buffer",
}

# An Amazon product link only earns commission when it carries an associate
# tag, so the tag -- not the hostname -- is what makes it affiliate.
AMAZON_HOST_HINT = "amazon."
AMAZON_TAG_PARAMS = ("tag", "ascsubtag", "linkcode")

# Hosts that are a creator's own storefront/sponsor landing rather than a
# network link. Worth separating: they signal a brand deal too, but the money
# path is different.
SPONSOR_PLATFORM_HOSTS = {
    "patreon.com": "patreon",
    "ko-fi.com": "kofi",
    "buymeacoffee.com": "buymeacoffee",
    "memberful.com": "memberful",
    "substack.com": "substack",
    "teespring.com": "merch",
    "fourthwall.com": "merch",
    "represent.com": "merch",
    "shopify.com": "merch",
    "squarespace.com": "known-sponsor",
    "nordvpn.com": "known-sponsor",
    "expressvpn.com": "known-sponsor",
    "surfshark.com": "known-sponsor",
    "skillshare.com": "known-sponsor",
    "brilliant.org": "known-sponsor",
    "audible.com": "known-sponsor",
    "hellofresh.com": "known-sponsor",
    "betterhelp.com": "known-sponsor",
    "manscaped.com": "known-sponsor",
    "raycon": "known-sponsor",
    "establishedtitles.com": "known-sponsor",
    "athleticgreens.com": "known-sponsor",
    "drinkag1.com": "known-sponsor",
    "factormeals.com": "known-sponsor",
    "ridge.com": "known-sponsor",
}

# Social/platform links that are never sponsorship. Filtered out of the
# affiliate count so the numbers mean something.
NOISE_HOSTS = (
    "youtube.com", "youtu.be", "instagram.com", "twitter.com", "x.com",
    "facebook.com", "tiktok.com", "discord.gg", "discord.com", "reddit.com",
    "twitch.tv", "threads.net", "linkedin.com", "spotify.com", "apple.com",
    "music.apple.com", "soundcloud.com", "t.me", "whatsapp.com", "snapchat.com",
    "pinterest.com", "github.com",
)

# Promo-code phrasing. Kept deliberately narrow: a loose pattern turns every
# capitalised word in a description into a "code".
PROMO_PATTERNS = (
    r"(?:use|using|with|apply|enter|redeem)\s+(?:my\s+|the\s+|discount\s+|promo\s+|coupon\s+)?"
    r"code[:\s]+([A-Z0-9][A-Z0-9_-]{2,19})\b",
    r"\bcode[:\s]+([A-Z0-9][A-Z0-9_-]{2,19})\b(?=[^a-z]|$)",
    r"\b(?:kode|kode\s+promo)[:\s]+([A-Z0-9][A-Z0-9_-]{2,19})\b",
    r"\b([A-Z0-9][A-Z0-9_-]{2,19})\s+(?:for|untuk)\s+\d{1,2}%\s*(?:off|diskon)",
)

DISCOUNT_PATTERN = r"(\d{1,2})\s*%\s*(?:off|discount|diskon|potongan)"

# Sponsor-disclosure phrasing, including the FTC-mandated forms.
SPONSOR_PATTERNS = (
    r"(?:this\s+(?:video|episode)\s+is\s+)?sponsored\s+by\s+([A-Z][\w&.\- ]{2,40})",
    r"thanks?\s+(?:to\s+)?([A-Z][\w&.\- ]{2,40})\s+for\s+sponsoring",
    r"in\s+partnership\s+with\s+([A-Z][\w&.\- ]{2,40})",
    r"brought\s+to\s+you\s+by\s+([A-Z][\w&.\- ]{2,40})",
    r"\bdisponsori\s+oleh\s+([A-Z][\w&.\- ]{2,40})",
)

DISCLOSURE_MARKERS = (
    "#ad", "#sponsored", "#paidpartnership", "paid promotion", "paid partnership",
    "affiliate link", "affiliate links", "commission", "includes paid promotion",
    "as an amazon associate", "#endorsement",
)
