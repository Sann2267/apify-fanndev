"""Tunables for the tech stack detector."""

from __future__ import annotations

# There is no target site, so there is no fingerprint gate to defeat. A plain
# modern Chrome profile is used so sites serve their normal markup rather than
# a legacy or bot-simplified variant, which would hide the very script tags the
# fingerprints key off.
TLS_PROFILE = "chrome124"

BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0
REQUEST_DELAY = 0.3

# Only this much of a page is kept for matching. Homepages run to several MB of
# inlined state, and every fingerprint worth having appears in the head or in
# the asset references near it -- so this caps memory per concurrent fetch
# without costing detections.
MAX_HTML_BYTES = 2_000_000

# robots.txt is an optional second request. It is cheap and occasionally decides
# a case the homepage cannot: platform-specific disallow paths (/wp-admin/,
# /cart, /checkouts/) survive even on sites that render everything client-side.
ROBOTS_PATH = "/robots.txt"

ROBOTS_MARKERS = [
    ("WordPress", "/wp-admin/", "likely"),
    ("Shopify", "/checkouts/", "likely"),
    ("Shopify", "/cart/add", "likely"),
    ("Magento", "/catalogsearch/", "likely"),
    ("Drupal", "/core/", "likely"),
    ("PrestaShop", "/modules/", "likely"),
    ("Ghost", "/ghost/", "likely"),
]
