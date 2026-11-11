# Steam Community Market Scraper - Prices, History & Order Books

Track the in-game economy of the Steam Community Market: full price history going back as far as 2014, live buy and sell order books, individual listings with float and pattern seed, catalogue search across any game, and a live feed of completed sales. Works for CS2, Dota 2, TF2, Rust, Steam trading cards and every other game with a market. No Steam account, no login, no API key.

## Why use this actor

- **No Steam account required.** You get the complete price series as data, every day since an item was first sold plus hourly points for the last month. No login, no API key, no chart-reading.
- **The whole order book, not just the best price.** Every buy and sell price level with quantities and running depth. A popular case has thousands of levels on each side, enough for real liquidity and spread analysis.
- **Ready-made market statistics.** Each item comes with its bid/ask spread, 24-hour, 7-day, 30-day, 90-day and 1-year average price and units sold, all-time high and low (with dates), and the 7-day vs 30-day trend.
- **Float, pattern seed and stickers on every listing.** Sort a skin's listings by lowest float and stop at a float cap: the quickest way to find low-wear copies, specific patterns or sticker crafts.
- **Any currency.** Pick USD, EUR, GBP, IDR, BRL, or any of the 39 currencies Steam supports.
- **Clean, stable JSON** for spreadsheets, databases, dashboards and trading bots, with automatic retries and export to JSON, CSV or Excel.

## How it works

1. Choose what to collect: a catalogue search, item overviews, price history, order books, individual listings, or the recent sales feed.
2. List your items by name or paste their Steam market page URLs. Or leave the list empty and let a search pick them, e.g. "the 50 most popular CS2 cases".
3. Optionally turn on **Include every variant** to get every wear, StatTrak and Souvenir version of a skin in one go.
4. The actor collects everything, paging through long lists for you and retrying anything that stumbles.
5. Results land in the dataset, one clearly typed row per item, price point, listing or sale, ready to download or push onward.

No scrapers, browsers or blocks to babysit.

## Input

**Item overview** (one summary row per item):

```json
{
    "mode": "itemOverview",
    "items": [
        "AK-47 | Redline (Field-Tested)",
        "https://steamcommunity.com/market/listings/730/Dreams%20%26%20Nightmares%20Case"
    ],
    "appId": "730",
    "currency": "USD",
    "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"], "apifyProxyCountry": "US" }
}
```

**Price history of the 20 most popular CS2 cases**, one row per data point:

```json
{
    "mode": "priceHistory",
    "appId": "cs2",
    "searchFilters": { "Type": ["CSGO_Type_WeaponCase"] },
    "maxItems": 20,
    "historyDays": 90,
    "historyOutput": "perPoint",
    "currency": "USD"
}
```

**Lowest-float listings** of a skin:

```json
{
    "mode": "listings",
    "items": ["AK-47 | Redline (Field-Tested)"],
    "listingSort": "floatAsc",
    "maxFloat": "0.16",
    "maxListingsPerItem": 100,
    "currency": "USD"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `search`, `itemOverview`, `priceHistory`, `orderBook`, `listings` or `recentSales`. |
| `items` | array | Exact market names (`AK-47 \| Redline (Field-Tested)`) or Steam market page URLs. Leave empty to take items from a search. |
| `appId` | string | Game: a Steam app id (`730` CS2, `570` Dota 2, `440` TF2, `252490` Rust, `753` Steam) or `cs2`, `dota2`, `tf2`, `rust`, `pubg`, `steam`. |
| `currency` | string | Currency of all prices (USD, EUR, GBP, IDR...). Uses Apify Proxy. |
| `expandVariants` | boolean | Add every wear / StatTrak / Souvenir variant of each item. |
| `searchQuery` | string | Text to search for (`knife`, `case`, `redline`...). |
| `searchFilters` | object | Category filters, e.g. `{"Type": ["CSGO_Type_WeaponCase"]}`, `{"Exterior": ["WearCategory0"]}`, `{"Quality": ["strange"]}`. |
| `sortBy` | string | `popular`, `priceAsc`, `priceDesc`, `quantityDesc`, `quantityAsc`, `nameAsc`, `nameDesc`. |
| `minPrice` / `maxPrice` | integer | Price range for search, in US dollars. |
| `maxItems` | integer | How many items search returns, or picks for the item modes. |
| `historyDays` | integer | Keep only the last N days of history points (0 = all). |
| `historyOutput` | string | `perItem` (one row per item with a `prices` list) or `perPoint` (one row per data point). |
| `orderBookDepth` | integer | Price levels per side of the order book (0 = all). |
| `maxListingsPerItem` | integer | Listings to collect per item. |
| `listingSort` | string | `priceAsc`, `priceDesc`, `floatAsc`, `floatDesc`, `patternAsc`, `patternDesc`. |
| `minFloat` / `maxFloat` | string | Float range for listings, e.g. `0.15` to `0.16`. |
| `includeFullDescription` | boolean | Keep the full description text on every listing and sale row. |
| `recentSalesPolls` / `recentSalesIntervalSecs` | integer | Poll the recent sales feed several times to build a longer history. |
| `filterRecentSalesByApp` | boolean | Only keep sales from the selected game. |
| `maxConcurrency` | integer | Parallel requests (default 4). |
| `proxyConfiguration` | object | Residential proxy recommended. Its country sets the currency. |

## Output

Every row has `recordType` plus `_input` (what you asked for), `_source` and `_scrapedAt`. Steam's own field names are kept as they are, and readable decimal prices are added next to them. The samples below are real rows from a live run. Item-mode samples were captured from an Indonesian connection, so they are priced in IDR; with the default settings you get USD. Long lists are cut short.

**`search`, recordType `ITEM`** (search is always priced in USD):

```json
{
    "_input": "redline",
    "_source": "S1-market-rpc",
    "_scrapedAt": "2026-10-10T21:17:45Z",
    "recordType": "ITEM",
    "strHash": "AK-47 | Redline (Field-Tested)",
    "cSellOrders": 1657,
    "eCurrency": 1,
    "strMinSellSubtotal": "$25.58",
    "appid": 730,
    "marketHashName": "AK-47 | Redline (Field-Tested)",
    "type": "Classified Rifle",
    "sellListings": 1657,
    "minSellPrice": 25.58,
    "minSellFee": 3.33,
    "currency": "USD",
    "commodity": false,
    "bucketGroupId": "G1807209A023004",
    "bucketGroupName": "AK-47 | Redline",
    "marketUrl": "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29"
}
```

**`itemOverview`, recordType `ITEM_OVERVIEW`**:

```json
{
    "recordType": "ITEM_OVERVIEW",
    "marketHashName": "AK-47 | Redline (Field-Tested)",
    "type": "Classified Rifle",
    "tagsByCategory": { "Type": "Rifle", "Weapon": "AK-47", "ItemSet": "The Phoenix Collection", "Rarity": "Classified", "Exterior": "Field-Tested" },
    "currency": "IDR",
    "highestBuyOrder": 578192.0,
    "lowestSellOrder": 588401.0,
    "spread": 10209.0,
    "spreadPct": 1.74,
    "buyOrderQuantity": 48161,
    "sellOrderQuantity": 1195,
    "historyPoints": 5253,
    "firstSaleDate": "2014-02-21T00:00:00Z",
    "allTimeHigh": 1414082.5,
    "allTimeHighDate": "2025-05-11T00:00:00Z",
    "allTimeLow": 75902.6797,
    "allTimeLowDate": "2015-06-21T00:00:00Z",
    "avgPrice24h": 591720.2078,
    "volume24h": 86,
    "avgPrice7d": 621463.0296,
    "volume7d": 651,
    "avgPrice30d": 663293.2597,
    "volume30d": 2395,
    "change7dVs30dPct": -6.31,
    "buyOrders": [{ "price": 578192.0, "quantity": 34, "cumulativeQuantity": 34 }, "... 9 more"],
    "sellOrders": [{ "price": 588401.0, "quantity": 1, "cumulativeQuantity": 1 }, "... 9 more"]
}
```

**`priceHistory`, recordType `PRICE_HISTORY`** (with `perPoint`, each entry of `prices` becomes its own `PRICE_POINT` row):

```json
{
    "recordType": "PRICE_HISTORY",
    "marketHashName": "Dreams & Nightmares Case",
    "currency": "IDR",
    "historyPoints": 2413,
    "firstSaleDate": "2022-01-21T00:00:00Z",
    "lastMedianPrice": 25242.041,
    "allTimeHigh": 191060.2344,
    "allTimeHighDate": "2022-01-21T00:00:00Z",
    "volume24h": 108584,
    "volume30d": 3381228,
    "change7dVs30dPct": -8.64,
    "prices": [
        { "time": "2026-10-09T22:00:00Z", "unixTime": 1791583200, "medianPrice": 25186.6406, "volume": 6718 },
        { "time": "2026-10-09T23:00:00Z", "unixTime": 1791586800, "medianPrice": 25237.1562, "volume": 6089 },
        "... 20 more"
    ]
}
```

**`orderBook`, recordType `ORDER_BOOK`**:

```json
{
    "recordType": "ORDER_BOOK",
    "marketHashName": "Dreams & Nightmares Case",
    "currency": "IDR",
    "highestBuyOrder": 25319.0,
    "lowestSellOrder": 25504.0,
    "spreadPct": 0.73,
    "buyOrderQuantity": 2684479,
    "sellOrderQuantity": 537117,
    "buyPriceLevels": 1847,
    "sellPriceLevels": 9345,
    "buyOrders": [
        { "price": 25319.0, "quantity": 2, "cumulativeQuantity": 2 },
        { "price": 25113.0, "quantity": 1, "cumulativeQuantity": 3 },
        "... more levels"
    ],
    "sellOrders": [
        { "price": 25504.0, "quantity": 82, "cumulativeQuantity": 82 },
        { "price": 25508.0, "quantity": 1, "cumulativeQuantity": 83 },
        "... more levels"
    ]
}
```

**`listings`, recordType `LISTING`** (sorted by lowest float):

```json
{
    "recordType": "LISTING",
    "listingid": "555788776600426528",
    "marketHashName": "AK-47 | Redline (Field-Tested)",
    "listingRank": 1,
    "price": 5576192.0,
    "sellerReceives": 4848863.0,
    "fee": 727329.0,
    "currency": "IDR",
    "floatValue": 0.15054911375045776,
    "paintSeed": 480,
    "stickers": [],
    "charms": [],
    "inspectImages": ["https://shared.akamai.steamstatic.com/market_listings/ea/730/555788776600426528/0_7801115096502093935.avif", "... 2 more"]
}
```

**`recentSales`, recordType `SALE`**:

```json
{
    "recordType": "SALE",
    "appName": "Counter-Strike 2",
    "marketHashName": "Prisma Case",
    "type": "Base Grade Container",
    "soldAt": "2026-10-10T21:17:48Z",
    "soldPrice": 29024.0,
    "soldPriceText": "IDR 29,024",
    "listingId": "533270778485424586"
}
```

| Field | Description |
| --- | --- |
| `recordType` | `ITEM`, `ITEM_OVERVIEW`, `PRICE_HISTORY`, `PRICE_POINT`, `ORDER_BOOK`, `LISTING`, `SALE` or `ERROR`. |
| `marketHashName` | The item's exact market name. Use it as the item key. |
| `currency` | Currency of the prices on that row. |
| `minSellPrice` / `sellListings` | Search: cheapest listing and number of listings. |
| `highestBuyOrder` / `lowestSellOrder` / `spread` / `spreadPct` | Best bid, best ask and the gap between them. |
| `buyOrders` / `sellOrders` | Order book levels: `{price, quantity, cumulativeQuantity}`, best price first. |
| `avgPrice24h` ... `avgPrice365d`, `volume24h` ... `volume365d` | Volume-weighted average price and units sold per window. |
| `allTimeHigh` / `allTimeLow` | Highest and lowest daily price ever, with dates. |
| `prices` / `medianPrice` / `volume` | History points: median sale price and units sold per day, or per hour for the last month. |
| `price` / `sellerReceives` / `fee` | Listings: what the buyer pays, what the seller gets, and the fee. |
| `floatValue` / `paintSeed` / `stickers` / `charms` | Listings: wear float, pattern seed, applied stickers (with scrape level) and charms. |
| `soldAt` / `soldPrice` | Sales: when the item sold and for how much. |
| `_error` / `_errorDetail` | Error rows only, e.g. `item_not_found` or `commodity_no_listings`, with a plain-language explanation. |

## Notes and limits

- **Item names must be exact.** Copy them from the item's Steam market page, or paste the page URL itself. A name that doesn't exist comes back as an `item_not_found` row, never as a silent gap.
- **Cases, keys, stickers and other interchangeable items** are traded through the order book only, so `listings` reports `commodity_no_listings` for them. Use `orderBook` or `itemOverview` instead.
- **Search groups variants:** one search row per skin (all wears together). Turn on **Include every variant** in an item mode to get each wear separately.
- **Currency follows the proxy country.** Steam prices everything in the visitor's local currency, so pick a currency (or a proxy country) and keep the residential proxy on. Search results are always in USD.
- **Recent sales:** Steam shows the latest 50 sales and refreshes about every 30 seconds. Set several polls to build a longer feed.
- Listings come 20 per page, so `maxListingsPerItem: 1000` means about 50 requests for that item. Every other mode needs one request per item, or one per 100 search results.
