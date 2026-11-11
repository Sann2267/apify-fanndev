# Crawling method — Shopify storefronts

Recon date: **2026-09-15**, against a 20-store sample. Everything below was
measured, not assumed.

## 1. There is no WAF

Shopify's storefront JSON is public and unauthenticated. The TLS ladder came
back identical on the same IP against `allbirds.com/products.json`:

| Client | Result |
| --- | --- |
| `requests`, **default Python user-agent** | `200` |
| `requests` + browser UA | `200` |
| `curl_cffi` chrome99_android / chrome124 / chrome131 / chrome136 | `200` |
| `curl_cffi` safari17_0 / edge101 / firefox133 | `200` |

**Do not rotate TLS profiles here.** `chrome124` is pinned for portfolio
consistency only. A failure is a disabled endpoint, a dead domain, or a
store-level block — never a fingerprint.

## 2. The public surface

All paths are relative to a resolved store origin.

| Path | Gives |
| --- | --- |
| `/products.json?limit=250&page=N` | Catalogue: variants, prices, compare-at, SKU, options, images, tags |
| `/meta.json` | `id`, `name`, city/province/country, `currency`, `money_format`, `myshopify_domain`, `published_products_count`, `published_collections_count` |
| `/collections.json?limit=250&page=N` | Collections with `products_count` |
| `Shopify.theme = {...}` inline in the homepage HTML | Theme name, id, `theme_store_id`, `schema_version`, role |
| `powered-by` response header | `Shopify`, or `Shopify, Oxygen, Hydrogen` on a headless storefront |

`limit` is clamped to 250 (asking for 251 returns 250). Paging is `page=1..N`;
an empty `products` array, or a short page, means the end.

## 3. `/products.json` is strictly `published_at` DESCENDING

Measured across 5 stores and **7,443 products**, counting adjacent pairs where
`published_at[i] < published_at[i+1]`:

| Store | Catalogue | Out of order |
| --- | --- | --- |
| gymshark.com | 2,750 | **0** |
| ruggable.myshopify.com | 2,575 | **0** |
| colourpop.com | 1,006 | **0** |
| untuckit.com | 555 | **0** |
| drsquatch.com | 557 | **0** |

This contract is what makes `new-products` cheap: stop paging the moment an item
older than the cutoff appears, instead of crawling the whole catalogue. On a
10,000-product store that is ~1 request instead of ~40.

**`sort_by`, `order` and `since_id` are SILENTLY IGNORED** on `/products.json`.
All three return a plausible 200 with byte-identical results:

```
/products.json?limit=5                              -> same 5 products
/products.json?limit=5&sort_by=created-descending   -> same 5 products
/products.json?limit=5&order=created_at+desc        -> same 5 products
/products.json?limit=5&since_id=7369944137808       -> same 5 products
```

Never pass them; never trust them. (`/collections/all/products.json` has its own,
different ordering and ignores `sort_by` too — we do not use it.)

`published_at` and `created_at` are frequently years apart (created 2025-08,
published 2026-08). "Newly added" must mean **published**.

## 4. Resolving a store is the hard part

Four measured complications, all handled in `src/resolver.py`:

### 4a. www and apex are not interchangeable

| URL | Result |
| --- | --- |
| `gymshark.com/products.json` | `200` |
| `www.gymshark.com/products.json` | **`403`** |

Both homepages load fine — the divergence only shows on the JSON path. So every
candidate origin is tried in both apex and `www` form.

### 4b. Stores geo-redirect to a different storefront

`gymshark.com/` lands on `us.checkout.gymshark.com` from our exit IP — a
different storefront with its own catalogue and currency. The actor records
`requestedDomain`, `resolvedDomain` and `catalogueDomain` separately and adds a
note, so output is never quietly about a different shop. A plain apex↔www
redirect is *not* noted (that would be noise on almost every store).

### 4c. The `.myshopify.com` rescue

Stores that 404 `/products.json` on their custom domain often still serve it on
their canonical Shopify domain:

| Store | Custom domain | `.myshopify.com` |
| --- | --- | --- |
| ruggable.com | `404` | `ruggable.myshopify.com` → **2,575 products** |
| fashionnova.com | ok | `fnova.myshopify.com` |
| drsquatch.com | ok | `drsquatchsoapco.myshopify.com` |
| chubbiesshorts.com | ok | `chubbies.myshopify.com` |
| peakdesign.com | — | `pd-aqua.myshopify.com` |

The canonical domain comes from `/meta.json` when that responds, otherwise from
a regex over the homepage HTML. `/meta.json` is then retried **on** the canonical
domain, which is how headless stores get their `shop_name`/`currency`/`country`
(ruggable goes from `likely` + no identity to `confirmed` + full profile).

### 4d. Decoy 200s

A JSON path can answer 200 with an HTML page:

```
ruggable.com/cart.js                     -> 200  367,668 bytes  text/html
ruggable.com/search/suggest.json?q=a     -> 200  389,830 bytes  text/html
mvmt.com/products.json                   -> 200  1,239,377 bytes text/html
```

So `client.get_json` checks **content-type**, not status, and a candidate origin
only counts as working when `/products.json` returns a real `products` array.

## 5. Platform detection

| Signal | Meaning |
| --- | --- |
| `powered-by: Shopify` | Confirmed Shopify, classic Liquid storefront |
| `powered-by: Shopify, Oxygen, Hydrogen` | Confirmed Shopify, headless storefront |
| Body markers (`Shopify.theme`, `cdn.shopify.com`, `/cdn/shop/`, `ShopifyAnalytics`, `myshopify.com`) | Counted; > 0 ⇒ "likely" |
| `/meta.json` returns an object with `id` | Upgrades to "confirmed" |

Marker count is a useful confidence signal on its own: a real storefront scores
in the hundreds or thousands (kith 3,003; thesill 4,240) while a custom frontend
that merely proxies Shopify images scores 6 (bombas).

Theme: `schema_name` is the theme *family* (Dawn, Split, Horizon, GS2) and is the
value to report. Some merchants blank it on a heavily customised theme
(untuckit: `schema_name: null`, `name: "UTK | Production"`), so it falls back to
`name`. `theme_store_id` is non-null only for an unmodified Theme Store install —
most large brands show `null` even on a recognisable Dawn fork.

## 6. What is deliberately NOT built

A JSON-LD fallback for stores with no reachable catalogue. `bombas.com` (Vercel
frontend, no `.myshopify.com` in the page, every JSON path 404) does carry
`<script type="application/ld+json">` with `@type: Product` — but that block has
**no `offers` node**: name, brand, sku, images and material only. No price, no
variants, and its images come from Contentful rather than Shopify.

Emitting those rows would satisfy the record count while missing the two fields
the actor exists to deliver. Such stores get `_error: no_public_catalogue`
instead. In the 20-store sample this was 1 store.

## 7. Coverage measured

Of 20 domains (17 Shopify, 3 controls):

- **16** yielded a full catalogue — 11 direct, 5 via the `.myshopify.com` rescue.
- **1** (bombas) detected as Shopify but has no public catalogue.
- **3** (nike, apple, mvmt, nakedwines) correctly rejected as not Shopify.

`detect` mode skips the catalogue probe entirely: "is this Shopify, which theme"
is answerable without it, so a headless store with a private backend is a
successful detection rather than a failure — and the mode costs several
requests less per domain.

## 8. Rate limiting

None observed. ~40 sequential page reads plus hundreds of probe requests during
recon produced no 429 and no throttling. `maxConcurrency` defaults to 4 to stay a
polite client, not because Shopify pushes back.

Transport-level failures (DNS, TLS handshake) were the *only* recurring error and
are transient — the client retries 4 times with exponential backoff before
reporting `domain_unreachable`.

## 9. Proxy

Not required; the default input is `useApifyProxy: false` and every measurement
here ran direct. `_maybe_proxy_url` only builds a `ProxyConfiguration` when the
user explicitly asks — calling `Actor.create_proxy_configuration`
unconditionally makes the SDK demand a proxy password and kills runs that never
wanted a proxy.

A country-specific proxy is genuinely useful for one thing: pinning which
regional storefront a geo-redirecting brand serves (see 4b).

**A proxy does NOT rescue a store that rate-limits you.** Measured on
`bombas.com`, which loads fine from a residential ISP but answers Apify with
`429`:

| Exit | Result |
| --- | --- |
| Local home ISP | `200` (resolves to `no_public_catalogue`) |
| Apify datacenter, no proxy | `429` × 4 attempts → `domain_unreachable` |
| Apify **RESIDENTIAL** proxy, country-US | `429` × 4 attempts → `domain_unreachable` |

Residential made no difference, so the limit is not IP-reputation based. Do not
spend residential GB trying to force this class of store. Note the consequence
for interpreting output: a store can legitimately report `no_public_catalogue`
from one network and `domain_unreachable` from another — the error kinds
describe what *this run* observed, not a permanent property of the store.
