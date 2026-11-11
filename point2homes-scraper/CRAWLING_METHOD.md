# Crawling Method — Point2Homes Scraper

**Last verified:** 2026-08-26

## robots.txt — re-verified independently, no block

`https://www.point2homes.com/robots.txt` returns HTTP 200. The `User-agent: *`
group has **no blanket `Disallow: /`** and no explicit Claude/ClaudeBot/
Claude-Web/Claude-SearchBot/anthropic-ai rule of any kind. No login wall
anywhere on the site. Cleared to build.

`robots.txt` is, however, the **load-bearing constraint on this actor's
architecture** (same pattern as `poshmark-scraper` in this portfolio) —
see "What robots.txt disallows" below.

## WAF: none active (Cloudflare present, but passive)

- `curl_cffi` `chrome124` gets clean `200`s on the homepage, every location
  search page, and every listing/apartment-complex detail page tested — no
  403s, no challenge pages, at no point during recon.
- Cloudflare **is** in front of the site (`cf-ray` header, `server:
  cloudflare`, `__cf_bm` cookie on every response) but never issued a JS
  challenge to a plain `chrome124` impersonation — no `Just a moment`, no
  `challenge-platform` marker, no `cf-mitigated` header.
- No PerimeterX (`_px3`/`_pxhd`/`pxcts`), no DataDome, no Kasada (`429` +
  `KP_UIDz`), no Akamai/Aliyun markers of any kind were observed on any
  request, despite the orchestrator's reasonable prior that a US/Canada
  real-estate portal might share Kasada/PerimeterX infrastructure with
  Zillow/Realtor.com — that did not turn out to be the case here. Given the
  first profile worked cleanly, the full TLS-profile ladder (chrome131,
  chrome99_android, safari17_0, edge101) was not needed.
- This makes sense given the site's actual business model now (see next
  section) — an SEO-driven rental-listings aggregator wants to be crawled.

## Important pivot: Point2Homes is now a rentals-only site

Point2Homes was historically a general (for-sale + rental) real-estate
portal. As of this recon, it operates as a **Yardi/RentCafe-network rental
listings aggregator**:
- Every homepage nav link is a "Houses For Rent" city page.
- The site sets a `.AspNet.Cafe.Au.Lait` cookie (a "RentCafe" branding
  tell) and the homepage links out to `rentcafe.com` and `yardi.com`.
- No working "for sale" URL was found. Guessed patterns
  (`/US/Homes-For-Sale/...`, `/US/Real-Estate-Listings/...`,
  `/US/Condos-For-Sale/...`) all returned `404`/`410`.
- `robots.txt` disallows `/Listings/*` (capital L, plural) broadly — very
  plausibly the old for-sale listings namespace, now retired but still
  blocked defensively.

**This actor is scoped to rental listings only** — houses/townhomes/condos
(`Houses-For-Rent`) and apartment complexes (`Apartments-For-Rent`), which
is the entirety of what's live and discoverable on the site today.

## What robots.txt disallows (and why it shapes this actor)

The single `User-agent: *` group disallows, among other things:

```
Disallow: */Search/*
Disallow: /ListingSearch*
Disallow: /Listings/*
Disallow: *LocationGeoId=
Disallow: *Location=
Disallow: *location=
Disallow: *SearchType=
Disallow: *sort_by=
Disallow: *SquareFeet=
Disallow: *YearBuilt=
Disallow: *ListingDate=
Disallow: *ListingPrice=
Disallow: *ListingsSearch=
Disallow: *Price=
Disallow: *Bedrooms=
Disallow: *OpenHouse=
Disallow: *selected_view=
Disallow: *selectedView=
Disallow: *search_mode=
Disallow: *showSaveSearchPopup=
Disallow: *agentname=
```

This rules out the site's actual filterable-search UI/API and every
query-string filter it exposes (price range, bed/bath count, sort order,
etc.) — none of that is used by this actor.

What is **not** disallowed and carries full, correctly-filtered data:

```
point2homes.com/US/Houses-For-Rent/<STATE>/<City>.html       -- NOT disallowed
point2homes.com/US/Apartments-For-Rent/<STATE>/<City>.html   -- NOT disallowed
point2homes.com/US/Home-For-Rent/<STATE>/<City>/<slug>.html  -- NOT disallowed (singular "Home", distinct from disallowed plural "/Listings/")
point2homes.com/US/Apartment-Buildings/<STATE>/<City>/<slug>.html -- NOT disallowed
...?page=<N>                                                  -- NOT disallowed (not in the query-param blocklist)
```

This actor is built entirely on that clean set. This mirrors the pattern
seen in `poshmark-scraper`: the disallowed "official" search surface turned
out to have an equally rich, non-disallowed alternative.

## Data shape: JSON-LD `RentAction`, both on search pages and detail pages

No `__NEXT_DATA__`/Apollo/Nuxt blob exists — this is a classic server-rendered
ASP.NET app (`.AspNet.Cafe.Au.Lait` cookie). Every relevant page embeds
valid, directly-`json.loads`-able `<script type="application/ld+json">`
blocks (no balanced-brace walking needed, unlike Poshmark's 4-5MB single-line
Vuex blob):

- **Search-results page** (`/US/Houses-For-Rent/TX/Dallas.html`): one
  `ItemList` block. `numberOfItems` is the **total** match count (not just
  what's on the current page); `itemListElement` carries 30 `ListItem`s per
  page, each wrapping a `RentAction` (price range + `object`: address, name,
  one thumbnail image, canonical URL, `@type` = `SingleFamilyResidence` or
  `ApartmentComplex`).
- **Listing/apartment-complex detail page**: two blocks — a `FAQPage` block
  (skipped; auto-generated SEO copy, not used) and a `RentAction` block
  carrying the full record: `agent` (`RealEstateAgent.name`),
  `priceSpecification`, and `object` with `description`, `numberOfRooms`,
  `numberOfBathroomsTotal`, `floorSize`, `petsAllowed`, and
  `accommodationFloorPlan` (array of per-unit-type `FloorPlan`s — an
  `ApartmentComplex` typically lists several, a `SingleFamilyResidence`
  usually just one).

Two fields exist **only** as HTML `data-*` attributes, nowhere in JSON-LD,
and are parsed separately:
- `<span id="location-info" data-geoid=... data-latitude=... data-longitude=...
  data-id=... data-companyId=... data-propertyshortname=...>` — geo-coordinates
  and Point2Homes' internal numeric IDs.
- `<ul class="gallery-photos"><li><img src="...">` — the photo gallery.
  Some `<img>` slots are literal placeholders (`src="/ilscontent/images/
  no-image.png"`, `alt="Images pending"`) — confirmed live on a real listing
  that genuinely has only 1 real photo uploaded. These are filtered out
  rather than kept as fake photo URLs.

## Pagination

`?page=<N>` on either search-results URL. 30 items/page. `numberOfItems`
(from the first page's `ItemList`) gives the true total so the actor knows
when to stop without guessing; a page beyond the last one 200s with an
empty `itemListElement` (`numberOfItems` header present but 0 `ListItem`s),
which is also treated as a stop condition, whichever comes first.

## Fail-loud finding: unrecognized location silently redirects instead of 404ing

**This was the single most important negative finding during recon.** An
unrecognized `<STATE>/<City>` slug does **not** return 404 — it returns a
`200` with a **silent server-side redirect** to an unrelated fallback page:

```
GET /US/Houses-For-Rent/ZZ/Nowhere.html
-> 200, final URL: /US/Houses-For-Rent.html
   (title: "Houses for rent in New York City, NY - 44 rentals ...")

GET /US/Houses-For-Rent/TX/Nonexistentcityxyz123.html
-> 200, final URL: /US/Houses-For-Rent/TX.html
   (title: "Houses for rent in Texas - 4516 rentals ...")
```

Without a defense against this, a typo'd or wrong location (e.g. a
county-requiring city given as plain `STATE/City`) would silently return
some *other* city's or state's listings, tagged with the wrong `_input` —
exactly the kind of silent-corruption failure `.ai/CLAUDE.md` principle #6
warns about. The fix: compare the **post-redirect URL** (`response.url`,
which `curl_cffi` exposes after following redirects) back against the
exact URL requested. Confirmed live that every valid location (including
county-qualified ones like `NV/Clark-County/Henderson`) round-trips with
**zero** redirect — `response.url == request_url` exactly — so a mismatch
is an unambiguous signal the location doesn't exist. Implemented in
`src/main.py::run_search` and surfaced as `_error: "location_not_found"`.

## Removed-listing detail pages return 410, not 404

Confirmed live with a fabricated listing slug: the detail-page equivalent
of a stale/removed listing returns **HTTP 410 Gone**, not 404. `src/main.py`
treats both as `listing_not_found`.

## Concurrency & proxy

Bounded by `asyncio.Semaphore(maxConcurrency)` for both the per-listing
detail-page enrichment fan-out (search mode) and the direct URL fetches
(listing mode). Each concurrent task gets its own `Point2HomesClient`
instance (own `curl_cffi` session) and its own fresh Apify Proxy URL — no
session is shared across `asyncio` tasks, per this portfolio's
anti-pattern list. Apify Residential proxy is the schema default; recon
itself was run from a plain datacenter/local IP with no issues, since
there's no active WAF to defeat.
