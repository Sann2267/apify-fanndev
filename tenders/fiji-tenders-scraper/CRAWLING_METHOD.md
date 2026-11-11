# Crawling Method — Fiji Government Tenders (TenderLink)

**Last verified:** 2026-08-27

Fiji's public procurement is administered by the Fiji Procurement Office
under the Ministry of Finance, which runs its tendering through the
third-party TenderLink SaaS platform (`portal.tenderlink.com/financefiji`)
rather than a custom-built government site.

## Discovery — a different TenderLink deployment than expected

This session already flagged TenderLink as a harder-than-average target
once, in the Saint Lucia recon (`stvincent-tenders-scraper/
CRAWLING_METHOD.md`): that deployment renders its tender table
client-side via a jQuery `.tmpl`-style template driven by an internal
`_Proxy.doAjax(...)` call into a minified ASP.NET bundle, with no readable
REST endpoint found without deeper reverse-engineering, plus a Google
reCAPTCHA on the page.

Fiji's TenderLink deployment turned out to be genuinely different: its
public list pages (`/alltenders/`, `/tenderfunction/?tenderaward=&
allawards=`) are plain, fully server-rendered HTML tables — no jQuery
template, no AJAX call needed to see the data, no CAPTCHA anywhere on
these pages. The site's *root* URL (`/financefiji/`) does redirect to a
login page, and viewing a tender's full details/documents or responding
requires TenderLink registration — but the two specific list views used
by this actor are public without any of that, discovered by trying the
exact URLs surfaced in a web search result's own title ("Ministry of
Finance, Government of Fiji - Recently Awarded Tender Notices") rather
than assuming the whole platform behaves like the Saint Lucia instance.
**Lesson applied:** don't generalize one deployment's difficulty to every
deployment of the same third-party platform — verify each government's
own instance independently, the same "don't assume, verify" principle
already noted in this portfolio for proxy requirements (Babak 29) and TLS
profile blocklisting (`.ai/CLAUDE.md` point 2).

## Robots.txt

`https://portal.tenderlink.com/robots.txt` doesn't exist as an actual
robots.txt file — the bare domain serves its own marketing homepage at
that path instead (HTTP 200, `text/html`, not `text/plain`). Treated as
unrestricted, per this portfolio's standing convention for a missing
robots.txt (no rule to violate).

## Site structure

Two pages, no pagination on either (each GET returns every row in one
response):

1. **Current tenders** (`/financefiji/alltenders/`) — ~17 rows at recon
   time. Table columns: Notice (reference number), Summary (title,
   sometimes with the procuring entity's name appended), Close Date/Time.
2. **Awards** (`/financefiji/tenderfunction/?tenderaward=&allawards=`) —
   tenders awarded within the past 36 months, ~369 rows at recon time.
   Identical 3-column shape, but the Summary cell for an awarded tender
   ends with `Awarded to: <company name>` roughly 88% of the time (324 of
   369 at recon time) — the remaining ~12% have no winner name published
   upstream, reported as `null` rather than guessed.

Both pages carry two `<table>` elements; the real data table is
identified by checking for a header row whose first cell is exactly
"Notice" (the first table on each page is just an instructional banner
paragraph wrapped in a single-cell `<table>`), rather than assuming a
fixed table index.

## Extraction

BeautifulSoup finds the data table via the "Notice" header-cell check
described above, then reads each row's 3 `<td>` cells positionally. For
`awards`, a regex (`Awarded to:\s*(.+)$`, case-insensitive) strips the
winner name off the end of the Summary text into its own `awardedTo`
field, leaving `summary` as just the tender description — the same
"split a compound upstream label into structured fields" approach already
used for Vanuatu's `tenderType`/`referenceNumber` split earlier this
session.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Reuses this session's "tenders
scraper" competitor scan (20 competitors — see `stvincent-tenders-scraper/
CRAWLING_METHOD.md`), plus a Fiji-specific re-check
(`python api-search-actors.py --query "Fiji tenders"`) that returned zero
genuinely comparable hits. Fiji is a larger, better-known Pacific economy
than this session's other Pacific tender actors, so this extra check was
worth doing explicitly rather than assuming the same first-mover gap
without verifying.

**Store category (Phase 5).** Primary: LEAD_GENERATION. Secondary:
BUSINESS. Same reasoning as this session's other tender actors.

**Pricing model (Phase 6).** Pay-per-event, single chargeable event
`apify-default-dataset-item` ("Result") — plain GETs, no auth/warmup cost
to justify a fixed per-run fee.

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source:
> `compranet-mexico-scraper` — see `stvincent-tenders-scraper/
> CRAWLING_METHOD.md`). Estimated operating cost: sub-cent per result, a
> single GET per list type. This actor's records are thinner than
> Vanuatu's/Samoa's (3 fields plus a parsed winner name) but the `awards`
> mode's ~369-record archive with real winning-bidder names is
> comparable in business value to CompraNet's own line items (also a
> Latin-America-analog market). Recommended price: **$0.006 per result
> (FREE tier)**, stepping down to **$0.0057 (BRONZE) / $0.0054 (SILVER) /
> $0.0051 (GOLD)** — matching the Saint Vincent and Kiribati actors'
> pricing (also this session's other thinner-record tender actors, for
> consistency across comparable record shapes).

Margin check: positive at every tier. A full 369-record `awards` run
costs $2.21 at the FREE-tier price — reasonable for a 36-month
lead/competitive-intelligence archive with named winners.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A current-tender or award record returned by the scraper."),
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


**Final verification (Phase 9).** Builds clean; local (`test_local.py
current`/`awards`, full-archive smoke test: 17 + 369 records, zero
errors) and remote (`apify call`, both `listType` values) both succeeded
with real, non-empty output on the first cloud attempt (nullable field
types applied proactively in `output_schema.json` from the start); no
login/private data — the public list views require no authentication,
even though the platform as a whole is login-gated for other functions;
Python + `curl_cffi`/BeautifulSoup only, no browser automation; Store
category and pricing are evidence-based per above, with Store publication
itself as the one named manual step.
