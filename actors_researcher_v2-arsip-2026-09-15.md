# Riset Pasar Apify Store — v2 (putaran 2026-09-15)

**Tanggal riset:** 2026-09-15
**Permintaan putaran ini:** daftar actor dengan demand tinggi / stats tinggi, khususnya dua pola —
(A) *total runs banyak tapi user sedikit*, (B) *user banyak tapi saingan sedikit* — lalu **dedupe wajib**
terhadap akun [`xtracto`](https://api.apify.com/v2/store?username=xtracto) supaya tidak membangun yang sudah ada.

## Dedupe tiga lapis (snapshot hari ini)

| Lapis | Jumlah | Angka | Snapshot |
|---|---:|---|---|
| `xtracto` (akun lama, yang kamu sebut) | **218 actor** | 6.140 user · 934 u30 · 385.180 run · **218/218 PAY_PER_EVENT** | `output/xtracto-full-v5.json` |
| `fanndev` (akun push saat ini) | **83 actor** | 171 user · 85 u30 · 1.261 run · 83/83 PPE | `output/fanndev-full-v5.json` |
| Folder lokal repo ini | **228 folder** | — | `scratchpad/_dedupe_names_v5.json` |
| **Gabungan nama unik untuk dedupe** | **444** | — | `scratchpad/_dedupe_blob_v5.txt` |

`fanndev` naik dari 75 → 83 sejak 2026-09-12. Yang baru published: `amazon-customer-insights-extractor`,
`amazon-product-search-scraper`, `bluesky-scraper`, `instagram-content-scraper`, `ph-court-decisions-scraper`,
`sinta-researcher-scraper`, `socialblade-creator-analytics-scraper`, `tiktok-all-in-one-scraper`.

## Data mentah putaran ini

| File | Isi |
|---|---|
| `output/scan-v5-corpus.json` | **23.864 actor unik** — 21 kategori × 7 band user × offset 0–900 (lewat `api-search-actors.py`) |
| `output/scan-v5-domains.json` | **586 vein dikelompokkan per DOMAIN** (metode baru putaran ini, §4) |
| `output/scan-v5-veins-token.json` | 369 vein per token (metode lama, sebagai pembanding) |
| `output/scan-v5-verify.json` | 30 brand diverifikasi ulang dengan query single-token |

Skrip: `scratchpad/scan_v5.py`, `money_v5.py`, `money_v5tok.py`, `lens_v5.py`, `lens_v5b.py`, `probe_v5.py`, `probe_v5b.py`, `probe_v5c.py`.
Arsip putaran sebelumnya: `actors_researcher_v2-arsip-2026-09-12-sore.md`, `-pagi.md`, `-2026-09-07.md`, dan `ACTOR_MARKET_RESEARCHER_NEW.md` (50 babak).

---

## 1. Ringkasan eksekutif

Korpus 23.864 actor, **MRR terukur $391.999/bulan**. Dari seluruh korpus, **2.261 actor memungut ≥$5/bulan**
dan **391 memungut ≥$100** — artinya ~90% rak Apify tidak menghasilkan apa pun. Itu konteks penting untuk dua
pola yang kamu minta: keduanya menyeret banyak actor yang ramai tapi gratis.

**Tiga hal yang keluar dari putaran ini:**

1. **Pola A dan pola B tetap seperti dua putaran sebelumnya** — mereka bagus sebagai *penjelas*, buruk sebagai
   *penyaring*. Pola A menghasilkan 3 kandidat beruang dari 30 teratas; pola B menghasilkan 8 rak, 5 di antaranya
   PII/ditolak atau sudah punya. Daftar lengkapnya tetap saya tulis di §3 dan §4 karena kamu memintanya, lengkap
   dengan alasan tiap baris gugur.
2. **Perbaikan metode yang akhirnya membuat pola B berguna: vein dikelompokkan per DOMAIN, bukan per kata.**
   Putaran lalu pola B tenggelam oleh token generik (`many`, `base`, `send`, `example`). Dengan mengelompokkan
   per domain yang disebut di nama/judul/deskripsi actor, 586 vein yang keluar semuanya brand nyata. Ini yang
   memunculkan Clutch, Gelbe Seiten, Ceneo, Firmy.cz.
3. **Satu kandidat lolos sampai Pass 5b dengan permukaan terbuka lebar dan uang nyata: `clutch.co`** —
   vein **$629/bln**, 29 seller di rak tapi **hanya 3 yang memungut**, dan halaman direktori balas **2,73 MB
   berisi 166 baris provider + 72 link profil tanpa anti-bot**. Nol di `xtracto`, nol di `fanndev`, nol di folder lokal. (§6)

**Yang belum bergerak sejak 2026-09-12:** kalibrasi harga `xtracto`. Ini masih tuas terbesar di seluruh dokumen dan
biaya engineering-nya nol. **Tapi audit harga penuh yang saya jalankan hari ini (§8) membalik arah rekomendasinya** —
actor-actor `xtracto` yang punya pembeli ternyata **sudah dihargai di atas median veinnya**, dan lantai pendapatan
akun bukan $143 melainkan **$566/bulan** begitu `apify-actor-start` ikut dihitung. (§8)

---

## 2. Papan atas pasar — siapa yang benar-benar dapat uang (konteks)

Bukan daftar target (semua ini raksasa), tapi perlu dilihat supaya tahu bentuk "demand tinggi" yang sebenarnya.

| Actor | u30 | Users | Runs | MRR terukur |
|---|---:|---:|---:|---:|
| `harvestapi/linkedin-profile-search` | 6.181 | 43.084 | 7,6 jt | **$29.531** |
| `apify/instagram-scraper` | 42.527 | 393.050 | 193,8 jt | $25.291 |
| `clockworks/tiktok-scraper` | 22.384 | 284.007 | 124,3 jt | $20.854 |
| `apify/instagram-profile-scraper` | 26.600 | 216.997 | 114,5 jt | $14.006 |
| `apify/google-search-scraper` | 16.742 | 180.977 | 118,6 jt | $13.948 |
| `bebity/linkedin-jobs-scraper` | 252 | 35.559 | — | **$7.557** (FLAT $29,99) |
| `peakydev/leads-scraper` | 73 | 3.585 | — | **$7.300** (FLAT $100) |
| `webcrawlerr/dubai-property-crawler` | 11 | 994 | — | **$5.500** (FLAT $500) |

Tiga baris terakhir adalah pelajaran harga yang sama dengan `nexgenwatch` di putaran lalu: **73 pembeli menghasilkan
$7.300 karena harganya $100/bulan**, sementara `xtracto` dengan 934 pembeli menghasilkan $143. Traffic bukan
hambatannya.

---

## 3. POLA A yang kamu minta — "runs banyak, user sedikit"

Filter: `totalUsers ≥ 15` **dan** `totalRuns ≥ 100.000`, diurutkan runs-per-user, dari korpus 23.864.

| runs/user | Users | u30 | Runs | MRR | Actor | Baca |
|---:|---:|---:|---:|---:|---|---|
| 112.938 | 211 | 4 | 23,8 jt | $100 | `alien_force/facebook-scraper-pro-rental` | "rental" = model sewa, bukan niche |
| 78.672 | 32 | 3 | 2,5 jt | $36 | `canadesk/apple-app-store-plus` | App Store — 292 seller di rak |
| 75.027 | 42 | 3 | 3,2 jt | **$0** | `apify/monitoring-checker-schema` | **Infrastruktur Apify, gratis** |
| 71.139 | 16 | 1 | 1,1 jt | $0 | `apikit/upcheck` | uptime checker, gratis |
| 65.782 | 55 | 18 | 3,6 jt | $0 | `apify/s3-uploader` | infrastruktur |
| 48.544 | 19 | 1 | 0,9 jt | $20 | `canadesk/career-scraper-plus` | 1 pembeli aktif |
| 42.570 | 96 | 10 | 4,1 jt | $0 | `apify/monitoring-checker-run-status` | infrastruktur |
| 40.896 | 61 | 0 | 2,5 jt | $0 | `thescrappa/google-maps-advanced-search-scraper` | Google Maps, jenuh |
| 39.151 | 333 | 4 | 13,0 jt | $28 | `devisty/google-search` | SERP, jenuh total |
| 29.422 | 874 | 29 | 25,7 jt | **$0** | `build_matrix/company-employees-scraper` | 25 juta run, pungutan nol |
| **24.115** | **20** | 1 | 0,48 jt | **$502** | **`knagymate/hrs-reviews-scraper`** | ✅ carry-over #1 dari putaran lalu, masih berdiri |
| 21.310 | 1.078 | 1 | 23,0 jt | $50 | `muhammad_usama/Github-Apify-Linkedin-data-scraper` | LinkedIn, tutup |
| 20.273 | 1.033 | 86 | 20,9 jt | **$0** | `macrocosmos/reddit-scraper` | 21 juta run, nol pungutan |
| **15.077** | **2.099** | 32 | 31,6 jt | **$2.208** | **`making-data-meaningful/tecdoc`** | ⚠️ data berlisensi B2B — ditolak permanen |
| 15.162 | 61 | 6 | 0,9 jt | $0 | `scraped/tcgplayer-sales-history` | sudah punya `tcgplayer-price-scraper` |
| **12.244** | **2.192** | 52 | 26,8 jt | **$390** | **`novi/fast-tiktok-api`** | ⚠️ TikTok konsumen tertutup SlardarWAF; `fanndev` sudah punya `tiktok-all-in-one-scraper` |
| 11.609 | 405 | 1 | 4,7 jt | $0 | `danielmilevski9/google-maps-pins-map-ocr` | gratis |
| **3.132** | **104** | 28 | 0,73 jt | **$689** | **`zen-studio/apple-maps-scraper-pro`** | ⭐ satu-satunya kandidat *baru* dari pola ini — lihat §5 & §7 |

**Vonis pola A (putaran ketiga berturut-turut, sekarang di korpus 23.864):** dari 30 teratas, **3 punya uang nyata
dan belum tertutup** — HRS (sudah jadi carry-over), TecDoc (lisensi), dan **Apple Maps**. Sisanya infrastruktur
Apify gratis, vein jenuh, atau nol pungutan. Pola ini menemukan "actor yang dipakai terus-menerus", bukan "actor
yang dibayar" — dan dua hal itu jarang bertemu.

---

## 4. POLA B yang kamu minta — "user banyak, saingan sedikit"

**Perubahan metode:** putaran lalu pola ini dikelompokkan per *token kata* dan hasilnya nol kandidat karena
tercemar kata generik. Putaran ini dikelompokkan **per domain** yang disebut di nama/judul/deskripsi actor
(`scan-v5-domains.json`, 586 vein). Hasilnya jauh lebih bersih: semua baris di bawah adalah brand nyata.

Filter: total users ≥ 1.500 **dan** ≤8 seller di rak yang sama.

| Rak (domain) | Seller | Yang memungut | Users | u30 | Runs | MRR | $/pembeli | Dedupe | Vonis |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `realtyapi` (skip-trace) | 1 | 1 | 14.064 | 793 | 4,6 jt | **$1.645** | $2,07 | baru | ❌ **PII / skip-trace — ditolak permanen** |
| `apollo` | 8 | 4 | 17.952 | 1.778 | 3,2 jt | $478 | $0,27 | lama | ❌ PII lead-gen, $/pembeli terlalu tipis |
| `instantly` | 2 | 1 | 4.346 | 562 | 1,3 jt | $148 | $0,26 | baru | ❌ email-finder = PII |
| `threads` | 8 | 4 | 3.983 | 501 | 2,9 jt | $300 | $0,60 | **SUDAH PUNYA** | `xtracto/threads-post-detail-scraper` |
| `gmgn` | 6 | 1 | 2.094 | 58 | 0,1 jt | $24 | $0,42 | lama | ❌ monopoli 98% (mode kebohongan (b)) |
| `seek` | 6 | **0** | 2.068 | 500 | 0,06 jt | $3 | $0,01 | lama | ❌ **rak kosong karena semua gratis** (mode (a)) |
| `ozon` | 6 | 2 | 2.029 | 531 | 0,5 jt | **$397** | $0,75 | baru | 🟠 uang ada, **permukaan 403** (§7) |
| `rightmove` | 8 | 3 | 1.725 | 102 | 0,5 jt | $170 | $1,67 | lama | 🟡 sudah dibahas di riset lama |

**Vonis pola B: 1 kandidat hidup dari 8 (Ozon), dan itu pun tertutup di Pass 5.** Peningkatannya nyata dibanding
putaran lalu (0 dari 25), tapi kesimpulannya tidak berubah: **rak dengan banyak user dan sedikit seller hampir
selalu kosong karena alasan** — actornya gratis (`seek`), datanya PII (`realtyapi`, `apollo`, `instantly`), atau
satu pemain memonopoli (`gmgn`).

---

## 5. LENSA KE-3 (yang produktif) — vein beruang dengan sedikit penagih

Filter yang dipakai sejak putaran lalu: **MRR vein ≥ $60** DAN **≤3 seller yang benar-benar memungut ≥$5**,
dijalankan di 586 vein domain, lalu diverifikasi ulang per brand dengan query single-token. Ini yang melahirkan
seluruh kandidat baru putaran ini.

| Rak | MRR | Seller | Memungut | Users | u30 | $/pembeli | Incumbent teratas | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| **clutch.co** | **$629** | 29 | 3 | 9.027 | 349 | $1,72 | `curious_coder/clutch-scraper` $320 (FLAT $40) · `epctex/clutchco-scraper` $280 (FLAT $40, gagal 13,1%) | ✅ **terbuka, siap build** |
| **apple maps** | **$731** | 16 | 2 | 236 | 59 | **$12,38** | `zen-studio/apple-maps-scraper-pro` $689 (PPE, 731 rb run / 104 user) | 🟠 recon (§7) |
| **mobile.de** | $532 | 29 | 3 | 2.981 | 476 | $1,12 | `3x1t/mobile-de-scraper` $469 (**FLAT $9,99**, 1,07 jt run) | ⚠️ **sudah punya** `mobilede-listings` (u30=3) — celah produk & harga, bukan vein baru |
| **weibo** | $459 | 15 | 2 | 3.274 | — | $1,56 | `sian.agency/weibo-scraper` $426 (PPE) | 🟠 butuh cookie login (§7) |
| **ozon** | $427 | 14 | 3 | 2.221 | 578 | $0,74 | `natanielsantos/ozon-scraper` $254 · `zen-studio/ozon-scraper-pro` $134 | 🟠 403, butuh proxy RU |
| **opentable** | $343 | 19 | 2 | 838 | — | $2,96 | `memo23/opentable-reviews-cheerio` $325 (FLAT $25) | ❌ 403/404 (§7) |
| **mercari** | $243 | 36 | 3 | 940 | 126 | $1,93 | `scrapesage/mercari-japan-scraper` $155 (PPE, 3 user) | ❌ API 401 DPoP, halaman cangkang |
| **spotify — monthly listeners** | $235 | 2 | 2 | 866 | 33 | $5,61 | `augeas/spotify-monthly-listeners` $130 (FLAT **$5**) · `scrapestorm/…` $105 (FLAT $14,99) | ⚠️ **sudah punya 2 actor Spotify** yang memungut ~$0 — celah data-type (§8) |
| **carfax** | $218 | 8 | 2 | 515 | 46 | $4,75 | `lexis-solutions/carfax-com` $174 (FLAT $29) | ❌ 403 |
| **homedepot** | $206 | 32 | 3 | 2.119 | 189 | $1,09 | `jupri/homedepot` $150 (FLAT $30) | ❌ 403 Akamai |
| **bandsintown** | $176 | 9 | 1 | 170 | 34 | $5,19 | `lexis-solutions/bandsintown-scraper` $174 (FLAT $29) | ✅ terbuka (carry-over, API publik) |
| **gelbeseiten** | $173 | 30 | 3 | 941 | 53 | $3,26 | `plowdata/gelbe-seiten` $90 (FLAT $10, 401 rb run) | ✅ **terbuka** |
| **marktplaats** | $130 | 36 | 3 | 492 | 83 | $1,56 | `panjan/marktplaats` $60 (FLAT $20) | ✅ **terbuka** |
| **nobroker** | $122 | 15 | 1 | 577 | 88 | $1,38 | `ecomscrape/nobroker-property-search-scraper` $100 (FLAT $20) | 🟠 halaman cangkang |
| **ceneo** | $81 | 4 | 1 | 51 | 13 | **$6,21** | `trev0n/ceneo-scraper` $80 (FLAT $20) | ✅ **terbuka** (butuh cookie handshake) |
| **firmy.cz** | $60 | 13 | 1 | 505 | 21 | $2,87 | `jupri/firmy` $60 (FLAT $30, **1,19 jt run / 278 user**) | ✅ **terbuka** |
| **yellowpages** | $881 | 14 | 2 | 2.081 | — | $10,75 | `delicious_zebu/yellowpages-usa-…` $800 (FLAT) | ❌ 403 Cloudflare (US **dan** AU) |
| **rocketreach** | $350 | 2 | 1 | 364 | 12 | **$29,17** | `lexis-solutions/rocketreach-pr-226` $350 (FLAT $35) | ❌ PII kontak — ditolak |
| **darkweb** | $226 | 7 | 1 | 2.501 | 50 | $4,53 | `epctex/darkweb-scraper` $225 (FLAT $15) | ❌ risiko — tidak diambil |

---

## 6. Rekomendasi #1 — `clutch.co` (direktori agensi B2B)

**Kenapa ini yang teratas:** satu-satunya kandidat baru yang lolos ketiga syarat sekaligus — uang nyata
($629/bln), rak yang tidak dipungut ramai-ramai (29 seller, **3** yang memungut), dan **permukaan yang
sudah terbukti terbuka hari ini**.

**Probe langsung (chrome124 + safari17_0, 2026-09-15):**

```
GET https://clutch.co/web-developers  ->  200, 2.733.856 byte (2,73 MB)
  provider-row .................... 166
  link /profile/<slug> unik ....... 72
  "Min. project size" ............. 86
  ld+json ......................... 1 (FAQPage)
```

Tidak ada challenge, tidak ada `__NEXT_DATA__` yang perlu dipecah — datanya HTML biasa. Satu halaman kategori
= 72 profil agensi dengan ukuran proyek minimum, rate, lokasi, layanan.

**Kondisi incumbent:** `epctex/clutchco-scraper` memungut FLAT $40 dengan **gagal 13,1%** dan u30 turun ke 7;
`curious_coder/clutch-scraper` FLAT $40 dengan 8 u30. Rak 29 seller tapi 26 di antaranya memungut $0 — pesaing
nyatanya cuma dua, dan salah satunya rusak satu dari delapan run.

**Note build:**
- Sumbu datanya bukan cuma daftar agensi — yang dibayar di vein ini adalah **atribut lead**: min. project size,
  hourly rate, headcount, lokasi, layanan, klien. Itu semua ada di halaman kategori, tidak perlu masuk profil satu per satu.
- **Jangan pakai $0,002/item.** Dua pemain yang dapat uang di rak ini memungut FLAT $40. Kalau tetap PPE, pakai
  event tingkat-laporan, bukan per-baris.
- Turunan langsung dari basis kode yang sama: `goodfirms.co`, `designrush.com`, `sortlist.com` (rak sejenis,
  belum diukur putaran ini).

### Rekomendasi #2 — klaster "direktori & klasifikasi Eropa" (4 brand, satu parser)

Empat permukaan yang **lolos Pass 5b hari ini** dan tidak ada di ketiga lapis dedupe:

| Brand | Bukti permukaan terbuka | MRR rak | Incumbent |
|---|---|---:|---|
| **Gelbe Seiten** (DE) | 320 KB · 100 `data-realid` · 264 `mod-Treffer` · ld+json | $173 | `plowdata` FLAT **$10** |
| **Marktplaats** (NL) | 807 KB · `__NEXT_DATA__` 225 KB · 35 listing/halaman | $130 | `panjan` FLAT $20 |
| **Ceneo** (PL) | handshake cookie → 646 KB · **481 `cat-prod-row`** | $81 | `trev0n` FLAT $20 |
| **Firmy.cz** (CZ) | 599 KB · 15 blok ld+json · 14 link detail | $60 | `jupri` FLAT $30 |

Total rak **$444/bln**, dan tiap rak cuma punya **1–3 seller yang memungut**. Bentuk datanya sama semua
(nama · alamat · telepon · kategori · rating, atau judul · harga · lokasi · penjual), jadi **satu parser
direktori/klasifikasi → 4 actor**. Ceneo punya $/pembeli tertinggi di klaster ($6,21).

**Gotcha Ceneo yang harus masuk kode:** request pertama balas 200 tapi hanya **19 KB berisi `<meta http-equiv="refresh">`**
— itu bukan WAF, itu penanaman cookie (`sv3`, `__RequestVerificationToken`). Request kedua **dengan session yang sama**
balas 646 KB berisi data. Pakai `requests.Session`/`curl_cffi.Session`, jangan request tunggal.

---

## 7. Hasil probe permukaan — Pass 5 + Pass 5b (2026-09-15)

Semua diuji dua profil TLS (chrome124 + safari17_0). **200 bukan bukti** — kolom terakhir adalah Pass 5b.

| Target | chrome | safari | Isi sebenarnya (Pass 5b) | Vonis |
|---|---|---|---|---|
| `clutch.co/web-developers` | 200 / 2.669 KB | 200 / 2.669 KB | 166 provider-row, 72 link profil | ✅ **terbuka** |
| `marktplaats.nl/q/fiets/` | 200 / 807 KB | 200 / 807 KB | `__NEXT_DATA__` 225 KB, 35 listing | ✅ terbuka |
| `firmy.cz/?q=…` | 200 / 599 KB | 200 / 600 KB | 15 ld+json, 14 link detail | ✅ terbuka |
| `gelbeseiten.de/suche/…` | 200 / 320 KB | 200 / 320 KB | 100 `data-realid`, 264 `mod-Treffer` | ✅ terbuka |
| `ceneo.pl/;szukaj-…` | 200 / 19 KB | 200 / 19 KB | **req ke-2 sesi sama → 646 KB, 481 baris produk** | ✅ terbuka (handshake) |
| `maps.apple.com/place?q=…` | 200 / 30 KB | 200 / 30 KB | **ld+json cuma boilerplate "Apple Maps", 0 telepon, 0 place-card** | 🟠 **cangkang** |
| `cdn.apple-mapkit.com/ma/bootstrap` | **401** | 401 | 401 juga dengan Referer beta.maps / maps / developer.apple | 🟠 token ditutup |
| `open.spotify.com/artist/<id>` | 200 / 158 KB | 200 / 158 KB | **0 × "monthlyListeners", 0 accessToken, tanpa `__NEXT_DATA__`** | 🟠 cangkang |
| `open.spotify.com/api/token` | **400** | 400 | `"Usage of this endpoint is not permitted"` | 🟠 |
| `api-partner.spotify.com/pathfinder/v1/query` | **401** | 401 | `Missing/invalid/expired access token` | 🟠 |
| `jp.mercari.com/search?…` | 200 / 381 KB | 200 / 381 KB | **0 item id `m\d{11}`**, tanpa `__NEXT_DATA__` | ❌ cangkang |
| `api.mercari.jp/v2/entities:search` | 400 → **401** | 401 | `unauthorized: missing auth token` (DPoP) | ❌ |
| `nobroker.in/property/sale/…` | 200 / 47 KB | 200 / 47 KB | 1 ld+json, **1 propertyId** = cangkang | 🟠 |
| `autotrader.co.uk/car-search` | 200 / 85 KB → **6 KB** | 200 / 85 KB | fetch kedua menyusut ke 6 KB, 0 `/car-details/` | 🟠 tidak stabil |
| `m.weibo.cn/api/container/getIndex` | 200 | 200 | `{"ok":-100,…passport.weibo.com/sso/signin}` = **wajib login** | 🟠 |
| `ozon.ru/api/composer-api.bx` & `entrypoint-api.bx` | **403** | 403 | halaman blok 9 KB | ❌ |
| `homedepot.com/s/drill` | **403** | 403 | "Access Denied" (Akamai) | ❌ |
| `carfax.com/vehicle/<vin>` | **403** | 403 | — | ❌ |
| `yellowpages.com` / `.com.au` | **403** | 403 | `.com.au` = "Just a moment…" (Cloudflare) | ❌ |
| `opentable.com/s?term=…` | **403** | 200 / 2 KB | safari 200 pun isinya "Access Denied" | ❌ |
| `seloger.com/list.htm` | **403** | 404 | DataDome | ❌ |
| `judge.me/api/v1/widgets/product_review` | **401** | 401 | butuh API token toko | ❌ |

**21 probe menutup 11 kandidat dan membuka 5, dengan biaya beberapa menit.** Itu alasan Pass 5b tetap wajib:
Apple Maps, Spotify, Mercari, dan NoBroker semuanya balas **200 dengan halaman besar** dan tidak satu pun memuat
data yang dicari.

---

## 8. Audit harga `xtracto` — tiga koreksi terhadap putaran-putaran sebelumnya

> Bagian ini ditulis ulang **2026-09-15 setelah audit `currentPricingInfo` seluruh 218 actor**
> (`output/xtracto-price-audit.json`, skrip `scratchpad/price_audit.py` + `price_bench.py`).
> Tiga klaim dari putaran sebelumnya — termasuk yang saya tulis di draf pertama dokumen ini — **salah**.

### Koreksi 1 — model uang tidak pernah menghitung `apify-actor-start`

Setiap actor `xtracto` memungut **dua** event: `apify-default-dataset-item` (per item) **dan**
`apify-actor-start` (sekali per run, $0,0005–$0,05). Model Babak 50, v2 pagi, v2 sore, dan draf pertama dokumen ini
hanya menghitung event primer. Padahal dari **44.984 run sukses/30 hari**, actor-start sendiri = **$418,05/bulan**.

| Skenario | Dataset-item | Actor-start | Total | Setelah margin Apify 20% |
|---|---:|---:|---:|---:|
| Lantai (1 item/run) | $148,36 | $418,05 | **$566,40** | $453 |
| 5 item/run | $741,80 | $418,05 | $1.160 | $928 |
| 10 item/run | $1.483,60 | $418,05 | $1.902 | $1.521 |
| 20 item/run | $2.967,20 | $418,05 | $3.385 | $2.708 |
| 50 item/run | $7.418,00 | $418,05 | $7.836 | $6.269 |

**Angka "$131,89" (v2 sore) dan "$143,23" (draf pertama hari ini) adalah lantai yang salah hitung, bukan pendapatan.**
Yang benar-benar tidak diketahui tinggal **satu** variabel: rata-rata item per run. Itu satu angka di Console.

### Koreksi 2 — actor yang punya pembeli TIDAK underpriced

Klaim "naikkan dari $0,002 ke p90 Store $0,012" **tidak berlaku untuk actor yang dimaksud**. Median $0,002 itu
median seluruh 218 actor, yang ditarik ke bawah oleh ~150 actor tanpa pembeli. Harga actor yang benar-benar dipakai:

| Actor | u30 | Harga/item sekarang | Median vein | Posisi |
|---|---:|---:|---:|---|
| `shopee-search` | 217 | **$0,005** | $0,00399 | 12 dari 21 pesaing lebih murah — **di atas median** |
| `shopee-scraper` | 153 | $0,005 | $0,00399 | di atas median |
| `shopee-shop-scraper` | 66 | $0,005 | $0,00399 | di atas median |
| `shopee-product-detail` | 22 | **$0,015** | $0,00399 (p90 $0,01) | **di atas p90 vein** |
| `ebay-sold-comps-scraper` | 16 | **$0,02** | $0,003 (p90 $0,01125) | **74 dari 80 pesaing lebih murah** |
| `aliexpress-product-scraper` | 12 | $0,01 | $0,002 | di p90 vein |
| `alibaba-product-scraper` | 16 | $0,003 | $0,002 | sedikit di atas median |
| **`tiktok-trending-scraper`** | **37** | **$0,00075** | **$0,002** | ⬅️ **2,7× di bawah median — ini yang underpriced** |
| **`threads-post-detail-scraper`** | **14** | **$0,00099** | **$0,003** | ⬅️ **3× di bawah median** |
| `skyscanner-scraper` | 12 | $0,002 | $0,001 | di atas median (tapi actor gagal 40,6%) |

Jadi tuasnya bukan "naikkan harga semua". Yang underpriced cuma **dua actor**, dan dua actor lain
(`ebay-sold-comps`, `shopee-product-detail`) justru **kemahalan relatif terhadap veinnya**.

### Koreksi 3 — pertanyaan sebenarnya adalah PPE vs FLAT, bukan besar-kecil harga item

`shopee-search` punya **217 pembeli aktif/bulan**. Pesaing FLAT di vein yang sama memungut $19–$40/bulan.

| Actor | u30 | FLAT $19 · retensi 100% | retensi 25% | retensi 10% |
|---|---:|---:|---:|---:|
| `shopee-search` | 217 | $4.123 | $1.031 | $412 |
| `shopee-scraper` | 153 | $2.907 | $727 | $291 |
| `shopee-shop-scraper` | 66 | $1.254 | $314 | $125 |

Bahkan pada retensi 10%, tiga actor ini = **$828/bulan** — di atas lantai seluruh akun. Tapi **jangan eksekusi ini
sebelum Koreksi 1 diukur**: kalau ternyata rata-rata 20 item/run, PPE sekarang sudah menghasilkan ~$2.700 bersih dan
pindah ke FLAT justru merusaknya. Aturan lama tetap berlaku — **tidak ada klaim "FLAT menang" yang sah sebelum faktor
item/run diukur.**

### Dua celah produk (terpisah dari harga)

Dua rak di §5 ditandai ⚠️ karena **kamu sudah punya actornya**, dan justru itu temuannya:

| Rak | Milik kamu | Hasilnya | Pesaing | Hasil pesaing |
|---|---|---|---|---|
| **mobile.de** | `xtracto/mobilede-listings` | 11 user · u30 3 · 168 run | `3x1t/mobile-de-scraper` | **$469/bln** — FLAT **$9,99**, 1,07 jt run, gagal 0% |
| **Spotify** | `xtracto/spotify-scraper` (u30 3) + `spotify-play-count-scraper` (u30 0) | ~$0 | `augeas/spotify-monthly-listeners` | **$130/bln** — FLAT **$5**, 661 user, 321 rb run |

Perhatikan harga pesaingnya: **$9,99 dan $5** — bukan $50. Mereka tidak menang karena mahal, mereka menang karena
**memungut sama sekali** dan karena **data-type-nya yang dicari orang** (monthly listeners, bukan metadata track).
Ini celah **produk**, bukan celah harga.

Status akun hari ini: `xtracto` **218/218 PAY_PER_EVENT**, 934 pembeli aktif, 44.984 run sukses/30 hari,
lantai pendapatan **$566,40/bulan** (lihat Koreksi 1). Sebaran harga/item sendiri: median $0,002 · p25 $0,00099 ·
p75 $0,01 · rentang $0,00001–$0,08. Pembanding Store: PPE median $0,002 · p75 $0,004 · p90 $0,01199;
FLAT median **$19** (p25 $9,99 · p75 $25). `fanndev`: 83/83 PPE.

---

## 9. Status carry-over

| Kandidat | Prioritas sebelumnya | Angka hari ini | Status baru |
|---|---|---|---|
| **Kalibrasi harga `xtracto`** | 🔴 #1 non-build | Belum ada perubahan: 218/218 PPE @ $0,002, $143,23/bln, $0,153/pembeli | 🔴 **Tetap #1. Belum dikerjakan.** |
| **Klaster event langsung** (Bandsintown/Songkick/Dice.fm/RA/Shotgun) | 🔴 #2 build | Bandsintown rak $176, **1 dari 9 seller memungut**, $5,19/pembeli. Songkick turun jadi $31. Dice.fm $203 (satu actor `lexis-solutions`) | 🟡 **Turun ke #3.** Permukaan tetap terbuka, tapi uang rak menyusut — Songkick praktis nol |
| **Cluster review perjalanan `knagymate`** (HRS/Zoover/Despegar/Trip.com) | 🔴 #2 | HRS naik $499 → **$502**, rpu 24.115. Zoover $192 dari **2 user**. Tetap belum diprobe | 🟠 **Tetap belum diprobe** — uangnya masih bertumpu ≈7 pembeli |
| **Indeed Reviews** | 🟡 #3 | `memo23/apify-indeed-reviews` $330 (FLAT, 10 u30, gagal 0%), rak 7 seller / 1 memungut | 🟡 Dipertahankan |
| **Kleinanzeigen Immobilien** | 🔴 #3 | Rak $457, 21 seller, 2 memungut; `clearpath` FLAT $45 → $270 | 🟡 Dipertahankan |
| **`xtracto/skyscanner-scraper` rusak** | 🟠 #4 | u30 12, 125 user, 1.802 run | 🟠 Belum diperbaiki |
| **TecDoc** | ⚠️ lisensi | $2.208, rpu 15.077 | ❌ Tetap ditolak (lisensi B2B) |
| **realestate.com.au · domain.com.au · buildzoom · inmuebles24 · kununu · furnishedfinder · ra.co HTML** | ❌ tembok | Tidak diprobe ulang | ❌ Tetap tutup |

---

## 10. Status & note untuk build ke depan

### Urutan eksekusi

**#1 — Kalibrasi harga (nol engineering, dampak terbesar, sudah tertunda satu putaran).**
Urutannya berubah setelah audit §8 — **ukur dulu, baru ubah, dan yang diubah bukan yang dikira sebelumnya.**

**1a. Ambil satu angka dari Console `xtracto`** (cuma ini yang tidak bisa diambil dari API publik):
pendapatan riil 30 hari terakhir. Lalu:
`faktor_item_per_run = (pendapatan_riil − $418,05 actor-start) ÷ $148,36`.
Hasilnya langsung memberitahu di baris mana kamu duduk di tabel Koreksi 1 (§8). **Semua keputusan di bawah
bergantung pada angka ini — jangan lewati.**

**1b. Perbaiki dua actor yang memang underpriced** (tidak perlu menunggu 1a, ini murni di bawah pasar):
- `tiktok-trending-scraper` — 37 pembeli, $0,00075/item → **$0,002** (median vein TikTok)
- `threads-post-detail-scraper` — 14 pembeli, $0,00099/item → **$0,003** (median vein Threads)

**1c. Tinjau dua actor yang kemahalan relatif** (kandidat penyebab u30 rendah, bukan kandidat kenaikan):
- `ebay-sold-comps-scraper` $0,02/item sementara 74 dari 80 pesaing lebih murah (median vein $0,003)
- `shopee-product-detail` $0,015/item, di atas p90 veinnya ($0,01)

**1d. Baru setelah 1a: uji PPE vs FLAT pada SATU actor.** Kalau faktor item/run ternyata rendah (<5),
uji `shopee-shop-scraper` (66 pembeli, paling kecil risikonya) dengan FLAT $19. Kalau faktornya tinggi (≥20),
PPE sekarang sudah lebih baik — **jangan disentuh.**

*Note:* jangan ubah 218 actor sekaligus. Ubah 2–3, tunggu satu siklus 30 hari, baca `totalUsers30Days`
sebelum/sesudah. Actor yang sudah di atas median veinnya **tidak** ikut dinaikkan.

**#2 — Build `clutch.co` (§6).** Permukaan sudah terverifikasi 2,73 MB terbuka. Satu halaman kategori = 72 profil.
*Note:* output harus atribut lead (min. project size, rate, headcount, lokasi, layanan), bukan sekadar nama+URL —
itu yang membuat dua incumbent bisa memungut FLAT $40. Siapkan juga `goodfirms`/`designrush`/`sortlist` sebagai
turunan parser yang sama.

**#3 — Build klaster direktori & klasifikasi Eropa (§6, rekomendasi #2):** Gelbe Seiten → Marktplaats → Ceneo → Firmy.cz.
Urutan itu dari yang paling mudah. *Note:* Ceneo wajib pakai Session (handshake cookie); Marktplaats ambil dari
`__NEXT_DATA__`, jangan parse HTML.

**#4 — RECON Apple Maps (rak $731, $12,38/pembeli — $/pembeli tertinggi di antara kandidat baru).**
`zen-studio/apple-maps-scraper-pro` mendapat 731 rb run dari 104 user, jadi jalurnya pasti murah dan berulang.
Yang sudah diketahui: web `maps.apple.com` = cangkang, `cdn.apple-mapkit.com/ma/bootstrap` = **401** di semua Referer.
Yang belum dicoba: MapKit JS token dari akun Apple Developer (JWT ES256), dan endpoint GEO protobuf yang dipakai
aplikasi iOS. **Ini recon satu sesi, bukan build** — kalau butuh akun Apple berbayar, tinggalkan.

**#5 — Probe cluster review perjalanan `knagymate`** (HRS $502, Zoover $192, Despegar, Kurzurlaub, Trip.com).
Masih kandidat dengan uang terbesar yang belum pernah disentuh. Pass 5 + 5b. Trip.com sudah diketahui cangkang.

**#6 — Dua perbaikan produk di actor sendiri (§8):** tambah data-type **Spotify monthly listeners** ke
`spotify-scraper` yang sudah ada, dan cek kenapa `mobilede-listings` mati (11 user) sementara `3x1t/mobile-de-scraper`
dapat 1,07 juta run dengan FLAT $9,99.

### Aturan proses — yang berubah putaran ini

1. **Vein dikelompokkan per DOMAIN, bukan per token kata.** Ini memperbaiki pola B dari 0/25 jadi 8 rak brand nyata.
   Skrip: `scratchpad/money_v5.py`. Metode token (`money_v5tok.py`) tetap dijalankan sebagai pembanding, tapi
   outputnya masih tercemar kata generik (`interviews`, `amenities`, `hours`, `included`, `richest` — semuanya
   sebenarnya menunjuk actor yang sama).
2. **Pola A dan pola B sudah diuji tiga putaran berturut-turut** (korpus 5.773 → 23.779 → 23.864) dan hasilnya
   konsisten: **pakai sebagai penjelas, jangan sebagai penyaring.** Penyaring tetap `MRR vein ≥$60` DAN
   `≤3 seller yang memungut ≥$5`.
3. **Dedupe tiga lapis wajib** — `xtracto` (218) + `fanndev` (**83**, naik dari 75) + 228 folder lokal = 444 nama.
   Lapis kedua berubah tiap minggu, jadi tarik ulang tiap putaran; jangan pakai snapshot lama.
4. **Selalu Pass 5b.** Putaran ini: 4 target balas 200 dengan halaman 30–381 KB dan **tidak satu pun memuat data
   yang dicari** (Apple Maps, Spotify, Mercari, NoBroker).
5. **Gotcha baru: meta-refresh 19 KB ≠ WAF.** Ceneo terlihat seperti challenge di request pertama, padahal
   cuma penanaman cookie. Selalu coba request kedua dalam Session yang sama sebelum memvonis sebuah domain tertutup.
6. **Tulis file query lewat Python/Write, jangan heredoc Bash** (heredoc menelan satu level backslash; regex `\b`
   jadi karakter backspace dan diam-diam mencocokkan nol actor). Putaran ini heredoc juga gagal menulis dokumen
   markdown yang mengandung backtick + kutip — pakai tool Write.
7. **Satu brand = satu query single-token.** Query multi-kata under-count seller. Catatan: query single-token pun
   bisa over-count — `dice` menangkap Dice.fm **dan** Dice.com jobs, jadi selalu baca daftar top-nya.
8. **Model uang harus menjumlahkan SEMUA event, bukan cuma `isPrimaryEvent`** (§8 Koreksi 1). `apify-actor-start`
   ditagih sekali per run dan di akun `xtracto` nilainya **$418/bln — 2,8× event primernya**. Semua angka MRR di
   `money_v4.py`/`money_v5.py` dan di seluruh arsip adalah **lantai yang kurang hitung**, untuk actor sendiri
   maupun untuk pesaing. Peringkat relatif antar-actor PPE tetap sah; nilai absolutnya tidak.
9. **Harga per item bisa tiered ATAU flat.** `eventTieredPricingUsd.GOLD` dan `eventPriceUsd` dua-duanya dipakai di
   Store; skrip lama hanya membaca yang tiered dan diam-diam memberi $0 pada yang flat (7 actor `xtracto`, termasuk
   `tiktok-trending-scraper` yang punya 37 pembeli). `scratchpad/price_audit.py` membaca keduanya.
10. **Median harga satu akun bukan posisi pasar.** Median $0,002 milik `xtracto` ditarik ke bawah oleh ~150 actor
    tanpa pembeli; actor yang benar-benar dipakai duduk di $0,005–$0,02, **di atas median veinnya**. Selalu
    bandingkan per vein (`price_bench.py`), jangan per akun.

### Ditolak permanen (tidak berubah)

PII & skip-trace (`realtyapi`/`one-api/skip-trace` $1.645, RocketReach $350, Apollo, Instantly, Truecaller,
Dubai unit-number, Tinder/Hinge), TecDoc (lisensi B2B), darkweb, view/traffic generator (`epctex/traffic-generator`
$660 — muncul lagi putaran ini lewat token `behance`/`many`, tetap bukan target).
