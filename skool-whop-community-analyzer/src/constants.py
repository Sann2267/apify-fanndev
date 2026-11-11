"""Endpoints, headers, retry knobs -- one place for both platforms.

Recon summary (2026-08-29, see CRAWLING_METHOD.md for the full log):

**Skool** (`www.skool.com`) sits behind CloudFront, not a real WAF -- a
plain unauthenticated `curl` with an ordinary Chrome UA gets a clean 200
on every `/<slug>/about` page tested. No TLS impersonation ladder, no
warmup, no cookie jar needed. `robots.txt` only disallows `/*/--/*`.

**Whop** (`whop.com`) sits behind Cloudflare with Bot Management active
(`__cf_bm` cookie observed on every response), which is a materially
higher block-risk surface than Skool's plain CloudFront -- but every
storefront/plan page tested during recon still returned a clean 200 with
real data to a plain unauthenticated request, no JS challenge triggered.
`robots.txt` only disallows `/api/` and `/discover/search/*` (both
avoided by this actor already, since neither is used). `chrome124` is
pinned defensively for both platforms for TLS-fingerprint consistency,
even though Skool's CloudFront doesn't appear to check it.
"""

TLS_PROFILE = "chrome124"

SKOOL_BASE_URL = "https://www.skool.com"
WHOP_BASE_URL = "https://whop.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Skool renders a group's page inside `<script id="__NEXT_DATA__">` as
# plain JSON -- `props.pageProps.group` is the community object. Confirmed
# present unauthenticated on both free and paid communities.
SKOOL_NEXT_DATA_RE = r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>'

# Whop's storefront/plan pages ship data as a React Server Components
# (RSC) streaming payload (`self.__next_f.push([1, "..."])` chunks using
# unquoted-key object-literal syntax, e.g. `memberCount:4541`), NOT a
# clean JSON blob like Skool's __NEXT_DATA__. This actor extracts known
# fields with targeted regexes against the raw response text rather than
# attempting a full RSC/JS parse -- confirmed workable during recon (see
# CRAWLING_METHOD.md) but inherently more fragile than JSON.parse if Whop
# reshuffles its component prop order.
