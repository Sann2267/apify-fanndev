# 99.co Property Scraper (Indonesia & Singapore)

Scrapes property listings, prices, agents and market data from
[99.co](https://www.99.co). HTTP-only, no browser, no login, public data.

99.co runs **two entirely different applications on one domain**, which is the
single most important thing to know before scraping it:

| | Indonesia (`/id`) | Singapore (`/singapore`) |
| --- | --- | --- |
| Framework | Next.js Pages Router | Next.js App Router |
| Data layer | `__NEXT_DATA__` | schema.org JSON-LD + RSC flight payload |
| Page parameter | **`hlmn`** | **`page_num`** |
| Anonymous depth | **9 pages, hard** | no limit found |
| Per page | ~31 entries | ~36 entries |
| Corpus | 769,000+ listings | ~21,000 per query |

They share a Cloudflare edge and nothing else, which is why the modes are split
by market and the parsers do not overlap.

## Modes

| Mode | Input | Emits |
| --- | --- | --- |
| `idSearch` | `idSearchTargets` | Indonesian listings — the richest surface on the site |
| `idListingDetail` | `idListingSlugs` | Full listing plus POI, public Q&A and area price trend |
| `idLocations` | `idSearchTargets` | Location facets — the seeds for beating the page ceiling |
| `sgSearch` | `sgSearchTargets` | Singapore listings |
| `sgListingDetail` | `sgListingUrls` | Full Singapore listing from schema.org |
| `sgHdbResalePrices` | — | Median HDB resale price per town, from the open JSON API |

The Indonesian listing object is unusually good: alongside the asking price it
carries `last_price` and `last_price_change_at` (the previous asking price and
when it moved), `delta_price_percentage`, and `market_price` — 99.co's own
valuation to compare against. Plus an indicative mortgage table, coordinates,
the full administrative hierarchy, agent, and media counts.

## Anti-bot: what actually gates this site

**Cloudflare.** Plain `requests` is answered **403 on every path**. Under
`curl_cffi` impersonation, `chrome124`, `chrome131`, `firefox133` and
`safari17_0` are served normally.

`edge101` and `chrome99_android` are **deliberately excluded** from the ladder:
both drew "Just a moment" (HTTP 429, `cf-mitigated: challenge`) on the bare
homepage during recon. Rotating onto a profile that is itself challenge-prone
turns one bad request into two.

Blocks are detected on the **`cf-mitigated: challenge` response header**, not on
the status code — the same challenge arrives as 403 on deep Indonesian pages and
as 429 on the homepage, so status alone is ambiguous.

### The 9-page ceiling (the real constraint)

Indonesian search is **challenge-gated from page 10**. `?hlmn=10` and beyond
return `cf-mitigated: challenge`, and **no TLS profile gets past it** — verified
across `/id/jual/rumah` and `/id/sewa/rumah` at depths 10, 11, 12, 15, 20, 30,
50, 100, 200, 300, 400, 450 and 499, with a fresh session per profile.

This is policy, not a rate limit. A brand-new session is challenged on its very
first request to `hlmn=10`, while `hlmn=9` succeeds immediately afterwards.

So one Indonesian query reaches about **279 listings** (9 × 31), out of a corpus
of 769,000. The actor clamps `maxPages` to 9, logs the clamp, and after each
target logs how many of the matching listings it actually reached.

**The way through is to narrow the query** so each slice fits inside 9 pages.
Three dimensions are verified to reach the backend filter and move
`pagination.count`:

- **Location** — run `idLocations` and feed the `urlSlug` values back in.
  `jual/rumah` (769,269 matches) becomes `jual/rumah/jakarta-selatan` (87,872)
  becomes `jual/rumah/bandung/antapani`.
- **Price band** — `minPrice` / `maxPrice`. Jakarta Selatan houses narrowed to
  IDR 1–3 bn: 11,673 matches.
- **Bedrooms** — `minBedrooms`.

Singapore has no equivalent ceiling; `page_num=50` is served normally.

## Traps this actor handles

**1. Decoy pagination parameters, on both sites.** Indonesia takes `hlmn` and
Singapore takes `page_num`. `page`, `p`, `offset` and `start` are all accepted
with HTTP 200 and **silently ignored** — the response is page 1 again, with
`pagination.page` still reading 1. A scraper using `?page=` looks like it is
paging and returns the same 31 rows forever.

**2. The Indonesian listings array is not a list of listings.** It is a list of
*groups*, each tagged `primary` (paid developer and project placements) or
`secondary` (ordinary listings), interleaved. Both are emitted with `groupType`
attached; set `includeProjectPlacements: false` to drop placements, which you
want before counting a market, since placements are paid inventory rather than
organic supply.

**3. Singapore needs two extraction layers merged.** The schema.org `ItemList`
carries only URL, address and property type — but also the honest result total.
The RSC flight payload carries price, psf, beds, area, tenure and coordinates —
but no stable anchor to the canonical URL. They are joined on the listing id
(the last dash-separated token of the URL). Recon match rate: **36/36**.

**4. RSC encodes shared values as `$N` pointers.** A listing arrives as
`{"price": "$41"}` with row `41` holding `{"value":600,"unit":"S$"}`. Reading the
flight stream without resolving those gives you the string `"$41"` as a price.
The parser resolves them before emitting.

**5. Singapore *detail* pages have a different shape from search pages.** They
contain **no** `listing_id`-bearing RSC object at all — the data is in a
schema.org node typed `["Product", "Room"]`. Because `@type` is a *list* there,
any lookup keyed on the string form silently drops the richest node on the page.
(It did exactly that here until it was caught by a coverage check.)

**6. The Indonesian 404 is a 200-shaped page.** A dead slug renders normally
with `__NEXT_DATA__` present and `page: "/404"`. Detail pages do return a real
HTTP 404, so both are handled.

**7. The HDB price table splits meaning from values.** The API returns a
`headers` array and separate row arrays. Rows are zipped back onto their header
titles, and the raw `columns`/`values` pair is kept too, so a new flat-type
column widens the record rather than silently shifting every figure one cell
to the left.

## Output

Every record carries the house envelope — `_input`, `_source`, `_scrapedAt`,
`recordType` — on top of 99.co's own field shape. Indonesian records keep the
site's snake_case names (`full_address`, `location_pin`, `price.price_tag`);
Singapore records use the schema.org names.

Failures never disappear. A dead slug, an empty result set, a bad target or a
challenge wall each emit exactly one diagnostic row (`_error` = `not_found`,
`no_results`, `unparsable_input`, `challenge_wall`, `fetch_failed`,
`unexpected_shape`, `run_failed`), so a downstream join always sees a row for
every input. `challenge_wall` specifically means Cloudflare served a managed
challenge to *every* TLS profile — on Indonesian search that is the page-10
ceiling and is expected, not a bug.

See `.actor/output_schema.json` for every field.

## Local development

```bash
pip install -r requirements.txt

# All six modes plus the not-found / bad-target / ceiling controls
python test_local.py
python test_local.py idSearch sgSearch

# Run through the Apify SDK against local storage
apify run
```

`test_local.py` grades field coverage per record type, so a parser that quietly
stops matching shows up as a column of zeros rather than as a crash.

## Verified

Against the live site on 2026-09-21:

- All six modes return data; all three controls return exactly one diagnostic row.
- `idSearch` with `maxPages: 50` → clamped to 9, **240 unique listings, zero
  errors**, no challenge wall reached.
- `idSearch` on two targets with placements excluded → 120 records, 120 unique
  ids, **100% coverage** on `id`, `title`, `url`, `price`, `location_pin`,
  `agent`, `attributes`.
- Fan-out: `jual/rumah` 769,269 → `jual/rumah/jakarta-selatan` 87,872 →
  with an IDR 1–3 bn band, 11,673.
- `sgSearch` → 71 listings over 2 pages, 100% coverage, RSC join 36/36.
- `sgHdbResalePrices` → 27 towns.
- `idLocations` → 14 facets, all with a usable `urlSlug`.
- `apify validate-schema` clean on all three schemas.

## Notes on use

99.co's `robots.txt` disallows `/api` and a number of named crawlers. This actor
reads public, unauthenticated pages, and the one API endpoint it calls
(`hdb-resale-price`) sits under that prefix — check that your own use fits your
legal and contractual obligations before running it at volume, and keep
`maxPages` and `requestDelaySecs` proportionate to what you actually need.
