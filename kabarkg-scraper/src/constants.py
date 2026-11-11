"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): Kabar is the National News Agency of the
Kyrgyz Republic, Kyrgyzstan's state news agency. The flagship domain
`kabar.kg` serves Kyrgyz-language content (`<html lang="ky">`); a
language switcher in the header (`div.language-select-block`) links out
to `https://ru.kabar.kg` (Russian), `https://en.kabar.kg` (English), and
`https://tr.kabar.kg` (Turkish) — each a separate subdomain, not a path
prefix (`/en/`, `/ru/` all 404 on the flagship domain). This actor is
scoped entirely to `en.kabar.kg` (English edition), the same pattern as
`qazinform.com` for `kazinform-scraper` and the English subdomain of
Asharq Al-Awsat for `asharqalawsat-scraper`.

No active WAF challenge was found on en.kabar.kg during recon: plain
`curl` (no TLS impersonation) and `curl_cffi` `chrome124` both get a
clean 200 with identical byte size on the homepage, robots.txt, the news
sitemap, and article pages, served directly by nginx (no Cloudflare/
challenge markers, no `cf-ray` header). Retry/backoff scaffolding is kept
anyway per portfolio convention. See CRAWLING_METHOD.md for full recon
notes.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://en.kabar.kg"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap -- no working RSS/Atom feed found (/feed and /feed/
# 301-redirect to a path that itself 404s). Newest-first, confirmed
# against the freshest homepage story at fetch time. See CRAWLING_METHOD.md.
NEWS_SITEMAP_URL = f"{BASE_URL}/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
