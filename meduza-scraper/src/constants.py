"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): meduza.io (Meduza, independent Russian-language
press outlet in exile, Latvia-based) has NO active WAF challenge -- it sits
behind Cloudflare (cf-ray / __cf_bm cookie present) but never issues a JS
challenge; curl_cffi chrome124 gets a clean 200 on the homepage, both
editions' homepages, article pages, RSS feeds, and a synthetic 404 URL, with
no profile rotation needed. robots.txt is 75 bytes: a Twitterbot group with
no rules, and a `*` group disallowing only `/insite/` and `/embed/` --
no Claude/GPTBot/anthropic-ai disallow of any kind (re-verified fresh,
reading every `User-agent:` group's `Disallow:` lines individually, not just
the last one before a shared Disallow block). See CRAWLING_METHOD.md.

Meduza runs two editions on the same domain: the original Russian edition
(`meduza.io/<section>/<date>/<slug>`) and a curated, partly AI-translated
English edition (`meduza.io/en/<section>/<date>/<slug>`). Both share the
exact same page shape (one ld+json block + a `div.GeneralMaterial-module-
article` HTML container) -- this actor's extractor is edition-agnostic and
accepts either URL form. The English edition is used as the default/prefill
for consistency with this portfolio's other Russian-outlet actors (rt-
scraper, tass-scraper both default to their English editions).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://meduza.io"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL_EN = f"{BASE_URL}/rss/en/all"
RSS_URL_RU = f"{BASE_URL}/rss/all"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Body-bearing schema.org types worth requiring a non-empty articleBody for.
# /video/ pages (VideoObject) and other non-text layouts degrade gracefully
# with a _warning instead of raising -- they were never going to have a
# `div.GeneralMaterial-module-article > p` body in the first place.
TEXT_LD_TYPES = {"NewsArticle", "Article"}

# EN-edition articles that were AI-translated from the Russian original
# append a disclosure notice as ordinary <p> tags inside the same body
# container ("At Meduza, we are committed to transparency about our use of
# artificial intelligence..."). These substrings identify and strip those
# paragraphs so they don't pollute articleBody -- confirmed present via
# substring match on every EN sample checked during recon, absent on every
# RU sample checked.
AI_DISCLOSURE_MARKERS = (
    "committed to transparency about our use of artificial intelligence",
    "if you find any errors in this translation",
    "exclusive content in english",
)
