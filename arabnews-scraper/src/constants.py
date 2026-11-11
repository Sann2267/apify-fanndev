"""Endpoints, headers, profile choices — all in one place.

Recon 2026-08-24: arabnews.com (Drupal) served every surface to chrome124
with no challenge. robots.txt is generic Drupal boilerplate with no Claude/
GPTBot/anthropic-ai disallow. See CRAWLING_METHOD.md.

Re-measured 2026-09-23 after a cloud run failed on `Warmup failed: 403`:
Cloudflare is now in front of the site and scores the JA3 fingerprint. The
same request that a clean address answers 200 comes back as a 5.9 KB
"Just a moment" interstitial on three of the nine profiles tried:

    200 -> chrome124, chrome131, safari17_0, safari18_0, firefox133, firefox135
    403 -> chrome136, chrome99_android, edge101

So a single hardcoded profile is a single point of failure, and retrying the
SAME profile after a 403 -- which is what this client used to do -- can never
clear it. The list below is the measured-good set, tried in order, and the
client rotates to the next one on a block.

Cloudflare scores the exit IP as well as the fingerprint: the run that failed
in the cloud had asked for a residential proxy and still got 403 on the first
profile. Rotation is what recovers that, not the proxy alone.
"""

# Tried in order; the client rotates on a block. Ordered by how clean each was
# during the 2026-09-23 sweep, with the two Safari profiles early because they
# are the least commonly blocklisted.
TLS_PROFILES = (
    "chrome124",
    "safari17_0",
    "firefox133",
    "chrome131",
    "safari18_0",
    "firefox135",
)

# Kept as the default for callers that want one profile; it is the head of the
# ladder above.
TLS_PROFILE = TLS_PROFILES[0]

BASE_URL = "https://www.arabnews.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, advertised in robots.txt as `Sitemap:`.
NEWS_SITEMAP_URL = f"{BASE_URL}/googlenews.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 6
RETRY_DELAY_BASE = 1.0
