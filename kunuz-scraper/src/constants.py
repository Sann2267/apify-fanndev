"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): Kun.uz is Uzbekistan's most-visited news
portal (kun.uz), a Next.js SPA served with server-rendered HTML. It
publishes in 4 language tracks on ONE domain: default path (Latin
Uzbek), `/kr/` (Cyrillic Uzbek), `/ru/` (Russian), and `/en/` (English).
This actor is scoped entirely to the `/en/` prefix -- the same
domain-vs-path-scoping pattern as `qazinform.com` for Kazinform, except
here the language split is a URL prefix on one host rather than a
separate domain.

No active WAF challenge was found on kun.uz during recon: `curl_cffi`
`chrome124` gets a clean HTTP 200 on the homepage, article pages, the
dedicated latest-news listing page, the sitemap index, and even 404
pages, on every attempt -- despite the site being Cloudflare-fronted
(`server: cloudflare`, `CF-RAY` present on every response). Retry/
backoff scaffolding is kept anyway per portfolio convention. See
CRAWLING_METHOD.md for full recon notes.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://kun.uz"
WARMUP_URL = f"{BASE_URL}/en"

# Dedicated SSR "Latest news" listing page (linked from the homepage's
# <aside><h2><a href="/en/news/list">Latest news</a>) -- English-only,
# confirmed genuinely newest-first against real `datePublished`
# timestamps. Fixed at ~20 items server-rendered, no working pagination
# param found (see CRAWLING_METHOD.md) -- `limit` is capped to match.
LATEST_LIST_URL = f"{BASE_URL}/en/news/list"
LATEST_MAX_ITEMS = 20

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
