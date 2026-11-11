"""Constants for the PRAZ (Procurement Regulatory Authority of Zimbabwe)
electronic Government Procurement (eGP) system scraper.

Platform: egp.praz.org.zw, built by "Nextenders (India) Pvt Ltd"
(confirmed via <meta name="Creator" content="Nextenders India Private
Limited"/> on every page, and the footer copyright) -- a CakePHP web app,
BigIP/AWS-ALB fronted. A NEW e-GP vendor lineage for this portfolio (not
European Dynamics/ePPS, Perago Systems, TenderLink, Bonfire, or the
Korean-origin Rwanda platform seen in earlier tender-vertical actors).
See CRAWLING_METHOD.md for the full recon writeup.
"""

BASE_URL = "https://egp.praz.org.zw"

# "Live Tenders" bulletin board -- currently-open tenders. Page 1 has no
# query params; page 2+ needs the exact CakePHP paginator URL shape below
# (confirmed live: content differs page to page, real server-side pagination).
LIVE_TENDERS_URL = f"{BASE_URL}/Indexes/index"
LIVE_TENDERS_PAGE_URL = (
    f"{BASE_URL}/index?url=Indexes%2Findex&page={{page}}&direction=BulletinBoardLive.id"
)

# "Former Opportunities" (a.k.a. Past Tenders) -- historical/closed tenders,
# 64,000+ records observed live. Same real-pagination behaviour as Live Tenders.
FORMER_TENDERS_URL = f"{BASE_URL}/Indexes/getFormerOpportunities"
FORMER_TENDERS_PAGE_URL = (
    f"{BASE_URL}/indexes/get-former-opportunities"
    f"?url=Indexes%2FgetFormerOpportunities&page={{page}}&direction=BulletinBoardConcluded.id"
)

# Award Notices -- most recent contract awards (awardee, contract amount).
# NOTE: pagination for this listing is a confirmed no-op (see CRAWLING_METHOD.md
# "Known limits") -- ?page=2/3/... returns byte-identical rows to page 1. The
# page-URL constant is kept for completeness/future-proofing; main.py's
# generic same-page dedup guard is what actually protects against this.
AWARD_NOTICES_URL = f"{BASE_URL}/Indexes/getAwardNotices"
AWARD_NOTICES_PAGE_URL = (
    f"{BASE_URL}/indexes/get-award-notices"
    f"?url=Indexes%2FgetAwardNotices&page={{page}}&direction=BulletinBoardAward.id"
)

# Detail pages -- confirmed open with NO login wall regardless of tender
# status (live, closed, awarded, cancelled) or award age. This is notably
# more open than several other e-GP platforms in this portfolio (e.g.
# Zambia's ePPS login-walls detail once the bid deadline passes).
TENDER_DETAIL_URL = f"{BASE_URL}/Indexes/viewLiveTenderDetails/{{tender_id}}"
AWARD_DETAIL_URL = f"{BASE_URL}/Indexes/viewAwardNotice/{{award_id}}"

TLS_PROFILE = "chrome124"  # no WAF/CAPTCHA found; used per this portfolio's default posture

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.5
MAX_PAGES_HARD_CAP = 5000
