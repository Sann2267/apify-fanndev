"""Recon summary -- see CRAWLING_METHOD.md for the full writeup.

PACRA (Zambia's Patents and Companies Registration Agency) runs a separate
public "Business Search" single-page app at search.pacra.org.zm (Next.js,
statically exported). It calls a plain, unauthenticated JSON REST API on a
different subdomain/port for the actual data:

    GET https://xatu.pacra.org.zm:8344/api/v1/Search/registrysearch
        ?Searchtext=<query>&SortyBy=entity%20name&Direction=ASC

No API key, no session cookie, no CSRF/viewstate token, no WAF/CAPTCHA
observed -- confirmed working even with a bare request carrying none of the
frontend's own headers. `curl_cffi` impersonation is used anyway as this
portfolio's default posture for any external site (principle #2 in
.ai/CLAUDE.md), not because a block was ever seen.

The API caps results at 50 rows per query with no pagination parameter
discovered in the frontend bundle -- broad queries ("Zambia", "Limited",
"Trading") all returned exactly 50. Narrower/more specific company-name
queries return the true match count.

Registration-number search (advertised in the site's own placeholder text,
"Enter Registered Name or Registration Number") was tested with several
real, confirmed-valid registration numbers and consistently returned zero
results -- the endpoint appears to index/match on entityName only in
practice. Only name-based search is exposed by this actor; see
CRAWLING_METHOD.md "Known limits".
"""

SEARCH_API_URL = "https://xatu.pacra.org.zm:8344/api/v1/Search/registrysearch"
WARMUP_URL = "https://search.pacra.org.zm/"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Cache-Control": "no-store, no-cache, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://search.pacra.org.zm",
    "Referer": "https://search.pacra.org.zm/",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.5

# entityTypeId -> human-readable label. Derived from the frontend's own tab
# filter logic (entityTypeId===1 -> "Local Companies" tab, ===2 ->
# "Business Names" tab, ===4 -> "Foreign Companies" tab). Only 1 and 2 were
# ever observed in real samples; 4 is named from the frontend source even
# though no live sample surfaced one. Any other value falls back to
# f"Unknown Type {id}" in extractor.py rather than crashing -- this is a
# convenience label only, the raw entityTypeId is always passed through too.
ENTITY_TYPE_LABELS = {
    1: "Local Company",
    2: "Business Name",
    4: "Foreign Company",
}
