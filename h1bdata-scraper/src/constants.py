"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-08-31): h1bdata.info republishes the US Department of
Labor's public LCA (Labor Condition Application) disclosure dataset --
every H-1B sponsorship filing since 2012 -- behind a plain PHP/MySQL search
UI. No WAF of any kind was found: `robots.txt` is `User-agent: * /
Disallow:` (fully open, explicit `Sitemap:` line, no Claude/AI-bot block),
and `curl_cffi` `chrome124` gets clean 200s with zero challenge markers on
the homepage, search results, and case-detail pages alike. The only
"defense" is raw response size on unfiltered queries (a single big employer
across all years can return 10MB+ of HTML in one response -- there is no
pagination, the server just renders every matching row into one page) --
this is a performance concern, not a block, and is handled by requiring at
least one narrowing filter (employer/jobTitle/city) plus a maxResults cap.

Two endpoints matter:
- `index.php?em=&job=&city=&year=` -- search results table. Columns:
  EMPLOYER, JOB TITLE, BASE SALARY (links to details.php?id=<caseId>),
  LOCATION ("City, ST"), SUBMIT DATE, START DATE.
- `details.php?id=<caseId>` -- full LCA case record as a flat label/value
  HTML table (~76 fields): wage rate + prevailing wage + wage level,
  worksite address, employer address + point-of-contact name/email,
  sponsoring attorney/law-firm name + email, visa class, full/part-time,
  certification status and dates. This is the valuable enrichment layer --
  none of it is present in the search-results table.

See CRAWLING_METHOD.md for full recon detail and captured examples.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://h1bdata.info"
SEARCH_URL = f"{BASE_URL}/index.php"
DETAIL_URL = f"{BASE_URL}/details.php"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

VALID_YEARS = (
    "All Years", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
    "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012",
)

# Unfiltered/huge-employer queries can take a while to render server-side
# (observed ~5s for a single employer/single year at ~22k rows; "All Years"
# for a large employer can run well past a minute) -- generous timeout,
# no proxy-side rush.
REQUEST_TIMEOUT = 120

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
