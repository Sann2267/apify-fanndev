"""Endpoints, headers, profile choice -- all in one place.

Recon summary (2026-08-27): the Kingdom of Tonga's "Registry Service"
(businessregistries.gov.to), operated by the Ministry of Commerce, Consumer,
Trade, Innovation and Labour (MCCTIL, formerly the Ministry of Trade and
Economic Development which commissioned the build), runs on the exact same
Foster-Moore-derived platform as PNG's IPA registry in this portfolio
(`png-ipa-scraper`) -- an ASP.NET WebForms shell (`__VIEWSTATE`/
`aspnetForm`) whose real search/profile UI is a client-side `<vue-entity-
search>` Vue component and an Angular `EntityCtrl` controller, both talking
to a clean JSON REST API. There is no `/robots.txt` at all (plain HTTP 404,
IIS default 404 body) -- no restriction of any kind, no
Claude/anthropic-ai/AI-crawler mention (there's nothing to mention). No
CDN/WAF fingerprint was observed anywhere (no `cf-ray`, no CAPTCHA, no bot
challenge) across ~30 requests during recon.

The homepage's own meta description states outright: "The Tonga Registry
Services system is a single, fully electronic solution hosting both the
Personal Property Securities Registry and Business Entities Registry. Both
registries are searchable by the general public free of charge. It is
accessible 24/7."

    GET /Api/Corp/SearchCorp?Term=<name>&PaginationPageSize=&PaginationCurrentPage=&ExcludePending=true&...
    GET /Api/Corp/GetCorpProfile?id=<CorpId guid>

Every request under `/api/` (case-insensitive) must carry a `PA-Token`
request header, sourced from a hidden `<input id="paToken">` field embedded
in the *page* HTML (e.g. `/corp/search.aspx`). Confirmed to be a lightweight
anti-CSRF/anti-scraping token -- NOT a CAPTCHA and NOT a login -- that
rotates on every response (a fresh value comes back in the response's own
`PA-Token` header and must be threaded into the next call). A stale/missing
token gets HTTP 401/403. `client.py` implements harvest-and-thread, matching
`png-ipa-scraper`'s `IpaClient` pattern exactly.

**Notably better public access than PNG IPA on this same platform:**
`GetCorpProfile` returns real, populated `Directors`, `Members`
(shareholders), `ShareAllotments`, `Addresses` (including each officer's own
residential address), and `CorpFilings` arrays for anonymous
(unauthenticated) access -- confirmed across multiple entities. `Officers`,
`Secretaries`, `Owners`, and `BeneficialOwners` were empty on every entity
tested, and `IsAuthorized`/`IsLoggedin` are always `false` for this actor
(no-login policy) -- whether that reflects a stricter gate on those specific
role types, or simply no data on file for the entities tested, was not
possible to determine without a login this actor deliberately never
attempts. Passed through as-is either way.

A `GetCorpProfile` call for a nonexistent/invalid CorpId does NOT 404 -- it
returns HTTP 200 with a placeholder record where `CompanyName` and
`RegistrationNumber` are both the literal string "N/A" (same soft-not-found
quirk as PNG IPA; confirmed live against the all-zero GUID).

A short burst of rapid same-session requests can trigger a transient
HTTP 403 `{"Message":"Search page has expired. Please refresh the page."}`
or HTTP 429 -- both resolve after a fresh token re-harvest / short backoff
(handled by `client.py`), matching the ordinary small-government-system rate
limiting also seen on PNG IPA, not an anti-bot wall.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://businessregistries.gov.to"
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

# Server-side cap observed via GetSearchConfiguration's model.PaginationPageSize
# usage in the UI selector -- kept modest to stay a good citizen of a small
# government system, not because a larger value was seen rejected.
MAX_PAGE_SIZE = 50

# CorpTypes enum, from GetSearchConfiguration's model.CorpTypes (live recon,
# 2026-08-27) -- fewer categories than PNG IPA's 13, no separate
# "Associations"/"Business Groups" types on this registry.
CORP_TYPE_IDS = {
    1: "Company",
    2: "Overseas Company",
    3: "Business Name",
    4: "Business Licence",
    5: "Foreign Certificate - Overseas Company",
    6: "Foreign Certificate - Local Company",
    7: "Foreign Certificate - Individual",
    8: "Foreign Certificate - Unincorporated Entity",
}
