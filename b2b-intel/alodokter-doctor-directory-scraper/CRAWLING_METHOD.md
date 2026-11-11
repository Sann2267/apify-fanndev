# Crawling Method — Alodokter Doctor Directory Scraper

**Last verified:** 2026-09-08

## Target & jurisdiction choice

`alodokter.com/cari-dokter` — one of Indonesia's two main consumer health
platforms.

Babak 42 of `ACTOR_MARKET_RESEARCHER_NEW.md` established the candidate
("doctor directory × empty jurisdiction"): proven in Spain/LATAM
(Doctoralia, 10 sellers / 426 users), India (Practo, 9 sellers / 342 users)
and the US (25 sellers / 466 users), with **zero actors** for ID/PH/TH/VN.

### Correction to Babak 42: Halodoc is not scrapable, Alodokter is

Babak 42 named **Halodoc** as the primary Indonesian target on a "200 /
286 KB" probe. Re-checked here, that page weight is framework, not data:

| Check | Result on `halodoc.com/cari-dokter` |
|---|---|
| Rendering | Angular SPA (`main-*.js`, `_ngcontent-*` attributes) |
| Doctor data in HTML | none — the page renders *"Maaf, dokter tidak dapat ditemukan"* (no doctors found) without a location |
| `__NEXT_DATA__` / `__NUXT__` | absent |
| API host in main bundle (123 KB) | **none** — the data path lives in lazy-loaded chunks |

Alodokter, the other Indonesian target named in the same Babak, serves the
same data type **fully server-rendered with schema.org JSON-LD**, so it is
the executable one. BookingCare (VN) is Next.js with `__NEXT_DATA__` and
remains available for the same vein in another jurisdiction.

## Anti-bot

**None found.** Listing and profile pages return complete HTML to a plain
`curl_cffi` `chrome124` request — no challenge, no cookies, no login.
Retry/backoff and block detection are kept per portfolio convention.

## Route map

| Purpose | Route |
|---|---|
| Specialty listing | `/cari-dokter/<specialty>` |
| Specialty + city | `/cari-dokter/<specialty>/<city>` |
| Page N | `?page=N` (query string; `/2` as a path segment returns no list) |
| Doctor profile | `/cari-dokter/<doctor-slug>` |

Note the collision: a specialty and a doctor share the same URL space
(`/cari-dokter/dokter-anak` vs `/cari-dokter/dr-rifan-fauzie-spa-k`).

## Soft 404s — status code is not the tell

An unknown specialty slug returns **HTTP 200** with a ~17 KB shell.
Verified: `dokter-rehabilitasi-medik`, `dokter-anestesi` and
`dokter-kulit-dan-kelamin` all answered 200/17 KB with no list, while every
valid slug returned 178–337 KB. The client therefore treats a first page
under 40 KB as `NotFound`, and `reference` mode verifies all 17 shipped
slugs against the live site rather than trusting the constant.

Pagination end is clean by contrast: `?page=500` returns 200 with an
`ItemList` of **zero** items (it does not clamp back to page 1), so an
empty batch is a valid stop signal. A seen-URL guard is kept anyway.

## Parsing — JSON-LD, not selectors

Every listing page embeds a schema.org `ItemList` of `Physician` objects
carrying the entire record: name, sub-specialty, profile URL, `worksFor`
(hospital + address), `makesOffer` (consultation price + currency),
`aggregateRating` (satisfaction % + review count) and an
`additionalProperty` entry `next_schedule`. No CSS scraping is needed.

### Gotcha 1: upstream emits invalid JSON for apostrophes

A doctor named *drg. Lu'lu Ul Muhimmah* is serialised as:

```json
"name": "drg. Lu\&#39;lu Ul Muhimmah"
```

The apostrophe is JS-escaped (`\'`) **and then** HTML-encoded (`&#39;`),
leaving `\&` — not a legal JSON escape. `json.loads` raises
`Invalid \escape` and the whole `ItemList` is lost.

Impact when unhandled: the entire `dokter-gigi` specialty parsed to **zero
records** despite serving 307 KB of real content — a silent total failure
that a status-code check would never catch. `loads_lenient` retries with
`\&` → `&` and then HTML-unescapes string values. Verified: dokter-gigi now
yields 10 doctors ("drg. Febria Angelina Purwono", "drg. Willy", …).

### Gotcha 2: the same property is typed differently per page kind

`worksFor` and `makesOffer` are single objects on **listing** cards but
**lists** on **profile** pages (a doctor practising at several hospitals).
Calling `.get()` on the list form raised `AttributeError` and killed the
profile parse. Both are now funnelled through `_first_dict()` for the flat
fields, with the full list emitted separately as `hospitals` / `offers`.

## Field coverage (25-card sample, dokter-anak)

| Field | Coverage |
|---|---|
| name, profileUrl, hospital, consultationPrice, rating | 25 / 25 |
| nextSchedule | 23 / 25 |

## Known upstream quirks

- `rating` is a **percentage string** ("98%"), not a 0–5 score. Passed
  through as text rather than silently converted.
- Listing rows carry `medicalSpecialty` as the Indonesian sub-specialty
  ("Dokter Anak - Ahli Respirologi"); profile pages carry the schema.org
  term ("Pediatrics") and put the Indonesian label in `alternateName`.
  Both are emitted (`specialty`, `specialtyLabel`).
- Profile URLs carry a `sku_id` query parameter tied to a specific
  hospital/offer; it is preserved on listing rows and stripped when
  building a fetch path.
- `nextSchedule` is generated at request time and will differ between runs.
