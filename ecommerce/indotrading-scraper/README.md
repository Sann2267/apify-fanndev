# Indotrading.com B2B Supplier & Product Scraper

Scrapes products, suppliers and supplier contact details from
[Indotrading.com](https://www.indotrading.com), Indonesia's largest B2B
marketplace directory. HTTP-only, no browser, no login, public data.

Seven modes, one actor. They share a TLS gate, a session and a product-card
parser, which is why they are not seven actors.

| Mode | Input | Emits |
| --- | --- | --- |
| `categoryProducts` | `categories` | Every product under a category, 40/page |
| `searchProducts` | `searchTerms` | Keyword product search |
| `productDetail` | `productUrls` | Full product record from schema.org JSON-LD |
| `supplierProfile` | `suppliers` | Company profile, optionally its whole catalogue |
| `supplierDirectory` | `categories` | Every supplier under a category |
| `searchSuppliers` | `searchTerms` | Keyword company search |
| `categoryTree` | — | All ~4,010 category slugs, in one request |

Optional per-run enrichment:

- **`includeContact`** — the supplier's WhatsApp number. One extra request per
  product. About two thirds of sellers have one on file.
- **`includeLastLogin`** — minutes since the supplier last signed in, the
  freshness signal the site renders as *"Online 2 Hari Lalu"*. Batched per
  page, so effectively free.
- **`includeSupplierProducts`** — in `supplierProfile`, also walk the
  supplier's own catalogue pages.

## Anti-bot: what actually gates this site

**Cloudflare, TLS fingerprint only.** There is no JS challenge, no clearance
cookie, no token to harvest and no rate limit worth the name.

| Client | Result |
| --- | --- |
| `requests` / `httpx` | **403** — Cloudflare "Attention Required" |
| `curl_cffi` chrome124, chrome131, safari17_0, firefox133, edge101, chrome99_android | **200**, all six |

All six profiles were tried on the same IP within the same minute as the 403.
So the profile ladder in `constants.TLS_PROFILES` is a *recovery* path, not a
search: a challenge body or an unexpected 403 rotates to the next profile and
rebuilds the session rather than failing the run.

**No IP gate.** 25 sequential requests in 9.2 s from one datacenter address all
returned full product payloads. Proxying is therefore **off by default**.
Residential stays available for an Indonesian exit address or high volume.

If Apify Proxy is requested but cannot be set up — which is what a **local**
run gets on a plan without the *Proxy external access* feature — the actor logs
a loud warning and continues direct rather than failing the run, because for
this target a proxy is a nicety rather than a requirement. On the Apify
platform the proxy path works normally.

## Surfaces and how they were found

`robots.txt` leaks `/api/` and `/AjaxMethod.asmx`. The `.asmx` endpoint is dead
— it falls through to the homepage. The live API host comes from
`window.storefrontApiHost` in the Astro bundle
`CategoryInteractions.astro_*.js`, which points at
`https://webapi.indotrading.com`. Three of its endpoints are open to anonymous
callers with no `Authorization`, no cookie and no origin check:

| Endpoint | Gives |
| --- | --- |
| `GET /api/Product/GetWhatsappLeadsData?secureProductId=` | Supplier WhatsApp number |
| `POST /api/Company/GetListCompanyLastLogin` | Minutes since last login, batched |
| `GET /api/Product/ListByCompany?companyId=` | A company's product ids |

The pages themselves are Astro SSR, so the product and supplier data is in the
HTML. Product detail pages carry full schema.org JSON-LD (`Product`, `Store`,
`BreadcrumbList`), which is what this actor reads there — it survives restyles
that break CSS selectors.

## Traps this actor handles

These are the things that will silently corrupt a naive scrape of this site.

**1. The page counter lies.** `/jual-pressure-washer` prints *"Menampilkan 640
Produk … (Halaman 1 dari 16)"* and runs dry at page 13, yielding **362** real
products. `/jual-mesin-las` advertises 79 pages and is empty well before 50.
The advertised numbers are recorded as `advertisedPages` /
`advertisedTotalProducts` and **never** used as a stop condition — paging stops
on the first page that renders zero cards.

**2. Pagination overlaps, intermittently.** Page 3 of `/jual-pressure-washer`
comes back as a repeat of page 2 (0 new items), while pages 5–11 are all fresh.
Records are deduplicated per target by `productId` / `companySlug`, but a page
of pure repeats does **not** stop the walk — stopping there would have cost 280
of the 362 products. The run log reports how many repeats were dropped.

**3. Unknown paths return HTTP 200 with the homepage.** `/rfqlist/pompa`,
`/sitemap.xml` and `/supplier` all answer 200 with the identical 451 KB
homepage instead of a 404. A page carrying the homepage `<title>` when
something else was expected is treated as `not_found`. Real 404s also exist
(a 24-byte body for a dead category, a full *"Produk Tidak Ditemukan"* page for
a dead product id) and map to the same diagnosis.

**4. Decoy pagination parameters.** `?page=N` works, and so does the bare `/N`
suffix. `hal`, `p`, `pg` and `PageNumber` are all accepted with HTTP 200 and
**silently ignored**, returning page 1 every time — success-shaped nonsense.

**5. Hidden membership badges in the page header.** The logged-out header
carries one hidden `.membership-supplier` badge per tier (free, platinum,
diamond) as templates for the member menu. A document-wide query returns tiers
belonging to nobody. Badge reads are scoped to `#comproHeader` or to the
individual card.

**6. The WhatsApp button is a UI gate, not a data gate.** Only 18 of 40 cards
render a `.showWa` button, but the contact endpoint returns a number for the
other 22 as well. The encrypted id is read from whichever button carries
`data-enc-pid` (the phone button always does), taking contact coverage from
45% to ~100% of *lookups*, and ~67% of products end up with an actual number.

**7. `priceRaw` and `priceText` disagree on purpose.** When a seller hides the
price the page prints *"Minta penawaran"* over a placeholder number such as
`123`. Both values are emitted; reading `priceRaw` alone will invent prices.

**8. Indonesian digit grouping.** `Menampilkan 4.004 Produk` is four thousand
and four, not 4.004.

**9. The search redirect discards the page parameter.** A keyword matching a
category name is 302'd from `/searchkeyword.aspx?keyword=mesin+las&page=2` to
`/jual-mesin-las` — **without** the query string. Re-requesting the search URL
for page 2, 3, 4 therefore lands on page 1 of the category every time, and the
scrape silently caps at 40 products while looking like it paged four times.
This actor follows the redirect once on page 1 and then pages the destination
path directly, which took `mesin las` from 40 records to 158.

## Closed surfaces

- **`/rfqlist/`** (buying requests / tenders) — reachable but always empty for
  anonymous callers: *"Maaf, kami tidak menemukan Permintaan …"* for every
  keyword and category tried. Login-gated.
- **`/AjaxMethod.asmx/*`** — advertised in `robots.txt`, falls through to the
  homepage.
- **No sitemaps.** `/sitemap.xml` and friends are homepage fallbacks. Use
  `categoryTree` instead: one request, ~4,010 slugs.

## Output

Every record carries the house envelope — `_input`, `_source`, `_scrapedAt`,
`recordType` — on top of the site's own fields. `recordType` is one of
`product`, `supplier`, `category` or `error`.

Failures never disappear. A dead slug, an empty result set or a failed fetch
each emit exactly one diagnostic row (`_error` = `not_found`, `no_results`,
`fetch_failed`, `unexpected_shape`, `run_failed`), so a downstream join always
sees a row for every input. Non-fatal degradation is marked with `_warning`,
which distinguishes *"this seller has no WhatsApp number on file"*
(`no_whatsapp_number_on_file`) from *"the lookup did not complete"*
(`contact_lookup_failed`).

See `.actor/output_schema.json` for every field.

## Local development

```bash
pip install -r requirements.txt

# Exercise all seven modes plus the not-found controls against the live site
python test_local.py
python test_local.py categoryProducts productDetail

# Run through the Apify SDK against local storage
apify run
```

`test_local.py` grades field coverage per record type, so a parser that quietly
stops matching shows up as a column of zeros rather than as a crash.

## Verified

Against the live site on 2026-09-21:

- All seven modes return data; all three not-found controls return exactly one
  diagnostic row.
- `categoryProducts` on `/jual-pressure-washer` with `maxPages: 14` →
  **362 unique products from 79 suppliers, 79 repeats dropped, zero duplicates
  on disk**, clean stop at page 13.
- `categoryTree` → 4,010 categories in one request.
- `searchProducts` on the redirecting term `mesin las` with `maxPages: 4` →
  158 unique products across pages 1–4 (40 before the redirect fix).
- Contact enrichment: 100% of lookups answered, 67% carried a number.
- Last-login enrichment: 361/362.
- Field coverage 100% on `productId`, `productName`, `priceText`, `companyName`.

## Notes on use

Indotrading's `robots.txt` disallows a number of named crawlers and the `/api/`
prefix. This actor scrapes public, unauthenticated pages; check that your own
use fits your legal and contractual obligations before running it at volume,
and keep `maxPages` proportionate to what you actually need.
