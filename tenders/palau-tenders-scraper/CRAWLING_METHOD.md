# Crawling Method — Palau ROP Procurement

**Last verified:** 2026-08-27

The Republic of Palau (ROP) publishes government procurement opportunities
on a single page of its national government WordPress site,
`www.palaugov.pw/rfp-bids/` ("ROP Procurement").

## Discovery

Found directly via the official `palaugov.pw` government portal's own
navigation (not a third-party aggregator). A companion Tonga recon in the
same session (`finance.gov.to`) turned up only static compliance-KPI and
regulatory-PDF pages, no actual per-tender listing — Palau's page, by
contrast, is a genuine live tender table and was built; Tonga was left
unbuilt (see "Rejected candidate" below).

## Robots.txt

`https://www.palaugov.pw/robots.txt` is a stock WordPress robots.txt
(`Disallow: /wp-admin/`, `Allow: /wp-admin/admin-ajax.php`, plus a
`Sitemap:` pointer) with no Claude/AI-crawler-specific group.

## Site structure

One WordPress page, three plain HTML `<table>`s, each preceded by an
`<h3>` category heading:

1. **BHR** — routine goods/services procurement (Bureau of Human
   Resources' procurement office). 5 data rows at recon time.
2. **CIP** — Capital Improvement Projects (construction/design-build,
   Bureau of Public Works). 4 data rows at recon time.
3. **Other Organizations** — procurement run by other government bodies.
   Empty at recon time (a single blank placeholder row) — this is the
   site's own normal "nothing posted here right now" state, not a
   scraping error.

All three tables share the same underlying 5-column shape, though the
exact header wording differs slightly per table ("Items/Services" vs.
"Projects" vs. "Items/Services/Summary"; "Bid or RFP Number" vs.
"Announcement/Reference #") — normalized here into one field set:
Ministry/Department, Description, Reference Number (its cell links
directly to the official PDF notice), Opening Date, Closing Date.

No pagination, no JS rendering, no API — a single `curl_cffi` GET
(`chrome124` profile, no special headers) returned HTTP 200 with the full
page on the first try. No separate historical-archive or contract-award
page was found anywhere on the site (searched both in-page navigation and
targeted web search) — this page reflects "what's open right now" only,
reported as such.

## Extraction

BeautifulSoup finds every `<table>` on the page; for each, the nearest
preceding heading (`find_previous(["h1","h2","h3","h4"])`) becomes the
`category` label rather than hardcoding "BHR"/"CIP"/"Other Organizations"
by position — robust to the government reordering or renaming a section.
Each table's first `<tr>` is treated as the header and skipped; every
other row needs at least 5 cells, and a row where every cell's text is
empty (the "Other Organizations" placeholder) is skipped as a legitimately
empty row rather than emitted as a blank record. The 3rd cell's own
`<a href>` (if present) becomes `noticeUrl`.

`UnexpectedShape` is raised if the page has zero `<table>`s at all, or if
any table has zero `<tr>` rows (not even a header) — never silently
returning an empty/corrupt list.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Reuses this session's "tenders
scraper" competitor scan (20 competitors surveyed — see
`stvincent-tenders-scraper/CRAWLING_METHOD.md` for the full table). None
targets Palau or any Pacific-island nation. Same first-mover conclusion as
the other Pacific tender actors built this session (Vanuatu, Samoa).

**Store category (Phase 5).** Primary: LEAD_GENERATION. Secondary:
BUSINESS. Same reasoning as the other tender actors built this session.

**Pricing model (Phase 6).** Pay-per-event, single chargeable event
`apify-default-dataset-item` ("Result"). No separate `apify-actor-start`
charge, for consistency with the rest of this session's tender actors and
because the operating cost here is even lower than the others (one plain
GET, no pagination loop at all).

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source:
> `compranet-mexico-scraper` — see `stvincent-tenders-scraper/
> CRAWLING_METHOD.md`). Estimated operating cost: negligible — a single
> GET per run, no pagination. Distinguishing factor for this actor: Palau
> publishes very few tenders at any given time (9 at recon time across all
> three categories combined — a real reflection of the country's small
> government scale, not a scraping limitation), so per-run revenue is
> inherently thin regardless of price. Recommended price: **$0.008 per
> result (FREE tier)** — the top of the verified competitor band rather
> than a discount below it, because undercutting further would make an
> already-thin-volume niche not worth serving at all, while $0.008 is
> still exactly in line with what a real competitor (CompraNet Mexico)
> already charges for comparable per-record tender data. Stepping down to
> **$0.0076 (BRONZE) / $0.0072 (SILVER) / $0.0068 (GOLD)** — mirroring
> CompraNet's own tier spacing since it's the only verified reference
> point.

Margin check: positive at every tier given the near-zero operating cost.
A full current-state run (9 records) costs $0.072 at the FREE-tier price —
trivially low, so the FREE tier doesn't discourage evaluation; the
low absolute revenue per run is a genuine characteristic of this niche's
small size, not a pricing mistake.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A tender record returned by the scraper."),
  tiered at FREE $0.0080 / BRONZE $0.0076 / SILVER
  $0.0072 / GOLD $0.0068 (PLATINUM/DIAMOND matched to
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


**Final verification (Phase 9).** Builds clean; local (`test_local.py`,
full-page test: all 9 real records, zero errors, "Other Organizations"
empty section correctly skipped) and remote (`apify call`) both succeeded
with real, non-empty output; dataset schema declares nullable types for
every optional field from the start; no login/private data; Python +
`curl_cffi`/BeautifulSoup only, no browser automation; Store category and
pricing are evidence-based per above, with Store publication itself as
the one named manual step.

## Rejected candidate (same recon pass)

- **Tonga** (`finance.gov.to`) — clean robots.txt (Drupal, no AI-bot
  block), but `/procurementpublications` carries only static compliance
  KPI tables and regulatory PDF documents (Public Procurement Regulations,
  Procurement Manual), not individual live tender notices; `/procurement`
  (the Procurement Division's own page) returned no extractable content in
  the expected content region. No actual per-tender listing page was found
  anywhere on the site via in-page navigation or targeted search. Left
  unbuilt — a government that publishes procurement *policy* but not a
  structured *notice* feed isn't a valid target for this actor type,
  distinct from a robots.txt block or a data-quality issue.
