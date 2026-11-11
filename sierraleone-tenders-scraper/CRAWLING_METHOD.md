# Crawling Method — Sierra Leone Government Tenders (NPPA)

**Last verified:** 2026-08-27

## Target discovery — the "obvious" modern portal is dark, the older one is not

Sierra Leone's public procurement regulator is the **National Public
Procurement Authority (NPPA)**, domain `nppa.gov.sl`. NPPA operates two
separate web properties under variations of that name:

1. **A modern e-GP (electronic Government Procurement) platform**,
   `egp.nppa.gov.sl` — a Next.js single-page app backed by roughly ten
   NestJS microservices on subdomains like `tendering-egp.nppa.gov.sl`,
   `rms-egp.nppa.gov.sl`, `planning-egp.nppa.gov.sl`,
   `vendor-egp.nppa.gov.sl`, `administration-egp.nppa.gov.sl`, etc. (all
   resolving to the same IP, routed by hostname). Static asset strings
   baked into its JS bundles reference `maneps.mw` and `ppda.mw` (Malawi's
   procurement authority/e-GP platform) and `peragosystems.com` — this
   confirms the same vendor, **Perago Systems**, built both Sierra Leone's
   and Malawi's e-GP platforms (the first cross-country shared-vendor
   footprint found in the tender/procurement vertical, mirroring the
   Foster Moore Catalyst / OCRS / DotGovServer pattern already documented
   for business registries).
2. **NPPA's older WordPress "corporate" site**, also on `nppa.gov.sl` —
   a completely separate CMS install used for news, circulars, and (as it
   turns out) hand-maintained tender listings.

### The modern e-GP platform's tender listing is currently unusable

The e-GP frontend's `/procurement-notice` page is **100% client-rendered**
— its Next.js RSC payload was inspected directly and contains zero tender
data server-side; a real browser has to run JS and call
`GET tendering-egp.nppa.gov.sl/api/tenders` to populate it. That endpoint
returns a bare `502 Bad Gateway` on **every single path**, including `/`
and `/health` — not just `/api/tenders`. This was confirmed:

- Across `curl_cffi` (`chrome124`) AND plain Python `requests` (ruling out
  a TLS-fingerprint-specific block).
- Repeatedly over 10+ minutes of wall-clock retries, not a single attempt.
- While sibling microservices on the **exact same IP**
  (`rms-egp`, `planning-egp`, `vendor-egp`, `administration-egp` — verified
  via DNS) all respond normally (200s or well-formed 404 JSON from their
  NestJS routers).

This is a genuine, isolated outage of one backend pod, not a WAF and not a
network problem on our end. The Wayback Machine confirms `/procurement-notice`
was live and returning 200 as recently as 2026-05-18, so this is a
recent/temporary outage, not a permanently dead endpoint.

The platform also exposes an **Open Contracting Data Standard (OCDS)**
export at `rms-egp.nppa.gov.sl/api/ocds/get-records` (`POST`, no auth) —
this microservice IS up and returns a well-formed
`{"total": ..., "items": [...]}` response for any request body tried
(including `{}`, `{"take": 50}`, `{"filters": []}`, etc. — no validation
error is ever raised for unrecognized keys, which is how we know the
`total: 0` result isn't a request-shape problem). It is simply, genuinely
**empty right now** — no OCDS records have been published to it yet.

### The working alternative: NPPA's WordPress "Bids / Tenders" page

The older WordPress site's own nav menu has a **"Bids / Tenders"** link
pointing at **`nppa.gov.sl/bid/`** — an Elementor page embedding a
**TablePress** table (`id="tablepress-1"`) with one row per tender:

| Bidding Organization | Date Posted | Expiration Date | Description of Bidding | Download Bid |
|---|---|---|---|---|

This is genuinely current: the newest row when this actor was built
(2026-08-27) was dated 2026-08-20, one week prior. Rows go back to July
2025 and are **not** removed once expired — the page is a running log, not
a "currently open only" board. Confirmed directly: of the 31 rows on file
at verification time, only 1 had an Expiration Date still in the future;
the other 30 (including some from mid-2026) had already lapsed, and NPPA
had not removed any of them from the table.

This is the same "the flashy new system is broken but an older, plainer
part of the same domain still works" pattern already documented for
Sierra Leone's OARG business registry (`sierraleone-oarg-scraper`).

## robots.txt / WAF

`nppa.gov.sl/robots.txt`:

```
User-agent: *
Disallow: /wp-content/uploads/wc-logs/
Disallow: /wp-content/uploads/woocommerce_transient_files/
Disallow: /wp-content/uploads/woocommerce_uploads/
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://nppa.gov.sl/wp-sitemap.xml
```

Nothing under `/bid/` (or anywhere this actor touches) is disallowed. No
mention of `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/
`Claude-SearchBot`/`anthropic-ai` anywhere, and no blanket disallow for
`*`. (`egp.nppa.gov.sl/robots.txt` is also wide open — `Allow: /` with only
`/api/`, `/_next/`, `/manage/`, `/_app/` disallowed — moot for this actor
since it doesn't touch that host at all.)

No login wall, no CAPTCHA, no WAF/CDN challenge observed on `/bid/`: a
single stateless GET returns an identical `200` with full data across
every TLS profile tried, no throttling on repeated requests.

## Data source — S1-bid-tenders-table

`GET https://nppa.gov.sl/bid/` is a plain, parameter-free, server-rendered
HTML page. All ~30 rows are present in the initial response (TablePress's
DataTables JS only affects client-side sorting/paging in the browser, the
same pattern already seen in Ghana ORC / Tanzania BRELA / Sierra Leone
OARG). `/bid/page/2/` and `/bid/?paged=2` both return the identical page
(WordPress's default fallback for a non-paginated URL) — confirming there
is no hidden additional page of older tenders.

### Known upstream data-quality issues (not bugs in this actor)

- **Inconsistent date formatting.** Observed: `"14-08-2026"`,
  `"30- 04-2026"` (stray space around a dash), `"13-4-2026"` (no leading
  zero), `"23-04-26"` (2-digit year), `"23 -02- 2026"` (spaces on both
  sides). `extractor.py`'s `_parse_loose_date()` strips all whitespace,
  splits on `-`, and expands a 2-digit year to `20YY` — but returns `None`
  (never raises) for anything it still can't parse, since this is known
  upstream messiness, not a schema change.
- **Broken/missing document links.** Two distinct broken shapes were
  found in the live table: `<a>` with no `href` attribute at all, and
  `<a href="">` (empty string). Both are treated as "no document"
  (`documentUrl: null`) rather than an error.
- **Stray letter-spacing in organization names**, e.g. `"I N S T I T U TE
  OF PUBLIC ADMINISTRATION AND MANAGEMENT"` — present in the raw upstream
  HTML itself (verified by inspecting the raw response), not introduced by
  this actor's parsing. Passed through verbatim per the "raw passthrough"
  convention.
- **No reference/tender number field.** Unlike some countries' e-GP
  systems, NPPA's board does not have a dedicated reference-number column
  — any such number appears only incidentally inside the free-text
  `descriptionOfBidding` (e.g. `"EDSA_LOG_ICB_2026_0002"` as a filename,
  not a table cell). This actor does not attempt to regex-extract one out
  of free text, per the "no fabricated structure" convention.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No profile-specific blocking was ever observed on this target —
the only friction found anywhere on this domain was the modern e-GP
platform's own backend outage, not anti-bot defense.
