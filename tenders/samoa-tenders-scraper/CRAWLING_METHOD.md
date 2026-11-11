# Crawling Method — Samoa Ministry of Finance Tenders

**Last verified:** 2026-08-27

Samoa's public procurement is administered by the Ministry of Finance
(MOF), which publishes tender advertisements and contract award notices on
its own Webflow-built site, `www.mof.gov.ws`.

## Discovery — Webflow site, not the third-party e-tendering portal

MOF also runs a TenderLink-hosted e-tendering portal
(`portal.tenderlink.com/mof_samoa/`) — the same class of third-party SaaS
platform already flagged as a harder target in this session's Saint Lucia
recon (`stvincent-tenders-scraper/CRAWLING_METHOD.md`: client-side
rendering, CAPTCHA). MOF's own site pages (`/tender-adverisements`,
`/tender-awards`) were checked first instead and turned out to be fully
server-rendered Webflow CMS collections with everything needed inline — no
need to touch the harder third-party portal at all. (One `current`-tender
card does link out to the TenderLink portal login page as a "Portal Link"
contact field for a specific solicitation — passed through as plain text,
not followed.)

## Robots.txt

`https://www.mof.gov.ws/robots.txt` is a minimal, informally-written file —
not even valid `User-agent`/`Disallow` syntax, just a keyword comment line
("ministry finance samoa, samoa treasury, samoa finance") and a `Sitemap:`
pointer. No restriction of any kind, no Claude/AI-crawler mention.

## Site structure

Two Webflow CMS collection pages, each returned as one large, fully
server-rendered HTML response (no pagination, no API, no JS execution
needed to see the data):

1. **Current tenders** (`/tender-adverisements` — upstream's own spelling,
   kept verbatim since it's the real path) — ~101 cards at recon time,
   ~2.7MB response (Webflow duplicates a lot of inline SVG icon markup and
   a desktop/mobile-responsive field duplicate per card, which is what
   inflates the size, not the actual tender count). Each card:
   `div.collection-item-2.w-dyn-item[role=listitem]`.
2. **Contract awards** (`/tender-awards`) — ~40 cards at recon time,
   ~148KB response, a different Webflow collection (different CSS class
   namespace). Each card: `div.w-dyn-item[role=listitem]` with class
   *exactly* `["w-dyn-item"]` (the page's shared footer also renders
   `w-dyn-item` cards for an unrelated "press releases" widget and a
   "location-item" office-locations widget — filtered out by requiring the
   bare class list, since those two carry extra classes).

## Extraction

BeautifulSoup, with every `<svg>` decomposed first (Webflow inlines a full
icon `<path>` per field per card — noise for text extraction, and
expensive to grep through raw HTML by hand, which is how this recon itself
was slowed down before switching to BeautifulSoup mid-investigation).

**Current tenders:** title from `h1.heading-16` (required — its absence
raises `UnexpectedShape`). "Closing Date :" and "Agency:" are each a bare
`div.flex-block-4` with *exactly* two classes (`w-layout-hflex
flex-block-4`, no `.desktop`/`.doc`/mobile-duplicate class) — selected
positionally (1st = closing date, 2nd = agency) rather than by label text,
since the label text lives inside the div alongside the value with no
separate machine-readable field. Contact info is read only from the
`.desktop`-flagged blocks (`div.flex-block-4.desktop`) to avoid Webflow's
own mobile-responsive duplicate of the identical fields appearing later in
the same card — combined into one `contactText` blob rather than split
into separate name/email/phone fields, since a given tender can have 0-2
named contacts plus an optional portal link, and forcing that into fixed
columns would either drop data or fabricate empty ones. Documents:
every `a.link-4[href]` with non-empty link text and an href that isn't `#`
(Webflow renders unfilled CMS document slots as `w-dyn-bind-empty` links
with empty text and `href="#"` — filtered out), deduped by href since the
desktop/mobile duplicate sections repeat identical `<a>` tags.

**Contract awards:** a small helper (`_value_after_label`) finds the `div`
whose exact text matches a label ("Contract:", "Approval Dates:",
"Implementing Agency:", "Winning Bidder(s) and Contract Amounts:", "All
Bidders") and reads its next sibling `div`'s text as the value — label and
value are always adjacent siblings inside the same layout wrapper, so this
is robust to the exact CSS class names changing (which differ from the
current-tenders page's own class names, confirming the two pages are
different Webflow collections under the hood) as long as the label
wording itself doesn't change.

Both parsers raise `UnexpectedShape` if the expected card selector matches
zero cards, or if a required field (title / "Contract:") is missing on a
card that was found — never silently emitting an empty/corrupt record.

## Store market research, category & monetization (Phase 4-9)

**Competitive analysis (Phase 4).** Reuses this session's "tenders
scraper" competitor scan (20 competitors, all single-country national
procurement portals — see `stvincent-tenders-scraper/CRAWLING_METHOD.md`
for the full table). None targets Samoa or any Pacific-island nation.
Same first-mover conclusion as the Vanuatu actor built earlier this
session.

**Store category (Phase 5).** Primary: LEAD_GENERATION. Secondary:
BUSINESS. Same reasoning as the other two tender actors built this
session.

**Pricing model (Phase 6).** Pay-per-event, single chargeable event
`apify-default-dataset-item` ("Result") — no separate `apify-actor-start`
charge, for the same reason as the other two: plain GETs, no auth/warmup
cost to justify a fixed per-run fee.

**Price calculation (Phase 7).**
> Competitor range: $0.0068-$0.008 per result (source:
> `compranet-mexico-scraper`, the only competitor with retrievable tiered
> pricing — see `stvincent-tenders-scraper/CRAWLING_METHOD.md`). Estimated
> operating cost: still sub-cent per result, though `current` mode's
> single ~2.7MB response is meaningfully heavier bandwidth than the other
> two tender actors built this session (Vanuatu, Saint Vincent) at a few
> hundred KB each. This actor's records are the richest of the three —
> direct multi-document links (not just one PDF) plus, in `awards` mode,
> full competing-bidder lists most competitors don't expose at all.
> Recommended price: **$0.0075 per result (FREE tier)**, stepping down to
> **$0.0071 (BRONZE) / $0.0067 (SILVER) / $0.0063 (GOLD)** — priced at the
> top of the observed competitor band given the extra document/bidder
> data density, without exceeding it (CompraNet's $0.008 remains the
> highest verified comparable).

Margin check: positive at every tier — the heavier bandwidth per `current`
run is still a fraction of a cent in compute/proxy cost against a
$0.0063-$0.0075 per-record price. A full 101-record `current` run costs
$0.76 at the FREE-tier price, low enough not to discourage first-time
evaluation.

**Monetization configuration (Phase 8) -- automated via `apify api`.** The
installed Apify CLI (`apify-cli/1.7.1`) has no dedicated monetization/
pricing/category subcommand, but it does expose `apify api`, which makes
an authenticated request to the Apify API using the CLI's own stored
credentials -- no need to extract the raw token from the OS keyring at
all. Used `apify api PUT actors/{actorId}` to set:
- **Categories:** `["LEAD_GENERATION", "BUSINESS"]`.
- **Pricing:** Pay-per-event, event `apify-default-dataset-item`
  ("Result" / "A current-tender or contract-award record returned by the scraper."),
  tiered at FREE $0.0075 / BRONZE $0.0071 / SILVER
  $0.0067 / GOLD $0.0063 (PLATINUM/DIAMOND matched to
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
current`/`awards`, full-page smoke test: 101 + 40 records, zero errors)
and remote (`apify call`, both `listType` values) both succeeded with
real, non-empty output on the first cloud attempt (nullable field types
applied proactively in `output_schema.json` from the start, per the
lesson from this session's earlier Saint Vincent actor); no login/private
data; Python + `curl_cffi`/BeautifulSoup only, no browser automation;
Store category and pricing are evidence-based per above, with Store
publication itself as the one named manual step.

## Rejected candidate (same recon pass)

- **Solomon Islands** (`solomons.gov.sb/portal_tender/`) — the general
  `solomons.gov.sb` WordPress site itself has a clean robots.txt, but the
  `/portal_tender/` path specifically sits behind a Sucuri CloudProxy
  JavaScript challenge (`sucuri_cloudproxy_js` obfuscated redirect page,
  HTTP 307 with no usable `Location` header). Tried the full TLS-profile
  ladder (`curl_cffi` chrome124/chrome99_android/safari17_0/edge101/
  chrome131/safari18_0 plus `primp`) on the same IP per this project's
  "one profile failing is a data point, not a verdict" principle — every
  profile hit the same JS challenge, confirming it's a genuine
  JS-execution wall, not a TLS-fingerprint issue. Left unbuilt rather than
  escalating to a browser tool, per this project's HTTP-only constraint.
