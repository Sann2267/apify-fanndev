# Point2Homes Scraper

Browse Point2Homes (US/Canada) rental listings by location, and extract full listing/apartment-complex detail — no account or API key needed.

## Why use this actor

- Search any US/Canada city for houses/townhomes/condos for rent, or apartment complexes for rent, with automatic pagination
- Optional automatic enrichment: each search result can be followed up with a full detail-page fetch (description, bed/bath/floor-plan breakdown, agent/broker name, photo gallery, geo-coordinates) in one run
- `listing` mode fetches full detail directly for specific URLs you already have
- No account, login, or API key required
- Respects Point2Homes' own `robots.txt` — built entirely on paths it doesn't disallow (see Known limits)

## How it works

Pick a `mode`:
1. **`search`** — browse rental listings for one or more locations, paginated automatically.
2. **`listing`** — fetch full detail for one or more specific listing/apartment-complex URLs.

## Input

**Search, lightweight (summary cards only):**
```json
{
  "mode": "search",
  "propertyType": "Houses-For-Rent",
  "locations": ["TX/Dallas"],
  "maxItemsPerLocation": 60,
  "fetchDetails": false
}
```

**Search, enriched with full detail (default):**
```json
{
  "mode": "search",
  "propertyType": "Apartments-For-Rent",
  "locations": ["TX/Dallas", "CA/Los-Angeles"],
  "maxItemsPerLocation": 30,
  "fetchDetails": true
}
```

**Listing detail:**
```json
{
  "mode": "listing",
  "listingUrls": [
    "https://www.point2homes.com/US/Home-For-Rent/TX/Dallas/5031-Clover-Haven-Street.html",
    "https://www.point2homes.com/US/Apartment-Buildings/TX/Dallas/The-Brazos0.html"
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"search"` (default) or `"listing"`. |
| `propertyType` | string | `search` mode — `"Houses-For-Rent"` (default, covers houses/townhomes/condos) or `"Apartments-For-Rent"` (apartment complexes/buildings). |
| `locations` | array | `search` mode — one or more `"STATE/City-Name"` path segments exactly as Point2Homes uses in its own URLs, e.g. `"TX/Dallas"`, `"CA/Los-Angeles"`. Some cities require a county segment, e.g. `"NV/Clark-County/Henderson"` — copy the exact segment from a `point2homes.com/US/Houses-For-Rent/...` URL if a plain `"STATE/City"` doesn't work. |
| `maxItemsPerLocation` | integer | `search` mode — max listings per location, pagination followed automatically (30/page). Default 60. |
| `fetchDetails` | boolean | `search` mode — when `true` (default), each result is additionally fetched for full detail. When `false`, only the lightweight summary card is returned. |
| `listingUrls` | array | `listing` mode — full point2homes.com listing or apartment-building URLs. |
| `maxConcurrency` | integer | How many detail pages to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Search mode, `fetchDetails: false`** — one lightweight record per listing (real captured output, truncated):
```json
{
  "_input": "Apartments-For-Rent:TX/Dallas",
  "_source": "S1-search-summary",
  "_scrapedAt": "2026-08-26T02:21:36Z",
  "priceSpecification": { "minPrice": 1208, "maxPrice": 2470, "priceCurrency": "USD" },
  "object": {
    "@type": "ApartmentComplex",
    "name": "The Brazos",
    "image": "https://cdngeneral.point2homes.com/dmslivecafe/2/4573/Brazos - 2025-41.jpg?width=360&quality=80",
    "url": "https://www.point2homes.com/US/Apartment-Buildings/TX/Dallas/The-Brazos0.html",
    "address": {
      "streetAddress": "4341 Horizon North Pkwy",
      "addressLocality": "Dallas",
      "addressRegion": "TX",
      "postalCode": "75287",
      "addressCountry": "United States"
    }
  },
  "position": 1,
  "_gridTotal": 519
}
```

**Search mode with `fetchDetails: true` (default), or `listing` mode** — one full record per listing (real captured output, truncated):
```json
{
  "_input": "https://www.point2homes.com/US/Home-For-Rent/TX/Dallas/5031-Clover-Haven-Street.html",
  "_source": "S2-detail",
  "_scrapedAt": "2026-08-26T02:21:02Z",
  "agent": { "name": "Thomas Holbert" },
  "priceSpecification": { "minPrice": 2100, "priceCurrency": "USD" },
  "object": {
    "@type": "SingleFamilyResidence",
    "name": "5031 Clover Haven Street",
    "url": "https://www.point2homes.com/US/Home-For-Rent/TX/Dallas/5031-Clover-Haven-Street.html",
    "address": {
      "streetAddress": "5031 Clover Haven Street",
      "addressLocality": "Dallas",
      "addressRegion": "TX",
      "postalCode": "75227",
      "addressCountry": "United States"
    },
    "description": "Adorable 2 story Townhome close to shopping, walkable elementary school, and highway 30. Three bedrooms and 2 full bathrooms, backyard, and ample street parking. Perfect for families. $1850 per month with a full month deposit. Ready for move in today.",
    "numberOfRooms": 3,
    "numberOfBathroomsTotal": 2,
    "floorSize": { "value": 1200, "unitCode": "FTK" },
    "accommodationFloorPlan": [
      { "name": "3/2 1200 sqft", "numberOfBedrooms": 3, "numberOfBathroomsTotal": 2, "floorSize": { "value": 1200, "unitCode": "FTK" }, "price": 2100, "priceCurrency": "USD" }
    ]
  },
  "geoId": 2960449,
  "latitude": 32.7863,
  "longitude": -96.6894,
  "internalId": 2094045,
  "companyId": 262499,
  "propertyShortName": "5031-clover-haven-street",
  "city": "Dallas",
  "state": "TX",
  "country": "US",
  "photos": ["https://cdngeneral.point2homes.com/dmslivecafe/3/2094045/Clover(20250712125227581).png?width=590&quality=80"]
}
```

An apartment complex's `accommodationFloorPlan` typically lists several
entries (one per unit type), e.g. `The Brazos` returns floor plans named
`"Alamo"` (1bd/1ba, 660 sqft, $1214–1459) and `"Caddo"` (1bd/1ba, 773 sqft,
$1283–1568) among others.

A record with `_error` instead means that lookup couldn't complete — e.g.
`"_error": "location_not_found"` (unrecognized `STATE/City` slug) or
`"_error": "listing_not_found"` (removed/expired listing).

## Known limits

- **Rentals only.** Point2Homes now operates as a Yardi/RentCafe-network
  rental-listings aggregator — every discoverable page on the site is a
  rental. No working "for sale" URL pattern exists any more (confirmed —
  several guesses all 404/410). This actor is scoped accordingly.
- **Keyword/filter search is not available.** Point2Homes' `robots.txt`
  disallows the site's actual search UI/API (`/Search/*`, `/ListingSearch*`)
  and every query-string filter it exposes (`Price=`, `Bedrooms=`,
  `SquareFeet=`, `sort_by=`, etc.) for every crawler, with no exceptions —
  this actor honors that. Use `locations` (city-level browse) instead,
  which is not disallowed.
- **Some cities require a county segment in the URL** (e.g.
  `NV/Clark-County/Henderson`, `TX/Bexar-County/San-Antonio`) — a plain
  `STATE/City` for those returns `_error: "location_not_found"` rather than
  silently substituting another city's results (Point2Homes itself
  redirects an unrecognized slug to an unrelated fallback page instead of
  404ing — this actor detects that redirect and fails loud instead of
  passing through the wrong city's data).
- **Photo counts vary genuinely by listing**, not by a scraping limitation
  — some individually-listed rentals (as opposed to managed apartment
  complexes) have only 1 real photo on Point2Homes itself; placeholder
  "Images pending" slots are filtered out rather than returned as fake URLs.
