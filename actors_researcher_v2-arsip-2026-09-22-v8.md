# Riset Pasar Apify Store — v2 (putaran 2026-09-22 / v8)

**Tanggal riset:** 2026-09-22
**Permintaan putaran ini:** daftar actor dengan demand tinggi / stats tinggi di Apify Store, khususnya dua pola —
(A) *total runs banyak tapi user sedikit*, (B) *total user banyak tapi saingan sedikit* — lalu **dedupe wajib**
terhadap akun [`xtracto`](https://api.apify.com/v2/store?username=xtracto) supaya tidak membangun yang sudah ada.

> Putaran sebelumnya diarsipkan ke `actors_researcher_v2-arsip-2026-09-21.md` (termasuk peta permukaan Discord §12).

---

## Dedupe tiga lapis (snapshot ditarik ulang 2026-09-22)

| Lapis | Jumlah | Angka | Snapshot |
|---|---:|---|---|
| `xtracto` (akun yang kamu sebut) | **219 actor** | 933 pembeli aktif (u30) · 164 actor punya ≥1 pembeli · **49.747** run sukses/30h | `output/xtracto-full-v8.json` |
| `fanndev` (akun push saat ini) | **106 actor** | 105 u30 · 94 actor punya pembeli · 1.807 run sukses/30h | `output/fanndev-full-v8.json` |
| Folder lokal repo ini | **290 folder** | 185 di antaranya **belum terbit di akun mana pun** | `scratchpad/_dedupe_names_v8.json` |
| **Gabungan nama unik untuk dedupe** | **508** | — | `scratchpad/_dedupe_blob_v8.txt` |

**Perubahan sejak 2026-09-19 (v7):** `xtracto` 217 → **219** actor, tapi `u30` **945 → 933** (pembeli terus
bocor pelan) sementara `ok30` **47.265 → 49.747** (pemakaian per pembeli naik lagi). `fanndev` 96 → **106**
actor, `u30` 102 → 105, `ok30` 1.522 → **1.807**. Folder lokal 245 → **290**.

**Verifikasi duplikat seluruh shortlist:** tiap nama di §5–§8 dicek satu per satu terhadap ketiga lapis.
**Nol tabrakan pada shortlist final.** Yang **tersaring keluar karena ternyata sudah kamu punya** putaran ini —
dan ini penting, karena empat di antaranya muncul sebagai "peluang" di lensa sebelum dedupe:

| Kandidat yang gugur | Sudah ada di | Bentuknya |
|---|---|---|
| Google Ads Transparency (rak $1.132, top rating **1,93**) | `xtracto/google-ads-transparency` | sama persis |
| Crexi CRE | `xtracto/crexi-yield-scraper` | sama persis |
| Quora | `xtracto/quora-user-profile` | sama persis |
| Bilibili | `xtracto/bilibili-danmaku` | sama persis |
| Uber Eats · Kickstarter · ForexFactory · Substack · Snapchat | `xtracto` / `fanndev` | sama persis |
| Tech Stack Detector (**#2 rekomendasi v7**) | `fanndev/tech-stack-detector` | ✅ **sudah dibangun & terbit** |

## Data mentah putaran ini

| File | Isi |
|---|---|
| `output/scan-v8-corpus.json` | **24.194 actor unik** — 21 kategori × 7 band user × offset 0–900 |
| `output/scan-v8-domains.json` / `-clean.json` | **1.793 vein per DOMAIN**, versi bersih dilantai `ok30 ≥ 60` |
| `output/scan-v8-top-money.json` | 400 actor dengan MRR terukur tertinggi |
| `scratchpad/lens_v8_out.txt` | Lensa 1–8 (pola A, pola B, vein, incumbent rapuh, bookmark, penjual tunggal) |
| `scratchpad/lens_v8c_out.txt` | Lensa 10–11 (celah kapabilitas — **wajib tiap putaran**) |
| `scratchpad/lens_v8d_out.txt` | **Lensa 13–15 baru** (46 kelas kapabilitas, actor muda, harga yang diterima pasar) |
| `scratchpad/shortlist_v8_out.txt` | angka rak per kandidat final |

Skrip: `scratchpad/{dedupe,scan,money,lens,lens_v8c,lens_v8d,vein,shortlist}_v8.py` +
probe `scratchpad/probe_v8{,b,c,d}.py`.

---

## 1. Ringkasan eksekutif

Korpus **24.194 actor**. MRR terukur seluruh Store **$747.631/bulan** mentah, **$727.034** setelah lantai
kebisingan `ok30 ≥ 60`. **3.713 actor** memungut ≥$5/bulan secara nyata. (v7: 24.082 · $756.170 · $738.392 ·
3.808 — pasar **mendatar, bukan tumbuh**, dua putaran berturut.)

**Lima hal yang keluar dari putaran ini:**

1. **Satu koreksi metode membatalkan sebagian vonis "tertutup" dari putaran-putaran lalu.** Host yang selama
   ini balas *timeout* dari mesin ini — `api.sofascore.com`, `www.bet365.com`, `www.draftkings.com`,
   `api.underdogfantasy.com`, `market.yandex.ru` — ternyata **diarahkan ISP Indonesia ke 158.140.186.3**
   (blackhole blokir judi), bukan ditolak situsnya. Dipaksa lewat DoH Cloudflare, **SofaScore membalas
   200/64 KB berisi pertandingan sungguhan** dan **Yandex Market 200/1,97 MB berisi harga rubel sungguhan**.
   Detail di §7 dan Koreksi 9. *(Handelsregister dicek ulang dengan cara yang sama: DNS-nya normal, jadi
   penolakan permanennya tetap sah.)*
2. **Pola B per-domain tetap habis — dan sekarang jelas kenapa.** 17 rak yang lolos filter "user banyak,
   penjual sedikit" **seluruhnya** PII/skip-trace (`realtyapi`, `dievio`, `apollo`, `instantly`), merek vendor
   API (`scraptik`), atau sudah kamu punya (`trustpilot`, `yelp`, `expedia`, `wellfound`). Nol baris baru,
   putaran kelima berturut-turut. Lensa kapabilitas (§5) sekarang satu-satunya yang masih menghasilkan.
3. **Celah kapabilitas terbesar yang belum kamu sentuh bukan scraper situs, tapi *verifikasi email bulk*:**
   rak murni **$1.675/bulan, 11 penjual memungut, 6.481 pembeli aktif, 29.861 user, 1,41 juta run sukses/30h** —
   dan pemuncaknya `account56/email-verifier` (**5.050 pembeli aktif** sendirian) **gagal 24,7%**. Itu pola B
   murni: basis pembeli raksasa, incumbent rapuh, tanpa situs target yang bisa ditutup WAF. **Tapi dua penjual
   teratas ternyata cuma membungkus API berbayar orang lain** (MillionVerifier, validatedmails.com) — jadi
   bentuk produknya harus diputuskan dulu, dan satu syarat teknis harus diuji (§8 #1).
4. **Transkrip YouTube tetap rak terbesar dan tetap terkunci.** Rak naik $22,9k → **$23,1k** (19 penjual,
   7.439 pembeli aktif), dan `timedtext` **membalas 200 dengan 0 KB untuk keempat kalinya**. Tidak ada yang
   berubah sejak v7: ini menunggu satu uji proxy residential, bukan menunggu riset lagi.
5. **Angka yang mendahului seluruh daftar ini: 185 folder lokal belum terbit** (v7: 148), **184 di antaranya
   punya `actor.json` lengkap** — termasuk 8 actor yang dibangun *minggu ini* (`discord-server-scraper`,
   `etsy-ultimate-data-extractor`, `alfagift-scraper`, `noon-scraper`, `mobile-de-scraper`, `glints-jobs-scraper`,
   `techinasia-scraper`, `movie-tv-data-extractor`). Rak riset ini bernilai nol sampai langkah publish jalan (§11).

---

## 2. Papan atas pasar — di mana demand sebenarnya berada (konteks, bukan target)

Diurut per **pembeli aktif 30 hari** (`u30`), bukan `totalUsers`.

| u30 | Users | Runs | MRR bersih | Actor |
|---:|---:|---:|---:|---|
| 43.149 | 400.062 | 198,0 jt | $25.892 | `apify/instagram-scraper` |
| 36.585 | 612.497 | 39,7 jt | $5.582 | `compass/crawler-google-places` |
| 30.413 | 177.303 | 8,1 jt | **$0** | `apify/rag-web-browser` (gratis) |
| 27.091 | 222.350 | 116,9 jt | $14.706 | `apify/instagram-profile-scraper` |
| 23.303 | 289.928 | 127,5 jt | **$33.578** | `clockworks/tiktok-scraper` |
| 17.229 | 159.839 | 3,9 jt | $515 | `curious_coder/linkedin-jobs-scraper` |
| 16.915 | 186.233 | 120,3 jt | $21.527 | `apify/google-search-scraper` |
| 13.759 | 111.410 | 45,8 jt | $14.649 | `apify/facebook-posts-scraper` |
| 13.275 | 15.648 | 0,6 jt | $600 | `apify/web-fetch` — **rasio u30/users 0,85** |

Dan bentuk yang paling relevan buat kamu — **uang besar, pembeli segelintir**:

| MRR | u30 | Users | ok30 | $/pembeli | Actor | Baca |
|---:|---:|---:|---:|---:|---|---|
| **$14.177** | 13 | 230 | 2.835.386 | **$1.091** | `dev00/discord-username-checker` | **permukaan terbuka, diverifikasi hari ini (§8 #5)** |
| **$14.074** | 26 | 74 | 281.208 | $541 | `entertained_rattlesnake/youtube-subtitle-scraper-ai` | puncak vein transkrip — **bergerbang** |
| $6.700 | 67 | 3.602 | 3.600 | $100 | `peakydev/leads-scraper` | FLAT $100, gagal **25,0%** (naik dari 17,9%) |
| **$4.890** | 32 | 113 | 209.950 | $153 | `zen-studio/apple-maps-scraper-pro` | keputusan $99/thn, bukan recon (§9) |
| $4.500 | 9 | 1.001 | 115 | $500 | `webcrawlerr/dubai-property-crawler` | PII Dubai — ditolak permanen |
| **$4.364** | 6 | 61 | 42.371 | **$727** | `scraped/tcgplayer-sales-history` | **celah mode di rak sendiri (§8 #6)** |
| $3.059 | 24 | 196 | 22.989 | $127 | `harvestlab/ebay-scraper` | eBay sudah kamu pegang 4 actor |
| $2.551 | 74 | 643 | 510.142 | $34 | `lemur/tiktok-shop-creators` | TikTok Shop — Security Check (babak 53) |

---

## 3. POLA A yang kamu minta — "runs banyak, user sedikit"

Filter: `totalUsers ≥ 15` **dan** `totalRuns ≥ 100.000`, diurut runs-per-user, dari korpus 24.194.

| runs/user | Users | u30 | Runs | MRR | Model | Actor | Vonis |
|---:|---:|---:|---:|---:|---|---|---|
| 115.979 | 212 | 4 | 24,6 jt | $100 | FLAT | `alien_force/facebook-scraper-pro-rental` | model sewa + **gagal 52,1%** |
| 79.523 | 32 | 3 | 2,5 jt | $36 | FLAT | `canadesk/apple-app-store-plus` | rak App Store jenuh |
| 75.782 | 42 | 3 | 3,2 jt | $0 | FREE | `apify/monitoring-checker-schema` | infrastruktur Apify |
| **72.180** | **16** | 1 | 1,2 jt | **$694** | PPE | `apikit/upcheck` | uptime checker, $0,01/run — **1 pembeli** |
| 48.545 | 19 | 1 | 0,9 jt | $20 | FLAT | `canadesk/career-scraper-plus` | `ok30 = 29` → **lantai palsu**, abaikan |
| 40.897 | 61 | 0 | 2,5 jt | $0 | PPE | `thescrappa/google-maps-advanced-search-scraper` | `ok30 = 28`, **nol pembeli** |
| 29.524 | 882 | 29 | 26,0 jt | $1.902 | PPE | `build_matrix/company-employees-scraper` | PII — ditolak permanen |
| 24.384 | 21 | 1 | 0,5 jt | $781 | PPE | `knagymate/hrs-reviews-scraper` | **HRS sudah ditutup v7** (0 `reviewText` di RSC) |
| 21.288 | 1.035 | 81 | 22,0 jt | $1.664 | PPE | `macrocosmos/reddit-scraper` | Reddit: 10 penjual, rak $16k — jenuh |
| 15.377 | 2.112 | 28 | 32,5 jt | $1.932 | FLAT | `making-data-meaningful/tecdoc` | lisensi B2B — ditolak permanen |
| **15.175** | **61** | 6 | 0,9 jt | **$4.364** | PPE | `scraped/tcgplayer-sales-history` | **celah mode di rak sendiri (§8 #6)** |
| 15.119 | 64 | 7 | 1,0 jt | $18 | PPE | `saswave/noon-seller-monitoring` | **gagal 31,0%** — kamu baru bangun `noon-scraper` |
| **12.822** | **230** | 13 | 2,9 jt | **$14.177** | PPE | `dev00/discord-username-checker` | **§8 #5 — permukaan diverifikasi terbuka** |
| **10.907** | **74** | 26 | 0,8 jt | **$14.074** | PPE | `entertained_rattlesnake/youtube-subtitle-scraper-ai` | transkrip — **bergerbang (§7)** |
| 10.704 | 16 | 6 | 0,2 jt | $270 | FLAT | `clearpath/kleinanzeigen-immobilien-api-pro` | carry-over v7, selector sudah dipetakan |

**Cara membaca tabel ini (tidak berubah dari v7, tapi menagih lagi):** 21 dari 35 baris teratas adalah
infrastruktur Apify, model sewa, PII, atau lantai palsu `ok30 ≈ 29`. **Pola A adalah penjelas, bukan penyaring.**
Yang tersisa setelah disaring: `tcgplayer-sales-history`, `discord-username-checker`, transkrip YouTube.

---

## 4. POLA B yang kamu minta — "user banyak, saingan sedikit"

Filter vein per domain: `users ≥ 1.500` **dan** `sellers ≤ 8`, dari 1.793 vein.

| MRR rak | Penjual | Memungut | Users | u30 | Vein | Vonis |
|---:|---:|---:|---:|---:|---|---|
| $2.205 | 1 | 1 | 4.585 | 915 | `scraptik` | merek **vendor API**, bukan situs |
| $1.562 | 1 | 1 | 15.413 | 769 | `realtyapi` | PII skip-trace |
| $1.302 | 4 | 3 | 2.909 | 56 | `upwork` | top `jupri/upwork` **gagal 9,0%**; Upwork = login-gated |
| $1.040 | 4 | 1 | 5.204 | 84 | `trustpilot` | **sudah punya** |
| $983 | 3 | 3 | 1.827 | 148 | `yelp` | **sudah punya** |
| $890 | 4 | 3 | 1.645 | 145 | `expedia` | **sudah punya** |
| $763 | 1 | 1 | 16.003 | 525 | `dievio` | PII |
| $607 | 6 | 4 | 2.134 | 546 | `ozon` | **403 di 7/7 profil TLS** (babak 52) |
| $377 | 7 | 4 | 18.274 | 1.758 | `apollo` | PII |
| $58 | 8 | 3 | 21.022 | 1.759 | `naukrigulf` | 21k user, **$58 total** — rak gratisan |

**Vonis pola B: nol kandidat, putaran kelima berturut-turut.** Setiap rak yang lolos filter angka gugur di
salah satu dari empat mode kebohongan yang sudah terdokumentasi: (a) penjual memungut $0, (b) monopoli,
(c) PII, (d) vein = merek vendor API, bukan situs target.

**Satu baris yang layak dibaca ulang:** `naukrigulf` — 21.022 user dibagi 8 penjual, total pungutan **$58**.
Itu bukan peluang, itu bukti bahwa "user banyak + saingan sedikit" tanpa memeriksa **siapa yang memungut**
adalah sinyal palsu ([[apify-seller-count-overstates-density]]).

---

## 5. Lensa kapabilitas — 46 kelas (pengganti lensa domain yang sudah kering)

`scratchpad/lens_v8d.py`. Kelas dengan tanda **CELAH** = tidak ada actor padananmu di 325 actor terbit.

| MRR rak | Penjual | u30 rak | Kelas kapabilitas | Status rakmu |
|---:|---:|---:|---|---|
| **$23.104** | 19 | 7.439 | transkrip/subtitle | **CELAH** — bergerbang (§7) |
| $3.788 | 10 | 2.961 | unduh video/audio | **CELAH** — ditolak (ToS platform) |
| $3.507 | 3 | 70 | lelang | punya 2 (`ebay-*`) |
| $2.551 | 9 | 1.057 | influencer/creator DB | **CELAH** — mayoritas PII |
| **$1.675** | **11** | **6.481** | **verifikasi email (murni)** | **CELAH → §8 #1** |
| $1.285 | 2 | 184 | real estate komersial | punya 1 (`crexi-yield-scraper`) |
| $1.173 | 5 | 1.457 | backlink/SEO teknis | punya 1 |
| $1.132 | 8 | 1.185 | ad intelligence | punya 3 |
| $1.131 | 4 | 1.230 | hotel/penerbangan | punya 2 |
| $878 | 6 | 750 | terjemahan | CELAH — kelas turunan, bukan produk |
| $802 | 6 | 78 | mobil bekas | **CELAH** — `mobile-de-scraper` belum terbit |
| $796 | 5 | 372 | gambar/aset kreatif | CELAH — biaya GPU |
| $741 | 2 | 51 | restoran/reservasi | **CELAH → §8 #6** |
| $576 | 4 | 540 | SERP/rank tracking | CELAH — sumber volume berbayar (babak 53) |
| $307 | 3 | 78 | registry perusahaan AS | **CELAH** — permukaan terbuka (§7) |

### Lensa 14 — actor muda berpenghasilan (`u30/users ≥ 0,45`) = permintaan yang **baru terbentuk**

| rasio | MRR | u30 | Users | Actor | Catatan |
|---:|---:|---:|---:|---|---|
| 0,85 | $600 | 13.275 | 15.648 | `apify/web-fetch` | infrastruktur Apify |
| **0,83** | $1.264 | 1.220 | 1.462 | `nexgendata/wappalyzer-replacement` | **rekomendasi #2 v7 — sudah kamu bangun** |
| 0,77 | $162 | 1.530 | 1.993 | `danitn11/pisa-sr-image-upscaler` | model GPU, bukan scraper |
| 0,57 | $619 | 1.057 | 1.857 | `unseenuser/LinkedIn-Profile` | PII |
| 0,56 | $251 | 804 | 1.442 | `dev00/synthid-remover` | **ditolak** — menghapus watermark provenance AI |
| 0,52 | $429 | 105 | 202 | `apify/perplexity-search-scraper` | first-party Apify |
| **0,50** | $346 | 622 | 1.254 | `zen-studio/wechat-official-account-scraper` | **§8 #4 — gerbang Sogou terbuka** |
| 0,48 | $239 | 1.107 | 2.311 | `crawlstone/tennis-scraper` | **§8 #2** |

Pola yang terbaca dari lensa ini: **adopsi cepat sekarang terjadi di kapabilitas dan di platform Asia
(WeChat, Taobao, 1688), bukan di situs Barat baru.** Tidak ada satu pun domain Barat baru dengan rasio ≥0,45.

### Lensa 15 — harga tinggi yang **diterima pasar** (`$/pembeli ≥ $25`, `u30 ≥ 25`, gagal <5%)

`entertained_rattlesnake` $541/pembeli · `zen-studio/apple-maps-scraper-pro` $153 · `tecdoc` $69 ·
`bestscrapers` $67 · `yandex-market` $31 · `glassdoor` $32 · `realtor` $25.
**Artinya untuk penetapan hargamu:** pasar membayar $25–$150 per pembeli per bulan di rak niche yang andal.
`xtracto` memungut **$532,24/bulan dari 933 pembeli aktif = $0,57/pembeli** (diukur ulang hari ini dari
korpus yang sama, memakai aturan harga yang sama untuk semua orang). `fanndev`: **$0,92 dari 105 pembeli**.
Jarak ke rak niche yang andal **44×–260×**. Kalibrasi harga (§9) sudah empat putaran tertunda.

---

## 6. POLA A × POLA B digabung — daftar pendek yang lolos kedua saringan

Hanya 5 baris di seluruh korpus yang punya **runs/user > 10.000** *dan* **rak dengan ≤8 penjual memungut**
*dan* **bukan PII/infrastruktur/milik sendiri**:

| Actor | runs/user | Rak | Penjual memungut | Permukaan (diuji hari ini) |
|---|---:|---:|---:|---|
| `dev00/discord-username-checker` | 12.822 | $14.271 | 7 | ✅ **terbuka & anonim** |
| `scraped/tcgplayer-sales-history` | 15.175 | $4.364 | 1 | belum diprobe — rak sendiri |
| `entertained_rattlesnake/youtube-subtitle-scraper-ai` | 10.907 | $23.104 | 19 | ❌ **200/0 KB (gerbang)** |
| `clearpath/kleinanzeigen-immobilien-api-pro` | 10.704 | $228 | 2 | ✅ terbuka (v7) |
| `parseforge/copart-public-search-scraper` | 11,9 rpu tapi 5.807 ok30 | $160 | 4 | ✅ **terbuka, paginasi dalam** |

---

## 7. Hasil probe permukaan — Pass 5 / 5b / 5c / 5d (2026-09-22)

**Aturan tidak berubah:** `200` tidak dihitung terbuka sampai regex bukti menemukan baris data sungguhan.

### ✅ Terbuka (data terverifikasi ada)

| Target | Hasil | Bukti |
|---|---|---|
| **Copart** `POST /public/lots/search-results` | 200/240 KB | `totalElements = 36.303` untuk "honda"; **paginasi 100/halaman sampai page 9 tetap penuh**; `/public/data/lotdetails/solr/<lot>` balas JSON lot |
| **SofaScore** `api/v1/sport/{tennis,football}/events/live` | 200/64 KB & 16 KB | 30 objek `tournament`, 8 `homeTeam` — **hanya lewat DoH**, lihat Koreksi 9 |
| **Yandex Market** `/search?text=` | 200/1,97 MB | 19 harga ₽, 15 judul produk, **0 captcha nyata** — hanya lewat DoH |
| **Tennis Abstract** `player-classic.cgi` | 200/758 KB | 668 baris `var matchmx` (riwayat pertandingan mentah) |
| **Sogou → WeChat** `weixin.sogou.com/weixin?type=2` | 200/29 KB | 10 kartu `txt-box`, 20 tautan artikel, **0 antispider** |
| **Resy** `api.resy.com/3/venue` | 200/24 KB | 25 field venue — **butuh `Authorization: ResyAPI api_key="…"`** (kunci publik di bundle web) |
| **Discord** `POST /api/v9/unique-username/username-attempt-unauthed` | 200 | `{"taken":true}` — **anonim, tanpa captcha, tanpa token** |
| **VIES VAT (EU resmi)** `rest-api/ms/DE/vat/…` | 200 | `"isValid": true` — API pemerintah, tanpa kunci |
| **Colorado SoS** (Socrata) | 200 | 6 field entitas per baris — pola open-data yang berulang di banyak negara bagian |

### ❌ Tertutup / gugur putaran ini

| Target | Hasil | Tafsir |
|---|---|---|
| YouTube `timedtext` | **200 / 0 KB** (keempat kalinya) | gerbang token/IP — bukan permukaan mati (§8 #7) |
| OpenTable (`/r/…` dan `/dapi/fe/gql`) | 403 Akamai "Access Denied" | tertutup dari IP ini |
| LoopNet | 403 Akamai (chrome & firefox133) | tertutup dari IP ini |
| Coupang | 403 Akamai | tertutup dari IP ini |
| IAAI | 200/3,5 MB **tapi 0 baris lot** + skrip Imperva | tantangan JS — "200 besar tanpa data" (mode kegagalan lama) |
| DoorDash | 403 Cloudflare "Just a moment…" | tertutup |
| Underdog Fantasy | 403 Cloudflare (via DoH) | tertutup — **bukan** blokir ISP |
| PrizePicks | 403 `"unavailable in your location"` | **geo murni** — butuh proxy AS, bukan bypass |
| EU TARIC | ConnectionError ×2 | tidak dapat dinilai; rak $70 — tidak layak jatah probe ketiga |
| ATP Tour | 200/579 KB, 0 baris ranking | dirender JS; Tennis Abstract sudah menutupi kebutuhannya |

---

## 8. Rekomendasi

### #1 — Verifikasi email bulk — **rak pola-B terbesar yang permukaannya tidak bisa ditutup siapa pun**

**Angka rak (regex ketat, *verifier* saja — *email finder* dikeluarkan karena itu PII):**
$1.675/bulan · **11 penjual memungut** · **6.481 pembeli aktif** · 29.861 user · **1,41 juta run sukses/30h**.
(Dengan *finder* ikut dihitung: $3.094 · 30 penjual · 10.107 pembeli — angka itu **tidak** saya pakai.)

| MRR | u30 | Users | ok30 | Gagal | Harga | Actor |
|---:|---:|---:|---:|---:|---|---|
| $1.344 | **5.050** | 16.407 | 1.221.779 | **24,7%** | PPE $0,0011/email | `account56/email-verifier` |
| $74 | 449 | 1.862 | 123.318 | 0,8% | PPE $0,0006/email | `michael.g/email-verifier-validator` |

**Kenapa ini teratas:** 5.050 pembeli aktif pada satu actor yang **gagal 1 dari 4 run** adalah bentuk
"incumbent rapuh × basis pembeli raksasa" paling ekstrem di korpus. Tidak ada situs target → tidak ada WAF,
tidak ada perubahan DOM, tidak ada gerbang IP. Ini pengulangan pelajaran Tech Stack Detector yang sudah
terbukti benar putaran lalu.

**Yang wajib kamu tahu sebelum memutuskan — dua penjual teratas bukan membangun, mereka menjual ulang.**
`account56` judulnya harfiah "Email Verifier **by Million Verifier**"; `xmiso_scrapers` menulis "using
MillionVerifier api"; `fatihtahta` memakai "validatedmails.com API". Artinya rak ini punya **dua bentuk
produk yang berbeda**, dan kamu harus pilih sadar:
- **(a) Reseller** — bungkus API berbayar, margin dari markup, gagal 24,7% incumbent itu justru **bukti
  bahwa pipa pihak ketiga rapuh**. Murah dibangun, tapi biaya variabel per email dan kamu tidak memegang moat.
- **(b) Verifikasi sendiri** — DNS/MX + heuristik, opsional SMTP. **Bukti bahwa (b) bisa jalan di Apify ada
  di rak yang sama**: `george.the.developer/email-validator-api`, `crawlerbros/email-verifier`, dan
  `yasir-on-apify/email-verifier-deliverability-checker` semuanya mengiklankan "SMTP checks" tanpa menyebut
  vendor mana pun. Itu indikasi kuat port 25 terbuka di runtime Apify — **tapi tetap harus kamu uji sendiri,
  karena dari mesin ini port 25 diblokir.**

> **⚠️ Satu syarat teknis harus diuji sebelum menulis kode.** Dari mesin ini, **SMTP port 25 diblokir**
> (`socket.create_connection(("gmail-smtp-in.l.google.com", 25))` → TimeoutError). Sebagian besar penyedia
> cloud memblokir port 25 keluar secara bawaan. **Uji dulu di Apify** dengan satu actor tempel 10 baris:
> kalau port 25 terbuka di runtime Apify → verifikasi penuh (RCPT TO) mungkin; kalau tertutup → jual
> **tingkat verifikasi tanpa SMTP**, yang justru yang dipakai mayoritas pesaing.

*Note build:* tanpa SMTP pun masih ada 6 sinyal yang laku dijual: (1) sintaks RFC 5322, (2) **MX record
via `dnspython` — sudah terpasang di repo ini**, (3) daftar domain sekali-pakai (~60k domain,
open-source), (4) alamat role (`info@`, `admin@`), (5) deteksi catch-all lewat alamat acak, (6) typo domain
(`gmial.com` → `gmail.com`, jarak Levenshtein ke 200 domain teratas). Harga: **PPE $0,0008/email** —
di bawah `account56` ($0,0011) dan di atas biaya. Jual keandalan sebagai pembeda: **"gagal <1% vs 24,7%"**.

---

### #2 — Statistik olahraga SofaScore — **permukaan yang selama ini dikira mati, ternyata cuma diblokir ISP**

`api.sofascore.com` balas **200/64 KB** begitu DNS-nya dipaksa lewat DoH. Rak tenis/olahraga:

| MRR | u30 | Users | ok30 | Harga | Actor |
|---:|---:|---:|---:|---|---|
| $453 | 64 | 454 | 9.060 | PPE $0,050 | `zen-studio/prizepicks-player-props` (**geo AS**) |
| $256 | **710** | 1.755 | 11.633 | PPE $0,022 | `parseforge/tennis-abstract-scraper` |
| $239 | **1.107** | 2.311 | 39.841 | PPE $0,006 | `crawlstone/tennis-scraper` |
| $60 | 57 | 353 | 1.467 | PPE $0,041 | `abotapi/sofascore-scraper` |
| $14 | 890 | 2.032 | 13.459 | PPE $0,001 | `extractify-labs/flashscore-tennis-matches` |

**Bentuk peluangnya adalah harga, bukan data.** 1.107 + 890 + 710 = **2.707 pembeli aktif** membayar
$0,001–0,022 per item. Yang menjual lebih mahal (`abotapi` $0,041, `zen-studio` $0,050) hanya menjual
satu cabang. **Belum ada yang menjual satu actor multi-cabang dengan kedalaman SofaScore**
(rating pemain, line-up, insiden menit-per-menit, h2h, statistik shot) di harga menengah.

*Note build:* kamu sudah punya `espn-betting-odds-scraper` + `flashscore-all-sports-scraper` di `fanndev` →
skema output, README, dan pola join provider sudah ada. Mode: `live` · `event-detail` · `lineups` ·
`player-stats` · `h2h` · `tournament-standings`. Harga **PPE $0,008/pertandingan**.
**⚠️ Jangan pernah tes dari IP Indonesia tanpa DoH** — hasilnya timeout palsu (Koreksi 9). Di runtime Apify,
DNS-nya normal.

---

### #3 — Copart (lelang salvage) — **terbuka penuh, nol pesaing serius, nol gerbang**

`POST /public/lots/search-results` balas **36.303 lot** untuk satu kata kunci, **100 baris/halaman,
kedalaman minimal 10 halaman terverifikasi**, plus `/public/data/lotdetails/solr/<lot>` untuk detail.
Tanpa proxy, tanpa cookie, tanpa TLS khusus.

Rak: **$160/bulan · 4 penjual memungut · 990 user**. Uangnya kecil — tapi ongkos bangunnya juga kecil
(dua endpoint JSON), dan ini **kelas kapabilitas yang sepenuhnya kosong di rakmu** (`mobil bekas`, §5),
melengkapi `mobile-de-scraper` yang sudah jadi tapi belum terbit.

*Note build:* **jebakan yang sudah menggigit saya hari ini** — objek `filter` dengan sintaks kunci yang salah
(`{"MAKE":["make:HONDA"]}`) balas **200 dengan 0 baris**, bukan error. Pakai `query` (free-text) sebagai
jalur utama dan perlakukan `filter` sebagai lanjutan yang harus diverifikasi baris-demi-baris.
Saudaranya **IAAI ditolak** (Imperva, 3,5 MB tanpa satu pun baris lot).

---

### #4 — WeChat 公众号 lewat Sogou — **permintaan muda (rasio 0,50), gerbang terbuka**

`zen-studio/wechat-official-account-scraper`: **$346/bulan dari 622 pembeli aktif**, 1.254 user
(rasio u30/users **0,50** = sedang meledak). Rak total **$562, 3 penjual memungut, 873 pembeli aktif**.

`weixin.sogou.com/weixin?type=2&query=…` balas **200/29 KB dengan 10 kartu hasil + 20 tautan artikel,
tanpa antispider**.

*Note build:* Sogou adalah **satu-satunya pintu publik** ke konten 公众号 (WeChat sendiri tidak punya web
publik). Tautan `/link?url=` berumur pendek dan harus diikuti segera — rancang pipeline satu-lewat
(daftar → ikuti tautan → ambil artikel) dan jangan simpan URL untuk dipakai belakangan.
Harga: PPE $0,03/artikel (zen-studio $0,055).

---

### #5 — Discord username checker — **$14.177 dari 13 pembeli, endpoint anonim terverifikasi**

`POST https://discord.com/api/v9/unique-username/username-attempt-unauthed` dengan body `{"username":"…"}`
balas `{"taken":true}` — **200, tanpa token, tanpa captcha**. Rak: **$14.271/bulan, 7 penjual memungut,
10.135 user, 2,85 juta run sukses/30h**.

> **Baca angkanya dengan jujur:** $14.177 itu datang dari **13 pembeli** dengan 2,8 juta run. Ini satu-dua
> pelanggan besar, bukan pasar luas. `maged120` menjual hal yang sama ke **90 pembeli** dan hanya memungut $25.
> Jadi ini **taruhan pada satu pelanggan whale**, bukan rak yang lebar.

*Note build & batas:* jual sebagai **pemeriksa ketersediaan nama merek** (padanan cek domain), bukan alat
sniping — jangan sediakan mode klaim/otomasi pendaftaran, dan batasi laju per run. Endpoint ini anonim
tapi tetap milik Discord: **siapkan backoff 429 sejak hari pertama** dan rotasi IP datacenter; pelajaran
`discord-server-scraper` masih berlaku ([[discord-server-scraper-actor]]: matriks TLS yang terbelah rapi
ternyata rate limit ~6 req/IP, bukan gerbang sidik jari).

---

### #6 — Tiga perbaikan kecil di rak sendiri (uang terbesar per jam kerja)

**6a. `tcgplayer-sales-history` — putaran keempat, masih berdiri.** `scraped/tcgplayer-sales-history`
memungut **$4.364/bulan dari 6 pembeli** ($727/pembeli) sementara `xtracto/tcgplayer-price-scraper` diam.
Ini **penambahan mode**, bukan actor baru.

**6b. Resy availability — kunci publik sudah di tangan.** `api.resy.com/3/venue` balas 200/24 KB dengan
header `Authorization: ResyAPI api_key="…"` yang dipanen dari bundle web. Rak OpenTable/Resy $811 dengan
5 penjual memungut, dan `clearpath/opentable-availability-api` **gagal 76,5%**. OpenTable sendiri 403 dari
IP ini → **bangun sisi Resy saja**, jangan janjikan OpenTable.

**6c. Pakai angka keandalan pesaing di README.** `peakydev/leads-scraper` gagal **25,0%** (naik dari 17,9%),
`zerobreak/google-hotels-scraper` gagal 42,7%, `account56/email-verifier` 24,7%, `jupri/streeteasy` 38,0%.
Actor-mu gagal 0–2%. Itu baji pemasaran gratis.

---

### #7 — Carry-over yang tidak berubah: transkrip YouTube & Apple Maps

**Transkrip YouTube** tetap rak terbesar ($23.104, 19 penjual, 7.439 pembeli) dan `timedtext` tetap
**200/0 KB** — keempat kalinya. **Jangan riset ulang.** Yang dibutuhkan satu perintah, bukan satu sprint:
`scratchpad/probe_v7e.py` dengan `APIFY_TOKEN` + grup `RESIDENTIAL`. Biner: keluar segmen → build 3 mode;
tetap 0 KB → `youtubei/v1/get_transcript` dengan token panen halaman; gagal juga → **tinggalkan permanen**.

**Apple Maps** ($4.890 dari 32 pembeli, gagal 0,0%) tetap **keputusan bisnis, bukan recon**: bayar
$99/tahun Apple Developer untuk kunci MapKit JS resmi, atau coret permanen. **Jangan diprobe lagi.**

---

## 9. Status carry-over dari putaran v7

| Item | Status v7 | Hari ini | Vonis |
|---|---|---|---|
| **Tech Stack Detector** (#2 v7) | 🔴 build | ✅ **`fanndev/tech-stack-detector` sudah terbit** | ✅ **Selesai** |
| Transkrip YouTube (#1 v7) | 🟠 recon terblokir kredensial | `timedtext` 200/0 KB lagi (ke-4) | 🟠 **Tidak berubah — butuh `APIFY_TOKEN`** |
| Kalibrasi harga `xtracto` (#3 v7) | 🔴 mendesak | **Belum dikerjakan.** u30 945 → **933**, ok30 47.265 → **49.747** | 🔴 **Empat putaran tertunda; $0,16/pembeli vs pasar $25–150** |
| Kleinanzeigen Immobilien (#4 v7) | 🔴 build, selector sudah dipetakan | Tidak ada folder baru | 🟡 Masih berdiri, turun ke prioritas kedua |
| `tcgplayer` sales-history (#5 v7) | 🔴 jam-an | Belum; rak $5.225 → **$4.364** (tetap $727/pembeli) | 🔴 **Masih pekerjaan termurah di daftar** |
| Terbitkan 22 actor siap + batch-run sisanya | 🔴 #0 | **Belum.** Folder belum terbit naik 148 → **185** | 🔴 **Makin buruk — §11** |
| `dastelefonbuch` + `gelbeseiten` | 🟡 #6 | Rak `dastelefonbuch` $123, 1 penjual | 🟡 Dipertahankan, prioritas rendah |
| `fragrantica` + `goodreads` | 🟡 #6 | `goodreads` $90, 1 penjual | 🟡 Prioritas rendah |
| Apple Maps | ⚠️ keputusan | $5.119 → $4.890 | ⚠️ **Tetap keputusan $99/thn** |
| `hrs.de` · `housesigma` · `handelsregister` · USPTO · trip.com | ❌ | `handelsregister` DNS diuji ulang: **normal**, jadi timeout-nya sah | ❌ **Tetap ditolak** |

---

## 10. Koreksi metode putaran ini

### Koreksi 9 — *timeout* dari mesin ini bisa berarti **blokir ISP**, bukan gerbang situs (paling penting)

`socket.gethostbyname()` untuk `api.sofascore.com`, `www.bet365.com`, `www.draftkings.com`,
`api.underdogfantasy.com` semuanya mengembalikan **`158.140.186.3`** — satu IP blackhole milik ISP Indonesia
(blokir konten judi). `market.yandex.ru` mengembalikan **NXDOMAIN**. Situsnya sendiri hidup sehat:
lewat DoH Cloudflare + `CURLOPT_RESOLVE`, SofaScore balas 200/64 KB dan Yandex Market 200/1,97 MB.

**Aturan baru, wajib dijalankan sebelum memvonis timeout apa pun:**
```python
socket.gethostbyname(host)            # 158.140.186.x  -> blokir ISP, BUKAN gerbang situs
# lalu: DoH Cloudflare -> CurlOpt.RESOLVE ["host:443:<ip asli>"] -> probe ulang
```
Kelas yang paling sering kena: **judi/odds/DFS, marketplace Rusia, sebagian situs dewasa/torrent**.
Konsekuensinya: setiap vonis "timeout = mati" di putaran-putaran lalu untuk kelas ini **harus dianggap
belum diuji**. (`handelsregister.de` sudah dicek ulang: DNS normal → vonisnya tetap sah.)

### Koreksi 10 — `405 Method not supported: GET` = endpoint **hidup**, bukan mati

Copart membalas `405` + `<returnCodeDesc>Error occured</returnCodeDesc>` untuk GET. Dibaca sekilas itu
tampak seperti penolakan; ternyata itu **peta gratis**: endpoint ada, tinggal ganti ke POST — dan POST
langsung membuka 36.303 baris. Tambahkan `405` ke daftar "sinyal ada", sejajar dengan `419 Unauthorized`
(Resy: hanya kurang header `api_key`) dan `401 require_login`.

### Koreksi 11 — objek `filter` bersintaks salah membalas **200 dengan 0 baris**, bukan error

Ini bentuk kelima dari "hollow 200" yang sudah terdokumentasi di proyek ini
(`_basic` Blibli yang menghilangkan produk hidup, halaman provinsi Yellow Pages, dll). Pada Copart,
`{"MAKE":["make:HONDA"]}` balas `totalElements` ada tapi `content` kosong. **Selalu bandingkan satu
kueri berfilter dengan kueri free-text yang setara sebelum menyimpulkan "rak ini kosong".**

### Aturan proses yang masih berlaku (tidak berubah)

1. Jangan percaya `ok30` di bawah 60 — putaran ini **4.511 actor melapor tepat 29**.
2. Baca `eventPriceUsd` datar, bukan cuma `eventTieredPricingUsd.GOLD`.
3. Event `isOneTimeEvent` ≥$1 = pass langganan, bukan biaya per run.
4. Jumlahkan hanya one-time + SATU event primer per-item.
5. **Hitung penjual yang MEMUNGUT, bukan yang hadir.**
6. Vein bisa berupa merek vendor API, bukan situs target.
7. **Selalu Pass 5b** — `200` bukan bukti sampai ada baris data.
8. Timeout ≠ 403 — **dan sekarang: timeout ≠ mati sebelum DNS dicek (Koreksi 9).**
9. Dedupe tiga lapis wajib tiap putaran — hari ini 219 + 106 + 290 = **508 nama**.
10. Tulis markdown lewat Write/Python, jangan heredoc Bash (**menagih lagi hari ini**: heredoc gagal pada
    skrip lensa; f-string Python juga tidak boleh memuat backslash).
11. Urutkan demand per `u30`, bukan `totalUsers`.
12. Lensa kapabilitas (10/11/13) wajib tiap putaran — lensa domain sudah kering lima putaran.

---

## 11. Status & note untuk build ke depan

### ❗ Angka yang mendahului seluruh daftar di atas

| Keadaan | v7 (2026-09-19) | **Hari ini** |
|---|---:|---:|
| Folder lokal | 245 | **290** |
| **Belum terbit di akun mana pun** | 148 | **185** |
| — punya `actor.json` lengkap | 148 | **184** |
| Terbit di `xtracto` + `fanndev` | 313 | 325 |

**Delta tiga hari: +45 folder, +12 terbit.** Kecepatan membangun ~4× kecepatan menerbitkan. Delapan actor
yang dibangun minggu ini semuanya masih privat: `discord-server-scraper`, `etsy-ultimate-data-extractor`,
`alfagift-scraper`, `noon-scraper`, `mobile-de-scraper`, `glints-jobs-scraper`, `techinasia-scraper`,
`movie-tv-data-extractor`.

Runbook publish tidak berubah dan masih siap: **`scratchpad/publish_ready_v7.py`** (REST murni, token dari
env, dry-run bawaan, `--max` batch kecil, `--memory 1024` **wajib** karena `apify-actor-start` menagih
1 event per GB, resumable lewat `output/publish_log_v7.jsonl`).

```bat
set APIFY_TOKEN=<token>
python scratchpad/publish_ready_v7.py --scan                       :: tarik keadaan terkini
python scratchpad/publish_ready_v7.py --publish --max 3            :: dry-run
python scratchpad/publish_ready_v7.py --publish --max 3 --apply    :: eksekusi
python scratchpad/publish_ready_v7.py --run --max 5 --memory 1024 --apply
```

### Tabel status kandidat — siap build / perlu satu langkah / terblokir

| # | Kandidat | Rak | Pembeli aktif rak | Penjual memungut | Permukaan | Status |
|---|---|---:|---:|---:|---|---|
| 1 | **Verifikasi email bulk** | $1.675 | 6.481 | 11 | tanpa situs target | 🟢 **siap build** — uji port 25 di Apify dulu (10 baris) |
| 2 | **SofaScore multi-cabang** | $1.122 (tenis) | 2.707 | 8 | ✅ 200/64 KB via DoH | 🟢 **siap build** — reuse `espn-betting-odds-scraper` |
| 3 | **Copart salvage** | $160 | 990 user | 4 | ✅ 36.303 baris, paginasi dalam | 🟢 **siap build** — kecil tapi sejam jadi |
| 4 | **WeChat 公众号 (Sogou)** | $562 | 873 | 3 | ✅ 10 kartu/halaman | 🟢 **siap build** — tautan berumur pendek |
| 5 | **Discord username checker** | $14.271 | 469 | 7 | ✅ anonim | 🟡 **siap build, tapi whale-dependent** + batas etis |
| 6a | `tcgplayer` mode sales-history | $4.364 | 6 | 1 | rak sendiri | 🟢 **jam-an** — penambahan mode |
| 6b | Resy availability | $811 | 157 | 5 | ✅ dengan `api_key` publik | 🟡 **sisi Resy saja** (OpenTable 403) |
| 7 | Yandex Market | $869 | 67 | **1** | ✅ 1,97 MB, harga nyata | 🟡 **penjual tunggal $868** — uji ulang dari IP Apify |
| 8 | Kleinanzeigen Immobilien | $228 | — | 2 | ✅ (v7) | 🟡 carry-over, selector sudah dipetakan |
| 9 | Transkrip YouTube | **$23.104** | 7.439 | 19 | ❌ 200/0 KB ×4 | 🔴 **terblokir kredensial** — butuh `APIFY_TOKEN` + RESIDENTIAL |
| 10 | Apple Maps | $4.890 | 32 | 1 | 🔒 MapKit JS berbayar | ⚠️ **keputusan $99/tahun** |
| 11 | Registry bisnis AS (SoS) | $307 | 309 | 5–6 | ✅ Socrata terbuka per negara bagian | 🟡 **50 situs berbeda** — hanya layak jika digeneralisasi |

### Urutan eksekusi yang saya sarankan

**#0 — Terbitkan yang sudah jadi.** 185 folder, 184 lengkap, biaya nyaris nol, nol engineering.
Ini mendahului setiap baris di §8 karena setiap actor baru berakhir di langkah yang sama.

**#1 — Uji port 25 di runtime Apify** (satu actor tempel, 10 baris, <15 menit). Hasilnya menentukan bentuk
produk #1, dan tidak ada yang bisa dikerjakan di luar Apify untuk menjawabnya.

**#2 — Build verifikasi email bulk.** (§8 #1) 6.481 pembeli aktif, incumbent gagal 24,7%, tanpa permukaan
yang bisa ditutup. Kandidat paling mungkin selesai dalam satu sesi.

**#3 — Build SofaScore multi-cabang.** (§8 #2) Permukaan terverifikasi hari ini, skema & README sudah ada
dari dua actor olahraga yang sudah jadi. **Ingat DoH saat tes lokal.**

**#4 — Kalibrasi harga `xtracto`.** (§9) Empat putaran tertunda, dan gap-nya sekarang terukur:
**$0,57/pembeli vs $25–150/pembeli** di rak niche yang andal. Ambil pendapatan riil 30 hari dari Console,
bandingkan dengan $532,24 hasil perhitungan korpus untuk mendapat faktor koreksinya, lalu ubah
**2–3 actor saja** dan tunggu satu siklus 30 hari sebelum menyentuh sisanya.

**#5 — Copart + WeChat** (§8 #3, #4) — dua actor kecil, dua endpoint masing-masing, keduanya mengisi
kelas kapabilitas yang kosong.

**#6 — `tcgplayer` sales-history + Resy** (§8 #6) — jam-an, bukan harian.

**#7 — Transkrip YouTube** begitu `APIFY_TOKEN` ada (§8 #7). **Jangan riset ulang, langsung probe.**

**#8 — Recon yang sudah ditutup, jangan diulang tiap putaran:** `hrs.de`, `housesigma.com`,
`handelsregister.de`, USPTO, trip.com, IAAI, OpenTable, LoopNet, Coupang, DoorDash, Underdog.

### Ditolak permanen (bertambah putaran ini)

PII & skip-trace (`realtyapi`, `dievio`, `data_link_miner`, `build_matrix/company-employees-scraper`,
`webcrawlerr/dubai-property-crawler`, `gauravsaran/dubai-*`, RocketReach, Apollo, Instantly,
`eduair94/whatsapp-data-lookup`, Truecaller) · TecDoc (lisensi B2B) · darkweb · view/traffic generator ·
`handelsregister.de` (timeout ×3, DNS terverifikasi normal) · USPTO merek dagang · trip.com · `hrs.de` ·
`housesigma.com` · **`dev00/synthid-remover` dan sekelasnya** (menghapus watermark provenance AI —
$251/bulan dari 804 pembeli, tetap ditolak) · **unduh video/audio YouTube** ($3.788 rak, 10 penjual —
melanggar ToS platform, dan `entertained_rattlesnake/youtube-audio-segment-downloader` sendiri gagal 21,6%) ·
**IAAI** (Imperva, 200/3,5 MB tanpa baris lot).
