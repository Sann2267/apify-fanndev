# Crawling Method — Vanuatu Central Tender Board (CTB)

**Last verified:** 2026-08-27

The Central Tender Board (CTB) was established by an Act of Parliament
[Cap 245] of 1998 as a parastatal organization operating under Vanuatu's
Ministry of Finance and Economic Management (MFEM). It publishes tenders
and tender results through its own site, `ctb.gov.vu`.

## Discovery — a different agency, a different robots.txt

This target was flagged directly by this portfolio's own prior research
(Babak 29's "Rekomendasi lanjutan"): Vanuatu's *business registry* was
previously skipped for a `robots.txt` block, but the *tender board* is a
separate government agency on a separate domain — a pattern this project
has already confirmed independently 3 times before (Babak 26) where one
country's registry and its procurement board sit on different hosts with
different bot policies. Confirmed again here: `ctb.gov.vu`'s `robots.txt`
is clean.

## Robots.txt

`https://ctb.gov.vu/robots.txt` is a stock Joomla robots.txt (`Disallow`
limited to `/administrator/`, `/bin/`, `/cache/`, `/components/`,
`/includes/`, `/installation/`, `/language/`, `/layouts/`, `/libraries/`,
`/logs/`, `/modules/`, `/plugins/`, `/tmp/`) with no
Claude/ClaudeBot/anthropic-ai/GPTBot/CCBot-specific group of any kind.

**TLS note:** `ctb.gov.vu` fails strict certificate verification
(`unable to get local issuer certificate`) — an incomplete cert chain on
the server's own side (same class of misconfiguration observed earlier in
this portfolio's Saint Vincent recon pass on `tendersboard.gov.ag`), not a
WAF/anti-bot signal. This actor disables certificate verification for
`curl_cffi` requests to this host specifically.

## Site structure

Two Joomla "Smart Search" (`com_finder`) listing pages, both rendering the
exact same card shape (`<li class="tendersList">`) with standard Joomla
`?start=N` offset pagination, 20 cards per page:

1. **Actual Tenders** (`/en/tenders/actual-tenders`) — currently open
   tenders, 58 records / 3 pages at recon time.
2. **Tenders Results** (`/en/tenders/tenders-results`) — the historical
   archive of the same shape, 139 records / 7 pages (last page
   `?start=120`) at recon time.

Each card already carries, inline, without a per-item detail fetch:
solicitation type + reference number (e.g. "Request For Tender : No.RFT
MFEM MALAMPA 01/25" — the label before " : " varies, "Request For
Proposal" was also observed), title, purchaser (procuring
ministry/department/project), category, submission date, expiry date, and
a full free-text description. A per-tender detail page also exists
(`/en/tenders-category/<id>-<slug>`) with a handful of extra fields (Date
Issued, Completion Date, Opening date/time, Contact Person, Contact Person
Email) but was not fetched here — the list view alone already carries
richer inline data than most other countries' tender listings in this
portfolio, and skipping the per-item fetch keeps this actor to one request
per page of results rather than N+1. `detailUrl` is included in every
record so a user can open the extra fields themselves.

No JavaScript rendering, no API — every GET returned HTTP 200 on the first
`curl_cffi` request (`chrome124` profile, certificate verification
disabled for this host) with no WAF challenge, no CAPTCHA, no
session/CSRF requirement.

## Extraction

BeautifulSoup selects every `li.tendersList` on a page. For each card:
`p.result-text` (split on the first " : " into `tenderType` and
`referenceNumber` — see above), `h4` (title, required — its absence raises
`UnexpectedShape`), and four labeled `div`s (`.purchaser`, `.category`,
`.submissiondate`, `.expirydate`) each shaped like `<div class="...">
<span class='lbl'>Label : </span>value</div>` — parsed by taking the
div's full text and stripping the label span's own text off the front,
rather than hardcoding the exact label wording (robust to a label-text
tweak upstream). Pagination stops when a page returns zero
`tendersList` cards (the real last-page signal) or fewer than the
observed 20-per-page size (a short final page) — not a fixed
page-count assumption, so the actor keeps working if the archive grows.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Reuses this portfolio's "tenders
scraper" competitor scan from the same session (`stvincent-tenders-scraper/
CRAWLING_METHOD.md` — 20 competitors inspected, all scraping single
national procurement portals: Mexico, Japan, Singapore x2, India x2, EU x2,
Germany, Australia, Canada, Malaysia, UNGM). None targets Vanuatu or any
Pacific-island nation. Same conclusion holds here: high saturation at the
"tenders scraper" concept level, zero saturation for this specific
country — consistent first-mover gap.

**Store category (Phase 5).** Primary: LEAD_GENERATION. Secondary:
BUSINESS. Same reasoning and same dominant competitor pairing as
`stvincent-tenders-scraper` (see that actor's CRAWLING_METHOD.md for the
full breakdown) — structured bid leads with purchaser/category/deadline
fields is exactly a lead-generation use case, and there's no dedicated
GOVERNMENT category in the current Store taxonomy.

**Pricing model (Phase 6).** Pay-per-event, matching the surveyed
competitor set. Single chargeable event — `apify-default-dataset-item`
("Result") — no separate `apify-actor-start` charge, for the same reason
as the Saint Vincent actor: every run is a handful of plain GETs with no
auth/warmup cost to justify a fixed per-run fee.

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source:
> `compranet-mexico-scraper`, the only competitor in the surveyed set whose
> tiered pricing was retrievable via the public search API; see
> `stvincent-tenders-scraper/CRAWLING_METHOD.md` for the full competitor
> table). Estimated operating cost: sub-cent per result — static HTML GETs
> across 3-7 pages depending on list type, no JS rendering, no auth. This
> actor's records are richer than the Saint Vincent actor's (full
> free-text description included inline, plus a distinct solicitation-type
> field) and closer in shape to CompraNet's own line items. Recommended
> price: **$0.007 per result (FREE tier)**, stepping down to **$0.0066
> (BRONZE) / $0.0063 (SILVER) / $0.0059 (GOLD)** — priced between the
> Saint Vincent actor's $0.006 (thinner records) and CompraNet's $0.008
> (larger federal market), reflecting the fuller per-record content here
> while still recognizing a single Pacific micro-nation is a smaller
> addressable market than Mexico's federal procurement system.

Margin check: positive at every tier given the sub-cent operating cost. A
full 139-record `results` run costs $0.97 at the FREE-tier price — low
enough not to discourage first-time evaluation.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A tender or tender-result record returned by the scraper."),
  tiered at FREE $0.0070 / BRONZE $0.0066 / SILVER
  $0.0063 / GOLD $0.0059 (PLATINUM/DIAMOND matched to
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
current`/`results`, full-pagination smoke test: 58 + 139 records, zero
errors) and remote (`apify call`, both `listType` values) runs both
succeeded with real, non-empty output; dataset schema declares nullable
types for every optional field from the start (learned from the Saint
Vincent actor's Phase 3 `InvalidRequestError`, applied proactively here
rather than discovered by a second failed cloud run); no login/private
data; Python + `curl_cffi`/BeautifulSoup only, no browser automation;
Store category and pricing are evidence-based per above, with Store
publication itself as the one named manual step.
