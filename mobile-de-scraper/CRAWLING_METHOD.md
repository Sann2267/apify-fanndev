# mobile.de — crawling method and recon record

Everything below was established against the live site on **2026-09-22** from
an unproxied Indonesian address. Commands are reproducible; every claim here
came from a response, not from documentation.

---

## 1. The gate: Akamai Bot Manager, and it is TLS-only

mobile.de fronts every host with Akamai (`server: AkamaiGHost`, `_abck` /
`ak_bmsc` / `bm_sz` cookies). The denial page is a custom 7.7 KB
"Zugriff verweigert / Access denied" document naming OS age, browser age,
extensions and Proxy/VPN as possible causes.

**The gate is the TLS fingerprint, and nothing else.** Against the exact same
URL, cold, with no cookies and no headers:

| Client | Result |
|---|---|
| `requests` / `httpx` | **403**, 7.7 KB denial page |
| `curl_cffi` chrome136 / chrome131 / chrome124 / edge101 / firefox133 / safari17_0 / chrome99_android | **200**, full JSON |

There is **no JS challenge to solve, no `_abck` sensor POST to replay, no
warm-up request, no cookie to carry and no token to harvest.** The app issues
itself an anonymous `vi` JWT and sends `x-mobile-vi`; the API does not check
it. Requests succeed with an empty header set.

This is why the actor has no `gate.py`. If it ever starts returning the denial
page, the fix is a newer `curl_cffi` profile — not a token hunt.

### The host split (the actual discovery)

The 403s are **host-scoped, not IP-scoped**. From the same address, same TLS
profile, same second:

```
https://www.mobile.de/consumer/api/search/srp?url=...     200   ← works
https://m.mobile.de/consumer/api/search/srp?url=...       403
https://suchen.mobile.de/...                              403
https://www.mobile.de/          (homepage)                403
https://www.mobile.de/robots.txt                          200
https://www.mobile.de/auto/                               200
```

The web app's own `window.__PUBLIC_CONFIG__` sets
`apiBaseUrl: "https://m.mobile.de/consumer/api"` — the host that is blocked
internationally. The identical service is mirrored on `www.mobile.de`, which
is not. **Using the www mirror is the entire reason this actor works without a
German proxy.** A scraper that copies the app's configured base URL gets 403
from everywhere outside Germany and concludes, wrongly, that the site needs
residential DE proxies.

---

## 2. Finding the API

`www.mobile.de/auto/` (200) is a Next.js RSC page; the SRP is a separate React
app whose shell carries `window.__INITIAL_STATE__` and
`window.__PUBLIC_CONFIG__` but **no listings** — they are fetched client-side.
The endpoint table came from the client bundles at
`static.classistatic.de/consumer-webapp/static/*.js`, by grepping for the
paths handed to the app's fetch wrapper:

```
search/srp?url=<path>                     search results + facets + metadata
search/srp/items?page=N&url=<path>        paginated items (see §4 — avoid)
search/vip?url=<path>                     full vehicle detail page
search/vip/ad-contact/{adId}              seller legal imprint
search/vip/similar-ads?similarAdsLink=    similar vehicles
search/srp/similar-ads / srx-ads          sponsored blocks
search/hit-count?<filters>                result count only
search/reference-data/filters/{category}  every filter's allowed values
search/reference-data/models/{makeId}     model tree for a make
home?url=/                                homepage counts and campaigns
```

Header contract, lifted from the same bundle (all optional in practice):
`content-type: application/json`, `accept-language`, `x-mobile-device-type`,
`x-mobile-vi`, `x-mobile-feature-variant`.

**The `url` parameter must be a root-relative path.** The API resolves it
against `suchen.mobile.de`. An absolute `https://www.mobile.de/...` value
returns `400 {"reason":"ApiRequestFailed","message":"SVC API request failed"}`.

---

## 3. Silent-wrong-data traps (the important part)

Every one of these returns **HTTP 200 with a full page of plausible cars**.
None produces an error. Together they are the reason a mobile.de scraper can
look healthy for months while returning the wrong dataset.

### Trap 1 — legacy filter parameters are accepted and ignored

```
/fahrzeuge/search.html?makeModelVariant1.makeId=3500   →  1,574,052 results
/fahrzeuge/search.html?vc=Car&ms=3500;;;               →    136,896 results
```

The first is the entire German car market wearing a BMW-shaped URL. The
legacy `makeModelVariant1.*`, `scopeId` and `isSearchRequest` parameters —
still used by older mobile.de scrapers and most blog posts — are dropped
silently. Only the short codes (`vc`, `ms`, `p`, `ml`, `fr`, …) are honoured.

The same applies to the pretty URL the browser shows: `/s/auto/bmw/` returns
**1,574,052** results, i.e. no filter at all.

**Detection:** the response echoes `sanitizedFilterParamsString` — the filters
it actually applied. `parsers.describe_dropped_filters()` diffs what was sent
against it and writes the difference to the run log and to
`search_summary.data.droppedFilters`.

### Trap 2 — the `ms` filter has two model slots that are not interchangeable

`ms` is `makeId;modelId;modelGroupId;variant`. A **series** ("3 Series (All)",
`isGroup: true`) belongs in the third slot; a **single model** ("116") in the
second. The ids share one number space, so the wrong slot still matches:

```
ms=3500;20;;    →  2,250 cars — every one a BMW 525
ms=3500;;20;    → 17,102 cars — the BMW 1 Series
```

Both are BMWs, both are 200, and nothing distinguishes them but the count.
Handled by `parsers.build_ms()`, which refuses to accept both slots at once,
and by `flatten_model_options()`, which emits the finished `ms` string per
reference entry so a caller never has to choose.

### Trap 3 — unknown vehicle categories fall back to Car

`vc=Van`, `vc=Truck`, `vc=Coach`, `vc=CaravanMobileHome` all return
**1,574,045** — the car count. They are not category names. The real enum has
13 members (`VanUpTo7500`, `TruckOver7500`, …) and is validated locally in
`parsers.vehicle_category_or_raise()`, because the server will not.

### Trap 4 — `models/{makeId}` returns two different shapes

```
BMW    [{optgroupLabel: "1er Reihe", items: [{value, label, isGroup}, ...]}, ...]
Audi   [{value, label}, ...]                       ← flat, no wrapper
```

A walker written for the grouped shape alone silently returns **zero** models
for Audi, Abarth, Aiways and most other makes. Both shapes are handled.

### Trap 5 — SEO landing pages ignore extra parameters, including the paging ones

`/auto/bmw-3er-reihe.html` filters correctly (27,157). Adding `?p=:20000`
changes nothing — still 27,157. SEO URLs are fixed filter sets. They also
silently add `dam=false` (damaged vehicles excluded), which a plain search
does not.

Worse, they ignore **`psz` and `ps` too**, so a pasted SEO URL cannot be
walked at all:

```
/auto/bmw-3er-reihe.html?psz=200&ps=0      got=24  dup=0
/auto/bmw-3er-reihe.html?psz=200&ps=200    got=24  dup=20   ← 4 new rows
/auto/bmw-3er-reihe.html?psz=200&ps=400    got=24  dup=20   ← 4 new rows
```

A pager would trickle ~4 new rows per request and never terminate cleanly.

**The fix** (`parsers.rebuild_canonical_path`): the API echoes the filters it
applied in canonical short-code form, so replay them against
`/fahrzeuge/search.html`.

```
probe  /auto/bmw-3er-reihe.html
   ->  dam=false&ms=3500;;21;&od=up&s=Car&sb=rel&vc=Car
replay /fahrzeuge/search.html?dam=false&ms=3500;;21;&od=up&s=Car&sb=rel&vc=Car
   ->  identical 27,160 total, and now pages at 204 rows/request with 0 dup
```

`run_search` does this automatically for any path that is not
`/fahrzeuge/search.html`, at a cost of one extra request and only for pasted
URLs. It is what makes "paste a mobile.de URL" actually work.

---

## 4. Pagination: `ps`, never `page`

`searchResults.items` claims `numPages: 50`, which is a display cap — page 100
still returns rows. The real behaviour:

| Approach | Result |
|---|---|
| `page=N` | strides a fixed **20 rows** regardless of `psz` — with `psz=100`, consecutive pages overlap **80%** |
| `ps=N` (item offset) + `psz` | true offset, **zero overlap** |

Measured with `psz=200`, `ps` stepping by 200, 10 requests:

```
ps=0     got=204  dup=0   cum=204
ps=200   got=204  dup=0   cum=408
...
ps=1800  got=204  dup=0   cum=2039
```

**Hard depth ceiling: `ps=1900` is the last offset that returns rows.**
Binary-searched — 1900 returns 104 rows, 1901 returns 0. So any single query
yields **~2,000 listings maximum**, regardless of the 1.5 M it reports.

`psz` is honoured up to at least 200 (the `+4..+6` extra rows are the
sponsored `topAd` / `page1Ads` / `eyecatcherAd` slots). At `psz=200` a full
query costs **10 requests for ~2,000 listings**.

**`hasNextPage` stays `true` past the ceiling**, so it is never the stop
condition. The actor stops on an empty-or-all-duplicate page.

To go beyond 2,000: slice the query (price band, registration year, single
model, postcode radius) and run the slices — not deeper paging.

---

## 5. Item list is not a list of listings

`searchResults.items` mixes five `type` values, one of which nests:

| type | meaning |
|---|---|
| `ad` | organic listing |
| `topAd` | paid top placement |
| `eyecatcherAd` | paid highlighted placement |
| `page1Ads` | **container** — its own `.items` holds more listings |
| `inlineAdvertising` | display slot, `{slotId, type}` only, no vehicle |

A naive `[i["id"] for i in items]` raises `KeyError` on `inlineAdvertising`
and drops every listing inside `page1Ads`. `parsers.flatten_items()` recurses
the container, skips the empty slots and preserves `type` so paid placements
stay identifiable downstream.

**And the paid slots repeat vehicles already present organically in the same
page.** A dealer with 37 vehicles returned **41 rows** — four of them the same
cars a second time, as `topAd` / `page1Ad`. De-duplication therefore has to
run *within* a page, not only across pages, which is what
`parsers.dedupe_listings()` does. Where a vehicle appears twice it keeps the
organic copy, because `type` is the only signal a consumer has for "was this
paid placement", and a market average computed over rows where the paid copy
won is biased toward whatever dealers are promoting.

After the fix the same dealer returns **37 rows, 37 unique — exactly matching
the `adCount: 37` mobile.de reports for that seller**, which is the cleanest
available correctness check on the whole pipeline.

Two ad-id number spaces coexist — 9-digit (`453388631`) and 14-digit
(`46708782974368`). Both are valid and both resolve on `search/vip`.

## 6. Other shape notes

* `price` is `{gross, grossAmount, grossCurrency}`, plus
  `{net, netAmount, vat}` only when the seller publishes VAT-deductible
  pricing. `accept-language` changes the label text, not the field names.
* `make` / `model` arrive sometimes as a string, sometimes as
  `{id, localized}`. Passed through as-is.
* `search/vip/similar-ads` returns **two different schemas**. With
  `formatSimilarAds=true` it is a trimmed card; without it the rows carry more
  (price as `p`, plus `created`, `modified`, `hasDamage`, `makeId`/`modelId`,
  `images`) and share only ~18 of 33 fields with a search listing. The actor
  sends the richer form and tags it `similar_listing`, not `listing`.
* `search/vip/ad-contact/{id}` returns the seller's imprint as one
  pre-formatted German text block — company, street, phone, fax, email, web,
  Handelsregister court and number, VAT id, named directors. Passed through
  verbatim rather than guessed apart. Some sellers return `markingText` too.
* There is **no dealer-profile endpoint**. A dealer is reached through
  `sid=<sellerId>` as an ordinary search filter, and their imprint only
  through one of their ad ids.

---

## 7. robots.txt

`www.mobile.de/robots.txt` disallows `/api/`, `/svc/similar/` and
`/consumer/next/api/search/count` for `*`, plus locale-prefixed paths and
`printView`. It does **not** blanket-disallow `/`, and does not disallow
`/consumer/api/` — the path this actor uses. `suchen.mobile.de` and
`m.mobile.de` are far more restrictive (`/consumer/api/`, `/svc/`,
`/fahrzeuge/search.html`), and those are exactly the hosts that answer 403
anyway.

The actor reads only publicly served, non-authenticated listing data and
sends no login. Operators running it at volume should keep the request delay
conservative and respect mobile.de's Terms of Use for their jurisdiction —
the imprint data in `dealer_contact` is published for statutory disclosure
under §5 DDG, and using it for unsolicited marketing is regulated separately
under UWG.

---

## 8. Quick reproduction

```bash
curl -s 'https://www.mobile.de/consumer/api/search/srp?url=%2Ffahrzeuge%2Fsearch.html%3Fvc%3DCar%26ms%3D3500%3B%3B21%3B%26psz%3D200%26ps%3D0' \
  -H 'accept-language: de' --tlsv1.2 | head -c 400
# plain curl will be refused — run it through curl_cffi:
python -c "
from curl_cffi import requests as cr
import urllib.parse as up
p='/fahrzeuge/search.html?vc=Car&ms=3500;;21;&psz=200&ps=0'
r=cr.get('https://www.mobile.de/consumer/api/search/srp?url='+up.quote(p,safe=''),impersonate='chrome124')
print(r.status_code, r.json()['searchResults']['numResultsTotal'])"
```
