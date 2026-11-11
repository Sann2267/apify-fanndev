"""Pinned facts about Glints' public surface.

Everything here was verified live during reconnaissance on 2026-09-21.
See CRAWLING_METHOD.md for the evidence behind each constant.
"""

GRAPHQL_URL = "https://glints.com/api/v2/graphql"
SITE_ROOT = "https://glints.com"
SITEMAP_INDEX = "https://glints.com/sitemap_index.xml"
# robots.txt advertises the same sitemap index and is a separate path with
# its own edge treatment, so it doubles as a discovery fallback.
ROBOTS_TXT = "https://glints.com/robots.txt"

# Glints operates six SEA markets. The site paths differ per market
# (/id, /sg, /vn, ...) but one GraphQL host serves all of them.
COUNTRIES = ["ID", "SG", "VN", "MY", "PH", "TW"]
DEFAULT_COUNTRY = "ID"

# Which site path prefix to build public URLs under, per market.
COUNTRY_PATH = {
    "ID": "id", "SG": "sg", "VN": "vn",
    "MY": "my", "PH": "ph", "TW": "tw",
}

# searchJobsV3 silently truncates anything above 50. Asking for 100 or 200
# returns exactly 50, with no error and hasMore still true.
MAX_PAGE_SIZE = 50

# page >= 2 answers 403 {"message": "please login for more information"}.
# Anonymous callers get page 1 only; see SEARCH_LOGIN_GATE below.
ANON_MAX_PAGE = 1
SEARCH_LOGIN_GATE = "please login for more information"

# curl_cffi impersonation ladder. Glints sits behind Cloudflare but the zone
# does not gate on JA3 - all five profiles returned 200 on the same IP during
# recon. The ladder is kept as insurance for a future policy change, not
# because any profile is currently required. chrome124 leads because it is the
# quietest of the five (no Client Hints mismatch against the UA we send).
TLS_PROFILES = ["chrome124", "safari17_0", "firefox133", "edge101", "chrome99_android"]

# Body markers that mean "challenged" rather than "answered". Cloudflare
# returns 200 with a challenge body, so status alone is not enough.
BLOCK_MARKERS = (
    "just a moment",
    "cf-mitigated",
    "cf_chl_opt",
    "attention required",
    "checking your browser",
    "/cdn-cgi/challenge-platform",
)

# Enum values lifted straight from the introspected schema, so input
# validation rejects a typo instead of silently returning an unfiltered page.
JOB_TYPES = [
    "FULL_TIME", "PART_TIME", "INTERNSHIP", "CONTRACT",
    "TEMPORARY", "FREELANCE", "DAILY", "PROJECT_BASED",
]
WORK_ARRANGEMENTS = ["ONSITE", "HYBRID", "REMOTE"]
LAST_UPDATED_RANGES = ["PAST_24_HOURS", "PAST_WEEK", "PAST_MONTH", "ANY_TIME"]
EDUCATION_LEVELS = [
    "PRIMARY_SCHOOL", "SECONDARY_SCHOOL", "HIGH_SCHOOL", "DIPLOMA",
    "COLLEGE_DEGREE", "BACHELOR_DEGREE", "MASTER_DEGREE",
    "DOCTORATE", "PROFESSIONAL_EDUCATION",
]
SORT_BY = ["RELEVANCY", "LATEST", "SALARY"]
JOB_SOURCES = ["NATIVE", "SUPER_POWERED"]

# Sitemap families in sitemap_index.xml, keyed by what they enumerate.
# 'job' holds Glints-native postings, 'sourced' holds aggregated third-party
# postings (these carry externalApplyURL instead of an on-site application).
SITEMAP_FAMILIES = {
    "job": "sitemap_job_{cc}_",
    "sourced": "sitemap_sourced_job_{cc}_",
    "company": "sitemap_company_{cc}_",
}

RECORD_JOB = "JOB"
RECORD_JOB_DETAIL = "JOB_DETAIL"
RECORD_COMPANY = "COMPANY"
RECORD_FILTERS = "SEARCH_FACETS"
RECORD_SUGGESTION = "SUGGESTION"
RECORD_SKILL = "SKILL"
RECORD_ERROR = "ERROR"
