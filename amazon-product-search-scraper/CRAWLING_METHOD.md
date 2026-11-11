# Crawling method — Amazon Product & Search Scraper

Recon date: **2026-09-02**. Every figure below was measured live.

## Fingerprints: the search ladder, not the product ladder

This project now has four Amazon actors and each surface enforces its own
TLS allowlist:

| Surface | Accepted profiles |
| --- | --- |
| Best Sellers | every profile tried |
| **Search (`/s?k=`)** | **chrome131, chrome133a, chrome136, chrome150, safari184** |
| Product (`/dp/`) | chrome131, chrome133a, chrome150, chrome136 |

Note the trap: **safari184 clears search but is rejected on `/dp/`**, and
`safari17_0` is the reverse. chrome142/145/146 and every firefox profile
fail on search even though they are newer than ones that pass — there is no
"newest wins" heuristic. This actor reuses the sibling sponsored-ads
client and its five verified profiles, and a test asserts the list so it
cannot be "tidied" into the product-page ladder.

The search block is a **2,671-byte 503** ("Sorry! Something went wrong"),
versus the product page's 3,781-byte HTTP *200* soft wall. Because the block
body is short either way, any response under 200 KB is treated as blocked
regardless of status; a real SERP is ~1.7 MB.

## Category URLs need a keyword — measured

The brief asked for "keyword or category URL". Category URLs turn out to
work only in one shape:

| URL | `s-search-result` count |
| --- | --- |
| `/s?k=yoga+mat` | 48 |
| `/s?k=yoga+mat&i=sporting` | 24 |
| `/s?k=yoga+mat&rh=n%3A3407731` | 24 |
| `/s?k=yoga+mat&i=sporting&rh=n%3A3407731` | 24 |
| `/s?k=yoga+mat&rh=p_89%3AGaiam` (brand filter) | 48 |
| `/s?k=yoga+mat&rh=p_36%3A1000-3000` (price filter) | 60 |
| `/s?k=yoga+mat&s=review-rank` / `s=price-asc-rank` | 48 |
| `/s?rh=n%3A3407731` | **0** |
| `/s?i=sporting` | **0** |
| `/s?node=3407731`, `/b/?node=3407731` | **0** |

The node-only pages are not blocked — they return 200 at ~640 KB with zero
`data-asin` occurrences. Amazon renders them as a browse layout for
logged-out clients.

The rule is therefore simple: **`k=` present → results; `k=` absent → none.**
`normalise_target` enforces it and raises a message naming the fix, so a
node URL fails loudly at input validation instead of producing an empty run
that looks like a dead category.

## Pagination

| Page | Items | Next link |
| --- | --- | --- |
| 1 | 48 | yes |
| 2 | 48 | yes |
| 7 | 18 | **no** |
| 8 | 12 | no |
| 20 | 12 | no |

Pages past the end degrade to a short filler set rather than erroring, so
paging blindly wastes requests. `maxPages` caps at 7 and the loop stops as
soon as a page reports no next link.

Amazon repeats some ASINs across pages, so results are de-duplicated by ASIN
per search term — a verified 3-page run produced 144 items and 144 unique
ASINs. Without that, repeated products would skew any price distribution.

## Parsing pitfalls

**Item boundaries.** A result opens
`<div role="listitem" data-asin="…" … data-component-type="s-search-result">`
— `data-asin` comes *first*, so splitting on the component type decapitates
the ASIN and merges blocks. During the sibling actor's build that mistake
reported 7 sponsored results on a page with 1. The regex anchors on all
three attributes in order.

**Review counts are abbreviated in the visible text.** The page shows
`(70.3K)`; the exact figure is only in `aria-label="70,384 ratings"`. The
parser prefers the aria-label and falls back to expanding the abbreviation
(`10.5K` → `10500`) so the field is always an integer. A test asserts large
counts are not suspiciously round, which is what would happen if the
fallback silently took over.

**Price.** `a-offscreen` is the canonical formatted value; assembling
`a-price-whole` + `a-price-fraction` picks up neighbouring strike-through
prices. The list price is read from `a-text-price`, and `discountPercent` is
computed only when the list price is genuinely higher — never from a
same-or-lower "Typical" figure.

**`bought in past month`** appears on 45 of 48 results as `6K+`, expanded to
6000. It is a demand signal Amazon publishes for free on the SERP.

## There is no brand field

Checked across `yoga mat`, `laptop` and `coffee maker`:

| Signal | Hits |
| --- | --- |
| `data-brand` attribute | 0 |
| `"brand":` JSON | 0 |
| `s-line-clamp-1` (old brand row) | 0 |
| `a-size-base-plus` | present — but it is the **title** element |

Inspecting the markup directly confirms it: `class="a-size-base-plus
a-spacing-none a-color-base a-text-normal"` wraps
`BLACK+DECKER 12-Cup Drip Coffee Maker…` — the full title. Older scrapers
that read that class as "brand" are emitting titles.

Rather than ship a `brand` field that is really a title fragment, the actor
emits **`brandGuess`**, derived from the leading words of the title and
documented as a heuristic. It is right for `Gaiam` and `BLACK+DECKER`, wrong
for `Amazon Basics` (it yields `Amazon`). No field claims to be scraped
brand data, because none exists.

## Prime and delivery follow the exit IP

From the Indonesian development IP, a 48-result page returned **0** Prime
badges and rendered `Ships to Indonesia` with per-item international
delivery fees (`$16.61 delivery`). This is not a parsing gap — Amazon does
not offer Prime to that destination, so the badge is genuinely absent.

The actor therefore emits `shipsTo` on every row, and the README states that
`isPrime: false` from a mismatched country means *unknown*, not *not Prime*.
Verifying the positive case needs a residential proxy in the marketplace's
country, which the development environment could not reach.

**Currency is pinned** with the `i18n-prefs` cookie: without it the same IP
returns `IDR 336,939.57` for a $19.99 item. `&currency=` and `lc-main` alone
were previously measured to be ignored.
