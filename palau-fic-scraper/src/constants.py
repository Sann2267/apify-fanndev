"""Endpoints, headers, profile choice -- all in one place.

Recon summary (2026-08-27): the Republic of Palau's "Registry Services"
system (palauregistries.pw), operated by the Financial Institutions
Commission (FIC), runs on the exact same Foster-Moore-derived platform as
PNG's IPA registry, Tonga's MCCTIL registry, Fiji's ROC registry, and the
Solomon Islands' SBR registry already in this portfolio -- an ASP.NET
WebForms shell (`__VIEWSTATE`/`aspnetForm`) whose real search/profile UI
talks to a clean JSON REST API. There is no `/robots.txt` at all (plain HTTP
404, IIS default 404 body) -- no restriction of any kind, no
Claude/anthropic-ai/AI-crawler mention (there's nothing to mention). No
CDN/WAF fingerprint was observed anywhere (no `cf-ray`, no CAPTCHA, no bot
challenge).

The homepage's own meta description states outright: "The Palau Registry
Services system is a single, fully electronic solution hosting both the
Personal Property Securities Registry and Business Entities Registry. Both
registries are searchable by the general public free of charge. It is
accessible 24/7." A public notice on the FIC's own site
(ropfic.org/2025/01/20/public-notice-new-online-corporate-registry/)
confirms the new online registry launched 20 January 2025 alongside a new
Corporations Act.

    GET /Api/Corp/SearchCorp?Term=<name>&PaginationPageSize=&PaginationCurrentPage=&ExcludePending=true&...
    GET /Api/Corp/GetCorpProfile?id=<CorpId guid>

Every request under `/api/` (case-insensitive) must carry a `PA-Token`
request header, sourced from a hidden `<input id="paToken">` field embedded
in the *page* HTML (e.g. `/corp/search.aspx`). Confirmed to be a lightweight
anti-CSRF/anti-scraping token -- NOT a CAPTCHA and NOT a login -- that
rotates on every response (a fresh value comes back in the response's own
`PA-Token` header and must be threaded into the next call). A stale/missing
token gets HTTP 401/403 or a soft `{"Message":"Search page has expired.
Please refresh the page."}` payload. `client.py` implements harvest-and-
thread, matching this portfolio's other Foster-Moore-derived actors.

**Notably rich public access, matching Tonga rather than PNG on this same
platform:** `GetCorpProfile` returns real, populated `Directors`, `Officers`,
`Members` (shareholders), `ShareAllotments`, `Addresses`, and `CorpFilings`
arrays for anonymous (unauthenticated) access -- confirmed live against
"ASIA PACIFIC COMMERCIAL BANK, INC." (registration 10000895): 4 directors, 2
officers, 3 members, 3 share allotments, 2 addresses, and 1 filing, all
while `IsAuthorized`/`IsLoggedin` are `false`. `Secretaries`, `Owners`, and
`BeneficialOwners` were empty on the entity tested -- passed through as-is
either way (no-login policy, never attempted).

A `GetCorpProfile` call for a nonexistent/invalid CorpId does NOT 404 -- it
returns HTTP 200 with a placeholder record where `CompanyName` and
`RegistrationNumber` are both the literal string "N/A" (same soft-not-found
quirk as PNG IPA / Tonga MCCTIL; confirmed live against the all-zero GUID).

A `SearchCorp` call using a stale/already-used token returns HTTP 200 with
`{"Message":"Search page has expired. Please refresh the page."}` instead of
`{"records": [...]}` -- confirmed live on a genuinely empty-result search
term right after a prior successful call on the same harvested token. A
fresh token harvest immediately resolves it (`records: []`). `client.py`
treats this payload shape the same as a 401/403: one token re-harvest and
retry before giving up.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://palauregistries.pw"
SEARCH_PAGE_URL = f"{BASE_URL}/corp/search.aspx"
PROFILE_PAGE_URL = f"{BASE_URL}/Corp/EntityProfile.aspx"
SEARCH_API_URL = f"{BASE_URL}/Api/Corp/SearchCorp"
PROFILE_API_URL = f"{BASE_URL}/Api/Corp/GetCorpProfile"

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}

API_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0

# Server-side cap kept modest to stay a good citizen of a small government
# system, not because a larger value was seen rejected.
MAX_PAGE_SIZE = 50

# CorpTypes enum, from GetSearchConfiguration's model.CorpTypes (live recon,
# 2026-08-27) -- only 4 categories on this registry, matching the meta
# keywords on the homepage ("Palau For Profit Corporation, Foreign For
# Profit Corporation, Palau Nonprofit Corporation, Foreign Nonprofit
# Corporation") -- no separate Business Name/Business Licence types like
# Tonga's registry on the same platform.
CORP_TYPE_IDS = {
    1: "Palau For Profit Corporation",
    2: "Foreign For Profit Corporation",
    3: "Palau Nonprofit Corporation",
    4: "Foreign Nonprofit Corporation",
}
