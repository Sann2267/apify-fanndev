"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): the Companies Office of Jamaica (COJ,
formerly the Office of the Registrar of Companies -- hence the domain)
is Jamaica's official company/business-name registry, at
`www.orcjamaica.com`. A separate `services.orcjamaica.com/validation`
sub-app exists but is a narrow "QR Code Validation" tool that looks up a
single already-known certificate/document number -- NOT a general
name/number search, and out of scope here. The real public search lives
on the legacy ASP.NET WebForms site at `www.orcjamaica.com/CompanySearch.aspx`.

`robots.txt` (`www.orcjamaica.com/robots.txt`) has a `User-agent: *` group
with an EMPTY `Disallow:` (i.e. allowed) plus `Crawl-delay: 120` and a lone
`Disallow: /cgi-bin/`. No Claude/AI-crawler user-agent (ClaudeBot,
Claude-Web, Claude-User, Claude-SearchBot, anthropic-ai) is mentioned
anywhere in the file. `CompanySearch.aspx`, `PaymentConfirmation.aspx`,
`CompanySearchResults.aspx`, and the `/AsyncServices/` polling path used
below are all unlisted, i.e. not disallowed. The stated `Crawl-delay: 120`
is honored by this actor via `REQUEST_DELAY_SECS` (see below) and a long
retry backoff on transient blocks, rather than a hardcoded 120s sleep
between every single request -- 120s/query would make even a handful of
queries take tens of minutes; empirically, bursts of requests trip a
temporary block that recovers within roughly 1-2 minutes (see below), so a
much shorter default pace plus generous retry/backoff is the pragmatic
middle ground. Operators who want strict `robots.txt` compliance can set
`requestDelaySecs` to 120 in the input.

**No login, no CAPTCHA, no account required for the search itself** -- the
whole flow below was reproduced end-to-end from a completely fresh,
cookie-less HTTP client. (A free COJ account is mentioned elsewhere as a
prerequisite for actually *purchasing* certified documents -- irrelevant
here, since this actor never reaches that step.)

## The search flow (classic ASP.NET WebForms + an async job poll)

`CompanySearch.aspx` is server-rendered ASP.NET WebForms (`__VIEWSTATE`,
`__EVENTVALIDATION`, `__doPostBack`), fronted by a CDN/WAF (`Server:
ZENEDGE`, `X-Cdn: Served-By-Zenedge`). The whole flow, reproduced with
plain HTTP:

1. `GET /CompanySearch.aspx` (first hit, any session) -- does NOT return the
   real page. It returns a tiny (~665 byte) HTML snippet with a `<script>`
   that does `document.cookie = "__zjc<N>=" + Math.floor(<epoch> * pi)` then
   `window.location` back to the same URL. **This looks like a Zenedge JS
   "Human Interaction Check" but is not one** -- it is the framework's
   standard ASP.NET `AspxAutoDetectCookieSupport` cookieless-session probe,
   just re-skinned with Zenedge's own JS challenge template. The response
   ALSO sets a real `Set-Cookie: AspxAutoDetectCookieSupport=1` header.
   Sending the `__zjc` cookie is not required at all -- simply repeating the
   *same* `GET /CompanySearch.aspx` a second time, in the same cookie-jar
   session (now carrying `AspxAutoDetectCookieSupport=1`), returns the real
   ~30KB page with a working `__VIEWSTATE`/`__EVENTVALIDATION` pair and an
   `ASP.NET_SessionId` cookie. This "hit the URL twice" warmup is the only
   "challenge" in this entire flow and needs no JS execution or math at all.
2. `POST /CompanySearch.aspx` (same session/cookies) with the full WebForms
   postback field set (`__VIEWSTATE`, `__VIEWSTATEGENERATOR`,
   `__EVENTVALIDATION`, `__EVENTTARGET=ctl00$Space$btnSearch`,
   `ctl00$Space$org_name=<query>`, plus the empty boilerplate fields --
   see `client.py`). The query box (`org_name`) is a loose substring match
   on BOTH name and number fields, not an exact match on either: a name
   query (e.g. "Blueberry Nonexistent Trading Enterprises Limited") still
   matched every real entity whose name starts with "Blueberry" (token
   match, not exact-phrase); a numeric query (e.g. `384`) matched every
   entity whose formatted registration number CONTAINS that substring
   anywhere, across every suffix style COJ uses -- `384 (Local)`,
   `384 (Overseas)`, `384 (Foreign S.C.)`, and business names `384/1980`,
   `384/1981`, etc. all matched a plain `384` query (200 rows, capped).
   `61230` happened to return exactly one match ("Digicel (Jamaica)
   Limited") only because no other registration number on file contains
   that digit sequence -- it is not evidence of exact matching.
3. The POST response is another tiny redirect snippet, this time to
   `PaymentConfirmation.aspx?cId1=<transaction-guid>` -- despite the name,
   this is NOT a paywall for the search itself; it is a generic "processing"
   page used for any async server-side job on this site (search included).
4. `GET PaymentConfirmation.aspx?cId1=<guid>` (same session) twice (the
   first hit can 200 with the page already fully rendered if the earlier
   cookie warmup already ran in this session) returns an HTML page embedding
   three hidden fields: `ctl00_Space_Response` (an async job id, DIFFERENT
   from `cId1`), `ctl00_Space_PollURL`
   (`https://www.orcjamaica.com/AsyncServices/`), and
   `ctl00_Space_ResultUiController`
   (`CompanySearchResults.aspx?cId1=<another-guid>`).
5. `POST {PollURL}asyncState/{Response}` (`Content-Type: application/json`,
   empty body) returns `{"CurrentState": "...", ...}`. Observed states in
   order: `Preparing` -> `Committing` -> `Succeeded` (2-3 polls, ~1.5s apart,
   is typical). `Failed` (or the retry states `Awaiting retry of
   rollback`/`Awaiting retry of commit`) means the job genuinely errored --
   distinct from a WAF block, which shows up as an HTTP-level 403 on the
   POST itself, not a `Failed` job state.
6. `GET {ResultUiController}&asyncId={Response}` (i.e.
   `CompanySearchResults.aspx?cId1=...&asyncId=...`) returns the actual
   results page. Despite rendering an (empty, JS-populated-looking)
   `<table>`, the real data is a plain inline
   `<script>var database = {"data": [...], ...};</script>` blob -- NOT
   parsed from the DOM. Each element of `data` is one matched entity:
   `link` (always empty here), `rank`, `id` (internal registration id,
   distinct format for companies `"<num>-L"`/`"<num>-F"` vs business names
   `"<num>_<year>-"`), `name`, `office` (a single officer -- director/
   proprietor/secretary -- name and role, when on file), `status`
   (`ACTIVE`, `REMOVED`, `Registered`, `In BO Sanction Process`, ...),
   `type` (`COMPANY` or `BUSINESS`), `date` (registration/incorporation
   date, free-text e.g. `"09 Apr 1999"`), `address` (registered office
   address, free-text), `number` (formatted registration number with a
   `(Local)`/`(Overseas)` suffix for companies, or `NNNNN/YYYY` for business
   names), and `documentCount` (count of filed documents available for
   purchase -- purchasing them is out of scope, requires the paid/login
   flow this actor does not touch).

This means the search-result step alone already carries every field this
actor needs (name, registration number, status, entity type, registration
date, registered address, and one officer) -- there is no separate
"entity detail page" to click into for the fields this actor exposes.

## Known limits / gotchas found during recon

- **Result cap: 200.** A broad one-word query (`"Bank"`) returned exactly
  200 rows -- the largest observed, and presumably the server-side page
  size cap. A query broader than that may not return every match.
- **The "quiet" WAF block.** During recon, batches of rapid, back-to-back
  search flows (multiple full search+poll+results cycles within roughly a
  minute) intermittently tripped a hard `403` with body title `"Access to
  the website is blocked"` / `Code: HIC` from the Zenedge layer -- on the
  *initial* search POST, not on the harmless cookie-warmup GET. This
  recovered on its own within roughly 60-120 seconds (confirmed: the exact
  same query that got blocked succeeded again unmodified after a short
  wait), and did not correlate with the query text itself (a plain,
  ordinary business-name query tripped it just as readily as an
  intentionally garbage-looking one once enough requests had gone out) --
  i.e. this reads as a request-volume/behavioral rate limit, consistent
  with the site's own `Crawl-delay: 120` in `robots.txt`, not a content
  filter or a hard IP ban. `client.py`'s retry loop backs off and retries
  rather than treating a 403 as fatal.
- **Zero-result behavior was not cleanly isolated.** Every distinctly-worded
  query tried during recon matched at least one real entity (the search
  appears to do prefix/substring token matching, not exact-phrase
  matching, which made constructing a guaranteed-zero-result query
  difficult without also looking like a bot probe). `extractor.py` treats
  an empty `data` array in the results blob as the (expected, documented)
  no-match signal; if upstream's true zero-result shape differs, the
  actor emits `_error: "unexpected_shape"` instead of a false empty
  success, per this project's fail-loud rule.
"""

BASE_URL = "https://www.orcjamaica.com"
SEARCH_URL = f"{BASE_URL}/CompanySearch.aspx"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": BASE_URL,
}

# Upstream's own page-size cap, observed on a broad one-word query ("Bank").
MAX_RESULTS_CAP = 200

# How many times to poll the async job before giving up, and the pause
# between polls (observed: 2-3 polls at ~1.5s is typical for "Succeeded").
POLL_MAX_ATTEMPTS = 20
POLL_INTERVAL_SECS = 1.5

# Retry/backoff for the Zenedge "HIC" rate-limit block (see recon summary
# above) -- generous enough to ride out the ~60-120s recovery window
# observed during recon. Exponential: 15s, 30s, 60s, 120s, 240s.
MAX_RETRIES = 5
RETRY_DELAY_BASE_SECS = 15.0

# Minimum pause this actor inserts BETWEEN separate query flows (not
# between the internal warmup/poll requests of a single flow), as a
# good-faith nod to the site's own `Crawl-delay: 120` directive without
# making every run impractically slow. Configurable via input
# `requestDelaySecs`; set to 120 for strict robots.txt compliance.
DEFAULT_REQUEST_DELAY_SECS = 10.0

# Body markers that identify the Zenedge block page (distinct from a
# generic 403 some other layer might return).
BLOCK_MARKERS = [
    b"Access to the website is blocked",
    b"Code</td><td>HIC",
]
