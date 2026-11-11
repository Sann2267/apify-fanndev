# Facebook Marketplace Leads Scraper

Scrape Facebook Marketplace listings by city and category, or by search term:
title, price, location, posting date, age, sold status, photos, delivery
options, and the vehicle or property attributes Facebook renders alongside them.

Built for used-car dealers, property brokers and anyone doing second-hand price
research.

No login, no cookies to paste, no proxy required.

## Read this before you buy: the seller's name is not public

Facebook withholds the seller's identity from signed-out visitors —
`marketplace_listing_seller` comes back `null` on both the feed and the listing
page. This actor reports `sellerName: null` rather than omitting the field, so
the absence is visible in your data instead of looking like a parse gap. **No
logged-out scraper can return it**, whatever its listing promises.

What you *do* get for locating a lead: city, state, the human-readable location
line, and — on detail pages — the postal code and approximate coordinates.

## Use the city slug, not a location id

The city is the segment in the Marketplace URL: `nyc`, `jakarta`, `london`,
`sydney`.

A **numeric** location id looks like it works and does not. Measured on the same
category feed:

| Input | Result |
| --- | --- |
| `/marketplace/nyc/vehicles` | New York and New Jersey listings |
| `/marketplace/109571519060768/vehicles` | HTTP 200, 24 listings, all **California** |

The id is accepted and ignored, and you get Facebook's default location
presented as yours. This actor rejects numeric entries with a warning instead of
scraping them into wrong data.

## What you get

| Field | Example |
| --- | --- |
| `title`, `customTitle` | `2013 Subaru BRZ` |
| `priceText`, `priceAmount` | `$200,000`, `200000.0` |
| `city`, `state`, `locationText` | `Hayward`, `CA`, `Hayward, California` |
| `createdAtIso`, `ageDays` | `2026-09-10T…`, `9` |
| `subtitles`, `vehicleMileage`, `vehicleYear` | `["50K miles"]`, `50000`, `2013` |
| `bedrooms`, `bathrooms` | for property listings |
| `deliveryTypes`, `isSold`, `photoUrl`, `listingUrl` | |

With **`fetchDetails`** on, each listing page adds `description`, `condition`,
`currency`, `latitude`, `longitude` and `postalCode` — none of which appear in
the feed — at one extra request per listing.

## Input example

```json
{
  "cities": ["nyc", "jakarta"],
  "categories": ["vehicles"],
  "minPrice": 5000,
  "maxPrice": 25000,
  "sortBy": "creation_time_descend",
  "maxAgeDays": 7,
  "maxListingsPerQuery": 120,
  "fetchDetails": true,
  "exportFormats": ["csv"]
}
```

## Which filters are real

| Filter | How it is applied |
| --- | --- |
| `minPrice` / `maxPrice` | sent to Facebook **and** enforced locally — verified honoured (a $20k–$40k request returned $20,000–$39,000) |
| `sortBy` | sent to Facebook — verified to change the result set |
| `radiusKm` | sent to Facebook |
| `maxAgeDays` | enforced **locally**, against each listing's own timestamp |
| `excludeSold`, `titleContains` | enforced locally |

`maxAgeDays` is deliberately not sent as Facebook's `daysSinceListed`
parameter: that parameter is accepted and then ignored — a request with
`daysSinceListed=1` returned byte-for-byte the same listings as one without it.
Filtering on the published `creation_time` is the only version of this filter
that is actually true.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the ~24 listings Facebook renders.

The rate limit is on Facebook's GraphQL endpoint, which every actor in this
family uses for its second page onwards. It was measured on 2026-09-20 with the
Ad Library actor, three runs of the same search within a minute:

| Run | Result |
| --- | --- |
| Apify, no proxy | 30 results, 1 page — log: `Rate limit exceeded` |
| Apify, `RESIDENTIAL` proxy | 60 results, 4 pages |
| Local machine, no proxy | 70 results, 5 pages |

So: switch the Apify proxy on and pick the **RESIDENTIAL** group whenever you
want more than the first page. Running from your own machine needs no proxy at
all.

The actor logs a warning naming the rate limit when it hits one, so a short run
is never silently mistaken for a short result set.

## Notes

- Listings with no readable price are **dropped** by a price filter rather than
  admitted on a guess.
- `photoUrl` is a signed CDN link and expires.
- `vehicleMileage`, `bedrooms` and `bathrooms` are parsed from Facebook's
  free-text attribute line (`"50K miles"`), which is the only place the feed
  publishes them. The original strings are kept in `subtitles`.
- Coordinates on detail pages are Facebook's approximate point for the listing,
  not the seller's address.
