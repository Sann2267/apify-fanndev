"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): guardian.ng (The Guardian Nigeria -- a major
Nigerian daily; NOT related to the UK's The Guardian) sits behind Cloudflare
(`server: cloudflare`). A plain `requests`/`curl` baseline (no TLS
impersonation) hits a Cloudflare managed JS challenge ("Just a moment...")
on EVERY path, including `/robots.txt`. `curl_cffi` `chrome124` clears this
cleanly -- the homepage, article pages, and `/news-sitemap.xml` all return a
real 200 on the first try, no warmup-then-retry dance needed.

`/feed`, `/feed/`, and `/latest-news/` are a DIFFERENT story: they return a
hard Cloudflare 403 ("Attention Required!") across every TLS profile tried
(chrome124/chrome131/chrome99_android/safari17_0/edge101/firefox133) -- a
path-specific WAF rule, not a fingerprint gap, since the same profile gets a
clean 200 on the homepage and article pages. `latest` mode uses
`/news-sitemap.xml` instead (also referenced from robots.txt), which is
unaffected.

robots.txt is a stock Yoast SEO block (`User-agent: *` / `Disallow:` empty
-- allow-all) with no Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai disallow of any kind, and only one user-agent
group. Fetching robots.txt itself requires the same chrome124 impersonation
as everything else on this site -- a plain UA-only `curl` gets the JS
challenge page instead of the real robots.txt body.

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk observed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://guardian.ng"
WARMUP_URL = f"{BASE_URL}/"

# Yoast News SEO sitemap -- /feed and /latest-news/ are hard-blocked by
# Cloudflare (403 on every TLS profile tried), so this is the latest-mode
# source instead. Confirmed newest-first in file order (295 entries
# observed), each carrying loc / news:title / news:publication_date.
NEWS_SITEMAP_URL = f"{BASE_URL}/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
