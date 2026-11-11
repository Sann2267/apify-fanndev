# How this actor reads noon.com

Written for the engineer who maintains this actor. It records what was
measured, what was ruled out, and which 200 responses are lies.

---

## 1. The wall: www.noon.com is denied at the Akamai edge

Every Akamai-fronted noon host answers a 380-byte `Access Denied` page to
addresses outside noon's retail markets:

```
$ curl -s -o /dev/null -D- https://www.noon.com/robots.txt
HTTP/2 403
server: AkamaiGHost
server-timing: cdn-cache; desc=HIT, edge; dur=1, ak_p; ...
...
Reference #18.d94bd617.1790035055.2d4d4d92
```

Hosts confirmed denied: `www.noon.com`, `api.noon.com`, `catalog.noon.com`,
`mp-api.noon.com`, `minisite-api.noon.com`, `food.noon.com`, `ksa.noon.com`,
`uae.noon.com`, `now.noon.com`, `nowapi.noon.com`, `sam.noon.com`,
`sell.noon.com`, `cdn.noon.com`.

### Why this is NOT a fingerprint problem

Everything that would move a TLS or bot-score gate was tried and changed
nothing:

| Axis tested | Result |
| --- | --- |
| `curl_cffi` chrome124 / chrome131 / chrome136 / safari17_0 / edge101 / firefox133 | 403, all six, identical body |
| HTTP/2 vs HTTP/1.1 | 403 both |
| Full Chrome header set (sec-ch-ua, sec-fetch-*, UA, accept-language) vs no headers | 403 both, byte-identical |
| `/robots.txt` (a file no bot defence would gate) | 403 |

Two tells settle it. First, the deny covers `robots.txt` — a bot-management
rule that blocks the robots file would be a configuration error. Second,
`server-timing` reports `cdn-cache; desc=HIT`: the refusal is **cached at the
edge**, which a per-request bot score cannot be. This is an Akamai network-list
ACL keyed on the client network. No amount of fingerprint work opens it, so
none was spent. (See `.ai/lessons-learned.md`, "Escalating to a browser after
ONE TLS profile" — the ladder was run in full precisely so this conclusion is
evidence, not a guess.)

## 2. The door: minutes.noon.com is on Cloudflare, not Akamai

`minutes.noon.com` (noon Minutes, the 15-minute grocery arm) is served by
**Cloudflare** and is not part of that ACL:

```
https://minutes.noon.com/  -> 302 -> /uae-en/  (server: cloudflare)  200 OK
```

Its web app is TanStack Router with seroval SSR streaming. The streamed payload
leaks noon's own upstream request headers, including `"x-ipcountry":"id"` — noon
correctly identified the recon address as Indonesian **and served it anyway**.
That is the proof the deny is specific to the Akamai configuration rather than
to the client.

Downloading the 67 JS chunks from `z.nooncdn.com` (also reachable) and grepping
for path literals produced noon's internal API map. The decisive line is in
`getNoonProducts`:

```js
getNoonProducts: async t => {
  let n = l(t),
      r = `/_vs/nc/mp-customer-catalog-api/api/u${n.pathname}/?${n.searchParams}`;
  return await e.get(r, { ... })
}
```

`/_vs/nc/` is a server-side proxy prefix on the Minutes host that reaches the
**main marketplace catalogue service**. That is how this actor reads all of
noon.com without ever touching a denied host.

## 3. What is behind that door: no WAF at all

Measured, not assumed:

| Test | Result |
| --- | --- |
| Plain `requests`, zero custom headers | **200** |
| All 7 TLS profiles (incl. `chrome99_android`) | 200, byte-identical payloads |
| 30 concurrent requests, unproxied | **30/30 OK in 3.4 s (8.8 req/s)** |
| Proxy required? | **No** |

So the client carries no token harvest, no cookie warm-up and no signature. The
TLS ladder in `constants.py` exists only as insurance against a future edge
rule.

### The gateway is allowlisted, not open

Only one service routes through `/_vs/nc/`:

```
mp-customer-catalog-api  -> 200
mp-reviews-api           -> 404 (empty body)
mp-customer-reviews-api  -> 404
mp-identity-api          -> 404
mp-seller-api            -> 404
zzz-not-a-service        -> 404
```

This is why there is no review-text mode — see §5.

## 4. Decoys: 200 responses that mean nothing

Two traps here, both of which would have shipped fabricated data if the status
code had been trusted.

**(a) Any unknown path carrying `q=` falls through to search.**

```
/api/u/search/?q=ipho        -> 200  nbHits=1281  canonical_url=/search?q=ipho
/api/u/suggest/?q=ipho       -> 200  nbHits=1281  canonical_url=/search?q=ipho
/api/u/zzz-not-real/?q=ipho  -> 200  nbHits=1281  canonical_url=/search?q=ipho
/api/u/zzz-not-real/         -> 404  (honest)
```

`/suggest/` is not an autocomplete endpoint; it is the search handler wearing a
different URL. **noon exposes no keyword-suggestion surface through this
gateway**, so this actor ships no suggestions mode. The give-away is the
identical `canonical_url` — the server reports which query it actually ran, and
it is always the plain search.

Same trick catches `/api/u/review/<sku>/`: 200, 1.6 KB, breadcrumb "Review" — a
category slug catch-all, not reviews.

**(b) The brand filter that looks right is ignored.**

```
f[filter_attr_brand]=Apple -> nbHits 971, first page all Samsung, key dropped from canonical_url
brand=apple                -> nbHits 943, first page all Apple, echoed in search.brand
```

`filter_attr_brand` is the code the facet payload advertises, and it does
nothing. The working filter is the top-level `brand=<code>`. `constants.py`
pins the right one in `BRAND_PARAM`.

## 5. What is NOT available

* **Review text.** The PDP carries only the aggregate
  `product_rating: {"count": 32200, "value": 4.5}`. Individual review bodies
  live in a service the `/_vs/nc/` allowlist does not route. The aggregate is
  emitted; nothing is invented to fill the gap.
* **Keyword search volume / suggestions.** See §4(a).
* **Currency.** There is no currency field anywhere in any payload. Prices are
  bare numbers. The actor derives currency from the requested locale and stamps
  it on every priced row — the one field it adds that upstream does not send.

## 6. Endpoint map

Base: `https://minutes.noon.com/_vs/nc/mp-customer-catalog-api/api/u`

| Mode | Path | Notes |
| --- | --- | --- |
| search | `/search/?q=<kw>` | |
| category | `/<category/path>/` | path mirrors the site URL, minus the locale prefix |
| brand | `/brand/<code>/` | |
| product / offers | `/<anything>/<SKU>/p/` | **the slug is cosmetic** — see below |
| categoryTree | any listing, `category` facet | no navigation endpoint exists (`/api/u/navigation/` 404s) |
| facets | any listing, `limit=1` | |
| minutesSearch | `https://minutes.noon.com/_svc/catalog/search?q=` | different service and shape |

### The PDP slug is cosmetic

```
/api/u/iphone-17-pro-max-...-version/N70211544V/p/ -> 200, 113023 bytes
/api/u/totally-wrong-slug/N70211544V/p/            -> 200, 113023 bytes (identical)
/api/u/x/N70211544V/p/                             -> 200, 113023 bytes (identical)
/api/u/<real slug>/N00000000X/p/                   -> 404
```

Only the SKU is resolved. So callers can pass a bare SKU and the actor never
has to resolve a slug first — worth knowing, because the sibling Etsy actor in
this portfolio *does* require an exact slug and the assumption does not carry
over.

## 7. Pagination contract

| Parameter | Behaviour |
| --- | --- |
| `limit` | honoured to **200**, silently clamped above (`limit=500` returned 201 hits and echoed `limit: 200`). 200 is the default: 4x fewer requests than the site's own 50. |
| `page` | clamped to **50** server-side (`page=100` came back with `canonical_url` rewritten to `page=50`). |
| End of results | **200 with an empty `hits` array**, never a 404. |

**`nbHits` is not a total.** The same query answered 1309 / 1293 / 1323 / 1301
on four consecutive calls — it is an approximate, sharded counter. It is passed
through for reference and never used as a stop condition. The stop conditions
are: an empty page, an all-duplicate page, `maxPages`, or the item budget.

Cross-page duplication is normal and expected — measured at `limit=200`:

```
page 1 -> 200 products (200 new)
page 2 -> 200 products (183 new)
page 3 -> 200 products (185 new)
page 4 -> 200 products (184 new)
adjacent-page overlap: 0 / 0 / 0
```

No two adjacent pages overlap, but ~8% of each page repeats something from an
earlier page as the ranking shifts under a live index. The walker dedupes on
SKU, so 752 rows came back 752 unique.

## 8. Locale is the whole country switch

`x-locale` alone — no cookie, no session, no geo-IP dependency — switches
catalogue, currency and language:

| `x-locale` | nbHits (q=iphone) | first hit price |
| --- | --- | --- |
| en-ae | 1309 | 4899 (AED) |
| en-sa | 1028 | 5699 (SAR) |
| en-eg | 1273 | 58100 (EGP) |
| ar-ae | 1309 | 4899, Arabic title |

Seven countries answer distinctly: ae, sa, eg, kw, qa, bh, om.

## 9. noon Minutes has a different shape — and it moves

Minutes returns `hits: []` **even when it has hundreds of results**. The real
products are CMS modules under `results[].modules[]`, interleaved with ad
banners. During recon the module type was `instantPLPItem` (one product at
`data.product`); on the very next run the same query returned
`instantProductBox` (a `products` list).

That is why `parsers.extract_instant_products` does **not** key on the module
type — it reads both container shapes structurally and collects anything
carrying a `sku`. Keying on the type string is exactly what made this mode
return zero rows on its first test while the HTTP call succeeded.

Minutes also emits **every field twice**, in camelCase and snake_case
(`salePrice` and `sale_price`, `maxQty` and `max_qty`). Both are passed through
unchanged per the raw-passthrough rule; it roughly doubles row size.

## 10. Known behaviour that looks like a bug

**A nonsense query returns unrelated products, not zero results.** Searching
`zzqqxx-no-such-product-zzz` returns a full page of feng-shui ornaments. noon's
search falls back to fuzzy matching rather than reporting no hits, so an empty
result set is not how "nothing matched" is signalled. Consumers should not read
a non-empty response as confirmation that the keyword exists in the catalogue.

## 11. The exit IP decides which noon paths you get

Measured across two different networks. This is the single most important
operational fact about this actor.

| Path | Residential IP (recon, Indonesia) | Apify datacentre IP |
| --- | --- | --- |
| `www.noon.com/...` (Akamai) | **403** cached edge deny | reachable (Go 404 for an unmounted path, i.e. no deny) |
| `minutes.noon.com/_vs/nc/...` (marketplace catalogue) | **200** | **200** |
| `minutes.noon.com/uae-en/` (storefront HTML) | 200 | **403**, ~5.9 KB |
| `minutes.noon.com/_svc/catalog/...` (Minutes) | **200** | **403**, ~6.3 KB |

Two independent gates, pointing opposite ways:

* **Akamai** denies the recon residential address and does *not* deny Apify's
  datacentre address. So the wall in §1 is network-specific, not universal.
* **Cloudflare on `minutes.noon.com` is PATH-SCOPED**: from a datacentre
  address it serves `/_vs/nc/` (200, full data) while refusing the storefront
  and `/_svc/` on the *same host, same connection*. So a 403 on Minutes is not
  an outage and not a bad query — it is the exit IP.

Consequences, all of them verified by cloud runs:

* The **seven marketplace modes need no proxy** even from Apify. Verified:
  `search` 250 rows, `offers` 11 rows, `facets` 35 rows, all on datacentre IPs.
* **`minutesSearch` needs a residential proxy** when run from Apify. The client
  says exactly that in the error row rather than emitting an empty dataset.
* The origin fallback is disabled for `/_svc/` paths, because `www.noon.com`
  does not mount them — falling back there converted a clear 403 into a
  meaningless `404 page not found` and sent the first debugging pass in the
  wrong direction.

## 12. The S2 fallback is declared, not measured

`client.py` will try `https://www.noon.com` with the same prefix if the Minutes
gateway is refused before it has ever worked. **This path was never verified**,
because every request to that host from the recon address was denied at the
edge. It exists so that a run from an allowed network has somewhere to go if the
gateway prefix is retired. §11 shows Apify's datacentre address is NOT denied
by Akamai, so the fallback is plausible from the cloud — but it has still never
been exercised end to end, because the gateway has never failed there. Treat it
as untested.
