"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): Eswatini has no working "CIPA" web presence --
`cipa.org.sz` (the domain widely cited as "the CIPA portal" by third-party
KYC/company-search blogs) does **not resolve at all** (NXDOMAIN on every
lookup tried). The REAL, live, government-run company-name-search system is
part of Eswatini's general citizen e-services portal, "Government Online
Services", run by Government Computer Services under the Ministry of ICT,
linked directly from the official Registrar of Companies page on
`gov.sz` (departments-sp-1596706154?id=522):

    https://online.gov.sz/e-companysearch.aspx   ("Company Name Search")

Also on the same portal's "Business" menu (not used by this actor -- all
require login): Company Name Reservation (`e-reservationSignOn.aspx`),
Company Registration (`e-registrationLOGIN.aspx`), Trading and Liquor
License Application (`TradingLicenseSignOn.aspx`).

**Use `online.gov.sz` (no `www.`)** -- the TLS cert is `CN=*.gov.sz` /
SAN `*.gov.sz, gov.sz`, which does NOT cover `www.online.gov.sz` (two
subdomain labels deep). `https://online.gov.sz` validates cleanly;
`https://www.online.gov.sz` throws a hostname/cert mismatch in any client
that verifies certs (confirmed with both a bare TLS client and curl_cffi).

`robots.txt` returns a plain HTTP 404 (no file at all) -- no restrictions,
no Claude/AI-crawler mention (there's nothing to mention anything in).

No WAF observed: plain `nginx` in front of an ASP.NET 4.0 (`X-AspNet-Version:
4.0.30319`, `X-Powered-By: ASP.NET`) app. All of `curl_cffi`'s chrome124,
chrome131, safari17_0, and edge101 profiles got clean HTTP 200s with
identical bodies -- no fingerprint gate.

## The search flow (public, no login, classic ASP.NET WebForms postback)

1. `GET /e-companysearch.aspx` -- returns the search form HTML embedding
   three hidden fields required for every postback: `__VIEWSTATE`,
   `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`. The server also sets an
   `ASP.NET_SessionId` cookie on this GET -- the same `curl_cffi` session
   (cookie jar) must be reused for the following POST, or the postback is
   rejected (ASP.NET WebForms server-side validation ties `__EVENTVALIDATION`
   to the session that issued it).
2. `POST /e-companysearch.aspx` with the three hidden fields plus
   `ctl00$MainContent$txtreserve=<query>` and
   `ctl00$MainContent$Button1=search` (form-encoded, not JSON -- a real
   `<form method="post">` submission). Response is a full HTML page (NOT an
   AJAX partial) containing either:
   - an `id="MainContent_GridView1"` HTML `<table>` with columns "Company
     Name" / "Company Status" / "Date Registered" -- one `<tr>` per match,
     rendered directly server-side (ASP.NET `GridView` control), or
   - a `<span id="MainContent_Label2">No match was found for the specified
     company name</span>` marker when nothing matches (distinct, reliable
     zero-result signal -- see `extractor.NoResultsFound`).

No JSON API was found behind this UI -- the whole app is server-rendered
WebForms with no client-side JS driving the search (view-source confirms
a plain `<form>`/`<input type=submit>`, no fetch/XHR).

## No pagination, no per-record detail page

The `GridView1` table is NOT paginated -- confirmed with a broad "trading"
query that returned **3,864 result rows in one single response** (a
~1.46&nbsp;MB HTML page, ~10-25s response time). There is no "next page"
postback (`__doPostBack('GridView1','Page$2')` pattern, common on other
ASP.NET GridViews) anywhere in the markup -- every match for the query is
rendered in one page load. This actor slices to `maxResultsPerQuery`
client-side after parsing.

**There is no detail/profile page reachable without login.** Rows in the
results table are plain `<td>` text, not hyperlinks -- there is nothing to
click through to. The only three columns ever exposed by this free, public
search are: Company Name, Company Status (`COMPANY REGISTERED` /
`RESERVED`, observed values), and Date Registered. Getting anything more
(registration number, directors, addresses) requires the login-gated
Company Registration / annual-return modules on the same portal, which are
out of scope per this project's no-login policy.

## A very short/broad query can time out

A 1-2 character query (e.g. `"a"`, `"in"`) was observed to make the SERVER
itself hang (no bytes received after 60s, not a client-side issue) --
presumably it tries to render an enormous result set (tens of thousands of
rows) synchronously server-side. A 3+ character query with a somewhat
specific prefix (e.g. `"trad"`, 5,556 rows, ~10s; `"eswa"`, 6,564 rows,
~16s) reliably completes, and a realistic company-name search (`"moza"`,
138 rows, 1.8s; `"mtn"`, 42 rows, 1.2s) is fast. `MIN_QUERY_LENGTH` enforces
a floor of 3 characters client-side, and `REQUEST_TIMEOUT` is generously
set to allow a legitimately broad-but-valid query to still complete.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://online.gov.sz"
SEARCH_URL = f"{BASE_URL}/e-companysearch.aspx"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": BASE_URL,
    "Referer": SEARCH_URL,
}

MIN_QUERY_LENGTH = 3

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.5
REQUEST_TIMEOUT = 75  # broad-but-valid queries can take 20-30s server-side
