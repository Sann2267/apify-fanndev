# Ecommerce Platform Market Share & Migration Scraper

How many live stores does Shopify have this quarter? How fast is WooCommerce growing? How many stores left Wix for Shopify? This Actor turns the public platform reports at Store Leads into rows you can chart, compare and track - for **110 ecommerce platforms**, back to 2019.

## Why use this actor

- **110 platforms, one schema** - Shopify, WooCommerce, BigCommerce, Wix, Squarespace, Magento, Shopware, PrestaShop, Cafe24, Ecwid, Demandware and 99 more.
- **Seven years of quarterly history** in one run - the store-count series starts in 2019 Q1.
- **Migration flows both ways** - how many stores switched *to* a platform and *away from* it, broken down by the other platform.
- **Deep breakdowns** - stores by country, category, app, technology, theme, shipping carrier, top-level domain, employee count, product count, social media presence and published contact details.
- **Only public data.** The per-store database behind the publisher's paid account is not touched; what you get is exactly what the public reports publish, including their own "top stores" and "new stores" lists.
- **The in-progress quarter is flagged**, so a partial quarter never looks like a decline in your chart.

## How it works

1. Pick a mode and one or more platform slugs (`shopify`, `woocommerce`, ...), or set `allPlatforms` for the whole market.
2. The Actor reads each platform's published report page.
3. It parses the report's tables and embedded data into flat rows, parsing counts into real numbers and attaching machine codes (`US` next to `United States`) where the report publishes them.
4. Rows stream into your dataset for JSON, CSV or Excel export.

## Input

```json
{
    "mode": "platform",
    "platforms": ["shopify", "woocommerce", "bigcommerce"],
    "maxItems": 1000
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `platform`, `growth`, `breakdown`, `migration`, `stores` or `reference`. |
| `platform` / `platforms` | string / array | Platform slugs. A full report URL is accepted too. |
| `allPlatforms` | boolean | Process every published platform report (~110) instead of a list. |
| `dimension` / `dimensions` | string / array | Restrict `breakdown` to specific dimensions. |
| `maxItems` | integer | Row cap for the run. Default `1000`. |
| `maxConcurrency` | integer | Reports fetched in parallel. Default `4`. |
| `proxyConfiguration` | object | Optional; not needed. |

### Example inputs

Rank the whole market by live stores:

```json
{ "mode": "platform", "allPlatforms": true, "maxItems": 200 }
```

Chart Shopify vs WooCommerce since 2019:

```json
{ "mode": "growth", "platforms": ["shopify", "woocommerce"] }
```

Which countries and apps dominate Shopify:

```json
{ "mode": "breakdown", "platform": "shopify", "dimensions": ["country", "app"] }
```

Who is winning migrations:

```json
{ "mode": "migration", "platforms": ["shopify", "wix", "squarespace"] }
```

## Output

### `PLATFORM` (platform mode)

```json
{
    "_input": "shopify",
    "recordType": "PLATFORM",
    "platform": "shopify",
    "platformName": "Shopify",
    "reportUrl": "https://storeleads.app/reports/shopify",
    "reportTitle": "The State of Shopify in 2026",
    "reportUpdated": "2026-09-11",
    "liveStores": 3077514,
    "quarterOverQuarterGrowthPct": 7.3,
    "quarterOverQuarterQuarter": "2026 Q2",
    "yearOverYearGrowthPct": 11,
    "latestQuarter": "2026 Q3",
    "latestQuarterIsPartial": true,
    "latestQuarterStores": 3077515,
    "quartersOfHistory": 31,
    "sectionsFound": ["growth", "socialmedia", "contactinfo", "topcategories", "topcountries", "topapps", "employees", "products", "toptechnologies", "shipping", "themes", "tlds", "topstores", "newstores", "windomains", "lossdomains"]
}
```

| Field | Type | Description |
|---|---|---|
| `liveStores` | integer | Live stores on the platform right now. |
| `quarterOverQuarterGrowthPct` / `yearOverYearGrowthPct` | number | Growth rates as the report publishes them. |
| `latestQuarterIsPartial` | boolean | Whether the newest quarter is still running. |
| `quartersOfHistory` | integer | Length of the growth series for that platform. |
| `sectionsFound` | array | Which sections carried data - smaller platforms publish fewer. |

### `GROWTH` (growth mode)

```json
{ "recordType": "GROWTH", "platform": "shopify", "quarter": "2019 Q1", "activeStores": 753977, "isPartialQuarter": false }
{ "recordType": "GROWTH", "platform": "shopify", "quarter": "2026 Q3", "activeStores": 3077515, "isPartialQuarter": true }
```

31 rows for Shopify, 27 for WooCommerce - one per quarter since the publisher started counting.

### `BREAKDOWN` (breakdown mode)

```json
{ "recordType": "BREAKDOWN", "platform": "shopify", "dimension": "country", "label": "United States", "code": "US", "stores": 1169447 }
{ "recordType": "BREAKDOWN", "platform": "shopify", "dimension": "app", "label": "Judge.me Product Reviews App", "stores": 412553 }
```

Dimensions: `country`, `category`, `app`, `technology`, `theme`, `tld`, `shipping-carrier`, `employee-count`, `product-count`, `social-media`, `contact-info`.

### `MIGRATION` (migration mode)

```json
{ "recordType": "MIGRATION", "platform": "shopify", "direction": "switched-in", "otherPlatform": "WooCommerce", "stores": 8728 }
{ "recordType": "MIGRATION", "platform": "shopify", "direction": "switched-out", "otherPlatform": "WooCommerce", "stores": 6006 }
```

Both directions against the same platform, so net flow is a subtraction.

### `STORE` (stores mode)

```json
{
    "recordType": "STORE",
    "platform": "shopify",
    "listType": "top",
    "name": "Barnes & Noble®",
    "domain": "www.barnesandnoble.com",
    "url": "https://www.barnesandnoble.com",
    "rank": 74,
    "created": "2016/12/30"
}
```

`listType` is `top` (highest-ranked stores on the platform) or `new` (recently created).

### `AVAILABLE_REPORT` (reference mode)

```json
{ "recordType": "AVAILABLE_REPORT", "platform": "bigcartel", "reportUrl": "https://storeleads.app/reports/bigcartel" }
```

Run this first to get all 110 slugs.

### Error rows

```json
{
    "recordType": "ERROR",
    "_input": "definitely-not-a-platform",
    "_error": "not_found",
    "_errorDetail": "no report published for 'definitely-not-a-platform'. Run mode 'reference' to list every available platform."
}
```

## What you can build with it

- **Market share dashboards** - one `platform` run with `allPlatforms`, refreshed monthly, ranks the entire ecommerce platform market by live stores and growth.
- **Competitive migration analysis** - net flow between two platforms, quarter after quarter.
- **App and technology adoption** - how many Shopify stores run a given review app, analytics tag or shipping carrier, and how that compares on BigCommerce.
- **Geographic expansion research** - which countries a platform is strongest in before you localise a product for it.
- **Prospect discovery** - the top and newest store lists give real domains with traffic ranks.

## Notes & limits

- **The reports update roughly weekly** - `reportUpdated` on every `PLATFORM` row tells you exactly when.
- **The newest quarter is partial.** It is flagged with `isPartialQuarter` / `latestQuarterIsPartial`; comparing it to a full quarter understates growth.
- **Breakdowns are top-N lists**, not exhaustive - the report publishes roughly the top 10-20 values per dimension.
- **Store lists are what the report publishes**, typically 10 top stores and 10 new stores per platform. The publisher's full store database is a paid product and this Actor does not access it.
- **Smaller platforms publish fewer sections.** `sectionsFound` shows which ones had data, so an empty breakdown is visible rather than mysterious.

## Scheduling tips

- `platform` with `allPlatforms`: weekly or monthly is plenty - the source updates weekly.
- `growth`: monthly, and append to your own table; quarterly values are revised as data comes in.
- `migration` and `stores`: monthly.

## Troubleshooting / FAQ

**A platform returns `not_found`.** The slug is not one the publisher covers. Run `reference` for the full list - slugs are lower-case and have no spaces (`bigcommerce`, not `BigCommerce`).

**A breakdown dimension comes back empty.** That platform's report does not publish that section. Check `sectionsFound` on its `PLATFORM` row.

**The latest quarter looks lower than the previous one.** It is still in progress. Filter on `isPartialQuarter = false` when charting trends.

**Can I get the full list of stores on a platform?** Not from the public reports - only the top and new store lists they publish. This Actor stays on the public side.

## Legal & fair use

This Actor reads report pages that the publisher makes freely available to anyone, without an account and without circumventing any access control, and it does not touch the subscriber-only store database. The output is aggregate market statistics plus the store lists the reports themselves publish. Check the publisher's terms before redistributing the data commercially.
