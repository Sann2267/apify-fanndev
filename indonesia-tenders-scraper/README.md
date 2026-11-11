# Indonesia Government Tenders Scraper

Extracts public tender records from Indonesia's national tender search,
SPSE Nasional, run by LKPP (the National Public Procurement Agency). It
aggregates public procurement notices across all ~600+ regional and agency
LPSE (electronic procurement service) portals nationwide, from one host.

## Why use this actor

- No account, login, or API key required — every record here is public
  government procurement data.
- One national search instead of chasing 600+ independent regional/agency
  LPSE portals individually.
- Real budget-ceiling and, once awarded, real signed contract values in
  rupiah — not placeholder text.
- Browse by fiscal year, category, procuring agency, or winning contractor
  name, or fetch full announcement detail for tenders you already have the
  code for.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## How it works

1. Choose **List** mode to browse the national "Cari Paket" (search
   package) table for a chosen fiscal year, optionally filtered by category,
   agency, or winning contractor name — or **Detail** mode to fetch one or
   more specific tenders you already know the code for.
2. The actor pulls each record from SPSE Nasional's own search and
   announcement-page endpoints — the same data the public search page
   itself displays.
3. Detail records include procuring agency, budget ceiling, work location,
   contract type, qualification requirements, and participant count.
4. Automatic session refresh and retries handle temporary hiccups, so you
   don't have to babysit failed requests.

## Input

**List mode** — browse tenders for a fiscal year:

```json
{
  "mode": "list",
  "tahunAnggaran": 2026,
  "kategoriId": "",
  "instansiId": "",
  "rekanan": "",
  "maxResults": 25,
  "fetchDetail": false,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"], "apifyProxyCountry": "ID" }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `tahunAnggaran` | integer | Fiscal year ("Tahun Anggaran") to browse. Defaults to the current year. Multi-year contracts appear under every year they span. |
| `kategoriId` | string | Optional category filter (goods / construction / consulting / other services). Leave blank for all. |
| `instansiId` | string | Optional filter by a specific procuring agency's SPSE ID (e.g. `L4` for BKKBN). Leave blank for all agencies. |
| `rekanan` | string | Optional filter by winning contractor/company name — a genuine full-text search on the source's own "Nama Pemenang Berkontrak" field. Leave blank for all. |
| `maxResults` | integer | Caps how many tenders this run returns. |
| `fetchDetail` | boolean | When `true`, enriches each list row with the full announcement-page fields (one extra request per row — slower). |
| `proxyConfiguration` | object | Apify Proxy settings. Residential + Indonesia (`apifyProxyCountry: "ID"`) is required, not just recommended — see Notes below. |

Note: the source's own tender-title search box does not actually filter
anything server-side (confirmed during testing — see
`CRAWLING_METHOD.md`), so this actor does not expose a fake keyword-search
field for it. `rekanan`/`kategoriId`/`instansiId` are the filters that are
genuinely functional upstream.

**Detail mode** — fetch specific tenders by code:

```json
{
  "mode": "detail",
  "kode": "10051479000",
  "kodes": [],
  "maxConcurrency": 2,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"], "apifyProxyCountry": "ID" }
}
```

| Field | Type | Description |
|---|---|---|
| `kode` | string | A single tender's code (find one from a "list" mode run's `kode` field). |
| `kodes` | array | Multiple tender codes to fetch in one run. |
| `maxConcurrency` | integer | How many tenders to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run
(`tahunAnggaran: 2026`):

```json
{
  "_input": "list:tahun=2026",
  "_source": "S1-dt-lelang",
  "_scrapedAt": "2026-08-27T07:07:52Z",
  "kode": "10045257000",
  "namaPaket": "PEMBANGUNAN GEDUNG TEKNIK LISTRIK DAN ENERGI TERBARUKAN",
  "statusBadges": [],
  "instansi": "Kementerian Pendidikan Tinggi, Sains, dan Teknologi",
  "tahapanSaatIni": "Tender Sudah Selesai",
  "nilaiHPS": "36,9 M",
  "metodeKualifikasi": "Pascakualifikasi Satu File",
  "jenis": "Tender",
  "metodeEvaluasi": "Harga Terendah Sistem Gugur",
  "jenisPengadaan": "Pekerjaan Konstruksi",
  "tahunAnggaran": [2025, 2026],
  "nilaiKontrak": null,
  "kontrakSudahDibuat": false
}
```

Real sample from a **detail** run (`10051479000`, a completed Universitas
Sriwijaya building tender — `syaratKualifikasi` truncated, the full record
includes the complete qualification-requirements text):

```json
{
  "_input": "10051479000",
  "_source": "S1-pengumumanlelang-detail",
  "_scrapedAt": "2026-08-27T07:08:15Z",
  "kode": "10051479000",
  "kodeTender": "10051479000",
  "namaTender": "Pembangunan Gedung Kuliah Fakultas Kesehatan Masyarakat Universitas Sriwijaya",
  "rencanaUmumPengadaan": [
    {
      "kodeRup": "59596096",
      "namaPaket": "Pekerjaan Konstruksi Pembangunan Gedung Kuliah Fakultas Kesehatan Masyarakat Universitas Sriwijaya",
      "sumberDana": "APBN"
    }
  ],
  "tanggalPembuatan": "25 Juni 2025",
  "tahapTenderSaatIni": "Tender Sudah Selesai [/nasional/lelang/10051479000/jadwal]",
  "instansi": "Kementerian Pendidikan Tinggi, Sains, dan Teknologi",
  "satuanKerja": "DIREKTORAT SUMBER DAYA",
  "jenisPengadaan": "Pekerjaan Konstruksi",
  "metodePengadaan": "Tender - Pascakualifikasi Satu File - Harga Terendah Sistem Gugur",
  "khususOrangAsliPapua": "Tidak",
  "tahunAnggaranRaw": "APBN 2025 APBN 2026",
  "nilaiPaguPaket": "Rp. 44.093.831.000,00",
  "nilaiHpsPaket": "Rp. 30.802.271.000,00",
  "jenisKontrak": "Harga Satuan",
  "lokasiPekerjaan": ["Jalan Srijaya Negara, Bukit Lama, Kec. Ilir Barat I, Kota Palembang, Sumater Selatan (30139) - Palembang (Kota)"],
  "kualifikasiUsaha": "Menengah",
  "syaratKualifikasi": "Persyaratan Kualifikasi Administrasi/Legalitas Memenuhi ketentuan peraturan perundang-undangan untuk menjalankan kegiatan/usaha. ... (full text in the real record)",
  "pesertaTender": "62 peserta",
  "tahunAnggaran": [2025, 2026]
}
```

| Field | Type | Description |
|---|---|---|
| `kode` | string | Stable code for this tender. |
| `namaPaket` / `namaTender` | string | The tender's title. |
| `instansi` / `satuanKerja` | string | The government agency and specific work unit running this tender. |
| `nilaiHPS` / `nilaiPaguPaket` / `nilaiHpsPaket` | string | Budget ceiling — abbreviated on list rows, full rupiah on detail rows. |
| `nilaiKontrak` / `kontrakSudahDibuat` | string / boolean | The signed contract's value once awarded, and whether it's been made yet. |
| `tahunAnggaran` | array | Fiscal year(s) this tender's contract spans. |
| `lokasiPekerjaan` | array | Work location(s). |
| `kualifikasiUsaha` / `syaratKualifikasi` | string | Business size tier required, and the full qualification requirements text. |
| `pesertaTender` | string | How many bidders participated (individual bidder identities are anonymized by the source itself until an award is made). |
| `_error` | string | Present only when a record couldn't be retrieved (`not_found` for an unknown tender code). |

A list row fetched with `fetchDetail: true` has the same additional fields
as a detail record, merged onto it.

## Notes

- This actor covers Indonesia's national tender search (SPSE Nasional,
  `spse.inaproc.id/nasional`) — the public aggregator across all regional
  and agency LPSE portals, not any single agency's own portal.
- List mode returns however many tenders genuinely match your filters —
  fewer than `maxResults` simply means fewer tenders currently exist for
  that year/keyword; nothing is padded.
- The fiscal year filter defaults to the current year; multi-year
  construction contracts appear under every budget year they touch, so
  browsing a future year can still surface active current tenders.
- Residential proxies pinned to Indonesia (`apifyProxyCountry: "ID"`, set
  by default) are required, not just recommended — the source's Cloudflare
  configuration was confirmed to block non-Indonesian residential/datacenter
  exit IPs with a 403, even with a clean browser TLS fingerprint.

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ghana
(GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Nigeria (NOCOPO), Bangladesh
(CPTU/BPPA), Pakistan (PPRA-EPMS), Vietnam (VNEPS), Sri Lanka (Treasury),
Zimbabwe (PRAZ), Liberia (PPCC), Madagascar (ARMP), Cameroon (ARMP), and
several more.
