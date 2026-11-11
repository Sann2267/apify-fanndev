"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-27): 24.kg is Kyrgyzstan's leading news agency and
the first Kyrgyzstan (Central Asia) outlet in this portfolio. The site is
bilingual Russian/Kyrgyz -- most sections (e.g. `/obschestvo/`, `/ekonomika/`,
`/sport/`, `/proisshestvija/`) publish in Russian, while `/kyrgyzcha/`
publishes in Kyrgyz (`<html lang="ky-KG">` on those pages vs `lang="ru-RU"`
elsewhere). No separate English edition was found -- this actor is scoped to
the single bilingual `24.kg` domain, and both languages are passed through
verbatim (raw passthrough, no translation).

No active WAF challenge was found during recon: a plain, non-impersonated
`requests.get()` gets an identical clean 200 to `curl_cffi` `chrome124` on
the homepage (`server: nginx/1.31.2`, no Cloudflare/challenge markers).
`chrome124` is still pinned, consistent with the portfolio-wide default, and
retry/backoff scaffolding is kept per convention. See CRAWLING_METHOD.md for
full recon notes.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://24.kg"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide RSS feed, newest-first, ~50 items, refreshed continuously
# (ttl=10 minutes). Teaser-only (title/description/category/pubDate) -- no
# full body text embedded, unlike Kazinform's feed.xml.
LATEST_FEED_URL = f"{BASE_URL}/rss/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
