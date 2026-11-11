"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): Gazeta.uz is Uzbekistan's major independent
news portal. This is the first Uzbekistan outlet in this portfolio (Central
Asia region opened previously with kazinform-scraper for Kazakhstan). The
site serves 4 language editions on ONE domain via path prefixes:
`/ru/` (Russian), `/uz/` (Uzbek Cyrillic), `/oz/` (Uzbek Latin), `/en/`
(English) -- confirmed via `hreflang` alternates on every page
(`hreflang="ru"`, `"uz-Cyrl"`, `"uz-Latn"`, `"en"`). This actor is scoped
entirely to the **`/en/` English edition** (same domain, path-prefixed --
NOT a separate subdomain like `qazinform.com`), the same "pick one language
scope" pattern as `asharqalawsat-scraper`/`kazinform-scraper`. English
content is substantial: dedicated `/en/politics/`, `/en/economy/`,
`/en/society/`, `/en/column/` sections, its own RSS feed
(`/en/rss/`) and its own Google News sitemap
(`/sitemap/google-news-en.xml`), all actively updated same-day as the
Russian edition.

No active WAF found: plain `curl` (no impersonation) and `curl_cffi`
`chrome124` both return clean 200s of matching size, served directly by
nginx (no Cloudflare/challenge markers). Retry/backoff scaffolding is kept
anyway per portfolio convention. See CRAWLING_METHOD.md for full recon
notes.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.gazeta.uz"
WARMUP_URL = f"{BASE_URL}/en/"

# Standard RSS 2.0 feed, English edition -- teaser-only (no full body),
# newest-first, 20 items. See CRAWLING_METHOD.md.
LATEST_FEED_URL = f"{BASE_URL}/en/rss/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
