"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): namibian.com.na (The Namibian, Namibia's
largest daily newspaper, est. 1985) has NO active WAF challenge. The site
is nginx + CloudFront fronted (X-Cache/X-Amz-Cf-* headers) but that's
CDN/analytics only -- no _abck/bm_sz/_px3/_dd_s bot-manager cookie was
ever set, no cf-ray, no challenge body. chrome124 gets a clean 200 on the
homepage, article pages (staff + wire-service), and the RSS feed.
robots.txt has TWO User-agent groups (`*` and `AdsBot`), each with its own
dedicated Yoast-generated Disallow block directly beneath it -- no
shared/merged block across groups (the Babak-14 false-clean parser bug
pattern does not apply here), and no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai token anywhere in the file. See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.namibian.com.na"
WARMUP_URL = f"{BASE_URL}/"

# WordPress default RSS feed. Not disallowed in robots.txt. Carries full
# article HTML in <content:encoded> -- latest mode gets complete article
# text with zero extra per-item HTTP calls (see CRAWLING_METHOD.md).
# WordPress paginates via ?paged=N (12 items/page observed) so `limit`
# above 12 triggers additional page fetches.
RSS_FEED_URL = f"{BASE_URL}/feed/"
RSS_PAGE_SIZE = 12

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
