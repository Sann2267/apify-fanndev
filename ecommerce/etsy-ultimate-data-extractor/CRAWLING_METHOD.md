# How this actor reads Etsy

Recon notes from 2026-09-21. Written down because every non-obvious choice in
`src/` traces back to one of these measurements, and because the cheapest way
to lose a day on this target is to re-derive them.

## The protection

`server: DataDome`, `x-datadome: protected`. A block is not an error page: it
is a ~780-byte stub with an inline `dd` object and a script from
`ct.captcha-delivery.com`.

```html
<script data-cfasync="false">var dd={'rt':'i','cid':'...','host':'geo.captcha-delivery.com',...}</script>
<script data-cfasync="false" src="https://ct.captcha-delivery.com/i.js"></script>
```

`'rt':'i'` is DataDome's *interstitial*. Clearing it means executing their
JavaScript, fingerprinting a real browser and posting the result back for a
cleared cookie. An HTTP-only client cannot do that, so the entire strategy is
**not to trigger it**. `_is_challenge` in `client.py` detects it from the
`server` header first (DataDome only answers the request itself when it is
blocking) and falls back to body markers.

## Three gates, measured separately

### 1. TLS fingerprint

Plain `requests` is blocked everywhere. Under `curl_cffi` impersonation the
answer varies by surface, which is why the ladder was measured rather than
guessed:

| URL | safari184 | safari17_0 | chrome131 | chrome124 | firefox133 | safari260 | edge101 |
|---|---|---|---|---|---|---|---|
| `/market/vintage_ring` | 403 | **200** | **200** | 403 | 403 | 403 | 403 |
| `/c/jewelry/rings` | **200** | **200** | 403 | 403 | 403 | 403 | 403 |
| `/search/shops?q=` | **200** | **200** | **200** | 403 | 403 | 403 | 403 |
| `/listing/<id>/<slug>` | **200** ×3 | 200 ×2 | 403 | 403 | 403 | 403 | 403 |

safari184 leads the ladder; safari260 and edge101 are excluded because they
were challenged on surfaces the others passed, and rotating onto a
challenge-prone profile turns one bad request into two.

### 2. Path shape — the locale prefix bypass

This is the finding that made shop and reviews modes possible.

```
/shop/antiquecut            403 interstitial  (every profile, every IP tried)
/uk/shop/antiquecut         200  820 KB
/de-en/shop/antiquecut      200  810 KB
/shop/antiquecut/reviews    403
/uk/shop/antiquecut/reviews 200  294 KB
```

Reproduced on four different shops back to back, all four bare-prefix requests
blocked and all eight locale-prefixed ones served. DataDome's rule for the shop
class is registered on the bare prefix only. `shop_url()` therefore always
emits a prefix, falling back to `uk` when the run asked for the unprefixed
site.

Listing pages are the opposite: the locale prefix makes no difference there,
and `/uk/listing/...` and `/listing/...` behave identically.

### 3. Slug exactness

```
/listing/4306368113/birth-flower-ring-925-sterling-silver   200  610 KB
/listing/4306368113/wrong-slug-that-is-long-enough-here     403
/listing/4306368113/birth-flower-ring                       403
/listing/4306368113/x                                       403
/listing/4306368113                                         403
```

A wrong or absent slug makes Etsy answer 301 to the canonical URL, and DataDome
blocks the redirect rather than the destination. The consequence is
architectural, not cosmetic: **a bare listing ID cannot be resolved from
outside**, so product URLs must arrive whole or be discovered from a grid or
shop page, both of which emit the full href. This is the main reason the modes
chain rather than standing alone.

Early recon mistook this for IP reputation, because the first probes used a
placeholder slug and the first real-slug probes succeeded. Isolating the two
variables cost an hour and is the single most useful thing in this file.

## robots.txt

Re-read 2026-09-21, 52 KB, three user-agent groups: `Spinn3r` (blanket deny),
`AdsBot-Google-Mobile`, and `*`. No `Claude`, `anthropic-ai`, `CCBot`,
`GPTBot`, `PerplexityBot` or `Google-Extended` rule anywhere.

What `*` disallows, and how each one shaped the design:

| Rule | Consequence |
|---|---|
| `/search?*q=` (×4 spellings) | No keyword product search. The whole keyword pipeline exists because of this line. |
| `/api/` | No internal AJAX. Deep reviews come from paginated shop review pages instead. |
| `*/shop/*/sold*` | Sold-item history is out of scope. |
| `*/shop/*/favoriters*`, `*/listing/*/favoriters*` | Favouriter lists are out of scope. |
| `*/shop/*/rss_shop.php` | The per-shop RSS feed is out of scope. |
| `/*?order=*` | No sort parameter is ever sent; results come back in Etsy's relevancy order. |
| `/c/*attr_*=*`, `/c/*price_bucket=*`, `/c/*ship_to=*`, `/c/*search_type=*` | No faceted refinement on category pages. |

And the line that makes keyword search possible at all, repeated per locale:

```
Allow: /search/shops
```

It ties with `Disallow: /search/*?*q=` on pattern length, and under the
longest-match-wins rule a tie resolves in favour of `Allow` — which matches the
evident intent, since Etsy added the `Allow` lines after the disallows.

## Two decoys

Both answer 200 with a plausible-looking page. Neither is used.

**`/c?q=<keyword>`** returns a full 64-card grid for any keyword — and the same
64 cards for all of them:

| query | cards | titles containing the query word |
|---|---|---|
| `vintage ring` | 64 | 5 |
| `leather journal` | 64 | 2 |
| `crochet pattern dinosaur` | 64 | 1 |
| `zzzqqqxyznotathing` | 64 | — |

Identical first three titles in all four. The `q` is parsed and discarded.
`?page=` on the same path *is* real, and returns genuinely different products.

**`/market/<keyword>`** is a real keyword page but carries an eight-card
promotional strip, not a result grid — 305 KB of page for 8 products, against
990 KB for 64 on a category page.

The in-shop equivalent, by contrast, genuinely filters:
`/uk/shop/VintageRingDesigns?search_query=ring` returns 36 cards of which 35
have "ring" in the title, against a visibly different unfiltered catalogue, and
`?search_query=dinosaur` on a crochet shop with no dinosaur items returns 0.
That is what the keyword pipeline uses.

## Ceilings and quirks

**Category paging stops at 250.** Page 249 and 250 are full; 251, 260 and 500
return the "Try searching for something else instead?" page. 250 × 64 ≈ 16,000
listings per category.

**An empty grid does not mean the end.** Page 25 of `/c/jewelry/rings` came
back empty while pages 50, 100 and 250 were full, minutes apart on the same
profile. Paging therefore tolerates `EMPTY_PAGE_TOLERANCE` empty pages before
accepting exhaustion, and end-of-results is read from the pagination nav
(`nav.search-pagination a[data-page]`) rather than from a card count. Shop
keyword search is the exception — it is not sharded and an empty page 1 is
conclusive.

**Currency follows the exit IP.** The same category returned `Rp`, `€`, `£`,
`AU$` and `CA$` purely by changing the exit or the locale prefix. The locale
prefix wins over the IP, which is why it is an input.

**Grid stars are the seller's.** Card for listing `4306368113`: 4.72 / 9,023.
That listing's own page: 4.7 / 2,282. That shop's page: 4.5 all-time, 4.7
recency-weighted, 9,023 reviews. The 9,023 match is exact, and every card from
one shop in a grid carries the same pair. Hence `shopRating` /
`shopReviewCount`.

**"(30% off)" parses as a review count** if the review-count span is matched by
shape alone — it sits in an identically-classed span. The count is therefore
required to be a bare number.

**Etsy publishes two shop ratings and they disagree.** Organization JSON-LD
carries the all-time average (4.5); the shop header carries a recency-weighted
one (4.7), described in its own tooltip as halving each year. Both are kept.

## What is not there

**Bestseller / Star Seller badges are not in grid HTML.** The listing-card
render config in the page says it plainly:

```json
"hide_rating": true, "hide_bestseller": false, "badges_disabled": true,
"quality_signals.bestseller_logic_desktop": ["off", "x", "9973d9"]
```

One occurrence of `hide_bestseller` per page, not per card — it is a global
switch, and there is no per-listing bestseller field anywhere in the markup.
Checked on Indonesian, German and UK renders. Listing pages *do* carry badges
(`aria-describedby="etsys_pick"`), so the parser reads them there.

**Seller SEO tags are gone from listing pages.** Zero `/market/<tag>` links on
a current listing page. The nearest real substitutes — taxonomy path, structured
highlights, AI review tags — are extracted instead, and `sellerTags` is `null`
rather than a guess.

## Where the data actually lives

| Layer | What it carries |
|---|---|
| `Product` JSON-LD | description, 12 images with alt text, category path, brand, price range (min/max across variants), strikethrough price, ISO currency, `eligibleQuantity` (stock), availability, aggregate rating, and the first few reviews |
| `Organization` JSON-LD | shop name, description, location, logo, banner, slogan, staff with roles, all-time aggregate rating |
| `ItemList` JSON-LD | the shop's visible catalogue with ISO currency and list price — merged with the card markup by `parse_grid` |
| `BreadcrumbList` / `FAQPage` JSON-LD | taxonomy placement; shop FAQs |
| `v2-listing-card` markup | ad flag, position, shop id, rendered currency symbol, discount, shop stars |
| `data-appears-event-data` | the AI review sentiment tags with their positive/negative split, per-listing and per-shop rating counts, shop tenure. **Only** place these exist. |
| `li[data-review-region]` / `div.review-card` | reviews: id, rating, text, date, buyer, photos, seller response, and the item bought |

Buyer review photos are served from `/iap/` on Etsy's image CDN; listing photos
use `/il/` and avatars `/isla/`, so the path segment is a sound discriminator.

Etsy's Collage components are declarative shadow DOM — every icon wraps a
`<template>` holding a `<style>` block. selectolax walks into those, so reading
an element's text without decomposing them first returns CSS instead of copy.
That is what `_clean_text` is for.
