"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): dn.pt (Diario de Noticias, Portugal's oldest
daily newspaper, part of Global Media Group) has NO active WAF challenge.
`curl_cffi` chrome124/chrome116/chrome99_android/safari17_0/edge101 all get
a clean 200 on the homepage and article pages, with zero cookies set on any
request. `x-powered-by: Express` plus a `qt`-namespaced embedded JSON state
blob (`<script id="static-page">`) and `media.assettype.com` image CDN
identify the CMS as Quintype (a SaaS publishing platform used by many
international news orgs). robots.txt has ONE `User-agent: *` group with
`Allow: /` and no `Disallow` lines at all -- fully open, two Sitemap:
lines advertised. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.dn.pt"
WARMUP_URL = f"{BASE_URL}/"

# RSS feed (found via the /feed -> /stories.rss redirect; not advertised in
# robots.txt). Near-real-time, and its <content:encoded> element already
# carries the (near-)full article HTML body -- see CRAWLING_METHOD.md.
RSS_URL = f"{BASE_URL}/stories.rss"

# Google News sitemap advertised in robots.txt -- documented as an
# alternative latest-mode source, not used by this actor's fetch_latest
# (RSS is richer: it embeds the body, sitemap only has title/link/date).
NEWS_SITEMAP_URL = f"{BASE_URL}/news_sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
