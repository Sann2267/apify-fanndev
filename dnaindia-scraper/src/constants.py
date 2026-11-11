"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-27): dnaindia.com (DNA India -- Daily News & Analysis,
published by Zee Media Corporation Ltd, major English-language national
daily) sits behind **Akamai** (`errors.edgesuite.net` deny page on a plain
UA-only `curl`/`requests` baseline) but shows NO active challenge under TLS
impersonation -- `curl_cffi` `chrome124` returns a clean 200 on the homepage,
every sampled article page, `robots.txt`, and the Google News sitemap on the
first try, no profile-ladder escalation needed.

`robots.txt` (`https://www.dnaindia.com/robots.txt`) has a notable quirk: a
`User-agent: ClaudeBot` group (bundled with ChatGPT/GPTBot/PerplexityBot/
claude-web/Google-Extended/SemrushBot/Yandex) carries **zero** Allow/Disallow
directives before the next group starts -- i.e. an empty ruleset, which per
RFC 9309 semantics means nothing is disallowed for those agents (same effect
as the default `Allow: /` already in the `User-agent: *` group above it).
This differs from this portfolio's established skip precedent (USA Today,
Politico, The Hill all carry an explicit `Disallow: /` attached to the
ClaudeBot line by name) -- no such directive exists here. Treated as
NOT BLOCKED per that precedent, but flagged for human review since the
empty-group authoring is unusual and the intent is ambiguous (see
CRAWLING_METHOD.md for the full text and reasoning).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.dnaindia.com"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, referenced from robots.txt (`Sitemap:` line). Confirmed
# live: 98 entries, same-day freshness, each carrying <loc>, <news:title>,
# <news:publication_date> (real per-article ISO 8601 timestamp), and
# <news:keywords>. No site-wide RSS feed was probed for since this sitemap
# already satisfies the `latest`-mode freshness requirement with a real title
# and timestamp in one lightweight XML request.
GOOGLE_NEWS_SITEMAP_URL = f"{BASE_URL}/googlenews.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
