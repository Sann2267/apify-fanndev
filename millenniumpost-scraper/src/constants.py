"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): millenniumpost.in sits behind Cloudflare
(`server: cloudflare` on every response) but presented NO challenge to
`curl_cffi` `chrome124` impersonation -- homepage, article pages across 3
sections (business, nation, bengal), and `/news-sitemap-daily.xml` all
returned 200 with full content on the first try, no "Just a moment"/
challenge-platform/captcha body markers. chrome124 is pinned per the
portfolio-wide default of avoiding the most-blocklisted `chrome131` profile
even when it currently works.

robots.txt (`User-agent: *` / `Allow: /`, plus a `Googlebot-News: Allow: /`
group) has no Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai disallow of any kind and no plain-English AI/LLM-training
prohibition in its comments -- independently re-verified live during this
build.

The site-wide `/rss` and `/feed` endpoints both 200 but return an EMPTY
`Hocalwire`-generated RSS channel (zero `<item>` elements, `lastBuildDate`
over a year stale as of this build) -- a dead feed, not usable for `latest`
mode. `/news-sitemap-daily.xml` is used instead: 273 `<url>` entries
observed in one fetch, each carrying a real per-article `news:title` and
`news:publication_date`, newest-first in file order.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.millenniumpost.in"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, updated continuously through the day. Preferred over
# the dead /rss and /feed endpoints (both 200 but zero items -- see recon
# summary above). Confirmed newest-first in file order (273 entries observed,
# top entry matching the freshest homepage headline at fetch time);
# extract_sitemap_items() still sorts descending by publication_date
# defensively.
NEWS_SITEMAP_URL = f"{BASE_URL}/news-sitemap-daily.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
