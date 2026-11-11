# Riset Pasar Apify Store — v2: Scan Lintas-Kategori (bukan Country-by-Country)

**Tanggal riset:** 2026-09-07
**Akun pembanding (jangan sampai duplikat):** [`xtracto`](https://api.apify.com/v2/store?username=xtracto) — di-refresh ulang hari ini via `apify-my-store.py xtracto`, **218 actor published** (naik dari 205 di snapshot 2026-08-10).
**Riset sebelumnya (baca dulu sebelum lanjutkan riset ini):** [`ACTOR_MARKET_RESEARCHER_NEW.md`](ACTOR_MARKET_RESEARCHER_NEW.md) — sudah 37+ babak, sangat matang untuk pola **"data-type terbukti × yurisdiksi/negara kosong"** (tender, court judgments, business registry per-negara kecil). Dokumen v2 ini **melengkapi, bukan mengulang** riset itu — lihat [Metodologi](#metodologi) untuk bedanya.
**Sumber data:** Algolia `prod_PUBLIC_STORE` via `api-search-actors.py` (14 kategori mainstream, 721 actor unik terkumpul) + 54 keyword-competition query lintas ecommerce/business/social/professional-data.

## ⚠️ Penting: `xtracto` BUKAN akun yang isinya folder actor di repo ini

Cross-check folder actor lokal (214 folder, mis. `nytimes-scraper`, `substack-scraper`, `bluesky-scraper`, semua actor tender/registry per-negara) vs isi live `xtracto-full.json` → **212 dari 214 folder TIDAK ada di store `xtracto`**. Jadi `xtracto` adalah **akun kedua yang terpisah**, persis seperti disebut user, isinya **218 actor generik** (Shopee, TikTok, Instagram, YouTube, Walmart, Reddit, Pinterest, eBay, LinkedIn, dll — hampir semua platform besar) yang **hampir semuanya cuma 1–5 users** (strategi "spray wide", beda total dari akun utama di repo ini yang fokus niche ekstrem dan actor unggulannya jauh lebih laku, mis. `nytimes-scraper` 57 users/260rb runs).

**Implikasi buat riset ini:** dedupe HARUS dicek terhadap `xtracto-full.json`, bukan terhadap folder repo. Detail lengkap 218 actor ada di `output/xtracto-full.json`.

---

## Metodologi

Beda dari babak 9–37 (yang menebak nama platform spesifik per negara satu-satu — job board, business registry, court judgments), v2 ini pakai **2 scan lebar** lebih dulu untuk cari "vein" yang belum pernah disentuh:

```bash
# refresh inventory xtracto dulu (wajib, sebelum lihat market)
python apify-my-store.py xtracto -o output/xtracto-full.json

# Pass 1 — 14 kategori mainstream (skip AUTOMATION/DEVELOPER_TOOLS/AI/AGENTS/MCP_SERVERS/OPEN_SOURCE,
# sesuai catatan skill: kategori itu didominasi SaaS/integrasi yang tidak relevan buat akun scraping)
# ECOMMERCE, SOCIAL_MEDIA, NEWS, TRAVEL, JOBS, REAL_ESTATE, LEAD_GENERATION, SEO_TOOLS,
# BUSINESS, MARKETING, SPORTS, FOR_CREATORS, VIDEOS, INTEGRATIONS — length=60/kategori, relevance order
# -> 721 actor unik terkumpul, difilter: 5<=users<=3000, runs>=3000, runs_per_user>=150

# Pass 2 — 54 keyword-competition query (tripadvisor, glassdoor, crunchbase, airbnb, zillow,
# g2 reviews, capterra, upwork, tender, company registry, dst) — length=15/keyword,
# dicatat top-5-users-sum (proxy demand) vs daftar seller aktual (bukan nbHits Algolia —
# lihat Gotcha di bawah, nbHits TERNYATA fuzzy/typo-tolerant dan TIDAK VALID sebagai proxy
# jumlah kompetitor, contoh: query "used cars" nbHits=51.052 padahal jelas noise)
```

Semua hasil mentah ada di:
- `output/scan-v2-categories-merged.json` (721 actor, Pass 1)
- `output/scan-v2-keyword-competition.json` (54 keyword, Pass 2, termasuk daftar seller per keyword)

### Gotcha metodologi (penting buat riset berikutnya, biar tidak diulang)

1. **`nbHits` dari `search_store()` TIDAK BISA dipakai sebagai proxy jumlah kompetitor.** Algolia query tanpa `restrictSearchableAttributes` itu fuzzy/typo-tolerant ke seluruh index — `--query "used cars"` balikin `nbHits=51.052` padahal itu jelas match teks umum di seluruh 57rb actor, bukan 51rb actor "used cars". Proxy yang benar: hitung manual seller **distinct** dari daftar `hits` yang benar-benar relevan (nama/judul match konsep), sama seperti metodologi babak 9+ di riset lama.
2. **Nama actor (`name`/slug) TIDAK unik lintas akun.** Beberapa seller berbeda bisa punya actor dengan slug identik persis (mis. `walmart-reviews-scraper` ada versi `web_wanderer` DAN versi `xtracto`, keduanya actor yang sama sekali berbeda). Dedupe otomatis berbasis nama-saja **menghasilkan false positive DAN false negative** — contoh nyata yang kejadian di scan ini: `redfin-scraper` (jupri, 782 users, band Pattern A) sempat lolos sebagai "kandidat baru" padahal `xtracto` sudah punya `redfin-listings` (nama beda tapi konsep identik). Solusi yang dipakai: cek token platform (mis. "redfin", "zillow") terhadap **seluruh** `xtracto-full.json` (nama+judul, 218 actor), bukan cuma cocokkan nama exact atau lihat top-8 hasil pencarian kompetitif.
3. **Cross-check WAJIB ke `ACTOR_MARKET_RESEARCHER_NEW.md` sebelum klaim "kandidat baru".** Beberapa hit di Pattern A kelihatan seperti hidden gem di scan dangkal (length=15-60, relevance order) padahal riset lama sudah membuktikan jenuh lewat query mendalam tanpa batas. Kasus nyata di bawah: `secretary-of-state-business-search`, `bundesagentur-fur-arbeit`, `fragrantica`, `opentable`, dan job board China (Zhaopin/Liepin/51job) — semua sempat kelihatan "1 seller kecil" di scan v2 ini, tapi riset lama (babak 9b-area, line 82/88/865/1597/1609 di `ACTOR_MARKET_RESEARCHER_NEW.md`) sudah membuktikan itu 4–8+ seller begitu di-query tuntas.

---

## ✅ Kandidat Baru (belum ada di `xtracto`, belum pernah diverifikasi jenuh di riset lama)

| Prioritas | Ide Actor | Bukti Demand | Kompetitor Ditemukan | Kenapa Layak |
|---|---|---|---|---|
| 🔴 Tinggi | **Generic Article/Readability Extractor** (URL apa pun → judul/byline/tanggal/teks bersih, mirip Mercury Parser/Readability) | `web.harvester/articles-extractor` — 760 users, 902.927 runs (1.188 rpu) | 1 seller ditemukan di scan ini, belum pernah dicek di riset lama | **Moat reuse tertinggi**: akun utama (repo ini) sudah py 100+ scraper artikel per-outlet — logic ekstraksi/boilerplate-removal sudah matang, tinggal digeneralisasi jadi 1 actor generik. Beda produk (tool generik) dari yang sudah ada (scraper per-outlet), jadi bukan duplikat konsep. |
| 🔴 Tinggi | **StreetEasy Scraper** (listing jual/sewa NYC — data terlengkap real estate kota besar AS) | `jupri/streeteasy-scraper` — 214 users, 1.954.364 runs (9.133 rpu), **1 seller** | 1 (unfiltered, dicek manual) | Real estate per-KOTA (bukan per-negara) belum pernah jadi fokus riset lama (babak 9+ fokus real estate per-NEGARA). `jupri` jual banyak varian travel/real estate lain dengan pola serupa (Airbnb Explorer, Zillow Explorer, dll) — indikasi niche kota besar AS belum banyak digarap. |
| 🟠 Sedang-Tinggi | **Apartments.com Scraper** (listing sewa apartemen AS, volume tinggi) | `epctex/apartments-scraper` (1.012u/4,47jt runs) + `apartments-scraper-api` (361u/896rb runs), rating 5.0 (12 & 11 review) | 1 seller (`epctex`, 2 produk) | Demand besar & konsisten (2 produk dari seller sama, rating sempurna) — bukti TAM nyata. Perlu sudut beda dari `epctex` (mis. filter/format lebih fleksibel, coverage kota tambahan) sebelum eksekusi. |
| 🟡 Sedang | **Indeed Reviews** (ulasan karyawan — beda data-type dari Indeed Jobs yang sudah dipunya `xtracto`) | `memo23/apify-indeed-reviews` — 287 users, 319.072 runs (1.112 rpu) | 1 ditemukan, tapi `memo23` adalah seller sistematis yang disebut berkali-kali di riset lama (kemungkinan akan meng-clone niche apa pun yang terbukti laku) | Data-type belum dipunya `xtracto` (yang ada cuma job POSTINGS, bukan REVIEWS). Verifikasi lebih dulu apakah sudah ada seller lain masuk sebelum eksekusi — jangan asumsikan `memo23` sendirian selamanya. |
| 🟡 Sedang | **Upwork Freelancer/Talent Profile Scraper** (data profil freelancer, BUKAN job postings) | Gabungan: `parseforge` 341u, `powerai` 173u, `bovi` 60u, `sian.agency` 53u, `crw` 21u — total demand modest (~650u) | ~5 seller — moderat, bukan "sepi banget" | Upwork JOB POSTINGS sendiri sudah sangat jenuh (12+ seller termasuk `jupri`, `neatrat`, `upwork-vibe`, `kobimantzur`, dll) — SKIP itu. Tapi sub-niche TALENT/FREELANCER PROFILE punya seller lebih sedikit. Hanya layak kalau ada sudut beda jelas (mis. filter skill/rate spesifik). |
| 🟢 Rendah-Sedang | **Crunchbase (sub-niche funding/investor, bukan company profile generik)** | Gabungan 7 seller (`pratikdani` 1.100u, `curious_coder` 3.378u, `vulnv` 471u, `saswave` 821u, `scrapefull` 404u, `davidsharadbhatt` 180u, `complex_intricate_networks` 311u) | 7 seller — sudah cukup ramai untuk company-profile generik | Company profile generik sudah jenuh. Kalau mau masuk, cari data-type spesifik yang belum ada (mis. investor portfolio, funding-round timeline) — bukan kloning ke-8. |
| 🟢 Rendah | **ImmobilienScout24 Scraper** (portal real estate #2 Jerman, setelah Immobilien.de) | `igolaizola/immobilienscout24-scraper` — 79 users, 78.826 runs (998 rpu), 1 seller | 1 | TAM absolut kecil (79 users). `igolaizola` sendiri sudah py banyak actor real estate Eropa (idealista, dll) — kemungkinan pasarnya memang kecil, bukan belum ditemukan. Prioritas rendah, catat saja. |
| ⚪ Catatan saja (di luar strategi) | **Cloud Storage Uploader** (S3/GCS — generic utility, BUKAN scraper) | `apify/s3-uploader` (55u/3,5jt runs — official Apify) + `circ_le/gcp-uploader` (50u/587rb runs) | 2 (genuinely tipis) | Niche genuinely sepi, tapi **kategori DEV_TOOLS/AUTOMATION** — di luar fokus akun (yang bisnisnya scraping, bukan tooling). Dicatat sebagai referensi, bukan rekomendasi aktif. |

---

## 🔁 Sudah Dibangun oleh `xtracto` (verified via full-inventory grep, bukan cuma top-8 hasil pencarian)

Konsep-konsep ini muncul di Pattern A/B scan v2 tapi setelah dicek **seluruh** `xtracto-full.json` (bukan cuma nama exact), `xtracto` **sudah punya** actor untuk platform ini (meski kebanyakan traksinya masih 1–5 users):

| Platform/Konsep | Actor `xtracto` yang sudah ada |
|---|---|
| TripAdvisor | `tripadvisor-scraper` (5u), `tripadvisor-reviews-scraper` (3u) |
| Indeed Jobs | `indeed-jobs-scraper` (4u) |
| Reddit | `reddit-subreddit-posts-scraper`, `reddit-post-detail-scraper`, `reddit-user-profile-scraper`, `reddit-search-scraper` |
| Glassdoor | `glassdoor-reviews` (3u), `glassdoor-jobs` (3u), `glassdoor-company` (2u) |
| Airbnb | `airbnb-occupancy` (39u), `airbnb-reviews-scraper` (3u), `airbnb-scraper` (3u) |
| Zillow | `zillow-all-in-one-scraper` (2u) |
| YouTube | 7 actor (search, shorts, playlist, video detail, comments, channel, sponsor detector) |
| Pinterest | 4 actor (user profile, board, search, pin detail) |
| Trustpilot | `trustpilot-reviews` (2u) |
| Walmart | 4 actor (seller, reviews, search, product) |
| Capterra | `capterra-b2b-scraper` (1u) |
| Amazon | `amazon-products-scraper`, `amazon-reviews-scraper` |
| Booking/Hotel | `booking-hotels-scraper` (5u), `agoda-hotels-scraper` (15u) |
| Etsy | 3 actor (product, search, shop) |
| Google (Maps/Reviews/Trends/dll) | 10 actor |
| eBay | 4 actor (sold comps, product, bid history, search) |
| TikTok | 6 actor (trending, profile, comments, post detail, top ads, search) |
| LinkedIn | `linkedin-company-profile`, `linkedin-jobs-scraper` |
| Instagram | 7 actor |
| Flight (Skyscanner) | `skyscanner-scraper` (116u — traksi terbaik di antara semua actor `xtracto`) |
| Shopee | 4 actor |
| Alibaba | `alibaba-search-scraper` |
| Redfin | `redfin-listings` (2u) — **catatan penting**: beda nama dari `redfin-scraper` (kompetitor `jupri`, 782u) yang sempat lolos scan sebagai kandidat, ternyata konsepnya sudah dipunya |
| GLEIF/LEI (Legal Entity Identifier) | `gleif-lei` (1u) |

---

## ⛔ Di-skip

| Niche | Alasan | Sumber Verifikasi |
|---|---|---|
| **Secretary of State Business Registry (AS)** | Sudah 6+ seller (`whetstonetools` 90u/10.891 runs terbesar) | Riset lama, `ACTOR_MARKET_RESEARCHER_NEW.md` baris ~1597 |
| **Bundesagentur für Arbeit (job board resmi Jerman)** | Sudah 6 seller (`lexis-solutions` 512u dominan) | Riset lama, baris ~82 |
| **Fragrantica.com Scraper** | Sudah 6 seller, TAM kecil (niche parfum) | Riset lama, baris ~88 |
| **OpenTable** | Sudah ramai — cluster dengan DoorDash/Grubhub, semua sudah dikuasai (`yasmany.casanova`, `memo23`, `easyapi`, dll) | Riset lama, baris ~1609 |
| **Job board China (Zhaopin, Liepin, 51job, ChinaHR)** | Awalnya kelihatan "1 seller kecil" di scan v2 ini (Liepin 22u, Zhaopin 32u) — TAPI riset lama sudah verifikasi mendalam: **semua 4–8+ seller** begitu di-query tanpa batas | Riset lama, baris ~865 ("Job board per-negara ... semua tanpa kecuali sudah 4-8+ seller") |
| **Upwork Job Postings** (bukan freelancer/talent) | 12+ seller berbeda (`jupri`, `neatrat`, `upwork-vibe`, `kobimantzur`, `devcake`, `matthewjames`, `flash_mage`, `blackfalcondata`, dll) — sangat jenuh | Scan v2 Pattern A+B gabungan |
| **Similarweb Website Analytics** | 4 seller aktif (`pro100chok`, `radeance`, `mscraper`, `tri_angle`) meski masing-masing user-nya kecil — jenuh, bukan sepi | Scan v2 Pattern A |
| **TecDoc / Automotive Parts Catalog** | BUKAN hidden gem — `making-data-meaningful/tecdoc` sudah 2.095 users, incumbent besar sendirian. RPU tinggi (14.623) di sini cuma bukti volume bisnis si incumbent, bukan sinyal "belum ditemukan" | Scan v2 Pattern A (salah tafsir awal, dikoreksi di sini) |
| **Generic keyword scan lain yang match cluster company-registry/tender/court-records global** (GLEIF varian lain, Handelsregister.de, Moneyhouse.ch, PhilGEPS, TED EU Tenders, SEC EDGAR, USPTO trademark/patent, WHOIS domain, court records AS) | Semua sudah dianalisis MENDALAM di riset lama sebagai bagian sweep 30+ negara/target — semua 2–8+ seller. **Jangan scan generik lagi** — riset lama sudah menyimpulkan (baris ~1688) strategi yang lebih produktif: ambil data-type yang **terbukti laku**, cari **yurisdiksi yang masih kosong** — bukan menebak nama platform baru | Riset lama, multi-baris (lihat bagian "~30 ide data publik pemerintah AS" dan "Business/company registry per-negara") |

---

## 🌊 Klaim "kategori sepi = blue ocean" — DITARIK setelah verifikasi

Facet count awal (`--list-categories`) menunjukkan **SPORTS** (194 actor total) dan **FOR_CREATORS** (236 actor total) jauh lebih kecil dari kategori lain (ECOMMERCE 14.573, LEAD_GENERATION 26.333) — kelihatan seperti "kategori belum digarap". **Setelah cross-check ke riset lama, klaim ini salah untuk SPORTS**: sub-niche paling bernilai di SPORTS (odds/betting data) justru sudah dikuasai 8+ seller (`zen-studio`, `parseforge` — sendirian punya 5 actor sumber berbeda, `scrapemint`, `zhorex`, `automation-lab`, `ichigowa`, `nortonw3`, `extractify-labs`, `piotrv1001`). Sub-niche non-odds di SPORTS (raw match stats: MLB, tennis, injury reports — semua di scan v2 ini masih di bawah 300 users per actor, tapi belum diverifikasi mendalam) **mungkin masih ada celah, tapi butuh sesi riset khusus** — jangan langsung eksekusi dari sinyal facet count saja.

FOR_CREATORS: TAM kelihatannya kecil juga secara kualitatif — isinya didominasi "downloader" tools (YouTube/TikTok/Bandcamp downloader) yang cenderung dianggap komoditas/gratis oleh user, sulit dimonetisasi PAY_PER_EVENT. Tidak direkomendasikan tanpa sinyal demand tambahan dari luar Apify.

---

## Rekomendasi & Status untuk Build ke Depan

1. **Prioritas eksekusi (kalau mau langsung jalan):**
   - **Generic Article Extractor** — highest moat-reuse, effort rendah (kombinasi ulang logic dari 100+ scraper artikel yang sudah ada), TAM terbukti (760 users di kompetitor tunggal).
   - **StreetEasy Scraper** — real estate kota besar AS, 1 seller, demand kuat (9.133 rpu).
   - **Apartments.com** — perlu riset kecil dulu untuk cari sudut beda dari `epctex` sebelum commit.
2. **Butuh riset lanjutan sebelum diputuskan:**
   - SPORTS non-odds (MLB/tennis/injury/live-scores raw stats) — belum diverifikasi mendalam seperti odds/betting.
   - Indeed Reviews & Upwork Talent — perlu cek ulang jumlah seller aktual (bukan cuma top-8 hasil scan v2 ini) sebelum eksekusi, karena `memo23` dkk terbukti agresif meng-clone niche yang laku.
3. **Jangan diulang** (sudah tuntas diverifikasi jenuh, ada di tabel Di-skip di atas): job board per-negara/generic, business/company registry generik, tender/procurement generik, court records generik, secretary-of-state, Bundesagentur, Fragrantica, OpenTable, Similarweb, Upwork Job Postings.
4. **Update proses dedupe untuk riset berikutnya:** selalu refresh `xtracto-full.json` dulu (`python apify-my-store.py xtracto -o output/xtracto-full.json`), cek token platform terhadap SELURUH isi file itu (bukan cuma exact-name match atau top-8 hasil pencarian), dan **grep `ACTOR_MARKET_RESEARCHER_NEW.md`** untuk nama platform/niche sebelum mengklaim "kandidat baru" — dokumen itu sudah 37+ babak dan mencakup jauh lebih banyak niche daripada yang kelihatan dari judul babak-babaknya saja.

## File Referensi

- `output/xtracto-full.json` — snapshot 218 actor `xtracto`, 2026-09-07
- `output/scan-v2-categories-merged.json` — 721 actor unik dari 14 kategori (Pass 1)
- `output/scan-v2-keyword-competition.json` — 54 keyword + daftar seller (Pass 2)
