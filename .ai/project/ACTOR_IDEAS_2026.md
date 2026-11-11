# New actor ideas — high-ROI / low-competition (planning, 2026-06-06)

> Planning doc only — nothing built yet. Research basis: Apify Store survey
> + competitor density check (June 2026). The goal is to repeat what already
> works in this portfolio: **Alibaba RFQ** and **StockX orderbook / release
> calendar** win because they expose a *rare structured data-type* with
> buy-side value — not another generic "product scraper".

## The pattern that wins (use this as the filter)

A generic "`<Platform>` product scraper" is **saturated** — every major
marketplace already has 3–8 Apify actors (Amazon, Temu, Mercado Libre,
Wildberries, Ozon, Allegro, Coupang, IndiaMART, StubHub…). Don't build those.

Build the **one data-type within a platform that competitors skip** and that
someone makes money from:

1. **Order-book depth** — per-size/section bid–ask, spread, velocity (StockX ✓).
2. **Buy-side intent** — RFQ / buying-requests / tenders (Alibaba RFQ ✓).
3. **Sold comps with price bands** — p10–p90, sell-through, confidence.
4. **Forward-looking calendars** — releases, restocks, drops (StockX ✓).
5. **Live / time-sensitive streams** — live auctions, flash buy-leads.
6. **Cross-reference joins** — pop-report × sold-price, supplier × trust.

Two extra multipliers we already own:
- **Anti-bot moat reuse.** We already beat Aliyun/Baxia (Alibaba/AliExpress),
  Akamai (eBay), DataDome (Etsy), PerimeterX (Walmart). Pick targets behind the
  **same WAF families** — the hard part is already solved (see
  [CRAWLING_METHOD.md](CRAWLING_METHOD.md), `.agents/anti-bot/`).
- **Domain reuse.** Sneaker slugs/sizing (StockX), B2B supplier/MOQ parsing
  (Alibaba) transfer directly to adjacent platforms.

---

## Tier S — build first (rare data-type + reuses our moat)

### 1. GOAT order-book suite (search + product + offers)
- **Why ROI:** GOAT is the #2 sneaker platform. Pairing GOAT's per-size
  lowest-ask / highest-offer with our existing **StockX orderbook** unlocks
  the killer use case: **cross-platform sneaker arbitrage**. That's a data
  product resellers pay monthly for.
- **Why low competition:** existing GOAT actors only do flat product *search*
  (ecomscrape, moving_beacon). **Nobody exposes the bid/offer depth.**
- **Infra reuse:** StockX sneaker domain knowledge (slugs, sizes, brand
  taxonomy) transfers ~1:1. New actor template already exists.
- **Risk/WAF:** GOAT uses a signed mobile/JSON API behind Cloudflare —
  moderate. Our Cloudflare + signed-request playbooks cover it.

### 2. Made-in-China "Buying Requests" (RFQ) scraper
- **Why ROI:** direct analog of our rare **Alibaba RFQ** winner, on the #2
  Chinese B2B platform. Buy-leads = high-value sales-lead-gen data.
- **Why low competition:** every MIC actor scrapes *products*; **none scrape
  buying-requests / RFQ.** Same gap Alibaba RFQ exploited.
- **Infra reuse:** MIC sits behind **Aliyun WAF — the same family as
  Alibaba/AliExpress** we already beat. Biggest moat reuse on this list.
- **Risk/WAF:** Aliyun/Baxia — known territory, residential proxy.

### 3. Global Sources + Europages B2B supplier / RFQ
- **Why ROI:** B2B sourcing/lead-gen sells well (verified suppliers, MOQ,
  trade-show presence, contacts).
- **Why low competition:** Global Sources has **one thin actor** (piotrv1001);
  Europages (pan-EU B2B directory) is barely covered.
- **Infra reuse:** Alibaba/company-scraper supplier+trust parsing patterns.
- **Risk/WAF:** light — mostly SSR HTML.

---

## Tier A — strong, manageable competition

### 4. eBay Sold Comps (dedicated)
- **ROI:** proven, recurring demand — a **Terapeak alternative** at ~6× lower
  cost; reseller-grade price bands (p10–p90, sell-through, velocity, confidence).
- **Competition:** exists (harvestlab, khadinakbar) but it's a staple with
  steady users; differentiate on the *stats summary*, not raw rows.
- **Infra reuse:** **we already have working eBay actors** (Akamai bypass live
  as of 2026-06-06) — this is an extension, not a new build.

### 5. Whatnot live-auction scraper
- **ROI:** live commerce is exploding; sold prices + live-stream auction data
  for cards/sneakers/collectibles is time-sensitive and scarce.
- **Competition:** few actors (devcake, wisteria_banjo) — thin.
- **Infra reuse:** collectibles domain overlaps StockX/cards.

### 6. Graded-card market suite (TCGplayer + Cardmarket + PSA pop join)
- **ROI:** card investors pay for a clean **pop-count × sold-price (APR)**
  index; today it's fragmented across many thin single-source actors.
- **Competition:** several thin actors per source — the *join* is the moat.
- **Infra reuse:** sold-comps stats engine shared with eBay Sold Comps (#4).

---

## Tier B — deprioritize (saturated or weak moat)

Generic product scrapers for: **Temu** (Oxylabs/BrightData/Scrapeless + many
Apify), **Amazon**, **Mercado Libre / Wildberries / Ozon / Allegro / Coupang**,
**IndiaMART products**, **StubHub / SeatGeek event prices** (8+ actors),
**Chrono24 basic** (3), **Grailed** (3), **Faire / Ankorstore** (covered).
Only revisit with a clear data-type differentiator (e.g. a section-level
*ticket order-book* with price history vs. the existing flat price-range actors).

---

## Recon results (probed 2026-06-06 — see [recon/](../../recon/README.md))

Feasibility probing **overturned the original build order.** The B2B-sourcing
bet (Tier S #2 & #3) failed; the resale/market-data bets all passed.

| Idea | Verdict | Why |
|---|---|---|
| eBay Sold Comps | ✅ PROCEED | 240/240 sold rows via the **existing** eBay parser; Akamai cleared by warmup. ~90% reuse. |
| GOAT order-book | ✅ PROCEED | `__NEXT_DATA__` SSR + `api/v1` JSON; Cloudflare passive. Need a live slug/cnstrc key. |
| Card market (TCGplayer+PSA) | ✅ PROCEED (partial) | TCGplayer `mp-search-api`/`mpapi` **fully open** HTTP-only; PSA pop/APR render behind passive CF (`__next_f`). |
| Whatnot live | ✅ PROCEED | Public same-origin GraphQL `POST /services/graphql/`, no auth, passive CF. |
| Global Sources / Europages | ⚠️ DEFER | Imperva + AWS-WAF JS-VM challenges — needs headless/residential, not a plain primp actor. |
| **Made-in-China RFQ** | ❌ **DROP** | Buyer RFQs are **login-gated**; public `RFQ.html` is just product search. And it's **Cloudflare, not Aliyun** — the moat-reuse premise was wrong. |

## Revised build order (recon-validated, reuse-first)

1. ✅ **eBay Sold Comps** — BUILT & verified 2026-06-10 at
   `ebay/ebay-sold-comps-scraper/`. SOLD_LISTING rows + a COMPS_SUMMARY price
   band (min/p10/median/p90/max) per query. soldDate normalized; IDR/USD locale
   handled (US residential → USD).
2. ✅ **GOAT product + per-size availability** — BUILT & verified at
   `goat/goat-product-scraper/`. SSR identity island + `buy_bar_data` per-size
   `lowestPriceCents`/`lastSoldPriceCents`/`stockStatus` (34 sizes) — the
   orderbook "prize" IS reachable HTTP-only, no auth/signing.
3. ✅ **TCGplayer price + search** — BUILT & verified at
   `cards/tcgplayer-price-scraper/`. Open search + pricepoints APIs → CARD rows
   with marketPrice/lowestPrice + per-printing pricePoints. **PSA pop side +
   the pop×price JOIN actor still TODO.**
4. ✅ **Whatnot** — BUILT & verified (+deployed) at `whatnot/whatnot-live-scraper/`.
   NOTE: the livestream feed/search GraphQL is **auth-gated** (empty for anon),
   so the actor ships **public LISTING** data (SSR island) instead — title,
   price, seller, status, live-show linkage. Live-feed needs an account (future).
5. ~~Made-in-China RFQ~~ (dropped — login-gated) · Global Sources/Europages —
   only with a headless/residential stack later.

**Next up:** GOAT search + offers (suite completion), PSA pop scraper + the
cards-market-index JOIN, eBay sold-comps → cross-platform sneaker arbitrage join
with StockX.

## Open questions before committing
- GOAT: pull a current slug from SSR `__NEXT_DATA__`, then confirm the per-size
  availability/offer endpoint returns depth (recon got blocked on a stale slug).
- Whatnot: lift exact GraphQL `operationName` + query docs from the JS bundle.
- PSA: decide RSC `__next_f` parse vs residential for reliable pop counts.
- Pricing model: per-result (sold-comps, prices) vs per-event/lead.
