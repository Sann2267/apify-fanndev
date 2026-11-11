"""Endpoints, headers, profile choice -- all in one place.

Recon summary (2026-08-27): Sierra Leone's official business registry is run
by the **Office of the Administrator and Registrar-General (OARG)**
(oarg.gov.sl). The main site is a WordPress install and is currently in a
**broken state** -- every WordPress-rendered page (including the homepage
`/` and the marketing page `/business-register/`) returns HTTP 500 with a
PHP fatal error visible in the response body:
`Uncaught Error: Call to undefined function eltron_content_open() in
.../wp-content/themes/eltron/header.php`. This is a genuine site-side outage
(a broken theme function), not a bot block -- the same 500 is returned to
every TLS profile tested (chrome124/chrome131/safari17_0/edge101) and to a
plain browser.

The actual interactive search tool, however, lives in a **separate legacy
PHP app** at `oarg.gov.sl/company-search/` (title: "Company Search Office
of Administrator and Registrar General (OARG)", footer: "powered by
Customerworth", a Bootstrap 4 + DataTables dashboard template unrelated to
the WordPress install) and is unaffected by the WordPress fatal error --
it returns clean `200`s throughout. This is the ONLY functioning public
search found on the domain, and it is the target of this actor.

## What the tool actually does

It is a **business-name availability checker** -- the same tool OARG
provides so people about to register a business name can check whether
their candidate name is already taken. It does a case-insensitive
substring ("contains") match against the existing business-name register
and returns one of exactly three outcomes:

1. Zero matches -> a green `alert-success` banner: "`<name>` is available."
2. One or more matches -> a red `alert-danger` banner: "`<name>` already
   exist." followed by every matching existing business name as a table
   row (**name only** -- no registration number, incorporation date,
   status, address, entity type, or owner/director name; those fields are
   not exposed by this public tool at all).
3. A query under 3 characters -> plain text "Minimum length is 3" (no
   alert banner).

There is no separate registration-number/detail lookup anywhere on the
site -- this name-availability check is the entirety of OARG's public
online search surface (confirmed: no other search form or "verify
certificate" tool found on oarg.gov.sl or linked from it).

## No login, no CAPTCHA, no CSRF, no WAF

`GET /company-search/?query=<term>` is a single, stateless, unauthenticated
request -- no cookies, no session, no CSRF token, no rate limiting observed
(5 back-to-back queries completed in ~1.8s with no throttling). `robots.txt`
at the domain root is wide open (`User-agent: *` / `Allow: /`, only a
handful of well-known crawlers like AhrefsBot/MJ12bot/SemrushBot/YandexBot
are individually disallowed by name -- no mention of Claude/ClaudeBot/
anthropic-ai anywhere, and no blanket disallow). No WAF/CDN challenge layer
observed -- a Cloudflare Web Analytics beacon script is present (`cf-ray`
style asset injection) but it does not gate requests; every TLS profile
tested returned identical `200` responses.

## A real operational hazard: no server-side result cap

Like several sibling actors in this portfolio (Ghana ORC, Tanzania BRELA),
there is no pagination or row limit on the server side -- `DataTables` only
paginates client-side in the browser. A broad "contains" query for a
common word returns EVERY match in one response: `query=trading` returned
**1,972 rows**. `maxResultsPerQuery` in this actor's input truncates
client-side AFTER the full response is downloaded and parsed.

## A GoDaddy "hosting plan expired" banner is injected into every page

Every response from `/company-search/` carries a JS-injected banner
("Hosting plan for this site has expired. Renew now to avoid service
disruption.") -- a hosting-provider-level warning, not a bug in this
actor. It's cosmetic (doesn't affect the actual search response body) but
is a signal this endpoint could go dark if the underlying hosting account
lapses; flagged here for whoever revisits this actor later.

## A real upstream bug: certain punctuation crashes the query entirely

An apostrophe (`'`) or a semicolon (`;`) anywhere in the query string
causes the backend to die mid-render with a suppressed PHP error --
the response is truncated right after the search form (no alert banner,
no results table, no footer, no closing `</html>`), most likely an
unescaped value reaching a raw SQL string. A double quote (`"`) doesn't
crash the whole page but does corrupt the `<table>` element's opening tag
(the closing `</tbody></table>` still renders, but the `<thead>`/opening
`<table>` do not) -- the alert-banner message and its embedded query
(HTML-escaped as `&quot;`) still render correctly, so this case remains
parseable and is not a hard failure. This actor documents both as known
upstream limitations rather than silently returning wrong data --
queries containing `'` or `;` are rejected client-side before any request
is sent (see `client.py`), since retrying can't fix an upstream bug.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://oarg.gov.sl/company-search/"

MIN_QUERY_LENGTH = 3

# Characters observed to crash the upstream backend entirely (suppressed
# PHP fatal error, truncated response with no results/no footer). Rejected
# client-side rather than sent -- see constants.py docstring above.
UNSAFE_QUERY_CHARS = {"'", ";"}

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
