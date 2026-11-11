# Etsy Ultimate Data Extractor (All-in-One)

Five Etsy scrapers in one actor: product discovery, shop analytics, deep product
detail, reviews with sentiment, and a chained crawl that runs the lot from a
single keyword. One input schema, one dataset, one relational record shape.

No login, no API key, no browser. Every surface it reads is one Etsy's
`robots.txt` allows.

---

## Modes

| Mode | What it does | Records it emits |
|---|---|---|
| **search** | Products from category pages; shops and their keyword-matched products from keywords | `search_result`, `shop_result` |
| **shop** | Seller metrics plus the whole active catalogue | `shop_profile`, `search_result`, optionally `review` |
| **product** | One listing in full: description, variants, stock, taxonomy | `product_detail`, optionally `review` |
| **reviews** | Reviews, ratings, buyer photos, and Etsy's AI sentiment tags | `review`, `review_sentiment` |
| **deepCrawl** | search → every product it finds → that product's reviews, in one run | all of the above |

### Search

Two entry points, and they behave differently for a reason.

**A category URL** (`https://www.etsy.com/c/jewelry/rings`) walks the product
grid: 64 products per page, up to page 250 — about 16,000 listings per
category. Paste any `/c/...` URL from Etsy's own category navigation.

**A keyword** goes through shops. Etsy's `robots.txt` disallows `/search?q=`
product search for *every* crawler, so this actor does not request it. It uses
`/search/shops`, which Etsy explicitly allows with its own `Allow:` line, to
find the shops that match the keyword, then searches each of those shops'
catalogues for the same keyword. You get keyword-matched products plus the
sellers behind them. A nonsense keyword correctly returns nothing.

`shopsPerKeyword` controls how many matched shops get searched (default 12, one
full page of shop results). Shops and their products are interleaved, so a
small `maxItems` still returns products rather than a page of shops.

### Deep crawl

```
mode: deepCrawl
searchKeywords: ["vintage ring"]
deepCrawlProducts: 10
maxItems: 200
```

Finds the shops, pulls their keyword-matched listings, then opens the first 10
products in full and collects their reviews and sentiment tags. Half the item
budget is reserved for the discovery pass so the detail stage always has room.

---

## Output

Every record has the same envelope, so products, shops, reviews and diagnostics
can share one dataset and still be joined:

```json
{
  "item_type": "search_result",
  "id": "4306368113",
  "data": { "...": "depends on item_type" },
  "metadata": {
    "scrapedAt": "2026-09-21T09:14:03+00:00",
    "sourceUrl": "https://www.etsy.com/uk/c/jewelry/rings",
    "mode": "search",
    "keyword": "vintage ring",
    "rank": 5,
    "page": 1,
    "parentId": "PBJewelryGift",
    "locale": "uk"
  }
}
```

Join `metadata.parentId` to the `id` of the shop or product a row hangs off.
`metadata.rank` is the position across the whole target, continuing across
pages, so it survives pagination.

### A sample of each type

<details>
<summary><code>product_detail</code></summary>

```json
{
  "listingId": "4306368113",
  "title": "Birth Flower Ring 925 Sterling Silver ...",
  "description": "<the seller's full description, 2 KB of it>",
  "shopName": "PBJewelryGift",
  "shopTotalSales": 59500,
  "shopTenure": "9 years",
  "categoryPath": "Jewelry < Rings < Multi-Stone Rings",
  "breadcrumbs": [{ "name": "Jewelry", "url": "https://www.etsy.com/c/jewelry" }],
  "price": 27.58, "priceMin": 27.58, "priceMax": 34.81,
  "originalPrice": 39.39, "currency": "GBP",
  "availability": "InStock", "quantityAvailable": 431,
  "lowStockRemaining": null, "peopleWithItemInCart": null,
  "shipsFrom": "US",
  "rating": 4.7, "reviewCount": 2282,
  "images": [{ "url": "...", "thumbnail": "...", "alt": "May include: A delicate gold ring ..." }],
  "variations": [{ "name": "Primary colour", "options": ["Silver", "Gold", "Rose gold"] }],
  "highlights": ["Made by PBJewelryGift", "Materials: Sterling silver", "Adjustable"],
  "reviewFeatureTags": ["Looks great", "Love it", "Perfect gift", "Fast shipping"],
  "listingBadge": "etsys_pick"
}
```
</details>

<details>
<summary><code>review</code></summary>

```json
{
  "reviewId": "5185546518",
  "rating": 5,
  "text": "This ring is so pretty, high quality.",
  "date": "20 Sept, 2026",
  "buyerName": "Etsy buyer",
  "buyerProfileUrl": null,
  "photos": ["https://i.etsystatic.com/iap/.../iap_300x300....jpg"],
  "sellerResponse": null,
  "purchasedListingId": "4509331836",
  "purchasedListingTitle": "Sterling Silver Dangling Ball Ring ..."
}
```
</details>

<details>
<summary><code>shop_profile</code></summary>

```json
{
  "shopName": "PBJewelryGift",
  "location": "California, United States",
  "totalSales": 59504,
  "onEtsySince": 2017,
  "rating": 4.5, "ratingAllTime": 4.5, "ratingRecencyWeighted": 4.7,
  "reviewCount": 9023,
  "announcement": "Welcome to my little handmade jewelry studio ...",
  "members": [{ "name": "Gia Lur", "role": "owner, maker" }],
  "faqs": [{ "question": "What carrier do you use?", "answer": "We currently use USPS only." }]
}
```
</details>

---

## Things worth knowing before you run it

These are measured facts about Etsy, not caveats about the actor. They change
what you should ask it for.

### Grid stars describe the seller, not the item

A card in a category grid shows the **shop's** rating and review count. The card
for listing `4306368113` reports 4.72 and 9,023 — that listing's own page
reports 4.7 and **2,282**, and its shop reports exactly 9,023. Every card from
one shop in a grid carries the same pair.

The fields are therefore named `shopRating` and `shopReviewCount`, and
`minRating` / `minReviewCount` filter on them. For per-item ratings, run
`product` mode (or `deepCrawl`, which does it for you).

### `bestsellerOnly` returns almost nothing right now

Etsy does not render the Bestseller or Star Seller badge into server-side HTML
on grid pages at all. The page's own listing-card config reports
`badges_disabled: true` and the `quality_signals.bestseller_logic_desktop`
experiment is `off` — confirmed across several locales and exit countries.

The option is still here because it starts working the moment Etsy re-enables
the badge, and the parser does read badges where Etsy *does* emit them (listing
pages carry `etsys_pick`). But for popularity filtering today, use
`minReviewCount` and `minRating`. The actor logs a warning at startup if you
turn `bestsellerOnly` on.

### Seller SEO tags are gone

Etsy used to link a listing's seller tags at the bottom of its page as
`/market/<tag>` links. There is not one left on a current listing page.
`sellerTags` is always `null` rather than a guess. What you get instead, and
what most tag analysis was really after:

- `categoryPath` and `breadcrumbs` — Etsy's own taxonomy placement
- `highlights` — the structured attributes (materials, gemstone, made-to-order)
- `reviewFeatureTags` — Etsy's AI summary of what buyers say
- the full `title` and `description`

### Product URLs need their exact slug

`https://www.etsy.com/listing/4306368113/birth-flower-ring-925-sterling-silver`
works. `https://www.etsy.com/listing/4306368113` does not, and neither does any
wrong slug: Etsy answers those with a redirect to the canonical URL, and its bot
protection blocks the redirect rather than following it. A bare listing ID
cannot be resolved into a URL from outside.

This is why the modes chain. Grids and shop pages emit the full href, so
`search` → `product` works; typing an ID into `productUrls` does not, and the
actor tells you so in an `unresolvable_listing` row instead of failing quietly.

### Currency follows the exit IP unless you pin it

The same ring came back priced in IDR, EUR, GBP, AUD and CAD purely by changing
the proxy's exit country. Set `locale` to pin it: `uk` → GBP, `de-en` → EUR,
`au` → AUD, and so on. Leave it empty only if you are running through a US exit
and want USD.

`search_result` and `product_detail` carry both `currency` (the ISO code, from
Etsy's JSON-LD) and `currencySymbol` (as rendered).

### Use residential proxies

Etsy is behind DataDome. In testing, datacentre addresses were challenged on
every surface, including the category grid that residential addresses cleared.
Without any proxy, one address degrades after roughly 30 requests. The default
proxy configuration is `RESIDENTIAL`; the actor warns if you change it.

When a page is challenged the actor rotates TLS fingerprint and retries; a URL
that every fingerprint fails on produces a `challenge_wall` diagnostic row
rather than a silent gap.

### Ceilings

| Surface | Per page | Ceiling |
|---|---|---|
| Category grid | 64 products | page 250 (~16,000 per category) |
| Shop keyword search | 12 shops | until results run out |
| Shop catalogue | ~36–46 products | until results run out |
| Shop reviews | 14 reviews | until results run out |
| Listing page | 4 reviews inline | the rest come from the shop's reviews pages |

To go deeper than a category's 16,000, split it into its subcategories — each
gets its own 250 pages.

---

## Cost control

`maxItems` is one ceiling for the whole run, shared across every stage of a
chained crawl. The settings that actually drive request count:

- `maxPagesPerTarget` — pages per category, shop or keyword
- `shopsPerKeyword` — one request per shop searched
- `deepCrawlProducts` — one request per product opened in full
- `maxReviewPages` — one request per 14 reviews

A category page is about 1 MB, so a long run is bandwidth-heavy on residential
proxy. `requestDelaySecs` defaults to 2 and lowering it raises the block rate.

For scale: a verification run on the Apify platform — one category page, three
products opened in full, ten reviews, 28 records — took 110 s and 0.015 compute
units at 512 MB, peaking at 71 MB. The default memory is 512 MB for that reason;
raising it costs more without making anything faster.

---

## Compliance

`robots.txt` was re-read on 2026-09-21. It names no AI crawler (no `Claude`,
`anthropic-ai`, `CCBot` or `GPTBot` rule). This actor requests none of the paths
disallowed for `User-agent: *`:

- `/search?q=` product search, in any of its four disallowed spellings
- `/api/` — every internal AJAX endpoint, which is why deep reviews come from
  the shop's own paginated reviews pages instead
- `*/shop/*/sold*`, `*/shop/*/favoriters*`, `*/listing/*/favoriters*`
- `*/shop/*/rss_shop.php`
- `/*?order=*` — so results come back in Etsy's default relevancy order and no
  sort parameter is ever sent
- `/c/*attr_*=*`, `/c/*price_bucket=*`, `/c/*ship_to=*`, `/c/*search_type=*`

Only public pages are read. Nothing requires a login, and no personal data
beyond the reviewer display names Etsy itself publishes on a public page is
collected.

Two surfaces that look useful are deliberately unused because they are decoys:
`/c?q=<keyword>` answers 200 with a full grid that is byte-for-byte identical
for every keyword including nonsense ones (the `q` is parsed and discarded), and
`/market/<keyword>` carries only an eight-card promotional strip rather than a
result grid.

---

## Development

```bash
python test_local.py          # 70+ parser checks against saved pages, offline
python test_local.py --live   # plus a few real requests, one per mode
```

The fixtures in `tests/fixtures/` are real Etsy pages captured on 2026-09-21.
They are what keeps a markup change visible as a failing assertion instead of a
dataset full of nulls.

`CRAWLING_METHOD.md` documents how each gate was found and why each surface was
chosen.
