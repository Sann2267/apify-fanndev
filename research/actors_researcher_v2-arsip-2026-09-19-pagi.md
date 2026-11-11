# Riset Pasar Apify Store — v2 (putaran 2026-09-19)

**Tanggal riset:** 2026-09-19
**Permintaan putaran ini:** daftar actor dengan demand tinggi / stats tinggi di Apify Store, khususnya dua pola —
(A) *total runs banyak tapi user sedikit*, (B) *total user banyak tapi saingan sedikit* — lalu **dedupe wajib**
terhadap akun [`xtracto`](https://api.apify.com/v2/store?username=xtracto) supaya tidak membangun yang sudah ada.

## Dedupe tiga lapis (snapshot hari ini, ditarik ulang 2026-09-19)

| Lapis | Jumlah | Angka | Snapshot |
|---|---:|---|---|
| `xtracto` (akun lama yang kamu sebut) | **217 actor** | 955 pembeli aktif (u30) · **166 dari 217 actor punya ≥1 pembeli** · 46.352 run sukses/30 hari | `output/xtracto-full-v6.json` |
| `fanndev` (akun push saat ini) | **94 actor** | 96 u30 · 89 actor punya pembeli · 1.397 run sukses/30 hari | `output/fanndev-full-v6.json` |
| Folder lokal repo ini | **245 folder** | — | `scratchpad/_dedupe_names_v6.json` |
| **Gabungan nama unik untuk dedupe** | **460** | — | `scratchpad/_dedupe_blob_v6.txt` |

**Perubahan akun sejak 2026-09-15:** `fanndev` naik 83 → **94** (baru: `ecommerce-platform-market-share-scraper`,
`google-hotels-rate-comparison-scraper`, 4 actor Google Maps, `haystack-tv-scraper`, `psa-card-cert-lookup-scraper`,
`shopify-store-analyzer`, `short-interest-filings-scraper`, `snapchat-profile-spotlight-scraper`).
`xtracto` turun 218 → 217 (`capterra-b2b-scraper` hilang dari Store).
`clutch-agency-directory-scraper` (rekomendasi #1 putaran lalu) **sudah ada sebagai folder lokal** — belum terbit di `fanndev`.

**Verifikasi duplikat untuk seluruh shortlist putaran ini:** semua nama di §5–§8 dicek satu per satu terhadap
ketiga lapis. **Nol tabrakan.** Yang tersaring keluar karena sudah ada: `clutch` (folder lokal),
`northdata-companies-scraper`, `idealista-property-scraper`, seluruh vein TikTok, `tcgplayer-price-scraper`.

## Data mentah putaran ini

| File | Isi |
|---|---|
| `output/scan-v6-corpus.json` | **24.055 actor unik** — 21 kategori × 7 band user × offset 0–900 |
| `output/scan-v6-domains.json` | **1.797 vein dikelompokkan per DOMAIN** |
| `output/scan-v6-domains-clean.json` | vein yang sama **setelah lantai kebisingan `ok30 ≥ 60`** (§9 Koreksi 3) |
| `output/scan-v6-top-money.json` | 400 actor dengan MRR terukur tertinggi |
| `scratchpad/lens_v6_out.txt`, `veins_v6_wide.txt`, `veins_v6_clean.txt`, `demand_v6.txt` | keluaran 5 lensa |

Skrip: `scratchpad/scan_v6.py`, `money_v6.py`, `lens_v6.py`, `probe_v6.py`, `probe_v6b.py`, `probe_v6c.py`,
`probe_v6d.py`, `probe_v6e.py`.
Arsip: `actors_researcher_v2-arsip-2026-09-15.md` (+ `-12-sore`, `-12-pagi`, `-09-07`) dan `ACTOR_MARKET_RESEARCHER_NEW.md` (50 babak).

---

## 1. Ringkasan eksekutif

Korpus 24.055 actor. **MRR terukur seluruh Store = $739.815/bulan** setelah tiga perbaikan model harga di §9 —
angka ini **1,9× lipat lebih besar dari putaran lalu** ($392k), bukan karena pasarnya tumbuh, tapi karena model
lama diam-diam memberi $0 pada ribuan actor. Dari korpus, **3.821 actor memungut ≥$5/bulan**.

**Empat hal yang keluar dari putaran ini:**

1. **Pola A dan pola B tetap seperti tiga putaran sebelumnya** — bagus sebagai *penjelas*, buruk sebagai *penyaring*.
   Pola A: dari 32 teratas hanya **4 punya uang nyata dan permukaan yang belum tertutup**. Pola B: dari 17 rak,
   **1 yang hidup, terbuka, dan bukan PII** (Telefonbuch DE). Daftar lengkap + alasan tiap baris gugur ada di §3 dan §4.
2. **Model harga diperbaiki tiga kali** (§9). Yang paling mahal: v5 hanya membaca `eventTieredPricingUsd.GOLD`,
   padahal **mayoritas actor memakai `eventPriceUsd` datar** — jadi mereka dihitung $0. Ini yang mengubah peta:
   `macrocosmos/reddit-scraper` naik dari "$0" jadi **$1.677**, `build_matrix/company-employees-scraper` jadi **$2.018**.
3. **Gotcha statistik baru yang membatalkan sejumlah kandidat: `ok30` punya lantai palsu ~29.**
   4.339 actor melaporkan **tepat 29** run sukses/30 hari dan **4.376 actor punya `ok30` > 0 dengan nol pembeli**.
   Setiap taksiran MRR PPE yang bertumpu pada `ok30` < 60 adalah **kebisingan, bukan pendapatan** (§9 Koreksi 3).
   Ini langsung membunuh 3 kandidat yang tadinya terlihat besar — termasuk satu yang "menghasilkan $2.052".
4. **Satu kandidat baru lolos sampai Pass 5b dengan permukaan terverifikasi terbuka: `dastelefonbuch.de`**
   — dan uniknya ia memenuhi **pola A dan pola B sekaligus** (25 user, 157.210 run, 43.618 run sukses/30 hari,
   1 penagih). Bentuk outputnya identik dengan actor Google Maps lead-gen yang baru saja kamu terbitkan. (§6)

Tiga kandidat terbuka lain yang lebih kecil tapi murah dibangun: **fragrantica.com** ($209), **goodreads.com** ($105),
**idealo.de** ($63). Ditambah carry-over yang masih berdiri: **gelbeseiten.de** ($92) dan klaster Eropa putaran lalu.

**Tuas terbesar putaran ini bukan actor baru, melainkan dua celah produk di rak sendiri** (§8): pesaing menjual
**riwayat penjualan TCGplayer seharga $5.594/bulan dari 6 pembeli** sementara `xtracto/tcgplayer-price-scraper`
berhenti di 2 user; dan klaster data perusahaan Jerman menghasilkan $807+$353 untuk orang lain sementara
`xtracto/northdata-companies-scraper` duduk di 6 pembeli.

---

## 2. Papan atas pasar — di mana demand sebenarnya berada (konteks, bukan target)

Diurut per **pembeli aktif 30 hari** (`u30`), bukan per total user. Ini ukuran demand yang benar: `totalUsers`
menumpuk sejak actor lahir, `u30` adalah orang yang benar-benar memakainya bulan ini.

| u30 | Users | Runs | MRR terukur | Actor |
|---:|---:|---:|---:|---|
| 43.265 | 397.489 | 196,2 jt | $25.840 | `apify/instagram-scraper` |
| 37.207 | 608.870 | 39,4 jt | $5.828 | `compass/crawler-google-places` |
| 30.957 | 175.639 | 8,0 jt | **$0** | `apify/rag-web-browser` (gratis) |
| 27.281 | 220.224 | 115,9 jt | $14.498 | `apify/instagram-profile-scraper` |
| 23.071 | 288.429 | 126,2 jt | **$34.072** | `clockworks/tiktok-scraper` |
| 18.034 | 158.581 | 3,9 jt | $527 | `curious_coder/linkedin-jobs-scraper` |
| 17.682 | 184.088 | 119,6 jt | $21.938 | `apify/google-search-scraper` |
| 9.617 | 70.739 | 28,9 jt | $23.753 | `harvestapi/linkedin-profile-scraper` |
| 6.361 | 43.880 | 7,7 jt | **$30.633** | `harvestapi/linkedin-profile-search` |

Dan lima actor yang **uangnya besar padahal pembelinya segelintir** — ini bentuk yang paling relevan buat kamu:

| MRR | u30 | Users | Run sukses/30h | Actor | Baca |
|---:|---:|---:|---:|---|---|
| **$13.627** | 27 | 73 | 272.268 | `entertained_rattlesnake/youtube-subtitle-scraper-ai` | 27 pembeli, $505/pembeli |
| $12.930 | 236 | 1.565 | 258.596 | `eduair94/whatsapp-data-lookup` | ❌ PII nomor telepon |
| **$11.650** | 13 | 224 | 2.329.985 | `dev00/discord-username-checker` | **13 pembeli, 2,3 juta run** — bulk checker, bukan scraper |
| **$5.594** | 6 | 61 | 54.307 | `scraped/tcgplayer-sales-history` | **6 pembeli → celah produk rak sendiri (§8)** |
| $7.000 | 70 | 3.594 | 3.778 | `peakydev/leads-scraper` | FLAT $100 — pelajaran harga lama, masih berdiri |

---

## 3. POLA A yang kamu minta — "runs banyak, user sedikit"

Filter: `totalUsers ≥ 15` **dan** `totalRuns ≥ 100.000`, diurutkan runs-per-user, dari korpus 24.055.

| runs/user | Users | u30 | Runs | MRR | Model | Actor | Vonis |
|---:|---:|---:|---:|---:|---|---|---|
| 114.508 | 212 | 4 | 24,3 jt | $100 | FLAT | `alien_force/facebook-scraper-pro-rental` | model sewa + gagal 53,7% |
| 79.316 | 32 | 3 | 2,5 jt | $36 | FLAT | `canadesk/apple-app-store-plus` | App Store, rak jenuh |
| 75.396 | 42 | 3 | 3,2 jt | $0 | FREE | `apify/monitoring-checker-schema` | infrastruktur Apify |
| **71.734** | **16** | 1 | 1,1 jt | **$698** | PPE | `apikit/upcheck` | uptime checker — 1 pembeli, $0,01/run |
| 65.295 | 56 | 19 | 3,7 jt | $0 | FREE | `apify/s3-uploader` | infrastruktur |
| 48.545 | 19 | 1 | 0,9 jt | $20 | FLAT | `canadesk/career-scraper-plus` | 1 pembeli |
| 42.714 | 96 | 10 | 4,1 jt | $0 | FREE | `apify/monitoring-checker-run-status` | infrastruktur |
| 40.896 | 61 | 0 | 2,5 jt | $0 | PPE | `thescrappa/google-maps-advanced-search-scraper` | Google Maps, jenuh |
| 39.034 | 334 | 4 | 13,0 jt | $28 | FLAT | `devisty/google-search` | SERP, jenuh total |
| **29.487** | **880** | 27 | 25,9 jt | **$2.018** | PPE | `build_matrix/company-employees-scraper` | ⚠️ naik dari "$0" (§9) — tapi **PII karyawan**, ditolak |
| 26.364 | 29 | 1 | 0,8 jt | $25 | FLAT | `jupri/apple-apps` | App Store |
| **23.481** | **21** | 1 | 0,5 jt | **$770** | PPE | `knagymate/hrs-reviews-scraper` | ⭐ carry-over #1, masih berdiri — **diprobe putaran ini (§7)** |
| 21.322 | 1.078 | 1 | 23,0 jt | $50 | FLAT | `muhammad_usama/Github-Apify-Linkedin-data-scraper` | LinkedIn, tutup |
| **20.838** | **1.034** | 85 | 21,5 jt | **$1.677** | PPE | `macrocosmos/reddit-scraper` | ⚠️ naik dari "$0" (§9) — Reddit, rak jenuh + risiko API |
| 17.441 | 180 | 13 | 3,1 jt | $5 | PPE | `saswave/amazon-seller-monitoring` | sudah punya 5 actor Amazon |
| 15.282 | 62 | 6 | 0,9 jt | $18 | PPE | `saswave/noon-seller-monitoring` | Noon 403 Akamai (§7) |
| **15.194** | **2.110** | 30 | 32,1 jt | **$2.070** | FLAT | `making-data-meaningful/tecdoc` | ❌ data berlisensi B2B — ditolak permanen |
| **15.172** | **61** | 6 | 0,9 jt | **$5.594** | PPE | `scraped/tcgplayer-sales-history` | ⭐ **celah produk rak sendiri (§8)** |
| 12.221 | 2.202 | 55 | 26,9 jt | $503 | PPE | `novi/fast-tiktok-api` | TikTok konsumen tertutup SlardarWAF |
| 11.609 | 405 | 1 | 4,7 jt | $0 | FREE | `danielmilevski9/google-maps-pins-map-ocr` | gratis, gagal 100% |
| **10.850** | **224** | 13 | 2,4 jt | **$11.650** | PPE | `dev00/discord-username-checker` | 🟡 bulk *checker* — bentuk produk, bukan niche data |

**Vonis pola A (putaran keempat berturut-turut):** dari 32 teratas, **4 punya uang nyata dan permukaan yang belum
tertutup** — HRS, TCGplayer sales-history, Discord username checker, dan Upcheck. Sisanya infrastruktur Apify gratis,
vein jenuh, PII, atau berlisensi. Pola ini menemukan **"actor yang dipakai terus-menerus"**, bukan "actor yang dibayar" —
dan dua hal itu jarang bertemu. Yang berubah putaran ini: setelah harga datar ikut dibaca (§9), **tiga baris yang
dulu tertulis "$0" ternyata memungut ribuan dolar** (`reddit-scraper`, `company-employees-scraper`, `fast-tiktok-api`).

**Pelajaran bentuk produk dari pola ini:** dua pemenang teratas bukan scraper katalog, tapi **lookup massal**
(`upcheck`, `discord-username-checker`: 2,3 juta run dari 13 pembeli). Pola itu = satu input → satu jawaban kecil,
dipanggil berulang-ulang dalam loop. Actor `xtracto` yang paling mendekati bentuk ini (`psa-card-cert-lookup-scraper`)
baru 6 run.

---

## 4. POLA B yang kamu minta — "user banyak, saingan sedikit"

Filter: total user vein ≥ 1.500 **dan** ≤8 seller di rak yang sama. Kolom **"memungut"** hanya menghitung seller
dengan harga ≠ $0 (perbaikan yang ditetapkan 2026-09-18 — jumlah seller mentah melebih-lebihkan persaingan).

| Rak (domain) | Seller | Memungut | Users | u30 | Runs | MRR | $/pembeli | Dedupe | Vonis |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `scraptik` | 1 | 1 | 4.562 | 893 | 13,1 jt | **$2.272** | $2,54 | baru | ❌ **vein = merek penjual, bukan situs target** — `scraptik.com` menjual API TikTok-nya sendiri; permukaan TikTok konsumen tetap SlardarWAF |
| `realtyapi` | 1 | 1 | 15.096 | 770 | 4,6 jt | $1.592 | $2,07 | lama | ❌ PII / skip-trace — ditolak permanen |
| `upwork` | 4 | 3 | 2.905 | 53 | — | $1.262 | $23,82 | lama | ❌ tembok lama; `jupri/upwork` gagal 8,3% |
| `trustpilot` | 4 | 1 | 5.203 | 88 | — | $1.100 | $12,50 | **SUDAH PUNYA** | — |
| `yelp` | 3 | 3 | 1.821 | 148 | — | $987 | $6,67 | **SUDAH PUNYA** | — |
| `expedia` | 4 | 3 | 1.638 | 141 | — | $851 | $6,03 | **SUDAH PUNYA** | — |
| `ozon` | 6 | 3 | 2.099 | 550 | 0,5 jt | $784 | $1,43 | baru | 🟠 uang ada, **permukaan 403** (diverifikasi 2026-09-15) |
| `dievio` | 1 | 1 | 15.951 | 535 | — | $763 | $1,43 | baru | ❌ `Leads-Scraper-apollo-zoominfo-rental` = PII lead-gen |
| `apollo` | 7 | 4 | 18.214 | 1.782 | 3,2 jt | $426 | $0,24 | lama | ❌ PII, $/pembeli terlalu tipis |
| `similarweb` | 2 | 1 | 4.098 | 221 | — | $145 | $0,66 | lama | ❌ 202 challenge (§7) |
| `dastelefonbuch` | 2 | **1** | 28 | 8 | 157 rb | **$131** | $16,36 | **baru** | ✅ **satu-satunya yang hidup — lihat §6** |
| `instantly` | 2 | 1 | 4.447 | 592 | — | $89 | $0,15 | lama | ❌ email-finder = PII |
| `naukrigulf` | 8 | 3 | 20.812 | 1.806 | — | $59 | **$0,03** | baru | ❌ **20 ribu user menghasilkan $59** — rak jobs India praktis gratis |
| `gmgn` | 6 | 1 | 2.116 | 66 | — | $36 | $0,55 | lama | ❌ monopoli 98% |
| `wellfound` | 5 | 2 | 3.542 | 454 | — | $21 | $0,05 | **SUDAH PUNYA** | — |
| `patreon` | 2 | 0 | 2.969 | 13 | — | $2 | $0,12 | lama | ❌ rak kosong karena gratis |
| `onlyfans` | 1 | 0 | 1.719 | 13 | — | $1 | $0,05 | lama | ❌ gratis |

**Vonis pola B: 1 kandidat hidup dari 17.** Sama seperti tiga putaran sebelumnya, rak dengan banyak user dan sedikit
seller hampir selalu kosong **karena alasan**: datanya PII (`realtyapi`, `apollo`, `instantly`, `dievio`), satu pemain
memonopoli (`gmgn`), permukaannya tertutup (`ozon`, `upwork`), veinnya cuma merek penjual (`scraptik`), atau semua
actornya gratis (`patreon`, `onlyfans`, `naukrigulf`). **Mode kebohongan keempat yang baru terlihat putaran ini:**
*vein = nama vendor API, bukan nama situs* — `scraptik` terlihat seperti rak $2.272 dengan 1 seller, padahal itu
vendor yang menjual API-nya sendiri dan tidak ada permukaan yang bisa kamu tiru.

---

## 5. LENSA KE-3 (yang produktif) — vein beruang dengan sedikit penagih

Penyaring utama sejak 2026-09-12: **MRR vein ≥$50** DAN **≤3 seller yang benar-benar memungut**, dijalankan di
1.797 vein domain **setelah lantai kebisingan `ok30 ≥ 60`** (§9 Koreksi 3). Hanya baris yang **belum pernah dibahas
di arsip mana pun dan bukan milik sendiri** yang dihitung sebagai kandidat baru; sisanya carry-over.

| Rak | MRR | Seller | Memungut | Users | u30 | $/pembeli | Incumbent teratas | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| **dastelefonbuch / telefonbuch** | **$131** | 2 | **1** | 36 | 10 | $16,36 | `santamaria-automations/telefonbuch-de-scraper` PPE, **43.618 run sukses/30h** | ✅ **terbuka, siap build (§6)** |
| **fragrantica** | **$209** | 5 | 2 | 588 | 22 | $9,51 | `lexis-solutions/fragrantica` FLAT **$29** (6.462 ok30) | ✅ **terbuka (§7)** |
| **goodreads** | **$105** | 2 | **1** | 653 | 7 | $15,00 | `epctex/goodreads-scraper` FLAT **$15** (8.769 ok30) | ✅ **terbuka (§7)** |
| **idealo** | $63 | 4 | **1** | 205 | 13 | $4,87 | `ecomscrape/idealo-product-scraper` FLAT $30 | ✅ **terbuka (§7)** |
| handelsregister | $807 | 3 | 2 | 306 | 35 | $23,07 | `radeance/handelsregister-api` PPE $647 | 🟠 host **timeout di 3 profil TLS** (§7) |
| propwire | $465 | 3 | 1 | 610 | 66 | $7,05 | `memo23/propwire-leads-scraper` PPE | ❌ 403 Imperva (§7) |
| builtwith | $357 | 1 | 1 | 629 | 118 | $3,02 | `builtwith/builtwith-official-technology-scraper` | ❌ actor resmi pemilik data — bukan target |
| zoover | $295 | 2 | 1 | 4 | 2 | **$147,69** | `knagymate/zoover-reviews-scraper` PPE (59.078 ok30) | ❌ **403 Cloudflare** (§7) — carry-over gugur |
| compass | $187 | 2 | 1 | 18 | 1 | $187,49 | `nanoteki/compass-scraper` PPE | ❌ **418 "blocked from your region"** (§7) |
| slickdeals | $156 | **1** | 1 | 21 | 3 | $52,02 | `powerai/slickdeals-search-scraper` PPE (1.643 ok30) | ❌ 403 Cloudflare (§7) |
| meesho | $134 | 3 | 2 | 1.232 | 30 | $4,47 | `ecomscrape/…` FLAT $20, **gagal 16,1%** | ❌ 403 Akamai (§7) |
| bandeyu | $292 | 1 | 1 | 267 | 12 | $24,32 | `imageaibot/midjourney-bot` | ❌ generator gambar AI, bukan scraping |
| gelbeseiten | $92 | 4 | **1** | 587 | 19 | $4,83 | `plowdata/gelbe-seiten` FLAT **$10** (16.704 ok30) | ✅ **terbuka** — carry-over, belum dibangun |
| marktplaats | $114 | 10 | 3 | 364 | 54 | $2,11 | `panjan/marktplaats` FLAT $20 | ✅ terbuka (carry-over) |
| bandsintown | $174 | 1 | 1 | 76 | 6 | $29,00 | `lexis-solutions/bandsintown-scraper` FLAT $29 | ✅ terbuka (carry-over, API publik) |
| housesigma | $63 | 5 | **1** | 243 | 10 | $6,54 | `memo23/apify-housesigma-cheerio` FLAT $21 | 🟡 SPA 4 KB, **host API menjawab JSON** (§7) |
| costco · streeteasy · pricecharting · dubizzle · myslabs · drushim · noon · allegro | $63–$204 | — | 1–3 | — | — | — | — | ❌ semuanya tertutup (§7) |

---

## 6. LENSA 4 & 5 (baru putaran ini)

### Lensa 4 — "incumbent rapuh": rak beruang yang pemuncaknya sering gagal

Gagasannya: tingkat kegagalan tinggi pada actor yang **tetap dibayar** = baji keandalan, bukan tembok.

| Rak | MRR | Memungut | Pemuncak | Gagal | Run sukses/30h | Vonis |
|---|---:|---:|---|---:|---:|---|
| upwork | $1.262 | 3 | `jupri/upwork` FLAT $30 | **8,3%** | 330.517 | ❌ permukaan Upwork tetap tertutup |
| skyscanner | $240 | 1 | `jupri/skyscanner-flight` FLAT $30 | **18,2%** | 60.895 | ⚠️ **SUDAH PUNYA** `xtracto/skyscanner-scraper` (14 pembeli) — pesaing rusak 1 dari 5 run |
| streeteasy | $204 | 2 | `jupri/streeteasy-scraper` FLAT $30 | **38,6%** | 373.403 | ❌ 403 Cloudflare — kegagalannya menjelaskan kenapa |
| zillow | $151 | 1 | `jupri/zillow-scraper` FLAT $30 | **41,1%** | 35.250 | ⚠️ sudah punya |
| dexscreener | $105 | 1 | `crypto-scraper/dexscreener-tokens-scraper` | **21,0%** | 4.867 | ⚠️ sudah punya |

**Vonis lensa 4:** tidak melahirkan target baru, **tapi menemukan dua baji di rak sendiri** — `skyscanner` dan
`zillow`: di kedua rak itu pesaing yang memungut $30/bulan gagal di 18–41% run-nya, dan actor `xtracto` untuk
kedua situs itu sudah ada tapi belum dijual dengan sudut "yang ini tidak gagal".

### Lensa 5 — "permintaan muda": u30/users tinggi

Rasio pembeli-bulan-ini terhadap pengguna-sepanjang-masa ≥0,25 = rak yang baru ramai, bukan warisan lama.

| Rak | MRR | Seller | Memungut | Users | u30 | Rasio | Vonis |
|---|---:|---:|---:|---:|---:|---:|---|
| ozon | $784 | 6 | 3 | 2.099 | 550 | 0,26 | 🟠 permukaan 403 |
| foundit | $12 | 7 | 1 | 1.119 | 282 | 0,25 | ❌ $12 untuk 282 pembeli |
| coles | $10 | 3 | **0** | 410 | 278 | 0,68 | ❌ nol penagih |
| aldi | $7 | 4 | 1 | 324 | 216 | 0,67 | ❌ $7 |

**Vonis lensa 5:** lensa ini **mati** — 4 baris, semuanya gratis atau tertutup. Rak yang tumbuh cepat di Apify
tumbuh cepat justru karena gratis. Jangan diulang putaran depan kecuali digabung dengan syarat `$/pembeli ≥ $1`.

---

## 7. Hasil probe permukaan — Pass 5 + Pass 5b (2026-09-19)

40+ probe, dua profil TLS (chrome124 + safari17_0), plus putaran koreksi URL. **200 bukan bukti** — kolom terakhir
adalah Pass 5b: apakah data yang dicari benar-benar ada di badan respons.

### ✅ Terbuka (data terverifikasi ada)

| Target | Status | Isi sebenarnya (Pass 5b) |
|---|---|---|
| `dastelefonbuch.de/Suche/Friseur/Berlin` | 200 / 329 KB (chrome & safari) | **11 `vcard` · 15 `itemprop=name` · 10 `streetAddress` · 10 `addressLocality` · 20 telepon · 1 ld+json**; paginasi `?pi=2` balas 317 KB dengan isi berbeda |
| `fragrantica.com/designers/Dior.html` | 200 / 2.597 KB | **691 link `/perfume/`** |
| `fragrantica.com/perfume/…` | 200 / 1.839 KB | 14 link nota parfum + blok rating |
| `goodreads.com/search?q=dune` | 200 / 186 KB | **40 link `/book/show/` + 20 blok rating** |
| `idealo.de/preisvergleich/…?q=iphone+15` | 200 / 841 KB | **49 `/OffersOfProduct/<id>` · 52 harga € · 36 judul produk** |
| `gelbeseiten.de/suche/friseur/berlin` | 200 / 320 KB | 100 `data-realid` · 264 `mod-Treffer` (carry-over, masih berdiri) |

### 🟠 Perlu satu sesi recon (menjawab, tapi data belum ketemu)

| Target | Status | Temuan |
|---|---|---|
| `hrs.de/hotel/deutschland/berlin/` | 200 / 281 KB | 10 link `/hotel/`; halaman detail 229–259 KB dengan **98 kemunculan "rating" tapi 0 `reviewText`** — data ada di **35–41 potongan `self.__next_f.push` (RSC Next.js)**, harus didekode. Ini rak $770 & rpu 23.481 |
| `housesigma.com` | 200 / 4 KB | SPA kosong, **tapi `housesigma.com/bkv2/api/…` menjawab JSON sungguhan** (`{"status":false,…"API endpoint Not Found"…"API":"v5.38.205"}`) — endpoint-nya cuma perlu ditemukan |
| `bundesanzeiger.de/pub/de/suchen` | 200 / 21 KB (req ke-1 **dan** ke-2 dalam sesi yang sama) | cangkang JSF; pencarian butuh postback `jakarta.faces`, bukan GET |
| `makerworld.com/en/search/models` | 200 / 1.540 KB | `__NEXT_DATA__` **694 KB tapi 0 `designId` dan 0 link `/models/`**; `api/v1/design-service/design/search` balas `{"total":0,"hits":null}` |
| `subito.it` · `target.com` | 200 / 377 KB · 127 KB | Next.js; 118 harga tapi 0 kartu item (Subito), 0 `tcin` (Target) |

### ❌ Tertutup (tembok baru yang diverifikasi putaran ini)

| Target | chrome | safari | Bentuk tembok |
|---|---|---|---|
| `slickdeals.net` | 403 / 5 KB | 403 | Cloudflare "Just a moment…" |
| `pricecharting.com` | 403 / 5 KB | 403 | Cloudflare |
| `zoover.nl` | 403 / 5 KB | 403 | Cloudflare — **carry-over `knagymate/zoover` gugur** |
| `streeteasy.com` | 403 / 5 KB | 403 | Cloudflare |
| `meesho.com` (web **dan** `/api/v1`) | 403 | 403 | Akamai "Access Denied" |
| `costco.com` | 403 | 403 | Akamai |
| `noon.com` | 403 | 403 | Akamai |
| `propwire.com` | 403 / 1 KB | 403 | Imperva |
| `dubizzle.com` | 200 / 6 KB | 200 | Imperva "Pardon Our Interruption" (200 palsu) |
| `compass.com` | **418** | 418 | "Access to this resource is blocked from your region" — geo, bukan bot |
| `drushim.co.il` | 403 | 403 | 403 Forbidden polos |
| `allegro.pl` | 403 | 403 | — |
| `similarweb.com` · `builtwith.com` | 202 | 202 | challenge tertunda |
| `handelsregister.de` · `racenet.com.au` · `equibase.com` | **Timeout** | Timeout/SSLError | tidak menjawab di chrome124/chrome131/firefox133 — **rak $807 handelsregister tidak bisa dinilai dari sini** |
| `myslabs.com` | 200 / 381 KB (beranda) | — | beranda punya 75 link listing, **tapi `/search`, `/browse`, `/listings` semuanya timeout/404** |

**16 probe menutup 14 kandidat dan membuka 6, dengan biaya beberapa menit.** Tiga di antaranya (`dubizzle`,
`makerworld`, `housesigma`) balas **200 dengan halaman besar tanpa satu pun baris data** — alasan Pass 5b tetap wajib.

---

## 8. Rekomendasi

### #1 — `dastelefonbuch.de` (direktori bisnis Jerman) — **kandidat baru terkuat**

**Kenapa teratas:** satu-satunya kandidat yang **memenuhi kedua pola yang kamu minta sekaligus** dan permukaannya
terverifikasi terbuka hari ini.

- **Pola A:** 25 user, **157.210 run** (rpu 5.617) — dipakai terus-menerus oleh segelintir orang.
- **Pola B:** rak 2 seller, **hanya 1 yang memungut**, dan yang memungut itu mencatat **43.618 run sukses/30 hari**
  dengan kegagalan 0,1% — jadi angkanya bukan kebisingan lantai `ok30` (§9).
- **$/pembeli $16,36** — tiga kali lipat median rak direktori.
- **Nol tabrakan** di `xtracto`, `fanndev`, dan 245 folder lokal.

**Bukti permukaan (chrome124 + safari17_0, 2026-09-19):**

```
GET https://www.dastelefonbuch.de/Suche/Friseur/Berlin  ->  200, 329 KB
  vcard ....................... 11      itemprop=name ........... 15
  itemprop=streetAddress ...... 10      addressLocality ......... 10
  itemprop=telephone / .tel ... 20      application/ld+json ..... 1
GET .../Suche/Friseur/Berlin?pi=2      ->  200, 317 KB, isi berbeda (paginasi jalan)
```

**Note build:**
- Skemanya **microdata `itemprop`, bukan `__NEXT_DATA__`** — parser CSS/XPath biasa, tanpa browser. Ambil
  `name`/`streetAddress`/`addressLocality`/`postalCode`/`telephone` langsung dari atribut itemprop; jangan regex teks.
- **11 hasil per halaman** — paginasi `?pi=N` wajib ada di input, dan hitung biaya per halaman, bukan per hasil.
- **Bentuk output = kembaran actor Google Maps lead-gen yang baru kamu terbitkan** (nama · alamat · telepon ·
  kategori · rating). Kalau skema outputnya disamakan, pembeli bisa memakai keduanya sebagai satu pipeline
  lead-gen "Jerman + global" — itu sudut jualannya.
- **Klasterkan dengan `gelbeseiten.de`** (§ bawah): satu parser direktori DE → dua actor. Gelbe Seiten sudah
  terverifikasi terbuka dua putaran berturut-turut dan incumbent-nya cuma memungut FLAT **$10**.
- **Harga:** satu-satunya penagih di rak ini memakai PPE. Karena outputnya baris-lead, PPE per baris masuk akal
  di sini (beda dengan Clutch) — tapi **jangan di bawah $0,003/baris**; median vein direktori $0,002 dan
  `plowdata` membuktikan pasar mau membayar FLAT $10 untuk data yang sama.

### #2 — Klaster "referensi konsumen" (fragrantica + goodreads), dua actor, satu bentuk parser

| Brand | Bukti permukaan terbuka | MRR rak | Memungut | Incumbent |
|---|---|---:|---:|---|
| **fragrantica.com** | 2.597 KB · **691 link `/perfume/`** · halaman parfum 1.839 KB dengan nota + rating | $209 | 2 | `lexis-solutions/fragrantica` FLAT **$29** |
| **goodreads.com** | 186 KB · **40 link `/book/show/` + 20 rating** | $105 | **1** | `epctex/goodreads-scraper` FLAT **$15** |

Keduanya database referensi dengan bentuk data identik (entitas → atribut → rating → agregat ulasan), jadi
**satu kerangka parser → dua actor**. Fragrantica punya sudut yang tidak dimiliki incumbent: **piramida nota
parfum** (top/middle/base) yang bisa dikeluarkan sebagai kolom terstruktur, bukan teks.
*Note:* kedua incumbent memakai FLAT ($29 dan $15) — **jangan masuk dengan PPE $0,002/item**; rak ini terbukti
membayar langganan bulanan.

### #3 — `idealo.de` (perbandingan harga Jerman)

Rak $63, **1 penagih** (`ecomscrape` FLAT $30). Permukaan terbuka lebar: 841 KB, **49 `productId` + 52 harga +
36 judul** per halaman pencarian. Rak paling kecil di antara ketiga rekomendasi, tapi biaya bangunnya juga
paling kecil karena bentuk datanya sama persis dengan actor e-commerce yang sudah kamu punya.
*Note:* ambil `/OffersOfProduct/<id>` sebagai kunci produk — itu ID stabil Idealo; jangan pakai slug judul.

### #4 — Dua celah produk di rak sendiri (uang terbesar, engineering paling kecil)

**4a. Riwayat penjualan TCGplayer.** `scraped/tcgplayer-sales-history` menghasilkan **$5.594/bulan dari 6 pembeli**
(54.307 run sukses/30 hari, harga: `apify-actor-start` **$0,10** + $0,003/item), sementara
`xtracto/tcgplayer-price-scraper` berhenti di **2 user, 90 run**. Yang dibayar bukan harga saat ini, tapi
**comps penjualan historis** — data yang sama yang membuat `ebay-sold-comps-scraper` punya 16 pembeli.
Ini penambahan mode di actor yang sudah ada, bukan actor baru.
*Note harga:* perhatikan bahwa pesaing memungut **$0,10 per start** — 200× lipat dari start `xtracto` ($0,0005).

**4b. Klaster data perusahaan Jerman.** `radeance/handelsregister-api` $807 dan `silentflow/northdata-scraper` $353
sementara `xtracto/northdata-companies-scraper` duduk di **6 pembeli**. Permukaan `handelsregister.de` **timeout
di tiga profil TLS dari sini** (bukan 403 — mungkin blok jaringan/geo), jadi ini **recon dulu lewat proxy DE**,
bukan build. `bundesanzeiger.de` (laporan keuangan tahunan) adalah pasangan alaminya dan cuma butuh alur JSF postback.

---

## 9. Koreksi metode putaran ini — empat perbaikan yang membatalkan angka sebelumnya

### Koreksi 1 — harga datar (`eventPriceUsd`) akhirnya ikut dibaca

`money_v5.py` hanya membaca `eventTieredPricingUsd.GOLD`. Kenyataannya **mayoritas actor PPE memakai
`eventPriceUsd` datar** — dan semuanya diam-diam dihitung **$0**. Akibatnya di arsip lama:
`macrocosmos/reddit-scraper` tertulis "$0" (sebenarnya **$1.677**), `build_matrix/company-employees-scraper`
tertulis "$0" (sebenarnya **$2.018**). Seluruh kolom MRR di arsip 2026-09-07/12/15 **under-count secara sistematis**.

### Koreksi 2 — jangan jumlahkan *semua* event; event ≥$1 adalah pass langganan

Percobaan pertama putaran ini menjumlahkan seluruh event per run dan menghasilkan MRR Store **$3,47 juta/bulan** —
jelas mustahil. Dua sebabnya:
1. Actor multi-mode punya 3–12 event per-item yang **tidak pernah menyala bersamaan** dalam satu run
   (`crawloop/tractorhouse-scraper`: `scraped-listings-row` **dan** `scraped-details-row`). Yang benar:
   **event one-time + SATU event primer per-item**.
2. Sebagian actor menaruh **`day-pass $4,99` dan `monthly-pass $49` sebagai `isOneTimeEvent`**.
   Dijumlahkan mentah, `zen-studio/ticombo-scraper` terlihat memungut **$54 per run** → "$2.052/bulan" palsu
   dari 1 pembeli. Setelah pass dipisah (ditagih per periode × u30, bukan per run), rak itu jatuh ke ~$5 dan
   **hilang dari shortlist**. Ambang: event one-time **≥$1 = pass**, **<$1 = biaya start**.

Hasil akhir: **$739.815/bulan** untuk 24.055 actor.

### Koreksi 3 — `ok30` punya lantai palsu ~29, dan itu membunuh kandidat

Sebaran `stats.publicActorRunStats30Days.SUCCEEDED` di korpus:

| nilai | 29 | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| jumlah actor | **4.339** | 2.074 | 897 | 730 | 551 | 471 | 405 | 349 | 345 |

**4.376 actor punya `ok30` > 0 padahal pembeli 30 harinya nol.** Artinya angka di bawah ~60 bukan lalu lintas
pelanggan (kemungkinan run uji pengembang atau lantai privasi). Setiap MRR PPE yang dihitung dari `ok30` kecil
adalah fiksi. Contoh yang gugur putaran ini: `dubizzle` ("$295" — dua actor dengan `ok30`=29 masing-masing),
`ticombo`, dan sebagian besar rak $60-an ber-`ok30`≈30. **Aturan baru: abaikan komponen PPE ketika `ok30 < 60`;
untuk actor FLAT tidak ada masalah karena hitungannya `u30 × harga`.**

### Koreksi 4 — ekonomi akun `xtracto` diukur ulang (menggantikan §8 arsip 2026-09-15)

| Angka | 2026-09-15 | **2026-09-19** |
|---|---:|---:|
| Actor | 218 | **217** |
| Pembeli aktif (u30) | 934 | **955** |
| Run sukses / 30 hari | 44.984 | **46.352** |
| Lantai PPE terukur | $566,40 | **$573,38** |
| — di antaranya `apify-actor-start` | $418,05 | **$423,24 (74%)** |
| Actor **dengan** ≥1 pembeli | "≈150 tanpa pembeli" | **166 dari 217 punya pembeli** (hanya 51 yang nol) |

Klaim lama bahwa "median $0,002 adalah artefak ~150 actor tanpa pembeli" **salah** — yang tanpa pembeli hanya 51.
Tetap benar: **74% lantai pendapatan akun datang dari `apify-actor-start`, bukan dari data yang dijual.**
Ingat juga multiplier memori (1 event per GB): dengan default 4096 MB, biaya start yang sebenarnya ditagih
ke pembeli **4× angka di atas**.

---

## 10. Status carry-over

| Kandidat | Prioritas sebelumnya | Angka hari ini | Status baru |
|---|---|---|---|
| **`clutch.co`** | 🔴 #2 build (2026-09-15) | Folder `clutch-agency-directory-scraper` **ada**, belum terbit di `fanndev`. Rak $357, `epctex` masih gagal 13,1% | 🟢 **Dibangun — tinggal publish** |
| **Kalibrasi harga `xtracto`** | 🔴 #1 non-build | Belum berubah; angka diperbarui di §9 Koreksi 4 | 🔴 **Tetap #1 non-build. Belum dikerjakan.** |
| **Klaster direktori Eropa** (Gelbe Seiten · Marktplaats · Ceneo · Firmy.cz) | 🔴 #3 build | Gelbe Seiten $92 (1 penagih, FLAT $10) · Marktplaats $114 · Firmy $64 · Ceneo $80 | 🟡 **Masih berdiri, naik prioritas** — gabung dengan Telefonbuch jadi satu klaster DE |
| **HRS / klaster review perjalanan `knagymate`** | 🟠 #5 recon | HRS naik $502 → **$770**, rpu 23.481. **Diprobe pertama kali hari ini**: halaman hidup, ulasan ada di potongan RSC | 🟠 **Recon separuh jalan** — tinggal dekode `self.__next_f` |
| **Zoover** (bagian klaster yang sama) | 🟠 | $295, $147/pembeli | ❌ **Gugur — 403 Cloudflare** |
| **Apple Maps** | 🟠 #4 recon | Tidak diprobe ulang; `cdn.apple-mapkit.com/ma/bootstrap` 401 | 🟠 Tidak bergerak |
| **Indeed Reviews · Kleinanzeigen Immobilien** | 🟡 #3 | Indeed $143 (5 penagih) · Kleinanzeigen $228 (2 penagih) | 🟡 Dipertahankan |
| **`xtracto/skyscanner-scraper` rusak** | 🟠 #4 | 14 pembeli; **pesaing `jupri` gagal 18,2% tapi tetap memungut $30** | 🟠 **Naik jadi baji, bukan sekadar perbaikan** (§6 lensa 4) |
| **TecDoc · realtyapi · RocketReach · darkweb** | ❌ ditolak | $2.070 · $1.592 · $350 · — | ❌ Tetap ditolak |
| **Tembok lama** (yellowpages, homedepot, carfax, ozon, opentable, seloger, mercari, spotify, weibo, nobroker, autotrader.co.uk) | ❌ | Tidak diprobe ulang | ❌ Tetap tutup |

---

## 11. Status & note untuk build ke depan

### Urutan eksekusi

**#0 — Publish `clutch-agency-directory-scraper`.** Sudah dibangun, belum terbit. Prasyarat publish (dari memori
proyek): `push` → `apify call` sampai ada satu run sukses → `PUT isPublic`. *Note harga:* dua pesaing di rak itu
memungut FLAT $40; jangan terbitkan dengan PPE $0,002/baris.

**#1 — Kalibrasi harga `xtracto` (nol engineering, tertunda dua putaran).**
- **1a. Ambil satu angka dari Console:** pendapatan riil 30 hari. Lalu
  `faktor_item_per_run = (pendapatan_riil − $423,24) ÷ $150,14`. Semua keputusan harga bergantung pada angka ini.
- **1b. Dua actor yang memang di bawah pasar** (tidak perlu menunggu 1a): `tiktok-trending-scraper`
  (38 pembeli, item $0,00075 → **$0,002**) dan `threads-post-detail-scraper` (18 pembeli, $0,00099 → **$0,003**).
- **1c. Dua yang kemahalan relatif:** `ebay-sold-comps-scraper` ($0,025/run, 16 pembeli) dan
  `shopee-product-detail` ($0,025/run, 23 pembeli, di atas p90 veinnya).
- **1d. Baru setelah 1a:** uji PPE vs FLAT pada **satu** actor. `shopee-shop-scraper` (65 pembeli) tetap kandidat
  paling aman. *Note:* jangan ubah 217 actor sekaligus — ubah 2–3, tunggu satu siklus 30 hari, baca `u30` sebelum/sesudah.

**#2 — Build klaster direktori Jerman: `dastelefonbuch.de` → `gelbeseiten.de`.** (§8 #1)
Satu parser, dua actor, dua permukaan terverifikasi terbuka. *Note:* Telefonbuch pakai microdata `itemprop`
(11 hasil/halaman, paginasi `?pi=N`); Gelbe Seiten pakai `data-realid` (100/halaman). **Samakan skema output-nya
dengan actor Google Maps lead-gen** supaya bisa dijual sebagai satu pipeline.

**#3 — Tambah mode `sales-history` ke `tcgplayer-price-scraper`.** (§8 #4a) Pesaing: $5.594/bulan dari 6 pembeli.
*Note:* ini penambahan mode + perubahan harga start, bukan actor baru. Pasangkan dengan
`fanndev/psa-card-cert-lookup-scraper` yang sudah ada → satu klaster kartu koleksi.

**#4 — Build klaster referensi konsumen: `fragrantica.com` → `goodreads.com`.** (§8 #2)
*Note:* kedua incumbent memakai FLAT ($29 / $15). Sudut pembeda Fragrantica = piramida nota parfum terstruktur.

**#5 — Recon HRS (rak $770, rpu 23.481) — satu sesi, bukan build.** (§7)
Yang sudah diketahui: `hrs.de` hidup, halaman hotel 229–259 KB, **rating ada tapi bukan di HTML mentah** —
35–41 potongan `self.__next_f.push`. Yang perlu dikerjakan: dekode potongan RSC itu (pola yang sama dengan blob
base64 k-injected di actor Amazon customer-insights). Kalau ulasan tidak ada di sana, tinggalkan —
`zoover` sudah gugur dan `trip.com` sudah diketahui cangkang.

**#6 — Recon dua permukaan yang menjawab tapi belum ketemu datanya:** `housesigma.com/bkv2/api/…`
(host API membalas JSON versi 5.38.205 — tinggal temukan endpoint) dan `bundesanzeiger.de` (postback JSF).
Keduanya murah, masing-masing < 1 jam.

**#7 — `handelsregister.de` lewat proxy Jerman.** Rak $807 dengan 2 penagih, tapi host **timeout dari sini**
di chrome124/chrome131/firefox133. Ini satu-satunya rak >$500 yang belum bisa dinilai. Kalau proxy DE juga timeout,
coret permanen.

### Aturan proses — yang berubah putaran ini

1. **Jangan percaya `ok30` di bawah 60.** Lantai palsu ~29 mengenai 4.339 actor. Abaikan komponen PPE-nya;
   untuk FLAT tidak masalah. (§9 Koreksi 3)
2. **Baca `eventPriceUsd` datar, bukan cuma `eventTieredPricingUsd.GOLD`.** Ini yang membuat model lama
   menulis "$0" untuk actor bernilai ribuan dolar. (§9 Koreksi 1)
3. **Event `isOneTimeEvent` ≥$1 adalah pass langganan, bukan biaya per run** — pisahkan, atau satu actor akan
   terlihat memungut $54/run. Ambang $1. (§9 Koreksi 2)
4. **Jumlahkan hanya `event one-time + SATU event primer per-item`**, bukan semua event — actor multi-mode punya
   sampai 12 event yang tidak pernah menyala bersamaan.
5. **Hitung seller yang MEMUNGUT, bukan seller yang hadir** (ditetapkan 2026-09-18, terbukti lagi putaran ini:
   `housesigma` 5 seller / 1 penagih, `gelbeseiten` 4 / 1, `goodreads` 2 / 1).
6. **Mode kebohongan ke-4 "seller sedikit": vein = merek vendor API, bukan situs target.** `scraptik` terlihat
   seperti rak $2.272 dengan 1 seller; itu perusahaan yang menjual API TikTok-nya sendiri. Cek selalu: apakah
   nama domain vein itu **punya permukaan publik yang bisa kamu scrape**, atau cuma nama penjualnya.
7. **Selalu Pass 5b.** Putaran ini `dubizzle`, `makerworld`, dan `housesigma` balas **200 dengan halaman 6 KB–1,5 MB
   tanpa satu pun baris data**. `makerworld` bahkan punya `__NEXT_DATA__` **694 KB berisi nol `designId`**.
8. **Timeout ≠ 403.** `handelsregister`, `racenet`, `equibase` tidak menjawab sama sekali di tiga profil TLS —
   itu bisa blok jaringan/geo (bandingkan `compass.com` yang terang-terangan menjawab **418 "blocked from your region"**).
   Jangan dicatat sebagai "WAF"; catat sebagai "belum bisa dinilai dari IP ini".
9. **Dedupe tiga lapis wajib tiap putaran** — `xtracto` (217) + `fanndev` (**94**, naik dari 83) + 245 folder lokal
   = 460 nama. Lapis kedua berubah tiap minggu; jangan pakai snapshot lama.
10. **Tulis file markdown lewat Write/Python, jangan heredoc Bash** (heredoc menelan satu level backslash dan
    gagal pada markdown berisi backtick + kutip). Juga: **f-string Python tidak boleh memuat backslash** di dalam
    ekspresi — dua skrip probe putaran ini gagal karena itu.
11. **Urutkan demand per `u30`, bukan `totalUsers`.** `totalUsers` menumpuk sejak actor lahir;
    `compass/crawler-google-places` punya 608 ribu user tapi 37 ribu pembeli aktif, sementara
    `apify/instagram-scraper` punya lebih sedikit user tapi lebih banyak pembeli aktif.

### Ditolak permanen (tidak berubah)

PII & skip-trace (`realtyapi`/`one-api/skip-trace` $1.592, `dievio`/`x_guru` lead rental $763, RocketReach $350,
Apollo, Instantly, `eduair94/whatsapp-data-lookup` $12.930, `build_matrix/company-employees-scraper` $2.018,
Truecaller, Dubai unit-number, Tinder/Hinge), TecDoc (lisensi B2B), darkweb, view/traffic generator.
