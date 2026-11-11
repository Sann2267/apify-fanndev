# Crawling Method — Namibia Government Tenders (CPBN)

**Last verified:** 2026-08-27

## Target discovery — two candidate platforms, only one is real

The brief pointed at "Central Procurement Board of Namibia (CPBN)". Web
search surfaced two official-looking domains, both genuinely CPBN's, but
serving very different content:

1. **`eprocurement.gov.na`** — a Liferay portal ("Portal Ariel" theme, JSP
   `senna`/AUI markup). This is the platform the Government Procurement Act
   (Act No. 15 of 2015) formally references, and it does exist and respond.
   But crawling its full sitemap (21 pages total, enumerated via
   `/sitemap.xml`) found **no live tender/bid listing at all** — only static
   policy/legislation pages (`legistrations`, `guidelines1`, `directives1`,
   `templates1`, `policies1`), a document library of PDF folders (procurement
   plans, annual reports, standard bidding *form templates*, media articles),
   an `expression-of-interest` page, and a `news-and-announcements` page —
   none of which contained an actual open-tenders table. Site search
   (`/search?q=tender`) only turned up mentions of the word "tender" inside
   legislation/report PDFs, never a live listing. This portal reads as the
   policy/document-repository side of CPBN's web presence, effectively
   dormant for day-to-day bid publishing.
2. **`www.cpbn.com.na`** — CPBN's own corporate site (different tech stack
   entirely: PHP/CodeIgniter-style `index/<controller>/<method>` routing,
   `PHPSESSID` cookie, LiteSpeed server). Its "Bids" nav dropdown links to
   eight listing views (`/index/external/2` through `/99`) titled "Bids:
   Open", "Bids: Closed & under evaluation", "Bids: Cancelled", "Bids:
   Notice for Selection of Awards", etc. — and these genuinely have live,
   current data (a bid closing 2026-08-05, another issued 2026-06-19, i.e.
   within weeks of this survey's "today" of 2026-08-27). **This is the real,
   actively-maintained source** and what this actor scrapes.

This mirrors the Babak 25 "domain-hint mismatch" pattern seen elsewhere in
this vertical — the statutorily-named platform isn't always the one that's
actually alive; always verify against real, dated content rather than
trusting the platform name alone.

## robots.txt

- `https://eprocurement.gov.na/robots.txt` → real file, `User-Agent: *` /
  `Disallow:` (empty — allows everything), plus a `Sitemap:` line. Clean.
- `https://www.cpbn.com.na/robots.txt` → no such route exists; the app's own
  catch-all controller renders the normal homepage template at that path
  with a `200` (same pattern documented for `ghaneps.gov.gh` — a
  server-rendered app with no static-file route for `/robots.txt`, not a
  deliberate block). No `Disallow` rule of any kind exists on either host,
  and no plain-English AI/bot-prohibition text was found anywhere.

## No login required to view listings or bid detail

Checked directly against every one of the site's eight "Bids" listing views
plus real bid-detail pages pulled from them — not assumed:

- `GET /index/external/2` ("Open"), `/3` ("Under evaluation"), `/5`
  ("Cancelled"), `/6` ("Awarded"), `/7` ("Clarifications"), `/9` ("Opening
  register"), `/99` ("Notices"), `/98` ("All bids") → all `200`, zero
  cookies/auth needed, full HTML with every row embedded server-side.
- `GET /index/bid/<id>` for ids pulled from the above (e.g. `109`, `98`,
  `101`) → `200`, full bid detail (category, institution, description,
  document price, closing date, opening-of-bids logistics, clarification
  contact, pre-bid meeting info).

A **login wall does exist**, but only for actually **downloading** some
(not all — see Data quirks below) attached PDF documents: clicking a
document link calls `openModalRemoteContent('.../ajax/download/<id>')`,
which returns a lead-generation **form** (Full Name / Phone / Email /
Company) rather than the file directly. This actor does not fill in that
form or attempt to bypass it — it only records the document's label and
that URL as metadata, exactly matching the "fine if only BIDDING/downloading
requires an account" carve-out (viewing every bid's title, reference number,
dates, and full text description needs no login at all).

## No WAF challenge

`curl_cffi` `chrome124`, `safari17_0`, and `edge101` all return identical
`200`s with identical byte counts on `www.cpbn.com.na` — no `cf-ray`, no
bot-challenge HTML, no distinctive anti-bot cookies. `chrome124` used for
consistency with the portfolio default.

## Data source — eight listing views + one detail view, all server-rendered HTML, no pagination needed

No JSON API or SPA bundle exists — everything is server-rendered HTML from
the PHP app. Each listing view (`/index/external/<n>`) renders **every** row
it has as a `<div class="card">` inside a single `<table
id="activeBidsTable"><tbody class="page-data">` — the page's own DataTables
plugin (`$('#activeBidsTable').DataTable({...})`) only paginates
**client-side** via JS after the fact, so the full row count is already
present in one HTTP response (confirmed: "All bids" returns all 694 cards in
one `886 KB` response, "Awarded" returns all 106, etc.). This actor therefore
makes exactly one request per `listType` — no widget-id/page-number scheme
like `ghana-tenders-scraper` needed.

| `listType` | URL | Rows (2026-08-27) | Notes |
|---|---|---|---|
| `open` | `/index/external/2` | 0 | Genuinely empty at survey time — no bid was between publication and its closing date right then. Reported honestly (0 records), not faked. |
| `underEvaluation` | `/index/external/3` | 12 | |
| `cancelled` | `/index/external/5` | 43 | |
| `awarded` | `/index/external/6` | 106 | "Notice for Selection of Awards" |
| `clarifications` | `/index/external/7` | 169 | |
| `openingRegister` | `/index/external/9` | 194 | |
| `notices` | `/index/external/99` | 0 | Also genuinely empty at survey time. |
| `all` | `/index/external/98` | 694 | Full historical archive, spans years. |

### Two card shapes on every listing (handled generically, not an error)

1. **Bids with their own detail page** — title is an `<a href="/index/bid/<id>">`,
   info line reads `Reference number: X | Closing Date and Time: Y | More
   Details`.
2. **Older PDF-only notices** (602 of 694 rows on the "All bids" view) — title
   is plain text (no link), info line is just `Date: Y`. These predate the
   interactive bid-tracking system; their reference number is usually
   embedded in the free-text title instead of being a separate field.

The parser does not hardcode either shape: it splits the info line on `|`,
then each segment on the first `:`, and slugifies the label into a camelCase
key (`"Reference number"` → `referenceNumber`, `"Closing Date and Time"` →
`closingDateAndTime`, `"Date"` → `date`). A future label CPBN adds flows
through automatically; only a listing page that loses `table#activeBidsTable`
entirely raises `UnexpectedShape` (fail loud, not silently empty).

### Bid detail page (`mode: "detail"`)

`GET /index/bid/<id>` renders a `<tbody class="page-data">` of `<tr><th
class="title">Label</th><td class="value">Value</td></tr>` pairs. Field
count and set vary per bid (a Works tender has a pre-bid-meeting/site-visit
field that a Goods tender doesn't) — parsed generically the same
label-slugify way as the listing info line, so new fields pass through
automatically. An invalid/unrecognized `bidId` (tried `999999`, `0`, `abc`)
all fall through to CPBN's own generic homepage (`<title>CPBN</title>`, no
`tbody.page-data` at all) instead of a `404` — detected and reported as
`not_found_or_restricted`, not a crash.

### Document quirk — some downloads are gated, some aren't

Every bid/notice lists its attached PDFs as `<a class="download-link"
onclick="openModalRemoteContent('<url>')">`. Two distinct URL shapes were
observed for that same attribute, both left as-is (not resolved further):

- `https://www.cpbn.com.na/ajax/download/<id>` — returns an HTML **form**
  requesting Full Name / Phone / Email / Company before the actual file is
  released. This is the "bidding-adjacent" gate the actor does not bypass.
- `https://www.cpbn.com.na/uploads/files/<hash>.pdf` — a **direct**, fully
  public PDF, no form at all (confirmed: `200`, `application/pdf`, 385 KB,
  zero auth). Seen mainly on the older PDF-only notices (shape 2 above).

Both are recorded identically as `{label, downloadUrl}` — this actor makes
no attempt to distinguish or fetch either, since neither is required to get
the actual tender metadata (title, dates, institution, description), and
attempting to auto-fill the lead-gen form with fabricated contact details
would cross the "no fake identity to unlock data" line.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking observed on `www.cpbn.com.na`.
