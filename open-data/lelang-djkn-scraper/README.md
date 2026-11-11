# Indonesia Government Auction (Lelang DJKN) Scraper

Extract live property, vehicle and asset auction lots from **lelang.go.id** — the official state auction portal of DJKN (Direktorat Jenderal Kekayaan Negara, Indonesia's Ministry of Finance). No account, login, or API key needed.

## Why use this actor

- **The whole national auction catalogue in one place** — ~11,900 live lots at the time of writing: land, houses, shophouses, factories, hotels, cars, motorcycles, ships, machinery and small-business (UMKM) assets
- **Real money fields, not just listings** — reserve price (`nilaiLimit`), required deposit (`uangJaminan`), deposit deadline, auction open/close schedule and bidding method for every lot
- **Full lot detail** including the underlying items, their ownership documents (title deed / BPKB numbers and dates), specifications and photos
- **Geographic targeting** across all 71 KPKNL auction offices, each with its province and city
- **Free-text search and category filters** — find "toyota", or every `Rumah` + `Apartemen` lot nationwide
- **Ready-made feeds** for lots that are hot, ending soon, or running right now — ideal for a scheduled run that alerts you before a deposit deadline closes
- Stable JSON output for pipelines, databases or spreadsheets, with automatic retries — no scrapers or browsers to babysit

## How it works

Pick a `mode`:

1. **`catalog`** — search or browse every live lot nationwide, optionally filtered by free text and asset category.
2. **`kpknl`** — the same catalogue scoped to one or more KPKNL offices. This is how you target a region (e.g. everything handled by KPKNL Denpasar).
3. **`detail`** — full detail for specific lots, by lot ID or by pasting a lelang.go.id address.
4. **`feed`** — a curated feed: `hot`, `ending-soon`, or `live`.
5. **`reference`** — the live category list and all 71 offices with province/city, so you know exactly what to pass to the other modes.

Results are paginated automatically up to the `maxItems` you set.

## Input

**Search the catalogue:**

```json
{
  "mode": "catalog",
  "search": "toyota",
  "maxItems": 200,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Everything in one region, houses and apartments only:**

```json
{
  "mode": "kpknl",
  "office": "Denpasar",
  "categories": ["Rumah", "Apartemen"],
  "maxItems": 500
}
```

**Full detail for one lot:**

```json
{
  "mode": "detail",
  "lotId": "4e828a03-842c-4eef-8962-a0ced8041b31"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `catalog`, `kpknl`, `detail`, `feed`, or `reference`. |
| `search` | string | `catalog`/`kpknl`: free-text search over lot names. |
| `categories` | array | `catalog`/`kpknl`: one or more of Tanah, Rumah, Ruko, Pabrik, Hotel dan Villa, Mobil, Motor, Bongkaran, Kapal, Besi Tua, Elektronik, Kayu, Inventaris, UMKM, Gudang, Toko, Apartemen, Lain-lain. |
| `umkmOnly` | boolean | `catalog`: use the separate small-business (UMKM) asset catalogue. |
| `office` / `offices` | string / array | `kpknl`: office name (partial, case-insensitive, e.g. `Denpasar`) or its ID. |
| `lotId` / `lotIds` | string / array | `detail`: lot ID, or any lelang.go.id address containing one. |
| `feed` | string | `feed`: `hot`, `ending-soon`, or `live`. |
| `maxItems` | integer | Max lots per catalogue/office/feed (default 200). |
| `maxConcurrency` | integer | `detail`: how many lots to fetch in parallel (default 4). |
| `proxyConfiguration` | object | Apify Proxy settings. Optional; Residential is on by default. |

## Output

**`catalog` mode** (`search: "toyota"`) — real output, truncated:

```json
{
  "_input": "catalog:toyota",
  "_source": "S1-api",
  "_scrapedAt": "2026-09-08T06:26:40Z",
  "recordType": "LOT",
  "_namaLotLelangText": "TOYOTA INNOVA E di Kota Banda Aceh",
  "_lotUrl": "https://lelang.go.id/67051f1c-f64f-11ed-b3e2-5620a0c2ec5a/detail-auction/df522e19-9e08-4243-b2a7-b3d77edf1ad1",
  "id": "278b89fd-edc7-4198-8fd4-95e84a5fa999",
  "lotLelangId": "df522e19-9e08-4243-b2a7-b3d77edf1ad1",
  "namaLotLelang": "TOYOTA INNOVA E di Kota Banda Aceh",
  "nilaiLimit": "28041000",
  "uangJaminan": "8500000",
  "tanggalBatasJaminan": "2026-09-08T23:59:59+07:00",
  "namaLokasi": "KOTA BANDA ACEH",
  "unitKerjaId": "67051f1c-f64f-11ed-b3e2-5620a0c2ec5a",
  "namaUnitKerja": "KPKNL Banda Aceh",
  "tglMulaiLelang": "2026-09-02T00:00:00+07:00",
  "tglSelesaiLelang": "2026-09-09T15:00:00+07:00",
  "status": "TAYANG",
  "caraPenawaran": "OPEN_BIDDING",
  "photos": ["… 1 more"]
}
```

**`detail` mode** — same lot fields plus `kodeLot`, `views` and the nested items:

```json
{
  "recordType": "LOT_DETAIL",
  "_namaLotLelangText": "Toyota Short 3700 di Kota Prabumulih",
  "kodeLot": "VNR2LP",
  "nilaiLimit": "30310000",
  "uangJaminan": "30310000",
  "namaUnitKerja": "KPKNL Palembang",
  "tglSelesaiLelang": "2026-09-09T10:30:00+07:00",
  "status": "TAYANG",
  "content": {
    "barangs": [
      {
        "nama": "Toyota Short 3700",
        "buktiKepemilikan": "BPKB",
        "buktiKepemilikanNo": "5274856",
        "buktiKepemilikanTgl": "2005-11-28T00:00:00+07:00"
      }
    ]
  }
}
```

**`reference` mode** returns 18 `CATEGORY` records and 71 `KPKNL_OFFICE` records:

```json
{
  "recordType": "KPKNL_OFFICE",
  "id": "6705284a-f64f-11ed-b3e2-5620a0c2ec5a",
  "nama": "KPKNL Bukittinggi",
  "kodeSatker": "119745",
  "alamat": "Jl. Muhammad Yamin. SH., Nomor 60 Aur Kuning, Kec. Aur Birugo Tigo Baleh, Kota Bukittinggi, Sumatera Barat, 26131",
  "kota": "KOTA BUKITTINGGI",
  "propinsi": "SUMATERA BARAT",
  "telepon": "(0752) 34899"
}
```

| Field | Type | Description |
|---|---|---|
| `recordType` | string | `LOT`, `LOT_DETAIL`, `CATEGORY`, or `KPKNL_OFFICE`. |
| `_namaLotLelangText` | string | Lot name as plain text (the original `namaLotLelang` keeps its upstream formatting, which contains markup such as `m<sup>2</sup>`). |
| `_lotUrl` | string | Public lelang.go.id page for the lot. |
| `namaLotLelang` | string | Lot title as published. |
| `kodeLot` | string | Short public lot code. |
| `nilaiLimit` | string | Reserve price in IDR. |
| `uangJaminan` | string | Bid security deposit required, in IDR. |
| `tanggalBatasJaminan` | string | Deposit deadline. |
| `tglMulaiLelang` / `tglSelesaiLelang` | string | Auction open / close time. |
| `namaLokasi` | string | Asset location (regency/city). |
| `namaUnitKerja` | string | KPKNL office handling the lot. |
| `status` | string | Lot status, e.g. `TAYANG` (published). |
| `caraPenawaran` | string | Bidding method, e.g. `OPEN_BIDDING`. |
| `content.barangs` | array | `detail` only — the items in the lot with ownership documents, specs and description. |
| `photos` | array | Lot photos. |
| `views` | number | `detail` only — view counter. |
| `_error` / `_errorDetail` | string | Present only when a lot could not be fetched. |

## Notes & limits

- **Field names are Indonesian, exactly as published by the source.** They are kept unchanged so records match the portal one-to-one; the table above translates each one.
- **Live lots only.** The portal publishes lots that are open or upcoming (`status: TAYANG`); closed auctions drop out of the catalogue, so run on a schedule if you want a historical series.
- **Region filtering goes through `kpknl` mode.** Passing a province or city to `catalog` mode has no effect upstream — the actor deliberately does not offer those as inputs so you never get a silently unfiltered result.
- **Category filter is OR'ed** — `["Rumah", "Mobil"]` returns lots in either category.
- **Bidding is out of scope.** Placing bids or deposits requires a registered account on the portal; this actor only reads the public catalogue.
- Amounts are plain rupiah strings (no separators), so `"28041000"` means Rp 28,041,000.
