# Publikasi & Harga — Blibli Product & Price Monitor

Langkah yang harus dilakukan di Apify Console. Actor ini **tidak memerlukan
perubahan kode** untuk penagihan — kedua event-nya ditagih platform otomatis.

Actor: https://console.apify.com/actors/OqSXL0fZDcNKFa0MB

## 1. Verifikasi identitas (KYC)

Wajib sebelum actor berbayar bisa aktif. Console → **Settings → Billing** →
lengkapi verifikasi identitas dan data payout.

Tanpa ini, harga tidak bisa disimpan.

## 2. Publikasikan ke Apify Store

Console → actor → tab **Publication**.

- **Categories**: `ECOMMERCE` (kompetitor sejenis memakai kombinasi
  `ECOMMERCE` + `AUTOMATION`, atau `ECOMMERCE` + `LEAD_GENERATION`)
- **Title** dan **Description** sudah terisi dari `.actor/actor.json`
- README sudah siap-publikasi

Tekan **Publish to Store**.

## 3. Pasang harga pay-per-event

Console → actor → tab **Monetization** → pilih **Pay per event**.

Buat **tepat dua** event berikut:

| Nama event | Judul | Harga |
| --- | --- | --- |
| `apify-actor-start` | Actor Start | **$0,05** |
| `apify-default-dataset-item` | Result | **$0,01** |

Keduanya adalah event sintetis bawaan Apify: platform menagihnya otomatis —
`apify-actor-start` saat run dimulai, `apify-default-dataset-item` setiap kali
actor menulis satu baris ke dataset. **Tidak ada kode yang perlu ditambahkan**,
dan `apify-actor-start` justru dilarang ditagih dari kode.

## 4. Dasar penetapan harga

Diukur dari run nyata: 29 baris hasil dengan biaya $0,095 — sekitar **$0,0033
per baris**. Harga $0,01 per hasil memberi margin sekitar 3x.

Pembanding di Apify Store:

| Actor | Harga |
| --- | --- |
| easyapi/tokopedia-product-scraper | $0,09 start + $0,00499/hasil |
| xtracto/shopee-scraper (2.418 user) | $0,05 start + per-hasil |
| shahidirfan/tokopedia-search-scraper | $0,00005 start + $0,001/hasil |

Actor ini duduk di kelas atas rentang tersebut. Yang membedakannya: satu
permintaan mengambil 100 produk sekaligus tanpa browser headless, dan mode
detail memberi jumlah stok pasti serta deteksi selisih harga antara hasil
pencarian dan halaman produk — hal yang tidak diberikan scraper sejenis.

Kalau ingin mengejar volume pengguna lebih dulu, $0,005 per hasil masih
menyisakan margin sekitar 1,5x.

## 5. Setelah terbit

Uji dengan akun lain untuk memastikan tagihan muncul benar pada run pertama.
Periksa tab **Runs** → sebuah run → **Charges**.
