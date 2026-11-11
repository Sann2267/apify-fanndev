"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): dailymirror.lk (Daily Mirror, Sri Lanka's
leading English-language daily) shows NO active WAF challenge. The site is
Cloudflare-fronted (Server: cloudflare, cf-ray header, cf-cache-status:
DYNAMIC) but this is CDN/analytics plumbing only -- plain `curl` with no
TLS impersonation at all already got a clean 200 on the homepage, article
pages and category listing pages; the full curl_cffi profile ladder
(chrome124, chrome99_android, safari17_0, edge101, firefox133) all returned
200 with byte-identical bodies too. No _cf_chl_/"Just a moment"/
challenge-platform marker was ever seen. robots.txt has FOUR separate
User-agent groups (*, Googlebot, Slurp, msnbot), each with its own `Allow:
/` line immediately beneath it -- no Disallow anywhere in the file, so no
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai block
under any group. See CRAWLING_METHOD.md.

chrome124 is pinned for consistency with the rest of the portfolio even
though it made no observable difference here.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.dailymirror.lk"
WARMUP_URL = f"{BASE_URL}/"

# No RSS/Atom feed or real XML news sitemap was found (see CRAWLING_METHOD.md
# -- /rss, /feed, /rss/latest-news, /sitemap.xml, /sitemap-news.xml all
# either soft-redirect to the homepage or 404; the robots.txt-advertised
# "Sitemap: https://www.dailymirror.lk/sitemaps" URL renders an HTML page,
# not an XML sitemap, and has no links to a real machine-readable sitemap).
# "latest" mode instead scrapes the site's own Breaking News category
# listing, which is confirmed newest-first by descending numeric article ID
# and supports simple offset pagination (/breaking_news/108/<offset>).
LATEST_LISTING_URL = f"{BASE_URL}/breaking_news/108"
LATEST_LISTING_PAGE_URL = f"{BASE_URL}/breaking_news/108/{{offset}}"
LATEST_PAGE_SIZE = 30  # observed offset step between listing pages

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
