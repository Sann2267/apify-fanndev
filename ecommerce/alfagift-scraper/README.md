# Alfagift (Alfamart) Product, Price & Promo Scraper

Twelve Alfagift scrapers in one. No login, no browser, no captcha, no proxy
required.

[Alfagift](https://alfagift.id/) is the online store of **Alfamart**, Indonesia's
largest minimarket chain (~20,000 stores). This actor reads its public
catalogue through the same internal API the website itself uses: roughly
**10,000 products** with live prices, discounts, stock flags and full category
paths, plus the brand directory and every promotional campaign currently
running.

A full-catalogue run takes **49 HTTP requests and about three minutes** for
10,081 records.

---

## What you can pull

| Mode | What it gives you | Needs input? |
| --- | --- | --- |
| `search` | Products for a keyword, plus Alfagift's own SEO copy and spelling suggestions | keywords |
| `searchSuggestions` | Autocomplete suggestions for a seed keyword | keywords |
| `categoryTree` | The whole navigable category tree (61 nodes) | — |
| `categoryProducts` | Every product in one or more categories | category ids or URLs |
| `fullCatalog` | The entire catalogue, ~10,000 products in ten requests | — |
| `productDetail` | Full product page: **barcode**, brand, image gallery, HTML description, discount end date | product ids or URLs |
| `brandDirectory` | The A–Z brand directory (~2,400 brands) | — |
| `brandProducts` | Every product carried under a brand | brand ids or URLs |
| `newArrivals` | The newest-products feed (198 items) | — |
| `recommendations` | The homepage recommendation rail (48 items) | — |
| `promoBanners` | Live promotional campaigns with artwork and run dates | — |
| `promoProducts` | The products inside each live campaign, at promo prices | — |

Every mode accepts **pasted alfagift.id URLs** as well as raw ids, so you can
drive a run straight from links in a browser.

## Quick start

Cheapest useful run — what Alfamart is promoting right now and at what price:

```json
{ "mode": "promoProducts" }
```

Price-track a keyword:

```json
{ "mode": "search", "searchKeywords": ["indomie", "susu uht", "kopi kapal api"] }
```

The whole catalogue:

```json
{ "mode": "fullCatalog" }
```

Enrich specific products with barcodes and brands:

```json
{
  "mode": "productDetail",
  "productIds": ["13585", "https://alfagift.id/p/indomie-mi-instan-goreng-84-g-754971"]
}
```

## Output

Every record shares one envelope, so a single dataset can hold products,
categories, brands and campaigns and still be joined on `id`:

```json
{
  "item_type": "product",
  "id": "845475",
  "data": {
    "productId": "845475",
    "productName": "Soulyu Stain Lip Tint 03 Courage 4 ml",
    "sku": "A8454750002167",
    "plu": "461719",
    "basePrice": 59000.0,
    "finalPrice": 29900.0,
    "discountPercent": 49.32203389830509,
    "stock": 0,
    "validFlag": false,
    "categoryNameLvl0": "Personal Care",
    "categoryNameLvl1": "Riasan Wajah & Tubuh",
    "categoryNameLvl2": "Liquid Lip",
    "productUrl": "https://alfagift.id/p/soulyu-stain-lip-tint-03-courage-4-ml-845475",
    "isBuyable": false,
    "isDiscounted": true,
    "discountAmount": 29100.0
  },
  "metadata": {
    "scrapedAt": "2026-09-21T14:05:13+00:00",
    "sourceUrl": "https://alfagift.id/promotion-products?id=6aacea5b144aa661216a3007",
    "mode": "promoProducts",
    "rank": 2,
    "parentId": "6aacea5b144aa661216a3007"
  }
}
```

Alfagift's own fields are passed through verbatim. Four are added:
`productUrl`, `isBuyable`, `isDiscounted` and `discountAmount`.

### Read `isBuyable` before you average anything

Alfagift leaves **delisted and out-of-area products in every listing**, with
`validFlag: false` and every price field set to `0.0`. An average price computed
over a raw category is dragged toward zero by rows that are not for sale at all.
`isBuyable` makes that one filter instead of a convention you have to know. The
row above is a real example: a live 49%-off promo item that is nonetheless
flagged unbuyable and out of stock.

## Things worth knowing

**Prices are national.** Alfagift publishes one price list (seller `SAT`) to
anonymous callers. The API accepts `latitude`/`longitude` headers but ignores
them — Jakarta, Medan and Jayapura return identical prices. Store-local pricing
needs a logged-in member with a chosen store, which this actor does not do.

**Some brand letters are broken upstream.** Letters **C, F, G, V and W** return
HTTP 500 from Alfagift's own brand index on every attempt, from every address.
21 of 26 letters work (~2,400 brands). The run reports those letters as
diagnostic rows rather than silently missing brands — it is Alfagift's index,
not the scraper.

**Some category pages are unreadable, and the actor works around it.** A few
listings contain a record Alfagift's gateway cannot serialise, so any page
spanning it returns HTTP 500 forever. At the time of writing that was the whole
1,008-product *Lifestyle* category, which returns **nothing** to a normal
request. This actor re-reads a failed page in smaller slices and recovered
**951 of the 1,008** products, with the summary row stating how many it could
not reach:

```json
{ "_warning": "poisoned_pages_skipped", "unreadablePages": 1, "approxRowsLost": 10 }
```

**Roughly half the catalogue is not actually for sale.** The 2026-09-21 full
run returned 10,071 products, of which **4,926 were buyable** and 4,749 carried
a discount. That ratio is why `isBuyable` exists.

**`fullCatalog` returned no duplicates.** Each product resolves to a single
top-level category, so the ten-category walk did not overlap once across 10,071
rows. De-duplicating on `data.productId` is still a cheap safeguard if Alfagift
ever starts cross-listing.

**Product ids are numeric — a SKU will not work.** `/v2/products/A13170001210`
returns HTTP 500. Use the numeric `productId` from a listing row, or paste the
`/p/` URL and let the actor extract it. The run says so explicitly rather than
failing quietly.

**Feed ceilings are the server's, not the actor's.** `newArrivals` stops at 198
rows and `recommendations` at 48, whatever limit you ask for.

**What this actor cannot reach.** Store locations, stock by store, carts,
orders and member data all require a real member login and stay closed. This is
a public-data actor by design.

## How it gets in

Alfagift has **no WAF** — no Cloudflare, no DataDome, no TLS fingerprint gate,
no IP or geo restriction. Plain HTTP/1.1 from a datacentre address works.

What it has is a custom `fingerprint` request header that the site's own
JavaScript builds by AES-encrypting a FingerprintJS visitor id. Without it every
endpoint returns `401 Unauthorized` — including the login endpoint itself, which
is the giveaway that it is a client check rather than authentication. The actor
reproduces the encryption in Python, so no browser is needed.

The full reverse-engineering write-up, the endpoint map, and every decoy and
trap measured are in **[CRAWLING_METHOD.md](CRAWLING_METHOD.md)**.

## Input reference

| Field | Default | Notes |
| --- | --- | --- |
| `mode` | `search` | See the table above |
| `searchKeywords` | — | Keywords or `/find/` URLs |
| `categoryIds` | — | 24-char ids or `/c/` URLs |
| `productIds` | — | Numeric ids or `/p/` URLs |
| `brandIds` | — | Numeric ids or `/b/` URLs |
| `promotionIds` | — | Optional; empty discovers every live campaign |
| `brandLetters` | A–Z | Restrict the brand sweep |
| `targets` | — | Generic list, routed to whatever the mode needs |
| `maxItems` | `0` (unlimited) | Hard cap on dataset rows |
| `pageSize` | `1000` | Alfagift enforces no cap; most targets fit in one request |
| `maxPagesPerTarget` | `50` | Safety ceiling |
| `bannerLocation` | `main_banner_new` | The only location the live site uses |
| `includePromoDetail` | `false` | One extra request per banner |
| `requestDelaySecs` | `0.2` | Raise if a long walk ever sees HTTP 429 |
| `proxyConfiguration` | off | Optional — only buys rate-limit headroom |

## Local development

```bash
cd alfagift-scraper
../.venv/Scripts/python.exe test_local.py          # all 63 checks, live
../.venv/Scripts/python.exe test_local.py search   # one mode

echo '{"mode":"categoryTree"}' > storage/key_value_stores/default/INPUT.json
../.venv/Scripts/python.exe -m src
```

`test_local.py` covers the AES gate against a fixed vector, URL/id resolution,
the derived fields, the dataset schema (including the `id: null` diagnostic row
that Apify validates batch-wide), the page-index paging regression, and every
mode against the live site.

## Legal

Reads only data Alfagift serves publicly to any visitor. No login, no account,
no personal data, no checkout or cart interaction. `robots.txt` is
`User-agent: * / Allow: /`.
