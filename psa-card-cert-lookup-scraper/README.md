# PSA Card Cert Lookup - Grade, Population & Comparable Sales

Turn a PSA certification number into a complete row: what the card is, what grade it earned, **how many exist at that grade**, how many grade higher, PSA's own value estimate, and the recent sales of comparable copies with prices, dates and marketplaces.

Population tells you how rare a card is. Sales tell you what it is worth. This Actor returns both from the same lookup - no PSA account, no API key.

## Why use this actor

- **Population and price in one row.** Most tools give you one or the other; the scarcity number and the market comps arrive together, so a rarity-versus-value screen is a single sort.
- **Real comparable sales** - price, date, marketplace, sale type, the grade that sold and its own certificate number, so you can follow any comp back to its own record.
- **`Pop Higher = 0` is the collector's question** - it tells you instantly whether a card is the top-graded copy.
- **Bulk-friendly.** Feed a list of certificate numbers, or walk a consecutive block with `range` mode, since PSA issues certificates sequentially.
- **Fails loudly.** An unknown certificate returns `not_found`, junk input returns `invalid_cert`, and a layout change returns `shape_changed` instead of a silently blank row.

## How it works

1. You give the Actor one or more PSA certification numbers - the number printed on the label. Full `psacard.com/cert/...` URLs and `#`-prefixed numbers work too.
2. The Actor opens each public verification page and reads everything it publishes.
3. `cert` mode returns one row per certificate with the item, its population and a sales summary; `sales` mode returns one row per comparable sale.
4. Rows stream into your dataset for JSON, CSV or Excel export.

## Input

```json
{
    "mode": "cert",
    "certNumbers": ["49204884"],
    "maxItems": 200,
    "maxConcurrency": 3
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `cert`, `sales`, `range` or `reference`. |
| `certNumber` / `certNumbers` | string / array | Certification numbers, URLs or `#`-prefixed numbers. |
| `startCert` | string | `range` mode: first certificate of the block. |
| `rangeCount` | integer | `range` mode: how many consecutive certificates to walk (max 5000). |
| `maxItems` | integer | Row cap for the run. Default `200`. |
| `maxConcurrency` | integer | Parallel lookups. Default `3` - keep it modest. |
| `proxyConfiguration` | object | **Residential proxy, on by default and required.** PSA refuses datacenter addresses. |

### Example inputs

Look up a collection:

```json
{ "mode": "cert", "certNumbers": ["49204884", "69300886", "147233572"] }
```

Pull the comps behind one card:

```json
{ "mode": "sales", "certNumber": "49204884" }
```

Sample a block of certificates graded around the same time:

```json
{ "mode": "range", "startCert": "49204884", "rangeCount": 50 }
```

## Output

### `CERT` (cert and range modes)

```json
{
    "_input": "49204884",
    "recordType": "CERT",
    "certNumber": "49204884",
    "certUrl": "https://www.psacard.com/cert/49204884",
    "itemGrade": "GEM MT 10",
    "gradeNumber": 10,
    "year": "2018",
    "brand": "PANINI PRIZM EMERGENT",
    "subject": "LUKA DONCIC",
    "cardNumber": "3",
    "category": "BASKETBALL CARDS",
    "varietyPedigree": "EMERGENT",
    "labelType": "w/ Fugitive Ink Technology",
    "psaEstimate": 60.0,
    "psaEstimateRaw": "$60.00",
    "psaPopulation": 4923,
    "psaPopHigher": 0,
    "recentSalesCount": 5,
    "recentSaleMin": 46.0,
    "recentSaleMax": 70.0,
    "recentSaleAvg": 56.8,
    "latestSaleDate": "2026-09-15"
}
```

| Field | Type | Description |
|---|---|---|
| `itemGrade` / `gradeNumber` | string / number | Grade as printed, plus its numeric part for sorting. |
| `psaPopulation` | integer | How many copies exist at this grade. |
| `psaPopHigher` | integer | How many copies grade higher. `0` means this is a top-graded copy. |
| `psaEstimate` | number | PSA's own published value estimate at this grade. |
| `recentSaleMin` / `recentSaleMax` / `recentSaleAvg` | number | Range and plain average of the comps on the page. |
| `latestSaleDate` | string | Most recent comparable sale. |

### `SALE` (sales mode)

```json
{
    "recordType": "SALE",
    "sourceCertNumber": "49204884",
    "saleIndex": 0,
    "subject": "LUKA DONCIC",
    "year": "2018",
    "soldPrice": 70.0,
    "soldDate": "2026-09-15",
    "seller": "eBay",
    "saleType": "FixedPrice",
    "grade": "PSA 10",
    "certNumber": "69300886",
    "lotNumber": "267742724000",
    "imageUrl": "https://i.ebayimg.com/images/g/aRgAAeSw6XlqarNX/s-l400.webp"
}
```

Each sale carries the certificate of the copy that sold, so you can look that one up in turn and build a chain of comparable cards.

### `SURFACE` (reference mode)

```json
{
    "recordType": "SURFACE",
    "surface": "cert-page",
    "isAvailable": true,
    "detail": "payload parsed",
    "sample": { "certNumber": "49204884", "itemGrade": "GEM MT 10", "psaPopulation": "4,923", "recentSales": 5 }
}
```

### Error rows

```json
{ "recordType": "ERROR", "_input": "999999999999", "_error": "not_found", "_errorDetail": "PSA has no such certification number" }
```

## What you can build with it

- **Collection valuation** - feed every certificate you own and get grade, scarcity and current market range in one sheet.
- **Rarity screens** - sort by `psaPopHigher = 0` to find top-pop copies, or by low `psaPopulation` for genuinely scarce grades.
- **Deal checking** - compare an asking price against `recentSaleMin`, `recentSaleAvg` and `psaEstimate` before you buy.
- **Market tracking** - schedule the same certificate list weekly and watch estimates and comps move.
- **Comp chains** - each sale row carries its own certificate number, so one card expands into its graded neighbours.

## Notes & limits

- **The full population report needs a PSA account.** This Actor returns the population figure the public certificate page prints, which is the population for that item at that grade, plus the count graded higher. It links to the full set report but does not open it.
- **Comparable sales are the ones PSA lists** - typically the five most recent. This is not a complete sales archive.
- **`psaEstimate` is PSA's own number**, not an appraisal by this Actor and not investment advice.
- **A residential proxy is required, not optional.** PSA answers home connections and refuses cloud ones; the Actor ships with Apify residential proxy enabled, and turning it off makes every row fail. This is also why the run costs a little proxy traffic.
- **The source is strict.** Keep `maxConcurrency` low; a wave of parallel lookups is the fastest way to get refused. The Actor negotiates the connection itself and records which profile worked in `_tlsProfile`.
- **Certificates are sequential**, which makes `range` mode useful for sampling a grading period - but most numbers in any block belong to cards you have no interest in.

## Scheduling tips

- Valuation refresh: weekly per certificate list is plenty; PSA's estimates do not move daily.
- New comps: `sales` mode weekly on the certificates you care about.
- Start any new schedule with one `reference` run to confirm the source is answering.

## Troubleshooting / FAQ

**A certificate returns `not_found`.** PSA has no record for that number. Check for a typo - the number is printed on the label under the barcode.

**`blocked_or_transient` on every row.** Almost always the proxy setting: PSA refuses datacenter IP addresses, so the residential proxy must stay enabled. If it is on, lower `maxConcurrency` and try again.

**`shape_changed`.** The page returned 200 but no item fields - PSA changed its layout. The row says so instead of shipping an empty record.

**Why is population empty for my cert?** A few item types (tickets, some memorabilia) do not publish one. The rest of the row is still complete.

**Can I search by player instead of certificate number?** Not in this Actor. The public entry point is the certificate number; searching by player needs the account-only sections.

## Legal & fair use

This Actor reads the public certificate verification page that PSA publishes for every graded item - the same page a buyer checks before a purchase - without an account and without touching the account-only population reports or auction-price archives. Prices and estimates are published market data, not investment advice.
