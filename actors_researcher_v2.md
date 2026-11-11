# Riset Pasar Apify Store — v2 (putaran 2026-09-22 sore / v9)

**Tanggal riset:** 2026-09-22 (putaran kedua hari ini)
**Permintaan putaran ini:** daftar actor dengan demand tinggi / stats tinggi di Apify Store, khususnya dua pola —
(A) *total runs banyak tapi user sedikit*, (B) *total user banyak tapi saingan sedikit* — lalu **dedupe wajib**
terhadap akun [`xtracto`](https://api.apify.com/v2/store?username=xtracto) supaya tidak membangun yang sudah ada.

> Putaran pagi (v8) diarsipkan ke `actors_researcher_v2-arsip-2026-09-22-v8.md`.

**Baca ini dulu — apa yang benar-benar baru di v9.** Korpus ditarik ulang penuh (24.197 actor) tapi jaraknya
cuma ~2 jam dari v8, jadi **angka pasar praktis tidak bergerak** dan saya tidak akan pura-pura sebaliknya.
Nilai putaran ini ada di dua hal lain: **4 lensa baru (16–19)** yang belum pernah dijalankan, dan
**34 permintaan probe permukaan** ke sepuluh target yang belum pernah diuji — hasilnya **3 permukaan terbuka
baru, 1 gerbang TLS yang bisa dilewati, 6 tertutup, 2 separuh terbuka**, plus empat koreksi metode yang
masing-masing sempat hampir membuat saya salah vonis.

---

## Dedupe tiga lapis (snapshot ditarik ulang 2026-09-22 sore)

| Lapis | Jumlah | Angka | Snapshot |
|---|---:|---|---|
| `xtracto` (akun yang kamu sebut) | **219 actor** | 933 pembeli aktif (u30) · 164 actor punya ≥1 pembeli · **49.747** run sukses/30h | `output/xtracto-full-v9.json` |
| `fanndev` (akun push saat ini) | **106 actor** | 105 u30 · 94 actor punya pembeli · 1.807 run sukses/30h | `output/fanndev-full-v9.json` |
| Folder lokal repo ini | **291 folder** | **186 belum terbit** di akun mana pun (185 punya `actor.json` lengkap) | `scratchpad/_dedupe_names_v9.json` |
| **Gabungan nama unik untuk dedupe** | **509** | terbit di dua akun: 323 | `scratchpad/_dedupe_blob_v9.txt` |

Tidak ada perubahan angka akun sejak pagi (wajar, Store memperbarui stats harian). Folder lokal 290 → **291**:
tambahannya `bulk-email-verifier`, yaitu kandidat #1 v8 yang sudah kamu bangun hari ini.

### Verifikasi duplikat — tiap kandidat v9 dicek satu per satu

| Kandidat yang diuji putaran ini | Ada di `xtracto`/`fanndev`/lokal? | Keputusan |
|---|---|---|
| Woolworths AU / Coles / Aldi AU | **tidak ada sama sekali** (0 dari 509 nama) | ✅ aman dibangun |
| Liquipedia / esports | tidak ada | ✅ aman (tapi gugur karena robots, §7) |
| Product Hunt | tidak ada | ✅ aman |
| StubHub / tiket acara | `xtracto/eventbrite-events` (Eventbrite saja) | ✅ aman (tapi gugur, §7) |
| Crunchbase / pendanaan | tidak ada | permukaan tertutup |
| Upwork | `xtracto/fiverr-gigs-scraper` (Fiverr saja) | permukaan tertutup dari IP ini |
| Similarweb / estimasi trafik | `xtracto/semrush-website-overview` | permukaan tertutup |
| Weibo | `xtracto/bilibili-danmaku`, `rednote-xiaohongshu-scraper` | butuh akun → tolak |
| Depop | `poshmark-*` (3), `vinted-listings`, `grailed-listings` | separuh terbuka |
| **Google Trends** | **`xtracto/google-trends-scraper` — SUDAH ADA** | ⛔ bukan build baru → **reposisi** (§8 #2) |

**Nol tabrakan pada shortlist final.** Satu-satunya yang tersaring keluar karena sudah dimiliki adalah
Google Trends — dan justru itu temuan yang menarik, lihat §8 #2.

## Data mentah putaran ini

| File | Isi |
|---|---|
| `output/scan-v9-corpus.json` | **24.197 actor unik** — 21 kategori × 7 band user × offset 0–900 |
| `output/scan-v9-domains.json` / `-clean.json` | 1.793 vein per DOMAIN, versi bersih dilantai `ok30 ≥ 60` |
| `output/scan-v9-top-money.json` | 400 actor dengan MRR terukur tertinggi |
| `scratchpad/lens_v9_out.txt` | Lensa 1–8 (pola A, pola B, vein, incumbent rapuh, bookmark, penjual tunggal) |
| `scratchpad/lens_v9d_out.txt` | Lensa 13–15 (46 kelas kapabilitas, actor muda, harga yang diterima pasar) |
| **`scratchpad/lens_v9e_out.txt`** | **Lensa 16–19 BARU** (62 kelas kapabilitas gelombang kedua + 3 lensa ketidakpuasan) |
| `scratchpad/shelf_v9_out.txt` | angka rak per kandidat + status dedupe per rak |

Skrip: `scratchpad/{dedupe,scan,money,lens,lens_v9c,lens_v9d,lens_v9e,vein,shelf}_v9.py` +
probe `scratchpad/probe_v9{,b,c,d}.py`.

---

## 1. Ringkasan eksekutif

Korpus **24.197 actor**. MRR terukur seluruh Store **$746.812/bulan** mentah, **$726.223** setelah lantai
kebisingan `ok30 ≥ 60`. **3.712 actor** memungut ≥$5/bulan secara nyata. (v8 pagi: 24.194 · $747.631 ·
$727.034 · 3.713 — **pasar mendatar, tiga putaran berturut**.)

**Lima hal yang keluar dari putaran ini:**

1. **Permukaan terbuka baru yang paling berguna: Woolworths Australia — dan sebabnya adalah metode HTTP.**
   Jalur `POST /apis/ui/Search/products` (yang dipakai actor-actor incumbent) membalas **403 Access Denied**
   di tiga profil TLS dan di HTTP/1.1. Jalur **`GET` dengan querystring yang sama persis membalas 200 berisi
   2.257 produk** untuk kueri "milk", lengkap dengan harga, stok, barcode, dan 115 field per produk.
   Itu menjelaskan kenapa tiga actor Australia di rak ini **gagal 34,6%, 56,7%, dan 73,6%** sementara
   1.488 pembeli aktif tetap memakainya.
2. **Rak paling ramai yang kamu belum sentuh ternyata dihargai nol.** Grosir Australia: 17 actor,
   11 penjual, **1.488 pembeli aktif** — total **$115/bulan** untuk seluruh rak, yaitu **$0,08 per pembeli**.
   Ini bukan alasan untuk melewatkannya (biayanya sejam kerja), tapi harganya jangan ikut lantai mereka.
3. **Vein media YouTube kalau digabung adalah $26.892/bulan dengan ~10.400 pembeli aktif dan NOL actor
   milikmu** — transkrip ($23.104, 19 penjual, 7.439 pembeli) plus unduh video/audio ($3.788, 10 penjual,
   2.961 pembeli). Diuji lagi hari ini: halaman watch memang membalas `playabilityStatus: OK` dengan 27 format,
   tapi **26 format adaptif datang tanpa `url` sama sekali** dan satu-satunya format progresif memakai
   `signatureCipher`. Kedua produk itu tergantung pada **satu gerbang yang sama**. Memecahkannya sekali
   membuka dua rak — ini pekerjaan rekayasa dengan imbalan tertinggi di seluruh portofolio.
4. **Pola B per-domain kering untuk putaran KEENAM.** Dari 17 vein yang lolos filter "user banyak, penjual
   sedikit", satu-satunya baris yang bukan PII, bukan merek vendor API, dan belum kamu punya adalah
   **`upwork`** ($1.302, 4 penjual, 3 memungut, $23/pembeli) — dan permukaannya **403 identik di lima profil
   TLS** dari IP ini. Pola A juga tetap didominasi infrastruktur Apify sendiri (`monitoring-*`, `s3-uploader`).
5. **Empat koreksi metode, semuanya nyaris membuat vonis salah** (§10): robots.txt yang harus diurai
   per-blok (Liquipedia hampir lolos padahal `api.php` dilarang untuk `User-agent: *`), metode HTTP sebagai
   sumbu gerbang tersendiri, `pageSize` di luar himpunan yang diizinkan yang membuat paginasi *tampak* jalan,
   dan **JSON 200 berisi data sungguhan yang tetap dekoy karena seluruh parameternya diabaikan** (StubHub).

---

## 2. Papan atas pasar — konteks, bukan target

Diurut per **pembeli aktif 30 hari** (`u30`), bukan `totalUsers`.

| u30 | Users | Runs | MRR bersih | Actor |
|---:|---:|---:|---:|---|
| 43.149 | 400.062 | 198,0 jt | $25.892 | `apify/instagram-scraper` |
| 36.585 | 612.497 | 39,7 jt | $5.582 | `compass/crawler-google-places` |
| 30.413 | 177.303 | 8,1 jt | **$0** | `apify/rag-web-browser` (gratis) |
| 27.091 | 222.350 | 116,9 jt | $14.706 | `apify/instagram-profile-scraper` |
| 23.303 | 289.928 | 127,5 jt | **$33.578** | `clockworks/tiktok-scraper` |
| 16.915 | 186.233 | 120,3 jt | $21.527 | `apify/google-search-scraper` |
| 13.275 | 15.648 | 0,6 jt | $600 | `apify/web-fetch` — rasio u30/users **0,85** |

Bentuk yang paling relevan buat kamu — **uang besar, pembeli segelintir** (tidak berubah dari pagi):

| MRR | u30 | ok30 | $/pembeli | Actor | Status permukaan |
|---:|---:|---:|---:|---|---|
| **$14.177** | 13 | 2.835.386 | **$1.091** | `dev00/discord-username-checker` | ✅ terbuka & anonim (v8) |
| **$14.074** | 26 | 281.208 | $541 | `entertained_rattlesnake/youtube-subtitle-scraper-ai` | ❌ gerbang (§8 #3) |
| $6.700 | 67 | 3.600 | $100 | `peakydev/leads-scraper` | PII — ditolak permanen |
| **$4.890** | 32 | 209.950 | $153 | `zen-studio/apple-maps-scraper-pro` | 🔒 keputusan $99/thn |
| **$4.364** | 6 | 42.371 | **$727** | `scraped/tcgplayer-sales-history` | 🟢 celah mode di rak sendiri |

---

## 3. POLA A yang kamu minta — "runs banyak, user sedikit"

Filter: `users ≥ 15`, `runs ≥ 100.000`, diurut `runs/user`. **Sepuluh teratas korpus v9:**

| runs/user | Users | u30 | Runs | MRR | Actor | Dedupe | Baca |
|---:|---:|---:|---:|---:|---|---|---|
| 79.523 | 32 | 3 | 2,54 jt | $36 | `canadesk/apple-app-store-plus` | belum punya | model sewa |
| 75.782 | 42 | 3 | 3,18 jt | $0 | `apify/monitoring-checker-schema` | — | **infrastruktur Apify** |
| **72.180** | 16 | 1 | 1,15 jt | **$694** | `apikit/upcheck` | belum punya | 1 pembeli = whale, cek uptime URL |
| 65.774 | 56 | 19 | 3,68 jt | $0 | `apify/s3-uploader` | — | infrastruktur Apify |
| 48.545 | 19 | 1 | 0,92 jt | $20 | `canadesk/career-scraper-plus` | belum punya | `ok30` = 29 → **lantai palsu** |
| 42.870 | 96 | 10 | 4,12 jt | $0 | `apify/monitoring-checker-run-status` | — | infrastruktur Apify |
| 40.897 | 61 | 0 | 2,49 jt | $0 | `thescrappa/google-maps-advanced-search-scraper` | Maps sudah punya 4 | `ok30` = 28 |
| 39.034 | 334 | 4 | 13,0 jt | $28 | `devisty/google-search` | — | `ok30` = 35 → lantai palsu |
| 36.694 | 142 | 26 | 5,21 jt | $0 | `apify/monitoring-runner` | — | infrastruktur Apify |
| 29.524 | 882 | 29 | 26,0 jt | $1.902 | `build_matrix/company-employees-scraper` | — | **PII** |

**Pembacaan yang sama seperti lima putaran sebelumnya, dan sekarang sudah pantas disebut aturan:**
pola A murni menghasilkan tiga kelas — (a) infrastruktur Apify sendiri yang dipanggil actor lain, (b) model
sewa/whale dengan 1–3 pembeli, (c) PII. Dari sepuluh baris di atas **hanya `apikit/upcheck` yang berbentuk
produk nyata**, dan itu pun $694 dari **satu** pembeli. Pola A tetap **penjelas, bukan penyaring**.

---

## 4. POLA B yang kamu minta — "user banyak, saingan sedikit"

Filter vein: `users ≥ 1.500`, `penjual ≤ 8`. **Seluruh 17 baris yang lolos:**

| MRR vein | Penjual | Memungut | Users | u30 | Vein | Verdict |
|---:|---:|---:|---:|---:|---|---|
| $2.205 | 1 | 1 | 4.585 | 915 | `scraptik` | **merek vendor API**, bukan situs |
| $1.562 | 1 | 1 | 15.413 | 769 | `realtyapi` | **PII / skip-trace** |
| **$1.302** | **4** | **3** | **2.909** | 56 | **`upwork`** | **satu-satunya baris nyata** → permukaan 403 (§7) |
| $1.040 | 4 | 1 | 5.204 | 84 | `trustpilot` | sudah punya |
| $983 | 3 | 3 | 1.827 | 148 | `yelp` | sudah punya |
| $890 | 4 | 3 | 1.645 | 145 | `expedia` | sudah punya |
| $763 | 1 | 1 | 16.003 | 525 | `dievio` | PII |
| $607 | 6 | 4 | 2.134 | 546 | `ozon` | 403 di 7/7 profil (babak 52) |
| $377 | 7 | 4 | 18.274 | 1.758 | `apollo` | PII |
| $142 | 2 | 1 | 4.122 | 222 | `similarweb` | permukaan 403 (§7) |
| $71 · $58 · $36 · $21 · $1 · $1 · $0 | 1–8 | 0–3 | — | — | `instantly`, `naukrigulf`, `gmgn`, `wellfound`, `patreon`, `onlyfans`, `anti-captcha` | PII / sudah punya / tidak memungut |

**Putaran keenam berturut-turut tanpa kandidat baru dari pola B per-domain.** Mode kebohongan "penjual
sedikit" tetap empat: penjual memungut $0, monopoli, PII, dan vein yang sebetulnya merek vendor API.
Lensa kapabilitas (§5–§6) sekarang satu-satunya jalur yang masih menghasilkan.

---

## 5. Lensa BARU putaran ini — 16, 17, 18, 19

`scratchpad/lens_v9e.py`. Lensa 16 memakai **62 kelas kapabilitas gelombang kedua** yang sengaja **tidak
mengulang satu pun** dari 46 kelas v8 — tujuannya mencari titik buta berikutnya sebesar "transkrip YouTube",
yang dulu lolos enam putaran karena dijual sebagai *kemampuan*, bukan sebagai *situs*.

### Lensa 16 — kelas yang punya uang, punya pembeli, dan **tidak kamu punyai** (`*** CELAH`)

| Rak/bln | Penjual memungut | Pembeli aktif | Kelas | Catatan permukaan |
|---:|---:|---:|---|---|
| $2.498 | 9 | 1.410 | **estimasi trafik situs** | Similarweb/Ahrefs — **403 di 5 profil TLS** (§7) |
| $991 | 8 | 661 | perbandingan harga | tersebar lintas situs; sebagian sudah kamu punya |
| $926 | 2 | 9 | monitor stok/ketersediaan | didominasi 1 whale (`apikit/upcheck` $694 dari 1 pembeli) |
| $880 | 9 | 259 | pendanaan/startup | Crunchbase — **DataDome 403** (§7) |
| $557 | 3 | 135 | esports | Liquipedia terbuka teknis tapi **dilarang robots** (§7) |
| $288 | 2 | 48 | speech-to-text | bertumpu pada unduhan media → gerbang yang sama dengan §8 #3 |
| $281 | 3 | 272 | social listening | Threads/Weibo/Reddit — Weibo butuh akun |
| $242 | 2 | 9 | IP geolocation | terlalu kecil |
| $191 | 2 | 55 | screenshot/render halaman | terlalu kecil |

Catatan jujur: kelas "captcha solving" muncul di puncak ($5.166) **karena kebocoran regex** — yang tertangkap
sebenarnya scraper email YouTube dan Upwork yang menyebut kata "captcha" di deskripsi. Jangan dipakai.
(Perbaikannya: cocokkan kelas pada `title`+`name` saja, bukan deskripsi — dicatat untuk v10.)

### Lensa 17 — incumbent rapuh berbobot pembeli (`u30 ≥ 150` **dan** gagal ≥ 15%)

| Skor (u30 × %gagal) | u30 | Gagal | Actor | Tindak lanjut |
|---:|---:|---:|---|---|
| 124.708 | 5.050 | **24,7%** | `account56/email-verifier` | ✅ sudah kamu jawab (`fanndev/bulk-email-verifier`) |
| 36.384 | 1.401 | **26,0%** | **`apify/google-trends-scraper`** | **kamu sudah punya actornya** → §8 #2 |
| 32.577 | 585 | 55,7% | `automation-lab/facebook-public-profile-scraper` | Facebook = jangan masuk |
| 24.052 | 507 | 47,4% | `zerobreak/google-hotels-scraper` | kamu sudah punya `google-hotels-rate` |
| 18.175 | 247 | **73,6%** | `getascraper/coles-scraper` | → §8 #1 |
| 15.769 | 278 | 56,7% | `dromb/coles-au-product-search-*` | → §8 #1 |
| 9.474 | 274 | 34,6% | `dromb/woolworths-au-product-search-*` | → §8 #1 |

**Tiga dari tujuh baris teratas adalah grosir Australia.** Itu bukan kebetulan: ketiganya memakai jalur
POST yang ditolak (§7).

### Lensa 18 & 19 — pasar tidak puas / minat tidak terkonversi

Lensa 18 (rating ≤ 3,4 dengan ≥3 ulasan dan u30 ≥ 80) menghasilkan 30 baris yang **hampir seluruhnya
raksasa sosial dan PII** (Instagram, Indeed, LinkedIn, Apollo) — artinya ketidakpuasan pasar terkonsentrasi
justru di rak yang tidak boleh/tidak sanggup kamu masuki. Dua baris yang berguna: `radeance/similarweb-scraper`
(rating 3,36, 175 pembeli) dan `pratikdani/crunchbase-companies-scraper` (**rating 1,49**, 60 pembeli) —
keduanya permukaannya tertutup (§7). Lensa 19 (bookmark ≥ 80 tapi bookmark/u30 ≥ 1,5) juga didominasi
LinkedIn/Instagram; satu-satunya baris non-PII yang menonjol adalah **`topaz_sharingan/Youtube-Transcript-Scraper-1`
(827 bookmark, 409 pembeli)** — lagi-lagi vein YouTube.

---

## 6. POLA A × POLA B digabung

Baris yang punya **runs/user tinggi**, **rak dengan ≤8 penjual memungut**, dan **bukan PII/infrastruktur/milik sendiri**:

| Actor | runs/user | Rak | Penjual memungut | Permukaan |
|---|---:|---:|---:|---|
| `dev00/discord-username-checker` | 12.822 | $14.271 | 7 | ✅ terbuka & anonim (v8) |
| `scraped/tcgplayer-sales-history` | 15.175 | $4.364 | 1 | rak sendiri — tinggal tambah mode |
| `entertained_rattlesnake/youtube-subtitle-scraper-ai` | 10.907 | $23.104 | 19 | ❌ gerbang (§8 #3) |
| `apikit/upcheck` | 72.180 | $926 | 2 | kapabilitas tanpa situs target; 1 pembeli |
| `clearpath/kleinanzeigen-immobilien-api-pro` | 10.704 | $228 | 2 | ✅ terbuka (v7) |

---

## 7. Hasil probe permukaan — Pass 5 / 5b / 5c / 5d / 5e (2026-09-22 sore)

**34 permintaan, 10 target baru.** Aturan tidak berubah: `200` tidak dihitung terbuka sampai regex bukti
menemukan baris data sungguhan — dan mulai putaran ini ditambah satu syarat: **parameter harus terbukti
berpengaruh** (lihat StubHub).

### ✅ Terbuka (data terverifikasi ada)

| Target | Hasil | Bukti |
|---|---|---|
| **Woolworths AU** `GET /apis/ui/Search/products?searchTerm=&pageNumber=&pageSize=` | 200 / 489–636 KB | `SearchResultsCount = 2.257` untuk "milk"; 24–36 produk/halaman; **115 field per produk** (Price, InstorePrice, WasPrice, IsOnSpecial, Barcode, Stockcode, CupPrice, IsInStock…); `pageNumber` 1/2/3 memberi Stockcode yang berbeda |
| Woolworths AU `GET /apis/ui/PiesCategoriesWithSpecials` | 200 / 827 KB | pohon kategori penuh, 5.070 penanda `NodeId`/`Description` |
| **Google Trends** `GET /trending/rss?geo=XX` | 200 / 19–21 KB | 10 `<item>` + `<ht:approx_traffic>` + `<ht:picture>` + 3 `<ht:news_item>` per item; **12 geo diuji semua 200** (US/ID/GB/IN/AU/DE/JP/BR/NG/PH/VN/TH; SG cuma 3 item, MY 7) |
| **Product Hunt** homepage | 200 / 1.748 KB | 79–80 penanda `votesCount` — **tapi hanya dari profil TLS tertentu**, lihat di bawah |
| Depop `GET /api/v1/shop/{id:int}/products/` | 200 | `{"meta":{"limit":24,"end":true},"products":[]}` — anonim & hidup, **tapi butuh id numerik** |

### ⚠️ Gerbang yang bentuknya penting

| Target | Bentuk gerbang | Detail |
|---|---|---|
| **Product Hunt** | **sidik jari TLS deterministik** | `chrome124` & `edge101` → **403 Cloudflare (5 KB)**; `chrome131`, `firefox133`, `safari17_0` → **200 (1.748–1.770 KB)**. Diulang berurutan: chrome124 tetap 403 *setelah* firefox133 sukses → **sidik jari, bukan rate limit** |
| **Woolworths AU** | **metode HTTP** | `POST /apis/ui/Search/products` → **403 Access Denied** di chrome124/safari17_0/firefox133 **dan** di HTTP/1.1; `GET` dengan parameter setara → **200 penuh**. `curl (92) HTTP/2 stream reset` yang muncul di POST pertama **bukan** tanda mati — dipaksa HTTP/1.1 ia berubah jadi 403 yang jujur |
| **YouTube (transkrip + unduh)** | token/IP, keempat–kelima kalinya | `watch` 200/1.323 KB `playabilityStatus: OK`, 27 format — **0 format punya `url`**, 26 adaptif tanpa `url` *maupun* `signatureCipher`, 1 progresif dengan `signatureCipher`. InnerTube `player`: WEB & MWEB → `UNPLAYABLE`, ANDROID & IOS → 400 `FAILED_PRECONDITION`, TVHTML5 → `ERROR` |
| **Google Trends** jalur lain | robots + laju | `robots.txt` UA `*` **melarang `/explore?` dan `/trends/explore?`** (RSS tidak dilarang); `api/explore` → **429** dua kali; `_/TrendsUi/data/batchexecute` → 400; `api/dailytrends` → **404 (pensiun)** |

### ❌ Tertutup / gugur putaran ini

| Target | Hasil | Tafsir |
|---|---|---|
| Similarweb `data.similarweb.com/api/v1/data` | **403 di 5 profil TLS**; `www` 202 cangkang kosong | tertutup dari IP ini |
| Upwork `/nx/search/jobs/` | **403 / 336 KB identik di 5 profil**; `/api/graphql/v1` → 401; feed RSS → 410/404 | IP/struktural, bukan TLS |
| Crunchbase (`/organization/…` dan `/v4/data/…`) | 403 "One moment, please…" (DataDome) di 5 profil | tertutup |
| Coles AU (halaman **dan** `/api/bff/products`) | 200 tapi isinya **Incapsula `_Incapsula_Resource`** | tertutup — kontras tajam dengan Woolworths |
| **Weibo** | `genvisitor` + `incarnate` **BERHASIL** (retcode 20000000, cookie `SUB`/`SUBP`/`SVB`/`SRT`/`SRF`) — tapi `m.weibo.cn` tetap `{"ok":-100}` → login; `s.weibo.com` → Sina Visitor System; `ajax/side/hotSearch` → 403 | **butuh akun** → ditolak (aturan yang sama yang menutup housesigma) |
| **Liquipedia** | api.php 200 & kaya (`search`, `categorymembers`, `parse` wikitext dengan 28 penanda prizepool) | **gugur karena kepatuhan**: `robots.txt` blok `User-agent: *` memuat `Disallow: /dota2/api.php` (dan tiap wiki lain). Jalur resmi `api.liquipedia.net/api/v3` → 403 `API key "" is not valid` = kunci gratis lewat registrasi |
| **StubHub** `/explore?method=getExploreEvents` | 200 JSON, 17 event **lengkap** (eventId, name, url, venueName, tanggal) | **DEKOY**: `q`, `limit`, `offset`, `categoryId` **semuanya diabaikan** — empat kueri berbeda memberi 17 event identik, dan kotanya mengikuti IP keluar (Jakarta). Halaman detail event → 403 |
| Depop `/api/v2` & `/api/v3/search/products` | **410 `Deprecated endpoint`** | pencarian mati; `www.depop.com` → Cloudflare 403 (251 KB) |

---

## 8. Rekomendasi

### #1 — Woolworths Australia (+ Aldi AU) — **permukaan terbuka, incumbent rusak, 1.488 pembeli**

**Angka rak (grosir Australia, seluruh korpus):** $115/bulan · 17 actor · 11 penjual (4 memungut) ·
**1.488 pembeli aktif** · 2.088 user · 21.912 run sukses/30h.

| MRR | u30 | ok30 | Gagal | Actor |
|---:|---:|---:|---:|---|
| $29 | 278 | 5.112 | **56,7%** | `dromb/coles-au-product-search-specials-stores-unofficial` |
| $21 | 242 | 2.808 | 0,0% | `solidcode/aldi-com-au-scraper` |
| $19 | 274 | 3.548 | **34,6%** | `dromb/woolworths-au-product-search-catalog-unofficial` |
| $16 | 96 | 2.629 | 0,2% | `clearpath/coles-scraper` |
| $5 | 260 | 4.339 | 0,0% | `scrapesage/woolworths-scraper` |

**Kenapa layak:** 1.488 pembeli aktif adalah basis terbesar di antara semua kandidat v9 yang permukaannya
benar-benar terbuka, dan sepertiganya memakai actor yang gagal sepertiga sampai tiga perempat run-nya.
Pola kerjanya **identik dengan `alfagift-scraper` dan `klikindomaret-scraper`** yang sudah kamu bangun —
katalog grosir, harga, stok, kategori.

**Kenapa harus sadar risikonya:** rak ini **dihargai $0,08 per pembeli**. Kalau kamu ikut lantai harga
mereka, hasilnya nol. Nilainya ada kalau (a) biayanya benar-benar sejam kerja, dan (b) kamu memasang harga
sendiri — grosir AU adalah data pemantauan harga kompetitif yang pembelinya bisnis, bukan hobiis.

**Yang sudah terpetakan, tinggal ditulis:**
- Cari: `GET https://www.woolworths.com.au/apis/ui/Search/products?searchTerm=<q>&pageNumber=<n>&pageSize=<24|36>&sortType=TraderRelevance`
- **`pageSize` hanya boleh 12, 24, atau 36** — 48 ke atas membalas **400**.
- **Tile bersponsor berulang di setiap halaman**: dengan `sortType=TraderRelevance` dan `pageSize=36`,
  tiap halaman mengembalikan **41** produk yang **5 di antaranya (`IsSponsoredAd`) sama persis di halaman
  berikutnya**. Dedupe per `Stockcode` wajib, atau datasetmu akan penuh duplikat senyap.
- Kueri tak dikenal membalas **200 dengan `SearchResultsCount = 0`**, bukan 404.
- Kategori: `GET /apis/ui/PiesCategoriesWithSpecials` (827 KB, seluruh pohon) — pakai ini untuk seeding.
- `/apis/ui/browse/category` menuntut parameter `formatObject` (tanpa itu: 400 `"FormatObject is required"`),
  dan dengan itu pun balasannya SEO-meta tanpa produk → **pakai jalur search, jangan browse**.
- `robots.txt` Woolworths melarang `/shop/search` (halaman HTML) tapi **tidak melarang `/apis/`**.
- Coles **tidak bisa** diikutkan (Incapsula). Aldi AU belum diprobe — satu jatah probe di v10.

### #2 — Google Trends: **kamu sudah punya actornya, yang salah posisinya**

Ini bukan build baru, dan justru karena itu ia naik ke urutan dua.

| | Milikmu | Incumbent |
|---|---|---|
| Actor | `xtracto/google-trends-scraper` | `apify/google-trends-scraper` |
| Pembeli aktif | **4** | **1.401** |
| Run 30h | 117 sukses / 7 timeout (**5,6% gagal**) | **gagal 26,0%** |
| Rating | — | 3,68 (32 ulasan) |

Rak Google Trends + tren platform lain: **$2.042/bulan, 18 penjual memungut, 4.101 pembeli aktif**.
Pemuncaknya `data_xplorer/google-trends-fast-scraper` ($511 dari 401 pembeli, gagal 0,1%) — jadi pasar
**jelas mau pindah** dari actor resmi yang rusak; mereka cuma tidak menemukanmu.

**Tindakan konkret (jam-an, bukan harian):** tambahkan mode `trending` yang memakai jalur yang terbukti
terbuka hari ini — `https://trends.google.com/trending/rss?geo=<XX>` — **12 geo terverifikasi 200**, tiap item
membawa judul, perkiraan trafik, gambar, dan tiga berita terkait. Ini juga satu-satunya jalur yang
**tidak dilarang `robots.txt`** (yang dilarang adalah `/explore?`). Lalu perbaiki judul/deskripsi agar
memuat kata kunci yang dicari orang yang kabur dari actor resmi.

### #3 — Vein media YouTube digabung: **$26.892/bulan, ~10.400 pembeli, nol actor milikmu**

| Kelas | Rak/bln | Penjual | Pembeli aktif | Pemuncak |
|---|---:|---:|---:|---|
| transkrip/subtitle | **$23.104** | 19 | 7.439 | `entertained_rattlesnake/youtube-subtitle-scraper-ai` ($14.074 dari 26 pembeli) |
| unduh video/audio | **$3.788** | 10 | 2.961 | `streamers/youtube-video-downloader` (**983 pembeli**, 21.156 user, gagal 1,8%) |

Bukti hari ini menegaskan keduanya **satu gerbang yang sama**: halaman watch memberi `playabilityStatus: OK`
dan 27 format, tapi **tanpa satu pun URL media**; seluruh jalur InnerTube `player` ditolak (UNPLAYABLE /
FAILED_PRECONDITION / ERROR). Sementara itu incumbent dengan **983 pembeli aktif gagal cuma 1,8%** — artinya
gerbangnya **bisa dilewati**, hanya bukan dari IP + tanpa mesin JS seperti sekarang.

**Ini satu-satunya item di daftar ini yang layak disebut proyek, bukan tugas.** Urutan ujinya:
(1) jalankan probe yang sama **dari runtime Apify** dengan `RESIDENTIAL` proxy — ini menjawab "IP atau bukan"
dalam satu run; (2) kalau URL muncul tapi terkunci `signatureCipher`, tambahkan solver player JS;
(3) baru putuskan produknya (transkrip dulu — raknya 6× lebih besar dan tidak perlu mengirim berkas media).
Jangan ulangi probe dari mesin lokal lagi: **lima putaran, lima hasil identik.**

### #4 — Carry-over v8 yang sudah terverifikasi terbuka dan belum dibangun

Tidak ada yang berubah sejak pagi; ketiganya masih siap dan tidak perlu riset lagi.

| Kandidat | Rak | Pembeli rak | Permukaan |
|---|---:|---:|---|
| **SofaScore multi-cabang** | $1.122 (tenis saja) | 2.707 | ✅ 200/64 KB **lewat DoH** (ingat blokir DNS ISP) |
| **Copart salvage** | $160 | 990 user | ✅ 36.303 baris/kueri, paginasi dalam |
| **WeChat 公众号 (Sogou)** | $562 | 873 | ✅ 10 kartu/halaman, tanpa antispider |

### #5 — Yang saya sarankan **tidak** dikerjakan putaran ini, dan sebabnya

| Kandidat | Sebab |
|---|---|
| Liquipedia / esports | `robots.txt` melarang `api.php` untuk semua UA — jalur legalnya butuh kunci LPDB (gratis, tapi itu keputusanmu, bukan temuan) |
| StubHub / tiket | API `explore` terbuka tapi **tidak bisa dikueri**; detail event 403 → tidak ada produk di baliknya |
| Product Hunt | permukaan bisa dilewati (TLS), tapi rak cuma **$202 dari 4 penjual memungut, 335 pembeli** |
| Depop | `/api/v1/shop/{id}` hidup, tapi tanpa resolver slug→id (www di balik Cloudflare) separuh produk tidak terjangkau |
| Upwork · Similarweb · Crunchbase · Coles · Weibo | tertutup dari IP ini / butuh akun (§7) |

---

## 9. Status carry-over dari v8 (pagi ini)

| # | Kandidat v8 | Status sore ini |
|---|---|---|
| 1 | Verifikasi email bulk | ✅ **dibangun & di-push** — `fanndev/bulk-email-verifier` 0.0.4, privat, 3 run cloud sukses. Port 25 terbukti tertutup di kedua jalur. **Sisa: keputusan produk**, bukan engineering |
| 2 | SofaScore multi-cabang | 🟢 siap build — belum disentuh |
| 3 | Copart | 🟢 siap build — belum disentuh |
| 4 | WeChat/Sogou | 🟢 siap build — belum disentuh |
| 5 | Discord username checker | 🟡 siap tapi whale-dependent (13 pembeli) + batas etis |
| 6a | `tcgplayer` mode sales-history | 🟢 penambahan mode di rak sendiri |
| 6b | Resy availability | 🟡 butuh header `ResyAPI api_key` publik |
| 7 | Yandex Market | 🟡 penjual tunggal $868 — uji ulang dari IP Apify |
| 9 | Transkrip YouTube | 🔴 naik pangkat jadi §8 #3 (digabung dengan unduh video) |
| 10 | Apple Maps | ⚠️ tetap keputusan $99/tahun |

---

## 10. Koreksi metode putaran ini

### Koreksi 12 — `robots.txt` harus diurai **per blok**, bukan dengan satu regex

Liquipedia punya **34 blok `User-agent`**. Regex `^User-agent:\s*\*\s*$` gagal menemukan bloknya (baris
memakai CRLF dan blok `*` ada di tengah, bukan di awal berkas), sehingga probe pertama menyimpulkan
"tidak ada aturan untuk UA `*`". Padahal blok itu ada dan memuat `Disallow: /dota2/api.php` — persis endpoint
yang barusan saya nyatakan terbuka. **Parser yang benar: normalkan `\r`, kumpulkan baris `User-agent`
berurutan sebagai satu grup, lalu tempelkan aturan yang mengikutinya ke setiap UA di grup itu.**
Dipakai ulang, parser ini juga yang menemukan bahwa `/apis/` Woolworths **tidak** dilarang dan
`/trending/rss` Google Trends **tidak** dilarang — dua izin yang menyelamatkan kandidat #1 dan #2.

### Koreksi 13 — **metode HTTP adalah sumbu gerbang tersendiri**

Woolworths: `POST /apis/ui/Search/products` → 403 Access Denied (3 profil TLS + HTTP/1.1).
`GET` dengan parameter yang setara → 200 berisi 2.257 produk. Sebelum ini saya hanya menguji sumbu
profil TLS, host, path, dan IP. **Tambahkan metode ke matriks.** Konsekuensi langsung: tiga actor incumbent
gagal 34–73% karena mengetuk pintu yang salah, dan rak itu sempat terlihat "sudah dikerjakan orang".

Turunannya: **`curl (92) HTTP/2 stream reset by server` bukan vonis.** Paksa HTTP/1.1 — di Woolworths
error itu berubah jadi 403 yang jujur, yang lalu mengarah ke uji GET.

### Koreksi 14 — `pageSize` di luar himpunan yang diizinkan membuat paginasi **tampak** jalan

Dengan `pageSize=36&sortType=TraderRelevance`, halaman 1, 2, 5, dan 20 semuanya mengembalikan produk pertama
yang sama — mudah disalahbaca sebagai "paginasi tidak didukung". Yang sebenarnya terjadi: server menyisipkan
**5 tile bersponsor yang dipatok di puncak setiap halaman** (jumlah item jadi 41, bukan 36). Dengan
`pageSize=24` paginasi terbukti benar (Stockcode berbeda tiap halaman). **Uji paginasi selalu dengan
membandingkan ID, jangan dengan melihat item pertama.**

### Koreksi 15 — 200 + JSON + baris data **masih bisa dekoy** kalau parameternya diabaikan

StubHub `explore` mengembalikan 17 event sungguhan dengan `eventId`, `name`, `url`, `venueName`. Tapi
`q=concert`, `q=taylor+swift`, `limit=100`, `offset=50`, dan `categoryId=26202` menghasilkan **17 event yang
persis sama** — dan kotanya mengikuti IP keluar. Itu widget rekomendasi beranda, bukan API pencarian.
**Syarat baru Pass 5b: setelah menemukan baris data, ubah satu parameter dan buktikan hasilnya berubah.**

### Aturan proses yang masih berlaku (tidak berubah)

1. Jangan percaya `ok30` di bawah 60 — putaran ini **4.512 actor melapor tepat 29**.
2. Baca `eventPriceUsd` datar, bukan cuma `eventTieredPricingUsd.GOLD`.
3. Event `isOneTimeEvent` ≥$1 = pass langganan, bukan biaya per run.
4. Jumlahkan hanya one-time + SATU event primer per-item.
5. Hitung penjual yang **MEMUNGUT**, bukan yang hadir.
6. Vein bisa berupa merek vendor API, bukan situs target.
7. **Selalu Pass 5b** — `200` bukan bukti sampai ada baris data (+ Koreksi 15).
8. Timeout ≠ 403, dan timeout ≠ mati sebelum DNS dicek (blokir DNS ISP, v8).
9. Dedupe tiga lapis wajib tiap putaran — hari ini 219 + 106 + 291 = **509 nama**.
10. Tulis markdown lewat Write/Python, jangan heredoc Bash.
11. Urutkan demand per `u30`, bukan `totalUsers`.
12. Lensa kapabilitas wajib tiap putaran — lensa domain sudah kering **enam** putaran.
13. **Cocokkan kelas kapabilitas pada `title`+`name`, jangan pada deskripsi** (kebocoran "captcha solving", §5).

---

## 11. Status & note untuk build ke depan

### ❗ Angka yang mendahului seluruh daftar di atas

| Keadaan | v7 (19 Sep) | v8 (22 Sep pagi) | **v9 (22 Sep sore)** |
|---|---:|---:|---:|
| Folder lokal | 245 | 290 | **291** |
| **Belum terbit di akun mana pun** | 148 | 185 | **186** |
| — punya `actor.json` lengkap | 148 | 184 | **185** |
| Terbit di `xtracto` + `fanndev` | 313 | 325 | 323 |

**186 actor jadi menganggur privat.** Sembilan dibangun dalam tujuh hari terakhir dan semuanya masih privat:
`bulk-email-verifier`, `movie-tv-data-extractor`, `mobile-de-scraper`, `noon-scraper`, `alfagift-scraper`,
`discord-server-scraper`, `etsy-ultimate-data-extractor`, `glints-jobs-scraper`, `techinasia-scraper`.
Rak riset ini bernilai nol sampai langkah publish jalan.

Runbook publish tidak berubah: **`scratchpad/publish_ready_v7.py`** (REST murni, token dari env, dry-run
bawaan, resumable lewat `output/publish_log_v7.jsonl`).

```bat
set APIFY_TOKEN=<token>
python scratchpad/publish_ready_v7.py --scan
python scratchpad/publish_ready_v7.py --publish --max 3            :: dry-run
python scratchpad/publish_ready_v7.py --publish --max 3 --apply
python scratchpad/publish_ready_v7.py --run --max 5 --memory 1024 --apply
```

`--memory 1024` **wajib**: `apify-actor-start` menagih 1 event per GB, jadi default 4096 MB = $0,02 biaya mati
per run di seluruh portofolio.

### Tabel status kandidat — siap build / perlu satu langkah / terblokir

| # | Kandidat | Rak/bln | Pembeli aktif rak | Penjual memungut | Permukaan | Status & catatan build |
|---|---|---:|---:|---:|---|---|
| 1 | **Woolworths AU (+Aldi)** | $115 | **1.488** | 4 | ✅ GET terbuka, 2.257 baris/kueri | 🟢 **siap build, ~1–2 jam.** Pakai jalur GET; `pageSize` ∈ {12,24,36}; dedupe `Stockcode` (tile sponsor berulang); seeding dari `PiesCategoriesWithSpecials`. **Coles tidak bisa** (Incapsula) |
| 2 | **Google Trends (reposisi)** | $2.042 | 4.101 | 18 | ✅ RSS 12 geo | 🟢 **jam-an** — tambah mode `trending` ke `xtracto/google-trends-scraper` yang sudah ada; incumbent resmi gagal 26% dengan 1.401 pembeli |
| 3 | **Transkrip + unduh YouTube** | **$26.892** | ~10.400 | 29 | ❌ 0 URL media, InnerTube ditolak | 🔴 **proyek, bukan tugas** — uji dari runtime Apify + RESIDENTIAL dulu; jangan probe lokal lagi |
| 4 | SofaScore multi-cabang | $1.122 | 2.707 | 8 | ✅ via DoH | 🟢 siap build — reuse `espn-betting-odds-scraper` |
| 5 | Copart salvage | $160 | 990 user | 4 | ✅ paginasi dalam | 🟢 siap build — sejam |
| 6 | WeChat 公众号 (Sogou) | $562 | 873 | 3 | ✅ 10 kartu/halaman | 🟢 siap build — tautan `/link?url=` berumur pendek |
| 7 | `tcgplayer` mode sales-history | $4.364 | 6 | 1 | rak sendiri | 🟢 penambahan mode |
| 8 | Discord username checker | $14.271 | 469 | 7 | ✅ anonim | 🟡 whale-dependent + batas etis |
| 9 | Product Hunt | $202 | 335 | 4 | ⚠️ TLS: pakai firefox133/safari17_0 | 🟡 rak kecil — hanya untuk melengkapi kelas |
| 10 | Depop | $1.425 | 528 | 14 | ⚠️ `/api/v1/shop/{id}` hidup, tanpa resolver | 🟡 butuh jalan ke id numerik |
| 11 | Liquipedia / esports | $557 | 135 | 3 | ⛔ dilarang `robots.txt` | 🔴 hanya lewat LPDB berkunci (registrasi gratis) = keputusanmu |
| 12 | StubHub / tiket | $533 | 57 | 4 | ⛔ dekoy (parameter diabaikan) | 🔴 tidak ada produk di baliknya |
| 13 | Upwork | $1.302 | 56 | 3 | ❌ 403 di 5 profil | 🔴 uji ulang dari IP Apify sebelum dicoret |
| 14 | Similarweb / trafik | $2.498 | 1.410 | 9 | ❌ 403 di 5 profil | 🔴 incumbent 0% gagal → mereka punya jalur lain |
| 15 | Crunchbase | $880 | 259 | 9 | ❌ DataDome | 🔴 tertutup |
| 16 | Weibo | $974 (satu actor) | 380 | — | ❌ butuh akun | 🔴 ditolak (aturan akun-login) |

### Urutan eksekusi yang saya sarankan

**#0 — Terbitkan yang sudah jadi.** 186 folder, 185 lengkap, biaya nyaris nol, nol engineering. Ini
mendahului setiap baris di §8 karena **setiap actor baru berakhir di langkah publish yang sama** — dan
angkanya naik lagi hari ini (185 → 186), bukan turun.

**#1 — Google Trends (§8 #2).** Paling murah per rupiah: actornya sudah ada, permukaannya sudah terverifikasi
terbuka hari ini, dan incumbent dengan 1.401 pembeli sedang gagal 26%.

**#2 — Woolworths AU (§8 #1).** Satu–dua jam, seluruh gotcha-nya sudah terpetakan di atas. Pasang harga sendiri.

**#3 — Uji gerbang YouTube dari runtime Apify (§8 #3).** Satu run menjawab pertanyaan senilai $26.892/bulan.
Kalau hasilnya negatif, coret vein-nya sekalian dan berhenti menghabiskan jatah probe di sana tiap putaran.

**#4 — SofaScore, lalu Copart + WeChat (§8 #4).** Tiga actor kecil yang permukaannya sudah diverifikasi pagi ini.

**#5 — Kalibrasi harga `xtracto`.** Tertunda lima putaran. Gap-nya terukur: **$0,57/pembeli** (933 pembeli,
MRR terukur $532) vs **$25–150/pembeli** di rak niche yang andal. Ambil pendapatan riil 30 hari dari Console,
hitung faktor koreksinya, ubah **2–3 actor saja**, tunggu satu siklus 30 hari.

### Ditolak permanen (bertambah putaran ini)

Weibo (butuh akun login — sekalipun token pengunjung anonim berhasil diterbitkan), Liquipedia via `api.php`
(`robots.txt` melarang untuk semua UA), StubHub `explore` (dekoy: parameter diabaikan).
Sebelumnya: `handelsregister.de`, USPTO merek dagang, trip.com, `hrs.de`, `housesigma.com`, Facebook,
IMDb (robots blanket + disclaimer komersial), TikTok konsumen, RockAuto, Ozon, AutoTrader UK, Dubai DLD.
