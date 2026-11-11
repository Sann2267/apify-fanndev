# Crawling method — Blibli homepage recommendation feed

Recon date: **2026-09-01**. Every figure below was measured live.

## WAF profile

Identical Cloudflare setup to every other actor in this portfolio targeting
`www.blibli.com`, re-verified against these endpoints specifically:

| Client | Result |
| --- | --- |
| `httpx`, plain TLS | **403** |
| `curl_cffi` impersonation, **no** `Referer` | **403** |
| `curl_cffi` impersonation **+ `Referer`** | **200** |

No cookie, token or login. No session state was sent on any request in this
recon (no cookies at all) and the feed still returns real, populated
content — this actor deliberately stays anonymous/cookie-free, since that
is both the reproducible variant and the one that doesn't require solving
Blibli's own session-bootstrap flow.

## What was ruled out first (so the next agent doesn't re-walk this)

Before landing on the homepage feed, three other "event" candidates were
checked and rejected:

1. **Product Q&A / Tanya-Jawab does not exist on Blibli.** A product page's
   embedded SSR state (`window.__PRODUCT_DETAIL_INITIAL_STATE__`) and its
   feature-flag config (`sivaConfig/productConfig`, 46 flags) were dumped in
   full — no `qna`/`tanya`/`question`/`diskusi` key anywhere. Blibli offers
   seller live-chat (`allowedCommissionTypeToChat`, `chatPharmacist`)
   instead of an asynchronous public Q&A thread. Unlike Tokopedia/Shopee,
   there is nothing here to scrape.
2. **`/backend/content/promotions` (the campaign + voucher-code feed,
   `page`-paginated, 451 items, ~70% carrying real redeemable voucher codes
   with cashback/discount terms) is already fully covered.** It is
   `blibli-promo-extractor`'s `promoCampaigns` mode (`PROMOTIONS_API` in
   that actor's `constants.py`) — raw-passthrough already keeps the nested
   `vouchers`/`vouchersDetail` arrays. Building a new actor around it would
   have been near-total duplication of a sibling actor already in this
   portfolio. Caught by reading the sibling's source before committing to a
   target, not by chance.
3. **The per-tab personalized feed (`/backend/brs-api/seller-reco`,
   `/backend/search/homepage-recommendation`) needed session/customer
   context this actor doesn't have** (`pageTypeId` required, 400/405/500 on
   every anonymous probe) — abandoned after a few tries per this
   portfolio's Baxia-investigation discipline (`.ai/project/CONSTRAINTS.md`:
   don't sink unbounded time into a token/session wall). The
   `homepage-infinite-recommendations` endpoint below turned out to need no
   session at all, which is why it's the one this actor uses.

## Finding the endpoint

The product page is now a **Vite-built SPA** (this site was on Parcel-style
hashed bundles as recently as `blibli-promo-extractor`'s 2026-09-01 recon,
a few hours earlier the same day — bundler migration mid-flight). No
`<script src="...">` tags reference the JS chunks at all; they're attached
at runtime via `modulepreload` link injection from an inline bootstrap
script. The site-wide API map still exists, just relocated:

```
window._main_staticPublicPath() -> 'https://www.static-src.com/frontend/'
+ 'static/js/config.<hash>.js'   (hash rotates; found via the inline
                                   modulepreload-injection script, not a
                                   literal <link> tag)
```

That bundle (`config.D3atzmzY.js` at recon time) contains the full
`/backend/...` path map — 106 distinct paths — including the two endpoints
this actor uses.

## The endpoints

### 1. Tab discovery

`GET /backend/content-api/homepage-infinite-recommendations/tabs`

No parameters. Returns every content tab the homepage currently exposes —
observed 8 at recon time: `TAB_1` "Untukmu" (For You, `MANUAL`), `TAB_4`
"Zona affiliate" (`MANUAL`), and six `AUTOMATIC` category tabs ("Handuk",
"Hobi & Koleksi", "Handphone Lainnya", ...). This list itself changes over
time as Blibli adds seasonal/category tabs — the actor always re-fetches it
rather than hardcoding tab names, and `tabs` input is optional for exactly
this reason.

### 2. The feed — and its one decisive trap

`GET /backend/content-api/homepage-infinite-recommendations/{tab}/products?page=N`

**Must be built with the tab's short `name` (`TAB_1`), not its `id`.** The
tabs response gives both: `id` is a long UUID-shaped string that *looks*
like the real key, and `name` looks like an internal short code you'd
expect to be private. It's the opposite. Every path shape tried with `id`
in it 404s or 500s (`HOMEPAGE_INFINITE_RECOMMENDATION_TAB_NOT_FOUND` once
the URL shape itself was otherwise correct); `name` works immediately. This
is the same class of trap as the review endpoint's `merchantCode` in
`blibli-store-review-analyzer` — the field that looks internal/opaque is
the one the API actually wants.

## Three tile shapes share one feed — caught during Phase 3 local testing

The feed interleaves three unrelated content types in one list, and the
first two are easy to find; the third was missed by the initial
implementation and only surfaced once `test_local.py` printed a real
type-breakdown instead of just asserting "got records":

| Type | Discriminator | Carries |
| --- | --- | --- |
| `product` | has `sku` | `name`, `price`, `merchantCode`, `review`, ... — a normal product |
| `ad_banner` | has `promoBannerInfo.brandAdId` | `brandNames`, `redirectUrl`, campaign start/end — a paid placement, no product at all |
| `category_card` | neither of the above, but has `cardLabel`/`url` | e.g. `name: "Sepatu Sneakers Pria"`, `cardLabel: "Lagi laris"`, `cardDescription: "1,7 rb terjual bulan ini"` — a curated "trending now" collection tile linking to a landing page, not a single SKU |

First implementation classified anything without `sku`/`promoBannerInfo` as
`"unknown"` — technically honest (nothing was dropped or mis-shaped) but it
threw away a real, recurring tile type instead of describing it. A live run
against `TAB_1`+`TAB_5-4` surfaced 2 such rows immediately; `_recordType`
now has a dedicated `category_card` branch and `_cardLabel`/
`_cardDescription` are flattened out, and `test_local.py` asserts zero
`unknown` rows on a normal run so a fourth tile shape would be caught the
same way rather than silently swallowed by the catch-all.

## This is a re-ranked feed, not a fixed catalogue — `paging.total_page` is noise

The endpoint's own field name (`homepage-infinite-recommendations`) and its
payload (`extendedData.personalizationLogic: ";;DEFAULT_RERANK"`,
`extendedData.personalizationSource: "brs"`) both say the same thing: this
is a live-ranked recommendation feed, not an enumerable list with a stable
end. Measured on `TAB_4` across 7 consecutive page requests in one sweep:

```
page 1: total_page=2   page 2: total_page=2   page 3: total_page=2
page 4: total_page=1   page 5: total_page=2   page 6: total_page=2
page 7: total_page=1
```

`total_page` oscillates request to request against the *same* tab with no
other parameter changed — it is not trustworthy as a stop condition, and
some `AUTOMATIC` tabs omit the `paging` key from the envelope entirely.
Items themselves did **not** repeat across those 7 pages (each page's ids
were new), so this isn't the review-endpoint's "repeats past the end" trap
— but nothing here guarantees it can't happen on a different tab or a
longer sweep, so the walk still stops on "this page added zero new ids" as
a second, independent safety net on top of the hard `maxPagesPerTab` cap.
`AUTOMATIC` category tabs (backed by a real, finite catalogue under the
recommendation wrapper) *do* terminate cleanly on an empty page — confirmed
on `TAB_5-4`, empty at page 7 after 4 pages of full results and one partial.

The upstream `sequence` field on every item was observed to be `0` on every
single row, on every page, across every tab tested — not usable as a rank.
`_rankInFeed` is this actor's own running counter over the order items were
actually returned, computed rather than trusted from upstream.

## Known limits

- **No absolute "all recommendations" concept.** `maxPagesPerTab` (default
  15, ~20 items/page) is the real governor of run size for `MANUAL`
  (personalized) tabs — there is no server-side end to converge on, by
  design of what a recommendation feed is.
- **Anonymous ranking only.** No cookies are sent, so this is Blibli's
  default/no-session ranking, not any particular shopper's personalization.
  That is the reproducible, cacheable variant and the one worth scraping on
  a schedule; a logged-in user's own feed would differ and is out of scope
  (this portfolio does not do authenticated scraping).
- **Tab list drifts.** Seasonal/category tabs come and go; `tabs` input
  resolves against a fresh call to the tabs endpoint every run, and an
  unrecognised requested tab name is skipped with a warning (or fails the
  run loudly via `INVALID_INPUT` if *none* of the requested tabs matched).
