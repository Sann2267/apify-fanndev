"""Endpoints, headers, and recon summary for Samoa's official company register.

Recon summary (2026-08-26/27): Samoa's company register is run by the
**Ministry of Commerce, Industry and Labour (MCIL)** under the Companies Act
2001. The public marketing site is `mcil.gov.ws` (Drupal); the actual
transactional "Business Registries" application lives on a separate domain,
`www.businessregistries.gov.ws`, and is a search-the-register / online-filing
portal ("Online Samoa Company Registry"). Its footer/branding says "Ministry
of Commerce, Industry & Labour" -- no vendor name is printed anywhere, but
the app's own cookie name (`x-catalyst-session-global`), JS globals
(`webuiConfig`, `catCallback`, `catHtmlFragmentCallback`), and the general
shape of the protocol (a per-session "view instance" state machine driving a
server-rendered form) are the same "Catalyst" framework family seen on
Botswana's CIPA (`botswana-cipa-scraper`) -- but this is an OLDER, jQuery-
driven generation, not the Vue3 "Verne" SPA used there. The wire protocol is
therefore completely different from `botswana-cipa-scraper` (custom
`multipart/x-www-form-urlencoded` POSTs with `_CBNODE_`/`_VIKEY_`-style
params and HTML-comment-delimited fragments, not JSON `commands` batches) --
see CRAWLING_METHOD.md for the full reverse-engineered protocol.

`robots.txt` on `www.businessregistries.gov.ws` is a plain HTTP 404 (the file
does not exist) -- no restriction of any kind, so no Claude/AI-crawler
mention either (there's nothing to mention). `mcil.gov.ws` (the unrelated
marketing site, never touched by this actor) has a stock Drupal robots.txt,
also with no AI-crawler mentions.

**"Company Search" (`/samoa-br-companies/service/create.html?...&service=
registerItemSearch`) is fully public -- no login, no account, no CAPTCHA.**
A "Logon / Register" link is present in the nav but is entirely optional; the
search form renders and works for a guest session. Confirmed with real,
current data: searching "Bank" returns Bank South Pacific (Samoa), ANZ Bank
(Samoa), Samoa Commercial Bank, and The National Bank of Samoa -- all with
real registration numbers, incorporation dates, and addresses. Opening any
match's full profile (General Details / Addresses / Directors / Shareholders
/ Share Parcels / Filings tabs) returns real director names, residential
addresses, shareholdings, and filing history with **zero login wall on any
tab** -- confirmed against Bank South Pacific (Samoa) Limited's 24 directors
(current and ceased) and 8 shareholders (individuals and corporate entities
like BSP Financial Group Limited).

No WAF, no Cloudflare, no CAPTCHA, no TLS-fingerprint gate observed anywhere
during recon -- plain `nginx` + `PHP/8.2.31` on the WordPress-fronted
marketing pages, and the same plain `nginx` in front of the Catalyst app.
`curl_cffi` `chrome124` is used for portfolio-wide consistency; a bare
`curl` baseline (no impersonation at all) also worked fine for every request
tried during recon.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.businessregistries.gov.ws"
SEARCH_START_URL = (
    f"{BASE_URL}/samoa-br-companies/service/create.html"
    "?targetAppCode=samoa-master&targetRegisterAppCode=samoa-br-companies"
    "&service=registerItemSearch&target=samoa-br-companies"
)

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Headers the live site's own jQuery AJAX layer sends on every fragment/tab
# POST (see `webuiConfig.headers()` in the shipped JS bundle). `x-security-
# token` is the literal string "null" (not an empty header) whenever the
# `x-security-token` cookie itself is empty, which is the guest-session norm.
AJAX_HEADERS = {
    "x-security-token": "null",
    "x-catalyst-async": "true",
    "x-catalyst-secured": "true",
    "X-Requested-With": "XMLHttpRequest",
}

# Tabs on a company's detail ("View Private/Public Company Details") page,
# in the fixed order the site itself renders them (tab index 0 -- "General
# Details" -- is embedded directly in the initial detail-page HTML, no extra
# POST needed; tabs 1-5 each require one `tabSelect` fragment POST).
DETAIL_TABS = {
    1: "addresses",
    2: "directors",
    3: "shareholders",
    4: "shareParcels",
    5: "filings",
}

RESULTS_PAGE_SIZE = 10  # confirmed from the pager's own kv metadata (10 rows/page)

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
