# Blibli Best Sellers Tracker

Memantau daftar **"Paling Laris"** [Blibli](https://www.blibli.com) per kategori
dan melaporkan produk mana yang **masuk, naik, turun, tetap, atau keluar** dari
daftar dibanding run sebelumnya.

Dibuat untuk penjual: mengetahui siapa yang menguasai kategori Anda, kapan
pesaing baru menyusup ke daftar, dan kapan produk Anda sendiri tergeser.

## Kenapa actor ini tidak sekadar mengurutkan "terlaris"

Ini bagian terpenting untuk dipahami sebelum memakainya.

Mengurutkan kategori berdasarkan jumlah terjual **tidak** menghasilkan daftar
"Paling Laris" Blibli. Pada kategori Memory Card:

| Peringkat resmi | Terjual |
| --- | --- |
| #1 | 1.899 |
| #2 | 4.178 |
| #3 | 315 |
| #8 | 4.262 |

Produk peringkat 1 terjual jauh lebih sedikit daripada peringkat 8, dan tiga
produk dengan penjualan tertinggi di kategori itu justru tidak berperingkat sama
sekali. Blibli memakai perhitungannya sendiri.

Peringkat resmi hanya tersedia di halaman masing-masing produk, pada
`statistics.bestSelling.rank` — angka yang sama yang memunculkan lencana
*"No. 2 terlaris di Memory Card"*. Actor ini membaca angka itu, bukan menebaknya
dari jumlah terjual.

Konsekuensinya: untuk menyusun daftar sebuah kategori, actor memindai sejumlah
produk terlaris di kategori tersebut lalu membaca peringkat resmi tiap produk.

## Kelengkapan daftar — dan cara actor membuktikannya

Peringkat Blibli berupa deret rapat 1, 2, 3, …, N. Kalau hasil pindai punya
peringkat 1, 2, 4, berarti pemegang peringkat 3 berada di luar jangkauan
pemindaian — bukan berarti peringkat 3 tidak ada.

Actor memeriksa hal ini sendiri dan melaporkannya:

- `leaderboardComplete` — `true` kalau peringkat 1..N rapat tanpa celah
- `leaderboardSize` — jumlah produk dalam daftar
- `candidatesScanned` / `candidatesFailed` — seberapa dalam pemindaian, dan
  berapa yang gagal diambil

Kalau ada celah **dan** ada kandidat yang gagal diambil, log akan menyebutkan
bahwa penyebabnya mungkin jaringan, bukan kedalaman — dua masalah dengan solusi
berbeda.

### Memilih kedalaman

Dari pengujian:

| Kategori | Kedalaman 100 | Kedalaman 300 |
| --- | --- | --- |
| Memory Card (ME-1000006) | lengkap, 11 produk | lengkap, 11 produk |
| Gaming Laptop (GA-1000002) | **bolong** (rank 15, 16 hilang) | lengkap, 21 produk |
| SSD (SS-1000001) | kosong | kosong |

Default `candidatesPerCategory` adalah **300**. Turunkan untuk hemat, naikkan
kalau `leaderboardComplete` masih `false`.

**Tidak semua kategori punya daftar "Paling Laris".** SSD tidak punya satu pun
produk berperingkat bahkan pada kedalaman 300. Actor melaporkannya apa adanya
alih-alih mengarang daftar dari urutan terjual.

## Pelacakan antar-run

Dengan `trackChanges` aktif (default), actor menyimpan snapshot ke key-value
store bernama dan membandingkannya di run berikutnya. Tiap baris hasil membawa:

| Status | Arti |
| --- | --- |
| `BASELINE` | Run pertama, belum ada pembanding |
| `NEW` | **Masuk** daftar sejak run lalu |
| `UP` / `DOWN` | Naik/turun peringkat (`rankChange`, positif = naik) |
| `SAME` | Peringkat tidak berubah |
| `DROPPED_OUT` | **Keluar** dari daftar — `rank` kosong, `previousRank` terisi |

Produk yang keluar tetap dikeluarkan sebagai baris tersendiri. Bagi penjual,
justru itu kabar yang paling perlu diketahui, dan baris itu akan lenyap tanpa
jejak kalau hanya daftar terbaru yang dilaporkan.

Jadwalkan lewat Apify Scheduler dengan input yang sama; `stateStoreName` yang
sama membuat run-run itu saling menyambung.

## Input

| Field | Keterangan |
| --- | --- |
| `categories` | URL atau kode kategori, mis. `["ME-1000006"]` |
| `discoverCategories` | Telusuri sendiri pohon kategori Blibli |
| `rootCategories` | Titik awal penelusuran; kosong = seluruh 14 kategori utama |
| `categoryLevel` | Kedalaman kategori target (default `3`) |
| `maxCategories` | Pembatas biaya (default `10`) |
| `candidatesPerCategory` | Kedalaman pemindaian (default `300`) |
| `trackChanges` | Bandingkan dengan run sebelumnya (default `true`) |
| `stateStoreName` | Key-value store untuk snapshot |
| `watchMerchantCodes` | Tandai `isWatched=true` untuk kode penjual ini |
| `maxConcurrency` | Permintaan paralel (default `10`) |
| `proxyConfiguration` | Disarankan proxy residensial Indonesia |

### Mencari kode kategori

Buka kategori di Blibli dan salin URL-nya — actor mengambil kodenya sendiri.
Daftar "Paling Laris" ada di kategori level 3, mis.
`https://www.blibli.com/c3/memory-card/ME-1000006`.

## Contoh keluaran

```json
{
  "rank": 2,
  "status": "DOWN",
  "previousRank": 1,
  "rankChange": -1,
  "productSku": "BLL-70058-00122",
  "name": "SanDisk Ultra microSDXC 64GB C10 UHS-I Card 100MB/s",
  "brand": "SanDisk",
  "salePrice": 259000,
  "listPrice": 299000,
  "discountPercentage": 13,
  "rating": 4.8,
  "reviewCount": 465,
  "stockQuantity": 97,
  "soldCount": 4178,
  "merchantCode": "BLL-70058",
  "merchantName": "Blibli (Laptop - Acc) Flagship Store",
  "isWatched": false,
  "categoryCode": "ME-1000006",
  "categoryName": "Memory Card",
  "leaderboardSize": 11,
  "leaderboardComplete": true,
  "candidatesScanned": 300,
  "candidatesFailed": 0,
  "previousRunAt": "2026-08-30T00:00:00.000Z",
  "runStartedAt": "2026-08-31T04:12:00.000Z"
}
```

Ringkasan per kategori juga disimpan di key-value store run sebagai
`RUN_SUMMARY`, termasuk daftar peringkat yang hilang bila ada.

## Harga

Actor ini ditagih **per kategori yang dipantau**, bukan per baris hasil:

| Item | Tarif |
| --- | --- |
| Memulai run | $0,05 |
| Tiap kategori yang menghasilkan daftar | $1,00 |

Alasannya jujur saja: satu kategori berarti ratusan permintaan halaman produk
tapi hanya belasan baris hasil. Menagih per baris akan membuat actor ini salah
harga secara serius — biaya nyatanya sekitar $0,06 per baris, dua puluh kali
lipat tarif per-hasil yang lazim di Apify Store.

**Kategori tanpa daftar "Paling Laris" tidak ditagih.** Blibli memang punya
kategori seperti itu (SSD salah satunya), dan Anda tidak seharusnya membayar
untuk jawaban kosong — meski memindainya tetap memakan permintaan.

Batas biaya maksimum run yang Anda pasang di Console juga dihormati sejak awal:
kalau anggaran hanya menutup 3 kategori, actor memindai 3 kategori, bukan
memindai 10 lalu gagal menagih.

### Biaya sumber daya

Satu kategori pada kedalaman 300 memerlukan sekitar 303 permintaan (3 halaman
daftar + 300 halaman produk). Sepuluh kategori berarti sekitar 3.000 permintaan.

`maxCategories` ada khusus supaya penelusuran otomatis tidak diam-diam
membengkak — 14 kategori utama Blibli bercabang menjadi ratusan kategori level 3.

Actor berjalan pada 1 GB memori secara default (puncak pemakaian nyata sekitar
200 MB), jadi biaya compute tetap rendah.

## Catatan teknis

Actor memakai API pencarian internal Blibli dan state JSON yang ditanam di
halaman produk, bukan browser headless. Blibli menolak permintaan yang headernya
tidak konsisten dengan XHR browser sungguhan, jadi profil header dikunci ke satu
identitas Chrome desktop.

### Soal proxy

Pemblokiran Blibli bertumpu pada header, bukan IP — tapi jenis proxy tetap
berpengaruh besar pada seberapa lengkap daftar yang terkumpul. Pengujian pada
kategori yang sama, kedalaman 300:

| Jalur | Daftar terkumpul | Kandidat gagal | Waktu |
| --- | --- | --- | --- |
| Tanpa proxy (IP Indonesia) | 11 dari 11 | 0 | 12 detik |
| Proxy residensial ID | 11 dari 11 | 1 | 4m 51s |
| Proxy datacenter | 6 dari 11 | banyak | 2m 52s |

Proxy datacenter jelas paling banyak ditolak — hindari. Residensial adalah
default yang disarankan.

Pengujian ulang di cloud (September 2026): IP datacenter Apify **selalu** 403,
sedangkan proxy residensial ditolak secara acak per IP. Residensial Indonesia
sempat gagal 9 kali berturut-turut pada satu run, sementara residensial tanpa
negara lebih jarang ditolak — karena itu default-nya kini residensial tanpa
negara. Permintaan daftar kandidat diberi jatah 20 kali ganti IP, karena
gagalnya halaman kandidat pertama berarti seluruh kategori hilang.

Actor juga berhenti sendiri dengan rapi sebelum timeout run (atau setelah
`maxRunSeconds` bila diisi) dan tetap menyimpan hasil yang sudah terkumpul,
sehingga run yang panjang tidak berakhir tanpa data. Tetap perhatikan `leaderboardComplete`: kalau masih
`false` sementara `candidatesFailed` besar, turunkan `maxConcurrency` lalu
jalankan ulang.

Actor sengaja memberi sesi toleransi beberapa kesalahan sebelum membuangnya —
lewat proxy berputar, tiap IP baru harus melewati pemeriksaan awal lagi,
sehingga membuang sesi terlalu cepat justru memperbanyak kegagalan.

## Pengembangan lokal

```bash
npm install
npm test          # tes unit untuk parsing, penyusunan, dan perbandingan daftar
apify run
```
