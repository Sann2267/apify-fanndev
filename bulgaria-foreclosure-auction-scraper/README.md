# Bulgaria Foreclosure Auction Scraper (BCPEA)

Every foreclosure property sale in Bulgaria is published by law on the portal of the Chamber of Private Enforcement Agents. This Actor turns that portal into structured rows: starting price in **EUR and BGN**, area, locality, district court, the bidding window, the announcement date and the enforcement agent's contact details.

About **1,400 sales are live at any time**, and none of it is available as a dataset anywhere else.

## Why use this actor

- **Complete national coverage.** Not a broker's selection - the official register that every private enforcement agent is required to publish to.
- **Both currencies, as published.** Bulgaria prints the opening price in euro and leva; both are returned, neither is converted.
- **Contact details included** - the enforcement agent running each sale, with registration number, office address and phone.
- **Dates you can sort.** Bidding opens, bidding closes and the announcement date, normalised to ISO.
- **Reaches closed sales too.** Sale IDs are sequential, so `range` mode walks back past the active list into sales that have already ended - which is how you build a price history.
- **Nothing lost in translation.** Bulgarian labels are mapped to English field names, and the portal's own labels and values ship alongside in `fields`.

## How it works

1. Pick a mode: sweep the active list, fetch specific sales, or walk a block of IDs.
2. The Actor reads the portal's published pages and parses each sale's label/value block.
3. Prices, areas and dates become numbers and ISO dates; everything else is passed through as published.
4. Rows stream into your dataset for JSON, CSV or Excel export.

## Input

```json
{
    "mode": "list",
    "perPage": 48,
    "fetchDetails": true,
    "maxItems": 200
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `list`, `property`, `range` or `reference`. |
| `fetchDetails` | boolean | In `list` mode, also open each sale's page for description, area, type, price and agent contact. |
| `perPage` | integer | Sales per list page, up to 100. Default `48`. |
| `startPage` | integer | Where to start paging. Default `1` (newest). |
| `propertyId` / `propertyIds` | string / array | Sale IDs or full portal URLs. |
| `startId` / `rangeCount` | string / integer | `range` mode: first ID and how many consecutive IDs to walk (max 2000). |
| `maxItems` | integer | Row cap. Default `200`. |
| `maxConcurrency` | integer | Parallel detail fetches. Default `4`. |
| `proxyConfiguration` | object | **Residential proxy, on by default and required for `list` mode.** |

### Example inputs

Sweep every active sale with full detail:

```json
{ "mode": "list", "perPage": 100, "fetchDetails": true, "maxItems": 1500 }
```

Cheap daily monitor - just the cards, newest first:

```json
{ "mode": "list", "perPage": 48, "maxItems": 100 }
```

Specific sales you are tracking:

```json
{ "mode": "property", "propertyIds": ["92444", "https://sales.bcpea.org/properties/92443"] }
```

Walk back into closed sales to build history:

```json
{ "mode": "range", "startId": "90000", "rangeCount": 500, "maxItems": 500 }
```

## Output

### `AUCTION`

```json
{
    "_input": "92444",
    "recordType": "AUCTION",
    "propertyId": "92444",
    "url": "https://sales.bcpea.org/properties/92444",
    "propertyType": "Парцел с къща",
    "locality": "с. Горно Черковище",
    "districtCourt": "Стара Загора",
    "area": 392,
    "areaUnit": "кв.м",
    "startingPriceEur": 3600,
    "startingPriceBgn": 7040.99,
    "startingPriceRaw": "Начална цена 3 600.00 EUR 7 040.99 лв.",
    "biddingStart": "2026-10-26",
    "biddingEnd": "2026-11-26",
    "announcementAt": "2026-11-27T09:00:00",
    "publishedAt": "2026-09-17T17:01:00",
    "enforcementAgent": "Ивелина Любенова Биволова",
    "agentRegistrationNumber": "869",
    "agentPhone": "042 633038",
    "agentMobile": "0888774465",
    "agentAddress": "с. Горно Черковище, ул. Христо Ботев 37",
    "description": "½ от ПОЗЕМЛЕН ИМОТ 36837.296.14, с площ от 2,708 дка ...",
    "detailFetched": true,
    "listPage": 1,
    "totalPages": 115
}
```

| Field | Type | Description |
|---|---|---|
| `startingPriceEur` / `startingPriceBgn` | number | Opening price in both published currencies. |
| `area` / `areaUnit` | number / string | Size, with the unit the portal used (square metres or decares). |
| `biddingStart` / `biddingEnd` | string | The window in which bids are accepted. |
| `announcementAt` | string | When the result is announced. |
| `publishedAt` | string | When the sale appeared on the portal. |
| `enforcementAgent` + `agent*` | string | Who runs the sale and how to reach them. |
| `fields` | object | Every label/value pair as the portal printed it, in Bulgarian. |
| `detailFetched` | boolean | Whether the row came from the sale's own page or only its list card. |

### `SURFACE` (reference mode)

```json
{
    "recordType": "SURFACE",
    "isAvailable": true,
    "detail": "payload parsed",
    "sample": {
        "cardsOnPage": 12,
        "totalPages": 115,
        "estimatedActiveSales": 1380,
        "newestPropertyId": "92444",
        "sampleCourt": "Стара Загора"
    }
}
```

Run this first to see how many sales are live before you size a sweep.

### Error rows

```json
{ "recordType": "ERROR", "_input": "999999999", "_error": "not_found", "_errorDetail": "no sale published under this id" }
```

## What you can build with it

- **Distressed property deal flow** - a daily sweep, filtered by district court, property type and price ceiling.
- **Price history** - `range` mode back through closed sale IDs gives starting prices over time, by region.
- **Enforcement agent directory** - who handles the most sales, in which courts, with contact details.
- **Regional market monitoring** - volume and average opening price per locality, month over month.
- **Lead lists for buyers' agents** - sales whose bidding window opens in the next 30 days.

## Notes & limits

- **Opening prices only.** The portal publishes the starting price, not the final hammer price - Bulgarian sealed-bid procedure announces the winner separately.
- **List cards carry a subset.** Court, agent, bidding window and announcement date come from the card; description, area, type, price and agent contact need `fetchDetails` or `property` mode.
- **Emails are obfuscated.** The portal protects them against harvesters, so `agentEmail` can arrive as a placeholder while the phone numbers are real.
- **Content is Bulgarian.** Field names are translated; values - localities, descriptions, property types - stay in the original, as published.
- **The list needs a residential connection.** The portal answers 403 to cloud datacenter addresses on its filtered list, so the Actor ships with Apify residential proxy enabled. Individual sale pages (`property` and `range` modes) work either way.
- **Sale IDs are sequential but not dense.** In `range` mode some IDs return `not_found`; that is normal and the row says so.

## Scheduling tips

- Daily `list` run with `perPage: 100` and no details is the cheapest way to catch new sales; enrich only the ones that pass your filter.
- Bidding windows are typically a month long, so a daily sweep never misses one.
- Use `reference` before resizing a sweep - it reports the current page count.

## Troubleshooting / FAQ

**Only 12 rows per page.** That is the portal's default. Raise `perPage` up to 100.

**`list` mode returns nothing but `property` mode works.** The proxy was turned off. The list is the part the portal refuses from datacenter addresses; leave the residential proxy enabled.

**`not_found` in range mode.** That ID was never used or was withdrawn. Expected when walking a block.

**No starting price on some rows.** List-card rows do not carry it - turn on `fetchDetails`.

**Can I filter by region or price in the input?** Not yet; the portal's filters are applied client-side. Pull the list and filter in your own pipeline - the fields you need are all in the output.

## Legal & fair use

Bulgarian law requires these sales to be publicly announced, and this portal is that public announcement. The Actor reads it as published, without an account and without circumventing any access control. The enforcement agent contact details are the official professional contacts published for each sale; treat them accordingly and respect applicable data-protection and marketing rules.
