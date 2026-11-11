# mobile.de Car & Vehicle Scraper — Listings, Prices, Dealers

Seven mobile.de scrapers in one Actor. No login, no browser, no captcha —
plain HTTP against mobile.de's own JSON API.

mobile.de is Germany's largest vehicle marketplace: about **1.57 million cars**
online at any moment, plus motorbikes, motorhomes, trucks, trailers,
construction machinery and e-bikes. This Actor reads all of it, and it reads
the one field that makes the data worth more than a price list:
**mobile.de's own price rating** — whether a vehicle is cheap or expensive
against the market for its exact spec, the six price thresholds it was judged
against, and how far off the market it sits.

---

## What you can pull

| Mode | What it returns |
|---|---|
| **`search`** | Vehicle listings for a filter set or a pasted mobile.de search URL, with facet counts |
| **`detail`** | The full vehicle page: seller's own description, complete equipment list, all attributes, image gallery, KBA type key |
| **`dealer_inventory`** | Every vehicle one seller currently has online, plus their headline count |
| **`dealer_contact`** | A seller's legal imprint — company, street address, phone, email, Handelsregister and VAT numbers, named directors |
| **`similar_ads`** | mobile.de's own "similar vehicles" set for a listing |
| **`market_count`** | Result count only, one request per filter set — for sizing a market without pulling listings |
| **`reference_data`** | The make and model id tree and every filter's allowed values |

---

## Quick start

**All 2018+ diesel VW Golfs under €20,000 from dealers, newest first:**

```json
{
  "mode": "search",
  "vehicleCategory": "Car",
  "makeId": "25200",
  "modelId": "14",
  "priceMax": 20000,
  "firstRegistrationMin": 2018,
  "fuelType": "DIESEL",
  "sellerType": "dealer",
  "sortBy": "age",
  "sortDescending": true
}
```

**Don't know the ids?** Run `reference_data` once with your vehicle category.
Each model comes back with the exact filter value already built:

```json
{"label": "3er Reihe (Alle)", "isGroup": true,  "modelGroupId": "21", "ms": "3500;;21;"}
{"label": "116",              "isGroup": false, "modelId": "2",       "ms": "3500;2;;"}
```

**Or just paste URLs** — but read the warning under *Filters that don't work*
first, because mobile.de's browser URLs mostly don't carry filters.

---

## The three things worth knowing before you run it

### 1. Any single query tops out at ~2,000 listings

mobile.de will happily tell you a query has 1,574,052 matches. You can reach
**about 2,000 of them**. The result window is capped at item offset 1900 —
past that the API returns an empty list while still reporting
`hasNextPage: true`.

This is a server limit, not an Actor limit, and no amount of paging gets
around it. To harvest more than 2,000 vehicles, **slice the query and run the
slices**: by price band, registration year, single model, or postcode plus
radius. `search_summary.data.reachableTotal` tells you when a query is larger
than its own window, so you know to split it.

Every listing row carries the `offset` it came from, so slices stitch together
cleanly and de-duplicate on `id`.

### 2. Filters that don't work — silently

mobile.de accepts several URL styles and **ignores most of them without an
error**. Same HTTP 200, same full page of cars, just the wrong ones:

| URL you might paste | What mobile.de actually returns |
|---|---|
| `/fahrzeuge/search.html?makeModelVariant1.makeId=3500` | **1,574,052** — every car on the site |
| `/s/auto/bmw/` (what the browser shows) | **1,574,052** — every car on the site |
| `/fahrzeuge/search.html?vc=Car&ms=3500;;;` | 136,896 — BMWs, correct |
| `/auto/bmw-3er-reihe.html` | 27,157 — correct, but ignores any parameter you add |

So a URL copied out of the address bar usually carries **no filter at all**.

SEO landing pages have a second problem: they ignore the paging parameters
too, serving a fixed 24 rows where `ps=200` comes back 20/24 duplicate. The
Actor works around this by probing the URL once, reading back the filters
mobile.de says it applied, and replaying them as a canonical search — same
result set, and it pages properly. You'll see that in the run log as
*"does not honour mobile.de's paging parameters; replaying its filters as …"*.

This Actor catches it. mobile.de echoes back the filters it really applied,
and the Actor diffs that against what it sent — anything dropped is named in
the run log as a warning and listed in
`search_summary.data.droppedFilters`. **If that field is non-empty, your
results are broader than you asked for.** Using the structured filter fields
instead of a pasted URL avoids the problem entirely.

### 3. Model vs. series are two different fields

`modelId` is one model (`116`, `A4`, `Golf`). `modelGroupId` is a whole series
(BMW 3 Series, 1 Series). They are **not interchangeable** — mobile.de keeps
both in one number space but reads them from different slots, so a series id
put in `modelId` returns a *different model's* cars with no error:

```
modelId      = 20  →  2,250 cars, all BMW 525
modelGroupId = 20  → 17,102 cars, the BMW 1 Series
```

Give one or the other, never both. `reference_data` marks which is which and
hands you the ready-made value.

---

## Output

Every record shares one envelope, so a single dataset can hold listings,
detail, dealers, counts and diagnostics and still be joined on `id`:

```json
{
  "item_type": "listing",
  "id": "41691080604224",
  "data": {
    "title": "Volkswagen Golf VII Variant GTD BMT*Navi*BI-Xenon",
    "price": { "gross": "16.950 €", "grossAmount": 16950, "grossCurrency": "EUR" },
    "priceRating": {
      "rating": "REASONABLE_PRICE",
      "ratingLabel": "Fairer Preis",
      "thresholdLabels": ["11.400 €","14.800 €","16.000 €","17.800 €","19.100 €","21.200 €"],
      "vehiclePriceOffset": 52
    },
    "attr": {
      "loc": "Paderborn", "z": "33106", "fr": "02/2018", "ml": "126.871 km",
      "pw": "135 kW (184 PS)", "ft": "Diesel", "tr": "Schaltgetriebe",
      "c": "EstateCar", "emc": "Euro6", "pvo": "2"
    },
    "sellerId": 27941698,
    "type": "topAd",
    "numImages": 21
  },
  "metadata": {
    "scrapedAt": "2026-09-22T00:20:51Z",
    "mode": "search",
    "sourceUrl": "https://suchen.mobile.de/fahrzeuge/details.html?id=41691080604224",
    "rank": 1,
    "offset": 0
  }
}
```

mobile.de's fields are passed through close to verbatim — the site ships
changes without notice, and unlisted fields flow through rather than failing
the run.

**`data.type` is worth keeping.** mobile.de mixes paid placements into
organic results: `ad` is organic, while `topAd`, `eyecatcherAd` and `page1Ad`
are paid. In a typical page of 250 rows, roughly 34 are paid. If you are
computing market averages, filter on `type == "ad"`.

**Failures produce rows too.** A dead ad id emits
`{"item_type": "error", "data": {"_error": "not_found", ...}}` rather than
vanishing — a missing row looks like the Actor crashed, an error row tells you
the input was processed.

---

## Chaining modes

The modes are designed to feed each other:

1. `search` → every listing carries `data.sellerId`
2. those ids → `dealer_inventory` for each dealer's full stock
3. any of their ad ids → `dealer_contact` for the imprint (B2B lead lists)
4. any ad id → `detail` for the description text and full equipment list

---

## Performance and cost

`pageSize` defaults to **200**, which mobile.de honours. A full 2,000-listing
query therefore costs **10 HTTP requests**, not 100. The validation run in
this repo pulled 250 verified-unique listings in **3 requests**.

Paging uses mobile.de's item-offset parameter rather than its page number —
the page number strides a fixed 20 rows no matter what page size you ask for,
so page 2 at size 100 would re-deliver 80 rows you already had.

---

## Proxy

**Optional.** mobile.de gates on the TLS fingerprint, not the IP address —
this Actor's requests succeed from an ordinary unproxied address while a
plain Python HTTP client is refused from that same address.

A **residential proxy with country `DE`** is still the safer setting for long
runs, and makes prices, delivery options and regional availability match what
a German buyer sees. If a proxy is requested but cannot be set up, the run
continues directly and says so in the log.

---

## Limits and known behaviour

- **~2,000 listings per query.** Slice the query to go deeper.
- **`hasNextPage` is unreliable** — it stays `true` past the result window.
  The Actor stops on an empty page instead.
- **Unknown vehicle categories are not rejected by mobile.de** — it quietly
  searches cars instead. The Actor validates the 13 real categories locally
  and fails with a clear message.
- **No dealer-profile endpoint exists.** A dealer's imprint is only reachable
  through one of their ad ids, which is why `dealer_contact` takes ad ids.
- **`similar_ads` rows have their own schema** (price as `p`, plus `created`,
  `modified`, `hasDamage`, `images`) and are tagged `similar_listing`, not
  `listing`.
- **Two ad-id formats coexist** — 9-digit and 14-digit. Both are valid.
- **`accept-language` changes label text only**, not field names. `net`,
  `netAmount` and `vat` appear only on VAT-deductible listings.

---

## Blocking

mobile.de is behind Akamai Bot Manager. If it ever starts refusing this
Actor, the run log will say so explicitly and the dataset will carry a
`{"_error": "blocked"}` row. The Actor rotates through six browser TLS
profiles before giving up. The fix in that case is a newer `curl_cffi`
release, not a configuration change.

There is no captcha solving, no login and no session token in this Actor, by
design.

---

## Legal note

This Actor reads only publicly served, unauthenticated listing pages. The
imprint data returned by `dealer_contact` is published by sellers for
statutory disclosure (§5 DDG). Using it for unsolicited marketing is
separately regulated under the UWG — check your obligations before building
outreach on it, and respect mobile.de's Terms of Use for your jurisdiction.

Technical detail, the full recon record and every trap found while building
this are in [`CRAWLING_METHOD.md`](CRAWLING_METHOD.md).
