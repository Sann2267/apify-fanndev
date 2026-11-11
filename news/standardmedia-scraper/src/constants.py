"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): standardmedia.co.ke (The Standard, Kenya --
one of Kenya's oldest daily newspapers, published by The Standard Media
Group) shows NO active WAF challenge. The site is Cloudflare-fronted
(`server: cloudflare`, `cf-ray`) but only as a CDN -- homepage, article
pages, and the Google News sitemap all return a clean 200 with chrome124
on the first try, and the only cookies set are a Laravel `XSRF-TOKEN` /
`thestandardmediagroup_session` pair (framework session plumbing, not a
bot-manager challenge cookie like `cf_clearance`/`__cf_chl_*`). No
profile-ladder escalation was needed.

`robots.txt` has a SINGLE `User-agent: *` group with an EMPTY `Disallow:`
-- every path is allowed, including `/sitemaps/*` and `/<section>/article/*`.
No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`,
or `anthropic-ai` token appears anywhere in the file (re-verified fresh,
reading the single group's Disallow line directly -- see CRAWLING_METHOD.md
for the full text and the "Babak 14" merged-Disallow-parser-bug context
this was re-checked against).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.standardmedia.co.ke"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, advertised via `sitemap:` lines in robots.txt.
# Confirmed to carry same-day articles (freshest item observed dated the
# day of the fetch) across a broad mix of sections (national, opinion,
# crime-and-justice, ...). The `business`/`sports` "section" sitemaps in
# robots.txt were probed and found to return either the same generic feed
# (businesssitemap) or malformed article URLs missing the `/article/`
# path segment (sports/googlenews) -- see CRAWLING_METHOD.md. This one
# feed is therefore the sole `latest`-mode source used.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemaps/googlenews.php"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
