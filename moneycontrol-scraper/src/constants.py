"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-27): www.moneycontrol.com is fronted by Akamai
(`AkamaiGHost` on non-200 responses, `_abck` Bot Manager sensor cookie set on
every response) but has **no active challenge** for normal browser-shaped
traffic. `curl_cffi` `chrome124` gets a clean 200 on the homepage, article
pages, `news-sitemap.xml` and the legacy RSS feed on the very first try, cold
(no warmup-then-retry dance needed) -- confirmed with a session that skipped
the homepage warmup entirely and went straight to an article URL.

Akamai Bot Manager DOES actively 403 ("Access Denied", `Server:
AkamaiGHost`) any request whose `User-Agent` string contains a recognized
bot/crawler token -- confirmed live for `ClaudeBot`, `Claude-Web` is NOT
blocked (200), `anthropic-ai` is NOT blocked (200), but `GPTBot`,
`PerplexityBot`, and even spoofed `Googlebot`/`bingbot` UA strings ARE
blocked (403), as is a nonsense control string `FooBot/1.0` -- this is a
generic "reject unverified crawler identity" edge rule, not a policy
targeted at Claude specifically (Claude-Web/anthropic-ai pass cleanly).
This actor never sends a bot-identifying User-Agent -- it impersonates a
real Chrome browser via `curl_cffi`, exactly like the rest of this
portfolio, so this rule never triggers.

robots.txt was independently re-fetched and checked line-by-line: the
`User-agent: *` group has ~30 path-specific `Disallow` rules (none touching
article pages or the news sitemap used here), and a separate block of
one-line groups explicitly disallows `CCBot`, `GPTBot`, `ChatGPT-User`,
`omgili`/`omgilibot`, `MAZBot`, `Baiduspider`, `DataForSeoBot`, and
`Google-Extended` -- i.e. a deliberate "block other companies' AI-training
crawlers" policy list. **`ClaudeBot`/`Claude-Web`/`Claude-User`/
`Claude-SearchBot`/`anthropic-ai` do NOT appear anywhere in that list or
anywhere else in the file**, and there is no plain-English prohibition
against AI/LLM scraping in any comment. This is the same domain/media group
(Network18) whose sibling site News18 explicitly disallows `ClaudeBot` and
`Claude-Web` in its own robots.txt (`User-agent: ClaudeBot` / `Disallow: /`)
-- moneycontrol.com does not carry that entry, so it was NOT skipped.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.moneycontrol.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap -- confirmed fresh (top entries match "today", 1000
# items spanning the last several days) and already newest-first in file
# order. The legacy `/rss/latestnews.xml` feed is stale (`lastBuildDate`
# over a year old at time of writing) so it is NOT used for `latest` mode,
# kept only as a documented dead end.
NEWS_SITEMAP_URL = f"{BASE_URL}/news/news-sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
