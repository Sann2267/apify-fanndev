# Crawling Method — IndonesiaYP Business Directory Scraper

**Last verified:** 2026-09-08

## Target & jurisdiction choice

`indonesiayp.com` — a national business directory for Indonesia
(~13,900 listings in Restaurants alone, 696 pages at 20 per page).

Babak 41 of `ACTOR_MARKET_RESEARCHER_NEW.md` established the candidate
("national business directory × empty jurisdiction"): the data-type is
proven in Germany (928 users; `plowdata/gelbe-seiten` 417u / 395,433 runs),
France (1,279u), India (1,635u) and the UK (434u), while Indonesia had
**3 sellers / 7 users** in total.

### Correction to Babak 41: the Turkish target was misread

Babak 41 ranked **Sarısayfalar (TR)** first, on a probe that returned
"200, Apache, 111 KB, no WAF". Re-checked here, that probe measured the
wrong kind of page — `sarisayfalar.com` is **not** a business directory
despite the name:

| Evidence | Finding |
|---|---|
| Homepage links | classified ads: `/N/vasita-atv`, `/N/emlak-turistik-tesis`, `/N/is-ilanlari-saglik`, `/ihtiyactan-satilik-...` |
| Search box | "Kelime, ilan no veya mağaza adı ile ara" — keyword, **ad number**, or shop name |
| `/arama/?s=avukat` (lawyer) | 200, but an effectively empty 20 KB result page |
| `/avukat/`, `/avukat/istanbul/` | **404** — no category-by-profession routes exist |

It is a small classified-ads portal, and Babak 42 separately proved the
classified-ads vein saturated (9 of 9 countries, 32–42 sellers each). Dead
twice over, so this actor targets Indonesia instead — the home market, and
the emptiest jurisdiction in Babak 41's own numbers.

Other live directories confirmed reachable for future jurisdictions:
`hitta.se` (SE — 2,453 hits for "advokat", 213 KB), `guiamais.com.br`
(BR, 160 KB), `pai.pt` (PT, 54 KB). `telelistas.net` serves its category
pages as **HTTP 410 Gone**, and `seccionamarilla.com.mx` times out — both
match the Babak 42 pattern of "zero competitors because the site is
unreachable", not opportunity.

## Anti-bot

**None found.** Listing and detail pages both return complete
server-rendered HTML to a plain `curl_cffi` `chrome124` request — no
challenge, no cookie jar, no warmup, no login. TLS impersonation and the
retry/block-detection scaffolding are kept per portfolio convention.

## Route map

| Purpose | Route |
|---|---|
| Category listing | `/category/<slug>` |
| Page N | `/category/<slug>/<N>` |
| City-scoped | `/category/<slug>/city:<City>` (the colon is literal) |
| City-scoped page N | `/category/<slug>/city:<City>/<N>` |
| Business detail | `/company/<id>/<name_slug>` |

Nine top-level categories are linked from the homepage; sub-category slugs
(`italian`, `japanese`, `indian`, `creole`, …) work on the same route.

## Pagination — two traps, both verified live

1. **`?page=N` is silently ignored.** `/category/restaurants?page=2`
   returns 200 and re-serves **page 1** (identical first two companies as
   the unpaged URL). Pagination must go in the path.
2. **A page past the end clamps back to page 1.**
   `/category/restaurants/99999` also returns 200 with page 1's companies —
   it never 404s and never returns an empty list.

Either trap alone would make a naive loop run forever, so the client stops
on three signals: no cards, a short page (< 20), **or a page whose
`data-cmpid`s were all seen already**. The third is the one that actually
catches the clamp.

Confirmed working: `/category/restaurants/2` → different companies
("Dapur Solo", "Martabak Martabux" vs "Spaccanapoli di Ubud", "LOONG 大
GE"); `/category/restaurants/city:Jakarta/2` likewise.

## Parsing

**Listing cards** — `div.company[data-cmpid]` carries the stable business
ID. Name and URL come from `div.company_header h3 a`, address from
`div.address` (city is the `<b>` inside it). Rating, "N Reviews", "+13
Years with us", "2012 Established" and "4 Photos" are plain text and are
read with narrow regexes.

The phone needs care: it sits in a `div.s` block, but **the same block
shape is reused** for "2012 Established", "E-mail", "Map", "Website" and
"N Photos". The icon's `aria-label="Phone number"` is what identifies the
right one — matching on block position or order would pick up the wrong
value.

**Detail pages** — schema.org `LocalBusiness` JSON-LD gives name, postal
address, telephone, website URL, `geo.latitude`/`longitude` and
`aggregateRating`. Everything the JSON-LD omits (mobile phone, working
hours, manager, establishment year, employee band, description, category
list) comes from `div.info` label/value blocks, keyed by their `div.label`
text. The label text repeats inside the block's own text and is stripped
off the value.

## Field coverage (25-card sample, /category/restaurants)

| Field | Coverage |
|---|---|
| name, profileUrl, address, phone, establishedYear | 25 / 25 |
| city | 24 / 25 |
| rating, reviewCount | 3 / 25 — most listings have no reviews |

## Known upstream quirks

- E-mail addresses are never published; the page renders a "Send Enquiry"
  button behind a sign-in link instead. `hasEmail` is emitted as a flag and
  no address is fabricated.
- The company slug in `/company/<id>/<slug>` is cosmetic — upstream
  resolves on the numeric ID alone, so a bare ID is accepted as input.
- City facet lists are rendered per category, so `reference` mode reads
  them from the largest category (restaurants) to get the widest list.
