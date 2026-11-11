"""Endpoints, headers, profile choice -- all in one place.

Recon summary (2026-08-27): the Papua New Guinea Investment Promotion
Authority's "PNG Registry Services" system (www.ipa.gov.pg) runs on Azure
App Service (`ARRAffinity`/`ARRAffinitySameSite` cookies, `x-powered-by:
ASP.NET`) with a hybrid ASP.NET WebForms shell + client-side Angular/Vue
widgets. There is no `/robots.txt` at all (plain HTTP 404 on both
`www.ipa.gov.pg/robots.txt` and the bare `ipa.gov.pg` -- which also fails
TLS hostname verification and is not used). No WAF/CAPTCHA of any kind was
observed anywhere in this recon.

The site's own homepage meta description states outright: "The Papua New
Guinea Registry Services system is a single, fully electronic solution
hosting both the Personal Property Securities Registry and Business
Entities Registry. Both registries are searchable by the general public
free of charge. It is accessible 24/7."

The "Business Entity Search" (`/corp/search.aspx`) and "Entity Profile"
(`/Corp/EntityProfile.aspx?id=<guid>`) pages render their real content
entirely client-side -- a `<vue-entity-search>` Vue component drives search,
an Angular `EntityCtrl` controller drives the profile page -- and BOTH call
a clean JSON REST API directly. No ASP.NET postback / `__VIEWSTATE` dance is
needed for the actual data, only for the (unused, login-gated) internal
"workflow" admin features that share the same page shell:

    GET /Api/Corp/SearchCorp?Term=<name>&PaginationPageSize=&PaginationCurrentPage=&ExcludePending=true&...
    GET /Api/Corp/GetCorpProfile?id=<CorpId guid>

Every request under `/api/` (case-insensitive) must carry a `PA-Token`
request header, sourced from a hidden `<input id="paToken">` field embedded
in the *page* HTML (e.g. `/corp/search.aspx`, `/Corp/EntityProfile.aspx`).
This is confirmed (via `/bundles/js/GlobalAjaxInterceptor`) to be a
lightweight per-session anti-scraping/anti-CSRF token -- NOT a CAPTCHA and
NOT a login. Any XHR/fetch to an `/api/` path gets this header auto-attached
client-side, and the token *rotates* on every response (a fresh value comes
back in the response's own `PA-Token` header and must be threaded into the
next call). A stale/missing token gets HTTP 401
`{"Message":"Invalid API Token"}`. See `client.py` for the harvest-and-thread
implementation.

**Known, deliberate limitation:** `GetCorpProfile` returns `IsAuthorized:
false` for every anonymous request tested (old and brand-new companies
alike), and the `Officers`, `Directors`, `Secretaries`, `Shares`, `Owners`,
and `BeneficialOwners` arrays are consistently EMPTY for anonymous access --
that data is gated behind an authenticated IPA Online account, which this
actor deliberately does not attempt to obtain or use (no-login policy). What
IS public and reliably populated: entity name (+ prior names), registration
number, registration date, status, entity type, registered office + postal
address, business activities, total shares, annual return due date, and
(for some entities) a contact email/phone captured at registration.

A `GetCorpProfile` call for a nonexistent/invalid CorpId does NOT 404 -- it
returns HTTP 200 with a placeholder record where `CompanyName` and
`RegistrationNumber` are both the literal string `"N/A"` (soft-not-found
quirk, handled explicitly in `extractor.py`).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.ipa.gov.pg"
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
# usage in the UI (10/20/50 selector) -- kept modest to stay a good citizen of
# a small government system, not because a larger value was seen rejected.
MAX_PAGE_SIZE = 50
