# Crawling method - sales.bcpea.org

Recon date: **2026-09-18**, plain HTTP, no proxy, no login, `chrome124`.

## How this target was chosen

The research note asked for foreclosure-auction portals in jurisdictions with no
Apify coverage, naming 🇵🇱 🇯🇵 🇹🇷 🇨🇿 🇷🇴 🇵🇭. **All six failed recon:**

| Jurisdiction | Result |
|---|---|
| 🇵🇱 licytacje.komornik.pl | SPA. Its API (`/services/endpoint-notice/api`, `/services/item-back/api`) answers **500 with a JSON error id** to anonymous calls; the Nuxt chunks rate-limit to a "Strona zablokowana" page |
| 🇯🇵 bit.courts.go.jp | Host moved to `www.bit.courts.go.jp` (200/360 KB), but search is a **POST** to `/app/top/pt001/h02` that returns **500** without session state |
| 🇨🇿 portaldrazeb.cz | Listing is Vue-rendered; the fetch URL comes from a form `action` that is **not in the HTML**. Its documented API is **write-only for bailiff offices** and needs credentials issued by email |
| 🇹🇷 esatis.uyap.gov.tr | SPA, 55 KB, no discoverable data endpoint |
| 🇷🇴 licitatii.ro | Redirects to `/_backup/20210316/` - the site is a **dead archive** |
| 🇵🇭 pagibigfundservices.com | Acquired-assets path redirects to a **maintenance page** |

Rather than guess at any of them, the same *product* was searched for in other
uncovered jurisdictions. Twelve EU portals were probed; Bulgaria's was the one
that is both **server-rendered** and **unclaimed on the Store**:

| Portal | Result |
|---|---|
| 🇧🇬 sales.bcpea.org | **200, 459 KB, server-rendered, 115 pages** |
| 🇬🇷 eauction.gr | 200 but only 12 KB - a shell |
| 🇱🇹 eaukcionai.lt | 200, 15 KB - thin |
| 🇸🇰, 🇭🇷 | DNS does not resolve |
| 🇪🇪 | TLS error |
| 🇱🇻, 🇵🇹 | connection timeout |
| 🇭🇺, 🇸🇮 | 200 but no listing markers |

Store dedupe (2026-09-18): no Bulgarian auction Actor exists. The same product
in other jurisdictions is proven -- `signalflow/spain-auction-scout` (82 users),
`webdata_labs/germany-zvg-auctions-api`, `parseforge/florida-realforeclose-auctions-scraper`.

## Surfaces

| Path | Result |
|---|---|
| `/properties?perpage=<n>&p=<page>` | 200, server-rendered list |
| `/properties/<id>` | 200, 426 KB detail page |

No WAF, no cookie gate, no challenge on any request.

## Second gate found on the platform: the exit IP

Locally every path answered without a proxy. On Apify the **detail pages still
worked, but the list answered 403**:

```
BlockedUpstream("Exhausted 4 retries for https://sales.bcpea.org/properties?perpage=12&p=1: blocked response 403")
```

Re-running with `{"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}`
returned `isAvailable: true` and 115 pages. So the portal refuses datacenter
ranges **on the query-string list only**, while `/properties/<id>` is served to
anyone. Residential proxy is therefore the Actor's default, and the input schema
says which mode depends on it.

Worth noting as a pattern: this is the second target in this batch (with
`psa-card-cert-lookup-scraper`) where local recon was clean and the platform
found a second gate. **A target is not verified until it has run on the
platform.**

## Gotchas found (and handled in code)

1. **The paging parameters are lower-case `perpage` and `p`.** `page` and
   `perPage` are accepted and **silently ignored** - every request returns page
   one. A scraper written against the obvious names would report that the portal
   has 12 listings, and be wrong by two orders of magnitude.
2. **`perpage` scales**: 12 -> 115 pages, 48 -> 29, 100 -> 14. A full sweep is
   14 requests, not 115.
3. **The price is outside the detail container.** It sits in a summary column
   (`div.col--right`), while the field block is inside `div.wrapper-single`.
   Parsing only the container returned a complete record with **no price** -
   caught by the local smoke test, which asserts a price is present.
4. **The filter sidebar publishes the same label.** "НАЧАЛНА ЦЕНА" appears first
   in the price *filter* ("Избери / до 10 000 лв / от 10 000 лв..."), so the
   first match is a dropdown bound, not a price. The first build reported
   **10 000 BGN for every property**. Windows containing "Избери" are skipped,
   and the test now asserts the price is not one of the filter's round bounds.
5. **Two currencies on one line** since the euro changeover: `3 600.00 EUR
   7 040.99 лв.`. Both are captured; converting one into the other would invent
   precision the portal did not publish.
6. **The publication date is written in Bulgarian words** ("Публикувано на 17
   септември 2026 г. в 17:01 часа"), so it needs a month-name table, while every
   other date on the page is `DD.MM.YYYY`.
7. **Cards and detail pages share one markup primitive** (`div.label__group` ->
   `div.label` + `div.info`), so one parser serves both and an unmapped label
   still lands in `fields`.
8. **Labels repeat** between the property block and the agent block (`ОКРЪЖЕН
   СЪД` appears in both). The first occurrence wins, because that is the
   property's own.
9. **IDs are sequential**, which makes a range walk possible - and means missing
   ids inside a block are normal, not failures.

## Verified sample (2026-09-18)

Active list: **115 pages x 12 = ~1,380 sales**, newest id 92444.
Sale 92444: plot with house, с. Горно Черковище, Stara Zagora district court,
392 кв.м, **3 600.00 EUR / 7 040.99 лв.**, bidding 2026-10-26 to 2026-11-26,
result announced 2026-11-27 09:00, agent Ивелина Любенова Биволова (reg. 869).

## Not implemented

- **Server-side filtering by region/price** - the portal applies its filters in
  the browser, so there is no URL to carry them. Filtering belongs in the
  consumer's pipeline.
- **Scanned announcement documents** - the record names the file; downloading
  and OCR-ing court documents is a different product.
