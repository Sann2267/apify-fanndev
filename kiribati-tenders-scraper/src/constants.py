"""Shared constants for Kiribati's Central Procurement Unit (Ministry of
Finance and Economic Development) tender list, `procurement.gov.ki`.

See CRAWLING_METHOD.md for the full recon writeup. Short version: a Drupal
site whose `/tender-list` page is a single chronological table (not split
into current/closed views) covering both open and long-closed tenders --
observed going back to at least 2021 across 50+ pages at recon time,
paginated with Drupal's standard `?page=N` (0-indexed) offset, 10 rows per
page.

Each row: Procurement No. (reference code, links to a per-tender detail
Drupal node), Procuring Entity (a ministry acronym -- MOE, MFED, MCIA,
etc.), Brief Description, Open Date, Close Date. The detail node additionally
carries downloadable tender documents, but is NOT fetched by this actor --
the archive is large (50+ pages observed, likely 500+ records), so an N+1
per-item detail fetch was judged not worth the added request volume for
data (document links) that most users of a "what tenders exist" feed won't
need per record; `detailUrl` is included so a user can open a specific
tender's documents themselves.

`https://procurement.gov.ki/robots.txt` is a stock Drupal robots.txt
(`Disallow` limited to internal system paths -- `/admin/`, `/user/login/`,
etc.) with no Claude/AI-crawler-specific group.
"""

BASE = "https://procurement.gov.ki"

TENDER_LIST_URL = f"{BASE}/tender-list"

PAGE_SIZE = 10  # Drupal's fixed page size for this view, observed at recon time

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
