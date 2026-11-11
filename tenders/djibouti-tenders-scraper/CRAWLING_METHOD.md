# Crawling Method — Djibouti Marches Publics

**Last verified:** 2026-08-27

Djibouti's public procurement is administered under Law No. 2013-027 of
28 June 2013, overseen by the Commission Nationale des Marches Publics /
Autorite de Regulation des Marches Publics, which runs the national
portal `marchespublics.gouv.dj`.

## Robots.txt

`https://marchespublics.gouv.dj/robots.txt` is `User-agent: * /
Disallow:` — the `Disallow` directive is present but has no value, which
per the robots.txt standard means nothing is disallowed (a blanket
allow). No Claude/AI-crawler-specific group.

**TLS note:** the host fails strict certificate verification
(`unable to get local issuer certificate`) — an incomplete cert chain on
the server's own side, the same class of misconfiguration already seen
on `ctb.gov.vu` and `tendersboard.gov.ag` earlier in this portfolio, not
a WAF signal. Certificate verification is disabled for this host in
`curl_cffi`.

## Site structure

Two pages, built on different underlying tech within the same Laravel
site:

1. **`/marches`** ("Tous les marches") — a Laravel Livewire component.
   Livewire server-renders the component's initial state on a plain GET
   (visible as a `wire:id`/`wire:initial-data` blob in the HTML), so the
   first page's ~7 tender cards ARE reachable with a plain request — no
   JS execution needed to see them. However, Livewire's *pagination*
   (and its filter/sort controls) work via an AJAX protocol that POSTs a
   component snapshot + checksum to a `/livewire/update` endpoint, not
   via a plain URL parameter. **Verified empirically, not assumed:**
   `?page=2` and `?page=3` in the URL return byte-for-byte the same 7
   cards as `?page=1` — the query string is not wired to the Livewire
   component's pagination state at all for a fresh (non-JS) request.
   Implementing the full Livewire AJAX update protocol (CSRF token
   handling, snapshot/checksum round-trip) was judged out of scope for
   this actor's current version — the first page's live tenders are
   still genuine, current data, reported honestly as "what's listed on
   the site's first page" rather than silently claiming to be the whole
   archive.
2. **`/attribution`** ("Notification d'attribution") — a plain server-
   rendered HTML table (`table100`/`row100` classes), NOT a Livewire
   component — no pagination limitation observed here. Shows the current
   announcement week's awarded contracts (~9 rows at recon time, headed
   "Attributions du <date>"), each with the winning supplier's name and
   the awarded amount in Djibouti Francs. No historical week-picker or
   archive link was found anywhere on the site.

## Extraction

**`/marches` cards:** each tender's detail link is identified by its
`href` starting with `https://marchespublics.gouv.dj/marche/` (not by
CSS class alone — the site reuses the class `card__title` generically
for an unrelated filter-box header, which would otherwise produce a
false-positive "empty" record; caught and fixed during local testing
before this was ever pushed). Each card's description block repeats
`<div class="col-md-6"><strong>Label :</strong> value</div>` pairs (Code,
Administration Contractante, Nature, Modalite, Date de parution, Date
limite de remise des offres, Lieu d'execution, Procedure) — read
generically by label text rather than hardcoding field position, so a
reordering of these fields upstream doesn't silently swap values between
columns.

**`/attribution` rows:** the first `<td>` of each `tr.row100.body` packs
four labeled fields inline as `<b>Label :</b> value<br/>` with no wrapper
element per field — parsed by walking the cell's child nodes, tracking
the current label at each `<b>` tag and accumulating following text
until the next one. Supplier name and DJF amount are their own plain
`<td>` cells; the 4th cell's link becomes `detailUrl`.

Both parsers raise `UnexpectedShape` if their respective card/row
selector matches nothing at all — never silently returning an empty list
on a page that legitimately has content.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Reuses this session's "tenders
scraper" competitor scan (20 competitors — see `stvincent-tenders-scraper/
CRAWLING_METHOD.md`), plus a Djibouti-specific re-check
(`python api-search-actors.py --query "Djibouti tenders"`) that returned
zero hits. Confirmed first-mover, no competitor of any kind for this
country.

**Store category (Phase 5).** Primary: LEAD_GENERATION. Secondary:
BUSINESS. Same reasoning as this session's other tender actors.

**Pricing model (Phase 6).** Pay-per-event, single chargeable event
`apify-default-dataset-item` ("Result") — plain GETs, no auth/warmup
cost to justify a fixed per-run fee.

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source:
> `compranet-mexico-scraper` — see `stvincent-tenders-scraper/
> CRAWLING_METHOD.md`). Estimated operating cost: negligible — one GET
> per list type. This actor's `awards` records carry genuine monetary
> value (winning supplier + awarded amount in DJF), comparable in
> business value to CompraNet's own line items, while `current` records
> are thinner (no dates published upstream for most tenders — "N/A" as
> published, a genuine data-completeness limitation on the government's
> side, not this actor's). Recommended price: **$0.007 per result (FREE
> tier)**, stepping down to **$0.0066 (BRONZE) / $0.0063 (SILVER) /
> $0.0059 (GOLD)** — between the Saint Vincent/Kiribati/Fiji actors'
> $0.006 (thinner records) and Vanuatu/Samoa's $0.007-0.0075 (richer
> records), reflecting that awards carry real monetary figures but
> current-tender records and the small `current` page size pull the
> blended value down from the top of the session's range.

Margin check: positive at every tier given the negligible operating
cost. A full run of either list type costs under $0.10 at the FREE-tier
price given the small record counts (7-9) — low enough not to
discourage evaluation, though also a genuine characteristic of this
niche's size (a small country whose portal doesn't paginate past page 1
without JS), not a pricing mistake.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A current-tender or award record returned by the scraper."),
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
current`/`awards`, zero errors, zero missing titles/designations) and
remote (`apify call`, both `listType` values) both succeeded with real,
non-empty output; dataset schema declares nullable types for every
optional field from the start; no login/private data; Python +
`curl_cffi`/BeautifulSoup only, no browser automation (Livewire's full
AJAX pagination protocol was deliberately not implemented rather than
reached for a browser tool — the honest first-page scope was judged
preferable to either fabricating deeper pages or escalating to browser
automation for a small country's tender archive); Store category and
pricing are evidence-based per above, with Store publication itself as
the one named manual step.
