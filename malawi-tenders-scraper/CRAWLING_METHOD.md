# Crawling Method — Malawi Government Tenders (PPDA)

**Last verified:** 2026-08-27

## Target discovery — the strong hint checked out, but pointed to the wrong host

The dispatch hint (from Sierra Leone's build) was that `egp.nppa.gov.sl`'s
JS bundles referenced `maneps.mw` and `ppda.mw`, suggesting the same e-GP
vendor built Malawi's platform. This was verified directly:

- **`maneps.mw`** is real and live (`200`, DNS resolves, TLS valid). It is
  a Next.js single-page app — its homepage HTML links directly to
  `peragosystems.com/home`, confirming **Perago Systems** as the vendor,
  same as Sierra Leone's `egp.nppa.gov.sl`. This is MANEPS, Malawi's
  transactional e-Government Procurement platform.
- **`ppda.mw`** is also real and live — but it is *not* a Perago Systems
  page at all. It is the **Public Procurement and Disposal of Assets
  Authority (PPDA)**'s own corporate website, a separate Laravel/Blade +
  Bootstrap + DataTables application (confirmed via `csrf-token` meta tag,
  `/build/assets/app.*.js` Vite manifest naming, and Bootstrap 5.2 CDN
  includes — nothing resembling the Next.js bundle Malawi/Sierra Leone
  share on the MANEPS/e-GP side).

Unlike Sierra Leone, **no outage was found on either host.** Both
`maneps.mw` and `ppda.mw` returned clean `200`s on every path probed.

### MANEPS (`maneps.mw`) — real, live, but client-rendered

`maneps.mw/procurement-notice` returns ~53KB of pure Next.js `<head>` +
script-tag boilerplate — the literal word "tender" never appears in the
server-rendered response; the page needs a JS engine to populate itself
(same architecture as Sierra Leone's `egp.nppa.gov.sl/procurement-notice`,
just without that host's specific backend 502 outage). No `*-egp.maneps.mw`
API subdomains exist (Malawi doesn't mirror Sierra Leone's
`tendering-egp.*` naming scheme — those hostnames don't even resolve), and
`maneps.mw/api/*` paths just 404 into the SPA's client-side fallback route,
not a real API response. This portfolio's HTTP-only constraint cannot
execute the JS needed to populate this page, so MANEPS is not this actor's
data source.

### PPDA's own site (`ppda.mw`) — the actual target, and a better one than expected

PPDA's own website turned out to publish the **exact same kind of
procurement notices as fully server-rendered HTML**, with zero JS
dependency — better than the "old WordPress fallback" pattern seen in
Sierra Leone, since this isn't a legacy backup system at all, just the
regulator's normal corporate site doing double duty as the public notice
board. Five categories share one page template (Bootstrap + a DataTables
`<table>` per page):

| URL | Table id | Rows observed (2026-08-27) |
|---|---|---|
| `ppda.mw/tenders` | `tenderstable` | 39, all dated 2026-08-08 through 2026-08-26 (currently open) |
| `ppda.mw/award-notices` | `awardstable` | 104, back to January 2024 |
| `ppda.mw/intentions-to-award` | `intentionstable` | 171, back to July 2023 |
| `ppda.mw/debarments` | `debarmentstable` | 5, back to 2025 |
| `ppda.mw/admin-review-notices` | `adminreviewstable` | 0 — page shows "No publications available at the moment" instead of a table |

Confirmed with a plain `curl` (no session, no cookies, generic UA) on the
first try — `200` with full real data. All four `curl_cffi` impersonation
profiles (`chrome124`, `chrome131`, `safari17_0`, `edge101`) also returned
byte-identical `200`s. No Cloudflare/Akamai/DataDome markers, no CAPTCHA,
no rate-limiting across repeated requests. DataTables' own JS
(`cdn.datatables.net/1.13.2/js/jquery.dataTables.min.js`) is loaded on
every page and calls `.DataTable()` on all seven table ids the site
knows about (`tenderstable`, `intentionstable`, `awardstable`,
`publicationstable`, `newsletterstable`, `debarmentstable`,
`adminreviewstable`) regardless of whether that particular page's table is
present — but this only adds client-side sort/search/pagination sugar;
**every row is already present in the initial HTML response**, the same
"DataTables/TablePress renders everything server-side" pattern already
seen for Ghana ORC and Sierra Leone NPPA.

`publications` and `newsletters` also exist as pages/tables on `ppda.mw`
but are general agency communications (media releases, OGP updates), not
procurement notices — out of scope for this actor.

## robots.txt / WAF

`ppda.mw/robots.txt`:

```
User-agent: *
Disallow:
```

An empty `Disallow` under `*` = allow everything. No mention of
`Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai`/`GPTBot` anywhere in the file, no blanket disallow.
(`maneps.mw/robots.txt` is `Allow: /` with only `/api/`, `/_next/`,
`/manage/`, `/_app/` disallowed — moot since this actor never touches that
host, but noted for completeness: even if MANEPS becomes scrapable in a
future recon pass, respecting that `/_next/`/`/api/` disallow would rule
out exactly the paths that would carry the SPA's data anyway.)

No login wall for viewing any of the five notice pages — all return `200`
directly with real data, no redirect to a login/auth page. PPDA does have
`/supplier-registration` and other bidder-facing flows elsewhere on the
site, but those are for participating in procurement, not for reading the
public notice boards.

## Data source — S1-ppda-notice-tables

A single GET per notice type: `GET https://ppda.mw/<path>` (see the table
above for the five paths). Each response is a complete, parameter-free,
server-rendered HTML page containing the whole current board for that
category. `extractor.py` reads the `<thead>` column labels dynamically and
maps them to canonical field names via a small lookup table
(`HEADER_FIELD_MAP` in `constants.py`), rather than hardcoding a fixed
column list per page — this means the same parsing function handles all
five notice types (four populated, one empty) without per-type special
casing, and would keep working if PPDA added or reordered a column.

### Known upstream data-quality notes (not bugs in this actor)

- **Dates are already clean ISO 8601** (`"2026-08-26"`, `"2023-07-26"`)
  on every page checked — unlike Sierra Leone's NPPA board or many other
  registries in this portfolio, no loose/lenient date parsing was needed.
- **The debarments board has no Institution or Reference No. column** —
  its table only has Title, Publish Date, and Attachment. `institution`
  and `referenceNo` are simply absent (omitted, not `null`) on
  `noticeType: "debarments"` records.
- **The intentions-to-award board has a "Financial Year" column**
  (Malawi's government FY notation, e.g. `"2023/2024"`) not present on
  any other board — passed through as `financialYear`, a plain string,
  not a parsed date.
- **A typo in a storage path**: debarment PDF links live under
  `ppda.mw/storage/documents/ebarments/` (missing the leading "d" —
  confirmed in the raw HTML, not introduced by this actor) with a doubled
  slash before the filename. Passed through verbatim per the "raw
  passthrough" convention — this actor does not attempt to "fix" upstream
  URLs.
- **`admin-review-notices` was genuinely empty** at build time — handled
  as a valid zero-row result (PPDA's own "No publications available at
  the moment" text is treated as the empty-state marker), not an error.
  If PPDA ever publishes to that board, the same generic header-driven
  parser would handle it automatically as long as it keeps using table id
  `adminreviewstable` (confirmed as the id the site's own shared
  DataTables-init script expects).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No blocking of any kind was ever observed on this target — the
only real finding on this host was that its flashy modern e-GP sibling
(MANEPS) needs a browser to render, while the regulator's own corporate
site quietly does the whole job HTTP-only.
