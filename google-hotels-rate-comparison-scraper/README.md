# Google Hotels Rate Comparison Scraper

Find out what **every booking site** charges for the same hotel room-night. For each hotel you
get 17–25 quotes side by side — Booking.com, Agoda, Expedia, Trip.com, Klook, the hotel's own
site and more — with the price, whether taxes are included, whether cancellation is free, and
the direct booking link for each one.

## Why use this actor

- **Rate parity in one row.** The cheapest quote, the dearest quote and the spread between
  them are calculated for you, so you can see instantly which site is undercutting the others.
- **Every booking site at once**, instead of running one scraper per travel site.
- **Google's own price verdict** — "GREAT PRICE", or "18% less than usual" — alongside the
  rating, review count, star class and amenities.
- **Direct booking links** for each quote, so a price can be verified or handed to a customer.
- **No account, no login and no API key.** Nothing to manage and no browsers to run.
- **Automatic retries** and clear failure records: if a hotel can't be read, you get a row
  saying so rather than a silently missing hotel.

## How it works

1. You give the actor a destination query (`hotels in Singapore`) or the IDs of hotels you
   already care about.
2. The actor reads Google's public hotel pages and collects each hotel's details plus every
   booking-site quote shown for it.
3. Results stream into your dataset — ready to download as JSON, CSV or Excel, or to load
   straight into a database.

Run it on a schedule and you have a daily rate-parity feed for your own hotels or your
competitors'.

## Modes

| Mode | What it does | Requests |
| --- | --- | --- |
| `search` | Find hotels for a query and return their cards (price, rating, star class, deal flag) | 1 per query, ~21 hotels |
| `hotel` | Full detail for specific hotels, with all booking-site quotes nested under `rates` | 1 per hotel |
| `rates` | The same quotes flattened to one record each — the shape you want for analysis | 1 per hotel |
| `sponsored` | The paid placements on a hotel's page (quotes for *other* hotels) | 1 per hotel |
| `reference` | Check the source is live and report what it returns, including your currency | 1 |

## Input

```json
{
  "mode": "hotel",
  "hotelIds": [
    "ChUI17vV0u_fprYCGgkvbS8wZGQ5MDMQAQ",
    "https://www.google.com/travel/hotels/entity/ChcIyo2FjenOuZ8xGgsvZy8xdGYyMTV2aBAB"
  ],
  "languageCode": "en",
  "countryCode": "us",
  "maxItems": 200,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `search` (default), `hotel`, `rates`, `sponsored` or `reference`. |
| `searchQuery` | string | A destination or hotel name, e.g. `hotels in Singapore`. |
| `searchQueries` | array | Several queries in one run, one request each. |
| `fetchRates` | boolean | In `search` mode, also pull every hotel's full quote table. Costs one extra request per hotel. Default `false`. |
| `hotelId` | string | A hotel ID, or the `google.com/travel/hotels/entity/<id>` URL it came from. |
| `hotelIds` | array | Several hotels in one run. |
| `languageCode` | string | Language of labels such as "Free cancellation". Default `en`. |
| `countryCode` | string | Influences which booking sites are listed. Default `us`. |
| `maxItems` | integer | Maximum records per run. Default 200. |
| `maxConcurrency` | integer | Hotels fetched in parallel. Default 3. |
| `proxyConfiguration` | object | Residential proxy, on by default. **The proxy country also decides the currency** — see Limits. |

## Output

Real output from `mode: "hotel"` (quote list truncated after 2 of 17):

```json
{
  "entityId": "ChUI17vV0u_fprYCGgkvbS8wZGQ5MDMQAQ",
  "name": "Marina Bay Sands Singapore",
  "hotelUrl": "https://www.google.com/travel/hotels/entity/ChUI17vV0u_fprYCGgkvbS8wZGQ5MDMQAQ",
  "address": "10 Bayfront Ave, Singapore 018956",
  "phone": "+65 6688 8868",
  "rating": 4.7,
  "reviewCount": 64684,
  "starClass": 5,
  "stayWindow": "Sep 27 – 28",
  "currency": "IDR",
  "rateCount": 17,
  "lowestRate": 21583872.0,
  "highestRate": 24962420.0,
  "rateSpread": 3378548.0,
  "cheapestProvider": "Expedia.co.id",
  "rates": [
    {
      "provider": "Marina Bay Sands",
      "providerHost": "linkcenterus.derbysoftca.com",
      "partnerId": "121",
      "isOrganic": true,
      "priceRaw": "IDR 21,691,972",
      "price": 21691972.0,
      "currency": "IDR",
      "rateType": "Total per night",
      "includesTaxes": true,
      "freeCancellation": true,
      "bookingUrl": "https://linkcenterus.derbysoftca.com/dplatform-linkcenter/booking.htm?hotelCode=SANDS-74224&checkInDate=2026-09-27..."
    },
    {
      "provider": "Expedia.co.id",
      "providerHost": "www.expedia.co.id",
      "partnerId": "89",
      "isOrganic": true,
      "priceRaw": "IDR 21,583,872",
      "price": 21583872.0,
      "currency": "IDR",
      "rateType": "Total per night",
      "includesTaxes": true,
      "freeCancellation": true,
      "bookingUrl": "https://www.expedia.co.id/Hotel-Search?selected=3231105&startDate=2026-09-27..."
    }
    // ... 15 more
  ],
  "recordType": "HOTEL",
  "_input": "ChUI17vV0u_fprYCGgkvbS8wZGQ5MDMQAQ",
  "_source": "travel-entity-prices-ssr",
  "_scrapedAt": "2026-09-18T04:21:11Z"
}
```

Real output from `mode: "search"`:

```json
{
  "entityId": "ChkIh46ls6ORhMkNGg0vZy8xMWZsZ3c1MnByEAE",
  "name": "ORIENTAL HOTEL KYOTO ROKUJO",
  "hotelUrl": "https://www.google.com/travel/hotels/entity/ChkIh46ls6ORhMkNGg0vZy8xMWZsZ3c1MnByEAE",
  "searchQuery": "hotels in Kyoto",
  "priceRaw": "IDR 1,018,048",
  "currency": "IDR",
  "price": 1018048.0,
  "priceIsTotal": true,
  "priceIncludesTaxes": true,
  "nights": 1,
  "stayWindow": "Sep 27 – 28",
  "dealFlag": null,
  "dealPercent": null,
  "rating": 4.2,
  "reviewCount": 1086,
  "starClass": 3,
  "propertyType": null,
  "amenities": ["Free Wi-Fi", "Parking", "Restaurant", "Accessible"],
  "reviewThemes": ["Property", "Breakfast", "Service"],
  "_source": "travel-search-ssr",
  "_input": "hotels in Kyoto",
  "_scrapedAt": "2026-09-18T05:08:49Z",
  "recordType": "HOTEL"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `entityId` | string | Google's ID for the hotel. Stable day to day, which is what makes rate tracking possible. |
| `name` / `address` / `phone` | string | Hotel identity, read from the hotel's own header block. |
| `rating` / `reviewCount` / `starClass` | number | Guest rating out of 5, number of reviews, official star class. |
| `priceRaw` / `price` / `currency` | string / number | Google's headline price, as published and as a number. |
| `priceIsTotal` / `priceIncludesTaxes` / `nights` | boolean / integer | What the price actually covers. |
| `stayWindow` | string | The dates the price applies to. See Limits. |
| `dealFlag` / `dealPercent` | string / integer | Google's verdict: "GREAT PRICE" or "18% less than usual". |
| `amenities` / `reviewThemes` | array | Amenity list, and Google's "People often mention" themes. |
| `rateCount` | integer | How many booking sites quoted this hotel. |
| `lowestRate` / `highestRate` / `rateSpread` | number | Cheapest, dearest, and the difference — the rate-parity figure. |
| `cheapestProvider` | string | Which booking site holds the lowest quote. |
| `rates` | array | Every quote: `provider`, `providerHost`, `price`, `rateType`, `includesTaxes`, `freeCancellation`, `bookingUrl`. |
| `recordType` | string | `HOTEL`, `RATE`, `SPONSORED`, `SURFACE` or `ERROR`. |
| `error` / `errorDetail` | string | Present only on failure rows, so a problem is never a silently missing hotel. |

## Limits worth knowing before you run it

These are properties of the source, not of the actor, and each one is reported in the data
rather than hidden:

- **The currency follows your proxy country, and cannot be requested.** Google ignores every
  currency parameter on these pages. Choose a proxy country matching the currency you want;
  every record tells you the currency it actually came back in.
- **The stay window is Google's default (tonight, one night) and cannot be chosen.** Every
  record carries `stayWindow` so you always know which dates a price refers to. For a rate
  history, run the actor on a daily schedule — that is what this data shape is for.
- **A search returns about 21 hotels and has no further pages.** To cover a city, run several
  narrower queries (by district or by hotel name) rather than expecting deeper pagination.
- **Not every hotel has many quotes.** A large property returns 17–25; a small one may return
  one or none, in which case you get an explicit record saying so.
- **Paid placements are kept separate.** The ads on a hotel's page are quotes for *other*
  hotels, so they only ever appear under `mode: "sponsored"` and never inside `rates` —
  mixing them in would quietly corrupt any parity analysis.
