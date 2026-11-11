# Crawling method — Amazon Sponsored Ads

Recon date: **2026-09-01**. Every figure below was measured live.

## Amazon search is a different target from Amazon Best Sellers

The sibling Best Sellers actor found *every* TLS profile returned 200.
Search is the opposite — it enforces a narrow fingerprint allowlist:

| Profile | `/s?k=` | Profile | `/s?k=` |
| --- | --- | --- | --- |
| chrome131 | **200** | chrome124 | 503 (4/4 attempts) |
| chrome133a | **200** | chrome123 / chrome120 / chrome119 | 503 |
| chrome136 | **200** | chrome142 / chrome145 / chrome146 | 503 |
| chrome150 | **200** | firefox135 / 144 / 147 | 503 |
| safari184 | **200** | safari180 / 260 / 2601, tor145 | 503 |

The failure is Amazon's *"Sorry! Something went wrong!"* page — a constant
**2,671-byte** body returned consistently, not intermittently, so it is a
fingerprint block rather than a throttle. chrome124 was retried four times
and failed identically every time.

Two things worth internalising:

1. **It is not "newest wins."** chrome142/145/146 fail while
   chrome131/133a/136/150 pass. There is no ordering heuristic — the ladder
   has to be measured.
2. **Do not copy the Best Sellers ladder here.** They share a domain and
   nothing else. The ladder in `constants.py` contains only the five
   verified-good profiles, and a test asserts that list so an "obvious
   tidy-up" cannot silently halve the success rate.

Because the block page is short, the client treats **any response under
200 KB as blocked** even when the status looks survivable, and rotates.

## Prices follow the egress IP unless you stop them

From an Indonesian IP, `amazon.com` returned `IDR 336,939.57` for a product
priced $19.99. Whatever proxy country a run exits from would otherwise
silently determine the currency, which would quietly corrupt any
price comparison across runs.

Tested fixes:

| Attempt | Result |
| --- | --- |
| default | IDR |
| `&currency=USD` query param | IDR (ignored) |
| `lc-main=en_US` cookie alone | IDR |
| **`i18n-prefs=USD` cookie** | **$19.99** |
| `i18n-prefs` + `lc-main` | $18.99 |

So the client always sends `i18n-prefs` set to the selected marketplace's
currency. Prices are comparable regardless of where the actor runs, and
`currency` is still emitted on every row so a consumer never has to assume.

## Detecting a Sponsored placement

A search result begins with:

```html
<div role="listitem" data-asin="B0H9LHWBDK" data-index="2"
     data-component-type="s-search-result" ...>
```

**`data-asin` precedes `data-component-type` in the same tag**, so splitting
on the component type alone decapitates the ASIN. During recon that mistake
produced blocks that bled into one another and reported *7* sponsored
results on a page that genuinely had 1. The item regex therefore anchors on
`role="listitem"` + `data-asin` + `data-component-type` in order.

The per-result label is `puis-sponsored-label-text`. Other sponsored-looking
strings on the page — `AdHolder`, `s-sponsored-label` inside the "Leave
feedback" widget — sit **outside** the result tiles and must not be counted;
tests assert they are ignored. Verified on a page with 48 results: every
`s-sponsored-label` occurrence that mattered was inside a result tile, and
no sponsored-brand carousel or video-ad component was present.

Field extraction uses `a-offscreen` for price — the canonical, fully
formatted value. Assembling `a-price-whole` + `a-price-fraction` picked up
neighbouring strike-through prices and produced nonsense like `354,682`.
Sponsored tiles also prefix their `aria-label` with `"Sponsored Ad - "`,
which is stripped so an ad row's title matches the same product's organic
title.

## Ad density is genuinely variable — hence sampling

Sponsored slots are auctioned per impression. Measured across seven keywords
in one session: **0%, 0%, 2.1%, 2.1%, 6.2%, 6.2%, 21.7%** — 17 of 252
page-one slots overall.

The variance is not just between keywords, it is between impressions of the
*same* keyword. In one three-sample run:

| Keyword | sample 1 | sample 2 | sample 3 |
| --- | --- | --- | --- |
| yoga mat | 13 ads | 1 ad | 13 ads |
| wireless earbuds | 1 | 0 | 1 |
| **protein powder** | **0** | **0** | **12** |

A single fetch of "protein powder" would have reported *no advertisers* on a
keyword with twelve. That is why `samplesPerKeyword` defaults to 3 and why
the summary ranks advertisers by how many samples they appeared in — an
ASIN present in every sample is bidding continuously, not winning one
auction.

It also means **zero sponsored results is a legitimate finding**, so a
summary row is emitted even when nothing was sponsored rather than leaving
a silent gap that reads like a failure.

Observed slot positions cluster the way Amazon lays ads out: 1–4, then
11–14, then 19–22 — which is what `slotBand` (TOP/MID/LOWER) encodes.

## Known limits

- **Page one only**, by design; that is where bidding competition is.
- Ad rendering may be sparser for anonymous or datacentre traffic than for a
  logged-in shopper, so figures are a lower bound on real ad density.
- No cost-per-click or spend data exists publicly — this measures *presence
  and position*, which is the observable proxy for bidding aggression, not
  actual bids.
- CAPTCHAs are reported as `CAPTCHA_ESCALATION`, never solved.
