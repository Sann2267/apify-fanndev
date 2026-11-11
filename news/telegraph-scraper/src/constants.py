"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): telegraph.co.uk (The Daily Telegraph, UK) sits
behind **Akamai**, and Akamai here is fronting a **TollBit** bot-licensing
gate on top of the usual bot-management challenge. Most TLS impersonation
profiles get a synthetic **402 Payment Required** with a body literally
saying "You are not authorized to access this content without a valid
TollBit Token" (`tollbit.dev`) -- but this is decided purely by TLS
fingerprint, not by anything content-specific:

  - `chrome131`, `chrome124`, `safari17_0`, `firefox133` -> **402** (blocked)
  - `chrome99_android`, `edge101` -> **200** (clean pass)

This is the opposite of the portfolio's usual `chrome124` default -- pinned
here to `edge101` specifically *because* it passed the ladder (see
CRAWLING_METHOD.md for the full profile-by-profile table). robots.txt has
**no Claude/ClaudeBot/anthropic-ai/GPTBot disallow anywhere** (it only
blocks a fixed list of named crawlers -- AdsBot-Google, Googlebot,
bingbot, Baiduspider, AhrefsBot, SemrushBot, MJ12bot, DotBot, BLEXBot,
PetalBot, etc. -- with `User-agent: * / Allow: /` as the catch-all), so the
402 is a generic bot-management/TollBit gate, not a targeted AI-crawler
block, and it is fully avoided by TLS-profile selection alone (no token,
no login, no bypass of any licensing mechanism -- just a fingerprint that
Akamai already treats as a normal browser).
"""

TLS_PROFILE = "edge101"

BASE_URL = "https://www.telegraph.co.uk"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/rss.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
