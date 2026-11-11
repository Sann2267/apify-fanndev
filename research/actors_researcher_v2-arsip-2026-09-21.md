# Riset Pasar Apify Store — v2 (putaran 2026-09-19 malam / v7)

**Tanggal riset:** 2026-09-19
**Permintaan putaran ini:** daftar actor dengan demand tinggi / stats tinggi di Apify Store, khususnya dua pola —
(A) *total runs banyak tapi user sedikit*, (B) *total user banyak tapi saingan sedikit* — lalu **dedupe wajib**
terhadap akun [`xtracto`](https://api.apify.com/v2/store?username=xtracto) supaya tidak membangun yang sudah ada.

> Putaran sebelumnya diarsipkan ke `actors_researcher_v2-arsip-2026-09-19-pagi.md`.

---

## Dedupe tiga lapis (snapshot ditarik ulang 2026-09-19 malam)

| Lapis | Jumlah | Angka | Snapshot |
|---|---:|---|---|
| `xtracto` (akun yang kamu sebut) | **217 actor** | 945 pembeli aktif (u30) · 166 actor punya ≥1 pembeli · **47.265** run sukses/30h | `output/xtracto-full-v7.json` |
| `fanndev` (akun push saat ini) | **96 actor** | 102 u30 · 91 actor punya pembeli · 1.522 run sukses/30h | `output/fanndev-full-v7.json` |
| Folder lokal repo ini | **245 folder** | — | `scratchpad/_dedupe_names_v7.json` |
| **Gabungan nama unik untuk dedupe** | **460** | — | `scratchpad/_dedupe_blob_v7.txt` |

**Perubahan sejak pagi:** `fanndev` 94 → **96**. `xtracto` tetap 217 tapi `u30` turun 955 → **945** dan
`ok30` naik 46.352 → **47.265** (pembeli sedikit berkurang, pemakaian per pembeli naik).

**Verifikasi duplikat seluruh shortlist:** tiap nama di §5–§8 dicek satu per satu terhadap ketiga lapis.
**Nol tabrakan.** Yang tersaring keluar karena sudah ada: seluruh vein Google Maps, `rednote`, `trustpilot`,
`yelp`, `expedia`, `wellfound`, `zillow`, `skyscanner`, `dexscreener`, `tcgplayer` (sebagai *price*, bukan
*sales-history*), `shopify-store-analyzer`, `semrush-website-overview`.

## Data mentah putaran ini

| File | Isi |
|---|---|
| `output/scan-v7-corpus.json` | **24.082 actor unik** — 21 kategori × 7 band user × offset 0–900 |
| `output/scan-v7-domains.json` / `-clean.json` | **1.808 vein per DOMAIN**, versi bersih sudah dilantai `ok30 ≥ 60` |
| `output/scan-v7-top-money.json` | 400 actor dengan MRR terukur tertinggi |
| `scratchpad/lens_v7_out.txt`, `lens_v7b_out.txt`, `lens_v7c_out.txt` | keluaran lensa 1–12 |

Skrip: `scratchpad/dedupe_v7.py`, `scan_v7.py`, `money_v7.py`, `lens_v7.py`, `lens_v7b.py`, `lens_v7c.py`,
`probe_v7.py`, `probe_v7b.py`, `probe_v7c.py`, `probe_v7d.py`.

---

## 1. Ringkasan eksekutif

Korpus **24.082 actor**. MRR terukur seluruh Store **$756.170/bulan** mentah, **$738.392** setelah lantai
kebisingan `ok30 ≥ 60`. **3.808 actor** memungut ≥$5/bulan secara nyata.

**Lima hal yang keluar dari putaran ini:**

1. **Lensa vein-per-domain sudah kering.** Dengan ambang yang sama seperti putaran lalu, Lensa 3 hanya
   menyisakan **6 baris**, dan semuanya receh ($60–$90 dengan 1–3 pembeli). Pola B per-domain pun habis:
   17 rak yang lolos filter **semuanya sudah dibahas atau sudah ditolak** (§4). Ini bukan kegagalan scan —
   ini tanda bahwa cara lama mencari sudah mentok.
2. **Penyebabnya ketemu, dan itu cacat metode selama enam putaran:** regex domain hanya menangkap actor
   yang **menyebut situs** di nama/judul/deskripsi. Seluruh kelas produk yang dijual sebagai **kemampuan**
   ("transcript", "tech stack detector", "OCR") tidak pernah muncul sebagai vein. Lensa 10 & 11 yang baru
   memperbaiki ini (§5) — dan langsung menemukan vein terbesar yang belum kamu sentuh.
3. **Celah terbesar di rak sendiri: transkrip YouTube.** Kamu punya **7 actor YouTube** dan **nol** actor
   transkrip. Rak transkrip YouTube memungut **≈$21.000/bulan** dari **≈6.000 pembeli aktif**, dengan hanya
   8–9 penjual. Ini demand terbesar non-PII yang ditemukan sepanjang tujuh putaran. **Tapi permukaannya
   tidak terbuka dari IP ini** — lihat peringatan di poin 4.
4. **Peringatan yang menyelamatkan satu sprint:** `timedtext` YouTube membalas **200 dengan 0 KB**.
   URL bertanda tangan dari halaman watch, InnerTube ANDROID/IOS (400), dan WEB (`UNPLAYABLE`) semuanya
   gagal (§7). Jadi #1 **bukan "siap build"** — ia **"recon dulu, satu sesi"**. Bukti jalur kerja itu ada:
   `starvibe/youtube-video-transcript` mencatat 441.977 run sukses/30h dengan rating 5,00 dan gagal 0,3%.
5. **Kandidat paling aman justru yang paling membosankan: Tech Stack Detector.** `nexgendata/wappalyzer-replacement`
   memungut $1.264/bulan dari **1.223 pembeli aktif** dengan **rasio u30/users 0,84** (adopsi tercepat di
   seluruh korpus non-PII), gagal **0,0%** — dan **permukaannya adalah situs mana pun**, jadi tidak ada WAF
   yang bisa menutupnya. Sudah diverifikasi Pass 5b (§7).

**Uang terbesar yang muncul baru tapi ditolak:** `zen-studio/apple-maps-scraper-pro` — **$5.119/bulan dari
30 pembeli**. Apple Maps sudah tiga putaran berturut gagal diprobe (`bootstrap` 401 lagi hari ini). §8 #5.

---

## 2. Papan atas pasar — di mana demand sebenarnya berada (konteks, bukan target)

Diurut per **pembeli aktif 30 hari** (`u30`), bukan `totalUsers`. `totalUsers` menumpuk sejak actor lahir;
`u30` adalah orang yang benar-benar memakainya bulan ini.

| u30 | Users | Runs | MRR bersih | Actor |
|---:|---:|---:|---:|---|
| 43.280 | 398.397 | 196,7 jt | $25.799 | `apify/instagram-scraper` |
| 37.110 | 610.282 | 39,5 jt | $5.752 | `compass/crawler-google-places` |
| 30.797 | 176.249 | 8,1 jt | **$0** | `apify/rag-web-browser` (gratis) |
| 27.328 | 221.018 | 116,2 jt | $14.526 | `apify/instagram-profile-scraper` |
| 23.111 | 289.017 | 126,5 jt | **$33.654** | `clockworks/tiktok-scraper` |
| 17.880 | 159.031 | 3,9 jt | $520 | `curious_coder/linkedin-jobs-scraper` |
| 17.694 | 184.703 | 119,9 jt | $21.685 | `apify/google-search-scraper` |
| 13.810 | 146.702 | 15,7 jt | $6.673 | `apify/instagram-reel-scraper` |
| 12.566 | 14.801 | 0,6 jt | $564 | `apify/web-fetch` — **rasio u30/users 0,85**, actor termuda di papan atas |

Dan bentuk yang paling relevan buat kamu — **uang besar, pembeli segelintir**:

| MRR | u30 | Users | ok30 | $/pembeli | Actor | Baca |
|---:|---:|---:|---:|---:|---|---|
| **$13.760** | 27 | 73 | 274.919 | **$510** | `entertained_rattlesnake/youtube-subtitle-scraper-ai` | **puncak vein transkrip (§5)** |
| $12.494 | 13 | 225 | 2.498.784 | $961 | `dev00/discord-username-checker` | bulk *checker*, bukan scraper |
| $6.800 | 68 | 3.598 | 3.674 | $100 | `peakydev/leads-scraper` | FLAT $100, gagal 17,9% — pelajaran harga |
| **$5.225** | 6 | 61 | 50.732 | **$871** | `scraped/tcgplayer-sales-history` | **celah produk rak sendiri (§8 #4)** |
| **$5.119** | 30 | 111 | 219.774 | $171 | `zen-studio/apple-maps-scraper-pro` | **baru & besar — tapi permukaan tertutup (§8 #5)** |
| $3.061 | 24 | 193 | 23.007 | $128 | `harvestlab/ebay-scraper` | eBay sudah kamu pegang 4 actor |
| $2.655 | 25 | 573 | 5.300 | $106 | `scraped/instagram-story-scraper` | Story IG — ditutup `require_login` (memori proyek) |

---

## 3. POLA A yang kamu minta — "runs banyak, user sedikit"

Filter: `totalUsers ≥ 15` **dan** `totalRuns ≥ 100.000`, diurut runs-per-user, dari korpus 24.082.

| runs/user | Users | u30 | Runs | MRR | Model | Actor | Vonis |
|---:|---:|---:|---:|---:|---|---|---|
| 114.990 | 212 | 4 | 24,4 jt | $100 | FLAT | `alien_force/facebook-scraper-pro-rental` | model sewa + **gagal 53,0%** |
| 79.384 | 32 | 3 | 2,5 jt | $36 | FLAT | `canadesk/apple-app-store-plus` | App Store, rak jenuh |
| 75.513 | 42 | 3 | 3,2 jt | $0 | FREE | `apify/monitoring-checker-schema` | infrastruktur Apify |
| **71.883** | **16** | 1 | 1,2 jt | **$699** | PPE | `apikit/upcheck` | uptime checker — 1 pembeli, $0,01/run |
| 65.467 | 56 | 19 | 3,7 jt | $0 | FREE | `apify/s3-uploader` | infrastruktur |
| 48.545 | 19 | 1 | 0,9 jt | $20 | FLAT | `canadesk/career-scraper-plus` | **ok30 = 29 → lantai palsu**, abaikan |
| 40.897 | 61 | 0 | 2,5 jt | $0 | PPE | `thescrappa/google-maps-advanced-search-scraper` | ok30 = 28, **nol pembeli** |
| 39.034 | 334 | 4 | 13,0 jt | $28 | FLAT | `devisty/google-search` | SERP, jenuh total |
| **29.472** | **881** | 30 | 26,0 jt | **$1.971** | PPE | `build_matrix/company-employees-scraper` | ❌ **PII karyawan** — ditolak permanen |
| 26.364 | 29 | 1 | 0,8 jt | $25 | FLAT | `jupri/apple-apps` | ok30 = 30 → lantai palsu |
| **23.742** | **21** | 1 | 0,5 jt | **$771** | PPE | `knagymate/hrs-reviews-scraper` | ⭐ carry-over, **recon separuh jalan (§9)** |
| 21.324 | 1.078 | 1 | 23,0 jt | $50 | FLAT | `muhammad_usama/Github-Apify-Linkedin-data-scraper` | LinkedIn, ditolak |
| **20.987** | **1.034** | 85 | 21,7 jt | **$1.673** | PPE | `macrocosmos/reddit-scraper` | Reddit — rak jenuh + risiko API resmi |
| 17.479 | 180 | 13 | 3,1 jt | $6 | PPE | `saswave/amazon-seller-monitoring` | Amazon, sudah kamu pegang 6 actor |
| 15.390 | 62 | 6 | 1,0 jt | $18 | PPE | `saswave/noon-seller-monitoring` | **gagal 31,0%** — noon diblok Akamai (arsip) |
| 15.278 | 2.112 | 30 | 32,3 jt | $2.070 | FLAT | `making-data-meaningful/tecdoc` | ❌ data berlisensi B2B — ditolak permanen |
| **15.172** | **61** | 6 | 0,9 jt | **$5.225** | PPE | `scraped/tcgplayer-sales-history` | ⭐ **celah produk rak sendiri (§8 #4)** |
| 12.222 | 2.202 | 55 | 26,9 jt | $448 | PPE | `novi/fast-tiktok-api` | TikTok, rak jenuh + WAF (memori proyek) |
| **11.573** | **225** | 13 | 2,6 jt | **$12.494** | PPE | `dev00/discord-username-checker` | 🟡 bulk *checker*, bentuk produk bukan niche data |
| **10.771** | **73** | 27 | 0,8 jt | **$13.760** | PPE | `entertained_rattlesnake/youtube-subtitle-scraper-ai` | ⭐ **#1 putaran ini (§8)** |
| **10.463** | **16** | 6 | 0,2 jt | **$270** | FLAT | `clearpath/kleinanzeigen-immobilien-api-pro` | ⭐ **permukaan terverifikasi terbuka (§8 #3)** |

**Cara membaca pola A, putaran ketujuh berturut-turut:** dari 35 teratas, **21 adalah infrastruktur Apify,
model sewa, PII, atau lantai palsu `ok30 ≈ 29`**. Yang tersisa sebagai peluang nyata: **3** —
`youtube-subtitle-scraper-ai`, `tcgplayer-sales-history`, `kleinanzeigen-immobilien`. Pola A tetap bagus
sebagai **penjelas**, buruk sebagai **penyaring**.

---

## 4. POLA B yang kamu minta — "user banyak, saingan sedikit"

Vein per domain dengan `users ≥ 1.500` dan `sellers ≤ 8`. **17 rak lolos filter. Nol yang bisa dipakai.**

| MRR | Penjual | Penagih | Users | u30 | Domain | Kenapa gugur |
|---:|---:|---:|---:|---:|---|---|
| $2.213 | 1 | 1 | 4.576 | 903 | `scraptik` | **bukan situs** — merek vendor API TikTok (mode kebohongan #4) |
| $1.575 | 1 | 1 | 15.284 | 773 | `realtyapi` | ❌ PII skip-trace |
| $1.272 | 4 | 3 | 2.907 | 54 | `upwork` | puncaknya `jupri/upwork` gagal 8,6%; rak freelance = ToS keras |
| $1.080 | 4 | 1 | 5.203 | 88 | `trustpilot` | ✅ **sudah punya** `xtracto/trustpilot-reviews` |
| $988 | 3 | 3 | 1.823 | 149 | `yelp` | ✅ **sudah punya** `xtracto/yelp-business-scraper` |
| $857 | 4 | 3 | 1.641 | 142 | `expedia` | ✅ **sudah punya** 2 actor Expedia |
| $763 | 1 | 1 | 15.978 | 534 | `dievio` | ❌ PII lead rental |
| $662 | 6 | 3 | 2.114 | 553 | `ozon` | ❌ 403 di 7/7 profil TLS (arsip babak 52) |
| $398 | 7 | 4 | 18.288 | 1.783 | `apollo` | ❌ PII |
| $146 | 2 | 1 | 4.110 | 229 | `similarweb` | ❌ 202 challenge tertunda (arsip) |
| $78 | 1 | 1 | 4.463 | 588 | `instantly` | ❌ PII email finder |
| $58 | 8 | 3 | 20.885 | 1.793 | `naukrigulf` | $0,03/pembeli — rak tanpa uang |
| $34 · $21 · $1 · $1 · $0 | — | — | — | — | `gmgn` · `wellfound` · `patreon` · `onlyfans` · `anti-captcha` | receh / sudah punya / ToS |

**Kesimpulan pola B:** rak "user banyak, saingan sedikit" **sudah habis diperas** di tingkat domain.
Yang tersisa cuma tiga kategori: PII (ditolak), sudah kamu punya, atau merek vendor yang bukan situs.
Ini yang memicu pergantian lensa di §5.

---

## 5. LENSA BARU — vein per KAPABILITAS, bukan per domain

**Cacat metode yang diperbaiki:** regex vein selama enam putaran mencari nama domain di judul/deskripsi.
Actor yang dijual sebagai *kemampuan* tidak punya domain di judulnya, jadi **tidak pernah terlihat**.

### Lensa 10 — celah kapabilitas di platform yang rak-nya sudah kamu pegang

| Platform | MRR rak | Kapabilitas | Status | MRR kapabilitas | Penjual |
|---|---:|---|---|---:|---:|
| **YouTube** | $45.911 | **transkrip / subtitle** | ❌ **CELAH** | **$24.969** | 22 |
| YouTube | | download / audio | ❌ celah | $13.961 | 14 |
| YouTube | | channel · comments · search · shorts | ✅ punya | — | — |
| Amazon | $5.026 | semua 5 kapabilitas | ✅ punya | — | — |
| Reddit | $16.380 | semua 4 kapabilitas | ✅ punya | — | — |
| Hotel/OTA | $5.702 | restoran (TripAdvisor) | ❌ celah | $387 | 3 |
| Twitter/X | $13.224 | followers | ❌ celah | $436 | 6 |
| Maps | $18.588 | semua 4 kapabilitas | ✅ punya | — | — |

**Satu baris yang penting dari tabel ini:** dari delapan platform yang kamu sudah kuasai, hanya **satu
kapabilitas** yang punya uang lima digit dan nol padanan di rak kamu — transkrip YouTube.

### Lensa 11 — kapabilitas non-platform (raksasa PII/sosial dikecualikan)

| MRR | Penjual | Kelas | Actor saya | Catatan |
|---:|---:|---|---:|---|
| **$22.878** | 18 | **transkrip / subtitle** | **0** | §8 #1 |
| $5.401 | 2 | kartu koleksi | 2 | `scraped/tcgplayer-sales-history` $5.225 → §8 #4 |
| $2.561 | 13 | monitor harga | 1 | terfragmentasi, tak ada pemuncak |
| **$2.411** | 6 | **deteksi tech stack** | 1 (Shopify saja) | §8 #2 |
| $1.280 | 5 | podcast / audio | 3 | sudah cukup terwakili |
| $1.147 | 7 | event / tiket | 1 | rak kecil, 7 penjual |
| $344 | 4 | registry perusahaan | 1 | `handelsregister` timeout lagi (§7) |
| $326 | 3 | whois / DNS / SSL | 0 | rak terlalu kecil |
| $114 | 1 | paten / merek dagang | 0 | ❌ USPTO tertutup (§7) |

### Lensa 12 — permintaan muda (rasio `u30/users` tinggi = adopsi cepat)

| MRR | u30 | Users | Rasio | Gagal | Actor |
|---:|---:|---:|---:|---:|---|
| $6.425 | 257 | 428 | 0,60 | 0,0% | `data_link_miner/linkedin-mass-people-profile-finder` ❌ PII |
| **$1.264** | **1.223** | 1.460 | **0,84** | **0,0%** | ⭐ `nexgendata/wappalyzer-replacement` → §8 #2 |
| $640 | 1.100 | 1.851 | 0,59 | 0,0% | `unseenuser/LinkedIn-Profile` ❌ PII |
| $564 | 12.566 | 14.801 | 0,85 | 7,3% | `apify/web-fetch` (milik Apify) |
| $272 | 456 | 773 | 0,59 | 1,5% | `zen-studio/wechat-official-account-scraper` — 🟡 belum diprobe |
| $107 | 509 | 559 | 0,91 | **42,7%** | `zerobreak/google-hotels-scraper` — ✅ kamu sudah punya, **dan pesaingnya gagal 4 dari 10 run** |

---

## 6. Vein transkrip dibuka penuh (ini rak yang dimaksud §8 #1)

Hanya baris YouTube; actor Instagram/Facebook yang kebetulan menyebut "subtitle" sudah dibuang.

| MRR | u30 | Users | ok30 | Harga | Rating | Gagal | Actor |
|---:|---:|---:|---:|---|---|---:|---|
| **$13.760** | 27 | 73 | 274.919 | PPE **$0,05005**/run | — (0) | 0,0% | `entertained_rattlesnake/youtube-subtitle-scraper-ai` |
| $2.939 | **2.364** | 24.714 | 419.791 | PPE $0,00700 | **3,72** (49) | **11,7%** | `pintostudio/youtube-transcript-scraper` |
| $2.210 | **2.255** | 10.961 | 441.977 | PPE $0,00500 | **5,00** (23) | 0,3% | `starvibe/youtube-video-transcript` |
| $1.125 | 127 | 1.176 | 32.130 | PPE $0,03500 | 4,27 (20) | 0,1% | `invideoiq/video-transcriber` |
| $700 | 35 | 4.687 | 194.753 | FLAT **$20** | 4,88 (14) | 0,0% | `topaz_sharingan/Youtube-Transcript-Scraper` |
| $621 | 9 | 36 | 4.672 | PPE $0,13290 | — (0) | 0,1% | `ilborso/youtube-text-scraper` |
| $360 | 24 | 3.067 | 413 | FLAT $15 | 4,89 (16) | 0,0% | `karamelo/youtube-full-channel-transcripts-extractor` |
| $335 | 409 | 8.103 | 33.451 | PPE $0,01000 | 5,00 (28) | 0,2% | `topaz_sharingan/Youtube-Transcript-Scraper-1` |
| $333 | 709 | 8.334 | 66.605 | PPE $0,00500 | 4,99 (15) | 0,0% | `karamelo/youtube-transcripts` |

**Total ≈$22.400/bulan · ≈5.960 pembeli aktif · 8 penjual.**

Tiga hal yang dikatakan tabel ini:

1. **Sebaran harga 26× lipat** untuk data yang sama ($0,005 vs $0,133 per run). Rak ini belum punya harga pasar.
2. **`pintostudio` adalah target penggeseran:** 2.364 pembeli aktif, **rating 3,72**, **gagal 11,7%**.
   Pembeli sebanyak itu dengan rating serendah itu artinya mereka bertahan karena tidak ada pilihan lain.
3. **`starvibe` membuktikan jalur yang andal itu ada**: 441.977 run sukses/30 hari, gagal 0,3%, rating 5,00.
   Jadi kegagalan probe di §7 adalah masalah **IP/metode saya**, bukan permukaannya mati.

Bonus di kelas yang sama (transkrip Instagram, engine yang sama): `crawlerbros/instagram-transcript-scraper`
**$2.056 dari 243 pembeli dengan harga $0,54/run** — 108× lipat harga transkrip YouTube termurah.

---

## 7. Hasil probe permukaan — Pass 5 + Pass 5b (2026-09-19 malam)

Dua profil TLS (chrome124 + safari17_0). **200 bukan bukti** — kolom terakhir adalah Pass 5b: apakah baris
data yang dicari benar-benar ada di badan respons.

### ✅ Terbuka (data terverifikasi ada)

| Target | Status | Isi sebenarnya (Pass 5b) |
|---|---|---|
| **Deteksi tech stack** — situs mana pun | 200 | `allbirds.com` 652 KB: **19 sinyal Shopify · 22 `<script src>` · 260 `<link href>`**; `notion.com` 183 KB: **88 sinyal Next.js**; `basecamp.com` 56 KB bersih. **Tidak ada WAF karena tidak ada satu situs target pun** |
| `kleinanzeigen.de/s-wohnung-mieten/berlin/…` | 200 / 796 KB | **27 `data-adid` · 62 harga €**; `seite:2` balas 840 KB dengan isi berbeda → paginasi hidup |
| `youtube.com/watch?v=…` (halaman) | 200 / 1.276 KB | **`captionTracks` ada · 6 baseUrl `timedtext` · `ytInitialPlayerResponse` · `INNERTUBE_API_KEY`** — metadata lengkap (judul, viewCount, daftar bahasa) |

### 🟠 Perlu satu sesi recon

| Target | Temuan |
|---|---|
| **`timedtext` YouTube** | **Ini penghalang #1.** baseUrl bertanda tangan (`signature`, `expire`, `sparams`, `ip=0.0.0.0`) balas **200 dengan 0 KB, 0 segmen** di lima varian (`polos`, `fmt=json3`, `fmt=srv3`, `+Referer`, `+CONSENT`, `xorp=true`). InnerTube: **ANDROID 400 · IOS 400 · WEB `UNPLAYABLE` · TVHTML5 `ERROR`**. Pola ini = gerbang `pot`/IP, bukan permukaan mati (bandingkan `starvibe` 441 ribu run sukses). **Uji berikutnya: proxy RESIDENTIAL** — persis pola yang sudah terbukti di actor Google Maps popular-times (memori proyek: 0% datacenter vs 62,5% residential) |
| `market.yandex.ru/search` | 200 / 1.902 KB tapi hanya **11 `snippet-title` + 11 `snippet-price`** dari ~48 item, ditambah **12 penanda captcha**. SSR separuh. Butuh proxy RU + satu sesi |
| `hrs.de` (carry-over) | 200 / 281 KB, 10 link `/hotel/`, **39 potongan `self.__next_f.push`** — tidak bergerak dari pagi, tinggal didekode |
| `housesigma.com/bkv2/api/…` (carry-over) | Masih balas JSON hidup `{"status":false,…"API":"v5.38.205"}` — endpoint belum ketemu |

### ❌ Tertutup / gugur putaran ini

| Target | Bentuk tembok | Vonis |
|---|---|---|
| **Apple Maps** | `cdn.apple-mapkit.com/ma/bootstrap` **401** · `api.apple-mapkit.com/v1/search` **401** · `maps.apple.com/api/search` **404** · halaman `maps.apple.com/place` 32 KB tanpa satu pun blok JSON | **Gagal ketiga kali berturut. Coret** kecuali kamu mau beli kunci MapKit JS resmi (§8 #5) |
| **USPTO merek dagang** | `tmsearch.uspto.gov/api-v1-0-0/…` 404/405 (bucket S3) · `tmsearch.uspto.gov/search/…` **SPA Angular 122 KB** · `tsdrapi` **401 "wajib API key mulai 2 Oktober"** · `assignment-api` & `ped.uspto.gov` **DNSError** | **Coret.** Rak cuma $114, tidak sebanding |
| **trip.com** | 200 / 352 KB tapi Pass 5b: **`reviewList`=0 · `commentList`=0 · teks ulasan=0 · `score`=0 · `hotelName`=0**. Yang ada cuma 7 blob `window.__CARGO_DATA__`/`__NFES_DATA__` | **Arsip benar: cangkang.** Incumbent `knagymate` 83 ribu run sukses pasti lewat jalur lain |
| **handelsregister.de** | **Timeout lagi** di chrome124 & safari17_0 (kali ketiga) | **Coret permanen** sesuai aturan proses #8 |

**14 probe menutup 4 kandidat, membuka 3, dan menyelamatkan satu sprint** (transkrip kelihatan "siap build"
sampai Pass 5b menunjukkan 0 KB).

### 7b. Lanjutan sesi yang sama — tiga carry-over ditutup jadi keputusan

**Kleinanzeigen — ✅ selector selesai dipetakan, risiko build hilang.**
Situsnya sudah didesain ulang: kelas BEM lama (`aditem-main--middle--price`) **tidak ada lagi**, diganti
kelas utilitas gaya Tailwind (`flex`, `font-strong`, `text-onSurfaceSubdued`). Satu kartu = `<article data-adid>`
sepanjang ~6,5 KB berisi:

| Field | Cara ambil | Contoh nyata |
|---|---|---|
| ID + slug | `href="/s-anzeige/<slug>/<adid>-<kategori>-<lokasi>"` | `…/3497784945-203-3380` |
| Judul | dari slug href (tidak ada `<h2>`) | `2-zimmer-in-neubau-nahe-s-bahnhof-springpfuhl…` |
| Harga | regex `[\d.]+\s*€` di dalam kartu | `1.150 €` |
| Lokasi | regex `\d{5}\s+[A-ZÄÖÜ]\w+` | `12681 Marzahn` |
| Atribut | regex `\d+\s*m²` dan `\d+\s*Zi\.` | `40 m²`, `2 Zi.` |

**Sisa 30 menit yang tadinya disisakan untuk memetakan selector sudah tidak perlu.**

**HRS — ❌ mati, batas waktu satu sesi terpakai dan hasilnya negatif.**
39 potongan `self.__next_f.push` didekode penuh jadi **185 KB**, isinya: **0 `hotelId` · 0 `rating`/`score` ·
0 `reviewText`/`comment` · 0 `reviewCount`**, hanya 2 link hotel. Digabung dengan probe pagi (halaman detail
punya 98 kemunculan kata "rating" tapi **0 `reviewText`**), kesimpulannya: **teks ulasan HRS tidak ada di HTML
maupun di RSC.** Rak $771 dengan rpu 23.742 itu nyata, tapi bukan lewat jalur ini. **Coret.**

**HouseSigma — ❌ tertutup, dan sekarang tahu persis kenapa.**
Bundle `index.*.js` membocorkan **peta endpoint lengkap** API v5.38.205 (`/listing/info/detail_v2`,
`/listing/info/photos`, `/listing/info/popularity`, `/listing/detail/showPrice`, `/agent/info/agentlist`,
puluhan `/user/watchlist/*`). Semuanya membalas **`{"status":false,"error":{"code":900,"message":"AUTHORIZATION header error"}}`** —
skemanya `Authorization: Bearer <access_token>`.

Token anonim **tidak dibagikan**: halaman tidak mengirim `Set-Cookie`, tidak ada JWT di HTML maupun di bundle,
dan satu-satunya endpoint yang berbau inisialisasi (`/auth/user/initcountrycode`) **juga minta Bearer**.
Hanya dua endpoint terbuka, dan isinya cuma taksonomi geografis:
`/community/list/init` → 215 KB (21 region · 21 grup municipality · **372 grup community dengan lat/lon** ·
6 tipe rumah) dan `/listing/climate_risk/get` → `data: null` tanpa parameter.

Artinya HouseSigma butuh **akun login**, bukan bypass — di luar pola portofolio ini. **Coret.**
(Pembanding yang berguna: `haystack-tv-scraper` membagikan JWT anonim gratis lewat `Set-Cookie`. HouseSigma tidak.)

---

## 8. Rekomendasi

### #1 — Transkrip YouTube — **rak terbesar, tapi recon dulu**

**Kenapa teratas:** satu-satunya kapabilitas dengan uang lima digit yang **tidak kamu punya sama sekali**
padahal kamu sudah pegang 7 actor YouTube — jadi seluruh README, skema output, dan basis pelanggan sudah ada.

- **Pola A terpenuhi:** `entertained_rattlesnake` 73 user / 786.316 run (rpu 10.771), $510 per pembeli.
- **Pola B terpenuhi:** ≈5.960 pembeli aktif dibagi hanya **8 penjual**.
- **Target penggeseran jelas:** `pintostudio` — 2.364 pembeli, rating **3,72**, gagal **11,7%**.
- **Harga belum punya pasar:** rentang $0,005–$0,133 per run untuk data identik.

**Status: 🟠 BELUM SIAP BUILD.** Permukaan gagal Pass 5b dari IP ini (§7). Urutan kerjanya:

1. Ulangi `scratchpad/probe_v7c.py` lewat **proxy RESIDENTIAL** Apify. Kalau `timedtext` mengeluarkan
   segmen, langsung build. Ini satu perintah, bukan satu sprint.
2. Kalau residential juga 0 KB: jalur kedua adalah **InnerTube dengan `pot` dari BotGuard**, atau
   panel `getTranscript` (`youtubei/v1/get_transcript`) dengan `params` yang dipanen dari halaman —
   pola **warm-page-token-harvest** yang sudah ada skill-nya di repo ini.
3. Kalau dua-duanya gagal, **tinggalkan** dan naikkan #2 jadi prioritas utama. Jangan paksakan;
   rak ini besar tapi bukan satu-satunya.

*Note build:* paketkan sebagai **satu actor 3 mode** — `video` (satu ID), `channel` (semua video),
`playlist` — supaya langsung menyaingi `karamelo` (FLAT $15 khusus channel) dan `pintostudio` sekaligus.
Harga: **PPE $0,003/video** menempatkanmu di bawah `starvibe` ($0,005) tanpa masuk wilayah rugi,
dan `apify-actor-start` **wajib diturunkan dari 4096 MB** (memori proyek: 1 event per GB = $0,02 biaya mati per run).

### #2 — Tech Stack Detector — **paling aman, paling cepat, permukaannya tidak bisa ditutup**

`nexgendata/wappalyzer-replacement`: **$1.264/bulan · 1.223 pembeli aktif · rasio u30/users 0,84 ·
gagal 0,0% · PPE $0,10/run · nol ulasan**.

Kenapa ini menarik justru karena membosankan:

- **Rasio adopsi 0,84 adalah yang tertinggi di korpus non-PII.** Actor ini baru dan sedang meledak.
- **Tidak ada situs target**, jadi tidak ada WAF, tidak ada perubahan DOM yang mematikannya, tidak ada
  gerbang IP. Terverifikasi Pass 5b hari ini di tiga situs (§7).
- **Kamu sudah punya 80% kodenya**: `fanndev/shopify-store-analyzer` sudah mendeteksi Shopify dari HTML.
  Ini generalisasi dari satu vendor jadi tabel sidik jari.
- **Pemuncaknya nol ulasan dan memungut $0,10/run** — 50× lipat lebih mahal dari `builtwith` resmi
  ($0,002/run). Ruang harga lebar.

*Note build:* sidik jari = `<script src>`, `<link href>`, header `Server`/`X-Powered-By`, cookie,
`meta generator`, dan pola di `/robots.txt`. Mulai dari ~60 teknologi yang paling laku
(Shopify, WooCommerce, Next.js, Klaviyo, GTM, Meta Pixel, Hotjar, Intercom, Cloudflare, HubSpot),
bukan 2.000 seperti Wappalyzer. **Bundel output-nya dengan `shopify-store-analyzer`** jadi satu pipeline
lead-gen e-commerce. Harga **PPE $0,01–0,02/domain** — di bawah `nexgendata`, di atas biaya.

### #3 — Kleinanzeigen Immobilien — **satu-satunya kandidat baru yang terbuka tanpa syarat**

`clearpath/kleinanzeigen-immobilien-api-pro`: 16 user, 167.403 run (**rpu 10.463**), 62.222 run sukses/30h,
FLAT $30 dari 6 pembeli = $270. Rak Kleinanzeigen total $228 dengan 2 penagih (carry-over dari arsip).

Permukaan **terverifikasi terbuka hari ini**: 27 `data-adid` per halaman, 62 harga €, paginasi `seite:N` hidup.

*Note build:* ini melengkapi klaster properti Eropa yang sudah kamu punya (`immobiliare-listings`,
`idealista`, `daft-ie`, `zoopla`, `rightmove`, `leboncoin`). **Selector detail belum dipetakan** —
tebakan saya (`aditem-main--middle--price`) meleset, jadi sisakan 30 menit untuk memetakan kelas CSS-nya.
Jangan pakai FLAT $30 seperti incumbent; PPE per listing lebih cocok dengan portofoliomu.

### #4 — Dua celah produk di rak sendiri (uang terbesar, engineering paling kecil)

**4a. `tcgplayer-sales-history` — masih berdiri, putaran ketiga.**
`scraped/tcgplayer-sales-history` memungut **$5.225/bulan dari 6 pembeli** ($871/pembeli!) sementara
`xtracto/tcgplayer-price-scraper` berhenti di 2 user. Ini **penambahan mode**, bukan actor baru.
Pasangkan dengan `fanndev/psa-card-cert-lookup-scraper` → satu klaster kartu koleksi.

**4b. `zerobreak/google-hotels-scraper` gagal 42,7%** dengan 509 pembeli aktif, sementara
`fanndev/google-hotels-rate-comparison-scraper` kamu sudah jalan. Pesaing yang gagal 4 dari 10 run
dengan 500 pembeli adalah **baji pemasaran**, bukan ancaman — pakai angka keandalan itu di README-mu.

### #5 — Apple Maps: uang besar, pintu terkunci — **keputusan, bukan tugas**

`zen-studio/apple-maps-scraper-pro` memungut **$5.119/bulan dari 30 pembeli** dengan gagal 0,0%.
Tiga putaran berturut-turut permukaannya menolak: `bootstrap` 401, `v1/search` 401, `/api/search` 404.

Artinya `zen-studio` hampir pasti memakai **kunci MapKit JS resmi** (Apple Developer, $99/tahun,
JWT ditandatangani ES256). Itu bukan bypass — itu **biaya berlangganan + akun developer Apple**.
**Keputusannya ada di kamu**, bukan di riset: kalau mau bayar $99/tahun, rak $5.119 itu terbuka legal
dan bersih. Kalau tidak, coret permanen dan berhenti memprobe tiap putaran.

---

## 9. Status carry-over dari putaran pagi

| Item | Status pagi | Hari ini | Vonis |
|---|---|---|---|
| `clutch-agency-directory-scraper` | 🟢 dibangun, belum terbit | ❗ **Klaim itu salah** — sudah terbit di `fanndev` dengan **2 user**, judul "Clutch.co Agency Directory & Lead Attributes Scraper" | ✅ **Selesai, coret dari daftar** |
| Kalibrasi harga `xtracto` | 🔴 #1 non-build | Belum dikerjakan. `u30` turun 955 → **945** | 🔴 **Naik jadi mendesak — pembeli mulai bocor** |
| `dastelefonbuch.de` + `gelbeseiten.de` | 🔴 #2 build | Tidak ada folder baru | 🟡 **Masih berdiri, turun ke #4** (kalah dari transkrip & tech-stack) |
| `fragrantica` + `goodreads` | 🔴 #4 build | `goodreads` rak turun $105 → **$90** | 🟡 Dipertahankan, prioritas turun |
| `idealo.de` | 🟡 | Tidak diprobe ulang | 🟡 Tidak bergerak |
| HRS (`$771`, rpu 23.742) | 🟠 recon separuh jalan | RSC didekode penuh: 185 KB berisi **0 `reviewText`, 0 `rating`, 0 `hotelId`** (§7b) | ❌ **Coret** — batas waktu satu sesi terpakai, hasilnya negatif |
| `housesigma.com` | 🟠 recon | Peta endpoint lengkap ditarik dari bundle; **semua butuh `Bearer`, token anonim tidak ada** (§7b) | ❌ **Coret** — butuh akun login, bukan bypass |
| `handelsregister.de` | 🟠 "belum bisa dinilai" | **Timeout kali ketiga** | ❌ **Coret permanen** |
| Apple Maps | 🟠 recon #4 | 401/401/404 — dan sekarang terlihat rak-nya **$5.119** | ⚠️ **Jadi keputusan bisnis (§8 #5), bukan recon** |
| `zoover` · TecDoc · realtyapi · RocketReach · darkweb | ❌ | Tidak berubah | ❌ Tetap ditolak |

---

## 10. Koreksi metode putaran ini

### Koreksi 5 — vein per domain melewatkan kelas produk yang dijual sebagai kemampuan

Enam putaran memakai regex domain pada nama/judul/deskripsi. Itu **secara struktural buta** terhadap
actor seperti `youtube-subtitle-scraper-ai` (tidak ada nama domain selain "youtube", yang ada di daftar
`SKIPDOM`) dan `wappalyzer-replacement` (domainnya "wappalyzer" — nama produk pesaing, bukan target).

Akibatnya terukur: rak **$22.878 dengan nol actor milikmu** tidak pernah muncul di enam laporan sebelumnya,
sementara Lensa 3 dilaporkan "kering" tiga putaran berturut-turut. **Lensa 10 & 11 sekarang wajib tiap putaran**
(`scratchpad/lens_v7c.py`).

### Koreksi 6 — lantai kebisingan `ok30 ≈ 29` terkonfirmasi ulang, dan makin besar

Korpus v7: **4.518 actor melaporkan tepat 29 run sukses/30 hari** (naik dari 4.339) dan **4.397 actor
punya `ok30` > 0 dengan nol pembeli**. Selisih MRR mentah vs bersih putaran ini: **$17.778/bulan kebisingan**.
Aturan tidak berubah: abaikan komponen PPE mana pun yang bertumpu pada `ok30` < 60.

### Koreksi 7 — "200 dengan 0 KB" adalah mode kegagalan tersendiri

Sebelumnya Pass 5b mengejar "200 dengan halaman besar tanpa baris data" (`dubizzle`, `makerworld`).
Putaran ini menemukan bentuk ketiga: **200 dengan badan kosong total** (`timedtext`). Ini tanda khas
**gerbang token/IP**, bukan permukaan mati — dan pembedanya adalah statistik pesaing: kalau ada actor
lain dengan ratusan ribu run sukses di permukaan yang sama, **kamu yang salah metode, bukan situsnya yang tutup**.

### Aturan proses yang masih berlaku dari putaran sebelumnya

1. Jangan percaya `ok30` di bawah 60.
2. Baca `eventPriceUsd` datar, bukan cuma `eventTieredPricingUsd.GOLD`.
3. Event `isOneTimeEvent` ≥$1 adalah pass langganan, bukan biaya per run.
4. Jumlahkan hanya `event one-time + SATU event primer per-item`.
5. **Hitung penjual yang MEMUNGUT, bukan yang hadir.**
6. Vein bisa berupa merek vendor API, bukan situs target (`scraptik`, `realtyapi`, `dievio`, `wappalyzer`).
7. **Selalu Pass 5b.**
8. Timeout ≠ 403. Tiga kali timeout = coret permanen (`handelsregister` kena hari ini).
9. Dedupe tiga lapis wajib tiap putaran — hari ini 217 + 96 + 245 = **460 nama**.
10. Tulis markdown lewat Write/Python, jangan heredoc Bash. **f-string Python tidak boleh memuat backslash**
    (dua skrip probe putaran ini gagal karena itu — kali ketiga aturan ini menagih).
11. Urutkan demand per `u30`, bukan `totalUsers`.

---

## 11. Status & note untuk build ke depan

### ❗ Temuan yang mendahului seluruh daftar ini: inventaris jadi yang belum diterbitkan

Setelah laporan pertama, satu pemeriksaan yang **tidak pernah dilakukan di tujuh putaran riset** memperlihatkan
hal berikut: **148 folder lokal punya `actor.json` + Dockerfile + input/output schema + README + `src/` lengkap
tapi namanya tidak ada di `xtracto` maupun `fanndev`.** Bukan eksperimen — ini template portofolio yang utuh.

Silang dengan berkas state yang sudah ada di repo (`output/fanndev-private-names.json`,
`fanndev-private-state.json`, `publish-readiness-2026-09-15.json`, snapshot **2026-09-15**):

| Keadaan | Jumlah | Artinya |
|---|---:|---|
| Sudah di-push ke `fanndev` sebagai **privat** | **146** | sudah ada di platform, tinggal diterbitkan |
| — di antaranya **sudah pernah run SUKSES** | **23** | **prasyarat publish sudah lunas** |
| — belum pernah dijalankan sama sekali | 123 | butuh satu `apify call` masing-masing |
| — pernah gagal | **0** | tidak ada yang rusak |
| Lolos kesiapan metadata | 143 | — |
| Belum lolos metadata | 3 | `haystack-tv-scraper` (sudah terbit), `klikindomaret-scraper`, `us-prober` — kurang `categories` |

**22 actor tinggal satu panggilan `PUT isPublic`** — nol engineering, nol recon, nol risiko:

`atlantic-scraper` · `axios-scraper` · `bangkokpost-scraper` · `clarin-scraper` · `dailyft-scraper` ·
`derspiegel-scraper` · `fiji-roc-scraper` · `handelsblatt-scraper` · `hindustantimes-scraper` ·
`inquirer-scraper` · `jakartapost-scraper` · `jamaicagleaner-scraper` · `jerusalempost-scraper` ·
`kyivpost-scraper` · `lanacion-scraper` · `mailguardian-scraper` · `nationthailand-scraper` ·
`nepal-ocr-scraper` · `philstar-scraper` · `statesman-scraper` · `thehindu-scraper` · `tuoitre-scraper`

**121 lagi** lolos metadata tapi belum pernah dijalankan — masing-masing butuh satu `apify call` sukses
dulu, lalu `PUT isPublic` yang sama (mayoritas klaster tender pemerintah + registry perusahaan negara kecil).

**Kenapa ini mendahului §8:** membangun actor baru memakan satu sesi penuh dan tetap berakhir di langkah
publish yang sama. 143 actor ini **sudah melewati semua langkah itu** dan sedang menghasilkan **$0**.
*Peringatan biaya:* sebelum menjalankan 121 run, **turunkan memori default dari 4096 MB** —
memori proyek mencatat `apify-actor-start` menagih 1 event per GB, dan batas $5/bulan plan FREE pernah kena.
*Peringatan nilai:* 20 dari 22 yang siap adalah scraper berita, vein bernilai rendah di riset ini —
harapkan pembeli sedikit per actor. Nilainya ada di **biayanya nyaris nol**, bukan di nilai per actor.

> Snapshot state ini tertanggal **2026-09-15** (4 hari lalu). Tarik ulang daftar actor privat lewat API
> sebelum mengeksekusi — butuh API token, yang juga tidak ada di `~/.apify/auth.json`.

#### Runbook — `scratchpad/publish_ready_v7.py`

REST API murni, **tidak butuh `apify login`**. Token dibaca dari env dan tidak pernah dicetak ke layar
maupun ke log. Dry-run adalah perilaku bawaan; `--apply` yang mengeksekusi.

```bat
set APIFY_TOKEN=<token>

:: 1. Tarik keadaan TERKINI (mengganti snapshot 2026-09-15). Read-only.
python scratchpad/publish_ready_v7.py --scan

:: 2. FASE A - terbitkan yang prasyaratnya sudah lunas. Mulai kecil.
python scratchpad/publish_ready_v7.py --publish --max 3
python scratchpad/publish_ready_v7.py --publish --max 3 --apply
::    periksa hasilnya di Store, lalu lanjutkan sisanya dengan --max 25

:: 3. FASE B - run murah lalu terbitkan yang sukses. PERHATIKAN --memory.
python scratchpad/publish_ready_v7.py --run --max 5 --memory 1024
python scratchpad/publish_ready_v7.py --run --max 5 --memory 1024 --apply
```

| Pengaman | Perilaku |
|---|---|
| Dry-run bawaan | tanpa `--apply`, hanya mencetak apa yang akan dilakukan (termasuk input yang akan dipakai) |
| `--max` | batas actor per invokasi, default 5 — batch kecil dulu, jangan 121 sekaligus |
| `--memory 1024` | default skrip, **bukan** 4096 platform; `apify-actor-start` menagih 1 event per GB |
| Abort kuota | berhenti otomatis setelah 3 error kuota berturut-turut (regex `usage limit\|quota\|payment required\|…`) |
| Resumable | log JSONL `output/publish_log_v7.jsonl`; actor yang sudah sukses dilewati saat diulang |
| Input termurah | integer bernama `max/limit/count/pages/results/items` di-cap ke 5 — tujuannya run sukses, bukan panen data |
| Token aman | setiap pesan error dilewatkan `scrub()` sebelum dicetak/dilog |

**Bug yang sudah diperbaiki saat penulisan:** `waitForFinish` API Apify **dibatasi 60 detik**. Memakainya
sebagai satu-satunya penungguan membuat actor yang lebih lambat balas `RUNNING`, sehingga run yang
sebenarnya sukses **tidak akan pernah diterbitkan**. Skrip sekarang start dengan `waitForFinish=60` lalu
polling `/actor-runs/{id}` tiap 10 detik sampai status terminal.

### Urutan eksekusi

**#0 — ~~Publish `clutch-agency-directory-scraper`~~.** ❗ **Sudah terbit** di `fanndev` dengan 2 user.
Klaim "belum terbit" di laporan pagi dan di arsip 2026-09-15 keliru. Diganti oleh:
**terbitkan 22 actor di atas, lalu batch-run 121 sisanya.**

**#1 — Recon transkrip YouTube lewat proxy residential. Satu perintah, bukan satu sprint.**

> ⚠️ **Terblokir kredensial, bukan teknis.** Skrip siap di `scratchpad/probe_v7e.py` (menguji 4 jalur
> berdampingan: tanpa proxy · DATACENTER · RESIDENTIAL US · RESIDENTIAL ID, dan tidak pernah mencetak rahasia).
> `~/.apify/auth.json` **tidak memuat API token maupun password proxy** — hanya daftar grup. Akun `fanndev`
> **punya grup `RESIDENTIAL`** (plan FREE; grup lain: `BUYPROXIES94952`, `GOOGLE_SERP`, `UNBLOCKER`).
> Untuk menjalankan: `set APIFY_TOKEN=<token>` lalu `python scratchpad/probe_v7e.py`.

Jalankan ulang `scratchpad/probe_v7c.py` dengan `RESIDENTIAL`. Keputusannya biner:
segmen keluar → langsung build 3 mode (§8 #1); tetap 0 KB → lanjut ke `youtubei/v1/get_transcript`
dengan token panen halaman (skill `warm-page-token-harvest`); gagal juga → tinggalkan, naikkan #2.
**Jangan mulai menulis actor sebelum langkah ini selesai.**

**#2 — Build Tech Stack Detector.** (§8 #2) Permukaan sudah terverifikasi, kode 80% ada di
`shopify-store-analyzer`. *Note:* mulai dari ~60 teknologi terlaris, bukan 2.000. Harga PPE $0,01–0,02/domain.
**Ini kandidat yang paling mungkin selesai dalam satu sesi** — kerjakan ini kalau #1 tersendat.

**#3 — Kalibrasi harga `xtracto`.** (§9) `u30` turun 955 → 945 sementara `ok30` naik: pembeli berkurang,
pemakaian per pembeli naik — pola khas harga yang salah letak. Langkah 1a–1d di arsip pagi tidak berubah:
ambil pendapatan riil 30 hari dari Console, hitung `faktor_item_per_run`, lalu ubah **2–3 actor saja**
dan tunggu satu siklus 30 hari.

**#4 — Kleinanzeigen Immobilien.** (§8 #3) **Selector sudah dipetakan (§7b) — langsung tulis parser.**
Kartu = `<article data-adid>`; ID+judul dari `href="/s-anzeige/<slug>/<adid>-…"`, harga/lokasi/atribut via regex
di dalam kartu. Jangan cari kelas BEM `aditem-main--*`: situsnya sudah didesain ulang ke kelas utilitas.

**#5 — Dua celah rak sendiri:** mode `sales-history` di `tcgplayer-price-scraper` (§8 #4a) dan
angka keandalan Google Hotels di README (§8 #4b). Keduanya jam-an, bukan harian.

**#6 — Klaster direktori Jerman** (`dastelefonbuch` + `gelbeseiten`) dan **klaster referensi konsumen**
(`fragrantica` + `goodreads`) — masih berdiri, turun prioritas karena §8 #1–#3 lebih besar atau lebih murah.

**#7 — Keputusan Apple Maps** (§8 #5): bayar $99/tahun Apple Developer untuk rak $5.119, atau coret permanen.
Jangan diprobe lagi tanpa keputusan ini.

**#8 — Recon yang sudah ditutup, jangan diulang tiap putaran:** `hrs.de` (teks ulasan tidak ada di HTML
maupun RSC), `housesigma.com` (semua endpoint minta `Bearer`, token anonim tidak dibagikan),
`handelsregister.de` (timeout ×3), USPTO, trip.com. Kelimanya sudah menghabiskan jatah recon-nya (§7, §7b).

### Ditolak permanen (bertambah putaran ini)

PII & skip-trace (`realtyapi`/`one-api/skip-trace` $1.575, `dievio`/`x_guru` $763, `data_link_miner` $6.425,
`build_matrix/company-employees-scraper` $1.971, RocketReach, Apollo, Instantly, `eduair94/whatsapp-data-lookup`,
Truecaller, Dubai unit-number), TecDoc (lisensi B2B), darkweb, view/traffic generator,
**`handelsregister.de` (timeout ×3)**, **USPTO merek dagang (semua API berkunci)**,
**trip.com (cangkang terkonfirmasi Pass 5b)**, **`hrs.de` (§7b)**, **`housesigma.com` (§7b)**.

---

## 12. Discord — permukaan dipetakan & 1 actor dibangun (2026-09-21)

**`discord-server-scraper` — 9 mode, SHIPPED.** Ide awal (arsip pesan, monitor kata kunci,
analisa tiket) semuanya butuh **bot token yang sudah diundang ke server target** — itu kredensial
per-pembeli, bukan sesuatu yang scraper bisa sediakan; alternatifnya user token = *self-botting*,
pelanggaran ToS yang bisa kena ban. Keduanya dicoret sebelum probe. Pertanyaannya diganti:
**apa yang Discord sajikan ke klien anonim?** Jawabannya jauh lebih besar dari dugaan.

### Terbuka (anonim, 12 profil TLS, semua 200)
| Endpoint | Isi |
|---|---|
| `/api/v10/invites/{code}?with_counts=true` | **resolver universal** — jalan untuk server yang TIDAK ada di Discovery (mayoritas Discord). Member + online count live, boost, boost tier, verification level, server tag |
| `/api/v10/guilds/{id}/widget.json` | 100 member online + voice channel, **hanya kalau owner mengaktifkan** (else 403 `50004`) |
| `/api/v10/applications/{id}/rpc` | metadata publik bot/app |
| `/servers`, `/servers/{kategori}` | SSR, Algolia, **~53.000 server**, bisa dijalani penuh |
| `/servers/{slug}-{id}` | SSR profil penuh + **`social_links`** (GitHub/X/Patreon/YouTube komunitas) = permukaan lead-gen |
| `/trending-games[/{tanggal}][/category/{slug}]` | chart mingguan + delta pemain W/W + riwayat |
| `/game/{slug}-{id}` | profil game |

### Tertutup (401/403 — jangan diulang)
`/guilds/{id}/preview` · `/discoverable-guilds` · `/discovery/categories` · `/guilds/{id}/scheduled-events`
· `/application-directory` (200 tapi **kosong** — CSR, fetch-nya butuh token; pakai `/applications/{id}/rpc`)

### ❗ Koreksi metode 8 — matriks TLS yang terbelah rapi bisa jadi rate limit, bukan gerbang
Matriks 12 profil pada `/servers?query=` menghasilkan **6 Chrome pertama 200, 6 Safari/Firefox/Edge
berikutnya 429** — terlihat persis seperti gerbang "harus Chrome". **Salah.** Dua kontrol:
(1) Safari **duluan** setelah jeda 30 dtk, spasi 6 dtk → Safari/Firefox/Edge/Chrome semua 200;
(2) Chrome sendirian tanpa jeda → 200 ×6 lalu **429 di request ke-7**.
Gerbangnya **volume per-IP (~6 request beruntun)**, sidik jari tidak relevan. 16 request @2,5 dtk = 0 blokir.
**Aturan baru: kalau matriks profil terbelah rapi mengikuti urutan jalannya, jalankan ulang terbalik
sebelum menulis "TLS gate".** (Ini kebalikan dari pola Blibli/PSA/Glints yang gerbangnya memang per-sidik-jari.)

`/api/v10` sendiri tidak dibatasi sama sekali — burst 25 request → 25×200, tanpa header `x-ratelimit-*`.
Karena itu client-nya punya **dua tier pacing terpisah** (2,0 dtk halaman SSR vs 0,4 dtk API).

### Dekoy & jebakan
* **`?q=` di `/servers` dibuang diam-diam** → 200 dengan listing home tanpa filter + `nbHits` seluruh indeks.
  Run yang memakainya **terlihat sukses** dan mengembalikan server generik untuk setiap kata kunci.
  Parameter aslinya **`query=`**. (Pola yang sama dengan `/c?q=` Etsy dan `l=` Yellow Pages.)
* **`?week=` di `/trending-games` juga dibuang** — tanggal itu segmen PATH.
* **`/trending-games/1999-01-01` balas 200 dengan chart MINGGU BERJALAN, bukan 404.** Jalan-mundur
  yang menambah 7 hari per langkah akan diam-diam mengisi dataset dengan duplikat. Actor mengikuti
  `prev_week_date` dari payload dan mencocokkan tiap respons dengan minggu yang diminta.
* `length=` diterima lalu diabaikan — **12 server/request itu keras**. 1.000 server = 84 request.
* **Hanya 5 dari ~50 id kategori punya halaman**: gaming(1), music(2), entertainment(3),
  science & tech(5), education(6). Cryptocurrency/Finance/Anime/Memes/Esports **404** — cuma tag
  di record, dijangkau lewat keyword search.
* `/servers/category/gaming` = 404; kategori ada di path telanjang `/servers/gaming`.
* **Slug itu kosmetik** — `/servers/{apa-saja}-{id}` dan `/servers/{id}` sama-sama resolve; hanya
  snowflake di ekor yang dikunci. (Kebalikan Etsy, di mana slug salah = fatal.)
* `nbHits` **melayang** (52.973 → 52.579 dalam hitungan detik) — jangan pernah jadi batas loop.
* Member widget **dianonimkan oleh Discord sendiri**: `id` = indeks dalam respons ("0","1","2"),
  bukan snowflake user. Join antar-run akan memasangkan orang yang tidak berhubungan.
* Dua sumber angka **beda sedikit dan dua-duanya benar**: invite Python lapor 431.648/34.152
  sementara halaman Discovery-nya 431.638/30.984 dalam selang detik — jadwal komputasi berbeda.

### Format SSR: TanStack Router + seroval
Data di `<script nonce>` terbesar, **bukan JSON**: key identifier telanjang, boolean `!0`/`!1`,
`void 0`, dan penanda `$R[n]=` di setiap nilai. Ditulis tokenizer penuh (`src/serialized.py`)
karena deskripsi server itu teks bebas — ditemukan nama server yang memuat `{id:` verbatim,
cukup untuk merusak pendekatan hitung-kurung apa pun. **Dua hal yang ketahuan hanya karena
diuji ke halaman hidup, bukan dari menalar format:** (1) **key objek numerik** `{0:32,1:24579}`
di `aggregateFacets` — parser key identifier-saja mati tepat di payload yang membawa total facet
direktori; (2) back-reference `$R[n]` telanjang saat ini **nol** di semua halaman, tapi tetap
diresolusi karena seroval memancarkannya begitu sebuah payload mengulang subtree.

### Tidak layak jadi mode
`/guilds/templates/{code}` (terbuka, tapi kode langka & tak bisa dienumerasi) ·
`/sticker-packs` (terbuka, 136 KB katalog Nitro — data marketing statis) ·
`/gateway` (terbuka, 1 URL WebSocket, tak berguna tanpa token).

### Verifikasi
`python test_local.py` → **116 asersi lulus**. Offline: 10 kasus tokenizer (kutip & kurung
ter-escape di dalam string, emoji surrogate pair, key numerik, lubang array, back-reference)
+ seluruh parser terhadap fixture 2026-09-21. Live: **9/9 mode** terhadap discord.com, meng-asersi
perilaku bukan sekadar status — keyword benar-benar memfilter, paginasi tidak menduplikasi,
invite mati → baris `not_found`, widget mati → `widget_disabled`, 2 minggu riwayat → 2 minggu
**berbeda**, `serverSnapshot` benar-benar menggabung ≥2 permukaan. 17 request, 0 kena rate limit.

### ❗ Jebakan platform yang menggigit lagi: `id: null` vs output schema
Run cloud pertama `serverSnapshot` **gagal exit 91, 0 record**:
`apify_client.errors.InvalidRequestError: Schema validation failed` pada `push_data`.
Sebabnya `output_schema.json` mendeklarasikan `id` sebagai `"type":"string"`, sementara
**setiap baris diagnostik membawa `id: null`**. Apify memvalidasi **seluruh batch** — satu baris
error menjatuhkan seluruh push. Dua mode yang jalan sebelumnya (`discoverySearch`, `trendingGames`)
lolos **hanya karena kebetulan tidak menghasilkan satu pun baris diagnostik**.
Perbaikan: `"type": ["string","null"]`. Ini pengulangan gotcha yang sama dari
Skool/Whop Community Analyzer — sekarang ditutup permanen dengan **tes regresi lokal**
(`test_dataset_schema()`) yang memvalidasi tipe tiap field terhadap `output_schema.json`
memakai batch yang **sengaja memuat baris error**, jadi kelas bug ini ketahuan di mesin lokal,
bukan di cloud. **Aturan: setiap actor baru wajib punya tes ini sebelum push pertama.**
