# Crawling Method — Saint Vincent and the Grenadines eProcurement Portal

**Last verified:** 2026-08-27

Saint Vincent and the Grenadines' government procurement is governed by the
Public Procurement Act of 2010, overseen by the Central Procurement Board.
Unlike its general government portal (`gov.vc`, Joomla, mixed content), SVG
runs a **dedicated eProcurement microsite** at `procurement.gov.vc/eprocure`
— found via a link on `gov.vc/index.php/procurement-notices` ("Procurement
Notices" → "Procurement Notices" → `procurement.gov.vc/eprocure/index.php/current-bids`),
not from any AI-summary or aggregator source.

## Discovery — avoiding the wrong "central procurement portal"

An initial web search surfaced `procurement.gov.vc/` (the bare root) as "the
Central Procurement Portal", but its landing page is a generic Joomla
homepage, not the actual bid listings. The real content lives one level
deeper, under `/eprocure/`, which is its own Joomla instance (separate
`robots.txt`, separate template) mounted at that path. This was confirmed by
following the actual in-page navigation link from `gov.vc`'s procurement
notices page rather than trusting the search engine's own top-level guess —
consistent with this portfolio's repeated finding that AI/search summaries
for small-country government portals often name the wrong host or a
non-existent one (see `lessons-learned.md`).

## Robots.txt

`https://procurement.gov.vc/eprocure/robots.txt` is a stock Joomla
robots.txt: `Disallow` limited to internal system paths (`/administrator/`,
`/bin/`, `/cache/`, `/components/`, `/includes/`, `/installation/`,
`/language/`, `/layouts/`, `/libraries/`, `/logs/`, `/modules/`, `/plugins/`,
`/tmp/`). None of the three listing paths used here
(`/index.php/current-bids`, `/index.php/recently-closed-bids`,
`/index.php/contract-award-notices`) are covered, and there is no
Claude/ClaudeBot/anthropic-ai/GPTBot/CCBot-specific group of any kind.

## Site structure

Three Joomla content-article pages, each wrapping one plain server-rendered
`<table>` inside `div.com-content-article__body`:

1. **Current Bids** (`/index.php/current-bids`) — ~21 rows at recon time.
   Columns: No., Reference Number, Description (title text, linked to the
   bid/ToR PDF), Procuring Entity, Procurement Type (Goods/Services/Works),
   Tender (the solicitation type — Invitation to Bid, Request For
   Expressions of Interest, Request for Quotation, etc.), Submission
   Deadline.
2. **Recently Closed Bids** (`/index.php/recently-closed-bids`) — same
   7-column shape, ~408 rows (historical archive back several years).
3. **Contract Award Notices** (`/index.php/contract-award-notices`) — a
   different, simpler 2-column table: Year → one or more links to quarterly
   "Award of Contracts" PDF bundles (2017-2025 at recon time). This is
   document-level, not contract-level — SVG doesn't publish a structured
   per-contract award table, only periodic PDF reports.

No JavaScript rendering, no API, no pagination controls on any of the three
pages — each GET already returns every row for that list in one response.
Every listing page returned HTTP 200 on the first `curl_cffi` request with
the `chrome124` profile and no special headers; no WAF challenge, no
CAPTCHA, no session/CSRF requirement to *read* the tables (a `login` link
exists in the nav for bidders who want to submit, not required here).

## Extraction

`div.com-content-article__body table` located via BeautifulSoup, then the
first (current/closed) or only (awards) `<table>` inside it is walked
row-by-row:

- **Bids** (current/closed): header row sanity-checked (`"reference
  number"` must appear in the 2nd header cell) before parsing, then each
  data row's 7 `<td>` cells are mapped positionally — no reliance on cell
  order beyond that check, since it's a plain HTML table with no `id`/data
  attributes to key off of. The Description cell's `<a href>` (if present)
  becomes `pdfUrl`; its link text (or the cell's own text, if no link)
  becomes `title`.
- **Awards**: header row sanity-checked (`"year"` in the 1st header cell),
  then each row's 2nd cell can contain *multiple* `<a>` tags (e.g. 2022 has
  six separate quarterly PDFs) — one output record is emitted per link, not
  per row.
- A response's `\xa0` (non-breaking space, UTF-8 `\xc2\xa0`) is normalized
  to a plain space in every extracted text field; the response's own
  `Content-Type: text/html; charset=utf-8` header is correct and was
  already being decoded properly — the raw `\xa0` bytes just render oddly
  in some terminals, not a real encoding bug.
- Both the header-shape check and the "zero data rows extracted" check
  raise `UnexpectedShape` rather than silently returning an empty/corrupt
  list, per this portfolio's fail-loud convention.

## Data quality note

`submissionDeadline` is occasionally blank on a data row — inspection shows
these are rows for a linked Terms of Reference document that shares its
parent bid's deadline (upstream doesn't repeat the value on the ToR row).
Reported as-is (`null`) rather than inferred/copied from the preceding row,
consistent with the "raw passthrough, no fabrication" convention.

## Rejected candidates (other OECS members checked in the same recon pass)

- **Antigua and Barbuda** (`tendersboard.gov.ag`) — clean WordPress site,
  REST API (`/wp-json/wp/v2/posts`) fully open, but all 15 tender posts date
  from 2021-2023 with nothing more recent — the WordPress front-end appears
  abandoned in favor of some other (non-public) channel. Not built: stale
  data would misrepresent itself as a live tenders feed.
- **Dominica** (`procurement.dominica.gov.dm`) — a dedicated procurement
  portal exists, but its "Recent Procurement Notices" and "Recent Awards"
  sections contain literal placeholder content (`"Procurement Notice 2 -
  Lorem ipsum dolor sit amet..."`, company name `"test"`, footer `"Copyright
  2020"`) — a template that was never populated with real data. Not built.
  (Dominica's separate `dominica.gov.dm/notices` Joomla feed is live and
  current, but mixes procurement notices with unrelated content — health
  bulletins, immigration-system notices, environmental management plans —
  with no clean category filter observed; left as a possible future
  candidate requiring more careful category-level discovery.)
- **Saint Lucia** (`in-tendhost.co.uk/goslprocurement`) — the government's
  own `govt.lc/tenders` page links out to a third-party "In-Tend"
  e-procurement SaaS platform. The tender-listing table is populated
  client-side via a jQuery-template (`{{if}}`/`{{html}}` `.tmpl`-style
  bindings) driven by an internal `_Proxy.doAjax("Projects", "GetProjects",
  ...)` call into a minified/compiled ASP.NET resource bundle (no readable
  REST endpoint found without deeper reverse-engineering), and the page also
  loads Google reCAPTCHA — a meaningfully harder target than the other three
  candidates. Left as a future candidate, not attempted this session.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Searched the Apify Store for
"tenders scraper" / "government tenders procurement" (2,753 total hits for
the broader query; 20 inspected in depth). Every genuinely comparable
competitor scrapes a single country's or region's national procurement
portal (Mexico CompraNet, Japan kkj.go.jp, Singapore GeBIZ x2, India GeM/
eProcure, EU TED x2, Germany, Australia, Canada, Malaysia, UNGM) -- none
targets Saint Vincent, any other OECS member, or a Caribbean micro-state
specifically. Scale is modest across the board (7-161 users, 71-1,471 runs;
`gem-portal-scraper` at 161 users/577 runs for India's huge GeM portal is
the outlier -- not a comparable market size to a ~30k-person nation). Every
single one of the 20 inspected uses PAY_PER_EVENT pricing with an
`apify-actor-start` + per-record event pair. One competitor
(`compranet-mexico-scraper`, also Latin-America-focused, built by a
different seller `scrapers_lat`) exposed its full tiered per-record price:
FREE $0.008, BRONZE $0.0076, SILVER $0.0072, GOLD $0.0068 per result. The
other 19 competitors' per-tier prices were not returned by the public
search API (`eventTieredPricingUsd: None` in the response) -- marked
unavailable here rather than guessed. Market saturation: high at the
"tenders scraper" concept level (20+ sellers), but zero saturation for this
specific country -- genuine first-mover gap, consistent with this
portfolio's broader Caribbean tender-vertical findings (Babak 25-29).

**Store category (Phase 5).** Primary: LEAD_GENERATION (structured bid
leads -- reference number, procuring entity, deadline, direct document link
-- is exactly what a bidding company/consultancy searches this category
for). Secondary: BUSINESS (government procurement is a business-data
subcategory). This is the dominant pairing across the competitor set
(`gebiz-procurement-scraper`, `india-eprocure-tender-scraper`,
`myprocurement-malaysia-government-tender-scraper` all use exactly
LEAD_GENERATION + BUSINESS). There is no dedicated GOVERNMENT category in
the current taxonomy (confirmed via `api-search-actors.py --list-categories`,
2026-08-27: 24 categories total, no government/procurement-specific one).

**Pricing model (Phase 6).** Pay-per-event, matching 100% of the surveyed
competitor set. Single chargeable event -- `apify-default-dataset-item`
("Result") -- rather than adding a separate `apify-actor-start` charge:
unlike a heavy-auth/warmup target, every run here is 1-3 plain GET requests
with no session handshake, so a fixed per-run cost isn't economically
justified per this repo's own monetization skill guidance, and a single
event is simpler for a user to estimate cost from.

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source: `compranet-mexico-scraper`,
> the only competitor whose tiered pricing was retrievable; the other 19
> competitors' per-unit prices are unavailable via the public search API).
> Estimated operating cost: sub-cent per result -- a single static HTML GET
> (no JS rendering, no pagination loop, no auth) plus Apify Residential
> proxy overhead; `current`/`awards` runs return ~20-25 records in a few
> seconds, `closed` returns its full ~400-record archive in one request.
> Recommended price: $0.006 per result (FREE tier), stepping down to
> $0.0057 (BRONZE) / $0.0054 (SILVER) / $0.0051 (GOLD), because this
> actor's records carry fewer structured fields than CompraNet's (no
> estimated-amount/CUCOP-category enrichment) and the addressable market
> for one micro-nation's procurement leads is inherently smaller than
> Mexico's federal system -- priced a notch below the one verifiable
> comparable rather than matching it, while staying inside the observed
> competitor band rather than undercutting the whole category.

Margin check: at $0.006/result and near-zero marginal compute/proxy cost
per record, margin is comfortably positive even at the GOLD tier. The FREE
tier price is low enough (a 500-record `closed` run costs $3.00) not to
discourage first-time evaluation.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A bid, closed-bid, or award-document record returned by the scraper."),
  tiered at FREE $0.0060 / BRONZE $0.0057 / SILVER
  $0.0054 / GOLD $0.0051 (PLATINUM/DIAMOND matched to
  GOLD).

Two things learned while doing this, worth recording for the next actor:
1. `pricingInfos` is an append-only history, not a "set current state"
   field -- a `PUT` must send the array starting with an exact copy of
   whatever the server already has stored (its own `createdAt` included),
   plus at most one new entry. Sending a full replacement array throws
   `incorrect-pricing-modifier-prefix`.
2. A brand-new, never-priced actor's *first* `pricingInfos` entry has to
   be flat (`eventPriceUsd`) -- attempting to go straight to
   `eventTieredPricingUsd` on the first entry throws a
   `schema-validation` error ("Charged event must contain price, title,
   and description") even though the request matches the documented
   schema exactly. Worked around by PUTting a flat entry first, then
   appending the real tiered entry as a second entry.

**Store publication (`isPublic: true`) -- blocked by a platform rate
limit, not a capability gap.** Apify enforces an account-wide cap of
**5 Actor publications per day**. The very first publish attempt this
session (on `stvincent-tenders-scraper`) returned
`429 daily-publication-limit-exceeded` before a single actor had been
published, meaning the day's quota was already exhausted by something
outside this session. Categories and pricing are live on all 7 tender
actors built this session; none are public yet. Remaining step: run
`apify api PUT actors/{actorId} -d '{"isPublic": true, "title": "<title>"}'`
for each actor once the daily limit resets, in batches of <=5/day.


**Final verification (Phase 9).** Builds clean; local (`test_local.py`
current/closed/awards) and remote (`apify call`, all three `listType`
values) runs both succeeded with real, non-empty output; dataset schema
matches actual output (fixed one `InvalidRequestError` -- see below); no
login/private data; Python + `curl_cffi`/BeautifulSoup only, no browser
automation; Store category and pricing are evidence-based per above, with
Store publication itself as the one named manual step.

**Bug found during Phase 3 remote testing.** The first `apify call` failed
with `InvalidRequestError: Schema validation failed` on `push_data` --
`output_schema.json` originally declared every payload field as plain
`"type": "string"`, but `submissionDeadline` (and, for other rows,
`pdfUrl`) is legitimately `null` for rows without a document link or a
distinct deadline. Fixed by widening those fields to
`"type": ["string", "null"]` and re-pushing (build 0.1.2) -- caught by the
mandatory `apify call` cloud smoke test, not by local testing, matching
this portfolio's Babak 29 finding that schema bugs need a real cloud run to
surface.
