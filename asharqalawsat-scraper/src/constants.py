"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): Asharq Al-Awsat (leading Pan-Arab daily,
London-based) publishes an English edition at `english.aawsat.com` (the
canonical redirect target of `aawsat.com/english`) alongside its Arabic
edition on the root `aawsat.com` domain -- this actor targets the English
edition exclusively. robots.txt is IDENTICAL (same Drupal-generated file,
byte-for-byte) on both `aawsat.com` and `english.aawsat.com`: a single flat
`User-agent: *` group, no Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai disallow of any kind, no blanket
`Disallow: /`. Disallowed paths (`/admin/`, `/search/`, `/user/*`,
`/core/`, `/profiles/`, `/json/`, etc.) do not overlap with article URLs
or the homepage this actor uses. `english.aawsat.com` sits behind
Cloudflare (`server: cloudflare` on every response) but shows no active
challenge -- `curl_cffi` `chrome124` gets a clean 200 on the homepage,
every sampled article, and a synthetic wrong-slug/wrong-ID 404 test. See
CRAWLING_METHOD.md.

Both `aawsat.com/googlenews.xml` and `aawsat.com/sitemap.xml` (advertised
in robots.txt) are Arabic-only feeds even when accessed via the
`english.aawsat.com` host (that subdomain's own `/googlenews.xml` is a
broken/mismapped copy -- empty `<loc>` tags, still-Arabic titles despite a
`news:language>en` tag) -- neither is usable for English "latest" mode.
`/feed` on english.aawsat.com 200s but is the homepage HTML, not RSS. So
"latest" mode scrapes the homepage instead, same homepage-fallback pattern
used by omanobserver-scraper/chinadaily-scraper/jamaicagleaner-scraper
when RSS/sitemap discovery is broken.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://english.aawsat.com"
WARMUP_URL = f"{BASE_URL}/"

# No usable English-language RSS/sitemap feed exists (see module docstring)
# -- the homepage doubles as the "latest" mode source.
LATEST_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
