# Alfagift — how this actor gets its data

Recon date: **2026-09-21**. Everything below was measured against the live
site, not inferred.

---

## 1. There is no WAF

This is the first thing to establish, because it changes what the 401s mean.

| Probe | Result |
| --- | --- |
| `alfagift.id` via `curl_cffi` chrome124 / chrome131 / chrome99_android / safari17_0 / edge101 | **200** on all five |
| `alfagift.id` via `primp` firefox_135 | **200** |
| `webcommerce-gw.alfagift.id` via plain `httpx`, HTTP/1.1, no impersonation | reaches the same backend, same response body |
| Datacentre IP, no proxy | served normally |

No Cloudflare, no DataDome, no PerimeterX, no Akamai, no challenge page, no
`cf-mitigated` header, no geo-fence. The TLS profile is irrelevant here — the
ladder in `constants.py` exists only as rotation fodder for transport errors.

The site is a **Nuxt 2 SPA** (`data-n-head` in the shell, `window.__NUXT__`,
`/_nuxt/*.js`). The HTML is a 4.4 KB shell with no SSR content, so there is
nothing to scrape from the page itself — all data comes from the gateway at
`webcommerce-gw.alfagift.id`.

## 2. The real gate: an AES-encrypted `fingerprint` header

Every gateway endpoint answers this until the header is present:

```json
{"code":"401","message":"Unauthorized","trxId":"","token":"","errorFields":[]}
```

**The tell that this is not an auth gate:** `/v1/account/member/login` returns
the same 401. A login endpoint that requires you to be logged in is not an auth
gate — it is a client check.

A bogus path returns a different body (`{"status":404,"error":"Not Found"}`),
which confirms the 401 comes from a filter in front of real routes rather than
being the gateway's catch-all.

The CORS preflight publishes the whole contract:

```
access-control-allow-headers: devicetype, devicemodel, latitude, longitude,
                              trxid, fingerprint, authorization
```

The bundle's axios plugin fills five of those from nothing:

```js
t.headers.common.deviceType = "Web"
t.headers.common.deviceModel = <browser name>
t.headers.common.latitude  = 0
t.headers.common.longitude = 0
t.headers.common.trxId     = <uuid v4>
t.headers.common.fingerprint = l          // <- the one that matters
```

and `l` comes from FingerprintJS v3 put through an encryption helper:

```js
// module 233, and repeated verbatim in the app's injected env object
const passphrase = CryptoJS.enc.Utf8.parse("m4p1-W3bc0mm-4lf@giFt-3ncRyp-022")
const iv         = CryptoJS.enc.Utf8.parse("m4p1-4lf@giFt-1v")
encrypt = t => CryptoJS.enc.Base64.stringify(
    CryptoJS.AES.encrypt(t, passphrase, {iv, mode: CBC, padding: Pkcs7}).ciphertext)

// module 144
fingerprint = encrypt((await FingerprintJS.load().get()).visitorId)
```

So: **AES-256-CBC, PKCS7, Base64 of the ciphertext only** (CryptoJS's
`.ciphertext` has no OpenSSL `Salted__` prefix).

**The server only checks that the value decrypts.** It does not check that the
plaintext is a visitorId any browser produced, does not bind it to a session,
and does not expire it. `src/gate.py` therefore mints
`encrypt(secrets.token_hex(10))` once per run — no browser, no FingerprintJS,
no login, no captcha. Confirmed: a random 20-hex plaintext returned 200 on
every endpoint.

`authorization` is only ever populated for a logged-in member, and nothing this
actor reads needs it.

### If this ever stops working

A blanket 401 means the passphrase/IV rotated. Re-harvest:

```bash
curl -s https://alfagift.id/ | grep -o '/_nuxt/[a-f0-9]*\.js'   # entry chunks
curl -s https://alfagift.id/_nuxt/<hash>.js | grep -o 'passphrase:"[^"]*","iv":"[^"]*"'
```

Update `GATE_PASSPHRASE` / `GATE_IV` in `src/constants.py`. `AlfagiftGateRejected`
says exactly this in its message, and never burns retries on it.

## 3. The endpoint map

Harvested from the bundle's API-constants module, then each one probed. Only
the anonymous-readable ones are implemented.

| Endpoint | Mode | Notes |
| --- | --- | --- |
| `GET /v2/categories` | `categoryTree` | 61 nodes: 10 level-0 + 51 level-1 |
| `GET /v2/products/category/{id}` | `categoryProducts`, `fullCatalog` | takes level-0 or level-1 ids only |
| `GET /v2/products/searches` | `search` | Solr-backed; also returns SEO block + spelling suggestions |
| `GET /v2/products/suggestions` | `searchSuggestions` | 5 suggestions, no volume data published |
| `GET /v2/products/{id}` | `productDetail` | barcode, brand, gallery, HTML copy |
| `GET /v2/brands?alphabet=` | `brandDirectory` | ~2,400 brands across 21 working letters |
| `GET /v2/products/brand/{id}` | `brandProducts` | `storeId` accepted empty |
| `GET /v2/products/newproduct` | `newArrivals` | hard ceiling 198 |
| `GET /v2/products/recommendations` | `recommendations` | hard ceiling 48 |
| `GET /v1/cms/banner/{location}` | `promoBanners` | only `main_banner_new` is used by the site |
| `GET /v1/cms/banner/promotions/{id}` | `promoBanners` (opt-in) | campaign detail, keyed by **banner** id |
| `GET /v2/products/promotions/{id}` | `promoProducts` | keyed by **promotion** id — a different id |

**Closed** (still 401 with a valid fingerprint — these need a real member
bearer token and are deliberately out of scope): all `/v2/stores/*`, the cart,
checkout, order history, and every `/v1/account/member/*` route.

## 4. Pagination: `start` is a page index

The single most important detail. `start` is a **0-based page number**, not an
item offset.

```
start=0&limit=50  -> rows   0-49
start=1&limit=50  -> rows  50-99     (NOT rows 1-50)
```

Treating it as an offset re-fetches page 0 forever and yields a dataset that
looks plausible and is wrong. `test_local.py::live_paging` asserts against
exactly this by checking no productId repeats across pages.

**There is no page-size cap.** Measured on the 2,072-product "Makanan"
category:

| `limit` | rows returned | time |
| --- | --- | --- |
| 100 | 100 | 0.2s |
| 1000 | 1000 | 0.2s |
| 2000 | 2000 | 0.4s |
| 5000 | **2072 (all of them)** | 0.3s |

So the actor asks for one big page (default 1000) and only loops if the server
says there is more. Most targets are one request.

**Stop condition:** walking past the last page returns HTTP 200 with
`products: []` and `currentPage` reset to 0. There is no 404 and no `hasMore`.

## 5. Poisoned pages — the one that loses you a tenth of the catalogue

Some listings contain a record the gateway cannot serialise. Any page spanning
it returns HTTP 500 with a bare Spring body (no `message`), **deterministically**
— 15/15 attempts, across page sizes, after a 20s cooldown, while the
neighbouring "Makanan" category answered the identical request fine at the same
moment. It is not load and it is not rate limiting.

At recon time this was the whole **Lifestyle** top-level category (1,008
products). Asked for as one page: 500, zero rows. But paged at `limit=100`,
only page 0 failed and 866 rows came back.

So `_rescue_page` splits a failed page's item range into ten smaller ones
(1000 → 100 → 10) and keeps what survives. Measured end to end:

| approach | rows recovered from Lifestyle |
| --- | --- |
| one page of 1000 (naive) | **0** |
| with page rescue | **951 of 1008 (94%)** |

Two things fall out of this and are handled:

- **Alfagift's paging has slack.** A page asked for at `limit=100` routinely
  returns 95 rows, so ranges at two different page sizes overlap. Mixing page
  sizes therefore duplicates rows, and every walk de-duplicates on `productId`
  within a target (`_fresh`).
- **A rescued page 0 has no payload to read totals from**, so the summary row
  would claim the category is named `null` with 0 products. A one-row probe
  (`limit=1`) recovers the echo fields — that page is too small to span the
  poisoned record.

The summary row admits the loss rather than hiding it:

```json
{"_warning": "poisoned_pages_skipped", "unreadablePages": 1, "approxRowsLost": 10}
```

## 6. Decoys and traps

| Thing | What it looks like | What it is |
| --- | --- | --- |
| `sortDirection` | a sort parameter | **ignored**. `''`, `asc`, `desc`, `1`, `priceAsc`, `nameAsc` all return identical ordering |
| `latitude` / `longitude` headers | store-local pricing | **ignored** for anonymous callers. Jakarta, Medan and Jayapura return identical prices — one national list (seller `SAT`) until a member picks a store |
| A banner's `id` | the promotion id | **not the same id.** The promotion id is inside `bannerDeepLinkTap`; using the banner id returns a **zero-length HTTP 200** |
| Unknown category / brand id | a 404 | **hollow HTTP 200**: `totalData: 0` and a blank `currentCategoryId`. Indistinguishable from an empty category unless you check the echo field |
| `/v2/products/promotions` (no id) | a promo feed | 500 `For input string: "promotions"` — it collides with `/v2/products/{id}` |
| A SKU in `/v2/products/{sku}` | a product lookup | 500 `For input string` — only the numeric `productId` works |
| `sitemap_product.xml` | a product sitemap | the Nuxt catch-all returns the same 4.4 KB SPA shell. All child sitemaps are hollow |
| `sitemap-webcatalog.alfagift.id` | a catalogue host | DNS resolves, connection times out. Dead |
| Level-2/3 category ids on products | queryable categories | the tree only publishes levels 0-1; a level-2 id returns `totalData: 0` |
| `alphabet=` or `alphabet=#` | all brands | a truncated 300-row slab, not the full table |

## 7. Known upstream faults

- **Brand letters C, F, G, V, W** return HTTP 500 `solr.brands.error` on every
  attempt, from every address, with backoff. Alfagift's brand Solr core has bad
  data behind those prefixes. 21 of 26 letters work, ~2,409 brands total. The
  actor emits `upstream_index_broken` rows for them instead of burning retries.
- **Empty search keyword** returns 500 from `solr6-oneprice-*`, which is where
  the search backend's hostname leaks.

## 8. Rate limiting

None reached. 20 back-to-back requests completed in 1.3s, all 200. The web app
redirects to `/too-many-request` on 429, so a limit exists somewhere, but recon
never found it. The client still paces at 0.2s by default and treats a 429 as a
30s sit-still (rotating wouldn't help — a volume limit is not fingerprint
shaped).

## 9. Catalogue size

Sum of the ten level-0 categories: **~10,130 products** by their own counters.
A full uncapped run on 2026-09-21 pushed **10,081 records (10 category
summaries + 10,071 products) from 49 HTTP requests**, exit 0, no error rows.
The ~59-row gap is the Lifestyle poisoned page.

All 10,071 productIds were **distinct** — each product resolves to exactly one
top-level category, so the ten-category walk does not overlap. 4,926 were
buyable and 4,749 discounted.

| Category | Products |
| --- | --- |
| Makanan | 2,072 |
| Personal Care | 2,038 |
| Minuman | 1,171 |
| Kebutuhan Ibu & Anak | 1,082 |
| Lifestyle | 1,008 |
| Kebutuhan Rumah | 775 |
| Kebutuhan Dapur | 690 |
| Produk Segar & Beku | 681 |
| Kebutuhan Kesehatan | 486 |
| Pet Foods | 127 |

## 10. Public URL shapes

Rebuilt by `parsers.py` so every row links back, and accepted as input so a run
can be driven by pasted links:

```
/p/<slug>-<productId>        numeric id, trailing
/c/<slug>-<categoryId>       24-hex ObjectId, trailing
/b/<slug>-<brandId>          numeric id, trailing
/find/<keyword-with-dashes>  also /jual/<keyword>
/promotion-products?id=<promotionId>
```

The slug function mirrors the site's own: lowercase, spaces to hyphens, then
drop everything that is not a word character or a hyphen.
