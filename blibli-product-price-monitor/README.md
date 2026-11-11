# Blibli Product & Price Monitor

Mengekstrak detail produk dari [Blibli](https://www.blibli.com) berdasarkan kata kunci
atau kategori: **nama, harga, diskon, rating, jumlah ulasan, dan status stok** —
plus data penjual, jumlah terjual, dan lokasi gudang.

Dibuat untuk dua pekerjaan: menganalisis tren harga pasar dan melacak dinamika
kompetitor dari waktu ke waktu.

## Yang dihasilkan

Satu baris per produk per query:

```json
{
  "productSku": "BLL-70058-00122",
  "name": "SanDisk Ultra microSDXC 64GB C10 UHS-I Card 100MB/s",
  "brand": "SanDisk",
  "url": "https://www.blibli.com/p/sandisk-ultra-microsdxc-64gb/ps--BLL-70058-00122",
  "salePrice": 259000,
  "listPrice": 299000,
  "discountPercentage": 13,
  "discountAmount": 40000,
  "currency": "IDR",
  "rating": 4.8,
  "reviewCount": 465,
  "stockStatus": "AVAILABLE",
  "inStock": true,
  "stockQuantity": 97,
  "soldCount": 4178,
  "merchantName": "Blibli (Laptop - Acc) Flagship Store",
  "merchantBadge": "DIAMOND",
  "merchantRating": 4.9,
  "location": "Kota Jakarta Timur",
  "categoryHierarchy": ["Komputer & Gaming", "Media Penyimpanan", "Memory Card"],
  "isFreeShipping": true,
  "queryType": "search",
  "query": "memory card",
  "rankInQuery": 1,
  "scrapedAt": "2026-08-31T02:27:52.194Z"
}
```

`rankInQuery` merekam posisi produk di hasil pencarian — berguna untuk melacak
naik-turunnya peringkat kompetitor pada kata kunci yang sama antar-run.

## Input

| Field | Keterangan |
| --- | --- |
| `searchTerms` | Daftar kata kunci, mis. `["laptop gaming", "kopi arabika"]` |
| `categories` | URL kategori Blibli atau ID-nya, mis. `["https://www.blibli.com/c3/memory-card/ME-1000006"]` atau `["ME-1000006"]` |
| `maxItemsPerQuery` | Batas produk per query (default `100`) |
| `sortBy` | `relevance`, `bestSelling`, `popular`, `cheapest`, `expensive`, `newest` |
| `minPrice` / `maxPrice` | Saringan harga dalam rupiah |
| `includeOutOfStock` | Sertakan produk habis (default `true`) |
| `fetchProductDetails` | Buka tiap halaman produk untuk data lebih dalam (default `false`) |
| `maxConcurrency` | Permintaan paralel (default `8`) |
| `proxyConfiguration` | Disarankan proxy residensial Indonesia |

Kata kunci dan kategori boleh dipakai bersamaan dalam satu run.

### Mencari ID kategori

Buka kategori mana pun di Blibli dan salin URL dari address bar — actor mengambil
ID-nya sendiri. `https://www.blibli.com/c3/memory-card/ME-1000006` dan
`ME-1000006` sama-sama diterima.

## Mode detail

Dengan `fetchProductDetails: false` (default), semua data diambil dari API
pencarian Blibli — satu permintaan untuk 100 produk. Cepat dan murah.

Dengan `fetchProductDetails: true`, setiap halaman produk ikut dibuka sehingga
menambah:

- `stockQuantity` — sisa stok dalam angka, bukan sekadar tersedia/habis
- `seenCount` — berapa kali produk dilihat
- `bestSellingRank` — peringkat terlaris di sub-kategorinya
- `merchantIsOfficial`, `merchantReviewCount`, `warranty`, `uniqueSellingPoint`
- `listingSalePrice` dan `priceMovedSinceListing`

Dua field terakhir layak diperhatikan. Indeks pencarian Blibli kadang tertinggal
dari halaman produk; pada pengujian, ada produk yang tampil `Rp55.999` di hasil
pencarian tapi sebenarnya `Rp42.999` di halamannya sendiri. Actor menyimpan
kedua angka dan menandai selisihnya alih-alih diam-diam memilih salah satu.

Biayanya: satu permintaan tambahan per produk.

## Batas yang perlu diketahui

Blibli hanya melayani **20 halaman per query**, jadi maksimal **2.000 produk**
per kata kunci atau kategori — batas dari situsnya, bukan dari actor ini.
Untuk memanen kategori yang lebih besar, pecah jadi beberapa query dengan
rentang harga yang berurutan:

```json
{
  "categories": ["ME-1000006"],
  "minPrice": 0,
  "maxPrice": 100000
}
```

lalu `100000`–`250000`, dan seterusnya. Tiap rentang punya jatah 2.000 sendiri.

## Harga

| Item | Tarif |
| --- | --- |
| Memulai run | $0,05 |
| Tiap produk yang dihasilkan | $0,01 |

Anda hanya membayar baris yang benar-benar masuk ke dataset. Batas biaya
maksimum run bisa Anda pasang sendiri di Apify Console.

Actor berjalan pada 1 GB memori secara default (puncak pemakaian nyata sekitar
155 MB), jadi biaya compute platform tetap rendah. Karena actor ini tidak
memakai browser headless, satu permintaan sudah mengambil 100 produk sekaligus.

## Memantau secara berkala

Untuk analisis tren, jadwalkan actor ini di Apify Scheduler (mis. tiap pagi)
dengan input yang sama persis. Setiap run menulis dataset baru dengan
`scrapedAt`; gabungkan dataset antar-run dengan `productSku` sebagai kunci untuk
mendapat deret waktu harga, diskon, rating, dan stok per produk.

## Catatan teknis

Actor ini memakai API pencarian internal Blibli dan state JSON yang ditanam di
halaman produk, bukan browser headless. Blibli menolak permintaan yang headernya
tidak konsisten dengan XHR browser sungguhan, jadi crawler mengunci profil header
ke satu identitas Chrome desktop. Karena tanpa browser, actor ini jauh lebih
cepat dan murah dibanding pendekatan Playwright/Puppeteer.

Kalau mulai muncul kegagalan berulang, turunkan `maxConcurrency` atau aktifkan
proxy residensial.

## Pengembangan lokal

```bash
npm install
npm test                      # tes unit untuk parsing dan normalisasi
apify run                     # baca input dari storage/key_value_stores/default/INPUT.json
```
