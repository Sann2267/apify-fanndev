"""Shared constants for the Sri Lanka Ministry of Finance procurement-notices
scraper.

See CRAWLING_METHOD.md for how these URLs / TLS profile were discovered and
verified. The site (`www.treasury.gov.lk`) is a Next.js (React SSR)
application -- every page ships its data pre-rendered inline in a
`<script id="__NEXT_DATA__">` JSON blob, so this actor parses that instead of
CSS-selecting HTML (more stable across cosmetic redesigns, per the
JSON-LD > __NEXT_DATA__ > HTML priority order).
"""

BASE = "https://www.treasury.gov.lk"

# "Current" notices -- a single page, no query params, holding whatever the
# Ministry currently has open (~20 at a time as of 2026-08-27). Its Next.js
# pageProps shape is {"notices": [...], "count": N}.
CURRENT_NOTICES_URL = f"{BASE}/procurement/procurement-notices"

# "Archive" -- a paginated CMS listing of every procurement notice ever
# published on this page going back to 2018/2019, independent of the buildId
# (path-based routing, not a Next.js dynamic-data fetch). Its Next.js
# pageProps shape is {"sections": [...], "count": N, "page": N}. Page numbers
# start at 1; requesting a page past the last one returns a real HTTP 404
# (not an empty 200), which is how this actor detects "end of archive"
# without hardcoding a page count that will grow over time (23 pages / 460
# notices as of 2026-08-27).
ARCHIVE_URL_TMPL = f"{BASE}/p/procurement-notices/{{page}}"

# Individual attachment download endpoint for CURRENT notices. Each
# attachment in a current notice's "attachments" list only carries a bare
# UUID as its "link" field (not a full path) -- this is the documented
# pattern for turning it into a real URL. Verified to serve the real PDF with
# no auth (see CRAWLING_METHOD.md).
CURRENT_FILE_DOWNLOAD_URL_TMPL = f"{BASE}/api/file/{{file_id}}"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

# Safety cap on how many archive pages a single run will walk, independent of
# maxResults -- guards against a pathological loop if the upstream 404-at-end
# behavior ever changes (e.g. starts returning empty 200s forever instead).
MAX_ARCHIVE_PAGES_PER_RUN = 100
