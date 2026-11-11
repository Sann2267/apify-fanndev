# Crawling method — Amazon ASIN Lookup & Buy Box Monitor

Recon date: **2026-09-02**. Every figure below was measured live.

## A third TLS ladder on the same domain

This project now has three Amazon actors, and all three needed a *different*
fingerprint allowlist:

| Surface | Accepted profiles |
| --- | --- |
| Best Sellers (`/gp/bestsellers/`) | every profile tried |
| Search (`/s?k=`) | chrome131, chrome133a, chrome136, chrome150, **safari184** |
| **Product (`/dp/`)** | **chrome131, chrome133a, chrome150, chrome136** |

Measured on `/dp/` across 3 ASINs with repeated attempts:

| Profile | Result | Profile | Result |
| --- | --- | --- | --- |
| chrome131 | **3/3** | safari17_0 | 0/3 (flaky) |
| chrome133a | **3/3** | safari180 | 0/3 |
| chrome150 | **3/3** | chrome142 | 0/3 |
| chrome136 | 2/3 | chrome146 | 1/3 |

Note the inversion: **safari184 works on search but fails on `/dp/`, and
safari17_0 is the reverse.** There is no ordering heuristic and no ladder
that can be shared between surfaces — each one has to be measured. A test
asserts this list so it cannot be "tidied" into the sibling actors' ladder.

**The block signature is different too.** Search returns a 2,671-byte 503.
The product page returns an HTTP **200** of ~3,781 bytes reading *"Amazon.com
— Click the button below to continue shopping"*: a soft bot wall wearing a
success status. Status code alone cannot detect it, so any response under
250 KB is treated as blocked (a real product page is ~2.8 MB).

## The finding that shaped this actor: two page variants

Amazon serves logged-out visitors two versions of a product page:

| | Full | Reduced |
| --- | --- | --- |
| title, brand, rating, reviews, BSR, images, variations | served | served |
| price, Buy Box seller, ships-from, return policy | served | **absent** |

On the reduced variant the strings `Sold by`, `Ships from` and `In Stock`
appear **zero times** in 2.8 MB of HTML, and none of Amazon's canonical price
containers exist either. The two usually travel together but not always —
B07ZPKN6YR returned a price with no seller block.

### What actually controls it: the exit IP

The first read of this was wrong, and the correction matters.

From a single home IP, two "reduced" ASINs were refetched **6 times each
across 4 fingerprints** and came back reduced every time — which looked like
per-ASIN determinism. It is not. Running the same 12 ASINs through an Apify
**residential** proxy flipped the membership of the set:

| ASIN | home IP | residential IP |
| --- | --- | --- |
| B0BJLBD427 | reduced (6/6 attempts) | **full** — $37.99, Amazon.com |
| B01MQQ4RFA | full | **reduced** |

So the variant tracks the **requesting IP/session**, not the product. It is
stable *within* a session, which is exactly why repeated fetches from one IP
look deterministic and why retrying on the same connection never helps.

Price and seller are also *not* perfectly correlated, as an earlier reading
suggested: B07ZPKN6YR returned a price with no seller block.

Everything below was tested from a fixed session and **none of it helps**,
because none of it changes the exit IP:

| Attempt | Result |
| --- | --- |
| Warming `amazon.com` first, reusing session cookies | no better; measurably worse on one ASIN |
| `?th=1&psc=1` (force variant selection) | identical reduced page |
| `/gp/product/<ASIN>?th=1&psc=1` | identical |
| `/gp/offer-listing/<ASIN>` | 200, 2.9 MB — but it is the product page again, 0 offer blocks |
| `/gp/aod/ajax?asin=…` (3 param variants) | **404** |
| `/gp/product/ajax?…experienceId=aodAjaxMain` | **404** |
| Resolving parent → child ASIN and fetching the child | child was reduced too |

A parent/child hypothesis was tested and rejected: `twister` variation data
is present on **every** ASIN including the ones that render fully, so being
a variation parent is not what suppresses the Buy Box.

The all-offers (`aod`) endpoints returning 404 is why this actor reports the
**Buy Box offer only** — competing-seller lists and used/refurbished prices
are not reachable without a login.

### Rotating the session is the fix

Because the variant is per-session, a missing Buy Box is worth refetching on
a **new proxy exit IP**. Measured over the same 12 ASINs on Apify:

| Configuration | ASINs with Buy Box seller |
| --- | --- |
| Residential proxy, one session for the whole run | 5/10 |
| Residential proxy, `buyBoxRetries: 2` | **10/10** |

Only *one* ASIN actually consumed a retry. Once a session rotates onto a
"good" exit the rest of the run inherits it, so the cost of the feature is
roughly one extra request per run rather than one per ASIN.

`buyBoxRetries` therefore defaults to 2. A retry result is only accepted if
it carries *more* than the response it replaces, so a rotation can never
downgrade a good row, and recovered rows are tagged `_source:
S2-dp-page-retryN`.

### How the actor handles it

Every row carries `buyBoxDataAvailable`. False means *withheld*, not
*Amazon-sold*. Two guards follow from this:

- **Change detection ignores a disappearing seller.** `old && new && old != new`
  is required for `BUYBOX_SELLER_CHANGED`; otherwise ~40% of any portfolio
  would fire a false Buy Box alert on every run. Same for stock.
- **`inStock` will not trust a lone cart button.** The reduced page renders
  an add-to-cart button (it belongs to the variant picker) while serving no
  offer. Counting it asserted "in stock" for all 4 reduced ASINs, so the
  button is only trusted when the offer block was actually served.

## Price must come from a canonical container

The reduced page contains dozens of `a-offscreen` price spans — they belong
to *related products and other variants*. Taking the first one, the standard
approach, produced this on B0BJLBD427 (a ~$25 protein powder):

```
first 6 a-offscreen: ['$59.99', '$1.48', '$54.99', '$1.64', '$139.99', '$1.75']
                 ->  reported price: $2489.00   (and $102.95 on another render)
```

Two renders of the same product gave two different wrong prices, both
plausible enough to pass unnoticed into a repricing pipeline.

The actor therefore reads price only from canonical containers, in order:

1. `"priceAmount": 62.99` (JSON, most precise)
2. `id="corePrice_feature_div"` → its `a-offscreen`
3. `twister-plus-price-data-price value="…"`
4. `"displayPrice": "$62.99"`

On the reduced page **none of these exist**, so the price is `null`. A
regression test feeds the parser 150 unrelated `a-offscreen` spans and
asserts it returns no price.

## Two independent seller signals

| Signal | Coverage (8 ASINs) |
| --- | --- |
| hidden `<input name="merchantID">` | 4/8 |
| visible `id="sellerProfileTriggerId"` | 3/8 |

They do not always co-occur — the hidden input survives on pages where the
visible block does not render — so both are tried, hidden input first. A
bare `seller=<id>` link is used as a last resort; it was checked for false
positives and is safe: where it appears it matches `merchantID` exactly, and
on reduced pages it is absent entirely (0 occurrences), so it never invents
a Buy Box that was not served.
`ATVPDKIKX0DER` is Amazon's own retail merchant id, which is what makes
`buyBoxIsAmazon` a definite answer rather than a guess at the display text.

## Currency follows the egress IP unless you stop it

Inherited from the sibling actors and re-confirmed here: from an Indonesian
IP, `amazon.com` prices in IDR. `&currency=USD` and `lc-main` alone are
ignored; the **`i18n-prefs`** cookie is what works, so the client always
sends it set to the selected marketplace's currency.

## Other measured details

- Review counts are rendered parenthesised — `acrCustomerReviewText` gives
  `(10,765)`, so the parser strips the bracket. An earlier regex that missed
  this returned 0/8 coverage.
- Best Sellers Rank parses from `Best Sellers Rank … #288 in Health & Household`.
- Variation families are read from `dimensionValuesDisplayData` with a
  pair-scraping fallback, since the blob is large and sometimes truncated.
  Measured families of 7, 19 and 58 children.
- Blocked ASINs emit a `CAPTCHA_ESCALATION` row rather than vanishing.
  CAPTCHAs are never solved. From a home IP, 2 of 12 ASINs were blocked
  even after 6 attempts — residential proxy matters here.
