# Amazon Product & Search Scraper

Scrape Amazon search results by keyword or search URL — ASIN, title, price,
list price and discount, rating, **exact** review count, bestseller and
Amazon's Choice badges, units bought last month, and image.

Built for price-distribution analysis and competitor catalogue monitoring.

No login, no API key. HTTP-only — no browser.

## What you get

```json
{
  "position": 1,
  "page": 1,
  "asin": "B01LP0U5X0",
  "title": "Amazon Basics Extra Thick Exercise Yoga Mat with Carrying Strap",
  "price": 24.18,
  "currency": "$",
  "listPrice": null,
  "discountPercent": null,
  "rating": 4.6,
  "reviewCount": 70384,
  "boughtInPastMonth": 10000,
  "isSponsored": false,
  "isBestSeller": true,
  "isAmazonsChoice": false,
  "imageUrl": "https://m.media-amazon.com/images/I/...",
  "productUrl": "https://www.amazon.com/dp/B01LP0U5X0"
}
```

Field coverage on a typical 48-result page:

| Field | Coverage |
| --- | --- |
| asin, title, rating, reviewCount, imageUrl | 48/48 |
| boughtInPastMonth | 45/48 |
| price | 44/48 |

Prices are missing on multi-variant tiles that show "See options" instead of
a figure. That is a real state, not a parse failure, so it stays `null`.

**Review counts are exact.** The visible text on Amazon is abbreviated
(`70.3K`); this actor reads the aria-label instead and reports `70384`. A
test asserts large counts are not suspiciously round.

## Category URLs: read this first

A URL only works if it contains a **`k=` keyword**. Measured:

| URL form | Results |
| --- | --- |
| `/s?k=yoga+mat` | 48 |
| `/s?k=yoga+mat&rh=n%3A3407731` (category filter) | 24 |
| `/s?k=yoga+mat&s=price-asc-rank` (sorted) | 48 |
| `/s?k=yoga+mat&rh=p_36%3A1000-3000` (price filter) | 60 |
| **`/s?rh=n%3A3407731`** (node only) | **0** |
| **`/s?node=3407731`**, **`/b?node=…`** | **0** |

Amazon serves node-only category URLs as a *browse* layout with no search
results at all for logged-out clients. The actor rejects those up front with
an explanation telling you to add a keyword, rather than running and quietly
returning nothing.

So: any filter, sort or category refinement works — just keep a keyword in
the URL.

## Input

```json
{
  "searchTerms": [
    "yoga mat",
    "https://www.amazon.com/s?k=coffee+maker&s=price-asc-rank"
  ],
  "marketplace": "com",
  "maxPages": 3,
  "maxItemsPerTerm": 0,
  "includeSponsored": true
}
```

| Field | Description |
| --- | --- |
| `searchTerms` | Keywords, or Amazon search URLs containing `k=` |
| `marketplace` | com, co.uk, de, fr, it, es, ca, com.au, co.jp, in |
| `maxPages` | Up to 7 — Amazon stops offering a next page around there |
| `maxItemsPerTerm` | Hard cap per term; 0 for no cap |
| `includeSponsored` | Off keeps only organic results, for a cleaner price distribution |
| `delaySeconds` | Pacing — Amazon serves CAPTCHAs to traffic it dislikes |
| `proxyConfiguration` | Residential **strongly recommended** |

ASINs are de-duplicated across pages, so a product Amazon repeats on page 2
is not double-counted in your price statistics. `position` is the global
rank across pages; `positionOnPage` restarts each page.

## Two fields that need a proxy in the right country

**`isPrime` and `deliveryInfo` follow the exit IP, not the marketplace.**
From an Indonesian IP, amazon.com showed **zero** Prime badges across 48
results and rendered "Ships to Indonesia" with international delivery fees
instead. Nothing was broken — Amazon simply does not offer Prime to that
destination.

Every row carries `shipsTo` so you can tell. If it is not the marketplace's
own country, treat `isPrime: false` as *unknown*, not as *not Prime*, and
rerun with a residential proxy in that country.

**Prices are pinned to the marketplace currency** regardless of exit IP,
via the cookie Amazon honours for this. Without it an Indonesian exit
returns `IDR 336,939.57` for a $19.99 item, which would silently corrupt
price analysis. `currency` is on every row, so never assume USD.

## About `brandGuess`

Amazon's current search results contain **no brand element** — no brand
span, no `data-brand` attribute, no brand JSON. Verified across three
queries. The `a-size-base-plus` class that older scrapers read for brand is
the *title* element on today's markup.

So `brandGuess` is **derived from the leading words of the title**, and it
is named that way on purpose. It gets `Gaiam` and `BLACK+DECKER` right, and
it will get `Amazon` where the brand is really `Amazon Basics`. Use it for
rough grouping; do not treat it as authoritative. There is no field here
claiming to be a scraped brand, because there is no such data to scrape.

## Known limits

- **~7 pages per term.** Amazon stops serving a next-page link; the actor
  stops with it rather than burning requests on filler pages.
- **No brand**, for the reason above.
- **Prime and delivery are geo-dependent** — see above.
- Sponsored placements are auctioned per impression, so the sponsored subset
  of a page differs between runs. `isSponsored` reflects that impression.
- CAPTCHAs are reported as `CAPTCHA_ESCALATION` rows, never solved.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the fingerprint matrix, the
category-URL measurements and the parsing pitfalls.
