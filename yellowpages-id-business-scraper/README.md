# Yellow Pages Indonesia Business & Lead Scraper

Extract Indonesian business listings from Yellow Pages ID — name, phone, email, website, full
postal address and GPS coordinates — plus B2B products, per-province market density and a
province/city directory. Pure HTTP, no browser, no API key, no login.

---

## Modes

| Mode | Input | Emits | What it is for |
| --- | --- | --- | --- |
| `search_businesses` | `queries` (+ `region` / `city`) | `BUSINESS` | The general lead builder. Keyword search across the whole directory. |
| `category_businesses` | `queries` = category slugs (+ `city`) | `BUSINESS` | The curated "top suppliers" block of a `/places/<slug>` page. Small but hand-ranked. |
| `company_details` | `companyUrls` | `COMPANY` | Full profile: labelled phone numbers, founding year, legal form, categories. |
| `search_products` | `queries` | `PRODUCT` | B2B product offers with price, seller and the seller's real shop URL. |
| `market_insights` | `queries` | `MARKET_INSIGHT` | Listing counts per province and city for a keyword, plus related keywords. One request. |
| `geo_directory` | `provinceCodes` | `GEO_NODE` | Provinces and their cities — the seed list for a systematic nationwide crawl. |

Set `enrichWithDetails: true` on the two business modes to merge each company's profile page into
its listing row (one extra request per company).

### Why one actor with modes rather than six actors

Every mode hits the same Django application, through the same host choice, with the same
pagination ceiling and the same record envelope. The host choice (below) is the fragile part of
this scraper — splitting it across six actors would mean six copies to re-verify whenever the
site's WAF configuration changes. Modes that emit different shapes stay separable through
`recordType`, which the dataset schema exposes as its own named views.

---

## How it gets the data

`www.yellowpages.id` puts a **Cloudflare Managed Challenge** on exactly the three paths that carry
the directory data:

| Path | yellowpages.id | yoys.id |
| --- | --- | --- |
| `/` , `/product-*` , `/citymap-*` | 200 | 200 |
| `/profil-*` (company profiles) | **403 `cf-mitigated: challenge`** | 200 |
| `/places/*` (categories) | **403 `cf-mitigated: challenge`** | 200 |
| `/listing/*` (search) | **403 `cf-mitigated: challenge`** | 200 |

All 18 `curl_cffi` TLS profiles — `chrome99_android` through `chrome136`, `safari15_5`–`18_0`,
`edge99`/`edge101`, `firefox133`/`firefox135` — return the **identical** 403 on the gated paths
while the homepage returns 200 from the same IP and the same session. A homepage warm-up issues no
clearance cookie. That makes it a path-scoped WAF *rule*, not a JA3 fingerprint gate, and it is not
solvable HTTP-only.

`www.yoys.id` is the same application serving the same Indonesian dataset — YP Media Ltd runs both
brands off one backend. Verified by resolving identical IDs on both hosts: `product-…_52399`
returns company `492034` on each, and `profil-551113` is the same company on each, byte-comparable
apart from brand strings. yoys.id applies no challenge on any path.

**So the actor reads from `yoys.id` and writes the matching `www.yellowpages.id` URL into
`yellowpagesUrl` on every record**, so results stay citable against the brand you asked for. If
yoys.id ever acquires the same rule the client fails over to yellowpages.id automatically and
rotates through the TLS ladder before giving up.

No IP-based blocking was observed, so **the proxy is off by default** — turn on Apify Proxy only
for very high volume.

---

## Known limits

These are properties of the site, measured rather than assumed. They are the things that will
surprise you if you do not know them.

- **250 rows per query, hard.** The result header advertises figures like "10000 hasil", but the
  backend serves only 10 pages of 25. Page 11 answers **HTTP 200 with a fully rendered, empty
  page** — not a 404 — so anything that pages on status code alone will loop silently. To go
  deeper, slice the same keyword by `region` or `city`; each slice gets its own 250. Run
  `market_insights` first to see where the volume actually is.
- **The free-text location box is a decoy.** The site's own `l=` parameter returns zero results for
  every value while echoing the place name in the page title. This actor ignores it and uses the
  facet parameters (`adm` / `cty`) that the sidebar actually uses.
- **Promoted listings ignore the region filter.** A sponsored entry from another province can
  appear in a filtered result set. Filter on `address.region` downstream if that matters.
- **Two kinds of entry share the directory.** `entryType: "COMPANY"` has a claimed profile page and
  a `companyId`; `entryType: "PHONE_LISTING"` is a phone-book record with a number but no profile
  page, so `companyId` is null and enrichment skips it.
- **Profile pages carry no coordinates.** Geo comes from listing pages only, so enrichment
  preserves the listing's `geo` rather than overwriting it.
- **Emails are rare.** Most listings publish none. Where one exists it is behind Cloudflare's email
  obfuscation, which this actor decodes.
- **Province codes are the site's own**, not Indonesia's official BPS numbering (`02` is Bali, not
  North Sumatra). Unused codes return a 200 page titled "Aceh" with zero cities; those are reported
  as `hollow_response` errors rather than pushed as empty provinces.
- **Missing companies return 302 → `/410`**, not 404. Reported as `not_found`.
- Fields are passed through as the site publishes them, so occasional upstream junk (an email in a
  `website` field, `foundedYear: "10"`) appears verbatim rather than being silently cleaned.

---

## Output

Every record carries the house envelope — `_input`, `_source`, `_scrapedAt`, `recordType` — on top
of the payload. Failures become `ERROR` rows with `_error` / `_errorDetail` instead of vanishing,
and truncated queries carry a `_warning`.

```json
{
  "_input": "percetakan",
  "_source": "S1-listing-search",
  "_scrapedAt": "2026-09-20T15:23:18Z",
  "recordType": "BUSINESS",
  "entryId": "365207",
  "entryType": "COMPANY",
  "companyId": "365207",
  "name": "Percetakan Raja Setting",
  "description": "Rajasetting merupakan Percetakan Offset dan Digital Printing…",
  "phone": "+62 81572606669",
  "emails": [],
  "website": "https://rajasetting.com",
  "address": {
    "street": "Jl. Babakan H. Tamim No. 25",
    "locality": "Bandung",
    "region": "Jawa Barat",
    "postalCode": "40125",
    "country": "Indonesia"
  },
  "geo": { "latitude": -6.90525, "longitude": 107.647461 },
  "detailUrl": "https://www.yoys.id/profil-365207-percetakan-raja-setting-bandung.html",
  "yellowpagesUrl": "https://www.yellowpages.id/profil-365207-percetakan-raja-setting-bandung.html"
}
```

Measured completeness on a 20-row `percetakan` / Jawa Barat run: phone 20/20, website 20/20,
coordinates 20/20, postcode 19/20, region 16/20, street 15/20.

---

## Recipes

**Build a city lead list**

```json
{ "mode": "search_businesses", "queries": ["percetakan"], "city": "Bandung",
  "enrichWithDetails": true, "maxItemsPerQuery": 250 }
```

**Find where the volume is before spending requests**

```json
{ "mode": "market_insights", "queries": ["bank"] }
```

Then feed the returned `regions[].filterValue` back in as `region` to collect 250 rows per
province instead of 250 nationwide.

**Nationwide sweep** — run `geo_directory` once for the city list, then iterate
`search_businesses` over `city` values.

---

## Stack

`curl_cffi` (TLS impersonation, `chrome124` primary with a 5-profile ladder) + `selectolax`
for parsing. Extraction follows JSON-LD first, HTML selectors only where JSON-LD does not reach.
Listing rows merge both layers per field, because neither is complete on its own.

Retries are exponential with jitter; `429`/`5xx` back off, challenges rotate TLS profile then host.
A shape change raises `UnexpectedShape` and fails the run loudly rather than emptying the dataset.
