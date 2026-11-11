# Steam Sales & Discount Tracker

Track every discount on Steam in one actor:
- All ~9,500 items on sale right now, with the exact time each discount ends and what kind of deal it is.
- The storefront's Daily Deal, Weekend Deals, Free Weekends and publisher/franchise sales.
- Free-to-keep giveaways.
- Regional prices converted to USD.
- Every item on a sale page.
- Steam's official calendar of seasonal sales and Fests.

Schedule it (for example every 6 hours) and each record also tells you **how the price changed since the previous run**. It also flags **new deals** and the **lowest price seen so far**, and lists **deals that ended**.

## What you can collect

| Mode | What you get | Requests |
|---|---|---|
| **All discounted items** (`deals`) | Every game, DLC and package on sale, filterable by tag, type, keyword, max price and minimum discount: price, original price, %, savings, review score, platforms, **discount end time**, **deal type** (daily / weekend / midweek / launch / special / named publisher campaign), developers, publishers | 1 per 100 items (+1 for details) |
| **Daily Deal & spotlights** (`featured`) | Today's Daily Deal, every storefront spotlight (Weekend Deal, Free Weekend, Franchise Sale, developer sales) with its end time and item count, and the featured specials | ~5 |
| **Free games** (`freebies`) | Free-to-keep giveaways (100% off, with the claim deadline) and Free Weekends | ~4 |
| **Regional prices** (`appPrices`) | Price and discount of your games in each country you list, converted to USD, ranked cheapest first, with the difference to the US price | 2 per country |
| **Sale page items** (`salePage`) | Every game, DLC, soundtrack, package and bundle on a publisher, franchise or developer sale page, priced, with the sale's start and end | 2 per sale |
| **Sale & Fest calendar** (`saleEvents`) | Steam's published schedule: Winter/Spring/Summer/Autumn sales, every themed Fest and Next Fest, with dates, status (upcoming / live) and days until start | 1 |

## Example input

```json
{
    "mode": "deals",
    "country": "US",
    "tags": ["Roguelike"],
    "category": "games",
    "minDiscount": 50,
    "maxPrice": 15,
    "maxItems": 10000,
    "compareWithPrevious": true,
    "alertPriceDropPct": 20
}
```

Regional price comparison:

```json
{
    "mode": "appPrices",
    "apps": ["1808500", "https://store.steampowered.com/app/632360/Risk_of_Rain_2/", "Elden Ring"],
    "countries": ["US", "GB", "DE", "BR", "TR", "IN", "ID", "AR"]
}
```

## Example output

A `DEAL` record (shortened):

```json
{
    "recordType": "DEAL",
    "country": "US",
    "position": 1,
    "totalDiscounted": 9463,
    "itemKey": "App_632360",
    "name": "Risk of Rain 2",
    "storeUrl": "https://store.steampowered.com/app/632360/Risk_of_Rain_2/",
    "discountPct": 67,
    "currency": "USD",
    "finalPrice": 8.24,
    "originalPrice": 24.99,
    "savings": 16.75,
    "reviewSummary": "Overwhelmingly Positive",
    "reviewPositivePct": 95,
    "reviewCount": 164199,
    "platforms": ["win"],
    "discountEndsAt": "2026-10-22T17:00:00Z",
    "hoursLeft": 274.6,
    "discountType": "special",
    "developers": ["Hopoo Games"],
    "publishers": ["Gearbox Publishing", "2K"],
    "discountedPurchaseOptions": [{"name": "Risk of Rain 2 + Survivors of the Void Expansion", "bundleId": 73409, "discountPct": 61, "bundleDiscountPct": 11}]
}
```

The same kind of record on a scheduled run, after a price drop:

```json
{
    "recordType": "DEAL",
    "name": "Japanese Ramen Simulator",
    "finalPriceCents": 1274,
    "previousFinalPriceCents": 1774,
    "priceChangeCents": -500,
    "priceDropPct": 28.2,
    "isNewDeal": false,
    "lowestPriceSeenCents": 1274,
    "isLowestPriceSeen": true,
    "alert": true
}
```

An `APP_PRICE` record:

```json
{
    "recordType": "APP_PRICE",
    "name": "Risk of Rain 2",
    "country": "ID",
    "currency": "IDR",
    "finalPrice": 39599.0,
    "discountPct": 67,
    "finalPriceUsd": 2.21,
    "usdRank": 1,
    "vsUsPricePct": -73.2,
    "cheapestCountry": "ID",
    "discountEndsAt": "2026-10-22T17:00:00Z"
}
```

A `SALE_EVENT` record:

```json
{
    "recordType": "SALE_EVENT",
    "eventType": "seasonal_sale",
    "name": "Winter Sale 2026",
    "startDate": "2026-12-17",
    "endDate": "2027-01-04",
    "status": "upcoming",
    "daysUntilStart": 67,
    "durationDays": 18
}
```

Record types: `DEAL`, `DAILY_DEAL`, `SPOTLIGHT`, `FEATURED_SPECIAL`, `FREEBIE`, `APP_PRICE`, `SALE_PAGE`, `SALE_ITEM`, `SALE_EVENT`, `DEAL_ENDED`, `ERROR`. Each record has `_input`, `_source` (which endpoint produced it) and `_scrapedAt`. Prices come as both amounts (`finalPrice`) and Steam's integer cents (`finalPriceCents`).

## Monitoring (change detection)

With **Compare with previous run** on (default), the actor remembers every item's price per task and adds:

- `previousFinalPriceCents`, `priceChangeCents`, `priceDropPct`. These show the change since the last run.
- `isNewDeal`: the item is discounted now but was not discounted (or not listed) last time.
- `lowestPriceSeenCents`, `lowestPriceSeenAt`, `isLowestPriceSeen`: the lowest price this task has ever recorded for the item.
- `alert`: a new deal, or a drop of at least **Price-drop alert threshold**.
- **`DEAL_ENDED` records** (in `deals` and `freebies` mode): items that were on sale last run and are gone now.

Snapshots are kept per mode **and per filter set** in the named key-value store `steam-sales-tracker-snapshots`, so tasks for different countries or tags never interfere. Ended deals are only reported after a run that read the **whole** result list. If `maxItems` cut the list short, that check is skipped, because a missing item could just be beyond the cut.

## Good to know

- **Prices are regional.** Steam runs different discounts per country (the US had 9,463 deals and Indonesia 9,593 on the same day), so `country` decides both the list and the currency. Prices follow the `country` setting, not the proxy location.
- **Seasonal sales and Fests** build their pages dynamically, so `salePage` cannot list their items. Use `deals` with the Fest's tag instead (for example `"tags": ["Cooking"]` during the Cooking Fest). Use `saleEvents` to know when they start.
- `minDiscount` and `maxPrice` are applied after download, because Steam has no discount filter. They don't reduce how many pages are read.
- About 2% of Steam's specials list is shown at 0%. These are edition upgrades, and DLC whose *bundle* is what's discounted. They are dropped by default (`minDiscount: 1`). Set `minDiscount: 0` to keep them; `discountedPurchaseOptions` then shows where the discount actually is.
- **Free Weekend** records show the game's discount end, if it is also on sale. Steam does not publish the free-play window's end time in machine-readable form.
- `sortBy: reviewsDesc` only lists reviewed items (about half of all deals). That's Steam's behaviour.
- USD conversion uses the European Central Bank's daily reference rates (about 30 currencies). Prices in other currencies keep `finalPriceUsd: null`.
- Unknown sale pages, appids and tag names come back as `ERROR` records with a clear reason. They never produce empty or made-up data.

## Technical notes

- **No WAF, no login, no browser.** Every endpoint is public: Steam store search, `api/featuredcategories`, `api/appdetails`, the sale pages, Steamworks' public "Upcoming Steam Events" page, and Valve's official keyless store API (`IStoreBrowseService/GetItems`) for discount end dates and deal types. HTTP only (`curl_cffi`, Chrome TLS profile; it rotates through a profile ladder if a gate ever appears).
- **The one limit is per IP on store search**: about 40 quick requests, then HTTP 429 for ~20 seconds. The actor paces search to one request every 2.5 seconds. With a proxy, a 429 switches to a new exit IP; without one, it waits the lockout out. A full 9,500-deal crawl takes about 5 minutes.
- **Pagination**: 100 items per page (Steam's maximum), read to the true end of the list.
- **Completeness**:
  - Steam's default "relevance" order keeps re-sorting during a long walk. In testing, a full walk in that order saw only 9,153 of 9,463 items, and price order loses ~0.6% to ties.
  - So a run that asks for the **whole** list (`maxItems` ≥ the number of deals) walks it in **name order**, which saw 9,463 of 9,463. `sortOrder` on each record tells you which order `position` refers to.
  - The actor measures coverage on every run. Ended deals are only reported when at least 99.8% of the list was seen.
- **Silent traps handled**:
  - An unknown country makes `appdetails` fall back to USD and search return 0, so country codes are validated up front.
  - Ended sale pages redirect to the homepage with HTTP 200 and are detected.
  - Unknown `sort_by` and `category1` values are ignored by Steam, so input values are restricted to the honoured ones.
  - Bundle-owner discounts carry two different prices in the page, and the displayed one is used.
- Proxy: Apify Residential is pre-selected. Datacenter or no proxy also works, just slower on very large crawls.
