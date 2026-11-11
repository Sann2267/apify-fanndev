# Crawling Method — Kiribati Central Procurement Unit

**Last verified:** 2026-08-27

Kiribati's public procurement is administered by the Central Procurement
Unit within the Ministry of Finance and Economic Development (MFED), which
runs its own Drupal site at `procurement.gov.ki`.

## Discovery

Kiribati also has a TenderLink-hosted third-party e-tendering portal
(`portal.tenderlink.com/kiribatimofaed/`) — the same class of platform
already flagged as harder in this session's Saint Lucia and (partly)
Samoa recon. `procurement.gov.ki`'s own site was checked first and turned
out to carry the full tender archive natively, so the third-party portal
was not touched. The homepage's intro article (`/article1`) itself carries
no listing, only descriptive text — the actual data lives at `/tender-list`
(found via that article's own in-page links, alongside `/tender`,
`/node/23` "Contracts", and a PDF-only "Procurement Manual 2002" page,
none of which carry the live tender table).

## Robots.txt

`https://procurement.gov.ki/robots.txt` is a stock Drupal robots.txt
(`Disallow` limited to internal system paths -- `/admin/`, `/user/login/`,
`/search/`, etc., same boilerplate as Tonga's `finance.gov.to`, apparently
a shared regional Drupal government template) with no
Claude/AI-crawler-specific group.

## Site structure

`/tender-list` is a single Drupal View rendering one chronological table —
**not** split into separate current/closed pages like most other tender
actors in this portfolio. Columns: Procurement No. (links to a per-tender
detail node), Procuring Entity (ministry acronym), Brief Description, Open
Date, Close Date. Standard Drupal pager, `?page=N` (0-indexed), 10 rows per
page. At recon time, paging confirmed real (not a stub/broken pager -- each
page's first row differed) out to at least page 50 with data still present
at page 50 (references from 2021, e.g. `16-G012-21`) and empty at page 100
— roughly 500+ records total, making this the largest single-list tender
archive built in this portfolio's Pacific-nation batch this session.

A per-tender detail node (e.g. `/-617`) additionally exposes downloadable
tender documents (a mix of `.zip`, `.docx`, etc. per tender) via a
well-structured Drupal field (`div.field--name-field-document`), plus
ISO-8601 `datetime` attributes on the open/close date `<time>` elements.
This actor does **not** fetch per-tender detail pages, given the archive's
size (500+ records) would multiply request volume for data (documents)
most bulk-list consumers don't need per record — `detailUrl` is included
in every record so a user can open a specific tender's own page for its
documents.

No JS rendering, no API — every GET returned HTTP 200 on the first
`curl_cffi` request (`chrome124` profile) with no WAF challenge, no
CAPTCHA, no session/CSRF requirement.

## Extraction

BeautifulSoup finds the page's `<table>`; if absent, that's treated as
"past the last page" (a normal pagination end state, not an error). If a
table IS present, its header row is sanity-checked ("procuring entity"
must appear in the 2nd header cell) before parsing, then every row with
5+ `<td>` cells is read positionally (reference+link, entity, description,
open date, close date) — a plain HTML table with no `id`/data attributes
to key off of, same approach as this session's Saint Vincent actor.
`UnexpectedShape` is raised if the header check fails or if the header
parses but zero data rows come out, never silently returning an
empty/corrupt list on a page that legitimately has a table.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Reuses this session's "tenders
scraper" competitor scan (20 competitors — see `stvincent-tenders-scraper/
CRAWLING_METHOD.md`). None targets Kiribati or any Pacific-island nation.
Same first-mover conclusion as this session's other Pacific tender actors
(Vanuatu, Samoa, Palau).

**Store category (Phase 5).** Primary: LEAD_GENERATION. Secondary:
BUSINESS. Same reasoning as the other tender actors built this session.

**Pricing model (Phase 6).** Pay-per-event, single chargeable event
`apify-default-dataset-item` ("Result") — plain paginated GETs, no
auth/warmup cost to justify a fixed per-run fee.

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source:
> `compranet-mexico-scraper` — see `stvincent-tenders-scraper/
> CRAWLING_METHOD.md`). Estimated operating cost: sub-cent per result —
> the largest archive of this session's Pacific tender actors (500+
> records) means a full-archive run makes more HTTP requests than the
> others (50+ pages at 10 records/page vs. Vanuatu's 7 pages at 20/page),
> but each request is still a small plain GET. This actor's records are
> thinner than Vanuatu's or Samoa's (no inline description-length text
> beyond a short brief, no documents inline), closer in richness to the
> Saint Vincent actor. Recommended price: **$0.006 per result (FREE
> tier)**, stepping down to **$0.0057 (BRONZE) / $0.0054 (SILVER) /
> $0.0051 (GOLD)** — matching the Saint Vincent actor's pricing exactly,
> since both have comparably thin per-record fields relative to the
> Vanuatu/Samoa actors' richer inline content.

Margin check: positive at every tier. A large 500-record full-archive pull
costs $3.00 at the FREE-tier price — reasonable for what would otherwise
require manually paging through 50 archive pages by hand.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A tender record returned by the scraper."),
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


**Final verification (Phase 9).** Builds clean; local (`test_local.py`,
including a 200-record/20-page pagination smoke test, zero errors, zero
missing reference numbers) and remote (`apify call`) both succeeded with
real, non-empty output on the first cloud attempt (nullable field types
applied proactively in `output_schema.json` from the start); no
login/private data; Python + `curl_cffi`/BeautifulSoup only, no browser
automation; Store category and pricing are evidence-based per above, with
Store publication itself as the one named manual step.

## Rejected/deprioritized candidates (same recon pass)

- **Marshall Islands** — web search surfaced only third-party aggregators
  and vague references to an "Office of the Attorney General" and
  "Marshall Islands Public Procurement Board" with no resolvable official
  URL found. Not pursued further this session — a candidate for deeper
  discovery (checking `rmigovernment.org` or ministry-specific sites
  directly) in a future session rather than a confirmed block or dead end.
- **Federated States of Micronesia (FSM)** — confirmed via search to have
  no single national e-procurement portal; procurement is decentralized
  across individual state/ministry sites. Not pursued this session — would
  need a per-state discovery approach rather than one target, out of scope
  for the time available.
