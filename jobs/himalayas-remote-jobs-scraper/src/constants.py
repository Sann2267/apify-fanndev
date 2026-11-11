"""Endpoint, limits and the filter fields this Actor implements itself.

Source: ``himalayas.app/jobs/api`` -- the remote-jobs feed Himalayas publishes
for exactly this purpose. The response's own ``comments`` field documents the
cursor pagination, so this is a published interface, not a private one.

Recon 2026-09-18, plain HTTP, no proxy, no cookie, no login:

* ``GET /jobs/api`` -- 200 ``application/json``. Envelope:
  ``comments``, ``updatedAt``, ``offset``, ``limit``, ``totalCount``,
  ``nextCursor``, ``jobs[]``. ``totalCount`` was **97,007**.
* Each job carries title, excerpt, full HTML description, company name + slug +
  logo, employment type, min/max salary with currency and period, seniority,
  categories, parentCategories, location and timezone restrictions,
  applicationLink, guid and pubDate.
* ``?cursor=<nextCursor>`` walks the feed. Three pages were fetched with
  **zero repeated guids**.
* The HTML site is a different story: ``/companies/api``, ``/companies/<slug>``
  and ``/jobs/<slug>`` all answer **403**. Only the JSON feed is open, which is
  why every mode here is built on it.

Two limits that decide this Actor's whole design:

* **``limit`` is hard-capped at 20.** ``limit=21``, ``50``, ``100``, ``200``
  and ``500`` all return exactly 20 jobs. Reaching a meaningful slice of
  97,000 jobs therefore means walking the cursor, not asking for a big page.
* **Every filter parameter is silently ignored.** ``query=python``,
  ``categories=Design``, ``seniority=Entry-level``, ``employmentType``,
  ``company``, ``minSalary`` and ``locationRestrictions`` are all accepted with
  HTTP 200 and change nothing -- ``categories=Design`` returned AI/ML
  engineering roles. An Actor that forwarded them would look like it filtered
  and quietly return unfiltered data, so **all filtering in this Actor happens
  locally, over records already fetched**.
"""

BASE = "https://himalayas.app"
URL_JOBS = BASE + "/jobs/api"

# No WAF was seen on the JSON feed; chrome124 is the portfolio default and
# answered 200 on every probe. chrome131 is deliberately not first (it is
# widely blocklisted in 2026, .ai/CLAUDE.md rule 2).
TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

MODES = ("jobs", "search", "companies", "reference")

# The server's own ceiling, proven by probe. Asking for more is not an error,
# it just quietly gives 20.
PAGE_LIMIT = 20

# A cursor walk has to stop somewhere even when the caller asks for more items
# than the feed holds.
MAX_PAGES = 1000

# Fields a caller may filter on locally, mapped to how they are compared.
# 'text' matches case-insensitive substrings; 'list' matches any element;
# 'min'/'max' compare numerically.
FILTER_FIELDS = {
    "titleContains": ("title", "text"),
    "companyContains": ("companyName", "text"),
    "descriptionContains": ("description", "text"),
    "categories": ("categories", "list"),
    "parentCategories": ("parentCategories", "list"),
    "seniority": ("seniority", "list"),
    "locationRestrictions": ("locationRestrictions", "list"),
    "employmentType": ("employmentType", "text"),
    "salaryPeriod": ("salaryPeriod", "text"),
}
