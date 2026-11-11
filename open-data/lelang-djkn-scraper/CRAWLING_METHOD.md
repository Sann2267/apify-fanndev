# Crawling Method — Lelang DJKN Scraper

**Last verified:** 2026-09-08

## Target

`lelang.go.id` — the official e-auction portal of DJKN (Direktorat Jenderal
Kekayaan Negara), Ministry of Finance, Republic of Indonesia. Carried
**11,889 live lots** at build time across 18 asset categories and 71 KPKNL
offices.

Discovered in Babak 43 of `ACTOR_MARKET_RESEARCHER_NEW.md` as part of the
"auction/foreclosure portal per jurisdiction" vein: the data-type is proven
in four ecosystems (US 574 users, Brazil 371, Spain ~169, Germany 32) while
Indonesia, India, the Philippines, Turkey, Poland, Czechia, Romania and
Japan had **zero** actors across three independent search passes.

## Architecture decision: one multi-mode actor

The portal exposes one catalogue with several projections of the same lot
object (nationwide, per-office, per-feed) plus a detail view and two
reference tables. All are served by the same host with the same (absent)
auth and the same client, so one actor with a `mode` input beats five
actors that would duplicate the Dockerfile, retry client and proxy wiring —
the same reasoning already applied to `luma-scraper` and `civitai-scraper`.

## How the data source was found

The page is a Vite/React SPA. Its HTML is **~2 KB** and contains no trace of
any data path — `grep`ing the served HTML for `/api` returns nothing, and
the SPA answers *every* path (including deliberately wrong ones) with the
same shell and a `200`, so path guessing gives no signal at all.

The map lives in the single JS bundle (`/assets/index-<hash>.js`, ~7.5 MB),
which carries a plain config object literal:

```js
const Pa = {
  BASE_API:       "https://api-auth.lelang.go.id/api",
  LARAVEL_API:    "https://api.lelang.go.id/api",
  PERMOHONAN_API: "https://api.lelang.go.id/api",
  MASTER_DATA_SERVICE: "https://api-backoffice.lelang.go.id/api",
  ...
}
```

paired with a service map of `{ path, domain }` entries:

```js
katalogLotLelang: t => g1({ path: "/v1/landing-page/katalog-lot-lelang",
                            params: t, domain: PERMOHONAN_API })
```

**Gotcha that cost two failed attempts:** the paths in the bundle are
relative to a host string that *already ends in* `/api`. Reading only the
path list and calling `api.lelang.go.id/v1/landing-page/...` returns 404
even though the path is correct. Host and path must be joined from the
config object — never assemble one from the other by eye.

## Anti-bot

**None found.** Verified across four client configurations against the same
catalogue request — all returned an identical `200` with a 2,564-byte body:

| Client | Result |
|---|---|
| `curl_cffi` chrome + `Origin`/`Referer` | 200 |
| `curl_cffi` chrome, **no** headers | 200 |
| No TLS impersonation at all | 200 |
| Safari profile | 200 |

No cookie jar, no warmup request, and no token is needed. `curl_cffi`
`chrome124` and the `Origin`/`Referer` headers are kept anyway per
portfolio convention and because a government host may tighten later.
Retry/backoff is kept for genuine transience — one timeout was observed on
`/v1/landing-page/metadata` during recon (that path is not used by this
actor).

## Parameter behaviour (verified one at a time)

Every param below was tested individually against
`/v1/landing-page/katalog-lot-lelang` and judged by whether `totalItem`
changed from the unfiltered baseline of 11,889.

**Working:**

| Param | Evidence |
|---|---|
| `page`, `limit` | `limit` 12/50/100/200/500 all honoured; `perPage` echoed, `totalPage` recomputed (991/238/119/60/24). No cap found. Actor pages in steps of 200. |
| `search=<text>` | `toyota` → 40 of 11,889 |
| `namakategori[]=<x>` | `Rumah` → 7,671; `Rumah`+`Mobil` → 7,800 (repeatable, OR'ed) |

**Silently ignored — returns a plausible `200` with the FULL unfiltered set.**
This is the same trap this portfolio hit on Blibli, and the reason none of
these is offered as an actor input:

`katakunci` (this is the frontend's *form field* name, not the API's),
`nama`, `keyword`, `namaLotLelang`, `provinsi`, `kota`, `sortby`, `sortdir`,
`dcp`.

**Hard error:** `namakategori=Rumah` without the `[]` suffix → HTTP 400. The
array syntax is mandatory, so the client sends params as a list of pairs
rather than a dict.

Because `provinsi`/`kota` are ignored, geographic filtering is only possible
through `/v1/landing-page-kpknl/{kpknlId}/katalog-lot-lelang` — hence the
dedicated `kpknl` mode, and the `reference` mode that lists all 71 offices
with their province and city.

## Endpoints used

| Mode | Path |
|---|---|
| catalog | `/v1/landing-page/katalog-lot-lelang` (+ `/v1/landing-page-umkm/...` for UMKM) |
| kpknl | `/v1/landing-page-kpknl/{kpknlId}/katalog-lot-lelang` |
| detail | `/v1/landing-page/info/{lotLelangId}` |
| feed | `/v1/landing-page/hot-lelang`, `/lelang-segera-berakhir`, `/lelang-saat-ini` |
| reference | `/v1/landing-page/kategori`, `/v1/landing-page/kpknl` |

All relative to `https://api.lelang.go.id/api`.

`/v1/permohonan/*` (bidding, applications, document upload) requires a
signed-in account and is **out of scope** per this project's "No Login"
constraint — not wired up.

## Public lot URL

Built as `https://lelang.go.id/{unitKerjaId}/detail-auction/{lotLelangId}`,
taken from the SPA's own router table (`path: ":idKpknl/detail-auction/:lotId"`).
It was **not** validated by HTTP status, because the SPA returns 200 for any
path — a wrong URL is indistinguishable from a right one over the wire.

## Known upstream quirks

- `namaLotLelang` contains raw HTML (`"30131 m<sup>2</sup>"`). The original
  is passed through untouched; a stripped `_namaLotLelangText` is added
  alongside it.
- Money fields (`nilaiLimit`, `uangJaminan`) are **strings** of plain
  rupiah digits, not numbers.
- The catalogue only contains lots with `status: TAYANG`; closed auctions
  disappear, so historical series require scheduled runs.

## Follow-up targets (same vein, not built here)

The DJKN bundle also references the bank-run auction portals
`infolelang.bri.co.id`, `lelang.bankmandiri.co.id`, `lelangagunan.bni.co.id`
and `lelang.bankbjb.co.id` — the cheapest expansion inside the same
jurisdiction. Outside Indonesia, Babak 43 confirmed zero competitors and
open HTTP on `licytacje.komornik.pl` (PL, 1.3 MB), `bit.courts.go.jp` (JP,
343 KB), `esatis.uyap.gov.tr` (TR, 54 KB), `portaldrazeb.cz` and
`licitatii.ro`.
