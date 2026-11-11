"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-25): guardian.co.tt (Trinidad Guardian, Trinidad and
Tobago's major English-language newspaper) has NO active WAF challenge.
robots.txt is a single `User-agent: *` group with only `Crawl-delay: 10` --
no Disallow lines at all, no Claude/GPTBot/anthropic-ai block of any kind,
and no `Sitemap:` line either. chrome124 gets a clean 200 on the homepage
and article pages (served through CloudFront, but no WAF/challenge markers
observed). Real 404s confirmed on non-article-shaped paths (synthetic
unrelated path, and every RSS/sitemap path probed -- see below).

Both discovery mechanisms this project would normally reach for first were
probed and are absent entirely (not merely broken -- there is nothing there
at all): /rss, /rss.xml, /feed, /feed/, /rss/news, /sitemap.xml,
/news-sitemap.xml, /sitemap_index.xml, /googlenewssitemap.xml all return a
plain HTTP 404, and the homepage HTML contains zero mentions of "rss",
"sitemap", or "feed" (no <link rel="alternate"> either). `latest` mode
instead scrapes the homepage for article links -- see CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.guardian.co.tt"
WARMUP_URL = f"{BASE_URL}/"
LATEST_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
