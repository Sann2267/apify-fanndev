# Crawling Method — Eswatini Government Tenders (ESPPRA)

**Last verified:** 2026-08-27

## Finding the real portal

Search-engine and third-party tender-alert results (`eswatinitenders.com`,
`tendersontime.com`, `globaltenders.com`, `tendersgo.com`) all point to
commercial aggregators, not the government system itself — same trap flagged
in this portfolio's `eswatini-roc-scraper` recon for `cipa.org.sz`. The real
official regulator surfaced from a search for "Eswatini Public Procurement
Regulatory Authority":

**Eswatini Public Procurement Regulatory Agency (ESPPRA)** — established
under the Public Procurement Act No. 7 of 2011 as Eswatini's independent
procurement regulator (policy, oversight, and publication of tender/award
notices for all government ministries, local authorities, and parastatals).
Its live site is:

```
https://esppra.co.sz/sppra/
```

A second domain, `sppra.co.sz` (the acronym without the leading "E"), is
still live and 302-redirects straight to `esppra.co.sz/sppra` — confirming
both names point at the same canonical system rather than one being a stale
decoy. `www.gov.sz` was not checked for a direct link-through this time since
ESPPRA's own domain, name, and legal mandate (Act No. 7 of 2011) were
independently confirmed via multiple search results and its own site content
(RHUS Office Park, Karl Grant Street, Mbabane address; `+268 24047527`
phone) — a much stronger signal than a single link-through.

The site is a custom-built PHP/Apache application — its own footer reads
*"This Website Is Created By ESPPRA IT Department"* — **not** one of the
shared vendor e-GP platforms seen elsewhere in this portfolio's tender
vertical (European Dynamics/"ePPS" for Ghana/Zambia/Jamaica; Perago Systems
for Sierra Leone/Malawi). No vendor footprint to cross-reference against
other countries here.

## Robots.txt

```
HTTP 404 (no robots.txt file exists at all)
```

Checked `esppra.co.sz/robots.txt` and `www.esppra.co.sz/robots.txt` — both
404 (Apache's own "Object not found!" page). No restrictions, no
Claude/anthropic-ai mention — there is nothing to mention anything in.

## Login wall check

**None, anywhere checked.** Every listing page relevant to this actor
(`tender.php`, `award_intention.php`, `suspended.php` / its JSON API) is
served to a plain unauthenticated GET. The old "PE Login" nav item visible
in an HTML comment in the page header (`<!--a href="pe/login.php"...`) is
itself commented out in the live markup — there isn't even a visible login
link on the current site, let alone a wall in front of viewing.

## TLS / WAF probe — cert chain problem, not a WAF

Plain `curl` failed with **exit 60** ("SSL certificate problem: unable to
get local issuer certificate") on `https://esppra.co.sz/`. This is a
**missing intermediate certificate** on the server's side, not a WAF or
bot-detection signal — confirmed by testing all four required `curl_cffi`
profiles with default verification:

| Profile | `verify=True` (default) | `verify=False` |
|---|---|---|
| `chrome124` | `CertificateVerifyError` | `200` |
| `chrome131` | `CertificateVerifyError` | `200` |
| `safari17_0` | `CertificateVerifyError` | `200` |
| `edge101` | `CertificateVerifyError` | `200` |

All four profiles return identical `200 OK` once `verify=False` is set — no
fingerprint gate, no CAPTCHA, no Cloudflare/`cf-ray`/Sucuri markers, no
divergent behavior between profiles. Same symptom (and same fix) already
documented for `nepal-tenders-scraper` / `nepal-ocr-scraper`'s Bolpatra/PPMO
infrastructure — apparently a common government-IT gap, this time in a
different country. `src/client.py` sets `verify=False` on every request.

## Listing pages — three usable public views, two different formats

ESPPRA's nav bar under "Tender" lists six items; three are public listings
with real, current data (as of this recon: 2026-08-27) and were built into
this actor. The other three (Procuring Entity Directory, Procurement Plans,
Expression of Interest — commented out) were left out of scope to keep the
actor focused on active tender/award transparency data, not reference
lookups.

### 1. `tenders` — Invitation To Tender (`tender.php`)

Server-rendered HTML. Each row is a `<div class="list-item job-box">`
containing an `<h5>` title, then a run of `<p>` tags: two unlabeled
(procuring entity in `<b>`, then the reference number as plain text) and 2-3
labeled ones ("Procurement Method: ...", "Tender Upload Date: ...",
"Submission Deadline: ..."), followed by a PDF download `<a id="..."
href="...">`. Parsed generically by matching the `Label: value` pattern on
each `<p>`'s text and slugifying the label to a camelCase key — not by fixed
position — so an ESPPRA-side field addition/removal flows through under its
own name instead of silently shifting into the wrong column.

Pagination: `GET tender.php?Page=<n>&txtKeyword=<kw>`. The page itself
states the ground truth directly in its body text — `"Total 61 Record : 7
Pages :"` as observed during this recon — parsed with a regex rather than
computed from an assumed page size, so it stays correct even if ESPPRA
changes rows-per-page later.

`txtKeyword` (also exposed by this actor as the optional `keyword` input)
works as a plain `GET` query parameter even though the on-page `<form>` uses
`method="post"` — confirmed live: `?txtKeyword=Eswatini%20Electricity`
narrowed 61 total rows down to 6, all genuinely matching "Eswatini
Electricity Company (EEC)" tenders.

### 2. `award_intentions` — Intention To Award (`award_intention.php`)

Identical `job-box` shell and pagination mechanics, one field set smaller
(no "Procurement Method" or "Submission Deadline" — just title, procuring
entity, reference number, and a single "Upload Date:" label). Much larger:
**1,572 records across 79 pages** as observed during this recon, vs. 61/7 for
open tenders — this is ESPPRA's transparency archive of every notice of
intention to award ever published, not just currently-open ones. Note: this
view does **not** carry the winning supplier name or contract amount (unlike
e.g. `ghana-tenders-scraper`'s "awarded" listing) — ESPPRA's own UI doesn't
surface that here; only the intention notice PDF link is available.

### 3. `suspended_suppliers` — Suspended Suppliers (`suspended.php`)

The one exception to the HTML-scraping pattern: `suspended.php` itself
renders an **empty** `<table id="example">` — its data is loaded client-side
by jQuery DataTables from a clean JSON endpoint:

```
GET https://esppra.co.sz/sppra/api/suspendedSupplier_list.php
```

```json
{"draw":0,"recordsTotal":1,"recordsFiltered":1,"data":[["1","LCC Capital Consulting","Consortium Consulting (Pty) LTD","17th Jun 22","17th Jun 25","1655900851.pdf","1st Jan 70"]]}
```

No pagination parameters needed or supported observed — the whole
(currently very small, 1-record) debarment register comes back in one call.
Column order matched against `suspended.php`'s own `<thead>` labels (Supplier
ID / Trading Name / Company Name / Suspension Start Date / Suspension End
Date / Suspension Document / Action). The download URL is built client-side
in `suspended.php`'s own JS (`"documents/suspended/" + data[5]`) — replicated
in `src/extractor.py`.

**Quirk:** column index 6 ("Action") is marked `visible: false` /
`searchable: false` in ESPPRA's own DataTables config, and its only observed
value is `"1st Jan 70"` — an epoch-zero placeholder, not real data. Passed
through raw as `_actionRawPlaceholder` per this project's raw-passthrough
convention rather than silently dropped, but flagged in the output schema
description as unreliable.

## No separate tender "detail" page

Unlike GHANEPS (Ghana) or Bolpatra (Nepal), ESPPRA's tender rows link
**directly to a PDF document**, not to an HTML detail page with structured
fields — `<a href="documents/tenders/<PE name>/<epoch>.pdf" download>`. There
is nothing to fetch beyond what the listing row itself already contains
(title, procuring entity, reference, procurement method, dates, and the PDF
link), so this actor is **list-only** — no `mode`/`detail` parameter, since
there is no second page shape to fetch. The PDF itself is the full document;
parsing PDF content was judged out of scope (raw-passthrough of the URL is
enough for a user to open/download it).

## Sample queries tested

- `tenders`, no keyword: 61 total / 7 pages.
- `tenders`, `keyword="Electricity"`: 6 total / 1 page, all genuinely
  Eswatini Electricity Company (EEC) tenders.
- `award_intentions`, no keyword: 1,572 total / 79 pages.
- `suspended_suppliers`: 1 total (single JSON call).
- 15-result run against `tenders` (page size 10) correctly crossed the page
  boundary: 10 rows tagged `_page: 1`, 5 rows tagged `_page: 2`.

## Known limits

- `award_intentions` does not include the winning supplier name or award
  amount — ESPPRA's own UI doesn't expose that on this page, only on the
  (unpublished) PDF notice itself.
- `suspended_suppliers`' `_actionRawPlaceholder` column is not meaningful
  data (see quirk above) — passed through raw rather than guessed at.
- Dates are passed through exactly as ESPPRA displays them (e.g. `"Tuesday
  28th July 2026 9:56 am"`, `"17th Jun 22"`), not normalized to ISO 8601 —
  the formats differ between the two `job-box` views and the JSON API, and
  guessing a canonical parse risked silently misreading a genuinely
  ambiguous government-published date.
- `maxResults` truncates client-side after each page is already fetched and
  parsed; it does not reduce server-side work for a broad `award_intentions`
  run spanning many pages.

## Diff cadence

Quarterly smoke test recommended — a small, in-house-built government PHP
site like this can be redesigned with little notice, and (unlike GHANEPS's
long-lived Struts/JSP shell) there's no evidence of a stable underlying
framework to expect long-term markup stability from.
