# Crawling Method — Zimbabwe PRAZ eGP Tenders

**Last verified:** 2026-08-27

The Procurement Regulatory Authority of Zimbabwe (PRAZ) runs an electronic
Government Procurement (eGP) system at `egp.praz.org.zw`. It is built on the
**"Nextenders (India) Pvt Ltd" e-GP platform** (confirmed via `<meta
name="Creator" content="Nextenders India Private Limited"/>` on every page,
and the footer `Copyright © 2018 Nextenders (India) Pvt Ltd`) — a **new
e-GP vendor lineage** for this portfolio's tender vertical, distinct from
European Dynamics/"ePPS" (Ghana/Zambia/Jamaica), Perago Systems (Sierra
Leone/Malawi), TenderLink/Bonfire (negative signals), and the Korean-origin
platform seen in Rwanda. It is a CakePHP web app, fronted by an AWS
Application Load Balancer (`Set-Cookie: AWSALB=...`). The marketing site
`www.praz.org.zw` (WordPress) and the older `praz.gov.zw` (does not resolve
via DNS at all — a dead legacy domain, do not use) are separate, unrelated
hosts and are not used by this actor.

## Robots.txt

- `GET https://www.praz.org.zw/robots.txt` → HTTP 200:
  ```
  User-agent: *
  Disallow: /wp-admin/
  Allow: /wp-admin/admin-ajax.php
  Sitemap: https://www.praz.org.zw/wp-sitemap.xml
  ```
  No blanket disallow, no bot named (Claude/ClaudeBot/anthropic-ai or
  otherwise), no natural-language prohibition.
- `GET https://egp.praz.org.zw/robots.txt` → HTTP 404, served by the CakePHP
  app's own "Oops! Page not found" error page (i.e. no robots.txt route is
  configured at all on this host — every unmatched path 404s through the
  app, not a static file server). No restriction found on either host.

## WAF / anti-bot

**None found.** `curl_cffi` tested across `chrome124`, `chrome131`,
`safari17_0`, and `edge101` impersonation profiles against the Live
Tenders bulletin board — all four returned identical HTTP 200 responses
with the same content length (136,433 bytes). No Cloudflare/DataDome/
Akamai/etc. markers in headers or body, no CAPTCHA on any page this actor
touches. `curl_cffi` (`chrome124`) impersonation is used anyway as this
portfolio's default posture (`.ai/CLAUDE.md` principle #2), not because a
block was ever seen. `proxyConfiguration` defaults to off for the same
reason.

## Login wall — none found (more open than several sibling platforms)

**Every listing and every detail page this actor uses is fully public,
with no login wall of any kind** — including detail pages for tenders past
their bid-submission deadline. This was explicitly checked because several
other e-GP platforms in this portfolio's tender vertical (e.g. Zambia's
ePPS) login-wall the detail page once a tender's status changes:

- `Indexes/index` ("Live Tenders") — currently-open tenders.
- `Indexes/getFormerOpportunities` ("Former Opportunities" / Past Tenders)
  — **64,233 historical records** observed live, spanning back to at least
  2024 (tender id `1`, `PRAZ/DOM/01/2024`).
- `Indexes/getAwardNotices` ("Award Notices") — recent contract awards.
- `Indexes/viewLiveTenderDetails/<id>` — confirmed HTTP 200 with full
  detail for a **currently-open** tender (id 46190, closing Sep 2026) AND
  for a **closed tender from 2024** (id 1) — no login redirect in either
  case, no different treatment by status.
- `Indexes/viewAwardNotice/<id>` — confirmed HTTP 200 with full detail
  (awardee name/address/contact person, contract amount, line-item
  breakdown) for recent awards, no login.

Login (`/Indexes/login`) and "Sign up" (`/Suppliers/add`) exist only for
suppliers who want to actually submit bids — per this project's stop
condition, that does not block the actor.

## Data source — reverse-engineering path

No JSON API, JSON-LD, or `__NEXT_DATA__` anywhere — this is a
server-rendered CakePHP app (`Set-Cookie: CAKEPHP=...`). All modes parse
plain HTML:

1. **Listing tables** (`latest`/`former`/`awards` modes) — each bulletin
   board renders one `<table class="table table-bordered table-hover ...">`.
   **Column headers are read live from the header `<tr>` (the first row
   containing `<th>` cells), and every subsequent `<tr>` is mapped strictly
   by cell *position*** against those headers — never by each `<td>`'s own
   `data-label` attribute. This matters because the site's own `data-label`
   attributes are confirmed **mislabeled/shifted by one column** on the
   Live Tenders and Former Opportunities tables (e.g. the cell holding a
   tender's actual title carries `data-label="Tender Reference Number"`,
   and the cell holding the reference number carries `data-label="Control
   Number"` — neither matches the real `<th>` header for that column).
   Trusting `data-label` would silently swap these two fields.
2. **Pagination** — `Indexes/index` and `Indexes/getFormerOpportunities`
   both have genuine, working server-side pagination via
   `?url=<encoded-controller>&page=<n>&direction=<GridName>.id` (confirmed
   live: page 2/3 return different rows than page 1). `Indexes/getAwardNotices`
   does **not** — see "Known limits" below.
3. **Markup bug on Former Opportunities**: the page ships **two nested
   `<thead>` open tags but only one `</thead>` close tag**. Under `lxml`'s
   HTML parser this makes *every* `<tr>` in the table resolve as a
   descendant of `<thead>`, which breaks a naive
   `tr.find_parent("thead") is None` row filter (returns zero rows). The
   fix used here: locate the header row directly (the first `<tr>`
   containing `<th>` cells) and take every `<tr>` that follows it in
   document order, ignoring `<thead>`/`<tbody>` boundaries entirely. The
   same technique is reused for the detail-page "Line Item Details"
   sub-table.
4. **Detail pages** (`Indexes/viewLiveTenderDetails/<id>` and
   `Indexes/viewAwardNotice/<id>`) — both render their fields as a flat
   sequence of `<label>Field Name: </label>` (or, for two fields —
   "Project Name"/"Description" — a `<b>Field Name:</b>` inline in a small
   table) followed by the value as sibling text/`<br>` tags, spread across
   three side-by-side columns inside `<div id="block_content">`. This
   actor walks every `<label>`/field-style `<b>` tag in document order and
   pairs it with either an inline value (`"Tender Id :46190"` →
   `tenderId: "46190"`) or the text of its following siblings up to the
   next label/bold-field or a `<table>` boundary (HTML comments — the site
   ships several commented-out label rows, e.g. a disabled "Approved
   Budget of the Contract" field — are skipped explicitly, not swallowed
   into the previous field's value). Field count varies: a goods tender
   observed ~24 fields plus a 1-row line-item table; an award notice
   observed ~20 fields plus a 6-row line-item table. Any `<table>` inside
   the block that has a real `<th>` header row is additionally parsed into
   `lineItems` (item no., UNSPSC code, lot name/description, quantity,
   unit of measure).
5. **Nonexistent-id handling**: requesting a tender/award id that does not
   exist returns **HTTP 200** with a near-empty template (only 4-5 generic
   placeholder fields like "BAC Members: -" render — the real "Tender Id
   :<id>" label never appears) rather than a 404 or error page. This actor
   detects that case by checking for the id field's own presence in the
   parsed fields and reports `_error: "not_found"` instead of a
   confusingly sparse "success" record.

## Known limits

- **Award Notices pagination is a confirmed no-op.** `Indexes/getAwardNotices
  ?page=2`, `?page=2&direction=BulletinBoardAward.id`, and the hyphenated
  `/indexes/get-award-notices?...` route all return **byte-identical**
  content to page 1 (only a `Date:` clock string in a `<script>` tag
  differs) — the listing's search form is also `method="POST"`, and GET
  query params for date-range filtering are silently ignored too. This
  means `awards` mode can only ever surface the ~100 most recent award
  notices, not the full historical set. This actor does not special-case
  this: a generic same-first-row-id pagination guard (used for all three
  listing modes, in case any of them regresses this way in the future)
  detects the repeat and stops cleanly rather than looping or duplicating
  records — confirmed live: requesting 250 award-notice items returns
  exactly 100 unique records, not 250 or 100 duplicated 2.5×.
- **No keyword/date/procuring-entity search.** All three bulletin boards
  have a search form in their HTML, but it is `method="POST"` and this
  actor does not attempt to reverse-engineer/replicate it (out of scope
  for this recon pass) — only plain listing + pagination is used.
- **Tender/award document *files* are not downloaded.** The "Documents"
  field's "Preview" link opens a modal (`Tenders/tender_doc_view/<id>/<id>`)
  that returns the full page shell (not the document list) when fetched
  directly without the page's AJAX context — actual attached PDF/DOCX
  links were not reverse-engineered in this pass.
- Dates/amounts are passed through as PRAZ's own raw strings (`dd-Mon-yy
  HH:MM AM/PM`, `US$ 1,234.56`) — not reformatted.
- The Former Opportunities archive's total record count (64,233 at time of
  writing) is a live, continuously-updated figure — do not treat it as a
  fixed constant.

## Diff cadence

Quarterly smoke test recommended. Flag the two markup quirks documented
above (mislabeled `data-label` attributes, double `<thead>` on Former
Opportunities) for re-verification on any future crawl failure — if PRAZ
ever fixes either bug, this actor's positional-parsing approach will
continue to work unaffected either way.
