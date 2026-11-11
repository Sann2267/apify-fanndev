# Crawling Method — Sierra Leone Business Registry (OARG Company Search)

**Last verified:** 2026-08-27

## Target discovery — the obvious pages are broken, the real tool is elsewhere

Sierra Leone's official registry is the **Office of the Administrator and
Registrar-General (OARG)**, domain `oarg.gov.sl`. The site's own marketing
page for this, `oarg.gov.sl/business-register/`, and the site's homepage,
`oarg.gov.sl/`, both return **HTTP 500** on every request (confirmed across
`curl_cffi` `chrome124`/`chrome131`/`safari17_0`/`edge101` — identical
byte-for-byte body on all four). The response body is not a WAF page but a
literal PHP fatal error trace:

```
Fatal error: Uncaught Error: Call to undefined function eltron_content_open()
in /home/l0957dyhb8b1/public_html/wp-content/themes/eltron/header.php:85
```

This is a genuine, currently-live outage of the WordPress "eltron" theme's
header template (a missing/renamed plugin function) — not a bot block, and
not something this actor can work around, since it affects the page for
every visitor including a real browser.

Fortunately the actual interactive search tool is **not part of the
WordPress install at all**. It's a separate, older PHP app mounted at
`oarg.gov.sl/company-search/` — page title "Company Search Office of
Administrator and Registrar General (OARG)", a Bootstrap 4 + DataTables
dashboard template (footer credit: "powered by Customerworth", a Sierra
Leonean/Nigerian dev shop; page author meta: "Moses Ibe"). Because it's a
separate codebase on a separate app path, it is completely unaffected by
the WordPress fatal error — it returns clean `200`s throughout. This is
the ONLY functioning public search feature found anywhere on the domain
(no other search form, verify-certificate tool, or API found linked from
the (broken) homepage, from web search results, or from Wayback-style
searches for `oarg.gov.sl` search pages).

## robots.txt / WAF

`oarg.gov.sl/robots.txt`:

```
User-agent: Baiduspider
Disallow: /
User-agent: AhrefsBot
Disallow: /
User-agent: MJ12bot
Disallow: /
User-agent: BLEXBot
Disallow: /
User-agent: DotBot
Disallow: /
User-agent: SemrushBot
Disallow: /
User-agent: YandexBot
Disallow: /
User-agent: *
Allow: /
Sitemap: https://oarg.gov.sl/?feed=xmlsitemap1633
```

Wide open for `User-agent: *` (`Allow: /`). Only a handful of well-known
SEO/link-index crawlers are individually disallowed by name — no mention
of `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`,
or `anthropic-ai` anywhere, and no blanket disallow for `*`.

No WAF/CDN challenge layer observed on `/company-search/`: a Cloudflare
Web Analytics beacon `<script>` tag is injected into every page (asset
`static.cloudflareinsights.com/beacon.min.js`), but it's passive analytics,
not a gating challenge — every TLS profile tested returned an identical
`200` with real data, and 5 back-to-back queries completed in ~1.8s with
no throttling or CAPTCHA observed.

## A cosmetic but notable signal: hosting-expired banner

Every response from `/company-search/` has a banner injected via inline
JavaScript reading "Hosting plan for this site has expired. Renew now to
avoid service disruption." (linking to `host.godaddy.com`). This is a
hosting-provider-level warning banner (GoDaddy injects these into HTTP
responses during a grace period after a hosting plan lapses), not a bug in
this actor and not something affecting the actual search response body —
but it's a real signal that this endpoint's availability is fragile and
could go dark entirely if the underlying hosting account isn't renewed.
Documented here for whoever revisits this actor later.

## Data source — S1-company-search

### The tool: a name-availability checker, not a full company-profile lookup

`GET /company-search/?query=<term>` is a single stateless request — no
cookies, no session, no CSRF token required. The backend does a
case-insensitive substring match against existing registered business
names and returns exactly one of three outcomes, rendered as different
HTML shapes:

1. **Match(es) found** — a `div.alert.alert-danger` reading
   `<strong><query></strong> already exist.`, followed by one
   `<tr><td>NAME</td></tr>` per matching existing business name.
   **Only the name comes back** — no registration number, incorporation
   date, status, address, entity type, or director/owner name. There is
   no other endpoint anywhere on the site that exposes those fields.
2. **No matches** — a `div.alert.alert-success` reading
   `<strong><query></strong> is available.` and zero result rows.
3. **Query too short** — the literal text `Minimum length is 3` with no
   alert div at all. Confirmed: a 1-character query (`a`) returns this;
   a 3+ character query proceeds to outcome 1 or 2.

### No server-side result cap — a real operational hazard

Like several sibling actors in this portfolio (Ghana ORC, Tanzania BRELA),
`DataTables` only paginates client-side in the browser — the server always
returns every match in one response. Confirmed: `query=trading` → **1,972
rows** in a single ~104 KB response; `query=bank` → 138 rows. There is no
request parameter to limit row count server-side.
`maxResultsPerQuery` in this actor's input can only truncate the OUTPUT
after the full response has already been downloaded and parsed.

### A real upstream bug: certain punctuation crashes the backend

Testing special characters in the query string turned up a genuine,
reproducible server-side bug (most likely an unescaped value reaching a
raw SQL string, though this was not exploited or investigated further —
only its *symptom* was characterized, to build a reliable detector):

- **Apostrophe (`'`) or semicolon (`;`)** anywhere in the query → the
  backend dies mid-render with a suppressed PHP fatal error. The response
  comes back `200` but is truncated right after the search form: no alert
  banner, no results table, no footer, no closing `</html>` tag at all.
  Confirmed with `query=O'Brien` (3,301-byte truncated response vs. a
  normal ~5.2–5.9 KB "available" response or larger for real matches) and
  `query=test;drop`.
- **Double quote (`"`)** does NOT crash the whole page, but corrupts the
  results `<table>` element: the closing `</tbody></table>` tags still
  render, but the opening `<table id="datatable1">`/`<thead>` portion is
  missing from the response. The alert-banner message itself (with the
  query correctly HTML-escaped as `&quot;`) still renders fine, so this
  case remains fully parseable via the alert-banner text alone — the
  extractor in this actor never depends on the `<table>` wrapper being
  present, exactly to route around this.

Because retrying can't fix an upstream bug, `'` and `;` are detected and
rejected **client-side, before any request is sent** (`src/main.py`),
returning a clear `_error: "unsafe_query"` record. If a query somehow
still produces the truncated-response shape (e.g. some other undiscovered
unsafe character), `src/extractor.py` detects the missing `</html>`/
`az-footer` markers and returns `_error: "upstream_backend_error"` instead
of raising an unhandled parse exception.

### Encoding note

The page correctly declares and serves `Content-Type: text/html;
charset=UTF-8` and ampersands/quotes in the query are properly
HTML-escaped in the echoed `<strong>` tag (e.g. `Tom & Jerry` →
`Tom &amp; Jerry`). One cosmetic artifact: the alert's dismiss button
(`<span aria-hidden="true">×</span>`) is sometimes served as a literal
non-UTF-8 byte for the `×` character, decoding as U+FFFD (replacement
character) under `curl_cffi`'s auto-detected UTF-8 — irrelevant to
extraction since this actor never reads that button's text.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No profile-specific blocking was ever observed on this target —
all friction found was upstream application bugs, not anti-bot defense.
