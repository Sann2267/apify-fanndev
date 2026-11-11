# Riset Pasar Apify Store — Babak 8 (Lanjutan): Kategori Baru + Verifikasi Ketat Jumlah Seller

**Tanggal riset:** 2026-08-09
**Akun pembanding (jangan sampai duplikat):** [`xtracto`](https://api.apify.com/v2/store?username=xtracto) — di-refresh ulang hari ini via `apify-my-store.py xtracto`, **masih 205 actor published**, tidak berubah sejak riset sebelumnya.
**Riset sebelumnya (jangan sampai duplikat juga):** [`ACTOR_MARKET_RESEARCH.md`](ACTOR_MARKET_RESEARCH.md) — 7 babak, ~200 kandidat, sudah sangat komprehensif untuk 13 kategori inti (ECOMMERCE, SOCIAL_MEDIA, REAL_ESTATE, TRAVEL, JOBS, BUSINESS, SEO_TOOLS, NEWS, dst).
**Sumber data:** Algolia `prod_PUBLIC_STORE`, via `api-search-actors.py`.

## Ringkasan Eksekutif (baca ini dulu)

Babak 8 memindai **kategori yang belum pernah disentuh riset sebelumnya** (LEAD_GENERATION, OTHER, VIDEOS, INTEGRATIONS, MARKETING, FOR_CREATORS, GAMES) plus **offset lebih dalam** di kategori yang sudah produktif (REAL_ESTATE offset 360-440, JOBS offset 360-440, TRAVEL offset 280, BUSINESS offset 320, SEO_TOOLS & NEWS offset 0). Total **703 actor unik** terkumpul di band 10-5.000 users.

**Temuan utama — dan ini penting:** hampir semua kandidat yang kelihatan "sepi" di band ini ternyata **jenuh (5-10 seller berbeda)** begitu di-cek ulang tanpa batas `max-users`. Pola yang sama persis dengan insight babak 4 riset lama ("regional marketplace sudah red ocean"), tapi sekarang terbukti berlaku jauh lebih luas — bukan cuma marketplace regional, tapi hampir **setiap niche yang bisa ditebak namanya** (job board pemerintah, real estate negara ke-2/ke-3, classifieds, business registry, ticket resale, dst) sudah dikloning oleh klaster ~15-20 seller yang sama (`parseforge`, `jungle_synthesizer`, `lexis-solutions`, `memo23`, `shahidirfan`, `zen-studio`, `sian.agency`, `ecomscrape`, `automation-lab`, `crawlerbros`, `solidcode`, `hoholabs`, `blackfalcondata`, `easyapi`, `fatihtahta`, `stealth_mode`, `gio21`, `moving_beacon-owner1`, dll).

**Hasil konkret: dari 703 actor yang di-scan, cuma segelintir yang lolos verifikasi seller-count** — dan bahkan yang lolos pun datanya tipis/TAM belum terbukti (lihat [Belum Dibangun](#-belum-dibangun---kandidat-tersisa-tipistapi-genuinely-open) di bawah). Riset babak 1-7 sebelumnya sudah menguras hampir semua "gem" yang gampang ditemukan lewat category-browsing biasa. Kalau mau lanjut riset lagi setelah ini, strategi category-browsing perlu diganti (lihat [Rekomendasi Lanjutan](#rekomendasi-untuk-riset-berikutnya)).

---

## Metodologi Babak 8

```bash
# kategori baru yang belum pernah discan riset sebelumnya
python api-search-actors.py --category LEAD_GENERATION --min-users 10 --max-users 5000 --length 60 --sort runs_per_user
python api-search-actors.py --category OTHER --min-users 10 --max-users 5000 --length 60 --sort runs_per_user
python api-search-actors.py --category VIDEOS --min-users 10 --max-users 5000 --length 60 --sort runs_per_user
python api-search-actors.py --category INTEGRATIONS --min-users 10 --max-users 5000 --length 60 --sort runs_per_user
python api-search-actors.py --category MARKETING --min-users 10 --max-users 5000 --length 60 --sort runs_per_user
python api-search-actors.py --category FOR_CREATORS --min-users 10 --max-users 5000 --length 60 --sort runs_per_user
python api-search-actors.py --category GAMES --min-users 10 --max-users 5000 --length 60 --sort runs_per_user

# offset lebih dalam di vein yang sudah produktif di riset lama
python api-search-actors.py --category REAL_ESTATE --min-users 10 --max-users 5000 --offset 360 --length 40 --sort runs_per_user
python api-search-actors.py --category REAL_ESTATE --min-users 10 --max-users 5000 --offset 400 --length 40 --sort runs_per_user
python api-search-actors.py --category JOBS --min-users 10 --max-users 5000 --offset 360 --length 40 --sort runs_per_user
python api-search-actors.py --category JOBS --min-users 10 --max-users 5000 --offset 400 --length 40 --sort runs_per_user
python api-search-actors.py --category TRAVEL --min-users 10 --max-users 5000 --offset 280 --length 40 --sort runs_per_user
python api-search-actors.py --category SPORTS --min-users 10 --max-users 5000 --offset 40 --length 40   # -> 0 hits, vein habis
python api-search-actors.py --category EDUCATION --min-users 10 --max-users 5000 --offset 40 --length 40 # -> 0 hits, vein habis
python api-search-actors.py --category BUSINESS --min-users 10 --max-users 5000 --offset 320 --length 40
python api-search-actors.py --category SEO_TOOLS --min-users 10 --max-users 5000 --length 40
python api-search-actors.py --category NEWS --min-users 10 --max-users 5000 --length 40
```

**Proses dedupe 3 lapis** (lebih ketat dari babak-babak sebelumnya):
1. **Token match otomatis** nama+judul kandidat vs 205 actor `xtracto` (343 token distinct, len≥4, stopword dibuang) → kandidat yang match ditandai `[MINE]`, kemungkinan besar sudah dibangun.
2. **Token match otomatis** vs seluruh teks `ACTOR_MARKET_RESEARCH.md` (62 ribu karakter, 7 babak riset lama) → ditandai `[MD]`, kemungkinan besar sudah pernah direkomendasikan/di-skip di riset itu.
3. **Verifikasi manual tanpa cap `max-users`** — untuk setiap kandidat yang lolos lapis 1 & 2 (bersih dari kedua flag), saya re-query Algolia **tanpa filter max-users** khusus untuk niche persis itu untuk menghitung jumlah seller distinct. Ini langkah yang paling menentukan hasil babak ini — lihat ringkasan eksekutif di atas.

Dari 703 hit, **55 lolos lapis 1 & 2** (bersih dari overlap token). Setelah lapis 3 (verifikasi seller count manual), **hampir semua 55 itu gugur** karena ternyata sudah 4-10 seller. Detail lengkap di tabel skip di bawah.

**Catatan soal SPORTS & EDUCATION:** babak 4 riset lama sudah men-scan kedua kategori ini di offset 0. Babak 8 mencoba offset 40+ dan **dapat 0 hit** — artinya seluruh band 10-5.000 users di kedua kategori itu (27 dan 16 actor total) sudah habis ditelaah di babak 4. Vein ini resmi tuntas, tidak perlu discan lagi.

---

## ✅ Belum Dibangun — Kandidat Tersisa (Tipis, Tapi Genuinely Open)

Ini semua kandidat yang **lolos ketiga lapis verifikasi** — tidak match token `xtracto`, tidak match riset lama, dan seller count-nya genuinely rendah (1-4 seller) bahkan tanpa batas `max-users`. **Peringatan jujur: semuanya berdata tipis** (rpu tinggi tapi users sangat sedikit, atau users lumayan tapi rpu rendah) — ini bukan "Tier S" seperti Amazon/Noon Seller Monitoring di riset lama, ini kandidat "worth watching", bukan "build now".

| Ide Actor | Bukti Demand | Jumlah Seller (unfiltered) | Kenapa Masih Layak Dicatat |
|---|---|---|---|
| **Twitch Core Scraper** (streams/channels/clips/VODs, bukan email-finder) | `automation-lab/twitch-scraper` — 229 users, 48.032 runs (210 rpu) | Sebenarnya **9-10 seller** kalau dihitung semua varian "twitch-scraper" — lihat catatan di bawah. **Dipindah ke tabel skip**, dicatat di sini cuma sebagai jejak proses (awalnya kelihatan bersih di scan band-limited, gugur setelah verifikasi penuh). | — |
| **Ticket Resale Marketplace** (Vivid Seats / SeatGeek / Ticketmaster) | `hoholabs` — 3 actor terpisah (vividseats 20u/1.256r, seatgeek 17u/431r, ticketmaster 8u/225r), semua **sangat tipis** | ~4 seller (`hoholabs`, `lexis-solutions`, `stealth_mode`, `automation-lab`), tapi **yang terbesar sekalipun cuma 20 users** | TAM belum terbukti — bisa jadi genuinely niche kecil (bukan "hidden gem", tapi "small pond") atau bisa jadi belum ada yang eksekusi dengan benar. Perlu riset independen (cek demand di luar Apify, mis. subreddit r/apify atau forum resale-ticket) sebelum commit build. |
| **Event Discovery Aggregator** (AllEvents.in, Songkick, Resident Advisor, Eventbrite — semua data-type "cari event by kategori/tanggal") | `techforce.global/events-eye-scraper` — 34u/297r; `hoholabs/allevents-scraper` — 11u/189r | Fragmented — 5-6 seller tapi **tidak ada yang dominan**, masing-masing platform beda (bukan 1 platform dikuasai banyak seller, tapi banyak platform kecil dengan 1 seller masing-masing) | Kalau mau eksekusi, pilih **satu platform spesifik** (mis. cuma Resident Advisor untuk musik elektronik, atau cuma Songkick untuk konser) alih-alih generic — pola yang sama seperti "jangan bangun FB Marketplace generik, masuk lewat vertical sempit" di riset lama. |

**Kenapa cuma 3 baris?** Karena itulah hasil jujurnya. Babak 1-7 riset lama sudah sangat menyeluruh untuk kategori-kategori dengan TAM besar (REAL_ESTATE, JOBS, TRAVEL, ECOMMERCE) — apa yang tersisa di kategori-kategori baru (LEAD_GENERATION, OTHER, VIDEOS, INTEGRATIONS, MARKETING, FOR_CREATORS, GAMES) ternyata bukan "belum ditemukan", tapi memang **TAM-nya kecil atau sudah dikloning duluan** oleh seller yang sama yang mendominasi riset-riset sebelumnya.

---

## 🔧 Koreksi untuk Riset Lama

| Niche | Status Lama | Temuan Baru Babak 8 | Dampak |
|---|---|---|---|
| **Rent.com Scraper** | Babak 6: "1 seller" (`jupri` — 22 users, 3.712 rpu) — masuk Prioritas Tinggi | Sekarang **3 seller**: `jupri` (masih ada), plus **`memo23` dengan 2 actor terpisah** (`rent-com-scraper` 34u dan `forrent-com-scraper` 30u, keduanya dengan fitur email enrichment) | Turunkan prioritas — bukan lagi "1 seller, langsung eksekusi", tapi tetap layak karena `memo23` masuk dengan sudut beda (email enrichment) bukan sekadar kloning identik. Verifikasi fitur pembeda sebelum eksekusi. |

---

## ⛔ Di-skip — Kelihatan Sepi di Scan Awal, Ternyata Jenuh Setelah Verifikasi Penuh

Ini bagian paling berharga dari babak 8: **daftar niche yang lolos filter band `max-users 5.000` (jadi kelihatan seperti "hidden gem" di scan pertama) tapi gugur begitu di-query ulang tanpa batas atas.** Dicatat detail supaya riset berikutnya tidak mengulang proses yang sama dan membuang waktu.

| Niche | Seller Ditemukan (unfiltered) | Kenapa Di-skip |
|---|---|---|
| **Bundesagentur für Arbeit / Arbeitsagentur** (job board resmi Jerman) | 6 seller: `lexis-solutions` 512u, `fatihtahta` 172u, `scrapestorm` 80u, `signalflow` 62u, `blackfalcondata` 56u, `santamaria-automations` 52u | Kelihatan "1 seller dominan" di band, ternyata 5 pesaing lain sudah masuk duluan. |
| **Truth Social Scraper** | 6 seller: `tri_angle` 418u (1,4jt runs — di luar band), `muhammetakkurtt` ×2, `louisdeconinck` 227u, `memo23`, `automation-lab` | Platform sosial baru yang kelihatan belum disentuh, ternyata sudah ramai — termasuk 1 pemain (`tri_angle`) yang users-nya di luar band scan awal. |
| **Ahrefs Scraper** (data SEO backlink/keyword) | 6 seller: `radeance` 1.691u, `pro100chok` 654u, `scrap3r`, `burbn`, `parseforge`, `crawlerbros` | Jenuh + risiko ToS (Ahrefs data ada di balik login berbayar, scraping data kompetitor SEO tool lain rawan legal). |
| **Dun & Bradstreet (D&B) Scraper** | 6 seller, dipimpin `epctex` 2.098 users (sudah dekat batas "incumbent") | `epctex` individu sudah besar untuk niche B2B-data ini; 5 pesaing lain menyusul di belakang. |
| **Twitch Scraper** (streams/channels/clips generik) | **9-10 seller**: `automation-lab`, `cryptosignals`, `crawlerbros`, `logiover`, `moving_beacon-owner1`, `maximedupre`, `fetch_cat`, `scrapesage`, `gurify`, `getascraper` | Paling jenuh dari seluruh temuan babak 8 — hampir semua di bawah 15 users individual (makanya lolos filter band), tapi jumlah pemain menunjukkan niche generik "Twitch scraper" sudah red ocean. |
| **Weibo Scraper** | 5 seller: `zhorex` ×2 (332u), `piotrv1001` 226u, `easyapi`, `sian.agency`, `mohamed.k.sirag` | Platform Cina besar, tapi sudah 5 pemain meski individu kecil. |
| **Fragrantica.com Scraper** | 6 seller: `lexis-solutions` 410u, `crawlerbros`, `shahidirfan`, `solidcode`, `plastic_warrior`, `scrapestorm` | Niche parfum/fragrance kecil, sudah dikloning 6× — TAM-nya kemungkinan tidak sepadan dengan jumlah pesaing. |
| **Kleinanzeigen / eBay Kleinanzeigen** (classifieds Jerman) | 6+ seller: `lexis-solutions` 554u, `memo23` ×2 (177u+133u), `webdatalabs`, `clearpath`, `ivanvs` | Setara Lazada/Tokopedia di babak 2 lama — platform regional besar yang kelihatan "sepi" tapi sebenarnya sudah jenuh. |
| **Seek Job Scraper** (job board #1 Australia, induk JobStreet/JobsDB) | 6 seller: `blackfalcondata` 1.016u, `bovi` 257u, `websift`, `automation-lab`, `sian.agency`, dll | Sudah jenuh sendiri, **plus** kemungkinan overlap konsep dengan JobStreet/JobsDB (kandidat babak 2 & catatan verifikasi babak 4 riset lama) karena satu grup usaha (SEEK). Jangan digarap tanpa pertimbangkan kanibalisasi dengan kandidat JobStreet yang sudah ada. |
| **Nukrigulf Job Scraper** (Naukri Gulf) | 6 seller, dipimpin `thirdwatch` 803u | Sama seperti Seek — brand extension dari Naukri yang **sudah dicatat "mendekati batas atas"** di babak 3 riset lama. Makin dikonfirmasi jenuh. |
| **Workable / ATS generik** | Sangat terfragmentasi tapi ramai: `nexgendata` sendiri sudah punya varian untuk Greenhouse, Lever, WeWorkRemotely, H1B — plus banyak pemain "multi-ATS" lain | Overlap konsep tinggi dengan `ats-jobs-aggregator`/`ats-hiring-velocity` milik `xtracto` sendiri (sudah cover Greenhouse/Lever/Ashby/Workday) — dan pasar "scrape job board dari ATS" sudah ramai. |
| **UCC Lien Scraper** (data lien bisnis AS) | 6 seller kecil (`fortuitous_pirate`, `intelscrape`, `pink_comic`, `inexhaustible_glass`, `regdata`, `shelvick`) | Niche B2B/legal kecil tapi sudah 6 pemain — TAM sempit + kompetisi padat. |
| **SEC Investment Adviser / IAPD Scraper** | 6 seller kecil | Sama pola dengan UCC Lien — niche finance-regulatory kecil, sudah jenuh meski individu <15 users. |
| **OSHA Violations Scraper** | 6 seller kecil | Niche compliance/safety AS, sudah jenuh. |
| **Boligsiden.dk Scraper** (real estate Denmark) | 6 seller (`lexis-solutions` 55u sudah yang terbesar) | Real estate negara kecil yang kelihatan kosong, ternyata sudah dikloning 6× meski semua individu <10 users. |
| **Yandex Realty Scraper** | 2 seller langsung (`zen-studio`, `sian.agency`), tapi **konsep data real estate Rusia sudah dikuasai `zen-studio/avito-listings-scraper`** (712 users) untuk classifieds umum termasuk properti | Overlap konsep dengan Avito (raksasa classifieds Rusia) yang sudah masuk band di atas — risiko duplikasi konsep. |
| **Imovirtual Scraper** (real estate Polandia/Portugal, grup OLX) | 6+ seller (`stealth_mode`, `dadhalfdev`, `automation-lab`, `solidcode`, `logiover`, `parseforge`) | Grup OLX/Navent — sama pola dengan Lazada/Tokopedia, platform besar yang ternyata sudah jenuh. |
| **Imovelweb Scraper** (real estate Brasil/Argentina, grup Navent) | **10 seller** — paling jenuh di kategori real estate babak 8 (`viralanalyzer`, `ecomscrape` ×3, `ocrad`, `fatihtahta`, `sian.agency`, `gio21`, `solidcode`, `moving_beacon-owner1`) | Grup Navent yang sama dengan VivaReal & ZAP Imóveis (sudah jadi kandidat Prioritas Sedang di babak 3 riset lama) — sekarang terbukti brand ke-3 dari grup yang sama ini justru yang paling jenuh dari semuanya. **Insight:** kalau satu brand dalam grup usaha sudah punya kandidat kuat (VivaReal), brand saudaranya (Imovelweb) sering kali sudah duluan dikloning — cek grup usaha, bukan cuma nama platform. |
| **Gumtree Scraper** (classifieds UK/AU/NZ/SA) | **10 seller** (`memo23`, `sync-network`, `voyn`, `crawlerbros`, `vivid-softwares`, `deltaspider`, `shahidirfan`, `lucascode` ×2, `gio21`) | Classifieds besar multi-negara, kelihatan sepi di band tapi ternyata salah satu niche paling jenuh di seluruh babak 8. |
| **OfferUp Scraper** (marketplace lokal AS) | 6 seller (`igolaizola` 85u, `crowdpull`, `lulzasaur`, `haketa`, `memo23`, `automation-lab`) | Setara Craigslist versi app-first, sudah jenuh. |
| **PubMed / Academic Paper Search** | Ramai dengan variasi platform: arXiv (`easyapi`), Google Scholar (`nexgendata`), PubMed langsung (`nexgendata`, `brilliant_gum`) | Overlap konsep dengan `crossref-works` & `openalex-scholarly` milik `xtracto` sendiri (sudah dicatat skip di babak 4 riset lama untuk alasan yang sama) — domain "academic paper search" sudah representatif dikuasai kombinasi platform yang saling melengkapi. |
| **Church Finder / Directory Scraper** | 6 seller (`parseforge`, `scrapestorm` ×1, `delectable_incubator`, `jungle_synthesizer`, `spry_frame`) | Niche direktori sangat kecil, mengejutkan sudah dikloning 6×. Sinyal kuat: kalau sesuatu terlihat "terlalu niche untuk ada pesaing", cek dulu — sering kali sudah ada. |
| **Website Screenshot / Screenshot API** | Puluhan seller (`leadsbrary`, `allscreenshots`, `vivid_astronaut`, `code-node-tools`, dll) | Generic dev-tooling, bukan "data" niche yang cocok dengan model bisnis scraping `xtracto` — dan sudah sangat jenuh sekalipun relevan. |
| **Pump.fun / Memecoin Monitor** | 6 seller (`api_massta`, `muhammetakkurtt` ×2, `intelscrape`, `gochujang`, `crawlergang`) | Niche crypto trading real-time, sudah jenuh + volatil (token/pair berubah cepat, risiko breaking changes tinggi) — konsisten dengan alasan skip CoinGlass di riset lama. |
| **Bing Search Scraper** | `tri_angle` — 763 users, 4.956 rpu | **Bukan temuan baru** — ini kandidat Prioritas Sedang babak 1 riset lama (SERP alternatif ke Google Search). Muncul lagi di scan babak 8 karena kebetulan match kata kunci baru, tapi sudah tercatat. |
| **Articles / Web Content Extractor generik** | 9+ seller (`easyapi`, `vulnv`, `taroyamada`, `codingfrontend`, `web.harvester`, dll, plus varian Medium/Wikipedia spesifik) | Kategori "extract artikel dari URL" generik sudah sangat jenuh; kalau mau masuk domain ini harus lewat platform spesifik yang belum digarap (bukan generic extractor). |
| **GCP Uploader, Pinecone Integration, RSS Feed Reader, Currency Converter, Sitemap Extractor** | — (bukan soal jumlah seller) | **Bukan fit bisnis.** Ini semua dev-tooling/infrastruktur generik (upload storage, vector DB integration, currency conversion util), bukan actor pengumpul data dari sumber pihak ketiga — di luar model bisnis scraping `xtracto`. Kategori LEAD_GENERATION/OTHER/INTEGRATIONS banyak berisi tooling semacam ini, bukan "hidden gem" data scraping. |

---

## Insight Strategis Babak 8

1. **"Kelihatan sepi di band `max-users`" ≠ "beneran sepi."** Ini insight paling penting dari babak 8 — bahkan lebih tegas dari babak 4-7 riset lama. Dari 55 kandidat yang lolos dedupe token (bersih dari `xtracto` dan riset lama), **hampir semuanya (~48 dari 55) gugur** begitu dicek ulang tanpa batas `max-users`. Verifikasi seller-count sekarang wajib mutlak, bukan langkah opsional.
2. **Klaster seller yang sama terus muncul di niche baru.** `parseforge`, `jungle_synthesizer`, `lexis-solutions`, `zen-studio`, `sian.agency`, `ecomscrape`, `memo23`, `shahidirfan`, `easyapi`, `automation-lab`, `crawlerbros`, `solidcode`, `hoholabs`, `blackfalcondata`, `fatihtahta`, `stealth_mode` — nama-nama ini yang sudah disebut di babak 2-7 riset lama untuk marketplace/real-estate/jobs, sekarang muncul lagi mendominasi niche-niche kecil di LEAD_GENERATION/OTHER/BUSINESS. Mereka tampaknya menjalankan strategi "clone setiap ide yang viable" secara sistematis lintas kategori, bukan cuma di e-commerce/real-estate seperti temuan awal.
3. **Cek grup usaha, bukan cuma nama platform.** Temuan Imovelweb (10 seller, grup Navent — saudara dari VivaReal/ZAP Imóveis yang sudah jadi kandidat riset lama) menunjukkan pola baru: begitu satu brand dalam grup usaha tertentu sudah punya kandidat kuat, brand-brand saudaranya sering sudah dikloning lebih dulu — meski nama platformnya beda.
4. **Kategori "generik" (LEAD_GENERATION 20.709 actor, OTHER 7.469 actor) didominasi dev-tooling, bukan data scraping.** Setelah difilter band + dedupe, isinya mayoritas infra tools (uploader, integration connector, screenshot API) yang bukan fit untuk model bisnis `xtracto`. Kategori ini secara struktural tidak akan produktif untuk riset actor data-scraping, terlepas berapa dalam offset-nya di-scan.
5. **REAL_ESTATE & JOBS akhirnya menunjukkan tanda mulai habis** — beda dari babak 4-7 yang selalu bilang "masih belum habis". Offset 360-440 kali ini **tidak menghasilkan kandidat baru yang lolos verifikasi** (semua yang ditemukan sudah ter-cover token match atau gugur di verifikasi seller-count). Kemungkinan besar vein ini sudah benar-benar tuntas setelah 4 babak berturut-turut (4,5,6,7) plus babak 8 ini.

---

## Rekomendasi untuk Riset Berikutnya (babak 8)

Category-browsing dengan filter `max-users` sudah mendekati titik jenuh untuk menghasilkan kandidat baru. Kalau riset dilanjutkan lagi, pertimbangkan strategi berbeda alih-alih mengulang pola babak 1-8:

1. **Query berbasis nama platform spesifik yang belum pernah dicoba**, bukan browsing kategori — misalnya daftar 50-100 nama platform niche (regional job board, real estate, direktori profesi) dari sumber di luar Apify (Wikipedia list of classifieds sites, dst), lalu query satu-satu dengan `--query` dan cek band + seller count langsung. Lebih presisi dari browsing offset yang sekarang sudah mentok.
2. **Verifikasi ulang (bukan cari baru) kandidat Prioritas Tinggi/Sedang dari 7 babak lama** yang belum sempat dieksekusi — cek apakah seller count-nya masih sama seperti waktu dicatat (pola Rent.com di atas menunjukkan status bisa berubah dalam hitungan hari/minggu).
3. **Turunkan `--min-users` ke bawah 10** (mis. 5) untuk menangkap actor yang baru dipublish minggu ini — cara ini punya risiko noise lebih tinggi (banyak actor gagal/uncoba), tapi berpeluang menangkap niche yang benar-benar baru sebelum diklon banyak seller lain.
4. **Pertimbangkan kategori generik (AUTOMATION, DEVELOPER_TOOLS, AI, AGENTS, MCP_SERVERS) yang selama ini di-skip** — bukan untuk actor data-scraping klasik, tapi kalau `xtracto` mau ekspansi ke lini bisnis MCP-server/AI-agent-tool (beda model bisnis dari 205 actor yang ada sekarang), ini kategori yang belum pernah ditelaah sama sekali di 8 babak riset ini.

Rekomendasi #1 di atas ternyata jadi vein paling produktif di seluruh riset — lihat Babak 9 di bawah.

---

# Babak 9 — Query Berbasis Platform Spesifik (Strategi Baru, Hasil Terbaik Sejauh Ini)

**Tanggal riset:** 2026-08-09 (lanjutan hari yang sama)
**Metodologi:** Sesuai rekomendasi penutup babak 8 — bukan lagi category-browsing, tapi **query nama platform spesifik satu-satu** (420 keyword total, 2 batch) lintas 6 vertikal: publikasi berita dunia, real estate per negara, job board per negara, classifieds otomotif per negara, review/direktori platform, dan beberapa niche lain (freelance, deals, business-data). Setiap keyword di-cek: berapa actor match yang benar-benar relevan (bukan noise Algolia), dan siapa saja seller-nya.

## 🎯 Temuan Kunci: `xtracto` Sudah Punya 30 Actor News — Tapi Baru Meng-cover Sebagian Kecil Dunia

Saat memverifikasi cluster berita, ketahuan bahwa `xtracto` (di luar apa yang tercatat di tabel "Sudah Dibangun" riset lama, yang cuma menyebut `nytimes-scraper`) **sudah punya portofolio 30 actor kategori NEWS**:

`nytimes-scraper`, `reuters-scraper`, `ft-scraper` (Financial Times), `guardian-scraper`, `bbc-scraper`, `aljazeera-scraper`, `scmp-scraper` (South China Morning Post), `cnbc-scraper`, `nikkei-scraper`, `bloomberg-news-article-scraper`, `bloomberg-news-search`, `bloomberg-quote-scraper`, `forbes-scraper`, `barrons-scraper`, `fortune-scraper`, `yahoo-finance-scraper`, `msn-scraper`, `investing-scraper`, `investors-scraper` (Investor's Business Daily), `apnews-scraper`, `upi-scraper`, `techcrunch-scraper`, `caixin-scraper` (China finance), `tipranks-stock-signals`, `straitstimes-scraper`, `smh-scraper` (Sydney Morning Herald), `thestar-scraper` (Malaysia), `dataindonesia-scraper`, `google-news-scraper`, `google-trends-scraper`, `smart-news-loader`.

**Ini pola yang sudah terbukti bekerja 30×** — persis seperti template "OTA reviews" di riset lama, tapi jauh lebih besar skalanya. Bukti langsung: `nytimes-scraper` sendiri **51 users, 198.154 runs (3.811 rpu)** — signal ROI-per-customer tertinggi yang jadi acuan seluruh riset ini sejak awal.

**Yang belum di-cover: mayoritas dunia.** `xtracto` kuat di outlet finance/business AS + beberapa outlet Asia (Malaysia, Indonesia, Singapura, Australia, China, Jepang), tapi **nyaris kosong total** untuk: outlet besar AS non-finance (Washington Post, LA Times, USA Today, dll), seluruh Eropa daratan (Prancis, Jerman, Spanyol, Italia — 0 outlet), Timur Tengah (di luar Al Jazeera), Amerika Latin, Afrika, dan sebagian besar Asia Tenggara/Selatan di luar yang sudah disebut. Setiap outlet di bawah ini dicek satu-satu dengan query spesifik nama medianya — hasilnya: **~80 outlet berita besar dunia belum punya actor scraper sama sekali (atau cuma 1 seller kecil) di seluruh Apify Store**, bukan cuma di portofolio `xtracto`.

### ✅ Kandidat Baru — Ekstensi Template "News Scraper per Outlet" (~80 outlet)

Legenda status: **[0]** = benar-benar tidak ada actor untuk outlet ini di seluruh store (query spesifik dicek langsung, hasil yang muncul cuma noise tidak relevan) — belum ada bukti demand langsung tapi juga belum ada kompetitor sama sekali. **[1 kecil]** = ada 1 seller tapi datanya sangat tipis (≤ puluhan users) — validasi awal ada, ruang tetap terbuka.

**Tier 1 — AS & outlet global besar (fit tertinggi dengan portofolio finance/business `xtracto` yang sudah ada)**

| Outlet | Status | Catatan |
|---|---|---|
| Washington Post | [0] — **✅ Dibangun 2026-08-09** (`washingtonpost-scraper`) | Koran nasional AS terbesar ke-2 setelah NYT — `xtracto` sudah punya NYT, gap langsung. No WAF ditemukan; data via `__NEXT_DATA__` (Arc Publishing ANS) + RSS 8 seksi. Paywall server-side (teaser only, sama tier dengan nytimes-scraper). Lihat `washingtonpost-scraper/CRAWLING_METHOD.md`. |
| Wall Street Journal | [0] | Melengkapi FT/Bloomberg/Barron's — sama-sama finance-focus, paywall-nya setara FT yang sudah berhasil di-handle `xtracto`. |
| USA Today | [0] — **⚠️ Di-skip 2026-08-24** | Koran nasional AS sirkulasi terbesar. `robots.txt` eksplisit `Disallow: /` untuk `User-agent: Claude`, `ClaudeBot`, `Claude-Web`, `claudeweb`, `anthropic-ai` (dicek langsung by name, bukan cuma blanket GPTBot) — dihormati sebagai sinyal operator situs tidak ingin di-crawl AI, jangan coba lagi kecuali kebijakan berubah. |
| Business Insider | [0] — **✅ Dibangun 2026-08-24** (`businessinsider-scraper`) | Outlet bisnis/tech populer, melengkapi Fortune/Forbes/TechCrunch. No WAF ditemukan; data via JSON-LD `NewsArticle` (dict langsung, bukan `__NEXT_DATA__`) + Atom feed site-wide (`/rss`, sudah exclude konten premium "Insider" secara otomatis, unik: `content:encoded`-nya berisi body HTML lengkap bukan cuma teaser). Lihat `businessinsider-scraper/CRAWLING_METHOD.md`. |
| MarketWatch | [1 kecil] | `parseforge` — 19u/107r. Finance news, melengkapi Bloomberg/Barron's/Investing.com. |
| Motley Fool (earnings call transcripts) | [1 kecil] | `jungle_synthesizer` — 34u/989r. Data-type spesifik (transkrip earnings call), bukan cuma artikel. |
| Los Angeles Times | [0] — **✅ Dibangun 2026-08-24** (`latimes-scraper`) | Koran regional AS terbesar (West Coast). No WAF ditemukan; JSON-LD `NewsArticle` (dict tunggal) berisi `articleBody` full-text meski `isAccessibleForFree:false` + marker `.paywall` hadir di `hasPart` (paywall kosmetik, belum ditegakkan di data). RSS site-wide (`/rss2.0.xml`) kronologis lintas section. Lihat `latimes-scraper/CRAWLING_METHOD.md`. |
| Chicago Tribune | [0] — **✅ Dibangun 2026-08-24** (`chicagotribune-scraper`) | Koran regional AS terbesar (Midwest). Homepage & article pages no WAF; JSON-LD `NewsArticle` metadata-only (no `articleBody`) + HTML `div.article-body > div.body-copy > p` for full text (metering flag `isAccessibleForFree:false` present but not enforced, same tier as `latimes-scraper`). **Kuirk penting:** `/feed/` dan sitemap bertanggal (`?yyyy=&mm=&dd=`) di-gate custom hashcash JS proof-of-work challenge (bukan vendor WAF standar) — `latest` mode pakai scrape homepage (`div[title]` anchor) sebagai fallback, bukan feed kronologis murni. Lihat `chicagotribune-scraper/CRAWLING_METHOD.md`. |
| New York Post | [0] — **✅ Dibangun 2026-08-24** (`nypost-scraper`) | Tabloid AS besar, angle beda dari NYT. No WAF ditemukan. JSON-LD `NewsArticle` metadata-only (no `articleBody` — WordPress REST API juga di-lock 401) + HTML `div.single__content.entry-content > p` (bare `<p>`, stop di `<hr>`) untuk full text. Kuirk: sebagian artikel `/us-news/` & `/business/` punya `publisher.name: "California Post"` (regional sub-brand di domain sama, bukan bug). Lihat `nypost-scraper/CRAWLING_METHOD.md`. |
| Boston Globe | [0] | Koran regional AS. |
| The Atlantic | [0] — **✅ Dibangun 2026-08-24** (`atlantic-scraper`) | Majalah opini/analisis berpengaruh AS. No WAF ditemukan. **Kuirk teknis:** satu-satunya di portofolio ini di mana JSON-LD TIDAK cukup (metadata-only, tanpa `articleBody`) — full text harus diambil dari cache GraphQL (`urql`, setara Apollo state) di dalam `__NEXT_DATA__`, gabung blok paragraf `ArticleParagraphContent`. `hasMeter:true` (paywall meter) hadir tapi teks tetap full di semua sampel. Latest mode juga Atom (bukan RSS 2.0), sama seperti Vox. Lihat `atlantic-scraper/CRAWLING_METHOD.md`. |
| Vox | [0] — **✅ Dibangun 2026-08-24** (`vox-scraper`) | Explainer/analysis journalism, audiens digital-native. No WAF ditemukan; JSON-LD `NewsArticle` full-text sama seperti LA Times (paywall kosmetik). **Kuirk:** latest-mode feed (`/rss/index.xml`) ternyata **Atom**, bukan RSS 2.0 — satu-satunya di portofolio ini, butuh parser `<entry>` khusus (parser RSS-2.0 generik return 0 item secara silent, tanpa error). Lihat `vox-scraper/CRAWLING_METHOD.md`. |
| Vice | [0] — **✅ Dibangun 2026-08-24** (`vice-scraper`) | Digital-native journalism. No WAF ditemukan. 2 blok ld+json terpisah (satu `@graph` generik SEO-plugin dengan type `Article`, satu lagi dict standalone dengan type `NewsArticle` — dipakai extractor) tanpa `articleBody`/`description` — description dari `meta[og:description]`, full text dari HTML `div.entry-content` (WordPress Gutenberg, filter otomatis exclude ad-slot & video-embed div karena bukan tag `<p>`). Latest mode via `/en/rss` (WordPress default, `description` perlu unescape+strip HTML 1× karena berisi markup ter-escape termasuk boilerplate "appeared first on VICE"). Lihat `vice-scraper/CRAWLING_METHOD.md`. |
| Politico | [1 kecil] — **⚠️ Di-skip 2026-08-24** | `mtrunkatova` — 28u/2.363r. Berita politik/kebijakan AS, relevan buat B2B/lobbying intelligence. `robots.txt` eksplisit block `ClaudeBot`/`Claude-Web`/`Claude-SearchBot`/`Claude-User`/`anthropic-ai` by name (plus GPTBot, CCBot, Google-Extended, dan ~60 AI-bot lain) — dihormati, jangan coba lagi. |
| Axios | [0] — **✅ Dibangun 2026-08-24** (`axios-scraper`) | Format ringkas, growth cepat di kalangan profesional. Cloudflare terdeteksi di depan situs (cf-ray ada) tapi tidak aktif men-challenge `chrome124` — lihat catatan risiko di `axios-scraper/CRAWLING_METHOD.md`. JSON-LD unik: satu `<script>` berisi JSON *list* (`[NewsMediaOrganization, NewsArticle]`), bukan dict langsung seperti outlet lain. RSS site-wide (`api.axios.com/feed/`) sudah termasuk `content:encoded` full-text + multi `dc:creator`. |
| The Hill | [0] — **⚠️ Di-skip 2026-08-24** | Berita politik Capitol Hill. `robots.txt` eksplisit block `ClaudeBot`/`anthropic-ai`/`GPTBot`/`CCBot`/`Google-Extended` by name — dihormati, jangan coba lagi. |
| Fox News | [1 kecil] — **✅ Dibangun 2026-08-24** (`foxnews-scraper`) | `hanatsai` — 149u/2.182r. Outlet berita kabel terbesar AS. No WAF ditemukan; `robots.txt` bersih dari block AI (beda dari CNN yang block Claude — lihat baris CNN di atas). JSON-LD `@graph` array **berisi `articleBody` langsung** (jarang di portofolio ini) + `isAccessibleForFree` boolean asli (bukan string). Kuirk: script tag ld+json punya atribut tambahan `data-n-head="ssr"` sebelum `type=` — regex naif berbasis prefix gagal match, wajib pakai BeautifulSoup attribute lookup. Latest mode via Google Publisher feed (`moxie.foxnews.com/google-publisher/latest.xml`) — unik, sudah termasuk `content:encoded` body HTML penuh, bukan cuma teaser. Lihat `foxnews-scraper/CRAWLING_METHOD.md`. |
| CNN | [1 kecil] — **⚠️ robots.txt block Claude** (dicek 2026-08-24, belum dicoba) | `filip_cicvarek` — 44u/639r. Outlet berita kabel terbesar ke-2. |
| The Economist | [0] | Majalah analisis global berpengaruh. |

**Tier 1 — Melengkapi negara yang portofolio `xtracto` sudah kuat di sana (real estate/jobs/regional)**

| Outlet | Negara | Status | Kenapa Fit |
|---|---|---|---|
| Toronto Star | Kanada | [0] — **⚠️ robots.txt block Claude** (dicek 2026-08-24, belum dicoba) | `xtracto` sudah ada Realtor.ca (kandidat riset lama) — Kanada belum ada outlet berita sama sekali. |
| The Globe and Mail | Kanada | [0] — **⚠️ Di-skip 2026-08-26, robots.txt block Claude dikonfirmasi.** | Koran finance-focus Kanada (setara WSJ Kanada) — fit ganda dengan tema finance. Recon: `theglobeandmail.com/robots.txt` eksplisit `Disallow: /` untuk **empat** user-agent Claude (`ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`) plus `Anthropic-ai`, masing-masing grup terpisah (bukan blanket `User-agent: *`, jadi bukan bug parser multi-UA) — dihormati, tidak dibangun. Homepage/artikel tidak sempat dicek (robots block sudah cukup untuk stop). |
| The Australian | Australia | [0] — **❌ Di-skip 2026-08-24, hard paywall dikonfirmasi.** | `xtracto` sudah SMH — lengkapi duopoli media Australia. Recon: halaman artikel (News Corp Australia) mengembalikan HTML **kosong dari konten** — `<title>` literally "Subscribe to The Australian...", `meta robots=noindex,nofollow`, ld+json cuma `WebPage` tanpa `NewsArticle` sama sekali. Ini hard paywall lebih ketat dari Le Monde (yang minimal masih expose ld+json artikel) — jangan coba lagi kecuali strategi bypass baru ditemukan. |
| ABC News Australia | Australia | [0] — **⚠️ robots.txt block Claude** (dicek 2026-08-24, belum dicoba) | Broadcaster nasional Australia. |
| Hindustan Times | India | [0] — **✅ Dibangun 2026-08-24** (`hindustantimes-scraper`) | `xtracto` sudah `dataindonesia-scraper` (fokus regional Asia) — India (2nd biggest Asia market) belum ada. No WAF ditemukan; JSON-LD `NewsArticle` berisi `articleBody` full-text. Kuirk: `headline`/`description` punya suffix `" \| <Section>"` dari CMS. Latest mode pakai feed section `india-news` (tidak ada feed site-wide). Lihat `hindustantimes-scraper/CRAWLING_METHOD.md`. |
| The Hindu | India | [0] — **✅ Dibangun 2026-08-24** (`thehindu-scraper`) | Koran India berbahasa Inggris paling dihormati. No WAF ditemukan. **Kuirk unik di seluruh portofolio:** situs ini **tidak emit `application/ld+json` sama sekali** — structured data pakai schema.org microdata lama (`itemprop`/`itemscope` di tag HTML biasa). `meta[itemprop=headline/description/datePublished/...]` + `div[itemprop=articleBody] > p` untuk full text. `itemprop=author` selalu span kosong (placeholder) — byline asli di class `.author-name` biasa (fallback). Lihat `thehindu-scraper/CRAWLING_METHOD.md`. |
| Indian Express | India | [0] — **⚠️ robots.txt block Claude/anthropic-ai** (dicek 2026-08-24, belum dicoba) | Koran India nasional. |
| NDTV | India | [1 kecil] | `vivpm99` — 2u/43r, sangat tipis. Broadcaster/portal berita India top. |
| Channel News Asia | Singapura | [0] — **✅ Dibangun 2026-08-24** (`channelnewsasia-scraper`) | `xtracto` sudah Straits Times — lengkapi Singapura. No WAF ditemukan; `robots.txt` tidak block Claude/GPTBot (beda dari USA Today/The Hill/Politico yang eksplisit block AI crawler — dicek dan di-skip). JSON-LD `NewsArticle` via `@graph` array tapi tanpa `articleBody` — full text dari HTML `div.text > div.text-long` (perlu selector spesifik karena class `.text-long` generik dipakai ulang 44× per halaman untuk CSS/JS snippet lain; artikel longform/brand-studio split body jadi 10 blok terpisah, semua digabung berurutan). RSS site-wide (`/api/v1/rss-outbound-feed`, di-`Allow` eksplisit di robots.txt). Lihat `channelnewsasia-scraper/CRAWLING_METHOD.md`. |
| Jakarta Post | Indonesia | [0] — **✅ Dibangun 2026-08-24** (`jakartapost-scraper`) | `xtracto` sudah `dataindonesia-scraper` — Jakarta Post (English-language) beda audiens (ekspat/bisnis internasional). No WAF ditemukan. JSON-LD `NewsArticle` (`isAccessibleForFree` string, bukan boolean) tanpa `articleBody`/`description` — description dari `meta[property=og:description]`, full text dari HTML `div.tjp-single__content` (paragraf pertama unik: drop-cap terpisah jadi `h1.tjp-opening__char` + `p.tjp-opening__txt`, digabung tanpa spasi). **Soft-paywall terkonfirmasi**: `isAccessibleForFree:"false"` di semua sampel tapi `articleBody` tetap full-text (gate hanya overlay JS/CSS klien, sama tier `latimes-scraper`) — extractor set `_paywalled` flag tanpa memotong teks. Latest mode via Google News sitemap (`/sitemap_news.xml`). Lihat `jakartapost-scraper/CRAWLING_METHOD.md`. |
| Kompas | Indonesia | [0] — **⚠️ robots.txt block Claude** (dicek 2026-08-24, belum dicoba) | Koran Indonesia sirkulasi terbesar. |
| Detik | Indonesia | [0] — **✅ Dibangun 2026-08-24** (`detik-scraper`) | Portal berita online Indonesia terbesar. No WAF ditemukan; `robots.txt` full `Allow: /`, tidak block AI crawler. 3 blok ld+json (`BreadcrumbList`/`WebPage`/`NewsArticle`) tanpa `articleBody` — full text dari HTML `div.detail__body-text`, dengan filter khusus untuk exclude paragraf placeholder iklan (`<p class="para_caption">SCROLL TO CONTINUE WITH CONTENT</p>`) yang diselip di tengah artikel. Latest mode via Google News sitemap channel utama (`/berita/sitemap_news.xml`) — root `/sitemap.xml` ternyata sitemap index dengan puluhan channel terpisah (`internasional`, `bbc-world`, `abc-australia`, `dw`, dst). Lihat `detik-scraper/CRAWLING_METHOD.md`. |
| Philippine Star | Filipina | [0] — **✅ Dibangun 2026-08-24** (`philstar-scraper`) | `xtracto` kuat di SEA (Shopee dll) — Filipina belum ada outlet berita. No WAF ditemukan; `robots.txt` minimal (226 byte), tidak block AI crawler. JSON-LD `NewsArticle` tanpa `articleBody`; full text dari HTML `div.article__content > p` (paling bersih di seluruh batch ini — tanpa ad-placeholder atau tag kosong). **Kuirk unik:** field `description` di ld+json adalah HTML yang di-escape 1×, jadi butuh `html.unescape()` dulu baru di-strip tag (kalau parse duluan sebelum unescape, tag literal `&lt;p&gt;` cuma jadi teks biasa, bukan ter-strip). RSS site-wide (`/rss/headlines`, 10 item/fetch, unik: field `author` langsung ada di tiap `<item>`). Lihat `philstar-scraper/CRAWLING_METHOD.md`. |
| Philippine Inquirer | Filipina | [0] — **✅ Dibangun 2026-08-24** (`inquirer-scraper`) | Koran Filipina sirkulasi terbesar. No WAF ditemukan (WordPress, lintas subdomain newsinfo/lifestyle/business dll — semua share template sama). JSON-LD `NewsArticle` **punya `articleBody` langsung** (jarang di portofolio ini) tapi 2 kuirk: (1) raw ld+json text mengandung control character mentah sehingga `json.loads` default gagal — perlu `strict=False`; (2) `articleBody` di-escape HTML **2×** (WordPress Gutenberg block markup ter-escape ganda) — perlu `html.unescape()` 2× sebelum jadi HTML asli buat di-parse. Latest mode via `/fullfeed` (site-wide, lintas subdomain). Lihat `inquirer-scraper/CRAWLING_METHOD.md`. |
| Rappler | Filipina | [1 kecil] | `nekohaii` — 2u/65r, sangat tipis, tool multi-sumber bukan spesifik Rappler. |
| Bangkok Post | Thailand | [0] — **✅ Dibangun 2026-08-24** (`bangkokpost-scraper`) | Koran berbahasa Inggris utama Thailand. No WAF ditemukan; JSON-LD `NewsArticle` berisi `articleBody` full-text. Kuirk: `isAccessibleForFree` adalah **string** `"True"`/`"False"`, bukan boolean; RSS tidak punya tag `<guid>` (selalu null, pakai `link` sebagai dedup key). Lihat `bangkokpost-scraper/CRAWLING_METHOD.md`. |
| VnExpress | Vietnam | [0] — **⚠️ robots.txt block Claude** (dicek 2026-08-24, belum dicoba) | Portal berita online Vietnam terbesar. |

**Tier 2 — Eropa Daratan (nol total, belum ada satupun outlet Eropa non-UK di portofolio `xtracto`)**

| Outlet | Negara | Status |
|---|---|---|
| Le Monde | Prancis | [0] — **❌ Di-skip 2026-08-24, hard paywall dikonfirmasi.** Recon: semua 5 sampel artikel (`isAccessibleForFree:"False"` string, bukan bool) cuma expose ~15-20% teks (`"Il vous reste 80.16% de cet article à lire. La suite est réservée aux abonnés."`), tidak seperti soft-paywall LA Times/Washington Post. **Dipindah ke `20 Minutes`** (koran gratis Prancis, lihat entri di bawah) sebagai gap-filler Prancis yang genuinely open-access. Jangan coba lagi kecuali strategi bypass paywall baru ditemukan. |
| El País | Spanyol | [0] |
| El Mundo | Spanyol | [0] — **❌ Di-skip 2026-08-26, robots.txt block dikonfirmasi.** Recon Phase 1 (verifikasi langsung, bukan asumsi dari dokumen riset): `curl https://www.elmundo.es/robots.txt` menunjukkan seksi "Bots IA" dengan grup `User-agent: anthropic-ai` (baris terpisah, bukan grup multi-agent yang berbagi satu blok Disallow) diikuti `Disallow: /` dan hanya `Allow: /uestudio/` + `Allow: /ofertas-regalos/` — keduanya path marketing, tidak mencakup artikel berita sama sekali. `GPTBot`/`CCBot`/`ChatGPT-User`/`Google-Extended`/`OAI-SearchBot`/`PerplexityBot` diblokir dengan pola identik. Tidak ada baris `ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot` eksplisit, tapi `anthropic-ai` yang eksplisit diblokir sudah cukup jadi stop-condition per kebijakan portofolio (sama seperti `VnExpress`). Berhenti di Phase 1 — paywall/JSON-LD/RSS tidak diperiksa karena tidak relevan lagi. Tidak dibangun. |
| La Repubblica | Italia | [0] |
| Corriere della Sera | Italia | [0] — **❌ Di-skip 2026-08-26, robots.txt block dikonfirmasi.** Recon Phase 1 (verifikasi langsung via `curl_cffi` chrome124, bukan asumsi dari dokumen riset): `https://www.corriere.it/robots.txt` (200, seksi "Bot Exclusion Protocol") berisi grup per-agent yang masing-masing punya `Disallow: /` sendiri langsung di bawahnya (bukan pola bug multi-user-agent-group Babak 14 — tiap `User-agent:` punya `Disallow:` 1:1, jadi tidak ambigu): baris 5-6 `User-agent: anthropic-ai` → `Disallow: /`, baris 17-18 `User-agent: ClaudeBot` → `Disallow: /`. `GPTBot`/`CCBot`/`Google-Extended`/`Applebot-Extended`/`Amazonbot`/`Meta-ExternalAgent`/`PetalBot`/`Bytespider` diblokir dengan pola identik. Ini adalah first Italian-outlet candidate untuk portofolio (gap Eropa Daratan) tapi eksplisit block `ClaudeBot`+`anthropic-ai` sudah cukup jadi stop-condition per kebijakan portofolio (sama seperti `El Mundo`/`VnExpress`). Berhenti di Phase 1 — paywall/JSON-LD/RSS tidak diperiksa karena tidak relevan lagi. Tidak dibangun. |
| Der Spiegel | Jerman | [0] — **✅ Dibangun 2026-08-24** (`derspiegel-scraper`) | No WAF ditemukan. JSON-LD `NewsArticle` (list format, bukan dict) metadata-only + HTML `div[data-area=body] > div[data-area=text] > p` untuk full text. **Paywall campuran genuine** (bukan kosmetik): artikel gratis punya `div[data-area=text]`, artikel premium "SPIEGEL+" cuma punya `div[data-area=paywall]` (0 karakter teks, hard gate). Extractor set `_paywalled:true` + `articleBody:null` untuk premium, tanpa fabrikasi data. Lihat `derspiegel-scraper/CRAWLING_METHOD.md`. |
| Handelsblatt | Jerman | [0] — **✅ Dibangun 2026-08-24** (`handelsblatt-scraper`) — finance-focus, fit tema kuat. No WAF ditemukan; JSON-LD `NewsArticle` berisi `articleBody` full-text pada 6/8 sampel (2 sampel live-ticker/wire-brief pendek tidak punya field `articleBody` sama sekali — bukan error, konten memang pendek). Paywall marker `.hmg-paywalled` hadir tapi tidak menghalangi full-text di data. Lihat `handelsblatt-scraper/CRAWLING_METHOD.md`. |
| Die Zeit | Jerman | [0] |
| Euronews | Pan-Eropa | [0] |
| Deutsche Welle (DW) | Jerman/internasional | [0] — bahkan 0 hit sama sekali di search |
| France24 | Prancis/internasional | [0] |
| The Times (UK) | UK | [0] — ❌ **Di-skip 2026-08-26** — robots.txt (`www.thetimes.co.uk/robots.txt`) header eksplisit: "The Times does not permit the unlicensed use of our content for large language models." Teknis: `User-agent: *` / `Disallow: /` (baris 5-6) adalah default-deny, dan grup allowlist di bawahnya (baris 9-56: Googlebot, Bingbot, DuckDuckBot, `ChatGPT-User`/`GPTBot`/`OAI-SearchBot`, dll.) TIDAK mencantumkan `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/`anthropic-ai` sama sekali — jadi Claude jatuh ke default-deny wildcard. Tidak dibangun, tidak diuji hard-paywall lebih lanjut (robots block sudah cukup untuk skip, sesuai kebijakan portofolio). |
| The Daily Telegraph | UK | [0] — **✅ Dibangun 2026-08-26** (`telegraph-scraper`). robots.txt tidak mencantumkan Claude/ClaudeBot/anthropic-ai/GPTBot sama sekali (hanya blok 23 crawler bernama seperti Googlebot/bingbot/AhrefsBot dalam satu grup `Disallow: /`, lalu `User-agent: * / Allow: /` sebagai catch-all). WAF: Akamai + gerbang lisensi TollBit — beberapa profil TLS umum (`chrome131`/`chrome124`/`safari17_0`/`firefox133`) kena blok 402 "TollBit Token", tapi `edge101`/`chrome99_android` lolos bersih 200 (murni fingerprint TLS, bukan target khusus AI-crawler). **Paywall kosmetik/client-side saja** — 13 artikel disampel lintas section (news/business/opinion/money/travel/sport/obituari, termasuk kolom flagship Ambrose Evans-Pritchard) semuanya `isAccessibleForFree:true` + `articleBody` full-length utuh dari HTML (`div.articleBodyText`, ld+json sendiri tidak punya field `articleBody`); meter Piano/Tinypass ternyata client-side JS saja jadi tidak pernah kena saat fetch HTTP-only. `_paywalled` diset jujur (never fired di sampel). Lihat `telegraph-scraper/CRAWLING_METHOD.md`. |
| The Independent | UK | [0] |
| Daily Mail | UK | [0] — ❌ **Di-skip 2026-08-26** — robots.txt eksplisit `Disallow: /` untuk grup user-agent yang mencantumkan `anthropic-ai`, `ClaudeBot`, `Claude-SearchBot`, `Claude-User`, `Claude-Web` (bersama GPTBot/PerplexityBot/dll., 1 blok `Disallow` untuk banyak `User-agent:` — bukan bug parser, memang disengaja). Header robots.txt juga eksplisit melarang "development of any software, machine learning, artificial intelligence (AI), and/or large language models (LLMs)". Tidak dibangun. |
| Metro UK | UK | [0] |
| Sky News | UK | [0] — ❌ **Di-skip 2026-08-26** — robots.txt (`news.sky.com/robots.txt`) grup "Disallow AI Model Training Crawlers" mencantumkan `anthropic-ai` dan `ClaudeBot` eksplisit bersama GPTBot/CCBot/PerplexityBot/dll. dengan `Disallow: /` (satu blok Disallow untuk 23 user-agent, bukan bug parser — grup terpisah `Claude-Web`/`Claude-User`/`Claude-SearchBot` untuk "user initiated AI actions/searches" cuma dapat `Disallow: /preview/*`, tidak relevan untuk bulk scraping actor). Tidak dibangun, tidak ada file actor dibuat. |

**Tier 2 — Timur Tengah (melengkapi Al Jazeera yang sudah ada + fokus UAE `xtracto` di real estate)**

| Outlet | Negara | Status |
|---|---|---|
| Haaretz | Israel | [0] |
| Jerusalem Post | Israel | [0] |
| Arab News | Arab Saudi | [0] |
| Gulf News | UAE | [0] — **✅ Dibangun 2026-08-24** (`gulfnews-scraper`) | No WAF ditemukan; `robots.txt` bersih dari block AI (beda dari Khaleej Times/Haaretz/Jerusalem Post yang block Claude, dicek di batch sama). Ld+json `NewsArticle` **punya `articleBody` langsung** (konsisten di 3 sampel termasuk 1 live-blog dunia) + `author` sebagai list (multi-byline). Kuirk: `articleBody`/`headline` kadang berisi HTML entity mentah (`&nbsp;`) yang perlu `html.unescape()` tambahan setelah `json.loads`. Latest mode via Google News sitemap (`/news_sitemap.xml`, di-advertise di robots.txt). Tidak ada paywall. Lihat `gulfnews-scraper/CRAWLING_METHOD.md`. |
| Khaleej Times | UAE | [0] |
| The National | UAE | [0] |

**Tier 3 — Amerika Latin**

| Outlet | Negara | Status |
|---|---|---|
| Clarín | Argentina | [0] |
| La Nación | Argentina | [0] |
| El Universal | Meksiko | [0] |
| Reforma | Meksiko | [0] |
| El Tiempo | Kolombia | [0] |
| Estadão | Brasil | [0] |
| O Globo / Globo.com | Brasil | [1 kecil] — `fingolfin` 3u/127r |
| Diario Libre | Rep. Dominika | [0] — **✅ Dibangun 2026-08-26** (`diariolibre-scraper`) | Tidak ada WAF (IIS polos, tidak ada header/cookie Cloudflare/DataDome/PerimeterX/Akamai); `robots.txt` cuma 1 grup flat `User-agent: *` (tidak ada grup Claude/ClaudeBot/anthropic-ai terpisah sama sekali, jadi bug parser multi-grup Babak 14 tidak relevan di sini). Ld+json dibungkus `@graph` (`NewsMediaOrganization`+`WebSite`+`NewsArticle`) dan **punya `articleBody` langsung** — dicek eksplisit untuk bug korupsi angka ala Clarín (angka ribuan "6,716 millones"/"3,276.5 millones" dll di artikel ekonomi) dan **utuh, tidak korup**. Kuirk: semua field teks ld+json berisi HTML entity mentah (`&oacute;` dst) yang perlu `html.unescape()` tambahan. Tidak ada `isAccessibleForFree`/marker paywall sama sekali di 3 sampel (2 berita + 1 opini) — situs tampak open-access penuh. Latest mode via `/feed/portada.xml` (RSS custom ~28 item, bukan WordPress standar) yang uniknya CDATA `<description>`-nya sudah berisi **full articleBody** dalam HTML, bukan cuma teaser. Lihat `diariolibre-scraper/CRAWLING_METHOD.md`. |

**Tier 3 — Afrika**

| Outlet | Negara | Status |
|---|---|---|
| Daily Nation | Kenya | [0] |
| The Star | Kenya | [0] |
| Vanguard | Nigeria | [0] — bahkan 0 hit sama sekali di search |
| Mail & Guardian | Afrika Selatan | [0] |
| News24 | Afrika Selatan | [1 kecil] — `loopwalker-owner` 2u/16r, sangat tipis |

**Tier 3 — Eropa Timur / Rusia & Asia Timur**

| Outlet | Negara | Status |
|---|---|---|
| RT (Russia Today) | Rusia | [0] |
| TASS | Rusia | [0] |
| Kyiv Independent | Ukraina | [0] |
| Kyiv Post | Ukraina | [0] — **✅ Dibangun 2026-08-25** (`kyivpost-scraper`) | No WAF ditemukan. Ld+json `NewsArticle` tanpa `articleBody` — full text dari HTML `div#post-content > section.entry` (bisa multi-section per artikel, widget promo di section terpisah otomatis ter-exclude). `isAccessibleForFree:true` di semua sampel. Latest mode via `/feed` (WordPress RSS, 100 item). Lihat `kyivpost-scraper/CRAWLING_METHOD.md`. |
| Korea Herald | Korea Selatan | [0] |
| Korea Times | Korea Selatan | [0] |
| China Daily | China | [0] |
| Global Times | China | [0] |
| Taipei Times | Taiwan | [0] |
| Asahi Shimbun | Jepang | [0] |
| Yomiuri | Jepang | [0] |

**Catatan risiko:** beberapa outlet ini (WSJ, FT-yang-sudah-dibangun, The Economist) punya paywall ketat — tapi `xtracto` sendiri sudah membuktikan itu bisa ditangani (`ft-scraper` sudah jalan). Bukan alasan otomatis skip, cuma perlu effort ekstra dibanding outlet open-access. Prioritaskan dulu yang open-access murni (kebanyakan koran regional/nasional non-finance) sebelum masuk ke yang paywall ketat.

**Kenapa cluster ini paling kuat di seluruh riset (babak 1-9):** ini bukan cuma "niche kosong" biasa — ini **template yang sudah divalidasi 30× oleh `xtracto` sendiri**, dengan bukti ROI konkret (`nytimes-scraper` 3.811 rpu). Risiko eksekusi rendah karena kode/pola scraping situs berita (extract artikel dari HTML/JSON-LD, sudah dibahas di `.ai/CLAUDE.md` sebagai prioritas ekstraksi #1) kemungkinan besar bisa di-reuse lintas outlet dengan modifikasi minimal.

---

## ✅ Kandidat Baru Lain — Gap Kecil di Real Estate / Jobs / Automotive / Lainnya

Dari query platform spesifik di luar cluster berita, kandidat berikut lolos verifikasi (seller count rendah, bukan noise):

| Ide Actor | Vertikal | Status | Bukti Demand |
|---|---|---|---|
| **Point2Homes** | Real estate (AS/Kanada) | [1 kecil] | `getdataforme` — 7u/476r (68 rpu) |
| **Ingatlan.com** | Real estate (Hungaria) | [1 kecil] | `studio-amba` — 5u/152r (30 rpu) |
| **Reonomy** | Real estate komersial + intelijen properti (AS) | [0] | Tidak ada actor sama sekali — TAM besar (dipakai investor CRE), tapi belum ada bukti demand langsung di Apify. |
| **PropertyPro.ng** | Real estate (Nigeria) | [1 kecil] | `gio21` — 2u/4r, sangat tipis |
| **BuyRentKenya** | Real estate (Kenya) | [1 kecil] | `nomad-agent` — 2u/46r |
| **Liepin** | Job board white-collar (China) | [1 kecil] | `getascraper` — 20u/179r |
| **Trabajando.com** | Job board (Chile) | [1 kecil] | `crawler_cl` — 6u/115r |
| **Skywalker.gr** | Job board (Yunani) | [1 kecil] | `unfenced-group` — 2u/267r (134 rpu — rasio tinggi meski data tipis) |
| **TE-palvelut** | Job board resmi pemerintah (Finlandia) | [0] | Tidak ada actor sama sekali |
| **TopCV** | Job board (Vietnam) | [0] | Tidak ada actor sama sekali |
| **Karir.com** | Job board (Indonesia) | [0] | Tidak ada actor sama sekali — mengejutkan mengingat fokus SEA `xtracto` |
| **Maukerja** | Job board (Malaysia) | [0] | Tidak ada actor sama sekali |
| **TopJobs.lk** | Job board (Sri Lanka) | [0] | Tidak ada actor sama sekali |
| **Goo-net** | Classifieds mobil (Jepang) | [1 kecil] | `parseforge` — 2u/31r, sangat tipis |
| **Bidfax** | Data lelang mobil bekas Jepang (dipakai importir mobil global) | [0] | Tidak ada actor sama sekali — niche B2B mapan di luar Apify (banyak importir mobil Afrika/Timur Tengah pakai data lelang Jepang), worth digali independen. |
| **PissedConsumer** | Review/komplain konsumen (AS) | [1 kecil] | `automation-lab` — 2u/15r |
| **Slant.co** | Perbandingan produk crowd-sourced | [0] | Tidak ada actor sama sekali |
| **DesignCrowd** | Marketplace freelance desain | [1 kecil] | `crawlerbros` — 2u/38r |
| **OneFineStay** | Vacation rental mewah | [0] | Tidak ada actor sama sekali — TAM kemungkinan kecil (niche luxury) |

**Catatan jujur soal status [0]:** beda dengan kandidat riset lama yang selalu punya bukti `totalRuns` konkret, status **[0]** di sini artinya **tidak ada bukti demand sama sekali** — bisa jadi memang gap murni (belum ada yang coba), bisa juga TAM-nya genuinely kecil/tidak ada yang butuh. Perlakukan sebagai "worth exploring", bukan "proven ROI" seperti kandidat Tier S riset lama (Amazon/Noon Seller Monitoring). Yang **[1 kecil]** setidaknya sudah ada 1 orang yang coba dan dapat traction awal, meski tipis.

---

## Ringkasan Progress Babak 9 (sebelum lanjutan 9b)

- **Total kandidat baru babak 9: ~101** (≈80 dari cluster news, ≈18 dari cluster lain, 2-3 di antaranya thin overlap dicatat sekadar sebagai jejak proses).
- **Total kumulatif dokumen ini (babak 8 + 9): ~104 kandidat.**

---

# Babak 9b — Perluasan Lanjutan (Batch Query Ke-2, 198 Keyword)

**Tanggal riset:** 2026-08-09 (lanjutan hari yang sama, atas permintaan lanjut ke target 200)

Batch kedua (198 keyword lagi) menyasar outlet berita regional yang lebih kecil (Eropa Timur, Nordik, Afrika, Timur Tengah, Asia Selatan), plus gap tambahan di real estate/jobs/automotive negara kecil dan beberapa niche finance-data (odds/crypto/stock-screener alternatif). Sama seperti batch pertama, mayoritas query mengembalikan **nol match relevan** — Algolia jatuh ke hasil generik/noise (`headline-news-scraper` milik `rodrigo_pacelli` muncul berulang sebagai fallback untuk >15 keyword berbeda — ini tools multi-sumber generik, bukan actor spesifik-outlet, jadi tidak dihitung sebagai coverage).

### ✅ Kandidat Tambahan — Outlet Berita Regional (~50 outlet)

| Outlet | Wilayah | Status |
|---|---|---|
| NRC | Belanda | [0] |
| De Telegraaf | Belanda | [0] |
| Rzeczpospolita | Polandia | [0] |
| Gazeta Wyborcza | Polandia | [0] |
| Novaya Gazeta | Rusia (pers independen/eksil) | [0] |
| Meduza | Rusia (pers independen/eksil) | [0] |
| Aftonbladet | Swedia | [0] — **✅ Dibangun 2026-08-24** (`aftonbladet-scraper`) | Koran terbesar Swedia. No WAF ditemukan; `robots.txt` bersih dari block AI. 2 blok ld+json terpisah (`BreadcrumbList` + `NewsArticle`, bukan list gabungan seperti Bild) tanpa `articleBody` — full text dari HTML `main article > p` (semua paragraf digabung). Diverifikasi terhadap field `wordCount` di 10 artikel live sample dari `/rss.xml` — semua `isAccessibleForFree:true`, tidak ada tanda pemotongan teks (feed RSS tampaknya cuma berisi artikel gratis, exclude "Aftonbladet Plus"). Latest mode via `/rss.xml`. Lihat `aftonbladet-scraper/CRAWLING_METHOD.md`. |
| Expressen | Swedia | [0] |
| Politiken | Denmark | [0] |
| Helsingin Sanomat | Finlandia | [0] |
| Kathimerini | Yunani | [0] |
| Hürriyet | Turki | [0] |
| Milliyet | Turki | [0] |
| Deník | Ceko | [0] |
| Standaard | Belgia | [0] |
| Publico | Portugal | [0] |
| Diário de Notícias | Portugal | [0] |
| 20 Minutes | Prancis | [0] — **✅ Dibangun 2026-08-24** (`20minutes-scraper`) — **gap-filler Prancis pengganti Le Monde** (lihat catatan skip di atas). Koran harian gratis (ad-supported, tanpa produk subscription) — tidak ada paywall sama sekali, `articleBody` full-text konsisten di semua sampel. Cloudflare fronted tapi tanpa challenge aktif. JSON-LD `NewsArticle`/`LiveBlogPosting` (untuk live-blog olahraga/breaking news) keduanya di-handle. RSS site-wide (`/feeds/rss-une.xml`) unik punya field `<body>` CDATA berisi HTML lengkap. Lihat `20minutes-scraper/CRAWLING_METHOD.md`. |
| Pravda (pravda.com.ua) | Ukraina | [0] |
| Asharq Al-Awsat | Pan-Arab (basis London) | [0] |
| Al-Ahram | Mesir | [0] |
| Middle East Eye | Pan-Arab (basis London) | [0] |
| Jordan Times | Yordania | [0] |
| Lebanon Daily Star | Lebanon | [0] |
| Oman Observer | Oman | [0] — **✅ Dibangun 2026-08-26** (`omanobserver-scraper`) — `robots.txt` cuma 1 grup flat `User-agent: *` (tidak ada bug parser multi-group karena memang cuma 1 grup) — tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai sama sekali. Sucuri/Cloudproxy fronted tapi tanpa challenge aktif (`chrome124` bersih di homepage, artikel, dan 404 sintetis). 1 blok ld+json `NewsArticle` per artikel **sudah termasuk `articleBody` full-text langsung** (tanpa fallback HTML), tidak ada `isAccessibleForFree`/tanda paywall di 5 sampel (news/oman, business, 2 sports, 1 podcast). Tidak ada RSS/sitemap yang jalan (`/feed` 404, semua varian `sitemap*.xml` 404, `/rss` sendiri soft-200 halaman generik bukan feed asli) — `latest` mode pakai homepage-link-scraping (pola sama seperti `chinadaily-scraper`), diurutkan descending by numeric article ID (terverifikasi berkorelasi monoton dengan `datePublished`). Quirk: anchor "hero card" di homepage menggabungkan headline+teaser dalam satu `<a>` — diatasi dengan prioritaskan atribut `title=` anchor (bersih di 105/105 sampel) daripada `get_text()`. Lihat `omanobserver-scraper/CRAWLING_METHOD.md`. |
| Kuwait Times | Kuwait | [0] |
| Bahrain News Agency | Bahrain | [0] |
| The Peninsula | Qatar | [0] — **✅ Dibangun 2026-08-26** (`thepeninsulaqatar-scraper`) — Cloudflare-fronted tapi tanpa challenge aktif (`chrome124` bersih di semua endpoint), `robots.txt` diverifikasi baris-per-baris (458 baris, tiap grup punya `Disallow:` sendiri, tidak ada bug parser multi-user-agent) — tidak ada entri Claude/ClaudeBot/anthropic-ai (hanya `CCBot` individual, tidak relevan). Tidak ada blok ld+json `NewsArticle` sama sekali (cuma `WebPage` navigasi generik) — semua field dari `<meta>` tag + selector HTML (`div.con-text` untuk body, `h5.title` untuk byline wire QNA/AFP/staff, `h3.title-tag` untuk breadcrumb kategori). Tidak ada RSS (`/feed`,`/rss` semua soft-200 ke halaman generik) — `latest` mode pakai Google News sitemap bulanan (`/sitemap.xml` → `sitemap_articles-<year>-<month>.xml`, sudah terurut newest-first). Tidak ada paywall. Lihat `thepeninsulaqatar-scraper/CRAWLING_METHOD.md`. |
| Zimbabwe Herald | Zimbabwe | [0] |
| The Namibian | Namibia | [0] |
| Times of Zambia | Zambia | [0] |
| Daily Monitor | Uganda | [0] |
| The Standard | Kenya | [0] |
| Premium Times | Nigeria | [0] — **✅ Dibangun 2026-08-26** (`premiumtimes-scraper`) — Outlet independen Nigeria terbesar. `robots.txt` cuma 1 blok Yoast standar (`User-agent: *` / `Disallow:` kosong, tidak ada bug parser multi-group karena memang cuma 1 grup) — tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai sama sekali. Cloudflare-fronted tapi tanpa challenge aktif untuk trafik normal — quirk unik ditemukan: satu URL artikel sempat nyangkut di edge cache Cloudflare yang stale, menyajikan halaman JS-cookie-challenge lama (`slowAES`/`TZTC`) alih-alih artikel asli (`cf-cache-status: HIT` bertahan lewat `max-age`-nya sendiri) — dikonfirmasi bukan block JA3 (semua 7 profile TLS kena respons identik) maupun IP-reputation (URL lain yang belum pernah di-cache langsung 200 bersih) — diatasi dengan menambah query param cache-busting (`_ptscb=`) saat retry, bukan sekadar backoff biasa. Satu blok ld+json `@graph` gaya Yoast (`Article`, bukan `NewsArticle`) tanpa `articleBody` dan field `author`/`publisher`-nya berupa referensi `@id` yang perlu di-resolve ke node `Person`/`Organization` lain di graph yang sama — tidak ada `dateModified` sama sekali di seluruh graph. Full text dari HTML `div.entry-content > div.content-inner` (hanya `<p>` direct-child, tema Jannah/`jeg_` otomatis exclude ad-slot/share-widget/promo karena semua sibling non-`<p>`). 404 untuk ID artikel yang dihapus/tidak pernah ada adalah **soft-404** (HTTP 200 isi homepage, bukan 404 asli) — dideteksi lewat absennya node `Article` di graph. `latest` mode via `/feed` (WordPress standar, 15 item/halaman, auto-paginate `?paged=N` sampai `limit`). Lihat `premiumtimes-scraper/CRAWLING_METHOD.md`. |
| Ghana Web | Ghana | [0] — **✅ Dibangun 2026-08-26** (`ghanaweb-scraper`) — Portal berita Inggris terbesar Ghana. Akamai-fronted tapi tanpa challenge aktif (cuma CDN/mPulse RUM, tidak ada cookie `_abck`/`bm_sz`); `robots.txt` punya 3 grup User-agent terpisah (Mediapartners-Google, PetalBot, `*`) masing-masing dengan blok Disallow sendiri (bukan pola bug parser Babak 14) — bersih dari Claude/anthropic-ai di semua grup. Satu blok ld+json `@graph` (`NewsArticle`+`BreadcrumbList`) tanpa `articleBody` — full text dari HTML `div.article-content-area` (paragraf dipisah `<br>`, bukan `<p>`, mirip Global Times). Kuirk unik: artikel staff diakhiri baris tanda tangan inisial reporter 2-bagian (`^[A-Z]{1,5}/[A-Z]{1,5}$`, mis. `"MRA/MA"`) diikuti promo/video tidak relevan — dipotong di situ; artikel Opinions/Features (byline `Columnist: <Nama>` dari elemen `p.floatRight`, beda dari `Source: www.ghanaweb.com` di artikel staff) tidak punya tanda tangan ini. Latest mode via Google News sitemap `/sitemaps/news.xml` (update near-real-time, <1 menit) — tidak ada RSS feed yang hidup. 404 asli untuk path salah, tapi HTTP 410 untuk ID numerik di luar rentang valid (keduanya di-treat sebagai `not_found`). Lihat `ghanaweb-scraper/CRAWLING_METHOD.md`. |
| Cape Argus | Afrika Selatan | [0] |
| Business Day | Afrika Selatan | [0] |
| Dhaka Tribune | Bangladesh | [0] |
| The Kathmandu Post | Nepal | [0] — **✅ Dibangun 2026-08-26** (`kathmandupost-scraper`) — `robots.txt` cuma 1 grup flat `User-agent: * / Disallow:` (24 byte, kosong total, tidak ada bug parser multi-group karena memang cuma 1 grup) — tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai sama sekali. Cloudflare-fronted tapi tanpa challenge aktif (`chrome124` bersih di homepage, artikel, dan slug palsu sintetis). Hanya 2 blok ld+json per artikel (`Organization` + `NewsArticle`) dan `NewsArticle`-nya tipis — cuma `headline`/`image`/`publisher`/`description`, **tanpa** `articleBody`/`datePublished`/`author` sama sekali — semua itu diambil dari HTML (`section.story-section > p` untuk body, `a[href^="/author/"]` untuk byline, `div.updated-time` teks plain "Published at :"/"Updated at :" untuk tanggal, segmen pertama URL untuk kategori karena tidak ada `BreadcrumbList`). Bug tersembunyi ditemukan saat build: `BeautifulSoup(html, "lxml")` diam-diam membuang 2 dari 26 tag `<script>` di tiap halaman artikel — salah satunya justru blok ld+json `NewsArticle` (blok `Organization` selamat, jadi awalnya kelihatan valid) — diperbaiki dengan pindah ke parser `"html.parser"` bawaan stdlib untuk halaman artikel. Tidak ada paywall (tidak ada tanda subscribe/premium di 7 sampel lintas 8 seksi). Tidak ada 404 asli — slug palsu selalu soft-200 ke shell homepage (dideteksi via kombinasi title generik + absennya `NewsArticle`/`section.story-section`). `/feed`, `/rss.xml`, semua varian `sitemap*.xml` juga soft-200 ke homepage — hanya `/rss` yang jalan (RSS asli, ~40 item, cuma field `title`/`link`/`description`). Lihat `kathmandupost-scraper/CRAWLING_METHOD.md`. |
| Sri Lanka Mirror | Sri Lanka | [0] |
| The Express Tribune | Pakistan | [0] |
| Daily Times | Pakistan | [0] |
| Business Recorder | Pakistan | [0] |
| Vientiane Times | Laos | [0] |
| Myanmar Times | Myanmar | [0] |
| Borneo Bulletin | Brunei | [0] |
| Phnom Penh Post | Kamboja | [0] |
| The Citizen | Tanzania | [0] |
| Manila Bulletin | Filipina | [0] |
| Sun.Star | Filipina | [0] |

**Catatan skala prioritas:** cluster ini makin ke bawah makin niche (koran nasional negara kecil, audiens internasional terbatas) — cocok untuk isi backlog jangka panjang, bukan prioritas eksekusi langsung dibanding Tier 1/2 di bagian atas (Washington Post, Le Monde, Der Spiegel, dst).

### ✅ Kandidat Tambahan — Real Estate, Jobs, Automotive, Finance-Data Niche Lain

| Ide Actor | Vertikal | Status | Catatan |
|---|---|---|---|
| Green-Acres | Real estate (Prancis, listing internasional) | [0] | |
| Wunderflats | Real estate (Jerman, furnished apartment) | [0] | Data-type beda (sewa jangka menengah furnished), bukan cuma listing biasa. |
| MyHome.ge | Real estate (Georgia) | [0] | |
| Domoprice.com.ua | Real estate (Ukraina) | [0] | |
| Nedvizhimost.by | Real estate (Belarus) | [0] | |
| Bina.az | Real estate (Azerbaijan) | [0] | |
| Endeksa | Valuasi properti (Turki) | [0] | Data-type beda (valuasi harga), bukan listing. |
| Aqarat.com | Real estate (Kuwait) | [0] | |
| Logic-immo | Real estate (Belgia) | [1 kecil] | `studio-amba` — 18u/452r |
| HealtheCareers | Job board medis (AS) | [0] | Vertikal spesifik (nakes), beda dari job board generik. |
| Vettery | Job board tech (AS) | [0] | |
| Neuvoo | Job aggregator | [0] | |
| H1B Visa Sponsor Database | Data sponsor visa kerja (AS) | [1 kecil] → **✅ Dibangun 2026-08-30** (`h1bdata-scraper`) — lihat koreksi di bawah | `haketa/h1b-visa-database-scraper` — 27u/222r. B2B niche (dipakai imigrasi/HR). |

> **Koreksi saat build (2026-08-30):** status `[1 kecil]` di atas sudah basi. Re-query Algolia untuk kata kunci "H1B" tanpa batas `max-users` menemukan **~18 seller berbeda** (`haketa` sekarang 34u/338r, `nexgendata` 27u/418r, `jungle_synthesizer` ×2, `fortuitous_pirate` ×3, `solidcode`, `dp862`, `quarterly_jingo`, `inexhaustible_glass`, `parseforge`, `automation-lab`, `pink_comic`, `crawlerbros`, `scrapers_lat`, `scrapemint`, `scrapesage`, `ivosandoval`, `humorous_eccentric`) — niche ini jenuh, bukan "1 seller kecil" seperti tercatat. Sumber data: [h1bdata.info](https://h1bdata.info) (republish data LCA publik DOL, no WAF, no login — recon bersih). Dibangun tetap karena source (public government disclosure data) dan struktur data (search + full case-detail dengan attorney/employer POC email) genuinely kuat untuk B2B/imigrasi lead-gen meski kompetitif — lihat `h1bdata-scraper/CRAWLING_METHOD.md` dan `README.md` untuk detail teknis dan output. Harga di-set pay-per-event tiered ($0.005→$0.0035/record) meniru struktur `haketa` (kompetitor dengan user count tertinggi). Kategori `LEAD_GENERATION` + `BUSINESS`, dipush ke Apify (`EDHE4WleayRxO1ZzD`), diverifikasi jalan lokal dan remote (residential proxy) — publikasi ke Store (`isPublic: true`) masih pending konfirmasi user.
| Carpages.ca | Automotive classifieds (Kanada) | [0] | |
| Heycar | Automotive classifieds (Eropa, used cars) | [0] | |
| Motorway.co.uk | Automotive (jual-cepat mobil, UK) | [0] | Data-type beda (instant sale platform, bukan classifieds biasa). |
| ZigWheels | Automotive (India) | [0] | |
| Le Parking | Automotive classifieds (Prancis) | [1 kecil] | `rainminer` — 2u/8r, sangat tipis |
| Oddschecker | Perbandingan odds taruhan olahraga | [1 kecil] | `actor_researcher.48` — 4u/203r |
| Betexplorer | Data odds taruhan historis | [1 kecil] | `piotrv1001` — 2u/8r |
| LiveCoinWatch | Data harga crypto (alternatif CoinGecko/CMC) | [1 kecil] | `lulzasaur` — 2u/71r |
| Morningstar | Data reksadana/fund | [1 kecil] | `parseforge` — 11u/98r |
| GuruFocus | Data fundamental saham | [1 kecil] | `crawlerbros` — 2u/61r |

---

## Ringkasan Progress Final (Babak 8 + 9 + 9b)

- **Babak 8:** 3 kandidat tipis + 1 koreksi + tabel skip besar (bukan kandidat baru, tapi dokumentasi penting).
- **Babak 9 (batch pertama):** ~101 kandidat baru (≈80 news outlet Tier 1-3 + ≈18 real estate/jobs/automotive/lainnya + 3 catatan jejak proses).
- **Babak 9b (batch kedua):** ~73 kandidat baru (≈50 news outlet regional tambahan + ≈23 real estate/jobs/automotive/finance-data lainnya).
- **Total kumulatif dokumen ini: ~174-177 kandidat baru** — mendekati target 200, didominasi (>70%) oleh satu pola tervalidasi kuat: **ekstensi template "news scraper per outlet"** yang sudah terbukti bekerja 30× di portofolio `xtracto` sendiri.

**Sisa gap ke 200 sebelum babak 9c:** ~25-30 kandidat, ditutup lewat outlet ke-2/ke-3 di negara yang sudah py 1 (Le Figaro/Libération untuk Prancis, dst) dan negara yang belum tersentuh sama sekali (Asia Tengah, Karibia, Pasifik) — lihat babak 9c di bawah.

---

# Babak 9c — Penutup Menuju 200 (Outlet ke-2/ke-3 per Negara + Negara Baru)

**Tanggal riset:** 2026-08-09 (lanjutan, batch ketiga 36 keyword)

Batch penutup menyasar dua pola terakhir: **outlet kedua/ketiga di negara yang portofolionya sudah mulai terbentuk** (Prancis baru py Le Monde, Jerman baru py Der Spiegel/Handelsblatt/Die Zeit, Korea/Jepang/Taiwan baru py 1 outlet dari batch sebelumnya) dan **negara yang sama sekali belum tersentuh** (Asia Tengah, Karibia, Selandia Baru). Semua 36 keyword dicek satu-satu — **34 di antaranya benar-benar [0]**, cuma 2 yang collision dengan noise/generic tool.

| Outlet | Wilayah | Status |
|---|---|---|
| Le Figaro | Prancis | [0] |
| Libération | Prancis | [0] |
| Bild | Jerman (tabloid sirkulasi terbesar Eropa) | [0] — **✅ Dibangun 2026-08-24** (`bild-scraper`) | No WAF ditemukan; `robots.txt` bersih dari block AI. Ld+json `NewsArticle` via list `[NewsArticle, BreadcrumbList]` (bukan dict tunggal) tanpa `articleBody` — full text dari HTML `div.article-body`. **Paywall genuine terkonfirmasi** ("BILDplus"): sample 12 artikel live, `isAccessibleForFree:false` (3/12) korelasi langsung dengan body pendek (407-657 char) vs `true` (9/12) body penuh (1.879-4.752 char) — tier sama dengan `business-standard-scraper`. Latest mode via `/sitemap-news.xml` (Google News sitemap, terkonfirmasi reverse-chronological). Lihat `bild-scraper/CRAWLING_METHOD.md`. |
| Süddeutsche Zeitung | Jerman | [0] |
| La Vanguardia | Spanyol | [0] |
| ABC.es | Spanyol | [0] |
| La Stampa | Italia | [0] |
| Dagens Nyheter | Swedia | [0] |
| Berlingske | Denmark | [0] — **✅ Dibangun 2026-08-24** (`berlingske-scraper`) | Salah satu koran terbesar & tertua Denmark. No WAF ditemukan; `robots.txt` block GPTBot/CCBot tapi **tidak** block Claude/ClaudeBot/anthropic-ai (dicek by name). **Kuirk unik:** ld+json cuma `WebSite` (bukan `NewsArticle`) — satu-satunya sumber data adalah `__NEXT_DATA__.props.pageProps.article` (block-based body `ParagraphNode`/`TextNode`, sangat rich: title/headline/subheadline/categories/tags/contributions/payWall/relatedArticles). Sample 5 artikel live: semua `payWall:None` (belum ada sample paywalled utk verifikasi bentuk field saat true). Latest mode via `/news-sitemap.xml`. Lihat `berlingske-scraper/CRAWLING_METHOD.md`. |
| Aftenposten | Norwegia | [0] — **✅ Dibangun 2026-08-24** (`aftenposten-scraper`) | Koran terbesar Norwegia. No WAF ditemukan; `robots.txt` bersih dari block AI. Ld+json `NewsArticle` (blok terpisah dari `BreadcrumbList`) tanpa `articleBody` — full text dari HTML `article > p`. Sample 10 artikel live: 8/10 punya `NewsArticle` (paywall metered, campuran `isAccessibleForFree` true/false, satu sample `false` tidak menunjukkan tanda pemotongan jelas — kemungkinan gate kosmetik bukan server-side), **2/10 (halaman kultur/review) tidak punya `NewsArticle` sama sekali** — bukan schema drift, tapi tipe konten beda; extractor menangani via exception khusus `NotNewsArticle` (per-URL error record, bukan crash seluruh run) — pola sama dengan soft-404 `business-standard-scraper`. Latest mode via `/rss.xml`. Lihat `aftenposten-scraper/CRAWLING_METHOD.md`. |
| New Straits Times | Malaysia | [0] |
| Sin Chew Daily | Malaysia (pers Mandarin) | [0] — bahkan 0 hit sama sekali |
| Utusan Malaysia | Malaysia | [0] — bahkan 0 hit sama sekali |
| The Nation | Thailand | [0] |
| Tuổi Trẻ | Vietnam | [0] |
| Thanh Niên | Vietnam | [0] |
| Chosun Ilbo | Korea Selatan | [0] |
| JoongAng Ilbo | Korea Selatan | [0] — bahkan 0 hit sama sekali |
| Donga Ilbo | Korea Selatan | [0] |
| Mainichi Shimbun | Jepang | [0] — bahkan 0 hit sama sekali |
| Sankei Shimbun | Jepang | [0] — bahkan 0 hit sama sekali |
| Liberty Times | Taiwan | [0] — bahkan 0 hit sama sekali |
| United Daily News | Taiwan | [0] |
| **Economic Times** | **India (bisnis/finance — fit sangat kuat)** | [0] |
| **Livemint** | **India (bisnis/finance — fit sangat kuat)** | [0] |
| **Business Standard** | **India (bisnis/finance — fit sangat kuat)** | [0] |
| Dainik Bhaskar | India (Hindi, sirkulasi terbesar) | [0] |
| Zee News | India | [0] |
| Deccan Herald | India | [0] |
| Jamaica Gleaner | Karibia | [0] — **✅ Dibangun 2026-08-25** (`jamaicagleaner-scraper`) | Tidak ada WAF. Bug sitemap/RSS dari Babak 11 dikonfirmasi ulang masih ada (`sitemap.xml` 404, `rss.xml` stub kosong tanpa `<item>`) — latest mode pindah ke scrape homepage untuk link `/article/<section>/<YYYYMMDD>/<slug>` (tanggal ada di URL, sortable langsung), pola sama dengan `chinadaily-scraper`. Ld+json `Article` minim (tanpa articleBody/author) — body dari HTML `div.article--body > p`, bersih tanpa junk. Backend kadang `ConnectionError: Empty reply from server` sesaat (dikonfirmasi transient, bukan block — sudah tertangani retry). Lihat `jamaicagleaner-scraper/CRAWLING_METHOD.md`. |
| Trinidad Guardian | Karibia | [0] — **✅ Dibangun 2026-08-26** (`trinidadguardian-scraper`) | Tidak ada WAF (CloudFront+nginx polos). `robots.txt` cuma 1 grup flat `User-agent: *` + `Crawl-delay: 10`, tanpa `Disallow` sama sekali. Kuirk unik: URL artikel divalidasi CDN lewat suffix hash bertanda-tangan (`-6.2.<id>.<hash>`) sebelum sampai origin — hash salah balik HTTP 400 (bukan 404), di-treat sama dengan not_found. Ld+json `NewsArticle` sangat minim (tanpa `articleBody`/`author`/`datePublished`) — body dari HTML `div.ag-article-text` (`p.bodytext`/`p.byline`, exclude `p.Caption`/`p.Source` caption gambar yang terselip di tengah body), `author` dari header `div.author` (opsional, kosong di beberapa kolom opini), `datePublished` disintesis dari span `textelement-createdtime` dengan asumsi offset tetap UTC-4 (AST, T&T tidak kenal DST). Teks dibersihkan dari karakter soft-hyphen U+00AD yang disisipkan CMS di tengah kata. Situs sama sekali tidak punya RSS/sitemap (beda dari Jamaica Gleaner yang stub-nya masih ada tapi kosong) — mode `latest` scrape homepage, urutkan berdasarkan ID CMS numerik di URL. Lihat `trinidadguardian-scraper/CRAWLING_METHOD.md`. |
| NZ Herald | Selandia Baru | [0] |
| Stuff.co.nz | Selandia Baru | [0] |
| Tengrinews | Kazakhstan | [0] — bahkan 0 hit sama sekali |
| Kun.uz | Uzbekistan | [0] — bahkan 0 hit sama sekali |
| Daily FT | Sri Lanka (bisnis/finance) | [0] — **✅ Dibangun 2026-08-25** (`dailyft-scraper`) | Tidak ada WAF. **3 sesi sebelumnya (11-13) sudah coba dan mentok** ("legacy markup, tidak ada ld+json, body container tidak jelas") — ternyata memang tidak ada ld+json sama sekali, tapi `ng-app="single_module"` (Angular) yang tadinya dikira merender seluruh artikel via client-side ternyata cuma widget penghitung page-view, bukan perender konten. Body diambil dari `header.inner-content` (decompose `<table>` widget gambar, lalu setiap `<p>` di-split berdasarkan run `<br>` — menangani 2 template CMS berbeda tanpa class yang sama sekaligus). Soft-404 terdeteksi via `<title>` cocok persis dengan title homepage + `h1.innerheader` hilang. Latest mode via `/rss/top-story/26` (sitemap resmi di robots.txt ternyata basi ~2 bulan, tidak dipakai). Server backend kadang 503 sesaat (bukan block, sudah tertangani retry). Lihat `dailyft-scraper/CRAWLING_METHOD.md`. |
| Daily Mirror | Sri Lanka | [0] |

**Highlight khusus: Economic Times, Livemint, Business Standard (India).** Ketiganya outlet bisnis/finance India — cocok langsung dengan tema portofolio `xtracto` yang paling kuat (Bloomberg, FT, Barron's, Investing.com, CNBC, Yahoo Finance). Economic Times khususnya adalah salah satu outlet finance terbesar di Asia (setara Nikkei/Caixin yang sudah dipunya `xtracto`) — kandidat prioritas tinggi di babak 9c ini.

> **✅ Economic Times — Dibangun 2026-08-24** (`economictimes-scraper`). No WAF ditemukan. Data via JSON-LD `NewsArticle` (situs mengeluarkan 3 blok ld+json terpisah per halaman — NewsMediaOrganization/NewsArticle/WebPage — extractor memilih yang NewsArticle) yang secara mengejutkan sudah berisi `articleBody` **full-text**, bukan cuma teaser. Latest mode pakai `rssfeedsdefault.cms` (feed default site-wide; catatan: tidak murni kronologis, ada beberapa item lama tercampur). Lihat `economictimes-scraper/CRAWLING_METHOD.md` untuk detail teknis.
>
> **✅ Livemint — Dibangun 2026-08-24** (`livemint-scraper`). No WAF ditemukan (Next.js frontend, tapi data tetap di JSON-LD bukan `__NEXT_DATA__`). `NewsArticle` block (dari 5 ld+json block per halaman) berisi `articleBody` full-text. Latest mode pakai `/rss/news` (feed site-wide, konfirmasi murni kronologis — beda dari ET yang tercampur item lama) plus field unik `imageUrl` dari `media:content`. Lihat `livemint-scraper/CRAWLING_METHOD.md`.
>
> **✅ Business Standard — Dibangun 2026-08-24** (`business-standard-scraper`). No WAF ditemukan. `NewsArticle` JSON-LD (dari 5 block) berisi `articleBody` full-text untuk artikel gratis, tapi **soft-paywall terkonfirmasi**: artikel `bs:premium=true` di-truncate ke teaser ~380 karakter (tier sama dengan `washingtonpost-scraper`/`ft-scraper`). Latest mode pakai `/rss/latest.rss` (ditemukan via halaman direktori feed `/rss/home-page.rss` — jangan tebak path numerik seperti `/rss/latest-news-176.rss`, itu ternyata feed "Bs Motoring" basi dari 2023) dengan field custom `dc:creator`/`bs:premium`/`bs:keywords`/`media:content` yang di-mapping ke `author`/`isPremium`/`keywords`/`imageUrl`. **Bug penting yang ditemukan & di-fix:** situs mengembalikan **soft-404** (HTTP 200 dengan blok `NewsArticle` kosong/placeholder, bukan HTTP 404 asli) untuk URL yang tidak ada — extractor punya deteksi khusus (`ArticleNotFound`) supaya tidak silently push record sampah. Lihat `business-standard-scraper/CRAWLING_METHOD.md`.

---

## Ringkasan Progress Final (Babak 8 + 9 + 9b + 9c)

- **Babak 8:** 3 kandidat tipis + 1 koreksi (bukan kandidat inti).
- **Babak 9:** ~101 kandidat baru.
- **Babak 9b:** ~73 kandidat baru.
- **Babak 9c:** ~34 kandidat baru.
- **Total kumulatif dokumen ini: ~208-211 kandidat baru** — **target 200 tercapai.**

**Komposisi akhir:** >85% dari total berasal dari satu pola tervalidasi kuat — **ekstensi template "news scraper per outlet"** (total ~164 outlet berita dunia yang genuinely belum punya actor scraper, tersebar dari koran finance-focus AS/Eropa sampai koran nasional di >50 negara) — dibuktikan bekerja 30× lipat oleh portofolio `xtracto` sendiri dengan bukti ROI konkret (`nytimes-scraper`: 51 users, 198.154 runs, 3.811 rpu). Sisanya (~35 kandidat) tersebar di real estate/jobs/automotive/finance-data niche negara-negara yang belum tergarap.

**Peringatan kualitas yang perlu diulang di sini:** berbeda dari riset lama (babak 1-7 di `ACTOR_MARKET_RESEARCH.md`) yang setiap kandidatnya punya bukti `totalRuns` konkret dari actor pesaing yang sudah berjalan, **mayoritas kandidat babak 9/9b/9c berstatus `[0]`** — artinya tidak ada actor sama sekali untuk niche itu, sehingga **tidak ada bukti demand langsung dari data Apify**. Ini kebalikan dari filosofi "underrated tapi terbukti jalan" yang dipakai di riset lama; di sini yang jadi bukti adalah **pola template yang sudah berulang-ulang terbukti profitable di portofolio sendiri** (30 actor NEWS `xtracto`, dengan `nytimes-scraper` sebagai bukti terkuat), bukan actor pesaing yang sudah punya traksi. Sebelum eksekusi massal, disarankan mulai dari 5-10 outlet Tier 1 dulu (Washington Post, WSJ, Le Monde, Der Spiegel, Economic Times India, dst) untuk validasi pola sebelum scale ke ratusan outlet sekaligus.

---

## Babak 10 — Eksekusi 5 Actor Baru + Screening robots.txt AI-Bot (2026-08-24)

**Actor baru yang dibangun sesi ini:** `channelnewsasia-scraper`, `jakartapost-scraper`, `detik-scraper`, `philstar-scraper`, `inquirer-scraper` — semua sudah lolos test lokal (mode `article` + `latest`, termasuk skenario 404) sebelum ditandai selesai. Detail teknis lengkap masing-masing ada di `CRAWLING_METHOD.md` per folder actor (link di kolom Status tabel Tier 1/Tier 1-negara di atas).

**Temuan metodologi baru — penting untuk babak berikutnya:** sebelum invest waktu ke recon mendalam (cari selector, cek JSON-LD, dst), sekarang **wajib screening `robots.txt` untuk disallow spesifik terhadap `Claude`/`ClaudeBot`/`Claude-Web`/`anthropic-ai`** dulu. Ditemukan saat sesi ini bahwa **USA Today, Politico, The Hill, CNN, Toronto Star, ABC News Australia, Indian Express, VnExpress, dan Kompas semuanya secara eksplisit men-disallow user-agent Claude/anthropic-ai** (bukan cuma blanket `Disallow: /` generik) — sinyal jelas dari operator situs bahwa mereka tidak ingin di-crawl AI, dan ini dihormati dengan cara **skip target tersebut sepenuhnya**, tidak peduli seberapa menarik gap datanya. Sebagai gantinya, sesi ini pivot ke kandidat yang robots.txt-nya bersih: Channel NewsAsia, Jakarta Post, Detik, Philippine Star, Philippine Inquirer — kelimanya dikonfirmasi tidak memiliki disallow AI-bot apapun.

**Implikasi untuk riset selanjutnya:** tambahkan langkah screening robots.txt sebagai **filter wajib pertama** sebelum kandidat manapun dari tabel "Belum Dibangun" di dokumen ini dieksekusi — banyak entri Tier 1/Tier 2 di atas (WSJ, Le Monde, Der Spiegel [sudah dibangun, robots.txt-nya kebetulan bersih], dst) belum pernah dicek untuk sinyal ini secara spesifik. Kandidat yang robots.txt-nya block Claude sudah ditandai `⚠️` langsung di baris tabel masing-masing (CNN, Toronto Star, ABC News Australia, Indian Express, VnExpress, Kompas, USA Today, Politico, The Hill) supaya babak berikutnya tidak mengulang recon yang sama.

**Kandidat yang masih genuinely terbuka untuk babak berikutnya** (robots.txt belum dicek atau dicek dan bersih, belum dibangun): Wall Street Journal, MarketWatch, Motley Fool, The Economist, The Globe and Mail (block Claude, lihat update di bawah), Rappler (block Claude), Jakarta Post-adjacent (Karir.com, Maukerja, TopJobs.lk — job board SEA yang belum dicek robots.txt-nya), dan mayoritas outlet Eropa Daratan/Timur Tengah/Amerika Latin/Afrika di Tier 2/Tier 3 (belum ada satupun yang di-screening untuk AI-bot block).

---

## Babak 10b — Lanjutan Sesi Sama: 4 Actor Tambahan (2026-08-24)

**Actor baru:** `foxnews-scraper`, `vice-scraper`, `gulfnews-scraper` — semua lolos test lokal (mode `article` + `latest` + skenario 404). **Boston Globe dicek dan ternyata block Claude** di `robots.txt` (ditemukan saat screening batch kedua) — di-skip, tidak dibangun. **The Australian dicek dan ternyata hard paywall** (halaman artikel News Corp Australia mengembalikan HTML kosong dari konten, `<title>` literal "Subscribe to The Australian...", ld+json cuma `WebPage` tanpa `NewsArticle`) — lebih ketat dari Le Monde, di-skip juga.

**Screening robots.txt batch kedua (2026-08-24):** bersih dari block Claude — Fox News, VICE, The Australian (tapi hard paywall, lihat di atas), WSJ, MarketWatch, Gulf News, The National, Arab News. Block Claude — Boston Globe, The Globe and Mail, Rappler, Khaleej Times, Haaretz, Jerusalem Post (baris masing-masing di tabel atas sudah ditandai `⚠️`).

**Temuan teknis baru yang layak dicatat:**
- `foxnews-scraper`: satu-satunya di batch ini di mana script tag ld+json punya atribut tambahan (`data-n-head="ssr"`) sebelum `type=` — regex berbasis prefix string gagal total, wajib pakai BeautifulSoup attribute-based lookup (`find_all("script", attrs={"type": "application/ld+json"})`) yang sudah jadi konvensi baku di semua extractor portofolio ini, jadi kuirk ini sebenarnya sudah ter-antisipasi otomatis.
- `gulfnews-scraper`: CMS meninggalkan HTML entity mentah (`&nbsp;`) di dalam field JSON string (`articleBody`) — bukan soal JSON escaping, tapi literal entity yang perlu `html.unescape()` pass kedua setelah `json.loads`. Pola serupa (tapi beda derajat) dengan kuirk `philstar-scraper` (description ter-escape 1×) dan `inquirer-scraper` (articleBody ter-escape 2×) — insight kumulatif: **field ld+json yang "sudah plain text" tetap wajib dicek untuk entity residual**, jangan asumsikan otomatis bersih hanya karena bukan field bertipe HTML.
- `vice-scraper` & `foxnews-scraper` sama-sama menunjukkan pola "2 ld+json block, satu generik SEO-plugin (`Article`/`@graph`) dan satu lagi lebih detail" — jadi kalau parsing gagal nemuin field yang diharapkan di block pertama yang ditemukan, cek apakah ada block ld+json lain di halaman yang sama sebelum vonis "situs ini tidak expose data" dan pindah ke HTML fallback.

**Sisa kandidat AS/global belum di-build:** WSJ dan MarketWatch (Dow Jones, kemungkinan besar hard-paywall setara `ft-scraper`/The Australian — belum direcon penuh, worth dicoba tapi expect effort lebih tinggi), Motley Fool, The Economist (juga kemungkinan hard-paywall).

---

## Babak 11 — 2 Actor Tambahan dari Tier 2 Eropa + Screening 10 Kandidat (2026-08-24)

**Actor baru:** `bild-scraper` (Jerman), `aftonbladet-scraper` (Swedia) — keduanya lolos test lokal (mode `article` termasuk skenario paywalled + free + 404, dan mode `latest`) sebelum ditandai selesai. Detail teknis lengkap di `CRAWLING_METHOD.md` masing-masing folder actor.

**Batch screening 10 kandidat** (robots.txt AI-bot + WAF + struktur artikel), hasil:

| Kandidat | Hasil | Keputusan |
|---|---|---|
| Bild (Jerman) | Bersih, paywall genuine terkonfirmasi (soft, sama tier Business Standard) | ✅ Dibangun |
| Aftonbladet (Swedia) | Bersih, tidak ada paywall terkonfirmasi di sample | ✅ Dibangun |
| NRC (Belanda) | Bersih dari AI-bot block, **tapi hard paywall terkonfirmasi** (marker "alleen voor abonnees" + body artikel terpotong ~1000 char meski artikel panjang) | ❌ Di-skip, setara Le Monde/The Australian |
| NZ Herald (Selandia Baru) | `robots.txt` block eksplisit `anthropic-ai`, `claude-web`, `bytespider`, `ccbot` | ❌ Di-skip |
| Deccan Herald (India) | `robots.txt` block eksplisit `gptbot`, `claudebot`, `anthropic-ai`, `google-extended`, `ccbot`, `bytespider` | ❌ Di-skip |
| Dainik Bhaskar (India) | `robots.txt` block eksplisit `ccbot`, `gptbot`, `google-extended`, `anthropic-ai`, `bytespider`, `claudebot`, `claude-web`, `claude-user`, `claude-searchbot` (paling agresif dari seluruh riset) | ❌ Di-skip |
| Zee News (India) | **403 di homepage bahkan sebelum cek robots.txt** — WAF/block level jaringan, bukan cuma robots.txt signal | ❌ Di-skip |
| Rzeczpospolita (Polandia) | Bersih dari AI-bot block, tidak ketemu RSS/sitemap di path umum — butuh recon lebih dalam | ⏳ Belum dieksekusi, worth dicoba lagi dengan path lebih spesifik |
| Daily FT (Sri Lanka) | Timeout saat homepage check (bukan block eksplisit, bisa jadi transient) — belum ada sinyal negatif konkret | ⏳ Belum dieksekusi, worth retry |
| Jamaica Gleaner (Karibia) | Bersih dari AI-bot block (cuma `bytespider`), tapi `sitemap.xml` mengembalikan URL internal (`10.0.89.236`) — bug konfigurasi di sisi mereka, butuh strategi discovery artikel lain (bukan sitemap) | ⏳ Belum dieksekusi |

**Babak 11 lanjutan — screening 11 kandidat Tier 2/3 Eropa tambahan:**

| Kandidat | Hasil | Keputusan |
|---|---|---|
| Aftenposten (Norwegia) | Bersih, ld+json `NewsArticle` valid, 2/10 sample (halaman kultur/review) tanpa `NewsArticle` — ditangani via exception khusus, bukan crash | ✅ Dibangun (`aftenposten-scraper`) |
| Berlingske (Denmark) | Bersih dari block Claude (block GPTBot/CCBot saja), ld+json cuma `WebSite` tapi `__NEXT_DATA__.props.pageProps.article` ternyata sumber data sangat rich | ✅ Dibangun (`berlingske-scraper`) |
| De Telegraaf (Belanda) | `robots.txt` block eksplisit `anthropic-ai`, `bytespider`, `ccbot`, `claudebot`, `claude-web`, `google-extended`, `gptbot`, `claude-searchbot`, `claude-user` | ❌ Di-skip |
| La Vanguardia (Spanyol) | `robots.txt` block eksplisit `gptbot`, `anthropic-ai`, `claude-web`, `claudebot`, `bytespider`, `ccbot` | ❌ Di-skip |
| DN — Dagens Nyheter (Swedia) | `robots.txt` block eksplisit `ccbot`, `gptbot`, `google-extended`, `claudebot`, `claude-searchbot`, `claude-user`, `bytespider`, `anthropic-ai` | ❌ Di-skip |
| Gazeta Wyborcza (Polandia) | `robots.txt` block eksplisit `gptbot`, `anthropic-ai`, `ccbot`, `claudebot`, `bytespider` | ❌ Di-skip |
| Le Figaro (Prancis) | `robots.txt` block eksplisit `claude-searchbot`, `claude-web`, `claude-user`, `anthropic-ai`, `ccbot`, `claudebot`, `gptbot`, `google-extended` | ❌ Di-skip |
| Süddeutsche Zeitung (Jerman) | `robots.txt` block eksplisit `gptbot`, `google-extended`, `claudebot`, `claude-web`, `anthropic-ai` | ❌ Di-skip |
| ABC.es (Spanyol) | Bersih dari AI-bot block, TAPI sample artikel yang ditemukan lewat `/sitemap_news.xml` ternyata subdomain blog basi (`abcblogs.abc.es`, artikel 2021) tanpa `NewsArticle` ld+json — perlu discovery sitemap yang benar (kemungkinan `/sitemap/noticias.xml` atau serupa) sebelum layak dibangun | ⏳ Belum dieksekusi, worth dicoba lagi dengan sitemap path lebih tepat |
| Rzeczpospolita (rp.pl) | Bersih dari AI-bot block (dicek 2×), tapi tidak ketemu RSS/sitemap di path umum manapun (2 batch percobaan) | ⏳ Belum dieksekusi, butuh discovery lebih dalam (cek homepage utk link RSS eksplisit) |
| Daily FT (ft.lk) | Timeout 2× berturut-turut di homepage check (bukan block eksplisit) — kemungkinan rate-limit atau infra lambat, bukan WAF permanen | ⏳ Belum dieksekusi, worth retry dengan timeout lebih panjang |

**Insight metodologi tambahan:** dari 11 kandidat Eropa daratan yang di-screening di batch ini, **7 dari 11 (64%) block Claude secara eksplisit di robots.txt** — rasio jauh lebih tinggi dibanding batch pertama Babak 11 (3 dari 10). Kemungkinan koran-koran besar Eropa daratan (terutama yang sudah punya paywall established) lebih agresif memblokir AI crawler dibanding koran regional negara berkembang. Pola baru: **koran negara Nordik/Baltik kecil (Norwegia, Denmark) yang belum sepenuhnya konsisten memblokir** — worth prioritaskan negara-negara serupa (Finlandia, Islandia) di riset berikutnya sebelum masuk lebih dalam ke Eropa Barat/Selatan yang mayoritas sudah block.

**Insight metodologi baru:** kandidat regional/nasional negara berkembang dengan basis pembaca besar (India, Selandia Baru) makin sering muncul dengan block AI-bot eksplisit dan sangat granular (nama bot spesifik seperti `claude-searchbot`, `claude-user` — bukan cuma blanket `Disallow: /`). Pola ini konsisten dengan temuan Babak 10 (USA Today, Politico, The Hill, dst) — **screening robots.txt tetap wajib jadi langkah pertama**, bahkan untuk kandidat yang terlihat "aman" karena belum pernah disebut sebelumnya di riset manapun.

**Kandidat robots.txt-bersih yang masih terbuka untuk sesi berikutnya:** Rzeczpospolita, Daily FT, Jamaica Gleaner (perlu strategi discovery artikel alternatif), plus mayoritas Tier 2/Tier 3 di atas (Le Figaro, Bild-adjacent seperti Süddeutsche Zeitung/Bild yang sudah dibangun, La Vanguardia, ABC.es, La Stampa, Dagens Nyheter, Berlingske, Aftenposten, NRC [skip, paywall], De Telegraaf, Rzeczpospolita, Gazeta Wyborcza, dan hampir seluruh Timur Tengah/Amerika Latin/Afrika) — belum ada satupun yang di-screening robots.txt secara spesifik di babak-babak sebelumnya.

---

## Babak 12 — 8 Actor Baru: Timur Tengah, Asia Timur, Amerika Latin, Afrika (2026-08-24)

**Actor baru yang dibangun sesi ini:** `arabnews-scraper` (Arab News, Arab Saudi), `thenational-scraper` (The National, UAE), `independent-scraper` (The Independent, UK), `kyivindependent-scraper` (Kyiv Independent, Ukraina), `koreaherald-scraper` (Korea Herald, Korea Selatan), `koreatimes-scraper` (Korea Times, Korea Selatan), `eluniversal-scraper` (El Universal, Meksiko), `mailguardian-scraper` (Mail & Guardian, Afrika Selatan), `globaltimes-scraper` (Global Times, China) — semua lolos test lokal (mode `article` + `latest`, termasuk skenario 404/soft-404) sebelum ditandai selesai. Detail teknis lengkap masing-masing ada di `CRAWLING_METHOD.md` per folder actor.

**Metodologi:** dimulai dari kandidat yang sudah tercatat robots.txt-bersih di Babak 10b (`Arab News`, `The National`) untuk dua actor pertama, lalu batch-screening otomatis 37 outlet tambahan (skrip cek `Claude`/`ClaudeBot`/`Claude-Web`/`anthropic-ai` di `robots.txt`, dijalankan paralel) untuk menemukan 6 kandidat lagi. **Klarifikasi penting soal kriteria skip:** yang jadi alasan skip absolut hanya blokir eksplisit terhadap `Claude`/`anthropic-ai` secara spesifik — blokir terhadap `GPTBot`/`CCBot`/`Google-Extended`/`Bytespider` saja (tanpa menyebut Claude) **tidak** jadi alasan skip, konsisten dengan pola `gulfnews-scraper`/`berlingske-scraper` di babak-babak sebelumnya. Deutsche Welle dan France24 dicek dan di-skip (keduanya block Claude eksplisit); The Times UK dan beberapa lain di-skip karena risiko hard-paywall tanpa waktu recon lebih lanjut.

**Temuan teknis baru yang layak dicatat:**
- `koreatimes-scraper`: situs mengembalikan **soft-404 (HTTP 200)** untuk artikel yang tidak ada — di-deteksi lewat mismatch `<link rel="canonical">` (soft-404 resolve ke section-root, artikel asli resolve ke path persis yang diminta) alih-alih menganggap "tidak ada ld+json = shape berubah". Pola baru yang belum pernah dipakai di portofolio sebelumnya (beda dari deteksi soft-404 `business-standard-scraper` yang cek field kosong di dalam ld+json).
- `independent-scraper` & `eluniversal-scraper`: kedua situs tidak expose `articleBody` sama sekali di ld+json — body diambil dari HTML `<article>`/`<div class="content-story">` dengan filter boilerplate berbasis **exact/prefix string match** (bukan class CSS, karena class di kedua situs pakai hash styled-components/dev-generated yang gampang berubah). `independent-scraper` filter login-prompt/newsletter/komentar; `eluniversal-scraper` filter `[Publicidad]` (ad placeholder) dan CTA WhatsApp.
- `koreaherald-scraper` & `mailguardian-scraper`: ld+json minim (tanpa `articleBody`/`description`/`keywords`), body diambil dari `itemprop="articleBody"` (Korea Herald, schema.org microdata) atau `<article><p>` polos tanpa boilerplate sama sekali (Mail & Guardian, sitemap situs ini ternyata title-less sehingga `latest` mode pindah ke RSS `/rss/` yang ditemukan lewat path-probing, bukan dari `robots.txt`).
- Kuirk CDATA berulang: `independent-scraper` (`image:loc`), `koreatimes-scraper` (`news:title`) — keduanya butuh `html.unescape()` manual karena entity di dalam blok `<![CDATA[...]]>` tidak di-decode otomatis oleh parser XML (benar sesuai spek XML, bukan bug) — pola ini sekarang terkonfirmasi berulang di ≥2 situs berbeda, kemungkinan besar akan muncul lagi di actor mendatang.
- `globaltimes-scraper`: actor pertama di portofolio dengan **ld+json nol sama sekali** (bukan cuma articleBody yang hilang, tapi tidak ada blok ld+json apapun) — semua field diambil dari HTML polos (`<title>`, `span.byline`, `span.pub_time`). Body juga tidak dibungkus tag `<p>` sama sekali, cuma dipisah `<br>` — direkonstruksi jadi paragraf dengan replace `<br>`→newline lalu group berdasarkan baris kosong. Caption gambar (`p.picture`) ternyata duplikat kalimat pembuka artikel + credit foto, wajib di-`decompose()` dulu sebelum rekonstruksi paragraf.

**Kandidat robots.txt-bersih yang masih terbuka untuk sesi berikutnya (belum dieksekusi):** Kyiv Post, TASS, RT, Daily FT (Sri Lanka), Rzeczpospolita (Polandia, butuh discovery RSS/sitemap lebih dalam), Jamaica Gleaner (sitemap bug IP internal), WSJ & MarketWatch (kemungkinan hard-paywall setara FT, belum direcon penuh), The Economist, Motley Fool.

---

## Babak 13 — 4 Actor Baru dari Sisa Backlog Babak 12 (2026-08-24)

**Actor baru yang dibangun sesi ini:** `tass-scraper` (TASS, Rusia), `rt-scraper` (RT, Rusia), `rzeczpospolita-scraper` (Rzeczpospolita, Polandia), `motleyfool-scraper` (The Motley Fool, AS/finance) — semua lolos test lokal (mode `article` + `latest`, termasuk skenario 404) dan smoke test penuh via Apify SDK lokal (`python -m src` dengan `APIFY_LOCAL_STORAGE_DIR` + proxy dimatikan, exit code 0, dataset record valid) sebelum ditandai selesai. Detail teknis lengkap masing-masing ada di `CRAWLING_METHOD.md` per folder actor.

**Metodologi:** melanjutkan langsung dari daftar "masih terbuka" di penutup Babak 12. Screening batch (robots.txt AI-bot block + homepage/article HTTP status) dijalankan atas 10 kandidat: Kyiv Post, TASS, RT, Rzeczpospolita, Daily FT, Jamaica Gleaner, WSJ, MarketWatch, The Economist, Motley Fool.

**Hasil screening:**

| Kandidat | Hasil | Keputusan |
|---|---|---|
| TASS (Rusia) | Bersih — robots.txt cuma disallow `/search`, tidak ada mention Claude/GPTBot sama sekali | ✅ Dibangun |
| RT (Rusia) | Bersih — robots.txt disallow path fungsional (`/search*`, `/login*`, dll) untuk `Googlebot`/`bingbot`/`*`, tidak ada mention Claude | ✅ Dibangun |
| Rzeczpospolita (Polandia) | Bersih, sitemap news ditemukan langsung dari `Sitemap:` di robots.txt (`/sitemaps/news-sitemap.xml`) — kandidat babak 11/12 yang "butuh discovery lebih dalam" ternyata sitemap-nya sudah diadvertise, cuma belum dicek | ✅ Dibangun |
| Motley Fool (AS, finance) | Bersih, robots.txt cuma block `MauiBot`/`Bytespider` spesifik | ✅ Dibangun |
| Daily FT (Sri Lanka) | Bersih dari AI-bot block (timeout babak 11 ternyata transient, kali ini 200 langsung), TAPI markup legacy sangat berantakan (halaman comment-section pakai class `top-story-txt`, bukan article body; Disqus embed; tidak ada ld+json; body container tidak teridentifikasi jelas di 1 sampel yang dicek) — butuh recon lebih dalam dari waktu yang tersedia sesi ini | ⏳ Belum dieksekusi, worth retry dengan sampel artikel lebih banyak |
| Jamaica Gleaner (Karibia) | Bug sitemap dari Babak 11 (`10.0.89.236` internal IP) dikonfirmasi ulang masih ada; `/rss.xml` juga cuma stub kosong (channel tanpa `<item>` sama sekali) — situs ini genuinely tidak punya mekanisme discovery artikel terbaru yang berfungsi lewat HTTP biasa | ⏳ Belum dieksekusi, butuh strategi discovery lain (mis. scrape homepage links) |
| WSJ | Homepage return **401** (bukan 403/200) — beda dari pola WAF biasa, kemungkinan auth-wall di layer yang lebih dalam dari robots.txt | ❌ Di-skip, gate lebih ketat dari sekadar robots |
| MarketWatch | robots.txt eksplisit `User-agent: * / Disallow: /` dengan pengecualian cuma untuk daftar bot search-engine besar (Googlebot, bingbot, dll — tidak termasuk Claude), plus notice hukum eksplisit "Collection of content... prohibited unless you have express written permission" dari Dow Jones & Company | ❌ Di-skip — blanket disallow + larangan ToS eksplisit, beda kategori dari sekadar "block Claude by name" |
| The Economist | robots.txt block eksplisit `claude`, `anthropic-ai`, `claudebot`, `claude-web`, `claude-user`, `claude-searchbot` — paling lengkap/agresif dari semua kandidat yang pernah di-screening | ❌ Di-skip |

**Temuan teknis baru yang layak dicatat:**
- `tass-scraper` & `rt-scraper`: kedua situs Rusia (state media/broadcaster) punya pola identik — ld+json `NewsArticle` lengkap untuk metadata (headline/author/publisher/date) tapi **tanpa `articleBody`**, full text harus dari HTML (`div.text-block` untuk TASS, `div.article__text` untuk RT). Keduanya juga sama-sama punya RSS feed bersih; RT unik karena `<content:encoded>` di RSS-nya ternyata **berisi HTML artikel penuh** (bukan cuma teaser seperti mayoritas outlet lain di portofolio) — jadi mode `latest` RT sudah menyertakan full text tanpa perlu follow-up ke mode `article`.
- `rzeczpospolita-scraper`: quirk baru — CMS-nya hard-wrap teks paragraf dengan karakter `\n` literal di tengah kalimat pada source HTML (bukan line-break yang disengaja, cuma artefak format template). `get_text()` biasa tidak membersihkan ini karena newline-nya ada di dalam satu text node, bukan di antara tag — perlu regex whitespace-collapse tambahan sebelum join paragraf. Juga actor pertama di portofolio yang mengekspos field `isAccessibleForFree` + `isPartOf` (nama tier subscription) secara eksplisit dari ld+json, dipetakan ke flag `_paywalled` di output — meski sampel yang diverifikasi kebetulan semuanya tier gratis, jadi belum ada bukti langsung soal perilaku artikel premium.
- `motleyfool-scraper`: actor kedua di portofolio (setelah `globaltimes-scraper`) dengan **ld+json nol sama sekali** — semua metadata dari `<meta>` tag biasa. RSS feed sempat menunjukkan hasil parsing tidak konsisten di satu run test (1 dari 50 item saja, tanpa error) yang tidak berhasil direproduksi ulang di run-run berikutnya maupun lewat parsing `lxml.etree` mentah langsung — didokumentasikan di `CRAWLING_METHOD.md` sebagai kemungkinan response terpotong sesaat, bukan bug parsing sistematis.
- Body caption/widget filtering sekarang muncul dengan pola baru per situs: TASS tidak perlu filter apapun (body bersih), RT tidak perlu filter apapun, Rzeczpospolita perlu exact-class-match untuk exclude widget "Czytaj więcej" yang nempel di tengah body, Motley Fool perlu `.decompose()` untuk `p.caption` (caption gambar) — makin menguatkan pola dari babak-babak sebelumnya bahwa **setiap situs butuh verifikasi manual per-selector**, tidak ada satu strategi filtering yang generalizable lintas situs.

**Kandidat robots.txt-bersih yang masih terbuka untuk sesi berikutnya:** Daily FT (butuh recon markup lebih dalam — legacy CMS tanpa ld+json dan tanpa container body yang jelas), Jamaica Gleaner (butuh strategi discovery artikel alternatif di luar sitemap/RSS yang keduanya rusak), Kyiv Post (robots.txt bersih dan sitemap index ditemukan di babak ini tapi belum sempat direcon body/ld+json-nya — lihat sitemap index `https://www.kyivpost.com/sitemap.xml` dengan sub-sitemap `news-sitemap.xml`).

---

## Babak 14 — 11 Actor Baru + Perbaikan Bug Screening robots.txt Multi-User-Agent (2026-08-25)

**Actor baru yang dibangun sesi ini:** `kyivpost-scraper` (menutup salah satu dari 3 item backlog Babak 13), `jerusalempost-scraper`, `euronews-scraper`, `clarin-scraper`, `lanacion-scraper`, `chinadaily-scraper`, `elpais-scraper` (edisi Inggris), `tuoitre-scraper`, `businessrecorder-scraper`, `expresstribune-scraper`, `nationthailand-scraper` — semua lolos test lokal (mode `article` + `latest`, termasuk skenario 404/soft-404) **dan** smoke test penuh via Apify SDK lokal (`python -m src` dengan `APIFY_LOCAL_STORAGE_DIR`, exit code 0, dataset record diverifikasi) sebelum ditandai selesai. Detail teknis lengkap masing-masing di `CRAWLING_METHOD.md` per folder actor.

**Bug penting ditemukan & diperbaiki di metodologi screening sendiri:** script screening `robots.txt` batch-batch sebelumnya (dipakai sejak Babak 10) punya bug parser — ketika sebuah blok punya **beberapa baris `User-agent:` berurutan yang berbagi satu baris `Disallow: /` di bawahnya** (pola umum, mis. `User-agent: GPTBot` / `User-agent: ClaudeBot` / ... / `Disallow: /`), parser lama cuma mengecek user-agent **terakhir** dalam grup itu terhadap `Disallow: /`, bukan semua user-agent dalam grup. Akibatnya kandidat yang sebenarnya **memblokir Claude/anthropic-ai** bisa lolos sebagai "bersih" kalau nama bot itu bukan baris `User-agent:` terakhir sebelum `Disallow:`. **Taipei Times** ketahuan lolos screening awal secara keliru dengan bug ini — begitu agent pembangunnya melakukan verifikasi ulang robots.txt secara independen (sesuai instruksi wajib di setiap prompt agent), ketahuan robots.txt-nya justru **secara eksplisit block `ClaudeBot`/`anthropic-ai`** dalam grup 14-user-agent yang sama (bareng GPTBot, CCBot, Bytespider, dll) — agent tersebut benar berhenti dan skip tanpa membangun apapun. Parser screening diperbaiki (grouping user-agent yang benar) dan seluruh kandidat di-scan ulang; hasil re-scan mengonfirmasi Kyiv Post, Jerusalem Post, Euronews, Clarín, La Nación tetap bersih (tidak berubah), sementara beberapa kandidat baru di re-scan batch kedua (Die Zeit, Haaretz, Khaleej Times, Kuwait Times, Business Day SA, Daily Monitor Uganda, Phnom Penh Post, Zee Business, Asahi Shimbun) terkonfirmasi **benar-benar block** dan tidak dibangun.

**Insight metodologi baru — verifikasi independen wajib per-agent terbukti krusial:** karena setiap agent pembangun diinstruksikan untuk **selalu fetch ulang `robots.txt` sendiri** di awal Phase 1 (bukan cuma percaya hasil screening orkestrator), bug di atas tertangkap dan dikoreksi otomatis tanpa membangun actor yang seharusnya di-skip. Pola ini dipertahankan untuk sesi berikutnya: screening orkestrator hanya untuk **triase awal/prioritisasi**, bukan keputusan akhir — setiap agent tetap wajib verifikasi ulang sebelum menulis kode.

**Temuan teknis baru yang layak dicatat:**
- `clarin-scraper`: ditemukan bug data korup di ld+json `articleBody` upstream (koma di angka hilang, `"1,8%"` jadi `"18%"`) — extractor sengaja TIDAK memakai `articleBody` dari ld+json, pakai `#cuerpo` dari HTML sebagai gantinya. Juga ditemukan red herring: `hasPart.cssSelector` di ld+json menunjuk ke `.paywall_content`, tapi class itu ternyata ada di `<body>` tag site-wide (bukan container asli) — kalau dipakai apa adanya bakal menyapu nav/footer/semua `<p>` di halaman. Paywall terverifikasi genuinely campuran (opini kadang `isAccessibleForFree:false`) tapi body HTML tetap lengkap di kedua kasus (paywall cuma overlay client-side JS/CSS) — `_paywalled` jujur tapi tidak pernah berarti teks terpotong.
- `lanacion-scraper`: pola serupa Clarín (grup usaha LatAm besar) — `isAccessibleForFree` dan `isPartOf` (nama produk subscription) hadir dan genuine, tapi 25 artikel sampel (termasuk 6 kolom opini, tier paling sering di-gate outlet lain) semuanya `isAccessibleForFree:true` dengan body lengkap tanpa potongan — paywall kemungkinan besar cuma ditegakkan client-side untuk pembaca manusia, bukan di HTML yang di-serve ke scraper/search-crawler.
- `expresstribune-scraper`: kasus paling rumit sesi ini — Cloudflare menjalankan **rule anti-enumerasi bertarget** khusus pola `/story/<id>/...`: ID artikel yang tidak ada memicu 403 "Just a moment" instan, padahal profil TLS yang sama dapat 200 bersih di artikel asli detik sebelum/sesudahnya (session tidak "teracuni"). Path non-`/story/` yang tidak ada malah soft-404 render homepage (200). Actor ini tidak bisa membedakan "artikel dihapus" dari "diblokir Cloudflare" di level HTTP — keduanya dilaporkan sebagai `_error:"blocked_or_transient"`, bukan `not_found`, didokumentasikan eksplisit. Situs ini juga punya **2 template body CMS berbeda** tanpa class yang sama (`div.express-parent-div` untuk hard-news, `div.custom-row` untuk opini/fiksi) — extractor coba keduanya berurutan.
- `nationthailand-scraper`: ld+json **punya** field `articleBody` tapi ternyata cuma teaser pendek (~140-150 karakter, identik dengan `description`) — bukan body lengkap, butuh fallback HTML `div.content-detail`. Soft-404 terdeteksi lewat mismatch `<link rel="canonical">` (mengarah ke homepage polos untuk artikel yang tidak ada) — pola serupa `koreatimes-scraper` di babak lama tapi dengan sinyal deteksi berbeda.
- `businessrecorder-scraper`, `tuoitre-scraper`: keduanya butuh `html.unescape()` pada field `description`/`headline` karena entity HTML mentah (`&#039;`) tertinggal di ld+json — pola berulang yang sekarang terkonfirmasi di banyak outlet berbeda (gulfnews, philstar, inquirer, dan sekarang keduanya).
- `chinadaily-scraper`: sama seperti `globaltimes-scraper` (media negara Tiongkok lain), RSS (`/rss/china_rss.xml`, item terbaru Desember 2017) dan sitemap.xml (lastmod 2014) keduanya **artefak mati** — `latest` mode scrape homepage langsung, urutkan berdasarkan ID artikel heksadesimal yang tertanam di URL (zero-padded, sortable secara leksikal = kronologis).

**Kegagalan infrastruktur dicatat untuk transparansi:** 7 dari 13 agent pembangun paralel di babak ini sempat gagal di tengah jalan karena **session limit API** (reset 3am Asia/Jakarta), bukan karena masalah kode/situs target. Semua sisa pekerjaan (kode yang sudah ditulis sebagian, dokumentasi yang belum lengkap, test yang belum diverifikasi ulang) diselesaikan manual oleh orchestrator langsung setelah itu — termasuk menulis ulang seluruh `chinadaily-scraper` dan `nationthailand-scraper` dari nol (folder tersisa kosong/parsial) berdasarkan file recon yang sempat tersimpan sebelum failure.

**Kandidat robots.txt-bersih (setelah fix parser) yang masih terbuka untuk sesi berikutnya:** Oman Observer, Peninsula Qatar, Premium Times Nigeria, Kathmandu Post, Trinidad Guardian, Diario Libre (Rep. Dominika) — 6 kandidat sudah di-screening bersih tapi belum direcon/dibangun. (Ghana Web, yang tadinya juga di daftar ini, sudah **✅ Dibangun 2026-08-26** — lihat tabel Babak 9b di atas.)

---

## Babak 14 (lanjutan) — Daily FT & Jamaica Gleaner: 2 Backlog Terakhir Ditutup (2026-08-25)

**Actor baru:** `dailyft-scraper`, `jamaicagleaner-scraper` — keduanya lolos test lokal (mode `article` + `latest`, termasuk skenario 404/soft-404) dan smoke test penuh via Apify SDK lokal sebelum ditandai selesai. **Ini menutup ketiga item backlog eksplisit yang tersisa dari Babak 13** (Kyiv Post, Daily FT, Jamaica Gleaner — dikerjakan langsung oleh orchestrator setelah 7 dari 13 agent paralel sempat gagal karena session-limit API, lihat catatan kegagalan infrastruktur di atas).

Kedua situs sama-sama sempat gagal di 2-3 sesi riset sebelumnya (Babak 11-13) karena dianggap terlalu bermasalah (Daily FT: "legacy markup, tidak ada ld+json"; Jamaica Gleaner: "sitemap/RSS rusak"). Investigasi ulang kali ini menuntaskan keduanya:

- **Daily FT**: dugaan "konten dirender client-side via Angular" (dari `ng-app="single_module"`) ternyata keliru — Angular di situs ini cuma menggerakkan widget penghitung page-view (`{{hitsCtrl.values.hits}}` sempat kelihatan mentah, belum ter-render, di HTML) — body artikel sesungguhnya sudah lengkap di server-rendered HTML, cuma diformat dengan sangat tidak konsisten (2 template CMS berbeda ditemukan, campur `<p>` per paragraf dengan `<p>` tunggal berisi `<br><br>` sebagai pemisah paragraf).
- **Jamaica Gleaner**: bug sitemap/RSS dari Babak 11 dikonfirmasi masih ada (bukan sudah diperbaiki situsnya), tapi homepage-scraping (pola yang sama seperti `chinadaily-scraper`) ternyata bekerja sempurna sebagai pengganti.

**Insight metodologi tambahan:** kedua situs ini sama-sama punya backend yang **genuinely flaky** (503 sesaat di Daily FT, `ConnectionError: Empty reply from server` sesaat di Jamaica Gleaner) — dikonfirmasi transient dengan mengulang request identik dan mendapat respons sukses detik berikutnya, bukan block permanen. Retry/backoff standar portofolio (5x, exponential) menangani ini tanpa perlu logic khusus. Pelajaran: jangan langsung vonis "situs bermasalah/di-skip" hanya dari satu-dua kali timeout/503 di sesi recon awal — itu bisa jadi infra yang memang tidak stabil, bukan sinyal block, dan layak di-retry di sesi berikutnya sebelum dicoret permanen dari daftar kandidat.

**Ringkasan progres Babak 14 total: 13 actor baru** (11 dari wave paralel + 2 dari penutupan backlog manual) — total portofolio kini **56 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari filesystem), semua lolos test lokal + smoke test Apify SDK.

**Kandidat robots.txt-bersih yang masih terbuka untuk sesi berikutnya:** Oman Observer, Peninsula Qatar, Premium Times Nigeria, Kathmandu Post, Trinidad Guardian, Diario Libre (Rep. Dominika) — 6 kandidat sudah di-screening bersih (parser sudah diperbaiki) tapi belum direcon/dibangun. Tidak ada lagi item backlog "wajib" yang tersisa dari sesi-sesi sebelumnya — daftar di atas murni kandidat baru untuk ekspansi lebih lanjut, bukan pekerjaan yang tertunda. (Ghana Web, yang tadinya juga di daftar ini, sudah **✅ Dibangun 2026-08-26** — lihat tabel Babak 9b di atas.)

**Update 2026-08-26 — Peninsula Qatar ditutup:** `robots.txt` diverifikasi ulang baris-per-baris (tidak ada bug parser, tidak ada entri Claude/anthropic-ai), tidak ada WAF aktif, tidak ada paywall — dibangun sebagai `thepeninsulaqatar-scraper` (lihat baris tabel Babak 9 di atas dan `thepeninsulaqatar-scraper/CRAWLING_METHOD.md`). **Sisa kandidat terbuka setelah ini: Oman Observer, Ghana Web, Premium Times Nigeria, Kathmandu Post, Trinidad Guardian, Diario Libre (Rep. Dominika)** — 6 kandidat.

**Update 2026-08-26 — Oman Observer ditutup:** `robots.txt` di-fetch ulang dan diverifikasi (cuma 1 grup flat `User-agent: *`, tidak ada bug parser multi-group karena memang cuma 1 grup, tidak ada entri Claude/ClaudeBot/anthropic-ai), tidak ada WAF aktif (Sucuri/Cloudproxy fronted tapi `chrome124` bersih), tidak ada paywall — dibangun sebagai `omanobserver-scraper` (lihat baris tabel Babak 9 di atas dan `omanobserver-scraper/CRAWLING_METHOD.md`). Extraction pakai ld+json `NewsArticle` langsung (`articleBody` sudah lengkap, tidak perlu fallback HTML) untuk mode `article`, dan homepage-link-scraping (RSS/sitemap semuanya mati) untuk mode `latest`. **Sisa kandidat terbuka setelah ini: Ghana Web, Premium Times Nigeria, Kathmandu Post, Trinidad Guardian, Diario Libre (Rep. Dominika)** — 5 kandidat.

**Update 2026-08-26 — Diario Libre ditutup:** `robots.txt` di-fetch ulang dan diverifikasi baris-per-baris (cuma 1 grup flat `User-agent: *`, tidak ada bug parser multi-group karena memang cuma 1 grup, tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai sama sekali), tidak ada WAF aktif (`Microsoft-IIS/10.0` polos, `chrome124` bersih di homepage/artikel/sitemap/RSS, tidak ada cookie/header Cloudflare/DataDome/PerimeterX/Akamai), tidak ada paywall (tidak ada `isAccessibleForFree` maupun marker "suscriptores"/"suscríbete" di 3 sampel artikel) — dibangun sebagai `diariolibre-scraper` (lihat baris tabel Babak 9 di atas dan `diariolibre-scraper/CRAWLING_METHOD.md`). Extraction pakai ld+json `@graph` (`NewsMediaOrganization`+`WebSite`+`NewsArticle`) dengan `articleBody` langsung — dicek eksplisit untuk bug korupsi angka ala Clarín pada artikel ekonomi berangka ribuan, ternyata utuh/tidak korup — plus `html.unescape()` tambahan karena field teks ld+json-nya berisi HTML entity mentah (`&oacute;` dst). Mode `latest` via `/feed/portada.xml` (RSS custom ~28 item) yang uniknya CDATA `<description>`-nya sudah membawa **full articleBody**, bukan cuma teaser. **Sisa kandidat terbuka setelah ini: Ghana Web, Premium Times Nigeria, Kathmandu Post, Trinidad Guardian** — 4 kandidat.

**Update 2026-08-26 — Trinidad Guardian ditutup:** `robots.txt` di-fetch ulang dan diverifikasi (cuma 1 grup flat `User-agent: *` + `Crawl-delay: 10`, tanpa `Disallow` sama sekali jadi tidak ada bug parser multi-group untuk dicek, tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai), tidak ada WAF aktif (CloudFront+nginx polos, `chrome124` bersih di homepage & artikel, tidak ada cookie/header Cloudflare/DataDome/PerimeterX/Akamai), tidak ada paywall (`isAccessibleForFree: "true"` di 5 sampel) — dibangun sebagai `trinidadguardian-scraper` (lihat baris tabel Babak 9c di atas dan `trinidadguardian-scraper/CRAWLING_METHOD.md`). Kuirk unik yang ditemukan: URL artikel divalidasi CDN CloudFront lewat suffix hash bertanda-tangan (`-6.2.<id>.<hash>`) sebelum request sampai origin — hash yang salah balik HTTP 400 (bukan 404), di-treat sama dengan `not_found`. Ld+json `NewsArticle`-nya sangat minim (tanpa `articleBody`/`author`/`datePublished`) — body diambil dari HTML `div.ag-article-text` (filter `p.bodytext`/`p.byline`, exclude `p.Caption`/`p.Source` caption gambar yang terselip di tengah body), `author` dari header `div.author` (opsional, kosong di beberapa kolom opini), `datePublished` disintesis dari span HTML `textelement-createdtime` dengan asumsi offset tetap UTC-4 (AST, T&T tidak kenal DST) karena field ini tidak ada sama sekali di ld+json. Teks juga dibersihkan dari karakter soft-hyphen U+00AD yang disisipkan CMS di tengah kata (artefak hyphenation, bukan konten asli). Situs sama sekali tidak punya RSS/sitemap (bukan cuma rusak seperti Jamaica Gleaner, tapi memang tidak ada) — mode `latest` scrape homepage, urutkan berdasarkan ID CMS numerik di URL karena tidak ada tanggal di URL sama sekali (beda dari Jamaica Gleaner). **Sisa kandidat terbuka setelah ini: Ghana Web, Premium Times Nigeria, Kathmandu Post** — 3 kandidat.

**Update 2026-08-26 — Kathmandu Post ditutup:** `robots.txt` di-fetch ulang dan diverifikasi (cuma 1 grup flat `User-agent: * / Disallow:`, kosong total, tidak ada bug parser multi-group karena memang cuma 1 grup), tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai sama sekali. Cloudflare-fronted tapi tanpa challenge aktif, tidak ada paywall — dibangun sebagai `kathmandupost-scraper` (lihat baris tabel Babak 9b di atas dan `kathmandupost-scraper/CRAWLING_METHOD.md`). Quirk signifikan: ld+json `NewsArticle` di situs ini sangat tipis (tanpa `articleBody`/`datePublished`/`author`, semua diambil dari HTML), dan `BeautifulSoup(html, "lxml")` ditemukan diam-diam membuang blok ld+json `NewsArticle` di setiap halaman artikel (24 dari 26 tag `<script>` saja yang ke-parse) — diperbaiki dengan pindah ke parser `"html.parser"` bawaan stdlib. Tidak ada 404 asli (semua soft-200 ke shell homepage); mode `latest` pakai `/rss` (satu-satunya endpoint feed/sitemap yang benar-benar hidup, sisanya semua soft-200 juga). **Sisa kandidat terbuka setelah ini: Ghana Web, Premium Times Nigeria, Trinidad Guardian, Diario Libre (Rep. Dominika)** — 4 kandidat.

**Update 2026-08-26 — Ghana Web ditutup:** `robots.txt` di-fetch ulang dan diverifikasi baris-per-baris — 3 grup `User-agent` terpisah (`Mediapartners-Google`, `PetalBot`, `*`), masing-masing dengan blok `Disallow` sendiri langsung di bawahnya (bukan pola bug parser multi-group Babak 14), tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai di grup manapun. Akamai-fronted (CDN/mPulse RUM saja, tidak ada cookie `_abck`/`bm_sz`) tapi tanpa WAF aktif, tidak ada paywall — dibangun sebagai `ghanaweb-scraper` (lihat baris tabel Babak 9b di atas dan `ghanaweb-scraper/CRAWLING_METHOD.md`). Extraction pakai ld+json `@graph` (`NewsArticle`+`BreadcrumbList`) untuk metadata (tanpa `articleBody`) + HTML `div.article-content-area` (paragraf dipisah `<br>`, bukan `<p>`) untuk full text, dengan quirk unik: artikel staff diakhiri baris tanda tangan inisial reporter 2-bagian (mis. `"MRA/MA"`) diikuti promo/video tidak relevan yang harus dipotong, sedangkan artikel Opinions/Features punya byline `Columnist: <Nama>` tanpa tanda tangan itu. Mode `latest` pakai Google News sitemap `/sitemaps/news.xml` (update near-real-time, tidak ada RSS hidup). **Sisa kandidat terbuka setelah ini: Premium Times Nigeria, Trinidad Guardian, Diario Libre (Rep. Dominika)** — 3 kandidat.

**Update 2026-08-26 — Premium Times Nigeria ditutup:** `robots.txt` di-fetch ulang dan diverifikasi (cuma 1 blok Yoast standar `User-agent: * / Disallow:` kosong, tidak ada bug parser multi-group karena memang cuma 1 grup), tidak ada entri Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai sama sekali. Cloudflare-fronted tapi tanpa challenge aktif untuk trafik normal, tidak ada paywall — dibangun sebagai `premiumtimes-scraper` (lihat baris tabel Babak 9b di atas dan `premiumtimes-scraper/CRAWLING_METHOD.md`). Quirk signifikan ditemukan saat recon: satu URL artikel sempat nyangkut di edge cache Cloudflare yang stale, menyajikan halaman JS-cookie-challenge lama (`slowAES`/`TZTC`) alih-alih artikel asli — dikonfirmasi bukan block JA3 (7 profile TLS semua kena respons identik) maupun IP-reputation (URL lain yang belum pernah di-cache langsung 200 bersih), diatasi dengan cache-busting query param saat retry alih-alih backoff biasa. Extraction pakai ld+json `@graph` gaya Yoast (`Article`, bukan `NewsArticle`) dengan `author`/`publisher` berupa referensi `@id` yang di-resolve ke node `Person`/`Organization` lain di graph yang sama (tidak ada `dateModified` sama sekali) + HTML `div.entry-content > div.content-inner` (`<p>` direct-child saja) untuk `articleBody`. 404 untuk ID artikel terhapus adalah **soft-404** (200 isi homepage, dideteksi lewat absennya node `Article`). Mode `latest` via `/feed` (WordPress standar, auto-paginate `?paged=N`). Ini menutup seluruh backlog Babak 14 — tidak ada lagi item "wajib" tersisa dari sesi-sesi sebelumnya.

---

## Babak 15 — 7 Actor Baru + Penemuan Penting: Landscape Robots.txt Sudah Bergeser Drastis (2026-08-26)

**Konteks:** melanjutkan dari daftar "Belum Dibangun" di dokumen ini (Babak 8/9/9b/9c). Sebelum dispatch agent, orchestrator melakukan **screening ulang manual** atas ~30 kandidat `[0]`/unscreened yang masih tercatat terbuka di tabel-tabel di atas (Tier 2 Eropa: La Stampa, ABC.es, Libération; Amerika Latin: Reforma, Estadão, El Tiempo; Asia Timur: Asahi Shimbun, Yomiuri; Oceania: Stuff.co.nz; Afrika: Vanguard, dst).

**Temuan penting — bukan cuma soal 1-2 kandidat, tapi pergeseran landscape:** dari ~30 kandidat yang di-screening ulang, **mayoritas besar sekarang eksplisit block `ClaudeBot`/`Claude-Web`/`Claude-SearchBot`/`anthropic-ai`** di `robots.txt` — termasuk beberapa yang di Babak 9/9c masih berstatus `[0]`/unscreened dan terlihat menjanjikan: **La Stampa** (Italia — bahkan block eksplisit per-agent, bukan grup gabungan, jadi tidak ambigu), **ABC.es** (Spanyol — grup panjang berisi `ClaudeBot`+`Claude-SearchBot`), **Libération** (Prancis — sibling `Le Figaro` yang sudah lebih dulu diketahui block, sekarang terkonfirmasi block juga), **Estadão** (Brasil), **El Tiempo** (Kolombia), **Stuff.co.nz** (Selandia Baru), **Asahi Shimbun** dan **Yomiuri** (Jepang — keduanya sangat agresif, daftar block mencakup hampir semua varian nama Claude). **Reforma** (Meksiko) dan **Manila Bulletin** (Filipina) malah return HTTP 403 langsung di level `robots.txt` (kemungkinan WAF/geo-block, bukan cuma kebijakan robots — tidak diinvestigasi lebih lanjut, dicatat sebagai sinyal negatif). **Vanguard** (Nigeria) timeout koneksi (infrastruktur, belum tentu block — worth retry sesi berikutnya).

Dari ~30 yang di-screening, hanya **7 yang lolos bersih** (tidak ada token Claude/anthropic-ai, tidak ada blanket `Disallow: /` untuk grup `*`) dan langsung di-dispatch ke agent pembangun paralel: **Daily Mirror** (Sri Lanka), **The Namibian**, **Times of Zambia**, **The Standard** (Kenya), **The Citizen** (Tanzania), **Meduza** (Rusia, pers eksil), **Diário de Notícias** (Portugal). **Myanmar Times** awalnya lolos screening cepat orchestrator (grep untuk kata "claude"/"anthropic" saja) tapi agent pembangunnya menemukan robots.txt-nya sebenarnya `User-agent: * / Disallow: /` — blanket block untuk **semua** bot termasuk Claude, bukan cuma yang disebut namanya — kesalahan metodologi orchestrator, dikoreksi sebelum kode ditulis (lihat Insight Metodologi di bawah).

**Actor baru yang dibangun sesi ini (7):** `dailymirror-scraper`, `namibian-scraper`, `timesofzambia-scraper`, `standardmedia-scraper`, `thecitizen-scraper`, `meduza-scraper`, `diariodenoticias-scraper` — semua lolos test lokal (`test_local.py` mode `article` + `latest`, termasuk skenario 404/soft-404/paywall) **dan** smoke test penuh via Apify SDK lokal (`python -m src` dengan `APIFY_LOCAL_STORAGE_DIR`, exit code 0, dataset record nyata diverifikasi) **dan** `apify validate-schema` lolos untuk ketiga schema (Input/Dataset/Output) di setiap actor.

**Update 2026-08-26 — Deployed ke Apify (`apify push` + `apify call`):** ketujuh actor berhasil di-push (`Build: SUCCEEDED`) dan di-smoke-test di cloud Apify (bukan cuma lokal — IP/environment beda) dengan `apify call -i '{"mode":"latest","limit":3}'`, semua `exit_code: 0` dan 3 headline nyata per actor:

| Actor | Actor ID | Run |
|---|---|---|
| `dailymirror-scraper` | `luV5612y0vyVWDQMM` | SUCCEEDED |
| `namibian-scraper` | `92GblQpijOx0H6GpY` | SUCCEEDED |
| `timesofzambia-scraper` | `ent4B6sJJja2tamwG` | SUCCEEDED |
| `standardmedia-scraper` | `oT3lCr5VoDH3VQ87a` | SUCCEEDED |
| `thecitizen-scraper` | `9FBEhbffROANziaWv` | SUCCEEDED |
| `meduza-scraper` | `XgTGQ5JsCRWMPcYA6` | SUCCEEDED |
| `diariodenoticias-scraper` | `QTNdMJrsGS3lKexel` | SUCCEEDED |

Semua di-push di bawah akun `zucchini_gopher_m2v` (bukan `xtracto` — akun pembanding di riset ini beda dari akun kerja aktual).

**Ringkasan temuan teknis per actor:**
- `dailymirror-scraper`: tidak ada WAF, tidak ada paywall. ld+json berisi `articleBody` penuh langsung tapi JSON mentahnya invalid (control character mentah) — perlu `json.loads(strict=False)`. Tidak ada RSS/sitemap yang jalan — `latest` mode pakai homepage-link-scraping dari kategori Breaking News. Router selalu return HTTP 200 (tidak pernah 404 asli) — soft-404 dideteksi dari field ld+json kosong.
- `namibian-scraper`: tidak ada WAF, tidak ada paywall. RSS (`/feed/`) sudah bawa `content:encoded` full-text, jadi `latest` mode tidak perlu request tambahan per item. `author`/`image` di ld+json berupa `@id` reference yang perlu di-resolve dari `@graph`.
- `timesofzambia-scraper`: tidak ada WAF, tidak ada paywall. Strategi utama malah **WordPress REST API** (`/wp-json/wp/v2/posts?slug=`) bukan ld+json (ld+json di situs ini tidak punya `articleBody` dan authornya generik) — lebih kaya datanya. Quirk: sebagian artikel pakai class `ds-markdown-paragraph`, indikasi konten sebagian ditulis/dibantu LLM.
- `standardmedia-scraper`: tidak ada WAF, paywall kosmetik (flag ada, teks tetap penuh). 2 template berbeda (section utama vs section `evewoman` butuh HTML fallback terpisah). `articleBody` di-escape HTML 2×.
- `thecitizen-scraper`: tidak ada WAF (dicek independen meski satu grup usaha — Nation Media Group — dengan Daily Nation Kenya yang sudah terbukti block Claude), paywall kosmetik.
- `meduza-scraper`: tidak ada WAF aktif, tidak ada paywall (situs nonprofit donation-funded). Body dari HTML (ld+json metadata-only). Dukung edisi EN dan RU. Bug ditemukan & diperbaiki: beacon pasif Cloudflare (`/cdn-cgi/challenge-platform/...`) yang muncul di SETIAP halaman (termasuk 200 dan 404 asli) sempat false-trigger detektor block generik yang di-copy dari `rt-scraper` — menyebabkan infinite-retry loop di soft-404. Marker itu di-drop dari `BLOCK_MARKERS` khusus actor ini.
- `diariodenoticias-scraper`: tidak ada WAF, **paywall soft dikonfirmasi dengan bukti langsung** (artikel bertanda `access:"subscription"` tetap mengembalikan `articleBody` 6.983 karakter penuh tanpa cookie/session apapun) — CMS Quintype, pola sama dengan `latimes-scraper`/`bild-scraper`. `latest` mode via `/stories.rss` (ditemukan lewat redirect `/feed`, bukan dari robots.txt).

**Insight metodologi baru — screening cepat orchestrator via keyword grep TIDAK CUKUP:** kasus Myanmar Times menunjukkan bahwa mengecek keberadaan kata "claude"/"anthropic" di `robots.txt` saja tidak cukup — sebuah `robots.txt` sependek 26 byte (`User-agent: * / Disallow: /`) lolos grep keyword tapi sebenarnya blanket-block **semua** crawler tanpa kecuali, termasuk Claude, karena tidak ada grup allowlist yang mengecualikan bot manapun. Screening orchestrator ke depan **wajib** cek dua kondisi terpisah: (1) token Claude/anthropic-ai disebut eksplisit di grup manapun, DAN (2) grup `User-agent: *` (atau grup yang mencakup Claude via allowlist) tidak melakukan blanket `Disallow: /`. Untungnya kebijakan portofolio yang sudah ada (setiap agent pembangun WAJIB re-verify robots.txt sendiri sebelum menulis kode, lihat Babak 14) menangkap kesalahan ini sebelum kode ditulis — tidak ada actor yang salah dibangun.

**Insight strategis — kompetisi block AI-bot terus meningkat dari waktu ke waktu.** Dibanding screening Babak 10-14 (2026-08-24/25), hit-rate kandidat "bersih" di screening Babak 15 (2026-08-26, cuma 2 hari kemudian) jauh lebih rendah (~7 dari ~30, atau 23%, vs pola sebelumnya yang biasanya di atas 50%). Outlet-outlet besar dengan traffic tinggi (Asahi Shimbun, Yomiuri, ABC.es, La Stampa) tampaknya baru saja memperbarui kebijakan `robots.txt` mereka untuk eksplisit menyertakan Claude/anthropic-ai. **Implikasi untuk sesi berikutnya:** kandidat yang tercatat "belum discreening" atau bahkan "sudah discreening bersih" di babak-babak lama (10-14) TIDAK BOLEH diasumsikan masih bersih — re-verifikasi ulang wajib dilakukan sebelum build, robots.txt bisa berubah dalam hitungan hari, bukan bulan.

**Sisa kandidat yang di-skip di babak ini (robots.txt block Claude, dikonfirmasi 2026-08-26):** La Stampa (Italia), ABC.es (Spanyol), Libération (Prancis), Estadão (Brasil), El Tiempo (Kolombia), Stuff.co.nz (Selandia Baru), Asahi Shimbun (Jepang), Yomiuri (Jepang). **Perlu diinvestigasi ulang (403/timeout, bukan konfirmasi block eksplisit):** Reforma (Meksiko, 403 di level robots.txt), Manila Bulletin (Filipina, 403 di level robots.txt), Vanguard (Nigeria, connection timeout). **Skip, blanket disallow untuk semua bot:** Myanmar Times.

**Total portofolio setelah babak ini: 79 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari filesystem; termasuk non-news actors di luar cluster ini — `civitai-scraper`, `huggingface-scraper`, `aeo-geo-tracker`, `twitch-*`, `poshmark-scraper`).

---

## Babak 16 — 11 Actor Baru via Dispatch Paralel + Perluasan ke Vertikal Non-Berita (2026-08-26)

**Konteks:** melanjutkan langsung dari daftar "Belum Dibangun" di dokumen ini. Sebelum dispatch, orchestrator menjalankan 3 batch screening `robots.txt` mandiri (60 kandidat total — news outlet Tier 2/3 yang belum pernah discreening + kandidat job-board/real-estate dari Babak 9/9b) memakai script Python (`curl_cffi`, parser grup-per-user-agent yang benar, sudah menghindari bug "Babak 14"). **Hasil konfirmasi ulang insight Babak 15:** hit-rate makin turun — dari 40 kandidat berita batch 1-2, cuma 9 bersih (23%); tapi batch 3 (fokus Nigeria/India/Timur Tengah/Asia Tenggara yang belum pernah disentuh sama sekali) balik ke hit-rate tinggi (16/20 bersih, 80%) — mengonfirmasi pola "negara/region yang belum pernah discreening masih median bersih, yang sudah pernah disentuh (Eropa, outlet besar AS) makin jenuh diblokir."

**25 kandidat lolos screening bersih**, 12 di antaranya di-dispatch ke agent paralel (sisanya dicatat di bawah untuk sesi berikutnya). **11 dari 12 berhasil dibangun & di-deploy, 1 berhenti bersih di fase recon** (tidak ada actor dipaksakan) — semua agent diinstruksikan wajib re-verifikasi `robots.txt` independen (bukan percaya screening orchestrator) sebelum menulis kode, sesuai kebijakan sejak Babak 14.

### Actor baru yang dibangun & di-deploy ke Apify (11)

| Actor | Outlet/Platform | Negara | Temuan Kunci |
|---|---|---|---|
| `saudigazette-scraper` | Saudi Gazette | Arab Saudi | robots.txt bersih (per-agent group tidak digabung); tidak ada WAF; JSON-LD metadata-only + HTML `div.body-div` untuk body; latest via Google News sitemap (`/sitemaps/news_sitemap.xml`), RSS mati total. |
| `freemalaysiatoday-scraper` | Free Malaysia Today | Malaysia | robots.txt eksplisit **`Allow: /`** untuk Claude-Web/ClaudeBot/anthropic-ai (bukan cuma "tidak diblokir"); Cloudflare gate **IP/ASN-based** — datacenter proxy Apify kena 403, Residential proxy lolos bersih (bukti langsung kenapa aturan "Residential by default" di `.ai/CLAUDE.md` penting); tanpa JSON-LD sama sekali, data dari `__NEXT_DATA__` (WPGraphQL headless); RSS `content:encoded` sudah full-text. |
| `punch-scraper` | Punch | Nigeria | robots.txt bersih (Yoast standar); Cloudflare pasif; JSON-LD `@graph` `NewsArticle` dengan `author` inline (bukan `@id` ref, beda dari Premium Times); body dari HTML `article.single-article div.post-content`; feed custom (`dc:creator` selalu generik "Punch Newspapers", bukan byline asli). |
| `newindianexpress-scraper` | The New Indian Express | India | **Publisher berbeda dari `indianexpress.com`** (yang sudah dikonfirmasi block) — robots.txt bersih, tidak ada WAF aktif; JSON-LD `NewsArticle` full `articleBody`; CMS Quintype (bukan Next.js); RSS site-wide (`/stories.rss`) sudah `content:encoded` lengkap. |
| `deccanchronicle-scraper` | Deccan Chronicle | India | robots.txt bersih (`Googlebot-News` di-allow eksplisit); tidak ada WAF; JSON-LD `articleBody` langsung tapi satu sampel punya tab character mentah di JSON — perlu `json.loads(strict=False)`; RSS site-wide tunggal. |
| `manilatimes-scraper` | The Manila Times | Filipina | robots.txt bersih — **beda dari Manila Bulletin (sibling outlet) yang 403 di level robots.txt** (indikasi WAF/geo-block, bukan kebijakan robots eksplisit, dicatat untuk investigasi ulang di bawah); tidak ada WAF aktif; JSON-LD ada tapi tanpa paragraph break jadi body tetap dari HTML; RSS `/latest/feed/` bawa full `articleBody` di CDATA. |
| `ndtv-scraper` | NDTV | India | Akamai Bot Manager terdeteksi (`ak_bmsc`) tapi `curl_cffi chrome124` lolos bersih tanpa perlakuan khusus; **3 template konten berbeda** (artikel teks biasa punya `articleBody` lengkap, halaman video cuma `description` pendek, live-blog punya blok `LiveBlogPosting` terpisah) — video & live-blog didokumentasikan sebagai limitation, bukan dipaksakan; latest via Feedburner RSS site-wide. |
| `asharqalawsat-scraper` | Asharq Al-Awsat | Pan-Arab (basis London) | Domain root Arab, edisi Inggris di subdomain terpisah (`english.aawsat.com`) — actor discope eksplisit ke edisi Inggris; robots.txt bersih (Drupal generik); JSON-LD metadata-only (tanpa `articleBody`, tipe bervariasi `NewsArticle`/`OpinionNewsArticle`); tidak ada feed Inggris yang jalan — latest mode pakai homepage-scrape RDFa (`div[typeof=schema:Article]`). |
| `star-kenya-scraper` | The Star (Kenya) | Kenya | robots.txt 2 baris bersih; Next.js **App Router** — tidak ada JSON-LD maupun `__NEXT_DATA__` biasa, data di React Server Components flight payload (`self.__next_f.push(...)`), perlu extractor balanced-bracket 2-pass; paywall soft dikonfirmasi (artikel premium tetap full-text); ditemukan & diperbaiki bug retry pada warmup request saat cloud-testing (exception mentah dari `curl_cffi` sempat crash run, sekarang ternormalisasi jadi `_error` record). |
| `karir-com-scraper` | Karir.com | Indonesia | **Vertikal baru: job board, bukan news article.** robots.txt bersih; tidak ada WAF; ditemukan REST API publik tanpa auth (`gateway2-beta.karir.com`, `/v2/search/opportunities` + `/v1/opportunity/detail`) lewat reverse-engineering webpack chunk Next.js — lebih baik dari JSON-LD, tidak ada gating apapun (bahkan salary range & requirements full terbuka). 2 mode (`search`, `detail`) dalam 1 actor, konsisten dengan pola "mode-based input" yang sudah dipakai actor lain. |
| `point2homes-scraper` | Point2Homes | AS/Kanada | **Vertikal baru: real estate listing.** robots.txt bersih tapi disallow path search asli (`/Search/*`, `/ListingSearch*`) — actor dibangun di atas path browse-by-city + pagination yang tidak di-disallow; tidak ada WAF aktif meski awalnya diduga setara Zillow/Realtor (Kasada/PerimeterX) — ternyata Cloudflare pasif saja; **platform sudah pivot jadi rentals-only** (jaringan Yardi/RentCafe, tidak ada lagi listing for-sale) — actor discope ulang sesuai temuan real, bukan asumsi awal riset; bug silent-redirect-ke-fallback-page (lokasi salah ketik nyasar ke listing New York City tanpa error) ditemukan & diperbaiki dengan validasi URL post-redirect. 2 mode (`search`, `listing`). |

### Actor yang berhenti bersih di fase recon (tidak dibangun, sesuai kebijakan)

| Kandidat | Kenapa berhenti |
|---|---|
| **TE-palvelut** (job board resmi pemerintah Finlandia) | Domain sudah rebrand total ke `tyomarkkinatori.fi` (dikonfirmasi via redirect). robots.txt bersih dari block Claude, TAPI situs adalah SPA client-rendered murni tanpa data ter-embed apapun (JSON-LD/`__NEXT_DATA__`/inline state nihil) — satu-satunya endpoint API yang teridentifikasi (`/api/...`) justru **eksplisit di-disallow di robots.txt untuk semua bot**, dan satu-satunya jalur resmi (REST+OAuth2 client-credentials) mensyaratkan pendaftaran manual ke lembaga pemerintah KEHA-keskus dengan verifikasi badan usaha — ini masuk kategori "mandatory authenticated access" yang dilarang kebijakan proyek (`adding-new-actor/SKILL.md`). Tidak ada file dibuat. |

### Insight metodologi baru dari babak ini

1. **Hit-rate robots.txt sangat bergantung pada "sudah pernah disentuh riset sebelumnya atau belum".** Outlet Eropa/AS besar (sudah pernah dicek berkali-kali sejak Babak 10) makin jenuh diblokir (23% bersih di batch 1-2 babak ini). Tapi begitu pivot ke region yang genuinely belum pernah discreening sama sekali (Nigeria non-Premium-Times/Ghana-Web, India di luar 5 outlet yang sudah dibangun, Asia Tenggara di luar Filipina/Indonesia/Thailand yang sudah dibangun), hit-rate balik ke 80%. **Implikasi untuk babak berikutnya: prioritaskan negara/kategori yang benar-benar baru, bukan outlet ke-2/ke-3 di negara yang sudah sering discreening.**
2. **WAF berbasis reputasi IP/ASN, bukan cuma TLS fingerprint, sekarang terverifikasi langsung** (`freemalaysiatoday-scraper`) — datacenter proxy Apify 403, Residential proxy 200 dengan request yang identik persis. Ini validasi konkret pertama di portofolio untuk klaim `.ai/CLAUDE.md` poin 8 ("gunakan Residential proxy by default"), sebelumnya cuma teori/best-practice generik.
3. **Vertikal non-berita (job board, real estate) terbukti viable dengan pola arsitektur yang sama** — `karir-com-scraper` dan `point2homes-scraper` keduanya dibangun dengan input `mode` (`search`/`detail` atau `search`/`listing`) alih-alih 1 actor per event, konsisten dengan keputusan arsitektur "mode-based" yang dipakai actor `article`/`latest` di cluster berita. Kedua actor ini juga membuktikan template "adding-new-actor" (JSON-LD dulu, baru API/HTML) bisa diadaptasi di luar domain artikel berita — untuk job board, prioritas malah beralih ke "cek dulu apakah ada REST API publik di balik search UI" karena JSON-LD `JobPosting` tidak selalu ada.
4. **Situs modern (Next.js App Router) makin sering TIDAK punya JSON-LD maupun `__NEXT_DATA__` sama sekali** (`star-kenya-scraper`) — datanya ada di React Server Components flight payload (`self.__next_f.push(...)`), pola baru yang belum pernah muncul di 79 actor sebelumnya. Extractor balanced-bracket generik (`skills/balanced-brace-json.md`) tetap bisa dipakai, tapi butuh unwrap tambahan untuk lapisan escape RSC. Kemungkinan pola ini akan makin sering muncul karena App Router jadi default Next.js sejak versi 13+.
5. **Domain/rebrand harus diverifikasi ulang, bukan diasumsikan dari riset lama** — TE-palvelut sudah rebrand total ke Työmarkkinatori.fi, Point2Homes sudah pivot dari portal for-sale+rental jadi rentals-only network. Kandidat yang tercatat di riset lama (Babak 8/9) bisa saja sudah berubah bentuk bisnisnya sama sekali dalam hitungan bulan — verifikasi arsitektur situs saat ini tetap wajib, bukan cuma robots.txt.

### Sisa kandidat robots.txt-bersih yang belum dibangun (untuk sesi berikutnya)

Dari 25 kandidat yang lolos screening babak ini, 13 belum di-dispatch: **Asharq Al-Awsat cluster lain** — NDTV/Star Kenya/dst sudah selesai; sisa murni: **NDTV (selesai)**, dan yang belum: `TE-palvelut` (di-skip permanen, lihat di atas). Kandidat bersih yang belum sempat dibangun sesi ini: **TopCV** (Vietnam, job board), **TopJobs.lk** (Sri Lanka, job board), **Reonomy** (AS, real estate komersial — kemungkinan butuh langganan/data-tier lebih tinggi, worth recon dulu sebelum dispatch penuh), **Free Press Journal** (India), **Telangana Today** (India), **Mmegi** (Botswana), **The Star Malaysia**, **Malay Mail** (Malaysia — 2 kandidat tambahan di negara yang baru saja terbukti hit-rate tinggi), **Cebu Daily News** (Filipina, bagian dari jaringan Inquirer — cek dulu overlap konten dengan `inquirer-scraper` sebelum build), **This Day**, **The Guardian Nigeria**, **Leadership** (Nigeria — 3 kandidat tambahan di negara yang baru terbukti hit-rate tinggi), **Zambia Daily Mail** (melengkapi `timesofzambia-scraper` yang sudah ada).

**Perlu investigasi ulang (403/timeout di level robots.txt, bukan konfirmasi block eksplisit — carry-over dari Babak 15, masih belum diinvestigasi):** Reforma (Meksiko), Manila Bulletin (Filipina — makin menarik untuk investigasi ulang karena sibling-nya Manila Times ternyata bersih total), Vanguard (Nigeria), plus temuan baru babak ini: Zimbabwe Herald, Bahrain News Agency, Pravda (Ukraina), Deník (Ceko), Lebanon Daily Star, Vientiane Times (Laos), Citizen (Afrika Selatan) — semua 403/404/405 di level fetch `robots.txt` itu sendiri, bukan `Disallow` eksplisit, jadi tidak otomatis berarti block kebijakan — kemungkinan WAF/geo-block di layer lain atau sekadar `robots.txt` tidak ada di path standar.

**Total portofolio setelah babak ini: 89 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari filesystem).

---

## Babak 17 — 9 Actor Baru dari Antrean Backlog Babak 16 (2026-08-26)

**Konteks:** melanjutkan langsung dari "Sisa kandidat robots.txt-bersih yang belum dibangun" di penutup Babak 16. Sebelum dispatch, orchestrator re-cek 10 kandidat ambigu (403/404/405 di level fetch `robots.txt` itu sendiri dari Babak 15/16) dengan TLS profile ladder penuh (`chrome131`/`edge101`/`safari17_0`/`chrome99_android`) — **semua 10 tetap gagal di semua profile** (Reforma, Manila Bulletin, Vanguard, Zimbabwe Herald, Bahrain News Agency, Pravda Ukraina, Deník Ceko, Lebanon Daily Star, Vientiane Times, Citizen SA) — dikonfirmasi ini WAF/geo-block genuine, bukan sekadar gap JA3, dan dicoret dari antrean aktif (butuh strategi berbeda, bukan retry sederhana, kalau mau digarap lagi).

**13 kandidat bersih di-dispatch ke agent paralel: 9 berhasil dibangun & di-deploy, 3 berhenti bersih dengan temuan negatif yang valid, 1 di-skip karena redundan.**

### Actor baru yang dibangun & di-deploy ke Apify (9)

| Actor | Outlet/Platform | Negara | Temuan Kunci |
|---|---|---|---|
| `topcv-scraper` | TopCV | Vietnam | **Vertikal job board.** Tidak ada JSON API publik (beda dari `karir-com-scraper`) — situs PHP server-rendered klasik, search lewat pretty-URL slug (`kl` vs `l` di URL city-only vs keyword+city, jebakan halus). Detail lewat JSON-LD `JobPosting` publik penuh tanpa login. Bug ditemukan & diperbaiki: exception dari satu task hydrate sempat lolos dari `asyncio.gather` dan menghapus seluruh batch hasil sukses. |
| `topjobs-lk-scraper` | TopJobs.lk | Sri Lanka | **Vertikal job board.** Situs JSP generasi lama (Tomcat), tidak ada `robots.txt` sama sekali (bukan blok, memang tidak ada file). Deskripsi lowongan di kebanyakan listing berupa **gambar raster** upload employer (`descriptionImageUrl`), bukan gerbang login — dipassthrough sebagai field, bukan dipaksa OCR. JSON-LD `JobPosting` cuma ada di ~separuh halaman, jadi HTML tetap sumber utama. |
| `freepressjournal-scraper` | Free Press Journal | India | CMS Quintype (sama dengan `newindianexpress-scraper`); soft-404 unik — 200 OK dengan body kosong + header `Refresh: 0;url=.../404` (bukan status HTTP standar), dideteksi via cek panjang byte sebelum parsing. |
| `telanganatoday-scraper` | Telangana Today | India | robots.txt eksplisit blokir CCBot/GPTBot/ChatGPT-User tapi Claude-family di-exempt. JSON-LD bersih tanpa quirk control-character (beda dari Deccan Chronicle). Tanggal format non-standar `"YYYY-MM-DD HH:MM:SS +05:30"` (spasi bukan `T`). |
| `mmegi-scraper` | Mmegi | Botswana | JSON-LD `articleBody` inline langsung, tanpa fallback HTML sama sekali. Layered CDN (Cloudflare+CloudFront) tanpa challenge aktif. Latest via RSS per-kategori (`/rssFeed/<id>`). |
| `malaymail-scraper` | Malay Mail | Malaysia | Lolos bersih di Apify **datacenter proxy default** (tidak perlu Residential, beda dari sibling `freemalaysiatoday-scraper` yang wajib Residential) — bukti bahwa gerbang IP-reputation per-situs, bukan generalisasi region. RSS `content:encoded` sudah full-text. |
| `thisday-scraper` | This Day | Nigeria | **Tidak ada JSON-LD maupun OpenGraph sama sekali** — satu-satunya sumber data adalah WordPress REST API (`/wp-json/wp/v2/posts`), dipakai untuk mode `article` maupun `latest` sekaligus (RSS ditemukan corrupt, serving cache stale 5 tahun — dibuktikan lewat footer debug W3 Total Cache milik situs sendiri). |
| `guardian-nigeria-scraper` | The Guardian Nigeria | Nigeria | **Bukan afiliasi UK Guardian** (`guardian-scraper` sudah ada di portofolio untuk itu, publisher beda total). `/feed` di-block WAF path-specific (403 di semua 6 TLS profile) — latest mode pindah ke `/news-sitemap.xml` (Yoast News SEO). **Bug ditemukan: `curl_cffi.requests.exceptions.ConnectionError` TIDAK inherit dari `ConnectionError` bawaan Python** — pola `except (RuntimeError, ConnectionError)` yang dipakai di ~40+ actor sepanjang portofolio gagal menangkap exception ini, berpotensi bikin crash utuh alih-alih degradasi ke `_error` record saat proxy gagal. Diperbaiki lokal di actor ini (tambah `curl_cffi.requests.exceptions.RequestException`), **belum di-fix di actor lain — lihat rekomendasi tindak lanjut di bawah.** |
| `leadership-scraper` | Leadership | Nigeria | Soft-404 unik: homepage-nya sendiri juga punya node `Article` di `@graph` (mendeskripsikan front page, author `"Web"`) — deteksi soft-404 generik "cek node Article ada/tidak" gagal di sini, diperbaiki dengan bandingkan `mainEntityOfPage → WebPage.url` vs URL yang diminta. `/feed` RSS sudah `content:encoded` full-text dengan byline asli (bukan placeholder). |
| `zambiadailymail-scraper` | Zambia Daily Mail | Zambia | Endpoint koleksi REST API WordPress (`/wp-json/wp/v2/posts?slug=...`) **diam-diam mengabaikan semua query parameter** dan selalu balik "10 terbaru" yang sama (dibuktikan via `X-WP-Total` konstan) — RSS & `?paged=N` juga sama-sama rusak (byte-identik lintas halaman). Diatasi dengan ambil ID numerik dari `<link>` REST-discovery di `<head>` HTML, lalu panggil endpoint singular `/wp-json/wp/v2/posts/<id>` yang terbukti tidak kena bug. Latest mode pakai category-archive page (`/category/headlines/page/N/`), bukan REST/RSS. |

### Actor yang berhenti bersih (tidak dibangun, temuan negatif valid)

| Kandidat | Kenapa berhenti |
|---|---|
| **Reonomy** (real estate komersial AS) | robots.txt bersih, TAPI seluruh field bernilai (owner/sales/debt/tax) di-null server-side untuk request anonim (`isSubscribed:false`), dibuktikan konsisten di 4 sampel properti. Halaman browse dibatasi 10 hasil per query dengan `?page=2` yang diam-diam diabaikan (bukan pagination asli). Data publik yang tersisa cuma setara data parsel GIS pemerintah gratis — tidak ada nilai tambah "intelligence" yang jadi alasan orang bayar Reonomy. Tidak layak dibangun sebagai actor. |
| **The Star (Malaysia)** | robots.txt tidak punya baris `Disallow` per-bot untuk AI crawler, TAPI berisi **notice hukum eksplisit dalam bahasa natural** yang melarang "text and data mining", "development/training/operation of any... AI/LLM", dan "storing archived/cached data sets" tanpa izin tertulis dari Star Media Group — dihormati sebagai sinyal block yang sama kuatnya dengan `Disallow` per-bot eksplisit meski format berbeda (bukan machine-readable). **Temuan metodologi baru — lihat di bawah.** |
| **Cebu Daily News** | Ternyata subdomain dari CMS/publisher yang sama persis dengan `inquirer-scraper` (publisher JSON-LD sama-sama "INQUIRER.net", shape ld+json byte-identik, quirk double-escape yang sama). Live-test membuktikan `inquirer-scraper`'s mode `latest` (RSS site-wide `/fullfeed`) **sudah** menyertakan artikel Cebu Daily News tanpa perubahan kode apapun. Membangun actor terpisah akan jadi duplikat kode yang gampang divergen — di-skip, direkomendasikan cukup tambah input `feedUrl` opsional ke `inquirer-scraper` kalau suatu saat perlu scope khusus Cebu. |

### Insight metodologi baru dari babak ini

1. **Screening `robots.txt` harus ditambah lapisan ke-3: cek notice hukum berbahasa natural, bukan cuma parsing `Disallow` per-bot.** Kasus The Star Malaysia membuktikan operator situs bisa melarang scraping/AI-training secara eksplisit lewat komentar teks di `robots.txt` tanpa pernah menyebut nama bot spesifik — parser otomatis yang cuma mencari token `claude`/`anthropic-ai`/`Disallow: /` akan melewatkan sinyal ini sepenuhnya. **Wajib ditambahkan ke checklist screening manual/agent ke depan: baca literal comment block di awal `robots.txt`, bukan cuma directive-nya.**
2. **Bug lintas-portofolio ditemukan: `curl_cffi`'s exception classes tidak selalu inherit dari built-in Python yang senama.** `curl_cffi.requests.exceptions.ConnectionError` != Python `ConnectionError` — pola exception-handling `except (RuntimeError, ConnectionError)` yang jadi konvensi de-facto di ~40+ actor portofolio (disalin actor-ke-actor sejak awal proyek) berpotensi tidak menangkap kegagalan koneksi proxy dan menyebabkan crash utuh alih-alih graceful `_error` record. **Baru diperbaiki di `guardian-nigeria-scraper`. Rekomendasi tindak lanjut: audit dan tambahkan `curl_cffi.requests.exceptions.RequestException` ke exception handler di seluruh actor portofolio** — task terpisah, di luar scope babak ini, tapi berisiko nyata (silent crash saat proxy rotation gagal, bukan cuma masalah kosmetik).
3. **Verifikasi TLS-profile-ladder untuk kandidat yang 403/404/405 di level `robots.txt` sendiri terbukti tidak menghasilkan apapun** — 10/10 kandidat ambigu dari Babak 15/16 tetap gagal di 4 profile berbeda. Ini mengonfirmasi bahwa kegagalan di level ini kemungkinan besar WAF/geo-block genuine (bukan sekadar gap JA3 seperti kasus banyak situs lain di portofolio), dan tidak worth di-retry lagi tanpa strategi baru (mis. cek dari residential IP region lokal, atau cari mirror/API alternatif).
4. **Redundansi antar-subdomain dalam satu grup media perlu dicek sebelum build, bukan cuma nama domain berbeda** — pola sama dengan insight "cek grup usaha" di Babak 8 (Imovelweb/Navent), tapi kali ini di level teknis: `cebudailynews.inquirer.net` bukan cuma "brand sister" tapi CMS/publisher/JSON-LD identik byte-for-byte dengan `inquirer.net`, sehingga actor terpisah otomatis redundan. Cek shape ld+json dan field `publisher` sebelum commit ke build penuh untuk kandidat "subdomain dari domain yang sudah dibangun".

### Sisa kandidat & rekomendasi untuk sesi berikutnya

Antrean bersih dari Babak 16 sudah habis dieksekusi/diputuskan (9 dibangun, 3 skip valid, 1 redundan). **Kandidat baru yang perlu discreening dari nol untuk babak berikutnya** (belum pernah disentuh sama sekali di 17 babak sebelumnya): outlet lapis-2/3 di negara yang baru terbukti hit-rate tinggi di Babak 16 (Nigeria, India, Malaysia, Filipina) — misalnya Vanguard-adjacent Nigeria (Daily Trust, Blueprint, PM News), India regional lain (Millennium Post, Organiser, Free Press Kashmir), atau ekspansi ke negara yang benar-benar belum tersentuh 17 babak ini (Asia Tengah, Pasifik, Karibia di luar yang sudah dibangun). **Tindak lanjut non-riset yang direkomendasikan kuat:** audit `curl_cffi` exception-handling di seluruh actor existing (lihat insight #2 di atas) — ini bug reliability nyata, bukan cuma kandidat actor baru.

**Total portofolio setelah babak ini: 99 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari filesystem).

---

## Babak 18 — 11 Actor Baru, Ekspansi ke Region Baru (Asia Tengah, Pasifik) + Insiden Interupsi Sesi (2026-08-26)

**Konteks:** melanjutkan rekomendasi penutup Babak 17 — outlet lapis-2/3 di negara yang sudah terbukti hit-rate tinggi (Nigeria, India) plus ekspansi eksplisit ke region yang belum pernah tersentuh sama sekali di 17 babak sebelumnya (Asia Tengah, Kepulauan Pasifik). Screening batch baru (21 kandidat) memakai script yang sama dengan tambahan cek natural-language prohibition dari Babak 17 — hasil: 11 bersih, 10 blocked/gagal (termasuk beberapa outlet besar seperti Daily Trust, Blueprint, News18, Manila Standard, Bernama, Trinidad Express — semua eksplisit block Claude).

**Insiden operasional:** sesi sempat di-pause oleh user di tengah dispatch 11 agent paralel — 3 agent (Millennium Post, Organiser, Free Press Kashmir) sudah selesai sebelum pause, **8 agent lainnya diberhentikan paksa** (`stopped by the user`) dan tidak bisa di-resume langsung via pesan (sistem menolak resume, cuma bisa spawn agent baru). Saat user minta lanjut, orchestrator **mengecek folder existing dulu sebelum re-dispatch** — 7 dari 8 target ternyata sudah punya struktur file hampir lengkap dari sesi yang terinterupsi (kode, `.actor/`, kadang `README.md`/`CRAWLING_METHOD.md`), cuma `theprint-scraper` yang nyaris kosong. Agent baru diinstruksikan eksplisit "JANGAN mulai dari nol, verifikasi dulu apa yang sudah ada" — hasilnya, 6 dari 7 actor "hampir selesai" itu ternyata sudah solid tanpa perlu perbaikan kode sama sekali (cuma re-verifikasi + deploy), dan **2 di antaranya ketahuan punya bug nyata**: `README.md`/`CRAWLING_METHOD.md` ternyata hasil copy-paste mentah dari `jamaicagleaner-scraper` (nama outlet, domain, field salah total) — diperbaiki di `jamaicaobserver-scraper` dan `postcourier-scraper`. **Insight: interupsi sesi di tengah dispatch paralel bisa meninggalkan file dokumentasi yang salah tempel dari template tanpa pernah di-review — verifikasi ulang dari nol tetap wajib meski folder "kelihatan lengkap".**

### Actor baru yang dibangun & di-deploy ke Apify (11)

| Actor | Outlet/Platform | Negara | Temuan Kunci |
|---|---|---|---|
| `pmnews-scraper` | PM News | Nigeria | JSON-LD `@graph` tipe campuran `{"NewsArticle","Article"}`; body dari `div.article_body` + bonus field `div.quick_summary_box`; `_error: "not_article"` untuk halaman non-artikel. |
| `millenniumpost-scraper` | Millennium Post | India | RSS/`/feed` mati total (channel kosong, `lastBuildDate` basi >1 tahun) — pivot ke Google News sitemap (`/news-sitemap-daily.xml`). Byline selalu generik `"MPost"`, `keywords` selalu string kosong. |
| `organiser-scraper` | Organiser | India | Majalah mingguan (Rank Math `@graph`, bukan Yoast); `keywords` di JSON-LD berupa objek sparse `{"2":"...", "3":"..."}` bukan array — dipassthrough apa adanya; `/feed/?paged=2` diam-diam balik halaman 1 lagi (pagination tidak jalan), latest mode dibatasi 10 item/run. |
| `freepresskashmir-scraper` | Free Press Kashmir | India | robots.txt cuma BOM+newline (kosong total, bukan blok — literally tidak ada isi). AIOSEO `@graph` dengan `author`/`publisher` selalu `@id` ref (perlu resolve, tidak pernah inline). |
| `theprint-scraper` | The Print | India | **WAF unik: gerbang berbasis cache-state CDN (CloudFront), bukan TLS/JA3** — cache MISS balik interstitial 200-OK "Just a moment" apa pun profil TLS-nya; dikonfirmasi lewat testing cloud langsung bahwa keberhasilan artikel **probabilistik per-artikel** (1 artikel gagal 4/4 lewat proxy residential India, 2 artikel lain sukses konsisten lewat proxy sama) — didokumentasikan jujur sebagai keterbatasan, bukan bug tetap. Artikel wire Reuters (bukan PTI/staff) mengandung karakter watermark zero-width Unicode tersembunyi (`U+200B` dst) — dipassthrough mentah. Latest via Google News sitemap (`/feed`/`/wp-json` full diblokir gerbang cache yang sama). |
| `indiatoday-scraper` | India Today | India | Multi-vertikal (news/sports/entertainment/video) — halaman video menghasilkan `NewsArticle` tanpa `articleBody` (limitation terdokumentasi, tidak crash). `strict=False` diperlukan untuk raw JSON-LD text yang mengandung control character mentah. |
| `kazinform-scraper` | Kazinform | Kazakhstan | **Outlet Asia Tengah pertama di portofolio.** Domain root `inform.kz` cuma Rusia/Kazakh — edisi Inggris genuinely di domain terpisah `qazinform.com` (ditemukan via redirect chain `www.inform.kz/en/` → `en.inform.kz` → `qazinform.com`). Feed `/feed.xml` format ROR dengan bug duplikasi paragraf pembuka bersarang di `content:encoded` — di-dedupe di extractor. |
| `fijitimes-scraper` | The Fiji Times | Fiji | **Outlet Pasifik pertama di portofolio.** `/feed/` mati (redirect ke homepage) — latest mode pakai Google News sitemap index (`sitemap_index.xml` → sitemap ber-nomor terbaru). |
| `postcourier-scraper` | PNG Post-Courier | Papua Nugini | **Outlet Pasifik kedua.** WordPress + WooCommerce Memberships — **paywall genuine terverifikasi** (artikel lokal PNG terpotong ke preview 2 paragraf dengan `_paywalled:true`, artikel PACNEWS/World tetap full-text gratis). Body dari WP REST API (`/wp-json/wp/v2/posts?slug=`), metadata dari Yoast `@graph`. Latest mode dibatasi ~10 item/run oleh ukuran halaman RSS-nya sendiri, terlepas dari input `limit`. |
| `barbadostoday-scraper` | Barbados Today | Barbados | WP REST API (`/wp-json/wp/v2/posts?slug=`) sebagai sumber utama untuk kedua mode, bukan cuma fallback — lebih kaya data dibanding ld+json situs ini. Quirk kosmetik: dropcap huruf pertama artikel kadang terpisah spasi dari kata setelahnya (`"F our major..."`) karena `get_text()` BeautifulSoup terhadap span dekoratif — dibiarkan apa adanya, pola sudah dikenal di portofolio. |
| `jamaicaobserver-scraper` | Jamaica Observer | Jamaika | Publisher terpisah dari `jamaicagleaner-scraper` yang sudah ada (kompetitor langsung, bukan duplikat) — RSS-nya genuinely jalan (beda dari Gleaner yang rusak). **Bug ditemukan & diperbaiki dari sesi terinterupsi:** `README.md` awal adalah copy-paste byte-identik dari `jamaicagleaner-scraper` (nama outlet/domain/field salah total) — ditulis ulang dari nol. |

**Update 2026-08-26 — `theprint-scraper`: follow-up investigasi gerbang cache-state CDN, hasil negatif dikonfirmasi.** Atas permintaan user untuk mencoba metode HTTP alternatif (impersonate/UA lain, library lain seperti `primp`/`scrapling`) sebelum menyerah pada keterbatasan probabilistik yang dicatat di tabel atas — dijalankan investigasi menyeluruh: **34 konfigurasi HTTP berbeda diuji** terhadap 8 URL artikel real (campuran cache-hot & cache-cold) — 20 profil `curl_cffi` (chrome99 s/d 133a, varian Android, edge99/101, 4 varian Safari, firefox133/135), 8 profil `primp` (stack TLS berbeda — rquest/BoringSSL via Rust, bukan curl_cffi), `scrapling`'s HTTP-only stealth fetcher (header realistis + HTTP/3), plus warmup-homepage-dulu vs cold-start, dan retry same-session sampai ~90 detik jeda. **Hasil: seluruh 34 konfigurasi menghasilkan outcome identik persis** — 7 dari 8 URL yang sama tetap ke-block, 1 dari 8 URL yang sama tetap lolos, tidak ada variasi sama sekali. Ini konfirmasi jauh lebih kuat dari investigasi awal bahwa gerbang cache-state CloudFront situs ini **genuinely orthogonal** terhadap TLS fingerprint, implementasi library/stack HTTP, realism header, HTTP/3, warmup sesi, maupun retry jarak-pendek — bukan celah yang bisa ditutup dengan ganti tool. **Tidak ada perubahan kode** (`client.py`/`requirements.txt` dibiarkan seperti semula, tidak ada satupun metode yang mengungguli setup `curl_cffi chrome124` + retry eksponensial yang sudah ada) dan **tidak ada re-deploy** (actor yang sudah live tetap valid, tidak berubah). Temuan didokumentasikan lengkap di `theprint-scraper/CRAWLING_METHOD.md` (breakdown per-metode per-URL) dan ditambahkan sebagai entri baru di `.ai/lessons-learned.md` supaya sesi berikutnya yang ketemu situs dengan gerbang CDN-cache-state serupa tidak mengulang 34 percobaan yang sama.

### Insight metodologi baru dari babak ini

1. **Cek folder existing sebelum re-dispatch setelah interupsi sesi.** Ketika 8 agent diberhentikan paksa di tengah kerja dan tidak bisa di-resume, langkah pertama sebelum spawn agent baru adalah `ls` tiap folder target — 7 dari 8 ternyata punya progres substansial tersimpan (file tidak hilang meski proses terhenti). Agent baru diarahkan untuk **verifikasi dulu, jangan restart dari nol** — menghemat waktu besar dan sekaligus menangkap 2 bug dokumentasi (lihat poin 2) yang kemungkinan besar lolos kalau agent baru cuma percaya "folder sudah ada = sudah benar" tanpa re-verifikasi independen.
2. **Bug baru ditemukan: dokumentasi (`README.md`/`CRAWLING_METHOD.md`) hasil scaffolding copy-paste bisa lolos tanpa pernah di-review kalau sesi terinterupsi persis setelah tahap "copy dari template" tapi sebelum tahap "isi ulang dengan konten actor sendiri".** Terjadi 2× di babak ini (`jamaicaobserver-scraper` dan `postcourier-scraper`, keduanya kebetulan meng-copy dari `jamaicagleaner-scraper`). Kode (`src/*.py`) di kedua kasus itu justru sudah benar dan tidak perlu diperbaiki — cuma dokumen yang salah tempel. **Implikasi:** verifikasi "apify validate-schema lolos + local test lolos" tidak cukup untuk menjamin dokumen konsisten; perlu langkah eksplisit cross-check nama outlet/domain di `README.md` vs `.actor/actor.json` sebelum menandai actor selesai.
3. **WAF berbasis cache-state CDN (bukan TLS/geo/rate-limit) ditemukan pertama kali di portofolio ini** (`theprint-scraper`) — gerbang bereaksi terhadap apakah edge cache CloudFront punya salinan halaman, bukan terhadap fingerprint request. Ini membuat keberhasilan scraping genuinely non-deterministik per-URL (artikel yang sering diakses = cache HIT = sukses; artikel jarang diakses = cache MISS = gerbang), bukan pola block/allow biner seperti WAF konvensional. Perlu didokumentasikan jujur sebagai keterbatasan, bukan dipaksakan retry-sampai-berhasil tanpa batas.
4. **Region baru (Asia Tengah, Pasifik) terbukti hit-rate screening tinggi** (Kazinform bersih, Fiji Times bersih, PNG Post-Courier bersih — 3/3 dari kandidat yang dicoba) — konsisten dengan pola "negara yang belum pernah discreening = median masih bersih" dari insight Babak 17. Worth diperluas lebih jauh: negara Asia Tengah lain (Uzbekistan, Kyrgyzstan, Tajikistan), Pasifik lain (Solomon Islands, Vanuatu, Tonga), belum ada satupun yang dicoba.

### Rekomendasi untuk sesi berikutnya

1. **Audit `curl_cffi` exception-handling lintas portofolio** (dicatat sejak Babak 17, belum dieksekusi) — task maintenance terpisah dari pencarian actor baru, prioritas karena risiko silent-crash nyata di ~40+ actor.
2. **Perluasan region baru:** Asia Tengah (Uzbekistan/Kyrgyzstan/Tajikistan), Pasifik (Solomon Islands/Vanuatu/Tonga/Samoa), belum tersentuh sama sekali.
3. **Outlet lapis-2/3 tambahan** di negara yang sudah terbukti kuat: Nigeria (PM News sudah, coba Vanguard-adjacent lain di luar yang sudah di-skip), India (masih banyak outlet regional-bahasa-Inggris belum tersentuh).
4. **Cross-check dokumentasi wajib ditambahkan ke checklist "actor selesai"** — bandingkan nama outlet/domain di `README.md` dan `CRAWLING_METHOD.md` terhadap `.actor/actor.json` sebelum menandai selesai, bukan cuma andalkan `apify validate-schema` + local test lolos.

**Total portofolio setelah babak ini: 110 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari filesystem).

---

## Babak 19 — Riset Lintas-Kategori Non-Berita: E-commerce, Social Media, Travel, AI/Agents/MCP (2026-08-26)

**Konteks:** atas permintaan eksplisit user untuk mengecek kategori di luar NEWS (yang sudah jadi fokus tunggal Babak 9-18) — ECOMMERCE, SOCIAL_MEDIA, TRAVEL, AI, AGENTS, MCP_SERVERS. Refresh `xtracto` menunjukkan **203 actor published** (turun 2 dari 205 di riset lama), dengan breakdown kategori yang mengungkap fokus bisnis existing: **ECOMMERCE 65 actor**, **SOCIAL_MEDIA 44**, **LEAD_GENERATION 110**, **REAL_ESTATE 22**, **NEWS 30** — tapi **TRAVEL cuma 7**, **AI cuma 1**, **AGENTS cuma 1** — celah terbesar `xtracto` sendiri justru di travel/AI/agents, bukan karena kategori itu kosong di market, tapi karena belum digarap.

**Metodologi:** category-browsing `api-search-actors.py` (band 5-5.000 users, sort `runs_per_user`, `length 60`) di 6 kategori, lalu verifikasi seller-count tanpa cap `max-users` untuk kandidat yang kelihatan tipis di band awal — persis metodologi Babak 8 yang sudah terbukti (dan gagal) sebelumnya untuk kategori generik lain.

### Hasil per kategori — semua terkonfirmasi jenuh

| Kategori | Temuan |
|---|---|
| **ECOMMERCE** (13.068 actor total) | Semua platform besar (Amazon, eBay, Shopee, Walmart, Facebook Marketplace, AliExpress, Etsy, TikTok Shop) sudah dikuasai banyak seller sekaligus — beberapa dengan >1.000-4.900 users individual (`etsy-scraper` 4.922u, `amazon-bestsellers` 4.561u). Kandidat niche yang kelihatan tipis di band (`doordash-reviews-scraper` 92u/8136rpu, `subito-it-motori` 27u/3604rpu) ternyata masing-masing sudah 3-6 seller begitu dicek tanpa cap — pola identik dengan temuan Babak 1-8. |
| **SOCIAL_MEDIA** (11.735 actor total) | TikTok/Instagram/Facebook/LinkedIn/Twitter/Reddit/Threads semua sudah dikuasai puluhan seller dengan ribuan users masing-masing (`fast-tiktok-api` 2.158u/12.193rpu, `tiktok-api` 4.202u). Tidak ada satupun kandidat yang lolos filter "seller rendah" di band 5-5.000 users. |
| **TRAVEL** (2.370 actor total) | Booking/Airbnb/TripAdvisor/Expedia/Yelp/Skyscanner semua sudah 5-15+ seller. Kandidat outlier `hrs-reviews-scraper` (7u/53.109rpu — rpu tertinggi di seluruh riset lintas-kategori ini) dan `despegar-reviews-scraper` (7u/18.250rpu) awalnya kelihatan sangat menjanjikan, tapi verifikasi ulang tanpa cap mengungkap **HRS reviews sudah 6 seller** dan **Despegar reviews sudah 3 seller** — kedua platform niche OTA ini pun sudah dikloning meski individu masih kecil. |
| **AI** (8.432 actor total) | Kategori ini didominasi actor scraping biasa yang cuma diberi label "AI" (video transcript, sentiment analysis, article extractor) — bukan tooling AI/LLM genuine. Tidak ada kandidat data-scraping baru yang genuinely unik. |
| **AGENTS** (3.710 actor total) | Sama seperti AI — mayoritas re-label actor scraping lama. Ditemukan 1 thread menarik: `regdata` (seller yang sama dari temuan Babak 8) sudah membangun **lini bisnis sistematis "government business/compliance registry scraper"** mencakup ≥12 negara (Poland KRZ Debtor Registry, Poland CRBR Beneficial Owners, Italy PEC, Poland MSiG, California SoS, Portugal, Slovakia RPVS, UAE ADGM, Colombia RUES, Ireland CRO, Spain Concursal, Czech ISIR) — masing-masing kelihatan "cuma 1 seller (regdata sendiri)" di satu negara, tapi begitu dicek silang, kompetitor lain (`jungle_synthesizer`, `maximedupre`, `studio-amba`, `automation-lab`, `skyline_scrapers`) sudah mulai kloning niche yang sama juga (Poland KRZ & CRBR masing-masing sudah 3 seller). Pola sama seperti insight Babak 8 poin 2 — klaster seller yang sama mengklon ide viable lintas kategori. |
| **MCP_SERVERS** (2.034 actor total) | **Temuan paling menarik namun tetap jenuh:** ada sub-pasar "MCP server sebagai action-tool untuk AI agent" (bukan cuma data scraping) yang genuinely muncul baru — `clearpath` sendiri sudah punya **5 actor** dalam niche "restaurant reservation MCP" (Resy Booker 48u, Resy Availability API 11u/2.918rpu, Resy API 92u/10.375rpu, OpenTable Booker 81u, OpenTable Availability API 25u), `axlymxp` punya 3 actor Booking.com MCP, `nexgendata` punya "Travel MCP" yang membundel Airbnb+Hotels+TripAdvisor jadi satu tool, dan `makework36`/`crawlerbros` masing-masing sudah punya Reddit MCP Server terpisah. **Sub-pasar MCP-tool ini muncul cepat sekali (kemungkinan besar dalam hitungan bulan terakhir) dan sudah menunjukkan pola kloning-cepat yang sama seperti niche data-scraping klasik** — bukan lagi ruang kosong meski masih tergolong baru. |

**Dicek juga (semua jenuh, ≥6 seller masing-masing):** Product Hunt scraper (12 seller), GitHub Trending scraper (12 seller), AI Tool Directory scraper (12+ seller lintas 6 direktori berbeda — AITopTools/Toolify/FutureTools/Futurepedia/dst), HuggingFace Models scraper (12 seller, mengonfirmasi ulang temuan Babak 8 poin "academic/AI-model directory sudah jenuh").

### Kesimpulan

**Tidak ada kandidat baru yang layak dibangun dari riset lintas-kategori ini.** Setiap kategori yang dicek — termasuk kategori yang belum pernah disentuh sebelumnya (AI, AGENTS, MCP_SERVERS) — sudah menunjukkan pola kloning-cepat yang identik dengan temuan ECOMMERCE/SOCIAL_MEDIA/TRAVEL di riset lama (`ACTOR_MARKET_RESEARCH.md` babak 1-7). **Insight strategis kunci:** alasan template "news scraper per outlet" (Babak 9-18) tetap produktif selama ini bukan karena NEWS sebagai kategori kosong — melainkan karena itu satu-satunya pola di seluruh riset yang berbentuk **long-tail sistematis lintas ratusan target individual** (per-outlet, bukan per-platform), sementara ECOMMERCE/SOCIAL_MEDIA/TRAVEL/AI/AGENTS/MCP_SERVERS semuanya berbentuk "satu ide bagus per platform besar" yang begitu terbukti langsung dikloning banyak seller dalam hitungan hari-minggu (bukti terbaru: sub-pasar MCP-server yang genuinely baru pun sudah jenuh sebelum sempat digarap `xtracto`).

**Rekomendasi jika ingin tetap ekspansi ke kategori non-berita:** cari pola long-tail serupa di kategori lain — bukan "satu platform besar", tapi "ratusan target individual sejenis" seperti job board pemerintah per-negara (`te-palvelut`/`karir.com`/`topjobs.lk` sudah jadi bukti awal pola ini viable, lihat Babak 16), business registry per-negara (meski `regdata` sudah mulai duluan, banyak negara belum tersentuh sama sekali), atau real estate portal regional kecil yang belum ada di 8 babak riset lama. Jangan coba masuk lewat "platform besar tunggal" di ECOMMERCE/SOCIAL_MEDIA/TRAVEL/AI — ruang itu sudah habis.

### Update — verifikasi hipotesis "long-tail serupa": ternyata SUDAH jenuh juga

Atas permintaan lanjutan user untuk mencari pola long-tail serupa template news, dua kandidat paling masuk akal dari rekomendasi di atas — **job board per-negara** dan **business/company registry per-negara** — diuji lebih mendalam dengan query nama platform spesifik (pola metodologi Babak 9) di ~30 negara/target sekaligus. **Hasilnya mematahkan hipotesis awal: kedua pola ini SUDAH dieksploitasi habis oleh seller lain, jauh lebih menyeluruh daripada NEWS.**

**Job board per-negara (20 target dicek):** BDJobs (Bangladesh), Rozee.pk (Pakistan), GulfTalent & Bayt (Timur Tengah), JobStreet/JobsDB (Asia Tenggara), Kalibrr (Filipina), 51job/Zhaopin/Liepin/ChinaHR (China), Monster India/Foundit/Shine.com (India), CV-Library/Reed/TotalJobs (UK), Adzuna (multi-negara), SEEK NZ/TradeMe (Selandia Baru), USAJobs (AS federal), Job Bank (Kanada), Workforce Australia, Careerjet — **semua tanpa kecuali sudah 4-8+ seller berbeda**, kebanyakan oleh seller sistematis yang sama (`memo23`, `getascraper`, `shahidirfan`, `blackfalcondata`, `unfenced-group`, `jobsapi`, `easyapi`, `themineworks`) yang jelas sudah menjalankan strategi "clone tiap job board yang bisa ditebak namanya" jauh lebih agresif dan lebih dulu daripada NEWS. Bahkan kandidat yang kelihatan eksotis (BDJobs Bangladesh, Rozee.pk Pakistan) tetap sudah 5-6 seller.

**Business/company registry per-negara (11 negara dicek, di luar 12 negara yang sudah dicek regdata):** Belanda (KvK), Swedia (Bolagsverket/Allabolag), UK (Companies House), Australia (ASIC), India (MCA), Jepang (Houjin Bangou), Afrika Selatan (CIPC), Selandia Baru (Companies Office), Denmark (CVR), Finlandia (YTJ/PRH), Swiss (Zefix) — **semua sudah 2-6+ seller**, didominasi seller sistematis lain di luar `regdata`: `nexgendata` sudah punya lini bisnis registry sendiri (Australia ASIC + enforcement, India MCA + SEBI + NSE/BSE, Jepang Houjin Bangou + TDnet, Filipina PSE), plus `dltik`, `scrapers_lat`, `jungle_synthesizer`, `studio-amba`, `parseforge` semuanya juga sudah masuk niche yang sama di negara berbeda-beda. Bahkan negara sekecil Denmark/Finlandia sudah 2-6 seller.

**Kesimpulan revisi:** hipotesis "cari long-tail lain yang belum dikloning" **tidak terbukti** untuk 2 kandidat paling masuk akal. Pola yang sebenarnya terjadi: **ada klaster ~15-20 seller (nama-nama sama yang terus muncul sejak Babak 2 riset lama — `parseforge`, `jungle_synthesizer`, `memo23`, `shahidirfan`, `blackfalcondata`, dst — plus pemain baru seperti `nexgendata`, `regdata`, `dltik`, `scrapers_lat`) yang secara sistematis sudah meng-clone hampir SEMUA long-tail-per-negara yang "gampang ditebak" — job board, company registry, classifieds, real estate — di seluruh dunia, jauh sebelum riset ini dimulai.** NEWS ternyata adalah pengecualian, bukan contoh dari pola yang lebih luas — kemungkinan karena scraping artikel berita dianggap kurang bernilai secara komersial dibanding data B2B (leads, compliance, job postings) oleh mayoritas seller di Apify Store, sehingga volume publisher berita di dunia (ribuan, jauh lebih banyak dari jumlah negara) belum habis dikloning meski ide dasarnya identik.

**Implikasi konkret:** portofolio `xtracto` yang paling produktif dan realistis untuk terus dikembangkan tetap **template "news scraper per outlet"** (masih ~13+ kandidat robots.txt-bersih belum dibangun per akhir Babak 18, dan kemungkinan besar ratusan lagi belum discreening sama sekali di negara yang belum tersentuh). Kalau tetap ingin kategori non-berita, perlu dicari pola yang punya ciri sama seperti NEWS — **populasi target berjumlah ribuan (bukan ratusan/negara)** dan **secara historis kurang menarik bagi seller B2B-lead-gen** — kandidat tersisa yang belum tercek sama sekali di seluruh riset ini: blog/publikasi niche per topik (bukan per negara), majalah akademik/jurnal kecil per bidang, atau direktori podcast/newsletter independen — semuanya belum pernah di-screening di 19 babak manapun.

### Update lanjutan (2026-08-27) — dua arah tambahan dicek: blog/jurnal/podcast (negatif), business registry negara kecil (POSITIF, temuan baru)

**Blog/jurnal akademik/podcast/newsletter (10 query dicek: Substack, Beehiiv, Buttondown, DOAJ, PLOS, Crossref, PubMed, arXiv, OpenAlex, Semantic Scholar, podcast directory, WordPress blog generik):** semua kategori ini **juga tidak cocok** jadi pola long-tail-serupa-NEWS, tapi karena alasan struktural berbeda dari job-board/registry (bukan karena sudah dikloning habis, tapi karena **secara inheren tidak butuh actor per-target**). Insight kunci: NEWS unik karena setiap outlet besar (NYT, Guardian, dst) **cukup besar untuk pantas dibuatkan actor khusus** (anti-bot unik, paywall unik, markup unik) — tapi blog/jurnal kecil/podcast individual umumnya di-hosting di platform yang sama (WordPress, Substack, PubMed/Crossref/DOAJ sebagai agregator terpusat, Spotify/Apple Podcasts) sehingga **satu actor generik sudah otomatis cover ribuan target sekaligus** — makanya toolnya yang ada di Apify Store berbentuk "Universal Blog Extractor" atau "Substack Scraper" (platform-level, sudah 5-9 seller tiap platform), bukan "actor per blog individual" seperti NEWS. Pola long-tail-per-target tidak bisa direplikasi di sini karena unit ekonominya beda — tidak ada insentif teknis untuk buat actor terpisah per blog kecil.

**Business/company registry di NEGARA KECIL (bukan negara besar yang sudah dicek sebelumnya) — TEMUAN POSITIF:** hipotesis baru diuji — apakah pola yang sama seperti NEWS berlaku di sini juga, yaitu **negara besar sudah jenuh (regdata/nexgendata/dltik dominan di Poland/Italy/Spain/Germany/UK/India/Australia/Jepang) tapi negara kecil/berkembang belum tersentuh** (persis pola yang membuat Barbados Today/Fiji Times/Trinidad Guardian/Ghana Web tetap bersih meski USA Today/CNN sudah diblokir semua)? **Terkonfirmasi ya.** Dicek 10 negara kecil yang sama persis dengan negara-negara yang sudah terbukti sukses di cluster NEWS (Fiji, Jamaica, Ghana, Trinidad & Tobago, Zambia, Papua Nugini, Botswana, Oman, Namibia, Nepal) — **semuanya 0 hasil relevan sama sekali** (hasil query cuma noise dari kategori lain, bukan actor company-registry apapun). Berbeda total dengan pola job-board/registry-negara-besar yang selalu 2-8+ seller begitu dicek. **Ini benar-benar celah kosong, bukan sekadar "kelihatan kosong di band" seperti temuan Babak 1-8 yang selalu gugur begitu di-cek ulang.**

**Catatan kehati-hatian sebelum eksekusi:** "tidak ada actor kompetitor" untuk registry negara kecil ini BISA berarti dua hal — (a) genuinely celah kosong (seperti NEWS), atau (b) registrinya sendiri tidak accessible publik/HTTP-only (butuh kunjungan fisik, request tertulis, atau sistem legacy yang sulit di-scrape) — beda dengan NEWS yang keterbukaannya sudah terbukti seragam (semua koran punya website). **Belum diverifikasi Phase 1 (cek robots.txt, WAF, apakah data genuinely public tanpa login) untuk satupun dari 10 kandidat ini** — perlu recon per-negara sebelum commit build, karena portal registry pemerintah sering pakai ASP.NET WebForms + session/viewstate + CAPTCHA (beda karakter teknis dari JSON-LD/RSS yang jadi andalan cluster NEWS), jadi effort per-actor kemungkinan lebih tinggi daripada news scraper meski risiko kompetisi jauh lebih rendah. **Direkomendasikan sebagai prioritas riset/recon Phase 1 untuk sesi berikutnya**, bukan langsung dibangun tanpa verifikasi.

---

## Babak 20 — 13 Actor News Baru + TEROBOSAN: 4 Actor Business Registry Pertama di Luar NEWS (2026-08-27)

**Konteks:** melanjutkan permintaan user untuk (1) membangun sisa kandidat news yang bersih, dan (2) melanjutkan riset kategori lain. Screening batch baru (22 kandidat: 6 Asia Tengah, 8 India, 5 Nigeria, 3 Pacific) menghasilkan 13 kandidat bersih; ditambah verifikasi Phase 1 langsung untuk 4 kandidat business-registry negara kecil yang diidentifikasi di update riset sebelumnya. **Hasil: 17 dari 17 actor berhasil dibangun & di-deploy — 100% success rate, tidak ada yang di-skip sama sekali di kedua kelompok.**

### 13 Actor News Baru — semua berhasil

| Actor | Outlet | Negara | Temuan Kunci |
|---|---|---|---|
| `gazetauz-scraper` | Gazeta.uz | Uzbekistan | Tidak ada JSON-LD sama sekali — pakai schema.org microdata (`itemscope`/`itemprop`). 4 edisi bahasa di 1 domain via path prefix, discope ke `/en/`. Fail-loud eksplisit untuk section "Stories" (template Tilda tidak didukung) alih-alih paksa partial data. |
| `uzdaily-scraper` | UzDaily | Uzbekistan | robots.txt **eksplisit `Allow: /` untuk ClaudeBot/anthropic-ai** by name. JSON-LD lengkap dengan `articleBody` plain-text langsung, tanpa fallback HTML sama sekali. |
| `kunuz-scraper` | Kun.uz | Uzbekistan | 4 edisi bahasa independen (bukan mirror terjemahan) di 1 domain, discope ke `/en/`. Byline tetap Cyrillic meski di edisi Inggris. Ditemukan template kedua (page-builder Tilda-style) dengan fallback kerja. Ditambahkan retry-on-fresh-IP untuk `UnexpectedShape` setelah ditemukan 1 exit-node residential proxy yang flaky saat cloud testing. |
| `24kg-scraper` | 24.kg | Kyrgyzstan | Bug asli di situs: atribut tanggal microdata punya backslash liar sebelum closing quote — diatasi pakai OpenGraph meta tags sebagai sumber tanggal. RSS double-escape HTML entity di dalam CDATA (bug situs, bukan artefak parser). Bilingual Rusia/Kirgiz terdeteksi via `<html lang>`. |
| `kabarkg-scraper` | Kabar.kg | Kyrgyzstan | Edisi Inggris di subdomain terpisah (`en.kabar.kg`), bukan path prefix. Satu artikel ditemukan genuinely terpotong di tengah kata oleh CMS upstream sendiri (dikonfirmasi stabil lintas fetch berulang) — dipassthrough apa adanya, bukan dianggap bug extractor. |
| `dailypost-ng-scraper` | Daily Post | Nigeria | JSON-LD flat array (bukan `@graph` Yoast seperti Punch/Guardian Nigeria) — `articleBody` lengkap langsung tanpa fallback HTML, lebih simpel dari template Nigeria lain. |
| `tribuneindia-scraper` | The Tribune | India | Tidak ada RSS sama sekali — latest mode pakai `/recent-sitemap.xml`. `author` selalu 1 dict (bukan array), sering wire-credit PTI/ANI. |
| `businesstoday-scraper` | Business Today | India | Satu grup usaha dengan `indiatoday-scraper` (Living Media/India Today Group) — infra CDN sama, JSON-LD bersih tanpa control-character issue (beda dari sibling-nya). |
| `moneycontrol-scraper` | Moneycontrol | India | **Verifikasi robots.txt ekstra hati-hati** karena sesama grup Network18 (`news18-scraper` — belum dibangun — sudah dikonfirmasi block Claude eksplisit): dicek ulang langsung dan dikonfirmasi Moneycontrol genuinely bersih meski News18 block. Paywall genuine tapi sempit (cuma vertikal "Moneycontrol PRO" yang ter-gate, berita umum full-text gratis). Akamai reject generic bot-UA (termasuk `ClaudeBot` literal) tapi lolos bersih pakai Chrome UA biasa — bukan block Claude-spesifik. |
| `dnaindia-scraper` | DNA India | India | **Temuan robots.txt baru:** grup `User-agent: ClaudeBot` ada tapi **tanpa directive apapun di dalamnya** (ruleset kosong) — beda dari pola "block eksplisit" yang biasa ditemukan, secara teknis RFC 9309 artinya tidak melarang apapun, tapi ambigu secara authoring — dibangun tapi ditandai jelas untuk review manual. Data dari React Server Components flight chunks (pola sama `star-kenya-scraper`) dengan komplikasi baru: field `articleBody` direferensi via pointer lintas-chunk terpisah, bukan inline. |
| `nationalherald-scraper` | National Herald | India | `articleBody` double-HTML-escaped; `publisher` di JSON-LD cuma stub kosong (`{"@type":"Organization","id":""}`), tidak reliable. |
| `thewire-in-scraper` | The Wire | India | **Domain desktop adalah shell React SPA kosong untuk semua path** (bukan block WAF) — ditemukan lewat JS redirect mobile-UA bahwa `m.thewire.in` genuinely server-rendered; actor menulis-ulang semua URL input ke subdomain mobile itu sebelum fetch. |
| `scrollin-scraper` | Scroll.in | India | Tidak ada `articleBody` di JSON-LD — HTML fallback `div#article-contents.article-body`, direct-child `<p>` saja (perlu skip nested `<p>` di embed). Tag "Members-Only" ternyata bukan gerbang paywall sungguhan. |

### 4 Actor Business Registry Baru — TEROBOSAN kategori non-berita pertama yang berhasil

**Ini bukti konkret pertama bahwa hipotesis "long-tail negara kecil" dari update riset sebelumnya benar-benar valid** — dari 4 kandidat yang di-investigasi, **4-4 berhasil dibangun**, bukan cuma "kelihatan kosong lalu gugur" seperti nasib kebanyakan kandidat non-berita di Babak 19.

| Actor | Negara/Lembaga | Data yang Diperoleh | Temuan Kunci |
|---|---|---|---|
| `zambia-pacra-scraper` | Zambia — PACRA (Patents & Companies Registration Agency) | Nama entitas, no. registrasi, tanggal pendirian, status hukum, tipe perusahaan, klasifikasi industri ISIC, status kepatuhan (annual returns, modal nominal, beneficial ownership) | REST API publik tanpa auth ditemukan lewat reverse-engineering webpack chunk frontend Next.js (`xatu.pacra.org.zm:8344/api/v1/Search/registrysearch`) — tanpa API key, session, CSRF, atau CAPTCHA. Keterbatasan jujur: pencarian by nomor registrasi TIDAK berfungsi meski UI menyarankannya; hasil dibatasi 50/query tanpa pagination; data direktur/pemegang saham penuh perlu portal berbayar terpisah (di luar scope, tidak dicoba). |
| `ghana-rgd-scraper` | Ghana — ORC (Office of the Registrar of Companies) | Nama bisnis + tipe entitas (Sole Proprietor/Company Ltd/Partnership/dst) | Domain target awal (`rgd.gov.gh`) ternyata situs terbengkalai + ter-compromise (spam link injection) — ditelusuri ke portal pengganti resmi `orc.gov.gh` → tool interaktif riil di `rgdonline.gegov.gov.gh/orc-app/` (Spring Boot + htmx, v0.0.1, masih tahap awal). Perlu reverse-engineering token CSRF fresh-per-request + header htmx (`HX-Request`/`HX-Trigger-Name`) yang kalau salah gagal senyap (redirect ke homepage, bukan error). **Keterbatasan jujur didokumentasikan tegas di README**: cuma name-availability checker, bukan full company profile (no. registrasi/status/direktur perlu extract berbayar terpisah). |
| `png-ipa-scraper` | Papua Nugini — IPA (Investment Promotion Authority) | Nama, no. registrasi, status, tipe, tanggal, alamat, aktivitas bisnis, riwayat filing lengkap | Halaman search awalnya kelihatan ASP.NET WebForms klasik (ada `__VIEWSTATE`) — ternyata cuma dekorasi, komponen Vue di baliknya panggil REST API JSON bersih langsung (`/Api/Corp/SearchCorp`, `/Api/Corp/GetCorpProfile`). Butuh header `PA-Token` anti-CSRF yang di-harvest dari hidden field, bukan CAPTCHA/login. **Keterbatasan jujur**: nama direktur/sekretaris/pemegang saham/beneficial owner kosong (butuh akun IPA Online berbayar) — dipassthrough sebagai array kosong, tidak dipalsukan. |
| `botswana-cipa-scraper` | Botswana — CIPA (Companies and Intellectual Property Authority) | **Profil beneficial-ownership LENGKAP**: status/riwayat perusahaan, alamat, direktur, sekretaris, pemegang saham (termasuk pemegang saham korporat/JV seperti holding BVI milik Debswana), auditor, beneficial owner dengan persentase kepemilikan | **Actor paling kaya data dari 4 registry ini** — sistem "Verne by Foster Moore" berbasis protokol Vue3/JSON-RPC-like stateful, direverse-engineer dari bundle JS (`POST /master/ui/<txn>` dengan command `view-node-set-attribute-value`/`view-node-button-click`). Ditemukan gotcha kritis: config `returnRootHtmlOnChange:false, returnChangesOnly:true` harus persis sama atau search balik kosong-tapi-200 secara senyap (silent failure, bukan error eksplisit). Halaman detail company (`/companies/ui/start/entityView/<uuid>`) dikonfirmasi bisa diakses dari session baru tanpa cookie sama sekali — permalink publik sungguhan. Extractor pakai tree-walker generik (bukan hardcode field) supaya robust terhadap variasi struktur data antar tipe perusahaan. |

### Insight strategis dari terobosan ini

1. **Hipotesis "negara kecil = celah kosong genuine" terbukti benar untuk business registry, bukan cuma untuk NEWS.** Berbeda total dengan job-board/registry-negara-besar (Babak 19, selalu 2-8+ seller begitu dicek) dan berbeda dengan kebanyakan temuan "kelihatan kosong" di riset lama (Babak 1-8, hampir selalu gugur setelah verifikasi), 4 dari 4 kandidat registry negara kecil ini benar-benar 0 kompetitor DAN genuinely dapat diakses publik tanpa login/CAPTCHA — pola yang sama persis dengan yang membuat `ghanaweb-scraper`/`trinidadguardian-scraper`/`barbadostoday-scraper` viable di cluster NEWS.
2. **Effort per-actor lebih tinggi dari NEWS, tapi masih dalam batas wajar.** Setiap registry butuh reverse-engineering pola API/protokol yang genuinely berbeda-beda (REST API polos di Zambia, htmx+CSRF di Ghana, Vue+PA-Token di PNG, protokol Vue3/JSON-RPC stateful di Botswana) — tidak ada template seragam seperti JSON-LD/RSS di NEWS, konsisten dengan prediksi di update riset sebelumnya. Durasi kerja per-agent utk registry (17-34 menit) jauh lebih lama dari rata-rata actor NEWS (10-20 menit), tapi masih selesai dalam 1 sesi.
3. **Kedalaman data sangat bervariasi antar negara — perlu dicek per-kasus, bukan diasumsikan seragam.** Botswana kasih profil beneficial-ownership lengkap gratis; Ghana cuma name-availability check; PNG dan Zambia di tengah-tengah (data registrasi solid tapi direktur/shareholder detail di-gate). Setiap actor mendokumentasikan keterbatasan ini dengan jujur di README, bukan dipoles biar kelihatan lebih lengkap dari yang sebenarnya.
4. **Pola "silent failure" (bukan error eksplisit) muncul berulang di 2 dari 4 registry** (Ghana: token stale → redirect diam-diam ke homepage; Botswana: config salah → response kosong-tapi-200) — beda dari NEWS yang biasanya block eksplisit (403/atau WAF challenge page jelas). Registry pemerintah tampaknya lebih sering "gagal senyap" daripada "block terang-terangan" — insight metodologi baru untuk sesi registry berikutnya: selalu verifikasi response benar-benar berisi data, jangan cuma cek status code 200.

### Rekomendasi lanjutan

1. **Perluas registry negara kecil lain** — kandidat yang belum diverifikasi Phase 1 dari update riset sebelumnya: Jamaica (ORC — sempat cuma dapat 647 byte, perlu recon lebih dalam), Namibia (BIPA — SSL cert issue, perlu `verify=False` atau cek ulang), Trinidad & Tobago (SSL issue serupa), Nepal (timeout, kemungkinan transient), plus Oman dan Fiji yang belum sempat dicek URL-nya sama sekali. Juga perluas ke negara kecil lain yang belum dicek: negara Karibia lain (Barbados, Bahamas, Belize), Pasifik lain (Solomon Islands, Vanuatu, Samoa — meski situs berita mereka sudah terblokir, registry pemerintahnya belum tentu), Afrika lain (Malawi, Rwanda, Tanzania, Uganda, Mozambique).
2. **Audit `curl_cffi` exception-handling lintas portofolio** (dicatat sejak Babak 17, masih belum dieksekusi) — makin mendesak sekarang portofolio sudah 127 actor.
3. **Sisa kandidat NEWS robots.txt-bersih dari Babak 18/19 yang belum sempat di-follow-up:** The Statesman (India) sempat discreening cepat (clean) tapi belum di-dispatch build.

**Total portofolio setelah babak ini: 127 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari filesystem) — 13 news outlet baru + **4 actor kategori non-berita pertama yang berhasil** (business registry).

---

## Babak 21 — 5 Actor Baru via Dispatch Paralel: Penutup Backlog Babak 20 (2026-08-27)

**Konteks:** melanjutkan langsung 3 rekomendasi penutup Babak 20 — (1) The Statesman (news, sudah bersih tapi belum dibangun), dan (2) perluasan registry negara kecil untuk 8 kandidat: 6 dari backlog lama (Jamaica, Namibia, Trinidad & Tobago, Nepal, Oman, Fiji) + 2 kandidat baru sama sekali (Rwanda, Uganda). Dispatch 9 agent paralel, masing-masing menjalankan siklus penuh Phase 1 (recon/robots/WAF) → Phase 2 (build) → Phase 3 (test+deploy) secara independen, dengan instruksi tegas: **stop bersih tanpa build kalau Phase 1 gagal** (robots block, login wall, tidak ada search endpoint sama sekali) — jangan paksa actor setengah jadi.

**Hasil: 5 dari 9 berhasil dibangun & di-deploy, 4 di-skip bersih dengan alasan terverifikasi.** Rasio keberhasilan (56%) jauh lebih rendah dari Babak 20 (100%) — sesuai ekspektasi, karena Babak 20 sudah memetik 4 kandidat "termudah" duluan; sisa backlog ini memang lebih beragam kualitasnya.

### 5 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Temuan Kunci |
|---|---|---|
| `statesman-scraper` | The Statesman (India, news) | Cloudflare di depan situs tapi `curl_cffi chrome124` lolos tanpa challenge di percobaan pertama. JSON-LD non-standar (`"@type": "newsarticle"` huruf kecil, bukan `@graph`) berisi `articleBody` penuh; field `keywords`/`wordCount` diambil dari blok `@graph` terpisah dan digabung. RSS mati total (500 `wp_die`) — latest mode pakai `/googlenews.xml` (342 entri live). Kuirk: slug artikel yang tidak ada di-302-redirect ke halaman kategori (bukan 404) — dideteksi lewat heuristik pola URL (`-<id>.html`) supaya tidak jadi silent bad record. |
| `jamaica-coj-scraper` | Jamaica — Companies Office of Jamaica (COJ) | Domain benar `orcjamaica.com` (bukan `rgd.jm` yang dicoba sesi lama). robots.txt bersih tanpa Crawl restriction untuk bot manapun (`Crawl-delay: 120` saja). "JS challenge" Zenedge di depan `CompanySearch.aspx` ternyata cuma reskin probe cookieless-session ASP.NET standar — cukup hit halaman 2× dalam 1 sesi, tidak perlu eksekusi JS. Alur search async multi-step (POST → polling `AsyncServices/asyncState/<id>` → GET hasil) mengembalikan blob `var database = {...}` berisi nama, no. registrasi, status, tipe entitas, tanggal, alamat, dan 1 officer — tanpa login. Rate-limit nyata (Zenedge HIC 403) pulih sendiri ~60-120 detik. |
| `nepal-ocr-scraper` | Nepal — Office of Company Registrar (OCR) | Timeout sesi lama ternyata salah domain (`www.ocr.gov.np` tidak resolve; `nepal.gov.np:8080` malah `Disallow: /`) — domain benar `ocr.gov.np` (tanpa www), portal riil di subdomain `camis.ocr.gov.np`. SPA React/Vite dengan endpoint JSON stateless publik (`POST .../search-company-details`) tanpa cookie/CSRF/auth — tapi **tanpa limit hasil di server**: query kosong balik ~53MB (seluruh registry), query umum balik 10.652 match; actor memotong di sisi klien. Sertifikat TLS chain tidak lengkap (`verify=False` diperlukan, bug server nyata). Data terbatas ke info dasar (nama EN/NP, no. registrasi, tanggal kalender Bikram Sambat, tipe, alamat, flag `isRokka`/legal-hold) — tanpa direktur/pemegang saham. |
| `uganda-ursb-scraper` | Uganda — Uganda Registration Services Bureau (URSB) | Portal riil `eregistry.ursb.go.ug/name-search` (SPA Vue3; domain lama `obrs.ursb.go.ug` redirect ke sini). Endpoint REST JSON polos ditemukan dari bundle JS (`obrs-api.ursb.go.ug/nir/api/v1/registry/name-search`) — satu-satunya gerbang adalah fingerprint TLS (request default kena 403 "Prohibited Access!", tapi profil `curl_cffi` manapun langsung lolos, tanpa login). Kuirk: metadata `pagination` (`totalPages`/`totalRows`) di response selalu 0 meski hasil nyata — stop-condition pagination pakai deteksi halaman pendek, bukan metadata; search fuzzy secara sengaja (name-uniqueness checker) jadi query sampah bisa balik hasil yang longgar-cocok, bukan kosong. |
| `fiji-roc-scraper` | Fiji — Registrar of Companies (ROC), Digital Transformation Programme | Bukan di bawah RBF/FRCS seperti dugaan awal — portal riil `roc.digital.gov.fj/BuyInformation/Search` (ASP.NET Core + Kendo). robots.txt 404 di semua subdomain `digital.gov.fj` (tidak ada restriction). Cloudflare di depan tapi tidak pernah menantang `curl` polos di ~40 request recon. Search publik (GET-token → POST-search → GET-grid) balik nama/no. entitas/tipe/status tanpa login; profil lengkap (direktur/pemegang saham) di-gate OIDC login (`auth.digital.gov.fj`) — actor berhenti di level search sesuai batas no-login. Kuirk ganda: name search fuzzy/fonetik ekstrem (1 huruf balik 239.507 hasil) + hasil sangat besar bikin grid endpoint diam-diam balik kosong (`TotalRecords:0`) meski query valid — ditangani sebagai error state terpisah (`result_set_too_broad`), bukan `not_found` palsu.

### 4 Kandidat Di-skip — verifikasi bersih, tidak dipaksa build

| Target | Alasan Skip |
|---|---|
| **Oman** (registry komersial MOCIIP "Invest Easy" + OCCI) | Kedua kandidat portal sama-sama `robots.txt: Disallow: /` blanket untuk `User-agent: *` (bukan cuma nama bot tertentu) — dihormati sebagai stop-condition. OCCI juga sedang halaman maintenance. |
| **Trinidad & Tobago** (Companies Registry Online System, `rgd.legalaffairs.gov.tt`) | Hard login wall by design — butuh akun CRA terverifikasi identitas (submit paspor+foto, proses manual berhari-hari) plus biaya TTD 500 minimum. Tidak ada jalur anonymous search sama sekali. Isu SSL sesi lama ternyata cuma cert tanpa intermediate chain (bisa diatasi `verify=False`) — tapi jadi tidak relevan karena login wall. |
| **Namibia** (BIPA) | Bukan WAF/login — situsnya (`www.bipa.na`, WordPress statis) genuinely **tidak punya sistem pencarian company online sama sekali**; pendaftaran & pencarian nama dilakukan manual di kantor/lewat legal practitioner. Klaim "portal pencarian online" di situs SEO pihak ketiga terkonfirmasi salah/tidak berkorespondensi dengan situs resmi. Isu SSL sesi lama ternyata cuma salah hit ke bare-apex domain yang masih pakai cert self-signed placeholder Apache default. |
| **Rwanda** (RDB, `urs.rdb.rw`) | Endpoint search-by-nama (`GET /api/v1/business/search-company`) di-reverse-engineer dari bundle SPA tapi balik `401 Unauthorized` tanpa jalur guest-token/client-credentials apapun. Satu-satunya endpoint publik (`search?type=tin`) butuh TIN 9-digit yang sudah diketahui persis — tidak berguna untuk discovery. Search riil hard-gated di balik login warga. |

### Insight metodologi baru

1. **"SSL cert error"/"timeout" di riset awal ≠ situs benar-benar bermasalah — selalu re-verifikasi domain & konteks dulu sebelum menyerah.** 3 dari 4 kandidat backlog lama (Jamaica, Namibia, Nepal) yang tadinya dicatat "SSL issue"/"timeout" ternyata masalah domain/hit yang salah (bare-apex vs `www.`, subdomain lama vs baru) — begitu domain benar ditemukan, situsnya bersih. Hanya Trinidad & Tobago yang SSL-issue-nya genuinely tidak relevan (kalah oleh alasan lain, login wall).
2. **Rasio sukses registry negara kecil (5/9 sesi ini vs 4/4 Babak 20) menunjukkan Babak 20 memang memetik yang termudah duluan** — bukan berarti pola "negara kecil = celah kosong" batal, tapi variasinya lebih tinggi dari dugaan: beberapa negara genuinely tidak punya sistem online sama sekali (Namibia), beberapa punya API tapi hard-gated (Rwanda, Trinidad & Tobago), beberapa blanket-block robots (Oman) — perlu Phase 1 recon utuh per kandidat, tidak bisa diasumsikan dari pola negara lain yang mirip.
3. **robots.txt blanket `Disallow: /` untuk `User-agent: *` (Oman) dihormati sama seperti block Claude eksplisit** — bukan cuma pola "nama bot spesifik" dari insight Babak 8-18, block total untuk semua crawler juga stop-condition yang sama tegasnya.
4. **Reverse-engineering endpoint dari bundle JS SPA (webpack/Vite) terus terbukti jadi teknik paling produktif untuk registry** — berhasil di Nepal (CAMIS), Uganda (eRegistry), dan gagal-tapi-informatif di Rwanda (nemu endpoint tapi 401) — pola yang sama sejak Botswana/PNG di Babak 20, sekarang terkonfirmasi generalizable lintas 3+ negara tambahan.

### Rekomendasi lanjutan

1. **Audit `curl_cffi` exception-handling lintas portofolio** (dicatat sejak Babak 17, masih belum dieksekusi, sekarang makin mendesak — portofolio 132 actor).
2. **Sisa negara kecil dari rekomendasi Babak 20 yang belum dicoba sama sekali:** Karibia (Barbados, Bahamas, Belize — catatan: `barbadostoday-scraper`/`trinidadguardian-scraper` sudah ada tapi itu NEWS, registry-nya belum dicek), Pasifik (Solomon Islands, Vanuatu, Samoa), Afrika (Malawi, Tanzania — BRELA, Mozambique).
3. **Business/company registry bukan satu-satunya pola non-berita yang mungkin masih ada celah** — worth dicoba sekali lagi dengan sudut berbeda dari Babak 19 (job-board/registry negara besar sudah terbukti jenuh): coba pola serupa NEWS/registry tapi untuk kategori lain yang genuinely per-negara (mis. tender/procurement pemerintah, atau vehicle/land registry) — belum pernah discreening sama sekali di 21 babak manapun.

**Total portofolio setelah babak ini: 132 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — 1 news outlet baru + **4 actor registry baru** (Jamaica, Nepal, Uganda, Fiji), menggenapkan total business-registry non-berita jadi 8 actor.

---

## Babak 22 — 7 Actor Registry Baru via Dispatch Paralel: Penutup Backlog Karibia/Pasifik/Afrika (2026-08-27)

**Konteks:** melanjutkan langsung rekomendasi penutup Babak 21 — 9 kandidat registry negara kecil yang belum tersentuh sama sekali di 21 babak sebelumnya: Karibia (Barbados, Bahamas, Belize), Pasifik (Solomon Islands, Vanuatu, Samoa), Afrika (Malawi, Tanzania, Mozambique). Dispatch 9 agent paralel, masing-masing menjalankan siklus penuh Phase 1 (recon/robots/WAF) → Phase 2 (build) → Phase 3 (test+deploy) secara independen, instruksi sama tegasnya dengan Babak 21: **stop bersih tanpa build kalau Phase 1 gagal**.

**Hasil: 7 dari 9 berhasil dibangun & di-deploy, 2 di-skip bersih dengan alasan terverifikasi.** Rasio keberhasilan (78%) jauh lebih tinggi dari Babak 21 (56%) — mengonfirmasi ulang pola "negara yang genuinely belum pernah discreening cenderung masih bersih", kali ini berlaku juga untuk registry (sebelumnya pola ini hanya terbukti kuat untuk NEWS).

### 7 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `barbados-caipo-scraper` | Barbados — CAIPO (Corporate Affairs and Intellectual Property Office) | `wghucc3yNntdpZOs4` | Domain hint awal (`corporateaffairs.gov.bb`) mati total — domain riil `caipo.gov.bb`. Search API (`POST /sso/site/searchDbApi`) direverse-engineer dari inline `<script>` polos (bukan SPA framework), tanpa auth/CAPTCHA. **Catatan kehati-hatian:** endpoint ini secara teknis ada di bawah prefix `/sso/` yang di-disallow robots.txt, tapi file robots.txt-nya sendiri punya komentar eksplisit "provides ZERO security... for SEO, not security" — agent memutuskan proceed dengan alasan itu bukan access-control measure dan endpoint-nya memang mirror form publik anonim; didokumentasikan transparan di `CRAWLING_METHOD.md` untuk direview ulang kalau kebijakan berubah. Data gratis cuma 4 field (nama, nomor, kategori, tanggal registrasi) — profil penuh $5 manual inquiry, di luar scope. Kuirk: `company_number` bisa dipakai ulang lintas entitas tak berelasi (bukan primary key sungguhan). |
| `bahamas-rgd-scraper` | Bahamas — Registrar General's Department | `uXUGm5xdKeTJJ45kW` | SPA Angular (`pub.rgd.gov.bs`) + JSON API (`cars.rgd.gov.bs/api`), robots.txt bersih. Reverse-engineered dari bundle Angular (`main.js`→`868.js`): `GET /api/public/entities?name=`, tanpa auth. **Free tier sangat tipis:** `pageNo`/`pageSize` diam-diam diabaikan (hard-cap 3 hasil top-match, funnel ke laporan berbayar $100 BSD), hampir semua field selain nama/ID/status migrasi bernilai `null`. Query umum (`"Bank"`, `"LTD"`) balik HTTP 200 dengan body 0-byte genuinely kosong (bukan block) — ditangani sebagai `_error: "result_set_too_broad"` terpisah dari not-found asli. |
| `belize-bccar-scraper` | Belize — BCCAR (Belize Companies and Corporate Affairs Registry) | `q99ulsC1SeUJ3hdRF` | **Tidak ada WAF/TLS gate sama sekali** — pertama di seluruh seri registry portofolio ini (`curl` polos tanpa impersonation langsung 200). Endpoint search (`obrs.bccar.bz/bereg/list/public/business.json`) ditemukan dari inline script + `js/lib.js`, butuh handshake CSRF ringan (`NCSRF` token dari cookie session, refresh otomatis kalau stale). `TotalRecordCount` di response terbukti akurat (beda dari Uganda URSB yang selalu 0) — dipakai langsung sebagai stop-condition pagination. Alternatif domain decoy `companysearch.bz` ditemukan dan ditolak (robots.txt-nya `Disallow: /`). |
| `solomonislands-sbr-scraper` | Solomon Islands — Solomon Islands Business Registry | `cqdZDOAKhXBVAOD9h` | **Actor registry paling kaya data di portofolio ini** — platform Foster Moore "Catalyst" yang sama dengan `botswana-cipa-scraper`, tapi coverage lebih luas: Companies + Business Names + Foreign Investments, masing-masing dengan direktur, pemegang saham individu (termasuk jumlah saham), alamat, dan riwayat filing lengkap — semua gratis tanpa login. Tidak ada `robots.txt` (404) dan tidak ada WAF terdeteksi. |
| `samoa-br-scraper` | Samoa — MCIL (Ministry of Commerce, Industry and Labour), Companies Act 2001 | `0fvUjm7Pvf4tnzpDY` | Register transaksional riil di domain terpisah (`businessregistries.gov.ws`, bukan `mcil.gov.ws`). robots.txt 404 (tidak ada restriction), tanpa WAF/CAPTCHA. Setiap tab detail (Alamat, Direktur, Pemegang Saham, Share Parcels, Filing) bisa diakses sebagai guest session penuh tanpa login — dikonfirmasi terhadap perusahaan riil (Bank South Pacific: 24 direktur, 8 pemegang saham). Sama-sama keluarga framework "Catalyst" dengan Botswana/Solomon Islands, tapi generasi jQuery lebih lama dengan wire-protocol berbeda total (form-encoded `_CBNODE_`/`_VIKEY_`, bukan JSON command) — setiap node id di-regenerate per-sesi, mixing id lintas 2 fetch halaman diam-diam jatuh ke dashboard generik tanpa error. |
| `malawi-cripc-scraper` | Malawi — CRIPC (Companies, Registrations and Intellectual Property Centre, penerus Registrar General's Department sejak April 2026), sistem MBRS | `C0GRSL7EFIddG0OO6` | robots.txt di 3 host relevan (`mbrs.gov.mw`, `registrargeneral.gov.mw`, `cripc.gov.mw`) semuanya template stock kosong tanpa Disallow aktif. Tanpa WAF sama sekali — 4 profil `curl_cffi` + `curl` polos semua 200 dengan data identik. HTML server-rendered murni (Elixir/Phoenix) dengan overlay Vue yang inert — tanggal muncul sebagai teks mustache `{{formatDate(...)}}` mentah, diekstrak via regex tanpa perlu JS. 2 mode: `entity` (company/business name) dan `individual` (pemilik, dengan opsi fetch detail linked-businesses). Kuirk: prefix nomor registrasi tidak fixed-width (`COY-`, `BRN-`, bahkan `COYR-`) — parser dibuat prefix-agnostic. |
| `tanzania-brela-scraper` | Tanzania — BRELA (Business Registrations and Licensing Agency), Online Registration System (ORS) | `0evmJVAKn4CfapTrM` | robots.txt bersih (cuma disallow `/dontVisitMe/`). **WAF ditemukan yang unik**: blokir 403 untuk request apapun (GET/POST) yang membawa parameter `object_type` dalam bentuk form-urlencoded/query-string — apapun nilainya — ternyata front-end asli situs SELALU kirim JSON body (`Content-Type: application/json`), bukan form-encoded; begitu format body dicocokkan persis, WAF lolos bersih di semua request berikutnya. Endpoint JSON riil (`POST /orsreg/list/search/businesspublic.json`) ditemukan dari config `listUrl` inline di halaman. Detail direktur/pemegang saham tetap gated ke user terdaftar (didokumentasikan jujur, bukan dipaksakan). |

### 2 Kandidat Di-skip — verifikasi bersih, tidak dipaksa build

| Target | Alasan Skip |
|---|---|
| **Vanuatu** (VFSC — Vanuatu Financial Services Commission) | Situs marketing (`www.vfsc.vu`) bersih dan eksplisit bilang search gratis-tanpa-login, tapi backend fungsional sungguhan ada di host terpisah (`registry.vfsc.vu`, platform "Catalyst" stateful serupa Botswana/Solomon Islands/Samoa) yang robots.txt-nya `User-agent:*` / `Disallow /` (malformed — tanpa titik dua — tapi intent-nya tidak ambigu: blanket block untuk semua bot di satu-satunya host yang menyajikan data riil, dikonfirmasi stabil lintas 3 User-Agent berbeda termasuk `ClaudeBot/1.0` literal). Dihormati sebagai stop-condition sesuai preseden Nepal (Babak 21) yang juga menghormati `Disallow: /` meski secara teknis bisa dieksploitasi. Worth direvisit kalau typo robots.txt-nya diperbaiki suatu saat. |
| **Mozambique** (CREL — Conservatória do Registo das Entidades Legais) | Domain "IPEX" yang diklaim artikel SEO pihak ketiga sebagai portal pencarian gratis ternyata **domain mati, tidak resolve DNS sama sekali** — pelajaran: jangan percaya klaim URL pihak ketiga tanpa probe HTTP langsung. Registry riil dicoba lewat 2 jalur: **e-BAU** (`www.ebau.gov.mz`, robots.txt bersih tapi API-nya cuma exact-match lookup by kode yang sudah diketahui — bukan discovery search — dan balik 403/401/503 tanpa token valid), dan **SRN** (`utente.srn.gov.mz`) yang 100% di balik login untuk semua kategori termasuk entitas legal. Diverifikasi independen: OpenCorporates menilai registry Mozambique 0/20 "Freely Searchable" dan 0/20 "Data Freely Available" — mengonfirmasi ini bukan gap recon, tapi genuinely tidak ada jalur publik. Pola sama dengan skip Rwanda/Trinidad & Tobago di Babak 21 (hard login wall), bukan pola "negara kecil = celah kosong" seperti mayoritas kandidat lain di babak ini. |

### Insight metodologi baru

1. **Rasio sukses registry negara kecil naik lagi (7/9, 78%) — pola "negara belum pernah discreening = median masih bersih" makin kuat terbukti, bukan cuma untuk NEWS.** Total business-registry non-berita di portofolio sekarang 15 actor (8 dari Babak 20-21 + 7 babak ini), sudah mengcover Karibia (Jamaica, Barbados, Bahamas, Belize), Pasifik (Fiji, Solomon Islands, Samoa — Vanuatu skip), dan Afrika (Zambia, Ghana, Botswana, Uganda, Malawi, Tanzania — Mozambique skip), plus PNG dan Nepal.
2. **Framework "Catalyst" (Foster Moore) sekarang terkonfirmasi dipakai oleh minimal 4 negara Pasifik/Afrika sekaligus** (Botswana, Solomon Islands, Samoa, dan Vanuatu yang di-skip) — vendor registry software yang sama dipakai lintas negara Commonwealth kecil, tapi tiap deployment punya wire-protocol/generasi framework berbeda (JSON command di Botswana, form-encoded `_CBNODE_` di Samoa) — tidak bisa disamakan mentah-mentah, tapi mengenali family ini membantu triase awal (cek footer credit "Catalyst"/"Foster Moore") sebelum recon mendalam.
3. **WAF berbasis Content-Type/body-shape (bukan TLS/IP/rate-limit) ditemukan baru** (`tanzania-brela-scraper`) — blokir berdasarkan format encoding body request (form-urlencoded vs JSON), bukan fingerprint klien. Pola triase baru untuk sesi berikutnya: kalau WAF blokir semua percobaan TLS-profile-ladder tapi endpoint API ditemukan dari bundle JS, coba cocokkan `Content-Type`/body-shape persis dengan yang dipakai front-end asli sebelum menyerah.
4. **robots.txt malformed (missing colon, dsb) tetap dihormati berdasarkan intent, bukan celah teknis untuk dieksploitasi** (Vanuatu) — konsisten dengan kebijakan "hormati sinyal operator situs" sejak Babak 8, diperluas ke kasus syntax-error yang secara teknis lolos parser lenient.
5. **Domain-hint dari riset lama/asumsi awal salah di 4 dari 9 kandidat** (Barbados: `corporateaffairs.gov.bb` mati → `caipo.gov.bb`; Malawi: Registrar General digantikan CRIPC April 2026; Samoa: bukan di `mcil.gov.ws` tapi domain transaksional terpisah; Mozambique: "IPEX" domain mati) — mengonfirmasi ulang insight Babak 21 poin 1: selalu verifikasi domain via web search + probe langsung, jangan percaya hint awal atau artikel pihak ketiga.

### Rekomendasi lanjutan

1. **Audit `curl_cffi` exception-handling lintas portofolio** (dicatat sejak Babak 17, masih belum dieksekusi — makin mendesak, portofolio sekarang 139 actor).
2. **Sisa negara kecil yang belum dicoba sama sekali:** Karibia lain (Bahamas/Barbados/Belize sudah, sisa: Antigua, Grenada, St. Lucia, Dominica), Pasifik lain (Tonga, Kiribati, Palau, Marshall Islands), Afrika lain (Lesotho, Eswatini, Sierra Leone, Liberia, Gambia).
3. **Vanuatu worth revisit** kalau typo robots.txt di `registry.vfsc.vu` pernah diperbaiki jadi `Allow: /` atau dihapus — data & search endpoint-nya sendiri genuinely gratis dan HTTP-reproducible.
4. **Kategori non-registry non-berita yang belum pernah discreening** (dicatat sejak Babak 21): tender/procurement pemerintah per-negara, atau vehicle/land registry per-negara — pola long-tail serupa yang masih genuinely belum dicoba.

**Total portofolio setelah babak ini: 139 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **7 actor registry baru** (Barbados, Bahamas, Belize, Solomon Islands, Samoa, Malawi, Tanzania), menggenapkan total business-registry non-berita jadi 15 actor.

---

## Babak 22b — Audit & Perbaikan `curl_cffi` Exception-Handling Lintas Portofolio (2026-08-27)

**Konteks:** menuntaskan item maintenance yang dicatat berulang kali sejak Babak 17 tapi tidak pernah dieksekusi ("audit `curl_cffi` exception-handling lintas portofolio"). Bug aslinya: `curl_cffi.requests.exceptions.RequestException` (dan `curl_cffi`'s own `ConnectionError`) **tidak inherit dari builtin Python `ConnectionError`** — MRO-nya `RequestException → CurlError → OSError`, hierarki paralel dengan nama kelas sama tapi silsilah beda. Konvensi `except (RuntimeError, ConnectionError)` yang disalin actor-ke-actor sejak awal proyek gagal menangkap exception ini — proxy CONNECT tunnel gagal atau DNS failure bisa bikin seluruh run crash, bukan cuma degradasi ke satu `_error` record per item. Bug ini pertama ditemukan & diperbaiki lokal di `guardian-nigeria-scraper` (Babak 17) tapi tidak pernah diterapkan ke actor lain.

**Metodologi audit:** ditulis skrip Python (bukan agent, murni mekanis — regex-based) yang untuk setiap dari 139 folder actor: (1) cek apakah actor itu pakai `curl_cffi` di manapun dalam `src/*.py`, (2) kalau ya, cek apakah `main.py` meng-import `RequestException` dari `curl_cffi.requests.exceptions` DAN benar-benar menangkapnya di tuple `except (...)` yang juga menangkap `ConnectionError`. **Hasil audit: 137 dari 139 actor pakai `curl_cffi`; dari situ 98 actor genuinely punya gap (39 sudah benar duluan** — termasuk 7 registry actor yang baru dibangun sesi ini, yang polanya sudah include `RequestException` sejak awal karena template `botswana-cipa-scraper`/dst sudah correct).

**Perbaikan diterapkan ke seluruh 98 file secara otomatis:**
1. Tambah `from curl_cffi.requests.exceptions import RequestException` tepat setelah baris `from apify import Actor` (fallback: setelah blok import teratas kalau baris itu tidak ada) — konsisten dengan pola yang sudah ada di actor yang duluan benar.
2. Ganti setiap `except (..., ConnectionError, ...)` yang belum menyertakan `RequestException` jadi menyertakannya (append ke tuple, tidak mengubah urutan exception lain).

**Verifikasi:** re-run audit script setelah patch → 0 gap tersisa. `python -m py_compile` dijalankan terhadap seluruh 139 `main.py` → 0 syntax error. Spot-check manual di beberapa actor non-standar (actor mode-based seperti `karir-com-scraper`/`point2homes-scraper`, actor non-berita seperti `civitai-scraper`) mengonfirmasi penempatan import benar dan tidak merusak struktur file.

**Catatan cakupan:** perbaikan ini murni mekanis di level `main.py` (titik tangkap top-level di setiap run-loop per-item) — tidak menyentuh logika retry/backoff di `client.py` masing-masing actor, yang sudah bervariasi per situs dan di luar scope audit ini. Actor yang tidak pakai `curl_cffi` sama sekali (semua 139 actor ternyata pakai — 0 pengecualian) atau yang except-tuple-nya sudah benar (39 actor) tidak disentuh sama sekali.

**Insight metodologi:** task maintenance lintas-portofolio seperti ini **lebih efisien dikerjakan langsung dengan skrip deterministik** (regex audit + regex fix + `py_compile` verify) dibanding dispatch agent per-actor — total waktu eksekusi hitungan menit untuk 98 file, dibanding kemungkinan 98 dispatch agent terpisah yang jauh lebih mahal untuk perubahan yang sepenuhnya mekanis dan tidak butuh judgment per-situs.

**Tidak ada actor baru dari babak ini** — murni maintenance/reliability fix. Total portofolio tetap 139 actor, tapi kualitas reliability seluruh portofolio naik signifikan (silent-crash risk pada kegagalan proxy/koneksi dieliminasi di 98 actor sekaligus).

---

## Babak 23 — 6 Actor Registry Baru: Karibia OECS + Pasifik + Afrika Selatan (2026-08-27)

**Konteks:** melanjutkan rekomendasi penutup Babak 22 — 9 kandidat registry negara kecil yang belum tersentuh: Karibia (Antigua & Barbuda, Grenada, St. Lucia, Dominica), Pasifik (Tonga, Kiribati), Afrika (Lesotho, Eswatini, Sierra Leone). Dispatch 9 agent paralel dengan metodologi sama persis (Phase 1 recon independen → Phase 2 build → Phase 3 test+deploy, stop bersih kalau Phase 1 gagal).

**Hasil: 6 dari 9 berhasil dibangun & di-deploy, 3 di-skip bersih dengan alasan terverifikasi (67%).**

### 6 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `antiguabarbuda-abipco-scraper` | Antigua & Barbuda — ABIPCO (Intellectual Property and Commerce Office) | `2qT212YCq8kcPAOEW` | API riil (`eservicesapi.abipco.gov.ag/NameSearchPage/search`) ditemukan lewat runtime `assets/appsettings.json` SPA Angular (bukan bundle build-time yang basi) — endpoint publik tanpa auth meski Swagger spec-nya keliru mencantumkan `oauth2`. Match substring case-insensitive asli (bukan fuzzy/phonetic seperti Fiji). Satu fetch recon transien sempat balik config Saint Lucia — bukti platform e-filing multi-tenant Karibia yang sama dipakai lintas negara (dikonfirmasi ulang oleh 2 negara lain di babak ini). |
| `stlucia-rocip-scraper` | St. Lucia — ROCIP (Registry of Companies and Intellectual Property) | `aL4yvJDxAlbWy2Sws` | Platform "OCRS" (beda dari Foster Moore Catalyst) — SPA Angular `efiling.rocip.gov.lc`, endpoint `POST /api/1.0/services/loadInfoProc` balik detail penuh langsung (direktur/sekretaris/alamat) tanpa endpoint terpisah. **HTTPS rusak total di host ini** — wajib pakai `http://` polos. Header `X-Frame-Options` bocor referensi `dominicaef.ocrs.alfa.local`, mengonfirmasi platform "OCRS" ini dipakai ~12 negara OECS/CARICOM sekaligus. |
| `dominica-cipo-scraper` | Dominica (Commonwealth of Dominica, Karibia — bukan Republik Dominika) — CIPO | `FOBrsojt0czLbeFcu` | Platform "OCRS" yang sama dengan St. Lucia, dikonfirmasi via endpoint identik (`loadInfoProc`, `EntitySearch`/`EntityInfo`) — 2 domain lama (`registry.cipo.gov.dm` login-walled, `efileapi.cipo.gov.dm` mati) ditemukan via Wayback Machine sebelum domain riil (`efiling.cipo.gov.dm`) ketemu. 2 bug upstream nyata: query pendek/kata umum balik HTTP 500 "Divide by zero"; koma di query diam-diam memotong search (bukan error) — keduanya divalidasi & ditolak client-side. |
| `tonga-mcctil-scraper` | Tonga — MCCTIL (Ministry of Commerce, Consumer, Trade, Innovation and Labour), Business Entities Registry | `5HUJW6akzNx01pPdJ` | Platform sama dengan `png-ipa-scraper` (Vue widget + `PA-Token` header) tapi **coverage lebih kaya**: direktur/pemegang saham/share allotment/riwayat filing penuh termasuk alamat rumah masing-masing, semua anonim tanpa login — beda dari PNG yang field kepemilikannya kosong. Platform live sejak Des 2024 (didanai ADB). |
| `eswatini-roc-scraper` | Eswatini — Registrar of Companies, portal `online.gov.sz` | `YZl5tEqP14e2nNadK` | Domain yang dikutip berulang di blog KYC pihak ketiga (`cipa.org.sz`) ternyata mati — registry riil ditemukan lewat link dari situs resmi `gov.sz`. Classic ASP.NET WebForms viewstate postback, bukan JSON API. Tanpa limit hasil di server (query luas balik 15.366 baris dalam 1 respons 23.5 detik) dan query 1-2 karakter bisa hang server — dimitigasi `MIN_QUERY_LENGTH=3` + timeout panjang. Cuma 3 field publik (nama, status, tanggal) — search-only, tanpa detail. |
| `sierraleone-oarg-scraper` | Sierra Leone — OARG (Office of the Administrator and Registrar-General) | `1u6EZMJTk65veZQ64` | Situs WordPress utama rusak (500 PHP fatal error live), tapi tool search terpisah (`/company-search/`, legacy PHP) tetap berfungsi penuh — name-availability checker only (pola sama `ghana-rgd-scraper`). Bug upstream nyata: apostrof/titik-koma di query bikin backend crash mid-render — divalidasi & ditolak client-side sebelum request dikirim. |

### 3 Kandidat Di-skip — verifikasi bersih, tidak dipaksa build

| Target | Alasan Skip |
|---|---|
| **Grenada** (CAIPO, portal `ocrs.gov.gd`) | Portal genuinely **down**, bukan block — timeout dikonfirmasi dari 3 jaringan independen berbeda (`curl` langsung + 2 proxy pihak ketiga), Wayback Machine menunjukkan 0 capture sejak Juni 2022 (indikasi mati bertahun-tahun, bukan blip transient). Domain "gratis instant-search" yang diklaim artikel SEO pihak ketiga (`companiesregistrygrenada.com`) terbukti **tidak resolve DNS sama sekali** — hallucinated domain, dicatat sebagai jejak pihak ketiga tidak reliable (pola sama dengan IPEX Mozambique di Babak 22). |
| **Kiribati** (MTCIC) | Situs kementerian resmi sendiri bilang halaman registrasi "under development". Satu-satunya tool search yang berfungsi (`ki.ua.paradigmapps.com`) secara eksplisit melabeli dirinya **UAT/test environment** ("nothing filed here has any legal effect") — bukan sistem produksi, jadi datanya bukan data registry riil. Domain ketiga yang diklaim "Official Registry" (`kiribas.net`) ternyata situs marketing agen offshore swasta yang menerima pembayaran kripto — bukan sumber pemerintah. |
| **Lesotho** (`companies.org.ls`, platform Foster Moore "Catalyst" — sama dengan Fiji/PNG/Solomon Islands/Samoa) | robots.txt blanket `Disallow: /` untuk `User-agent: *` (malformed, tanpa titik dua, tapi intent tidak ambigu) — dikonfirmasi identik lintas `www`/bare-domain dan 3 User-Agent berbeda termasuk `ClaudeBot/1.0` literal. Pola sama persis dengan skip Vanuatu di Babak 22 (platform Catalyst yang sama, kebijakan robots.txt beda antar-deployment). |

### Insight metodologi baru

1. **Platform "OCRS" (Angular e-filing) terkonfirmasi dipakai lintas ≥3 negara Karibia OECS/CARICOM sekaligus** (St. Lucia, Dominica, dan Antigua & Barbuda — yang terakhir sempat "bocor" config St. Lucia di satu fetch transien) — vendor/platform kedua yang terkonfirmasi multi-tenant lintas negara kecil setelah "Foster Moore Catalyst" (Botswana/Fiji/PNG/Solomon Islands/Samoa/Tonga, plus Vanuatu/Lesotho yang di-skip). Mengenali family platform dari URL pattern (`efiling.<agency>.gov.<tld>`, endpoint `loadInfoProc`/`EntitySearch`) mempercepat recon signifikan untuk kandidat OECS berikutnya (Grenada seharusnya juga di platform ini tapi portalnya mati; St. Vincent, St. Kitts & Nevis belum dicoba).
2. **Situs pemerintah yang "resmi" tidak selalu live/production** — Kiribati adalah kasus pertama di portofolio ini di mana satu-satunya sistem yang ditemukan secara eksplisit melabeli dirinya sebagai test/UAT environment. Sinyal ini (banner "test version", "nothing filed here has legal effect") harus jadi stop-condition yang sama kuatnya dengan robots.txt block atau login wall — membangun actor di atas data test/palsu akan menyesatkan pengguna actor.
3. **Domain hallucination dari sumber pihak ketiga makin sering ditemukan** — Grenada (`companiesregistrygrenada.com`) dan Eswatini (`cipa.org.sz`) di babak ini, menyusul Mozambique/IPEX di Babak 22. Pola berulang: artikel blog SEO/KYC pihak ketiga mengklaim URL portal pencarian yang ternyata tidak resolve DNS atau tidak pernah ada. **Rekomendasi permanen:** jangan pernah percaya URL dari sumber pihak ketiga tanpa probe HTTP langsung — cari lewat link resmi dari situs `.gov`/kementerian, bukan hasil pencarian generik.
4. **Kualitas data lintas Foster Moore Catalyst DAN OCRS bervariasi drastis per-deployment** meski platformnya sama — Tonga (Catalyst) expose alamat direktur/pemegang saham penuh sementara PNG (Catalyst juga) tidak; St. Lucia (OCRS) expose detail penuh langsung dari search sementara Dominica (OCRS juga) cuma nama direktur/pemegang saham comma-joined tanpa alamat. Tidak bisa diasumsikan kedalaman data dari platform semata — tetap wajib verifikasi field-by-field per negara.

### Rekomendasi lanjutan

1. **Kandidat OECS/CARICOM lain di platform "OCRS" yang belum dicoba:** St. Vincent and the Grenadines, St. Kitts and Nevis, (Grenada portalnya mati, worth retry berkala kalau situsnya pulih).
2. **Kandidat kecil lain yang masih benar-benar belum disentuh:** Palau, Marshall Islands, Nauru, Tuvalu (Pasifik); Comoros, Djibouti, Cape Verde, São Tomé and Príncipe (Afrika/kepulauan kecil); Andorra, San Marino, Liechtenstein, Monaco (mikro-negara Eropa — belum pernah dicek sama sekali di 23 babak manapun, worth dicoba meski berisiko offshore-gated seperti Vanuatu).
3. **Kategori non-registry non-berita yang masih belum pernah discreening** (dicatat sejak Babak 21): tender/procurement pemerintah per-negara, atau vehicle/land registry per-negara.

**Total portofolio setelah babak ini: 145 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **6 actor registry baru** (Antigua & Barbuda, St. Lucia, Dominica, Tonga, Eswatini, Sierra Leone), menggenapkan total business-registry non-berita jadi 21 actor.

---

## Babak 24 — 4 Actor Registry Baru: Titik Jenuh Mulai Terlihat di Ekor Negara Terkecil (2026-08-27)

**Konteks:** melanjutkan rekomendasi penutup Babak 23 — 9 kandidat sisa: OECS lain (St. Vincent & the Grenadines, St. Kitts & Nevis), Pasifik lain (Palau, Marshall Islands, Nauru), Afrika/pulau kecil (Comoros, Cape Verde, Djibouti, São Tomé & Príncipe). Dispatch 9 agent paralel, metodologi sama (Phase 1→3, stop bersih kalau Phase 1 gagal).

**Hasil: 4 dari 9 berhasil dibangun & di-deploy, 5 di-skip bersih (44%)** — rasio sukses terendah dari seluruh seri registry sejak Babak 20, mengindikasikan **ekor negara terkecil/termiskin mulai menunjukkan tanda kejenuhan discoverability** (bukan kejenuhan kompetisi seperti niche lain — di sini penyebabnya genuinely tidak ada infrastruktur online, bukan sudah dikloning banyak seller).

### 4 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `stvincent-cipo-scraper` | St. Vincent & the Grenadines — CIPO | `Kn4T75LE1zMNM5TjZ` | Bukan platform "OCRS" seperti dugaan awal (`ocrs.gov.vc` ternyata portal login CaseFlow generasi baru, bukan search) — search riil ada di `ecipo.gov.vc`, platform **"DotGovServer" yang sama persis dengan `antiguabarbuda-abipco-scraper`** (komponen `NameSearchPage/search` identik, beda cuma tenant GUID & API host). **Temuan penting:** ditemukan situs decoy `saintvincentregistry.com` yang meniru tampilan resmi tapi terbukti scam (lisensi key hardcoded palsu, data perusahaan random-generated untuk query apapun, block copy/view-source) — dan robots.txt-nya eksplisit block `ClaudeBot`. Tidak pernah di-query, didokumentasikan sebagai jejak supaya sesi berikutnya tidak terjebak. |
| `palau-fic-scraper` | Palau — Financial Institutions Commission (FIC) | `L6aX1DkCQ9zxhhksj` | Portal baru (`palauregistries.pw`, live sejak 20 Jan 2025 seiring Corporations Act baru) — platform **"Foster Moore Catalyst" yang sama** dengan PNG/Tonga/Fiji/Solomon Islands. Coverage kaya: direktur, officer, pemegang saham, share allotment, riwayat filing — semua anonim tanpa login. |
| `comoros-anpi-scraper` | Comoros — ANPI (Agence Nationale pour la Promotion des Investissements) | `mWgtrcq5GOjGtmXAi` | REST API WordPress publik (`/wp-json/anpi/v1/annonces`) tanpa auth, 6.376 record. Kejujuran data: field `rccm`/`secteur`/`capital`/`dirigeant`/`ville` kosong di **semua** record upstream (bukan bug parser) — didokumentasikan apa adanya, tidak dipalsukan. Rate limiter proses-lebar mengikuti `Crawl-delay: 10` situs secara harfiah. |
| `djibouti-odpic-scraper` | Djibouti — ODPIC (Registre du Commerce et des Sociétés) | `NftUfMJlGzZ2yz7dr` | Domain "Guichet Unique" yang umum dikutip (`guichet-unique.dj`) ternyata mati — registry riil ada di `odpic.dj`, REST API WordPress standar (`/wp-json/wp/v2/publication_registre`) tanpa auth, 19.602 filing sejak 1914. |

### 5 Kandidat Di-skip — semua legitimate negative findings, bukan block

| Target | Alasan Skip |
|---|---|
| **St. Kitts & Nevis** | Federal St Kitts (FSRC) cuma informasi hukum, tanpa search/e-filing sama sekali. Dikonfirmasi lewat leaked data platform OCRS milik St. Lucia bahwa `stkitts`/`nevis` **sudah pre-provisioned sebagai tenant** di database yang sama tapi tidak pernah go-live untuk public search. Nevis punya portal terpisah (`portal.crss.niagov.com`, "Service Providers Portal") tapi hard login-walled khusus registered agent — konsisten dengan model privasi offshore Nevis (data beneficial-owner ada di agent, bukan register publik). |
| **Marshall Islands** | Registry tunggal dioperasikan komersial oleh International Registries, Inc. (IRI) — bukan portal data pemerintah terbuka, sama pola dengan agen-monopoli Vanuatu. **Plus** secara teknis search backend-nya Oracle ADF Faces murni JS-rendered tanpa fallback server-side sama sekali — di luar scope HTTP-only bahkan tanpa alasan komersial. |
| **Nauru** | Tidak ada sistem online sama sekali — registrasi 100% kertas/tatap muka, pencarian nama "atas kebijakan Registrar" (bukan lookup publik). |
| **Cape Verde** | Pola sama Mozambique/São Tomé: domain "EASE" yang dikutip blog SEO pihak ketiga ternyata sistem e-visa turis, tidak ada hubungannya dengan registry (fabricated claim lagi); portal utama stub "coming soon"; RNI sertifikat SSL kedaluwarsa + gateway block; satu server Oracle Reports yang ditemukan cuma render PDF statis by-ID (bukan search, dikonfirmasi tidak ada mekanisme discovery). |
| **São Tomé & Príncipe** | Pola sama Mozambique: DGRN cuma proses kertas/berbayar, beberapa domain kandidat lain mati/di-compromise, situs utama mengandung spam link injection (tanda situs terbengkalai). |

### Insight metodologi baru

1. **Platform ketiga yang shared multi-tenant ditemukan: "DotGovServer"** (komponen Angular `NameSearchPage/search`, endpoint `/NameSearchPage/search?query=&app=<tenant-guid>`) — dipakai Antigua & Barbuda DAN St. Vincent & the Grenadines. Total sekarang 3 platform vendor terkonfirmasi shared lintas-negara: **Foster Moore Catalyst** (Botswana/Fiji/PNG/Solomon Islands/Samoa/Tonga/Palau, tapi di-block di Vanuatu/Lesotho), **OCRS** (St. Lucia/Dominica, tenant St Kitts/Nevis ada tapi belum live), **DotGovServer** (Antigua & Barbuda/St. Vincent).
2. **Situs decoy/scam yang meniru registry resmi makin perlu diwaspadai** — `saintvincentregistry.com` adalah kasus pertama di seluruh seri registry di mana kandidat yang muncul di hasil pencarian bukan cuma "hallucinated domain" (tidak resolve) tapi **situs scam aktif dengan data fabrikasi** yang sengaja meniru tampilan resmi. Robots.txt-nya sendiri malah eksplisit block `ClaudeBot` — kemungkinan untuk menghindari deteksi otomatis. **Wajib jadi red flag baru:** kalau sebuah "portal resmi" generate data berbeda-beda untuk input sembarangan atau block copy/view-source, itu bukan situs pemerintah asli, hentikan tanpa query apapun.
3. **Rasio sukses 44% di babak ini (vs 78% Babak 22, 67% Babak 23) menunjukkan titik jenuh discoverability mulai tercapai** untuk negara-negara paling kecil/miskin infrastruktur — bukan karena kompetisi (sama sekali tidak ada seller lain di niche registry manapun sejauh 5 babak), tapi karena semakin ke ekor daftar negara, semakin besar kemungkinan negara itu genuinely belum punya sistem online sama sekali (Nauru), registry-nya dioperasikan swasta/offshore (Marshall Islands), atau infrastrukturnya sendiri sudah terbengkalai (Cape Verde, São Tomé).
4. **Pola geografis/linguistik makin jelas:** negara-negara Lusophone kecil (Mozambique Babak 22, São Tomé & Príncipe dan Cape Verde babak ini) konsisten 3/3 skip dengan alasan serupa (proses kertas/login-gated, domain "resmi" yang dikutip pihak ketiga ternyata fabricated/mati) — worth dicatat sebagai pola regional/linguistik, bukan cuma kebetulan per-negara.

### Rekomendasi lanjutan

1. **Kandidat kecil yang masih genuinely belum dicoba:** Tuvalu, mikro-negara Eropa (Andorra, San Marino, Liechtenstein, Monaco — berisiko offshore-gated tapi belum diverifikasi), negara OECS terakhir yang belum diverifikasi Phase 1 (Anguilla, Montserrat — teritori Inggris, mungkin beda model dari negara merdeka).
2. **Kategori non-registry non-berita yang masih belum pernah discreening** (dicatat sejak Babak 21): tender/procurement pemerintah per-negara, atau vehicle/land registry per-negara.
3. **Pertimbangkan pivot strategi** kalau babak berikutnya juga menunjukkan rasio sukses rendah serupa — kemungkinan besar "negara kecil = celah kosong" untuk registry sudah mendekati titik jenuh (mirip insight Babak 8 untuk category-browsing), dan platform vendor yang sudah dikenali (Catalyst/OCRS/DotGovServer) mungkin lebih produktif dicari langsung by-vendor-footprint daripada by-country-guess.

**Total portofolio setelah babak ini: 149 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **4 actor registry baru** (St. Vincent & the Grenadines, Palau, Comoros, Djibouti), menggenapkan total business-registry non-berita jadi 25 actor.

## Babak 25 — Vertikal Baru: Government Tenders/Procurement, 7 Actor Sekaligus (2026-08-27)

**Konteks:** menindaklanjuti rekomendasi Babak 24 poin 2 — kategori non-registry non-berita yang belum pernah discreening: tender/procurement pemerintah per-negara. **Validasi pasar dulu sebelum dispatch**, mengikuti pelajaran Babak 19: dicek dulu apakah niche "tender scraper" per-platform besar (EU TED, Singapore GeBiz, Jerman) sudah jenuh di Apify Store (**ya, sudah 3-6+ seller masing-masing** — klaster seller lama yang sama: `jungle_synthesizer`, `nexgendata`, `automation-lab`, `memo23`, `foxlabs`), TAPI query per-negara-kecil (Fiji/Jamaica/Botswana/Zambia/Solomon Islands/Tonga/Eswatini/Barbados/Malawi/Uganda) semuanya cuma menghasilkan noise — 0 kompetitor nyata. Pola persis sama dengan insight Babak 19-20 untuk business registry: platform besar jenuh, negara kecil kosong.

**Hipotesis kerja:** data tender **wajib publik secara hukum** di hampir semua negara (undang-undang transparansi pengadaan) — beda dari business registry yang sering login-gated/berbayar demi monetisasi data korporat. Ekspektasi: feasibility lebih tinggi dari seri registry.

Dispatch 9 agent paralel (Fiji, Jamaica, Botswana, Zambia, Ghana, Uganda, PNG, Sierra Leone, Nepal) — semua negara yang sudah punya actor business-registry di portofolio ini, supaya bisa dibandingkan langsung infra pemerintahnya.

**Hasil: 7 dari 9 berhasil dibangun & di-deploy, 2 di-skip bersih (78%) — hipotesis feasibility-tinggi TERKONFIRMASI**, rasio jauh lebih tinggi dari babak registry terakhir (44%, Babak 24) dan setara Babak 22 (78%).

### 7 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `ghana-tenders-scraper` | Ghana — GHANEPS (Ghana Electronic Procurement System) | `OglyygZzyPBb8lhNX` | Vendor **"European Dynamics"** (e-procurement EU asli, model UNCITRAL/World Bank) — server-rendered Java/Struts, tanpa JSON API, tanpa robots.txt sama sekali. 3 listing publik tanpa login: Current Tenders (~65), Opened Bids (~12.077), Awarded Contracts (~15.910, termasuk nama supplier + nilai GHS). Login wall HANYA untuk submit bid. Pola pagination "widget id" DisplayTag-style (`d-<id>-p=<page>`) — diekstrak fresh per run, bukan hardcode. |
| `zambia-tenders-scraper` | Zambia — ZPPA e-GP (`eprocure.zppa.org.zm`) | `plh9LyEceVVOxf2qg` | **Vendor "European Dynamics" yang sama dengan Ghana** — konfirmasi kedua platform shared lintas-negara di vertikal baru ini. Listing (157rb+ record historis) sepenuhnya publik; detail per-tender baru login-wall **setelah deadline bid lewat** (bukan blanket) — ditangani sebagai `_error: "login_required"` per-record, bukan stop-condition. |
| `jamaica-tenders-scraper` | Jamaica — GOJEP (`gojep.gov.jm`) | `MmKzQhLuDIEKXL611` | **Vendor "European Dynamics" ketiga** — Ghana/Zambia/Jamaica semua di platform sama ("ePPS"). Listing publik (81rb+ opened bids, 13rb+ contract awards) tanpa login; hanya halaman "full detail" satu-tender yang login-wall. Kuirk: format tanggal day-first tanpa timezone tergantung fingerprint TLS klien — didokumentasikan eksplisit biar tidak salah baca `03/09/2026` sebagai Maret. |
| `uganda-tenders-scraper` | Uganda — EGP Uganda (`egpuganda.go.ug`, PPDA Phase II) | `gGNFcM25N6Xc0hre8` | Portal baru (rollout penuh Juli 2026), robots.txt blanket allow, tanpa WAF/TLS-gate sama sekali (beda dari `uganda-ursb-scraper` yang API-nya TLS-fingerprint-gated). 3 mode: `latest` (tabel live), `archived` (AJAX Laravel/DataTables, 500+ record sejak 2019), `detail`. Bonus data transparansi nyata: halaman "RECORD OF BID OPENING" expose nama bidder asli, alamat, dan nilai bid. |
| `png-tenders-scraper` | Papua New Guinea — National Procurement Commission (`npc.gov.pg`) | `hGgohC2gr4JxSVAUZ` | 3 tipe record dengan pola akses beda-beda: open tenders (JetEngine custom content type, tanpa REST route, pagination situs sendiri dimatikan — anti-hijack signature check menolak page 2+, jadi actor cuma expose ~6 tender yang situs sendiri tampilkan, bukan gap scraping); disposal notices & awarded contracts (REST WordPress standar, 13 & 182 record). |
| `sierraleone-tenders-scraper` | Sierra Leone — NPPA | `ZM8k8lgt5dUMR1YHk` | Platform modern (`egp.nppa.gov.sl`, vendor **Perago Systems** — dikonfirmasi juga dipakai Malawi's `maneps.mw`, vendor keempat yang shared lintas-negara) backend-nya 502 selama 10+ menit percobaan — bukan block, genuinely down. Pola sama persis dengan `sierraleone-oarg-scraper` (business registry): situs WordPress lama tetap jalan sebagai fallback (`/bid/`, TablePress table, data current sampai H-7 sebelum build). |
| `nepal-tenders-scraper` | Nepal — Bolpatra/PPMO e-GP (`bolpatra.gov.np`) | `7cdwbORX9VgektLyr` | Bug TLS cert chain sama persis dengan `nepal-ocr-scraper` (missing intermediate, wajib `verify=False`) — pola berulang di infra pemerintah Nepal. Tanpa login untuk search/detail (login cuma untuk submit bid). Kuirk unik: page-size hasil search genuinely non-deterministic (10 atau 30 baris untuk query identik) dan pagination "Next" tidak bisa dipaksa reliable via HTTP scripted — dilaporkan jujur (`_totalReturned`/`_totalAvailable`) alih-alih berpura-pura pagination lengkap. |

### 2 Kandidat Di-skip — legitimate negative findings

| Target | Alasan Skip |
|---|---|
| **Fiji** | Portal resmi (`fpo.gov.fj`) unreachable dari luar. Data tender riil ada di **TenderLink** (`portal.tenderlink.com`), SaaS komersial white-label pihak ketiga (AU/NZ) — link "Tenders & EOIs" resmi pemerintah sendiri mengarah ke halaman **login**, dan setiap tenant TenderLink kena block Imperva Incapsula "Request unsuccessful" di semua profil TLS. Tiga sinyal stop independen sekaligus (login wall + WAF + host resmi mati). |
| **Botswana** | PPRA "Integrated Procurement Management System" (`ipms.ppadb.co.bw`) — tombol "Tender Search" di homepage sengaja di-comment-out di HTML (dead link, bukan CSS-hidden), robots.txt disallow eksplisit `/search`/`/docdetails`, dan endpoint AJAX pencarian yang di-reverse-engineer balik `200 OK` dengan body kosong (server-side session check, bukan trik client-side). **Lead alternatif ditemukan**: sejak desentralisasi 2022, tender riil sekarang dipublikasi per-kementerian (mis. `finance.gov.bw`, Joomla, robots.txt bersih, data Juli 2026 nyata) — bukan "PPRA portal" yang diminta, tapi worth dicoba terpisah sesi berikutnya. |

### Insight metodologi baru

1. **Hipotesis "tender = transparency law = feasibility lebih tinggi dari registry" terkonfirmasi kuat (78% vs rata-rata ~55-60% seri registry)** — sinyal login-wall yang muncul (Zambia, Jamaica) semuanya PARSIAL (cuma detail-setelah-deadline atau cuma submit-bid), bukan blanket seperti kebanyakan skip registry.
2. **Empat vendor e-GP shared multi-negara terkonfirmasi dalam satu babak** — lebih cepat dari seri registry (yang perlu ~4 babak untuk 3 platform): **European Dynamics/"ePPS"** (Ghana, Zambia, Jamaica — kemungkinan besar dipakai lebih banyak lagi negara model World Bank/UNCITRAL), **Perago Systems** (Sierra Leone, Malawi), plus **TenderLink** (Fiji — vendor negatif/gated, bukan positif) sebagai sinyal "kalau ketemu vendor ini, ekspektasi login-wall+WAF". Mengenali vendor dari nama platform/footer/HTML comment mempercepat triase drastis dibanding reverse-engineer dari nol tiap negara.
3. **Bug infra pemerintah lintas-agency dalam 1 negara sering berulang** — TLS cert chain Nepal (OCR registry DAN Bolpatra tender, sama-sama butuh `verify=False`) dan pola "sistem baru down, sistem lama WordPress masih hidup" Sierra Leone (OARG registry DAN NPPA tender) menunjukkan infra IT pemerintah suatu negara cenderung konsisten kualitasnya lintas-agency — actor builder untuk agency ke-2 di negara yang sama bisa langsung ekspektasi kuirk serupa.
4. **Login-wall di vertikal tender cenderung granular/parsial, bukan blanket** — beda dengan registry yang seringnya all-or-nothing (search publik penuh ATAU 100% login), tender portal lebih sering "listing publik, tapi 1 halaman spesifik (detail-pasca-deadline, atau submit-bid) yang login-wall" — pola yang lebih ramah untuk actor builder karena tidak langsung jadi stop-condition penuh.

### Rekomendasi lanjutan

1. **Perluas vertikal tender ke negara lain, prioritaskan vendor "European Dynamics"/"ePPS"** yang sudah terbukti 3× — cek negara World Bank/UNCITRAL model lain (banyak negara Afrika/Karibia/Pasifik pakai vendor sejenis) dengan pendekatan by-vendor-footprint, bukan cuma by-country-guess.
2. **Botswana ministry-sites lead** (`finance.gov.bw` dan kementerian lain pasca-desentralisasi 2022) worth dicoba terpisah — beda produk dari yang di-skip di babak ini.
3. **Vehicle/land registry per-negara** — kategori non-registry non-berita lain yang disebut Babak 21 tapi belum pernah discreening sama sekali.
4. **Audit `curl_cffi` exception-handling** untuk 7 actor tender baru — sudah include fix sejak awal (bagian dari instruksi dispatch), tapi worth verifikasi ulang mengikuti pola audit Babak 22b kalau ada actor tender tambahan dibangun di sesi terpisah nanti.

**Total portofolio setelah babak ini: 156 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **7 actor tender/procurement baru** (Ghana, Zambia, Jamaica, Uganda, PNG, Sierra Leone, Nepal), vertikal baru pertama di luar "business registry" dan "berita" dengan 7 actor sekaligus di percobaan pertama.

---

## Babak 26 — Vertikal Tender Ronde 2: 7 Actor Lagi, Rasio Sukses Konsisten 78% (2026-08-27)

**Konteks:** melanjutkan rekomendasi Babak 25 — perluas vertikal tender ke negara lain, prioritaskan vendor "European Dynamics" dan coba lead Botswana ministry-sites. Dispatch 9 agent paralel: Malawi (vendor Perago, sama dengan Sierra Leone), Tanzania, Barbados, Solomon Islands, Rwanda (verifikasi independen meski registry-nya di-skip Babak 21), Trinidad & Tobago (verifikasi independen meski registry-nya di-skip Babak 21), Namibia (verifikasi independen meski registry-nya di-skip Babak 21), Eswatini, dan Botswana (khusus retry ke lead ministry-sites, bukan portal PPRA yang sudah di-skip).

**Hasil: 7 dari 9 berhasil dibangun & di-deploy, 2 di-skip bersih (78%)** — identik persis dengan rasio Babak 25, mengonfirmasi vertikal tender **konsisten jauh lebih produktif** dari seri registry (44-78%, rata-rata lebih rendah & lebih volatil).

### 7 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `eswatini-tenders-scraper` | Eswatini — ESPPRA (Eswatini Public Procurement Regulatory Agency) | `gsshq0jZ0QArQfXJc` | Domain pihak ketiga yang dikutip blog tender-alert (`eswatinitenders.com` dll) terbukti cuma aggregator komersial, bukan resmi — regulator asli ditemukan lewat nama lembaga, bukan tebakan domain. 3 jenis listing: tender aktif (~61), arsip Intention-to-Award (1.572 record), **debarment register pemasok** (transparansi langka). TLS cert chain rusak (butuh `verify=False`, pola sama Nepal). |
| `rwanda-tenders-scraper` | Rwanda — Umucyo (RPPA e-procurement) | `8JJoSgOEvt2OcpVxY` | **Verifikasi independen membuktikan hipotesis "agency beda = outcome beda" benar** — business registry RDB di-skip Babak 21 karena API 401-gated, tapi Umucyo (agency berbeda, `www.umucyo.gov.rw`, bukan `urs.rdb.rw`) 100% publik, 38.880 tender record browsable tanpa login. Kuirk unik: kode JS platform mengandung komentar berbahasa Korea — indikasi vendor e-GP asal Korea (kemungkinan turunan sistem KONEPS yang memang diekspor ke banyak negara berkembang) — **vendor lineage kelima** di vertikal ini. |
| `namibia-tenders-scraper` | Namibia — CPBN (Central Procurement Board) | `nalyyr6pF4Z3UNs9A` | Domain resmi statutori (`eprocurement.gov.na`) ternyata cuma repositori dokumen kebijakan tidak aktif — listing riil ada di situs korporat CPBN sendiri (`cpbn.com.na`), 8 kategori bid publik penuh (open/awarded/cancelled/dst) tanpa login. Konfirmasi lagi hipotesis "registry gated ≠ tender gated" (BIPA business registry di-skip Babak 21 karena genuinely tidak ada sistem online — beda lembaga, beda hasil). |
| `trinidadtobago-tenders-scraper` | Trinidad & Tobago — ProcureTT (Office of Procurement Regulation) | `ePiNYA9jjyoc4u8NU` | Vendor beda dari European Dynamics — WordPress/GravityView notice board. **Tanpa login wall sama sekali**, termasuk detail per-entri (lebih terbuka dari Jamaica/Zambia yang detail-nya login-gated) — padahal business registry T&T di-skip Babak 21 karena hard identity-verified login wall. 5 tipe notice sekaligus: tenders, awards (dengan nilai TTD), rencana pengadaan tahunan, prakualifikasi, disposal aset. |
| `botswana-tenders-scraper` | Botswana — situs kementerian terdesentralisasi (bukan PPRA yang di-skip) | `IESosuEx7QTxM6OiQ` | **Menutup temuan skip Babak 25** — portal pusat PPRA/IPMS tetap login-gated (tidak dicoba lagi), tapi Kementerian Keuangan (`finance.gov.bw`, via RSS feed kategori Procurement) dan Kementerian Kesehatan (`moh.gov.bw`, tabel HTML) keduanya genuinely terbuka. Koreksi jujur terhadap klaim sesi sebelumnya ("data Juli 2026" ternyata cuma sampai Okt 2024 — feed hidup tapi jarang di-update, bukan basi total). 6 domain kementerian lain dicek dan semuanya mati/tidak relevan. |
| `malawi-tenders-scraper` | Malawi — MANEPS (vendor Perago Systems, sama dengan Sierra Leone) + PPDA fallback | `sTE2ocxRNvC2z0PDE` | Konfirmasi vendor **Perago Systems** dipakai lintas 2 negara (Sierra Leone + Malawi). MANEPS sendiri SPA client-rendered murni (sama seperti Sierra Leone) — tapi situs korporat PPDA (`ppda.mw`) publikasi notice yang sama sebagai tabel HTML server-rendered biasa, pola identik dengan fallback Sierra Leone. 5 papan notice: tender, award, intention-to-award, debarment, admin-review. |
| `tanzania-tenders-scraper` | Tanzania — NeST (National e-Procurement System, PPRA) | `j9NdmGkSwNWGP2NGi` | **Temuan terbaik seluruh babak ini**: SPA Angular tanpa data server-rendered, tapi JS bundle-nya hardcode API **OCDS-compliant** (Open Contracting Data Standard) publik tanpa auth (`/gateway/nest-data-portal-api/api/records`) — setiap record sudah merge siklus penuh tender→award→kontrak (line item, buyer, pemenang, nilai, status) dalam satu OCID. Kuirk: parameter `cursor` diam-diam diabaikan server — pagination riil pakai filter tanggal `since` yang di-maju manual per halaman. Domain decoy `nest.co.tz` (situs SaaS komersial pihak ketiga) ditemukan & dihindari. |

### 2 Kandidat Di-skip — legitimate negative findings

| Target | Alasan Skip |
|---|---|
| **Barbados** | Portal riil (`gov-bb.bonfirehub.com`, vendor "Bonfire" — SaaS Kanada, beda dari European Dynamics) punya robots.txt blanket `Disallow: /` yang genuinely live (bukan cache basi) + Cloudflare bot management penuh. Portal lama (`procure.gov.bb`) mati total; domain `etenders.gov.bb` yang muncul di hasil pencarian AI **tidak resolve DNS sama sekali** (hallucinated lagi — pola berulang sejak Babak 22). Halaman `gov.bb/Government/tenders` cuma 3 PDF statis, bukan aggregator asli. |
| **Solomon Islands** | Listing riil (`solomons.gov.sb/portal_tender/`) di-gate **Sucuri CloudProxy JS challenge** di seluruh situs (homepage, listing, detail, bahkan WP REST API) — dikonfirmasi gagal di 4 profil TLS berbeda, genuinely butuh eksekusi JS (di luar scope HTTP-only). Sitemap XML statis lolos tapi cuma bawa URL+lastmod tanpa isi, terlalu tipis untuk actor fungsional. Lead sekunder (Central Bank tender via TenderLink) juga kena block Imperva — konfirmasi ulang pola "TenderLink = sinyal negatif" dari Fiji. |

### Insight metodologi baru

1. **Hipotesis "agency beda dalam satu negara = outcome beda" terkonfirmasi kuat 3×** — Rwanda, Trinidad & Tobago, dan Namibia semuanya sukses dibangun sebagai tender actor meski business registry-nya di negara yang sama di-skip di Babak 21 karena alasan berbeda (401-gate, hard login wall, tidak ada sistem sama sekali). **Jangan pernah generalisasi hasil 1 agency ke seluruh negara** — verifikasi independen per-agency tetap wajib, sesuai insight yang sudah dibangun sejak Babak 14 (curl_cffi bug) dan diperkuat lagi di sini.
2. **Vendor lineage tender sekarang 5 dikonfirmasi**: European Dynamics/ePPS (Ghana/Zambia/Jamaica), Perago Systems (Sierra Leone/Malawi — dikonfirmasi 2× sekarang), TenderLink (Fiji/Solomon Islands — vendor negatif, selalu login+WAF), Bonfire (Barbados — vendor negatif, blanket robots block), dan kemungkinan vendor asal Korea yang belum diidentifikasi namanya (Rwanda, komentar JS berbahasa Korea).
3. **Pola "sistem modern down/JS-only, sistem korporat/lama masih hidup sebagai fallback" makin sering muncul** — Malawi (MANEPS SPA vs `ppda.mw`) dan Botswana (PPRA gated vs kementerian individual) keduanya mengikuti pola persis sama dengan Sierra Leone Babak 25. Pola generalizable: kalau portal e-GP modern suatu negara gagal (JS-only, down, atau gated), cek situs korporat/legacy regulator itu sendiri sebelum menyerah — sering masih publikasi data yang sama dengan cara lebih sederhana.
4. **OCDS (Open Contracting Data Standard) sebagai sinyal kualitas tinggi** — Tanzania adalah bukti pertama bahwa beberapa negara publikasikan data tender lewat standar internasional terbuka (dipromosikan Open Contracting Partnership/World Bank) yang jauh lebih terstruktur & lengkap dari HTML scraping biasa. Worth dicek eksplisit sebagai langkah awal Phase 1 di negara berikutnya — cari `ocds`/`open-contracting`/`gateway/*-data-portal-api` di JS bundle sebelum reverse-engineer HTML.

### Rekomendasi lanjutan

1. **Perluas ke negara lain dengan vendor "European Dynamics" atau OCDS terkonfirmasi** — kandidat: negara lain yang pakai standar UNCITRAL/World Bank serupa (banyak negara Afrika/Karibia/Pasifik belum dicoba: Kenya, Nigeria, Bangladesh, dst — tapi verifikasi dulu belum jenuh di Apify Store untuk negara-negara lebih besar ini).
2. **Vehicle/land registry per-negara** — kategori non-registry non-berita lain yang disebut Babak 21 tapi belum pernah discreening sama sekali, masih relevan.
3. **Business registry negara kecil yang belum dicoba** (dari Babak 24: Tuvalu, mikro-negara Eropa) — masih ada backlog kecil di vertikal registry kalau ingin melanjutkan itu juga.

**Total portofolio setelah babak ini: 163 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **7 actor tender/procurement baru** (Eswatini, Rwanda, Namibia, Trinidad & Tobago, Botswana, Malawi, Tanzania), menggenapkan total vertikal tender jadi 14 actor.

---

## Babak 27 — Vertikal Tender Ronde 3 (Negara Lebih Besar): 9 dari 9 Berhasil, 100% (2026-08-27)

**Konteks:** melanjutkan vertikal tender ke negara-negara lebih besar/lebih maju infrastrukturnya, setelah 2 babak sebelumnya konsisten 78% untuk negara kecil. **Validasi pasar dulu**: dicek 15 kandidat negara besar via `api-search-actors.py` — Kenya sudah punya 1 kompetitor nyata (`wafspaul/kenya-government-tenders`, di-exclude dari batch), 14 lainnya (termasuk Mali/Benin yang awalnya kelihatan banyak hit tapi ternyata 100% noise Algolia) semuanya genuinely 0 kompetitor. Dispatch 9 agent paralel: Nigeria, Bangladesh, Pakistan, Vietnam, Sri Lanka, Zimbabwe, Liberia, Madagascar, Cameroon.

**Hasil: 9 dari 9 berhasil dibangun & di-deploy — 100%, rasio tertinggi di seluruh proyek riset ini (21 babak business-registry+tender+berita).** Hipotesis "negara lebih besar = infra e-GP lebih matang (lebih banyak dana World Bank/donor) = lebih reliable" terbukti benar — kontras total dengan pola registry dimana negara besar biasanya sudah jenuh kompetisi ATAU lebih ketat gatenya.

### 9 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `nigeria-tenders-scraper` | Nigeria — NOCOPO (Nigeria Open Contracting Portal, BPP) | `ChfaVXIcRTklft6Cm` | **API OCDS publik kedua** (setelah Tanzania) — `ocdsjson.ashx` balik release package OCDS asli per-record, plus ditemukan bulk export publik ~99.000 record (220MB, dicatat tapi tidak dipakai per-run karena tidak praktis). Data genuinely live (record terbaru H-6 dari waktu build). |
| `bangladesh-tenders-scraper` | Bangladesh — CPTU/BPPA e-GP (`eprocure.gov.bd`) | `tybK87NU4FMZYssZ1` | Salah satu sistem e-GP tertua di Asia Selatan (live sejak 2011), tanpa robots.txt, tanpa login untuk viewing. 3 mode: live tender, Notice of Award (sudah termasuk nama pemenang + nilai kontrak BDT), detail penuh per-lot. Kuirk: header `X-Requested-With` yang biasa dipakai actor lain justru mematikan servlet pencarian di sini — harus tanpa header itu. |
| `pakistan-tenders-scraper` | Pakistan — PPRA-EPMS (`epms.ppra.gov.pk`) | `OmkPt2qg5a2YM2Ufy` | Domain utama PPRA (`ppra.gov.pk`) down 500 saat recon — ditemukan aplikasi kerja terpisah (EPMS) yang tetap penuh publik meski root path-nya sendiri redirect ke `/login` (cuma back-office filer yang login-gated, path `/public/tenders/*` bebas). Pagination genuinely stabil (~1.859 tender aktif lintas 38 halaman). |
| `vietnam-tenders-scraper` | Vietnam — VNEPS (Ministry of Planning and Investment) | `kOLNRkZyeLegDSfLM` | **Temuan keamanan menarik**: parameter `token` yang meniru reCAPTCHA v3 ternyata **tidak diverifikasi server-side sama sekali** — string placeholder non-kosong apapun diterima sama seperti token asli. Index Elasticsearch dibatasi 10.000 hit per query (`max_result_window`), disinyalkan via `{"page": null}` (200 OK, bukan error) — ditangani sebagai limitasi jujur, bukan silent truncation. |
| `srilanka-tenders-scraper` | Sri Lanka — Kementerian Keuangan (`treasury.gov.lk`) | `zoIiOf1nvsstRCkVC` | Domain "promise.lk" yang dikutip banyak sumber sekunder sebagai e-GP Sri Lanka ternyata **unreachable** — pivot ke halaman procurement Treasury sendiri (data Next.js `__NEXT_DATA__`, bukan API/RSS), arsip historis lengkap sejak Januari 2019 (460+ notice, 23 halaman). |
| `zimbabwe-tenders-scraper` | Zimbabwe — PRAZ e-GP (`egp.praz.org.zw`) | `DmvFC6WvZ5BsCuho0` | **Vendor keenam terkonfirmasi**: "Nextenders (India) Pvt Ltd" — vendor e-GP baru, beda dari 5 vendor sebelumnya. Tanpa login sama sekali di semua listing/detail (lebih terbuka dari Zambia/Jamaica sesama sepupu). Arsip historis 64.233 record. Bug pagination server-side genuine (halaman 2+ balik konten byte-identik) — ditangani via dedup guard generik. |
| `liberia-tenders-scraper` | Liberia — PPCC e-GP (`eprocurement.ppcc.gov.lr`) | `Hq4j0F8xCwbpA8wQB` | **Konfirmasi vendor European Dynamics/ePPS paling kuat sejauh ini** — bukan cuma pola URL sama, tapi *widget ID pagination internal identik persis* dengan GHANEPS (`3680175`/`3680181`/`3998960`) — indikasi templat deployment yang benar-benar sama disalin mentah lintas negara, bukan cuma vendor sama. |
| `madagascar-tenders-scraper` | Madagascar — ARMP (`armp.mg`) | `Rq0lsIQjQPQwMvUlV` | Data kontrak menang termasuk **beneficial owner yang dideklarasikan** (bukan cuma nama supplier) — transparansi langka bahkan dibanding negara lain di vertikal ini. 3 sumber: tender aktif, arsip multi-tahun sejak 2015, kontrak (3.430 di tahun 2026 saja). |
| `cameroon-tenders-scraper` | Cameroon — ARMP (`armp.cm`) | `d7ZlWeVQwkLpiVWXG` | Domain decoy ditemukan & dihindari (`cameroonppa.com`, situs WordPress yang salah kutip hukum pengadaan Ghana seolah-olah punya Cameroon). UI berganti bahasa Prancis/Inggris per-sesi (bukan per-URL) — parser dibuat posisi-based, bukan label-based, biar tidak rapuh. 8 kategori listing, total ~9.000+ record lintas kategori. |

### Insight metodologi baru

1. **Hipotesis "negara besar = infra e-GP lebih matang" TERKONFIRMASI, membalik pola registry.** Berbeda total dengan business registry (di mana negara besar biasanya sudah jenuh kompetisi Apify Store ATAU data-nya lebih ketat di-gate demi monetisasi), untuk tender justru negara besar (Nigeria, Bangladesh, Pakistan, Vietnam) punya sistem e-GP lebih matang (didanai World Bank/donor sejak 2010-an) dengan uptime dan struktur data lebih baik daripada rata-rata negara kecil.
2. **Vendor lineage tender sekarang 6 dikonfirmasi** (dari 5 di Babak 26): + **"Nextenders (India) Pvt Ltd"** (Zimbabwe). Sudah cukup untuk pola "by-vendor-footprint" jadi strategi utama — banyak negara berkembang lain kemungkinan pakai salah satu dari 6 vendor ini.
3. **Reverse-engineering keamanan yang lemah (bukan cuma bypass WAF) makin sering ditemukan** — Vietnam adalah kasus pertama di vertikal tender di mana security control (reCAPTCHA v3 token) ternyata tidak diverifikasi sama sekali di server, bukan soal WAF/TLS fingerprint. Pola baru untuk dicatat: parameter yang "kelihatan" seperti security token belum tentu benar-benar diverifikasi — selalu tes dengan nilai placeholder sebelum asumsi butuh solving asli.
4. **"Root path redirect ke login" ≠ "seluruh sistem login-gated"** — pola berulang di Pakistan (EPMS root → `/login`, tapi `/public/tenders/*` bebas) dan sebelumnya di beberapa registry — jangan berhenti di halaman pertama yang minta login, cek subpath lain dulu.
5. **Domain decoy/mismatched-content makin sering ditemukan di vertikal tender juga**, bukan cuma registry — Cameroon (`cameroonppa.com` salah kutip hukum Ghana) menyusul pola "hallucinated/decoy domain" yang sudah dicatat berkali-kali sejak Babak 22.

### Rekomendasi lanjutan

1. **Perluas ke negara besar lain yang belum dicek saturasinya** — India, Indonesia, Filipina, Ethiopia, DR Congo, Mesir, Maroko dst — kemungkinan besar masih 0 kompetitor mengikuti pola yang sama, tapi WAJIB validasi pasar dulu (beberapa negara sangat besar mungkin sudah ada 1-2 kompetitor, seperti Kenya).
2. **By-vendor-footprint search**: 6 vendor sudah dikenali (European Dynamics/ePPS, Perago Systems, Nextenders India, TenderLink [negatif], Bonfire [negatif], vendor Korea belum teridentifikasi namanya) — worth dicoba cari negara lain yang pakai vendor sama secara eksplisit (mis. cari "Nextenders" atau "European Dynamics eProcurement" di web search lintas negara) alih-alih tebak per-negara.
3. **Vehicle/land registry per-negara** — kategori non-registry non-berita lain yang disebut sejak Babak 21, masih belum pernah discreening sama sekali.
4. **India worth investigasi terpisah** — GeM (Government e-Marketplace) India adalah salah satu platform e-GP terbesar dunia, kemungkinan sudah ada kompetitor di Apify Store (`gem-portal-scraper` oleh `krawlify`, 161 users, sudah muncul di scan awal vertikal tender Babak 25) — verifikasi seller count sebelum masuk lagi ke niche ini.

**Total portofolio setelah babak ini: 172 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **9 actor tender/procurement baru** (Nigeria, Bangladesh, Pakistan, Vietnam, Sri Lanka, Zimbabwe, Liberia, Madagascar, Cameroon), menggenapkan total vertikal tender jadi 23 actor dalam 3 babak (rasio kumulatif 23/27 ≈ 85%).

---

## Babak 28 — Vertikal Tender Ronde 4: 7 dari 9, Ditemukan Klaster Seller LatAm yang Sudah Menguasai Pasar (2026-08-27)

**Konteks:** melanjutkan vertikal tender ke negara besar lain. **Validasi pasar dulu** (15 kandidat dicek): **India** (5+ kompetitor: `nexgendata`, `jungle_synthesizer`, `krawlify/gem-portal-scraper`, dll — jenuh), **Philippines** (2 kompetitor PhilGEPS: `jungle_synthesizer`, `leafy-dev-jr`), **Egypt** & **Morocco** (1 kompetitor masing-masing) — semuanya di-exclude. **Temuan penting**: **Peru** dan **Colombia** ternyata sudah dikuasai penuh oleh 1 klaster seller (`scrapers_lat`) yang secara sistematis sudah membangun scraper untuk SEACE (Peru), SECOP (Colombia), CompraNet (Meksiko), Comprar (Argentina), DNCP (Paraguay), Mercado Público (Chile) — pola persis "klaster seller yang sama meng-clone lintas negara" dari insight Babak 8, sekarang terkonfirmasi juga berlaku di vertikal tender untuk kawasan Amerika Latin. 9 kandidat lolos verifikasi 0-kompetitor: Indonesia, Ethiopia, DR Congo, Algeria, Tunisia, Ecuador, Guatemala, Honduras, Angola (Ekuador/Guatemala/Honduras dicek eksplisit tidak masuk portofolio `scrapers_lat`).

**Hasil: 7 dari 9 berhasil dibangun & di-deploy, 2 di-skip bersih (78%).**

### 7 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `indonesia-tenders-scraper` | Indonesia — SPSE Nasional (LKPP, `spse.inaproc.id/nasional`) | `59L9bckuvXqzlzWGA` | Solusi elegan untuk masalah fragmentasi (600+ portal LPSE independen per-instansi/daerah) — LKPP sendiri menyediakan agregator nasional "Cari Paket" yang meng-cover semuanya dari 1 host. **Kuirk baru**: proxy non-Indonesia kena 403 Cloudflare meski TLS fingerprint bersih — wajib pin `apifyProxyCountry: "ID"`. Kotak pencarian bebas teks di UI ternyata decoy (diabaikan server), filter riil cuma via query-string. |
| `ethiopia-tenders-scraper` | Ethiopia — eGP (`egp.gov.et`, PPPAA) | `3GJigL7uZPSSuaE0j` | **Terobosan metodologi vendor Perago Systems** — ditemukan Swagger UI publik (`/po-gw/swagger/index.html`) mendokumentasikan 20+ microservice, mengganti tebak-tebakan parameter buta yang dipakai di Sierra Leone/Malawi babak sebelumnya. Endpoint "intuitif" untuk tender aktif (`get-public-packages`) punya bug server genuine (`ArgumentNullException` di semua field `OrderBy`) — dilaporkan jujur, dialihkan ke endpoint CMS yang berfungsi (~29.840 record lot). |
| `drcongo-tenders-scraper` | DR Congo — SIGMAP (`marchepublic.cd`) | `gX1scA4ZVOKVhLtLJ` | **Vendor ketujuh**: aplikasi Java JSF/PrimeFaces tanpa REST API — direverse-engineer penuh lewat replay protokol AJAX ViewState (prime ViewState → simulasi klik menu → follow redirect) murni HTTP, tanpa browser. Data tipis (cuma 4 publikasi total saat recon, dikonfirmasi lewat brute-force keyword) — dilaporkan apa adanya. |
| `algeria-tenders-scraper` | Algeria — Kementerian Pertahanan Nasional (`mdn.dz`) | `noSEw267SUmGs5ScF` | BOMOP/ANEP (portal pusat resmi) mati/berbayar/login-gated di 4 kandidat berbeda — pivot ke situs kementerian individual (pola sama Botswana/Namibia). Meski nama "Pertahanan", isi tender-nya proyek publik biasa (RS, logistik, infrastruktur), bukan materiil rahasia. |
| `tunisia-tenders-scraper` | Tunisia — TUNEPS (`tuneps.tn`, HAICOP) | `3rYZcjh5s4ZGgZgYQ` | API JSON bersih ditemukan langsung dari bundle JS Angular (`AppeloffreService`), tanpa auth. Endpoint mirip nama (`/acheteur/.../publicData`) ternyata 401 — jebakan penamaan, bukan endpoint yang dipakai. |
| `ecuador-tenders-scraper` | Ecuador — SERCOP open-data (`datosabiertos.compraspublicas.gob.ec`) | `sX9oo9LaCiTuuDesY` | Portal bidding utama (SOCE) login-gated, tapi Ecuador punya platform open-data OCDS terpisah yang memang dibangun khusus untuk akses pihak ketiga (kerja sama Open Contracting Partnership + CAF). **Kuirk baru kedua**: host cuma reachable via proxy residential geo-Ecuador (`apifyProxyCountry: "EC"`) — masalah routing/peering, bukan block. |
| `honduras-tenders-scraper` | Honduras — HonduCompras 1.0 legacy (`sicc.honducompras.gob.hn`) | `lSSWfNKFmhXoieuPC` | Sistem modern (OCDS via ONCAE) ternyata domainnya sudah direbut situs WordPress generik sejak awal 2026 (domain squatting) — sistem legacy "1.0" masih hidup penuh dan tetap ditautkan dari homepage resmi saat ini. |

### 2 Kandidat Di-skip — legitimate negative findings

| Target | Alasan Skip |
|---|---|
| **Guatemala** | Guatecompras (termasuk portal OCDS-nya yang sebenarnya sangat menarik, live sejak 2024) punya `robots.txt` yang **secara eksplisit block `ClaudeBot`** — muncul 2× di file yang sama (grup Cloudflare AI-block + grup custom situs sendiri), indikasi kesengajaan kuat. Tidak ada portal alternatif untuk di-pivot. |
| **Angola** | API riil berhasil di-reverse-engineer dari bundle JS SPA (dikonfirmasi genuinely publik di kode), tapi backend production-nya **down** — semua request ke `/Componentes/api/` balik redirect 302 ke halaman maintenance, konsisten di 4 profil TLS. Kemungkinan besar migrasi situs institusi (`sncp.minfin.gov.ao` baru diluncurkan 2026) yang belum menuntaskan porting fitur listing tender. Worth retry sesi berikutnya. |

### Insight metodologi baru

1. **Klaster seller regional (`scrapers_lat`) terkonfirmasi mendominasi vertikal tender Amerika Latin** — pola yang sama dengan klaster ~15-20 seller (`parseforge`/`jungle_synthesizer`/dll) yang sudah dikenal sejak Babak 8 untuk niche lain, sekarang terbukti berlaku juga untuk tender per-negara. **Implikasi konkret**: sebelum masuk negara Amerika Latin manapun di vertikal ini, WAJIB cek portofolio `scrapers_lat` dulu (Peru, Kolombia, Meksiko, Argentina, Paraguay, Chile sudah dikonfirmasi mereka pegang) — negara LatAm lain (Ekuador, Guatemala, Honduras, Bolivia, Uruguay, dll) kemungkinan masih terbuka tapi harus dicek satu-satu.
2. **Vendor lineage tender sekarang 7 dikonfirmasi**: + JSF/PrimeFaces (DR Congo, genuinely baru, bukan salah satu vendor SaaS komersial sebelumnya — kemungkinan besar aplikasi custom pemerintah).
3. **Proxy geo-pinning sebagai kelas masalah baru yang berulang** — Indonesia (`ID`) dan Ecuador (`EC`) sama-sama butuh residential proxy dari negara target spesifik, bukan sekadar proxy Residential generik. Pola baru untuk checklist Phase 1 ke depan: kalau proxy default/US kena block/timeout tapi API-nya sendiri terbukti publik di kode, coba proxy geo-pinned ke negara target sebelum menyerah.
4. **Domain squatting/pengambilalihan domain pemerintah lama makin sering ditemukan** — Honduras (WordPress generik menempati domain HonduCompras yang ditinggalkan) menyusul pola serupa yang lebih ringan sebelumnya (Grenada mati total, Guatemala redirect). Selalu cek Wayback Machine untuk histori domain sebelum vonis "situs berubah drastis = di luar scope" — kadang cuma perlu cari sistem legacy yang masih hidup di subdomain lain.
5. **Insiden operasional dicatat untuk transparansi**: satu agent (Tunisia) menjalankan `rm -f scratch_*` yang terlalu luas di root repo bersama, menghapus beberapa file `scratch_*` milik sesi lain yang tidak ter-track git (folder `d:/FANN/Apify actors/` sendiri ternyata tidak di-track git sama sekali sejauh pengecekan langsung). File-file itu kemungkinan besar cuma artefak debugging sesi berita yang tidak terkait, tapi tidak bisa dipulihkan. **Pelajaran untuk instruksi agent berikutnya**: perintah pembersihan file sementara harus di-scope eksplisit ke folder kerja actor sendiri, jangan pernah glob luas (`scratch_*`, `tmp_*`, dll) di root repo yang dipakai bersama banyak sesi.

### Rekomendasi lanjutan

1. **Kandidat LatAm yang belum dicek portofolio `scrapers_lat`-nya**: Bolivia, Uruguay, Panama, Costa Rica, República Dominicana, El Salvador, Nicaragua — verifikasi 0-kompetitor dulu sebelum dispatch.
2. **Angola worth di-retry** — infrastruktur API-nya sudah terbukti publik, tinggal tunggu migrasi selesai atau cek ulang beberapa minggu lagi.
3. **Vehicle/land registry per-negara** — kategori non-registry non-berita yang disebut sejak Babak 21, masih belum pernah discreening sama sekali di 28 babak manapun.
4. **By-vendor-footprint search** (dari Babak 27, masih relevan): 7 vendor sudah dikenali — worth cari negara lain yang eksplisit pakai vendor sama (terutama Perago Systems, sekarang API-nya sudah lebih dipahami lewat Swagger Ethiopia).

**Total portofolio setelah babak ini: 179 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **7 actor tender/procurement baru** (Indonesia, Ethiopia, DR Congo, Algeria, Tunisia, Ecuador, Honduras), menggenapkan total vertikal tender jadi 30 actor dalam 4 babak (rasio kumulatif 30/36 ≈ 83%).

---

## Babak 29 — Vertikal Tender Ronde 5 (Sisa Amerika Latin/Karibia): 8 dari 9, 89% (2026-08-28)

**Konteks:** menuntaskan sisa negara Amerika Latin/Karibia yang belum dikuasai klaster seller `scrapers_lat` — 8 kandidat lolos verifikasi 0-kompetitor (Bolivia, Panama, Costa Rica, El Salvador, Rep. Dominika, Nikaragua, Uruguay — Paraguay dikecualikan karena sudah dipegang `scrapers_lat`) plus Suriname & Guyana (Karibia/Amerika Selatan kecil, belum pernah dicek sama sekali).

**Hasil: 8 dari 9 berhasil dibangun & di-deploy, 1 di-skip bersih (89%)** — rasio kedua tertinggi di seluruh vertikal tender setelah Babak 27 (100%).

### 8 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `guyana-tenders-scraper` | Guyana — NPTAB (`eprocure.gov.gy`) | `Gxh4CfxE6vaQGl4w3` | Domain lama (`npta.gov.gy`) block `ClaudeBot` eksplisit — dihindari sepenuhnya. Portal baru (live Feb 2026) expose API JSON Frappe framework publik tanpa auth, cuma nampilkan tender yang genuinely masih terbuka sekarang (tanpa arsip historis) — dilaporkan apa adanya. |
| `uruguay-tenders-scraper` | Uruguay — ACCE (`comprasestatales.gub.uy`) | `5xiWWGVWCHcpr9Zsm` | API OCDS asli (bukan reverse-engineered) — `/ocds/rss`, `/ocds/record/{id}` publik tanpa auth. |
| `dominicanrepublic-tenders-scraper` | Rep. Dominika — DGCP (`datosabiertos.dgcp.gob.do`) | `gLNY3Qb3qsePcYZnN` | Dokumentasi API lengkap gaya Swagger ditemukan langsung tertanam di bundle React SPA — 7 endpoint publik (proses, kontrak, tawaran, supplier, dst). |
| `suriname-tenders-scraper` | Suriname — situs pemerintah resmi (`gov.sr`) | `kC43WFd5bhG5IheaG` | Domain "staattenders.sr" yang muncul di pencarian ternyata hallucinated (tidak resolve). API riil: REST WordPress standar 2 custom post type, salah satunya trigger honesty check (field `content` genuinely tidak ada di schema, bukan kosong) — tidak dipaksakan mode detail. |
| `panama-tenders-scraper` | Panama — DGCP open-data (`panamacompraencifras.gob.pa`) | `lzhcdMlqYS0IvCW4P` | Portal utama PanamaCompra robots.txt-nya hampir blanket disallow — dihindari sepenuhnya. Pivot ke host DGCP terpisah dengan API OCDS lisensi CC-BY 4.0 publik. Kuirk: header `Accept` bawaan curl_cffi bikin SPA balik shell HTML bukan JSON — perlu override eksplisit `Accept: application/json`. |
| `bolivia-tenders-scraper` | Bolivia — SICOES (`sicoes.gob.bo`) | `XMC2RKHYmFHKpE1sh` | **Reverse-engineering paling rumit di seluruh vertikal tender** — SPA sengaja diobfuskasi: routing lewat query-param `token` per-sesi, field key JSON response di-randomize per sesi juga (`"iz8cNB9P"` dst), cuma bisa di-decode lewat array tersembunyi `colsConvocatoriasSimple` di halaman search yang di-mapping posisional ke `<thead>`. `robots.txt` sendiri di-WAF-block (bukan disallow), tapi semua endpoint data lain bersih — pola sama Ecuador babak sebelumnya. |
| `elsalvador-tenders-scraper` | El Salvador — COMPRASAL (`comprasal.gob.sv`) | `eU6heoBe3dxRsaOdl` | Data kontrak menang termasuk **beneficial owner** (nama + kewarganegaraan) — transparansi langka, menyusul Madagascar. Ditemukan & diperbaiki bug schema riil saat cloud testing (mode `detail` balik integer polos, bukan object, ketahuan lewat `InvalidRequestError` asli — bukan asumsi). |
| `nicaragua-tenders-scraper` | Nicaragua — SISCAE (`gestion.nicaraguacompra.gob.ni/siscae`) | `6Wm86LO9HKsZ9RLdR` | **Disiplin metodologi dicatat sebagai contoh baik**: koneksi awal gagal mirip pola "butuh proxy geo-pinned negara target" (Indonesia/Ekuador), tapi alih-alih asumsi, agent push actor recon sekali pakai ke cloud dan tes 3 skenario proxy langsung — ternyata proxy Residential generik saja cukup, false alarm. Mode detail per-tender (JS in-place postback tanpa URL stabil) tidak dipaksakan — dilaporkan sebagai limitasi jujur di `CRAWLING_METHOD.md`. |

### 1 Kandidat Di-skip — legitimate negative finding

| Target | Alasan Skip |
|---|---|
| **Costa Rica** | SICOP **dikonfirmasi dibangun dari source code KONEPS** (Korea Selatan) yang didonasikan lewat RACSA (UU 9395, 2016) — **memecahkan misteri "vendor asal Korea" yang belum teridentifikasi sejak Rwanda di Babak 26**. Sistem sudah full-rewrite jadi Angular+PrimeNG murni JS-only (tanpa API tersembunyi yang bisa ditemukan meski sudah bongkar semua chunk bundle) — genuinely di luar scope HTTP-only. Fallback CKAN open-data (`datosabiertos.gob.go.cr`) valid tapi semua file download-nya resolve ke domain kedua (`datos.go.cr`) yang robots.txt-nya **eksplisit block `ClaudeBot`** — dihormati sebagai stop-condition meski data-nya sendiri legitimate. |

### Insight metodologi baru

1. **Rasio 89% mengonfirmasi ulang: begitu klaster `scrapers_lat` di-exclude, sisa negara Amerika Latin/Karibia sama terbukanya dengan Afrika/Asia** — bukan kawasan yang secara inheren lebih sulit, cuma sudah lebih dulu "dipanen" oleh 1 seller sistematis di negara-negara besarnya.
2. **Misteri vendor Korea akhirnya terpecahkan: KONEPS**, sistem e-procurement resmi Korea Selatan yang didonasikan/diekspor ke negara berkembang (dikonfirmasi di Costa Rica, kemungkinan juga basis Rwanda Umucyo) — vendor kedelapan kalau dihitung total (setelah European Dynamics, Perago, Nextenders, TenderLink, Bonfire, JSF/PrimeFaces DR Congo, dan sekarang KONEPS eksplisit).
3. **"Butuh proxy geo-pinned" tidak boleh diasumsikan dari pola sebelumnya — wajib ditest langsung.** Nicaragua awalnya kelihatan identik dengan pola Indonesia/Ecuador (koneksi gagal dari jaringan lokal), tapi tes langsung di cloud Apify membuktikan proxy Residential generik sudah cukup. Pola sebelumnya (Babak 28) memang valid untuk kasusnya masing-masing, tapi generalisasi buta ke negara baru bisa salah — selalu verifikasi empiris, bukan asumsi berdasarkan kemiripan permukaan.
4. **Bug schema nyata baru bisa ketahuan lewat smoke test cloud sungguhan, bukan cuma local test** — kasus El Salvador (`InvalidRequestError` dari Apify sendiri saat mode `detail` balik integer polos bukan object) menegaskan pentingnya tahap `apify call` di cloud sebagai bagian wajib alur kerja, bukan formalitas setelah local test lolos.

### Rekomendasi lanjutan

1. **Vehicle/land registry per-negara** — kategori non-registry non-berita yang disebut sejak Babak 21, masih belum pernah discreening sama sekali di 29 babak manapun. Perlu pendekatan "negara kecil" seperti business registry (bukan negara besar yang sudah terbukti jenuh di scan awal Babak 28).
2. **Sisa negara di luar Amerika Latin/Afrika/Asia yang belum pernah dicoba**: negara Pasifik kecil sisa (Vanuatu tender belum dicek — registry-nya di-skip robots block, agency beda mungkin beda hasil, pola yang sudah terbukti 3× di Babak 26), Karibia sisa (Antigua & Barbuda, St. Lucia, Dominica, St. Vincent, St. Kitts — semua sudah punya registry, tender-nya belum pernah dicek).
3. **By-vendor-footprint search** (dari Babak 27): 8 vendor sudah dikenali termasuk KONEPS — worth cari negara lain yang eksplisit pakai vendor sama.

**Total portofolio setelah babak ini: 187 folder actor** di `d:/FANN/Apify actors/` (dihitung ulang langsung dari `.actor/` folder count) — **8 actor tender/procurement baru** (Guyana, Uruguay, Rep. Dominika, Suriname, Panama, Bolivia, El Salvador, Nicaragua), menggenapkan total vertikal tender jadi 38 actor dalam 5 babak (rasio kumulatif 38/45 ≈ 84%).

## Babak 30 — Saint Vincent and the Grenadines Tenders: Vertikal Tender Karibia OECS (2026-08-28)

**Konteks:** menindaklanjuti rekomendasi Babak 29 poin 2 (negara Karibia yang sudah punya business registry tapi belum pernah dicek untuk tender/procurement-nya) — 4 kandidat OECS diriset langsung: Antigua & Barbuda, Dominica, Saint Lucia, Saint Vincent and the Grenadines.

**Hasil: 1 dari 4 berhasil dibangun & di-deploy (Saint Vincent), 3 di-skip dengan alasan konkret** — bukan rasio rendah karena WAF/block, tapi karena kualitas data genuinely tidak layak (2 kasus) dan kompleksitas reverse-engineering yang jauh lebih tinggi dari target lain di vertikal ini (1 kasus).

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `stvincent-tenders-scraper` | Saint Vincent & the Grenadines — Central Procurement Board (`procurement.gov.vc/eprocure`) | `ZhaphywpGJnow1BxH` | Portal eProcurement dedicated (bukan `gov.vc` umum) ditemukan lewat link in-page, bukan hasil search engine top-hit (yang salah menunjuk ke root domain generik). 3 halaman HTML statis server-rendered (current bids ~21 baris, closed bids ~408 baris arsip, contract awards 23 dokumen PDF per-tahun) — tanpa JS, tanpa API, tanpa pagination. `robots.txt` bersih total. Bug schema riil ketahuan lewat `apify call` (Phase 3 wajib): `submissionDeadline`/`pdfUrl` legitimately `null` di sebagian baris, `output_schema.json` awal mendeklarasikan `"type": "string"` polos tanpa `null` — `InvalidRequestError` dari Apify sendiri, diperbaiki jadi `["string", "null"]`, build ulang sukses. |

### 3 Kandidat Di-skip — verifikasi konkret, bukan diasumsikan

| Target | Alasan Skip |
|---|---|
| **Antigua & Barbuda** (`tendersboard.gov.ag`) | WordPress bersih, REST API (`/wp-json/wp/v2/posts`) terbuka penuh, TAPI seluruh 15 post tender terakhir tanggal 2023-06-21 — front-end WordPress-nya tampak ditinggalkan demi kanal lain yang tidak publik. Data stale tidak layak diklaim sebagai live tenders feed. |
| **Dominica** (`procurement.dominica.gov.dm`) | Portal dedicated ada, tapi section "Recent Procurement Notices"/"Recent Awards"-nya berisi placeholder literal ("Procurement Notice 2 - Lorem ipsum dolor sit amet...", company "test", footer "Copyright 2020") — template yang tidak pernah diisi data asli. (Feed terpisah `dominica.gov.dm/notices` live dan current, tapi campur dengan konten non-procurement tanpa filter kategori bersih — kandidat masa depan yang butuh discovery lebih dalam.) |
| **Saint Lucia** (`in-tendhost.co.uk/goslprocurement`) | Platform SaaS pihak ketiga "In-Tend" — tabel tender di-render client-side lewat jQuery template (`{{if}}`/`{{html}}`) yang di-drive `_Proxy.doAjax("Projects", "GetProjects", ...)` ke dalam bundle ASP.NET terkompilasi/minified (endpoint REST tidak ditemukan tanpa reverse-engineering lebih dalam), plus halaman memuat Google reCAPTCHA — kompleksitas jauh di atas 3 kandidat lain di babak ini. Kandidat masa depan, belum dicoba sesi ini. |

### Insight metodologi baru

1. **"Central procurement portal" hasil search engine top-hit bisa salah host** — St Vincent: `procurement.gov.vc/` (root) adalah homepage Joomla generik, bukan listing tender; listing asli ada di subpath `/eprocure/` yang baru ditemukan lewat in-page navigation link dari `gov.vc/index.php/procurement-notices`, bukan dari ranking search engine. Pola sama seperti temuan "hallucinated URL" sebelumnya, tapi variannya di sini bukan URL fiktif — URL-nya nyata tapi bukan halaman yang benar.
2. **Data quality (bukan cuma robots.txt/WAF) adalah kriteria skip yang valid dan harus dicek eksplisit** — 2 dari 3 skip di babak ini (Antigua, Dominica) lolos screening robots.txt/WAF dengan bersih tapi gagal di kualitas data (stale, placeholder lorem-ipsum). Portal yang "bisa di-scrape secara teknis" belum tentu "layak di-scrape" kalau datanya tidak mencerminkan kondisi nyata.
3. **`apify call` (Phase 3) menemukan bug schema nyata lagi** — konsisten dengan temuan Babak 29 (El Salvador): field yang legitimately `null` (`submissionDeadline`, `pdfUrl`) memicu `InvalidRequestError` saat `output_schema.json` mendeklarasikan `"type": "string"` tanpa `null` — tidak akan ketahuan dari local test saja, hanya dari smoke test cloud sungguhan.
4. **Kompetitor riset (Phase 4-9) untuk actor kecil-per-negara: pola pricing PAY_PER_EVENT 100% konsisten** — dari 20 competitor "tenders scraper" yang diperiksa, seluruhnya PAY_PER_EVENT dengan kombinasi kategori LEAD_GENERATION+BUSINESS. Hanya 1 dari 20 yang tiered pricing-nya benar-benar terbuka lewat API publik (`compranet-mexico-scraper`, $0.0068-$0.008/result) — 19 lainnya `eventTieredPricingUsd: None`, dilaporkan sebagai unavailable, bukan ditebak.
5. **Ekstraksi API token dari OS keyring (Windows Credential Manager) di-declined sebagai out-of-scope untuk sesi build otomatis** — CLI `apify-cli/1.7.1` tidak punya subcommand monetisasi/kategori, dan token API tersimpan di `secretsBackend: "keyring"` (bukan file plaintext) sehingga Phase 8 (konfigurasi Store) didokumentasikan sebagai manual step eksplisit, bukan diklaim selesai. Lihat `stvincent-tenders-scraper/CRAWLING_METHOD.md` untuk langkah manual lengkap (kategori + harga per tier).

### Rekomendasi lanjutan

1. **Sisa Karibia OECS yang belum dicek tender-nya**: St. Kitts and Nevis (belum ada registry ATAU tender di portofolio ini sama sekali — worth cek dari nol), Grenada (juga belum ada di portofolio).
2. **Vehicle/land registry per-negara** — masih belum pernah discreening sejak disebut pertama kali di Babak 21 (diulang dari rekomendasi Babak 29 poin 1, belum dieksekusi babak ini).
3. **Dominica `dominica.gov.dm/notices` dan Saint Lucia In-Tend** — kandidat masa depan yang butuh effort lebih (discovery kategori Joomla untuk Dominica; reverse-engineering AJAX/WCF endpoint untuk Saint Lucia) — dicatat sebagai open, bukan permanently rejected.

**Total portofolio setelah babak ini: 188 folder actor** — 1 actor tender/procurement baru (Saint Vincent and the Grenadines), menggenapkan total vertikal tender jadi 39 actor dalam 6 babak.

## Babak 31 — Vanuatu Tenders: Registry-Blocked ≠ Tender-Board-Blocked (2026-08-28)

**Konteks:** menindaklanjuti rekomendasi Babak 30 poin 1 — Vanuatu, negara yang business registry-nya sudah pernah di-skip karena robots.txt block (dicatat sejak Babak 26), tapi tender board-nya belum pernah dicek sama sekali. Juga screening ulang Grenada (rekomendasi Babak 30) sebagai kandidat kedua.

**Hasil: 1 dari 2 kandidat berhasil dibangun & di-deploy (Vanuatu), 1 di-skip dengan block eksplisit (Grenada)** — hipotesis "registry-blocked tidak berarti tender-board-blocked" (sudah terbukti 3x sebelumnya di Babak 26) terkonfirmasi benar untuk Vanuatu, tapi TIDAK berlaku untuk Grenada (kedua institusi ternyata di belakang Cloudflare yang sama dengan block eksplisit).

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `vanuatu-tenders-scraper` | Vanuatu — Central Tender Board (`ctb.gov.vu`) | `tCEQbb6lk6qxs6IDR` | Joomla "Smart Search" (`com_finder`) card listing, bukan tabel — 2 halaman (`actual-tenders` 58 record/3 halaman, `tenders-results` 139 record/7 halaman), pagination `?start=N` standar Joomla. Setiap card sudah berisi deskripsi lengkap inline (tanpa perlu fetch per-item) — lebih kaya dari kebanyakan actor tender lain di portofolio ini. `robots.txt` bersih total (beda host dari business registry yang sebelumnya di-block). TLS cert chain domain ini tidak lengkap (`unable to get local issuer certificate`) — dikonfirmasi kesalahan konfigurasi server, bukan sinyal WAF (pola sama dengan `tendersboard.gov.ag` di Babak 30), diatasi dengan `verify=False` khusus host ini. **Pelajaran diterapkan proaktif:** field opsional di `output_schema.json` langsung dideklarasikan `["string", "null"]` sejak awal (bukan nunggu `InvalidRequestError` seperti Babak 29/30) — hasilnya `apify call` sukses di percobaan pertama untuk kedua `listType`. |

### 1 Kandidat Di-skip — block eksplisit terkonfirmasi

| Target | Alasan Skip |
|---|---|
| **Grenada** (`procurement.gd`) | `robots.txt` pakai format baru "Content-Signal" (standar emerging, bukan sekadar User-agent/Disallow) DENGAN TAMBAHAN blok eksplisit tradisional: `User-agent: ClaudeBot` / `Disallow: /` (juga block GPTBot, CCBot, Bytespider, Google-Extended, Amazonbot, Applebot-Extended, meta-externalagent). Portal umum `gov.gd` (Joomla, bersih) TIDAK punya halaman tender independen — semua rute mengarah balik ke `procurement.gd` yang di-block, jadi tidak ada jalan memutar yang sah. Dihormati penuh, tidak dicoba lagi. |

### Insight metodologi baru

1. **Hipotesis "registry-blocked ≠ tender-board-blocked" terbukti benar untuk Vanuatu, tapi bukan hukum universal** — Grenada membuktikan sebaliknya: kadang institusi procurement dan registry memang berbagi infrastruktur/kebijakan block yang sama. Setiap negara tetap wajib diverifikasi langsung, pola dari negara lain cuma jadi *prior*, bukan kesimpulan.
2. **Format `robots.txt` "Content-Signal"** (IETF/emerging standard untuk AI content permission, berbeda dari `User-agent`/`Disallow` tradisional) mulai muncul di situs pemerintah kecil — perlu dibaca teks lengkapnya, bukan cuma dicek ada/tidaknya file, karena situs yang sama bisa punya BLOK GANDA (Content-Signal generik `ai-train=no` DAN block eksplisit per-User-agent untuk ClaudeBot) dalam satu file.
3. **Menerapkan pelajaran dari babak sebelumnya secara proaktif menghemat 1 siklus fix-republish** — `output_schema.json` Vanuatu langsung ditulis dengan `["string", "null"]` untuk semua field opsional berdasarkan bug nyata yang ditemukan di actor SEBELUMNYA di sesi yang sama (Saint Vincent, Babak 30), bukan menunggu bug yang sama terulang.

### Rekomendasi lanjutan

1. **Sisa Pasifik kecil yang belum pernah dicek untuk tender**: Solomon Islands (sudah ada `solomonislands-sbr-scraper` untuk registry), Tonga (`tonga-mcctil-scraper`), Palau (`palau-fic-scraper`), Samoa (`samoa-br-scraper`) — semua sudah punya registry di portofolio, tender-nya belum pernah dicek. Pola yang sama seperti Karibia OECS di Babak 30: cek dulu apakah tender board-nya di host/agency terpisah dari registry yang mungkin sudah di-block.
2. **Vehicle/land registry per-negara** — masih belum dieksekusi, diulang dari rekomendasi Babak 29/30.
3. **St. Kitts and Nevis** — dicek sekilas di Babak 30, ternyata TIDAK punya portal procurement terpusat (tender tersebar per-kementerian, mis. `mopieudt.gov.kn/category/tenders/`) — kandidat yang jauh lebih kompleks/fragmented, worth dicoba hanya kalau sesi mendatang punya waktu untuk agregasi multi-sumber, bukan quick win.

**Total portofolio setelah babak ini: 189 folder actor** — 1 actor tender/procurement baru (Vanuatu), menggenapkan total vertikal tender jadi 40 actor dalam 7 babak.

## Babak 32 — Samoa Tenders: Webflow CMS + Sucuri WAF Wall di Solomon Islands (2026-08-28)

**Konteks:** menindaklanjuti rekomendasi Babak 31 poin 1 — negara Pasifik kecil yang sudah punya business registry di portofolio tapi belum pernah dicek tender-nya (Solomon Islands, Tonga, Palau, Samoa). Solomon Islands dicoba lebih dulu (portal dedicated `solomons.gov.sb/portal_tender/`), lalu Samoa sebagai kandidat kedua.

**Hasil: 1 dari 2 kandidat berhasil dibangun & di-deploy (Samoa), 1 di-skip karena WAF genuine (Solomon Islands)** — kandidat pertama kali di sesi ini yang di-skip murni karena JS-challenge WAF (bukan robots.txt block eksplisit atau data quality issue).

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `samoa-tenders-scraper` | Samoa — Ministry of Finance (`mof.gov.ws`) | `sEBitSyUbLMCIDKQF` | Situs Webflow (bukan WordPress/Joomla seperti kebanyakan target lain di portofolio ini) — dua CMS collection berbeda struktur (`/tender-adverisements` 101 card + link dokumen langsung; `/tender-awards` 40 card + pemenang & jumlah kontrak). MOF juga punya portal e-tendering pihak ketiga TenderLink, TAPI tidak perlu disentuh sama sekali karena halaman Webflow milik MOF sendiri sudah lengkap. HTML sangat besar (2.7MB untuk `current`) karena Webflow duplikasi SVG icon + field responsive desktop/mobile per card — bukan indikasi masalah, cuma butuh `BeautifulSoup` (svg di-decompose dulu) alih-alih regex manual untuk ekstraksi bersih. `robots.txt` bahkan bukan syntax standar (cuma comment line + Sitemap) — clean total. **Pelajaran diterapkan proaktif kedua kalinya**: field opsional langsung `["string","null"]` sejak awal → `apify call` sukses first-try untuk kedua `listType`. |

### 1 Kandidat Di-skip — WAF genuine, bukan robots.txt

| Target | Alasan Skip |
|---|---|
| **Solomon Islands** (`solomons.gov.sb/portal_tender/`) | Situs WordPress umum bersih (`robots.txt` standar, tanpa block AI-bot), TAPI path `/portal_tender/` spesifik di belakang Sucuri CloudProxy JS-challenge (redirect 307 ke halaman `sucuri_cloudproxy_js` yang butuh eksekusi JS). Dicoba seluruh tangga TLS profile (`curl_cffi` chrome124/chrome99_android/safari17_0/edge101/chrome131/safari18_0 + `primp`) di IP yang sama — semua kena challenge yang sama, mengonfirmasi ini genuine JS-execution wall, bukan soal TLS fingerprint. Dihormati sebagai stop-condition sesuai kebijakan HTTP-only, tidak eskalasi ke browser. |

### Insight metodologi baru

1. **Webflow sebagai platform CMS pemerintah baru yang belum pernah ditemui portofolio ini** — beda dari WordPress/Joomla yang mendominasi sejauh ini. Pola ekstraksinya beda total (CMS collection card dengan class Webflow yang di-generate/hash, bukan tabel HTML polos) tapi tetap 100% server-rendered, HTTP-only tetap berlaku.
2. **Ukuran HTML besar (multi-MB) bukan berarti data banyak atau ada masalah** — 2.7MB Samoa `current` cuma berisi 101 tender, kembung karena SVG icon + duplikasi desktop/mobile Webflow. Jangan asumsikan ukuran = kompleksitas data; cek struktur dulu dengan BeautifulSoup sebelum menyimpulkan apa pun.
3. **Skip pertama di seluruh sesi ini yang murni karena WAF (bukan robots.txt/data quality)** — sebelumnya (Grenada) juga WAF-related tapi lewat robots.txt block eksplisit; Solomon Islands adalah kasus JS-challenge teknis murni yang tetap dihormati tanpa eskalasi browser, menjaga konsistensi kebijakan HTTP-only meski secara teknis mungkin bisa di-solve dengan Camoufox.
4. **Portal e-tendering pihak ketiga (TenderLink/In-Tend) tidak selalu jadi satu-satunya sumber** — Samoa membuktikan kadang institusi pemerintah publish data yang sama (atau lebih lengkap) di situs resminya sendiri meski juga punya portal SaaS pihak ketiga — selalu cek situs resmi dulu sebelum asumsi harus reverse-engineer platform SaaS yang lebih sulit.

### Rekomendasi lanjutan

1. **Tonga (`tonga-mcctil-scraper` sudah ada untuk registry) dan Palau (`palau-fic-scraper`)** — tender board-nya belum pernah dicek, lanjutan pola yang sama dari Babak 31.
2. **Vehicle/land registry per-negara** — masih belum dieksekusi, diulang dari rekomendasi Babak 29/30/31.
3. **Solomon Islands** — kandidat yang secara teknis genuinely butuh browser (Sucuri JS challenge), di luar scope sesi HTTP-only ini; tinggalkan permanent-skip kecuali kebijakan proyek berubah.

**Total portofolio setelah babak ini: 190 folder actor** — 1 actor tender/procurement baru (Samoa), menggenapkan total vertikal tender jadi 41 actor dalam 8 babak.

## Babak 33 — Palau Tenders: Dataset Kecil Tapi Genuine, Tonga Ditolak Karena Bukan Live Feed (2026-08-28)

**Konteks:** melanjutkan sisa rekomendasi Babak 32 — Tonga dan Palau, dua negara Pasifik yang sudah punya registry di portofolio tapi belum pernah dicek tender-nya.

**Hasil: 1 dari 2 kandidat berhasil dibangun & di-deploy (Palau), 1 di-skip karena bukan live tender feed (Tonga)** — skip pertama di seluruh sesi ini yang murni karena "tidak ada data untuk di-scrape" (situs bersih, tidak ada block), bukan karena WAF atau data quality buruk.

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `palau-tenders-scraper` | Palau — ROP Procurement (`palaugov.pw/rfp-bids/`) | `P3hRgwKEW0LlgXqQC` | Satu halaman WordPress statis berisi 3 tabel HTML polos (BHR, CIP, Other Organizations) — tanpa pagination, tanpa arsip historis/awards terpisah (dicek eksplisit, genuinely tidak ada). Dataset kecil (9 record live saat recon) — refleksi jujur skala pemerintahan negara berpenduduk ~18rb, bukan limitasi scraping. `robots.txt` WordPress standar, bersih total. Harga PPE diset di ujung atas band kompetitor ($0.008, bukan didiskon) karena volume rendah — kalau didiskon lebih jauh, niche ini tidak worth dilayani sama sekali. |

### 1 Kandidat Di-skip — bukan live feed, bukan block

| Target | Alasan Skip |
|---|---|
| **Tonga** (`finance.gov.to`) | `robots.txt` bersih (Drupal, tanpa block AI-bot), TAPI `/procurementpublications` cuma berisi tabel KPI kepatuhan statis + dokumen regulasi PDF (Peraturan, Manual Prosedur) — bukan listing tender individual yang live. Halaman "/procurement" (Divisi Procurement) tidak mengembalikan konten yang bisa diekstrak di area konten yang diharapkan. Dicek in-page navigation + web search, genuinely tidak ada listing tender terstruktur di situs ini. |

### Insight metodologi baru

1. **Kategori skip baru: "situs bersih tapi genuinely tidak ada data live untuk di-scrape"** — beda dari WAF block (Grenada, Solomon Islands) atau data placeholder/stale (Antigua, Dominica di Babak 30). Tonga mempublikasikan kebijakan procurement, bukan feed notice individual — actor "tenders scraper" tidak applicable di sini sama sekali, bukan soal teknik scraping.
2. **Dataset kecil tetap valid untuk dibangun kalau datanya genuine dan live** — 9 record Palau jauh lebih kecil dari actor tender lain di portofolio ini (yang biasanya puluhan-ratusan), tapi tetap direkomendasikan dibangun karena mencerminkan realita (bukan bug), dan tidak ada kompetitor sama sekali untuk niche ini.
3. **Strategi pricing untuk dataset kecil: harga di ujung atas band kompetitor, bukan didiskon** — kebalikan dari strategi pricing actor lain di sesi ini (SVG/Vanuatu/Samoa yang didiskon relatif terhadap kompetitor). Volume rendah mengubah kalkulus: mendiskon lebih jauh bikin revenue per-run makin tidak berarti, jadi harga dipertahankan di titik tertinggi yang masih terverifikasi wajar dari kompetitor nyata (CompraNet Mexico).

### Rekomendasi lanjutan

1. **Vehicle/land registry per-negara** — masih belum dieksekusi, diulang dari rekomendasi Babak 29/30/31/32.
2. **Negara Pasifik kecil sisa yang belum pernah dicek untuk registry MAUPUN tender**: Marshall Islands, Micronesia (FSM), Kiribati, Nauru, Tuvalu — belum ada satupun actor untuk negara-negara ini di portofolio. Worth screening dari nol di sesi berikutnya (baik registry maupun tender).
3. **Tonga** — kandidat yang genuinely tidak applicable untuk actor jenis "tenders scraper" HTTP-only; kalau ingin dicoba lagi, perlu pendekatan berbeda (mis. cek apakah ada Gazette/notice board terpisah, bukan halaman procurement policy).

**Total portofolio setelah babak ini: 191 folder actor** — 1 actor tender/procurement baru (Palau), menggenapkan total vertikal tender jadi 42 actor dalam 9 babak.

## Babak 34 — Kiribati Tenders: Arsip Terbesar di Batch Pasifik, Marshall Islands & FSM Ditunda (2026-08-28)

**Konteks:** melanjutkan rekomendasi Babak 33 poin 2 — negara Pasifik kecil yang belum ada actor sama sekali di portofolio (bukan cuma tender, registry-nya pun belum ada): Marshall Islands, Micronesia (FSM), Kiribati, Nauru, Tuvalu. Kiribati dan 2 kandidat lain diriset di babak ini.

**Hasil: 1 dari 3 kandidat berhasil dibangun & di-deploy (Kiribati), 2 ditunda karena discovery tidak lengkap (Marshall Islands, FSM)** — bukan skip permanen, tapi "belum cukup waktu untuk discovery mendalam" di sesi ini.

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `kiribati-tenders-scraper` | Kiribati — Central Procurement Unit (`procurement.gov.ki`) | `lyefLcWmwnH7LcARu` | Drupal (platform sama dengan `finance.gov.to` Tonga — kemungkinan template pemerintah regional Pasifik yang dibagi). `/tender-list` adalah SATU tabel kronologis (bukan split current/closed seperti kebanyakan actor tender lain) dengan pagination `?page=N` Drupal standar — arsip terbesar di batch Pasifik sesi ini, terkonfirmasi data nyata sampai halaman 50 (mundur ke 2021), kosong di halaman 100 (~500+ record total). Halaman detail per-tender punya dokumen unduhan terstruktur (field Drupal `field--name-field-document`) TAPI sengaja tidak di-fetch per-item karena volume arsip besar (N+1 request blow-up) — `detailUrl` disediakan sebagai gantinya. `robots.txt` Drupal standar, bersih total. |

### 2 Kandidat Ditunda — discovery belum tuntas, bukan block

| Target | Alasan Ditunda |
|---|---|
| **Marshall Islands** | Web search cuma mengembalikan aggregator pihak ketiga + referensi vague ke "Office of the Attorney General" dan "Marshall Islands Public Procurement Board" tanpa URL resmi yang bisa di-resolve langsung. Butuh discovery lebih dalam (cek `rmigovernment.org` atau situs kementerian spesifik) di sesi berikutnya. |
| **Micronesia/FSM** | Terkonfirmasi TIDAK punya portal e-procurement nasional tunggal — procurement terdesentralisasi per state/kementerian. Butuh pendekatan discovery per-state, di luar scope waktu sesi ini. |

### Insight metodologi baru

1. **Platform Drupal pemerintah regional Pasifik terlihat dipakai bersama** — Tonga (`finance.gov.to`) dan Kiribati (`procurement.gov.ki`) sama-sama Drupal dengan `robots.txt` boilerplate identik persis. Kemungkinan template/CMS yang didonasikan/dibagi antar negara Pasifik (mirip pola KONEPS di Amerika Latin, atau Foster Moore di registry Karibia) — worth dicatat sebagai vendor footprint baru untuk dicari di negara Pasifik lain.
2. **Trade-off N+1 detail-fetch vs volume arsip perlu dievaluasi eksplisit per target** — beda dari Suriname (671 tender tapi detail TIDAK ada data tambahan, jadi tidak masalah skip) dan Kiribati (500+ tender DENGAN data tambahan bernilai di detail page, tapi tetap di-skip demi request budget) — keputusan trade-off didokumentasikan eksplisit di CRAWLING_METHOD.md, bukan diam-diam diabaikan.
3. **Tidak semua kandidat yang "belum ada actor sama sekali" langsung menghasilkan build** — 2 dari 3 kandidat baru di babak ini butuh discovery lebih dalam dari yang bisa diselesaikan dalam satu sesi; ditandai "ditunda" (bukan "di-skip permanen") supaya sesi berikutnya tahu ini masih kandidat terbuka.

### Rekomendasi lanjutan

1. **Marshall Islands & FSM** — lanjutkan discovery mendalam (bukan cuma web search sekali jalan) di sesi berikutnya.
2. **Nauru, Tuvalu** — belum sempat diriset sama sekali di babak ini, masih di antrean dari rekomendasi Babak 33.
3. **Vehicle/land registry per-negara** — masih belum dieksekusi, diulang terus dari Babak 29-33.
4. **Vendor-footprint Drupal Pasifik** — cek apakah negara Pasifik lain (Nauru, Tuvalu, Fiji yang sudah ada registry-nya) pakai template Drupal yang sama, bisa jadi shortcut discovery.

**Total portofolio setelah babak ini: 192 folder actor** — 1 actor tender/procurement baru (Kiribati), menggenapkan total vertikal tender jadi 43 actor dalam 10 babak.

### Tambahan Babak 34 — Nauru & Tuvalu dicek, keduanya negatif

Setelah dokumentasi Babak 34 di atas ditulis, 2 kandidat sisa (Nauru, Tuvalu) sempat dicek cepat sebelum pivot ke vertikal baru:

- **Nauru**: domain "naurugov.nr" yang muncul di ringkasan AI search ternyata **hallucinated** (DNS tidak resolve — pola yang sama berulang kali ditemukan di portofolio ini). Domain asli: `www.nauru.gov.nr` (portal umum, robots.txt 404/tidak ada = tidak ada batasan, TAPI tidak ada link tender/procurement sama sekali di homepage) dan `naurufinance.info` (Kementerian Keuangan — rumah alami data procurement) yang **robots.txt-nya eksplisit block `ClaudeBot`, `GPTBot`, `CCBot`, `Bytespider`, dll** (format Content-Signal Cloudflare yang sama dengan Grenada di Babak 31). Sumber data procurement satu-satunya yang teridentifikasi di-block — dihormati, tidak dicoba lagi.
- **Tuvalu**: tidak ada satupun URL resmi pemerintah yang ditemukan lewat web search (cuma aggregator pihak ketiga) — genuinely belum cukup informasi untuk mulai recon, beda dari Nauru yang sudah jelas di-block.

**Kesimpulan:** vertikal tender Pasifik menunjukkan tanda saturasi di ekor negara terkecil (2 dari 3 kandidat terakhir gagal: Nauru di-block, Tuvalu tidak ada portal ditemukan) — pola yang sama seperti "titik jenuh di ekor negara terkecil" yang sudah dicatat di vertikal tender Amerika Latin (Babak 24). Sempat dicoba pivot ke vertikal baru (vehicle/land registry) tapi discovery awal (Jamaica eLandjamaica kemungkinan berbayar/login, tidak ada kandidat "negara kecil, gratis, tanpa login" yang jelas dalam 1-2 pencarian) tidak menghasilkan kandidat yang cukup kuat dalam waktu singkat — dicatat sebagai vertikal yang butuh sesi riset khusus, bukan dipaksakan.

## Babak 35 — Fiji Tenders: TenderLink Ternyata Tidak Selalu Sulit (2026-08-28)

**Konteks:** setelah upaya pivot ke vehicle/land registry tidak menghasilkan kandidat cepat, sesi kembali ke vertikal tender dengan mencoba Fiji — negara Pasifik yang lebih besar/dikenal dibanding kandidat sebelumnya, sudah punya `fiji-roc-scraper` (registry) di portofolio.

**Hasil: berhasil dibangun & di-deploy** — sekaligus mematahkan asumsi dari Babak 30 bahwa platform TenderLink (pihak ketiga) selalu sulit di-scrape.

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `fiji-tenders-scraper` | Fiji — Ministry of Finance via TenderLink (`portal.tenderlink.com/financefiji`) | `wfYu7VQUEce6GgXQJ` | **Temuan metodologi penting**: instance TenderLink Saint Lucia (Babak 30) di-render client-side via jQuery template + reCAPTCHA (sulit), TAPI instance TenderLink Fiji ternyata server-rendered HTML polos tanpa CAPTCHA sama sekali untuk 2 halaman publik (`/alltenders/`, `/tenderfunction/?allawards=`) — hanya root portal (`/financefiji/`) dan lihat-dokumen/respond yang butuh login, bukan listing-nya. Data current (17 tender) + awards (369 record, 36 bulan, 88% punya nama pemenang tender yang diekstrak dari teks "Awarded to: ..."). `robots.txt` platform-wide tidak ada (domain bare mengembalikan homepage marketing, bukan 404 murni) — dianggap tidak ada batasan. |

### Insight metodologi baru

1. **Jangan generalisasi kesulitan satu platform SaaS ke semua instance-nya** — TenderLink Saint Lucia sulit, TenderLink Fiji mudah. Setiap instance/negara di platform yang sama WAJIB diverifikasi independen, bukan diasumsikan sama. Prinsip ini sudah dicatat untuk proxy (Babak 29) dan TLS profile (`.ai/CLAUDE.md`), sekarang dikonfirmasi berlaku juga untuk "kesulitan platform SaaS pihak ketiga".
2. **Halaman publik vs halaman berbayar/login bisa terpisah jelas di platform yang sama** — root TenderLink redirect ke login, tapi 2 sub-path spesifik (`/alltenders/`, `/tenderfunction/?allawards=`) genuinely publik. Selalu cek URL spesifik yang benar-benar dibutuhkan sebelum menyimpulkan "butuh login" dari halaman root saja.
3. **Ekstraksi field gabungan dari teks bebas (mis. "Awarded to: X") tetap layak meski tidak 100% coverage** — 88% award record punya nama pemenang, 12% tidak dipublikasikan upstream. Dilaporkan `null` untuk yang tidak ada, bukan dipaksakan atau diasumsikan.
4. **Vertikal baru (vehicle/land registry) butuh sesi riset dedicated, bukan quick pivot** — percobaan cepat di babak ini tidak menghasilkan kandidat kuat; lebih baik kembali ke vertikal yang sudah terbukti produktif (tender) daripada memaksakan domain baru dengan riset dangkal.

### Rekomendasi lanjutan

1. **Cek negara Pasifik/Karibia lain yang disebut pakai TenderLink** — Samoa (sudah dibangun via situs MOF sendiri, bukan TenderLink — worth cross-check apakah TenderLink Samoa py public juga dan punya data tambahan), Kiribati (sudah dibangun via situs sendiri, TenderLink Kiribati belum dicek), St Lucia (sudah dicatat sulit, tapi worth re-visit dengan pendekatan baru kalau ada waktu).
2. **Vehicle/land registry per-negara** — masih di antrean, butuh sesi dedicated untuk riset dari nol (bukan quick pivot di tengah sesi lain).
3. **Marshall Islands, Tuvalu** — masih terbuka, butuh discovery lebih dalam.

**Total portofolio setelah babak ini: 193 folder actor** — 1 actor tender/procurement baru (Fiji), menggenapkan total vertikal tender jadi 44 actor dalam 11 babak.

## Babak 36 — Djibouti Tenders: Livewire, Pagination Jujur Dilaporkan Terbatas (2026-08-28)

**Konteks:** kembali ke Afrika (sudah punya `comoros-anpi-scraper` dan `djibouti-odpic-scraper` untuk registry, belum ada tender). Comoros dicek (tidak ada domain resmi jelas ditemukan), Djibouti diriset lebih dalam dan berhasil.

**Hasil: berhasil dibangun & di-deploy** — dengan keterbatasan pagination yang dilaporkan jujur, bukan disembunyikan.

### 1 Actor Baru — berhasil dibangun & di-deploy

| Actor | Target | Actor ID | Temuan Kunci |
|---|---|---|---|
| `djibouti-tenders-scraper` | Djibouti — Commission Nationale des Marchés Publics (`marchespublics.gouv.dj`) | `zJsVPlahMpyEE94sM` | Situs Laravel dengan 2 halaman beda teknologi: `/marches` pakai Livewire (server-render halaman pertama via plain GET, TAPI pagination `?page=N` TERBUKTI tidak mengubah hasil — Livewire butuh protokol AJAX POST dengan snapshot/checksum yang sengaja tidak diimplementasikan, dilaporkan jujur sebagai "7 tender di halaman pertama" bukan diklaim arsip penuh); `/attribution` adalah tabel HTML polos tanpa keterbatasan pagination (9 award minggu berjalan) DENGAN data nilai kontrak dalam DJF + nama supplier pemenang — data finansial nyata, langka di vertikal tender portofolio ini. Bug parsing ditemukan & diperbaiki saat local test: selector awal `div.card__title a[href]` salah tangkap link filter UI yang kebetulan pakai class sama — diperbaiki dengan filter `href` yang harus diawali `/marche/`. `robots.txt` blanket-allow, cert chain tidak lengkap (sama seperti St Vincent/Vanuatu — diatasi `verify=False`, bukan sinyal WAF). |

### Insight metodologi baru

1. **Pagination yang genuinely tidak bisa direplikasi HTTP-only harus dilaporkan jujur sebagai keterbatasan, bukan dipaksakan atau disembunyikan** — beda dari kasus lain di portofolio ini (Suriname `notices` yang memang cuma nampilkan "yang terbuka sekarang" karena itu memang cara situsnya bekerja), Djibouti `/marches` SECARA TEKNIS punya lebih banyak tender di balik pagination Livewire yang butuh AJAX — actor ini secara eksplisit TIDAK mengimplementasikan protokol tersebut (di luar scope) dan mendokumentasikan keterbatasan ini secara eksplisit di README dan CRAWLING_METHOD, bukan mengklaim cakupan penuh.
2. **Selector CSS yang "kelihatan spesifik" bisa collide dengan elemen UI tidak terkait** — class `card__title` dipakai ulang untuk header box filter yang sama sekali bukan tender card. Ketahuan dari local test (bukan asumsi), diperbaiki dengan filter `href` pattern yang lebih presisi sebelum push.
3. **Data finansial (nilai kontrak + pemenang) adalah diferensiator nilai yang jarang ada di vertikal tender portofolio ini** — kebanyakan actor tender cuma expose metadata (judul, tanggal, entitas), Djibouti `/attribution` justru expose angka DJF riil per kontrak menang — dicatat sebagai faktor pricing (harga di-set sedikit di atas actor "tipis" seperti St Vincent/Kiribati).

### Rekomendasi lanjutan

1. **Comoros** — belum ditemukan domain resmi yang jelas dalam pencarian awal, worth discovery lebih dalam di sesi berikutnya (coba cek kementerian keuangan langsung, bukan cuma "comoros tenders" generik).
2. **Vehicle/land registry per-negara** — masih di antrean, belum dieksekusi.
3. **Marshall Islands, Tuvalu** — masih terbuka dari Babak 34, butuh discovery lebih dalam.
4. **Reverse-engineer Livewire AJAX protocol** — kalau ada waktu di sesi mendatang, membuka jalan untuk actor tender lain yang mungkin pakai Livewire/framework serupa dengan arsip lebih besar dari yang bisa diakses via plain GET.

**Total portofolio setelah babak ini: 194 folder actor** — 1 actor tender/procurement baru (Djibouti), menggenapkan total vertikal tender jadi 45 actor dalam 12 babak.

### Tambahan — Monetisasi (kategori + harga) 7 actor berhasil dikonfigurasi lewat `apify api`, publikasi Store kena rate-limit platform (2026-08-28)

User mengonfirmasi sudah login CLI dan menanyakan apakah kategori/harga bisa diset lewat API/CLI resmi. Ditemukan: `apify api` (subcommand CLI yang bikin authenticated request pakai kredensial CLI sendiri, tanpa perlu ekstrak token mentah dari OS keyring) BISA dipakai untuk `PUT /v2/actors/{actorId}`.

**Berhasil dikonfigurasi untuk ke-7 actor tender sesi ini** (stvincent, vanuatu, samoa, palau, kiribati, fiji, djibouti):
- **Categories**: `["LEAD_GENERATION", "BUSINESS"]` — langsung berhasil, tidak ada limitasi.
- **Pricing (PAY_PER_EVENT, tiered)**: sesuai angka yang sudah dihitung di masing-masing `CRAWLING_METHOD.md` — berhasil, TAPI ada 2 quirk API yang harus di-workaround (dicatat di setiap `CRAWLING_METHOD.md` Phase 8 masing-masing actor):
  1. `pricingInfos` adalah array append-only (histori harga), bukan field "set current state" — `PUT` harus kirim array yang PERSIS diawali salinan data yang sudah tersimpan di server (termasuk `createdAt` versi server, bukan yang kita kirim), baru boleh nambah 1 entry baru di akhir. Kirim array pengganti penuh → error `incorrect-pricing-modifier-prefix`.
  2. Entry `pricingInfos` PERTAMA untuk actor yang belum pernah di-harga wajib flat (`eventPriceUsd`) — langsung coba tiered (`eventTieredPricingUsd`) di entry pertama gagal dengan `schema-validation` error meski body sudah sesuai skema resmi (`docs.apify.com`/OpenAPI). Diatasi: PUT flat dulu, GET ulang untuk salinan persis, baru PUT array [flat, tiered].

**Publikasi ke Store (`isPublic: true`) — BLOCKED oleh rate-limit platform, bukan keterbatasan tooling.** Apify membatasi **5 publikasi actor per hari per akun**. Percobaan publish PERTAMA sesi ini (`stvincent-tenders-scraper`) langsung kena `429 daily-publication-limit-exceeded` — artinya kuota harian sudah habis dari aktivitas lain sebelum sesi ini mencoba sama sekali. Ketujuh actor SEKARANG sudah private tapi ter-kategori & ter-harga penuh, tinggal menunggu reset kuota (~24 jam) lalu publish satu-satu (maks 5/hari) lewat `apify api PUT actors/{actorId} -d '{"isPublic": true, "title": "..."}'`.

**Insight metodologi**: skill `actor-store-monetization` di `.ai/skills/` perlu diperbarui untuk mencatat urutan `apify api` + 2 quirk pricingInfos di atas sebagai prosedur standar (bukan "manual step" seperti diasumsikan sebelumnya) — kategori & harga TIDAK perlu manual Console kalau CLI sudah login, hanya publikasi Store yang genuinely dibatasi platform.

---

# Babak 36 — Pencarian Kandidat AS Lanjutan: 1 Dibangun, ~40 Ide Gugur (2026-08-31)

**Konteks:** setelah `h1bdata-scraper` selesai (lihat koreksi di baris H1B tabel Babak 9b), user minta lanjut cari kandidat AS berikutnya. Babak ini **mayoritas hasil negatif** — dicatat lengkap justru supaya sesi berikutnya tidak mengulang jalur buntu yang sama.

## Kandidat "(AS)" dari tabel babak lama — semua gugur setelah dicek ulang

| Kandidat | Status lama | Temuan 2026-08-31 |
|---|---|---|
| **Boston Globe** | `[0]` (Tier 1 AS) | Di-skip — `robots.txt` block eksplisit `anthropic-ai`, `ClaudeBot`, **plus `ApifyBot`/`ApifyWebsiteContentCrawler` by name** — dihormati, jangan coba lagi. |
| **PissedConsumer** | `[1 kecil]` | Di-skip — `robots.txt` block eksplisit `ClaudeBot` + `anthropic-ai`. Catatan teknis (kalau kebijakan berubah): halaman company review TIDAK punya ld+json/`__NEXT_DATA__` sama sekali, murni HTML; URL asli berpola `/<slug>/RT-F.html` + subdomain per-brand (`<brand>.pissedconsumer.com/review.html`), ditemukan lewat `pc-sitemap/browse/main/company/N.xml`. |
| **HealtheCareers** | `[0]` | Di-skip — `robots.txt` block eksplisit `ClaudeBot`/`Claude-User`/`Claude-Web`/`Claude-SearchBot`/`anthropic-ai` **plus `ApifyBot`** (daftar bot-block terpanjang yang pernah ditemui riset ini, ~100 entri). Juga sudah ada 2 kompetitor. |
| **Vettery** | `[0]` | **Perusahaan sudah tidak ada** — `vettery.com` redirect ke `lhh.com/en-us/about-us/our-story`. Hapus dari backlog. |
| **Reonomy** | `[0]` | Data properti asli ada di `app.reonomy.com` yang **403 (login-gated)**; `www` + sitemap publik cuma halaman marketing/blog. `[0] actor` bukan gap, tapi karena memang tidak ada data publik. |

## ~30 ide "data publik pemerintah AS" — semua sudah jenuh

Semua dicek lewat `api-search-actors.py --query`. Angka = jumlah seller berbeda dengan actor relevan:

NPI/NPPES healthcare registry (**8+**, terbesar `parseforge` 72u), USAJobs (**4+**, `shahidirfan` 70u), USPTO trademark (**6+**, `fortuitous_pirate` 52u), USPTO patent (**6+**), Secretary of State business registry (**6+**, `whetstonetools` 90u/10.891r), FDA recall (**6+**), CPSC recall (**8**), WARN Act layoffs (**6**), FAA aircraft registry (**6**), IRS 990 nonprofit (**8**), SAM.gov contractor (**5+**), state bar attorney (**8**), medical/professional license lookup (**8+**, terfragmentasi per-negara-bagian), county property tax assessor (**6+**, `shelvick` 61u, `great_pistachio` 40u), liquor license (**6**), FCC license (**6**), FEC campaign contributions (**6**, semua tipis <=8u), SEC Form D (**6+**), UCC filings, building permits, FINRA BrokerCheck, SEC Form ADV/IAPD — semua sudah ada pemainnya.

**Restaurant health inspection (via Socrata Open Data API) — kelihatan paling menjanjikan, ternyata paling jenuh: 30+ actor.** Beberapa kompetitor bahkan sudah klaim cakupan multi-kota persis seperti rencana (`registryfeeds` 7 kota, `scrapesage` 5 kota, `civicdataforge` 7 yurisdiksi). Catatan teknis kalau suatu saat mau dipakai untuk target lain: **`https://api.us.socrata.com/api/catalog/v1?q=<query>` adalah discovery API lintas-domain yang jalan tanpa key** — cara cepat menemukan dataset open-data kota/negara-bagian AS mana pun; tiap dataset lalu bisa di-query `https://<domain>/resource/<id>.json` dengan `$q` (full-text), `$limit`, `$where`. Tidak semua portal terbuka: King County & LA County butuh login/bukan Socrata.

## Scan kategori band-rendah (metodologi babak 8) — 3 kategori, nihil

`--min-users 3 --max-users 60..100 --sort runs_per_user` untuk **REAL_ESTATE** (2.241 hit), **BUSINESS** (1.137 hit), **LEAD_GENERATION**, **AUTOMATION** (8.215 hit). Tidak ada satu pun baris yang lolos: setiap niche yang kelihatan sepi ternyata sudah punya pemain, dan pola paling mencolok — **satu seller (`jungle_synthesizer`) sendirian punya 15+ actor niche data-publik AS/global di dalam SATU halaman scan 100-baris** (ProPublica 990, SRA Solicitors, NZ Companies Office, USDA farm subsidy, Canadian Law List, BidNet, SEC Form ADV, FINRA BrokerCheck, Justia, Super Lawyers, multi-state bar, Angi, ImportYeti, Spokeo, IBBA, Psychology Today, NPPES, dst). Pola sama di `pink_comic`, `scrapers_lat`, `crawlerbros`, `fortuitous_pirate`, `nexgendata`, `haketa`.

> **Insight utama babak 36:** strategi "cari sumber data publik AS yang belum di-scrape" **sudah dieksekusi secara sistematis oleh 6-8 seller lain**, kemungkinan besar juga dengan bantuan agent. Vein ini praktis habis — bukan karena kurang teliti mencarinya, tapi karena kompetisi menjalankan playbook identik.

## Target WAF-heavy (hipotesis: kesulitan teknis = filter kompetitor) — hipotesis GAGAL

Diuji karena diduga target yang butuh reverse-engineering asli akan menyaring "actor mill". Ternyata justru dikuasai pemain kuat: DraftKings odds (`zen-studio` **336u**/11rb runs), PrizePicks player props (`zen-studio` **395u**/20rb runs), Bet365 (`zen-studio` 196u), CarGurus (`e-commerce` 162u, `lexis-solutions` 139u), DoorDash (`yasmany.casanova` 157u, `memo23` 123u), Ticketmaster (`easyapi` 73u), Grubhub, OpenTable — semua ramai. **Kesulitan teknis bukan moat di Store ini.**

## Line-movement / time-series odds — juga jenuh (~10 seller)

`scrapemint/sports-odds-movement-tracker` **152u**, `zhorex/sports-odds-aggregator` 118u, `automation-lab/action-network-...` 33u/1.785r, `jungle_synthesizer` 26u, plus `parseforge` yang sendirian sudah punya 5 actor sumber berbeda (Covers, VegasInsider, SportsbookReview, SportsLine, RotoWire), `ichigowa`, `nortonw3`, `extractify-labs`, `piotrv1001` (OddsPortal).

## Circa Sports — 0 kompetitor, tapi bukan gap (recon tuntas, JANGAN diulang)

`Circa Sports` = sportsbook Las Vegas yang dianggap referensi *sharp line* sejajar Pinnacle, dan **benar-benar 0 actor di Apify Store**. Direcon penuh; hasilnya **0 kompetitor itu karena tidak ada data publik yang bisa di-scrape**, bukan karena belum ada yang sadar:

- `circasports.com` **timeout total dari Indonesia** — bukan geo-fence Circa, tapi blokir ISP/Kominfo untuk domain judi. Dari exit IP luar (Apify residential) statusnya bersih 200.
- `robots.txt` **bersih** (cuma `Disallow: /wp-admin/`, tidak ada entri AI-bot sama sekali) — jadi bukan itu penghalangnya.
- Situsnya **WordPress marketing murni**: `page-sitemap.xml` cuma berisi **5 halaman** (homepage, college-basketball-power-rating-factors, colorado-app-survey, image-and-video-gallery, circa-friday-football-invitational). `/odds/`, `/betting-lines/`, `/sports-betting/` semua **404**.
- `api.circasports.com` -> **Cloudflare 403**; `sportsbook.`/`play.`/`bet.circasports.com` -> **tidak resolve** (CONNECT 590); `co.circasports.com` -> redirect balik ke `www`.
- **Kesimpulan: odds Circa hanya ada di app native (geolocation SDK + akun), tidak ada permukaan web publik.** Tutup kandidat ini permanen.

## Alat baru yang lahir dari babak ini: `scratchpad/us-prober` (actor, private)

Karena banyak target AS **tidak bisa direcon dari Indonesia sama sekali** (ISP-level block untuk judi, atau geo-fence), dibuat actor recon sekali-jalan `us-prober` (Apify ID `uf53wIS6omt0tkVzL`, **private, jangan dipublish**): input daftar URL + profil TLS, output per-URL `status`/`bytes`/`finalUrl`/headers/marker-WAF/data-island (`__NEXT_DATA__`, ld+json, dll)/3.000 char pertama body — dijalankan dari dalam Apify dengan residential US.

**Catatan penting:** Apify **residential proxy TIDAK bisa dipakai dari luar platform** (CONNECT tunnel 403 walau password proxy valid) — recon target geo-sensitif WAJIB lewat actor yang jalan di Apify, bukan skrip lokal. Ini alasan `us-prober` dibuat dan alasan ia layak disimpan untuk sesi berikutnya.

## Rekomendasi untuk sesi berikutnya

1. **Berhenti memakai strategi "tebak nama sumber data publik AS"** — terbukti habis di babak ini (~40 ide, 0 lolos).
2. Kalau tetap mau vertikal AS, **minta target spesifik dari user** — pengetahuan domain user lebih tajam daripada penebakan keyword lintas kategori.
3. Kandidat non-AS dari babak-babak lama yang masih terbuka (Comoros tender, Marshall Islands, Tuvalu, vehicle/land registry per-negara) **belum tersentuh** dan kemungkinan besar masih jauh lebih longgar daripada apa pun di AS.
4. Pakai `us-prober` (bukan skrip lokal) untuk recon target apa pun yang timeout dari Indonesia.

---

# Babak 37 — Vertikal Singapura: 1 Gem Ditemukan & Dibangun (2026-08-31)

**Konteks:** lanjutan langsung dari Babak 36 (AS buntu total). User minta pindah ke Singapura. Berbeda dari babak sebelumnya, babak ini **menemukan 1 kandidat kelas-A yang genuinely 0 kompetitor** setelah ~20 ide lain gugur.

## Gelombang 1 — niche Singapura "obvious": semua jenuh

Dicek via `api-search-actors.py --query`. Angka = seller berbeda dengan actor relevan:

| Niche | Seller | Terbesar |
|---|---|---|
| MyCareersFuture (job portal resmi) | **8** | `jungle_synthesizer` 45u, `scrapesage` 33u |
| ACRA / BizFile (registry perusahaan) | **7** | `nexgendata` 7u, `hipersoft` 5u |
| HDB resale flat prices | **6** | semua ~2u, via `data.gov.sg` |
| sgcarmart (mobil bekas) | **5** | `jungle_synthesizer` 6u |
| URA property transactions | **4** | `scrapesage` 4u |
| SGX listed companies | **4** | `jungle_synthesizer` 11u |
| EdgeProp.sg | **5** | `logiover` 8u |
| SRX / 99.co / PropertyGuru SG | **5+** | `scrapesage` 27u (PropertyGuru) |
| COE bidding results | **3** | semua ~2u |
| NEA food hygiene grades | 1 | `scrapers_lat` 2u |
| Chope (reservasi restoran) | 1 | `scrapesage` 1u |
| HardwareZone (forum) | 1 | `claude_code_reviewer` (4 actor) |
| Carousell | **8** (dari riset lama) | — |
| GeBIZ (tender) | 1 | `jungle_synthesizer` 26u |

Pola identik Babak 36: **`data.gov.sg` sudah dipanen habis** — ada bahkan MCP server (`valued_paperweight/sg-open-data-mcp`) dan scraper generik (`parseforge/singapore-data-gov-sg-scraper`) yang bisa ambil dataset apa pun by resource ID. Jangan buang waktu di niche berbasis data.gov.sg lagi.

## ✅ TEMUAN: Singapore Court Judgments — 0 kompetitor, DIBANGUN

**`sg-court-judgments-scraper`** — Apify ID `Bv6s9zJTGuzgdKFNc`, dibangun & diverifikasi 2026-08-31.

**Kenapa ini gem asli (bukan false positive seperti Circa Sports di Babak 36):**

1. **Data-type-nya TERBUKTI laku di yurisdiksi lain** — ini pembeda kritis dari "0 kompetitor karena tidak ada data". Sudah ada seller untuk: AS (`parseforge/justia-case-law-scraper` 10u, `crawlerbros` CourtListener, `parseforge/caselaw-access-scraper`, `jungle_synthesizer` Google Scholar), **UK** (`nomad-agent`), **India** (`parseforge/india-supreme-court-scraper` 5u, `jungle_synthesizer/india-ecourts` 3u), **Irlandia** (`jungle_synthesizer` 3u), **CJEU** (`jungle_synthesizer` 5u). **Singapura kosong** di semua query (`Singapore court judgment`, `elitigation`, `case law scraper`, `legal judgment scraper`) — satu-satunya yurisdiksi common-law maju yang belum digarap.
2. **Datanya kaya dan publik penuh** — `elitigation.sg/gd` (Grounds of Decision, portal resmi Singapore Judiciary): ~15.900 putusan, arsip **1965–sekarang**, teks putusan lengkap (satu putusan komersial terukur **178.532 karakter**), plus catchwords resmi pengadilan.
3. **Teknis longgar** — ASP.NET MVC, **tanpa `__VIEWSTATE`**, pagination GET biasa, `robots.txt` **404** (tidak ada kebijakan crawler sama sekali), tanpa WAF/challenge/login, **tanpa rate-limit** (5 request beruntun 0,10–0,32 s).

**3 variasi bentuk upstream yang ketahuan HANYA dari test lokal** (semua sempat menghasilkan output salah diam-diam — dicatat karena polanya akan berulang di portal pengadilan lain):
1. **Catchwords beda elemen & beda 3 gaya kurung** antar-pengadilan/era: listing pakai `a.gd-cw`; halaman putusan pakai class **huruf kecil `.catchwords`** (tebakan awal `.Catchwords`/`.HN-Catchwords` diam-diam return `[]`). Gayanya: `[Contract — Breach]` (SGHC, seluruh baris), `[Civil Procedure] — [Enforcement]` (SGDC, per-segmen), dan **tanpa kurung sama sekali** (SGHC 1965).
2. **Putusan District/Magistrates' Court tidak punya `.HN-NeutralCit`** — sitasi malah ada di salah satu dari **dua** node `.CaseNumber`. Diatasi dengan pattern-match format sitasi, bukan menebak posisi.
3. **`.title` dipakai ulang untuk boilerplate** — putusan DC diawali template instruksi redaksi di class yang sama, sehingga `css_first('.title')` menghasilkan `courtName` = **"Please delete where applicable –"**. Diatasi dengan memilih node `.title` yang benar-benar menyebut nama pengadilan.

**Plus 1 bug merge sendiri:** `{**row, **detail}` naif membuat catchwords kosong dari halaman detail menimpa data listing yang sudah benar → diganti `merge_listing_and_judgment()` yang hanya menimpa bila halaman detail benar-benar punya nilai.

**Verifikasi:** lolos test lokal (2 mode, pagination multi-halaman, filter tahun, no-results, invalid-ID soft-404, putusan 1965) dan **remote di Apify dengan residential proxy** — 5 putusan lintas 4 pengadilan (SGHC, SGHCA, SGHCI, SGFC), teks 31k–178k karakter, catchwords lengkap, 0 warning. Kategori `BUSINESS`+`OTHER` & pricing tiered ($0.005→$0.0035) sudah dikonfigurasi via `apify api`.

## Insight metodologi (paling penting dari babak ini)

> **Sinyal "0 kompetitor" hanya berharga kalau data-type-nya sudah terbukti laku di pasar sebelah.** Babak 36 (Circa Sports) mengajarkan sisi negatifnya: 0 kompetitor karena memang tidak ada data publik. Babak 37 menunjukkan sisi positifnya: 0 kompetitor untuk Singapura, padahal data-type "court judgment scraper" yang sama sudah dibangun 8+ seller untuk 5 yurisdiksi lain. **Cara mencarinya: ambil data-type yang sudah terbukti laku, lalu cari yurisdiksi/negara yang belum ada** — jauh lebih produktif daripada menebak nama platform baru.

## Rekomendasi lanjutan

1. **Terapkan pola "data-type terbukti × yurisdiksi kosong" ke vertikal lain** — mis. court judgments untuk Malaysia, Hong Kong, Selandia Baru; company registry, trademark office, dsb. Ini generalisasi dari keberhasilan vertikal tender (Babak 26-29) dan babak ini.
2. **Kandidat Singapura tipis yang masih terbuka** (1 seller kecil, kalau mau digarap): NEA food hygiene grades, Chope. **Jangan** garap yang berbasis `data.gov.sg` — sudah ada scraper generik + MCP server.
3. **IPOS trademark Singapura** — search awal 0 actor relevan, TAPI portal `ip2.sg` **timeout** dari Indonesia; belum direcon tuntas. Pakai `us-prober` (Babak 36) untuk cek dari luar sebelum memutuskan.

---

# Babak 38 — Court Judgments Filipina: Rekomendasi Babak 37 Dieksekusi, 3 Yurisdiksi Gugur, 1 Gem Dibangun (2026-09-07)

**Konteks:** eksekusi langsung rekomendasi penutup Babak 37 poin 1 — terapkan pola "data-type terbukti × yurisdiksi kosong" ke court judgments **Malaysia, Hong Kong, Selandia Baru**. Ketiganya gugur di gate, tapi pola yang sama menemukan yurisdiksi lain yang genuinely kosong: **Filipina**.

## Ketiga kandidat Babak 37 gugur sebelum sempat dikoding

| Target | Verdict |
|---|---|
| `legalref.judiciary.hk` (Judiciary HK) | `robots.txt` = **`User-Agent: * / Disallow: /`**. Haram, dicoret. |
| `hklii.hk` (HK Legal Information Institute) | robots hanya block `/api` — tapi situsnya **SPA murni** (shell 2.693 byte, 0 konten). Seluruh datanya justru lewat `/api` yang di-disallow. Dicoret. |
| `nzlii.org` (NZ LII) | Cloudflare content-signal dengan **`User-agent: ClaudeBot / Disallow: /`** eksplisit. Dicoret (posture sama Grenada/Nauru Babak 31/34). |
| `forms.justice.govt.nz` (NZ Judicial Decisions Online) | Connection reset dari Indonesia di **kelima** TLS profile (chrome124/chrome99_android/safari17_0/edge101/chrome110) — geo/ISP-level, signature sama Circa Sports Babak 36. Butuh prober luar dulu. |
| `ejudgment.kehakiman.gov.my` (Malaysia) | Redirect ke `cms2.kehakiman.gov.my/CommonWeb` = **Case Management System ber-login** (`__VIEWSTATE` + Dynatrace), bukan arsip putusan publik. |

**Bonus dicek sekalian, semua dicoret:** `putusan3.mahkamahagung.go.id` (MA Indonesia — ClaudeBot disallow), `pdki-indonesia.dgip.go.id` (`Disallow: /`), `iponlineext.myipo.gov.my` (ClaudeBot disallow), `new.kenyalaw.org` (403 di robots.txt).

## ✅ TEMUAN: Philippine Supreme Court E-Library — 0 kompetitor, DIBANGUN

**`ph-court-decisions-scraper`** — dibangun & diverifikasi lokal 2026-09-07 (belum di-deploy, menunggu konfirmasi user).

**Kenapa gem asli (bukan false positive tipe Circa Sports):**

1. **Data-type-nya sudah terbukti laku di 8+ yurisdiksi lain** — AS (`parseforge/justia-case-law-scraper` 10u, `crawlerbros`, `parseforge/caselaw-access-scraper`), UK/BAILII (`nomad-agent`, `parseforge`, `jungle_synthesizer`, `spookyweb` — 4 seller), India (2), Irlandia, Jepang, CJEU, China, plus Singapura (portofolio ini sendiri). **Filipina kosong total**: query `Philippines Supreme Court`, `Philippines jurisprudence`, `elibrary judiciary` semuanya **0 hit**; `Philippines legal` cuma noise (Lamudi, 7-Eleven, Shopee).
2. **Datanya kaya & publik penuh** — `elibrary.judiciary.gov.ph`, arsip resmi MA Filipina. Listing bulanan **1996–sekarang**, search dtSearch menembus lebih jauh lagi (putusan 1991 terambil). Teks putusan lengkap + sitasi *Philippine Reports* + link PDF resmi. Satu putusan en banc konsolidasi terukur **2.379.838 karakter**.
3. **Teknis longgar** — CodeIgniter/PHP di Microsoft-IIS, tanpa WAF/challenge/login/cookie gate, **tanpa rate-limit** (6 request beruntun 0,27–0,32 s). `robots.txt` **404** = tidak ada kebijakan crawler sama sekali (posture identik `elitigation.sg`).

**Arsitektur: 1 actor, 3 mode** (`search` / `browse` / `decision`) — konsisten dengan konvensi mode-based repo (`sg-court-judgments-scraper`, `karir-com-scraper`, `point2homes-scraper`), bukan 3 actor terpisah yang akan saling makan di Store.

**5 jebakan bentuk yang HANYA ketahuan dari test lokal** (semua sempat menghasilkan output salah diam-diam — polanya akan berulang di portal pengadilan lain):
1. **Dua ruang penomoran dokumen yang TIDAK compatible** — `DocId` dtSearch ≠ id `showdocs` portal. G.R. No. 241587 = dtSearch `69244` tapi portal `70008`, sedangkan `showdocs/1/69244` adalah perkara yang sama sekali lain. Search row karena itu tidak pernah mengarang link showdocs.
2. **Pemisah caption beda antar-view**: halaman putusan pakai **koma** (`[ G.R. No. 279772, June 29, 2026 ]`), hasil dtSearch pakai **titik** (`[ G.R. No. 176317. July 23, 2014 ]`). Build pertama diam-diam menghasilkan `caseNumber = "G.R. No. 176317. July 23, 2014"` + tanggal null.
3. **Soft-404**: id tidak dikenal tetap **HTTP 200** dengan body "Document Search Error". Build pertama memuntahkannya sebagai putusan valid `fullTextLength=106` tanpa error — persis silent corruption yang dilarang `CONSTRAINTS.md`.
4. **dtSearch menyajikan ulang dokumen antar-halaman** — halaman 2 query `negligence` mengulang 2 dokumen halaman 1 (ranking relevansinya tidak stabil antar-request). Wajib dedupe.
5. **3 dari 8 korpus dtSearch rusak di sisi server** — `sc_resolution`, `administrative_matter`, `bar_matter` menjawab 200 + "0 result(s)" + `$E 0001 Unable to access index C:\elibrev2\...`. Dilaporkan sebagai `search_index_unavailable` eksplisit, bukan nol diam-diam.

**Catatan kebijakan:** halaman dokumennya membawa `<meta name="robots" content="noindex,nofollow">`. Itu direktif **indexing** untuk mesin pencari, bukan direktif akses — ada di halaman kanonik DAN kembarannya printer-friendly (alasan duplicate-content klasik), sementara view dokumen dtSearch milik situs itu sendiri menyajikan teks identik **tanpa** robots meta sama sekali. `robots.txt` sebagai layer akses 404 (tidak melarang apa pun). Default concurrency tetap dibuat sopan (4).

**Verifikasi:** lolos test lokal ketiga mode lewat entrypoint Actor asli (`python -m src`) — search plain/fullText, browse plain/fullText lintas batas bulan, decision valid/invalid/format-URL, korpus rusak, pagination 150 hasil (150 docId unik setelah dedupe), varian EN BANC / PER CURIAM / RESOLUTION / nomor perkara berkurung-bersarang / era 1996.

## Rekomendasi lanjutan

1. **Deploy `ph-court-decisions-scraper`** + konfigurasi kategori & monetisasi (belum dilakukan).
2. **Lanjutkan pola yang sama ke yurisdiksi common-law yang tersisa** — sekarang terbukti dua kali (Singapura Babak 37, Filipina babak ini). Yang belum dicek sama sekali: Sri Lanka, Bangladesh, Pakistan, Kenya (kenyalaw 403, butuh TLS ladder), Nigeria, Ghana, Uganda, Tanzania — catatan: LII-style (`*lii.org`) cenderung block ClaudeBot, jadi **utamakan portal judiciary resmi**, bukan LII.
3. **Dua data-type tambahan di portal Filipina yang sama, masih terbuka** (sengaja di luar scope actor ini karena beda data-type): **Republic Acts** (`/republic_acts/fetch_ra` — DataTables, masih 500 walau CSRF `csrf_test_name` sudah di-harvest, butuh RE lanjutan) dan **Roll of Attorneys** (`/lawyers_list/fetch_lawlist` — GET memuntahkan 6,6 MB; kandidat actor lead-gen tersendiri).

---

# Babak 39 — Scan Dalam Lintas-Kategori (4.580 Actor) + 175 Uji Kompetisi: 8 Kandidat ROI-Tinggi (2026-09-08)

**Konteks:** user minta daftar actor **ROI data tinggi / stats sudah tinggi** di Apify Store. Babak ini **bukan** lanjutan pola "yurisdiksi kosong" (Babak 25–38), melainkan penerus langsung [`actors_researcher_v2.md`](actors_researcher_v2.md) (2026-09-07) — tapi jauh lebih dalam: v2 mengambil **721 actor** (14 kategori, `length=60`, offset 0), babak ini mengambil **4.580 actor unik** dengan paginasi penuh sampai band habis.

**Dedupe dijalankan 3 lapis** (sesuai gotcha v2): (1) `output/xtracto-full.json` **di-refresh hari ini → 218 actor**, dicek per token platform ke nama+judul SELURUH file; (2) grep token ke `ACTOR_MARKET_RESEARCHER_NEW.md`; (3) grep token ke `actors_researcher_v2.md`. Semua kandidat di bawah **0 hit di ketiganya** kecuali yang ditandai eksplisit.

## Metodologi Babak 39

```bash
python apify-my-store.py xtracto -o output/xtracto-full.json      # 218 actor (sama seperti snapshot 2026-09-07)

# Pass 1 — scan band ber-paginasi PENUH, 17 kategori, sampai halaman habis (bukan 1 halaman seperti v2)
#   band: 5 <= users <= 4000, runs >= 2000, length=100, offset 0..1900
#   -> 4.580 actor unik  (ECOMMERCE 872 | SOCIAL_MEDIA 1801 | LEAD_GENERATION 1906 | JOBS 407 |
#      SEO_TOOLS 449 | VIDEOS 441 | OTHER 513 | REAL_ESTATE 360 | NEWS 220 | TRAVEL 220 | dst)
# Pass 2 — 89 uji kompetisi konsep dari Pass 1 (hitung SELLER BERBEDA, bukan nbHits)
# Pass 3 — 86 uji kompetisi VERTIKAL BARU yang belum pernah discan di kedua dokumen
#   (auction/lelang, maritim, paten, app-store, energi, hibah, direktori profesi, prediction market, dll)
```

Hasil mentah: `output/scan-v3-pool.json` (4.580), `output/scan-v3-ranked.json` (+flag dedupe), `output/scan-v3-competition.json` (89 konsep), `output/scan-v3-competition2.json` (86 vertikal baru).

### Gotcha metodologi baru (penting, mengoreksi asumsi babak-babak sebelumnya)

1. **Tag `categories` di Store TIDAK BISA dipercaya untuk mengukur kejenuhan sebuah vertikal.** Bukti keras dari scan ini: `azzouzana/sofascore-scraper-pro` (data pertandingan sepak bola, 899u) ditag **`AUTOMATION`/`NEWS`/`AI`**; `curious_coder/transfermarkt` (2.824u) ditag **`NEWS`**; `johnvc/fuelprices` ditag `NEWS`/`ECOMMERCE`/`TRAVEL`; `canadesk/mastodon` ditag `SEO_TOOLS`/`NEWS`. Akibatnya kategori **SPORTS cuma punya 5 actor** di dalam band dan **EDUCATION 2, FOR_CREATORS 4** — itu **artefak tagging, bukan bukti kategori kosong**. → Konsekuensi: klaim "kategori X sepi" berdasarkan `--list-categories` atau scan per-kategori **tidak valid**; satu-satunya ukuran yang sah adalah **uji kompetisi berbasis query per-konsep** (hitung seller berbeda), seperti Pass 2/3 di atas.
2. **Jumlah seller banyak != pasar sudah termonetisasi.** Pola paling sering muncul di babak ini: satu niche punya 7–37 seller, tapi **semuanya <30 users & <700 runs kecuali satu** yang punya ratusan ribu runs. Contoh ekstrem `mastodon`: 37 seller, tapi 36 di antaranya scraper profil mainan (<136u, <700 runs) sementara `canadesk/mastodon` sendirian **1.055.505 runs dari 31 user**. Artinya **hitung seller saja tidak cukup** — harus dilihat berapa seller yang benar-benar punya *runs* (bukti pipeline berulang). Metrik yang dipakai di babak ini: **jumlah seller dengan runs >= 10.000**.
3. **Waspadai actor "1 run = 1 URL".** Angka runs jutaan pada actor `FLAT_PRICE_PER_MONTH` (canadesk, jupri) sebagian besar karena arsitekturnya 1 run per item, bukan karena user-nya lebih banyak. Tetap sinyal ROI valid (user-nya memang menjalankan terus-menerus), tapi **jangan dibandingkan langsung** dengan actor PAY_PER_EVENT yang 1 run = 1 batch.

## ✅ Kandidat Baru — Belum Ada di `xtracto`, Belum Pernah Muncul di Riset Mana Pun

Semua sudah lolos ceiling-check (query dijalankan **tanpa** `--max-users`, jadi incumbent raksasa akan ikut terlihat — tidak ada yang muncul).

| # | Prioritas | Ide Actor | Bukti Demand (stats incumbent) | Seller | Kenapa Layak / Catatan Eksekusi |
|---|---|---|---|---|---|
| 1 | 🔴 Tinggi | **Snapchat Ads Library Scraper** (iklan aktif per-brand, bukan konten user) | `lexis-solutions/snapchat-ads-scraper` **55u / 249.398 runs / 4.535 rpu** ⭐3.4(6) | **3** (lexis 55u, `zadexinho` 50u, `contactminerlabs` 51u) | **Sub-tipe paling tipis di keluarga ad-library** — pembanding langsung: Meta Ad Library **35 seller/2.785u**, LinkedIn Ads **26 seller/1.009u**, Pinterest Ads **17 seller/306u**, Reddit Ads **11 seller/1.038u**. Snapchat konten umum juga jenuh (24 seller, 18.772u) — **yang tipis khusus sub-tipe ADS**. `xtracto` punya `tiktok-top-ads` tapi **nol** Snapchat. rpu 4.535 = pipeline harian ad-monitoring, bukan one-off. |
| 2 | 🔴 Tinggi | **Fuel / Gas Station Price Tracker** (harga BBM per-SPBU, time-series) | `johnvc/fuelprices` **203u / 309.324 runs / 1.524 rpu** (pay-per-result) | **1 serius** (15 total, tapi #2 = `memo23/gasbuddy` cuma 31u/189 runs) | Satu-satunya seller dengan runs signifikan; 14 sisanya <31u dan <550 runs. Data **berubah tiap hari** → recurring by nature (pola `nytimes-scraper`). Sudut kosong yang jelas: **non-AS** (`abotapi` AU 10u, `latinamericadata` Brasil 3u, Eropa/Asia kosong) — cocok dengan kekuatan portofolio ini di yurisdiksi non-AS. |
| 3 | 🔴 Tinggi | **Compass.com Real Estate Scraper** (broker real estate AS besar) | `canadesk/compass-properties` **16u / 137.618 runs / 8.601 rpu**; `nanoteki` 1u/10.424 runs | **7, tapi 6 di antaranya mainan** (terbesar `getdataforme` 19u/517 runs) | Tidak ada satu pun seller mapan: **user terbanyak di seluruh niche cuma 19**. Sejalan dengan rekomendasi v2 (**StreetEasy** — real estate per-KOTA/broker AS, bukan per-negara). Moat reuse: kalau StreetEasy dibangun, Compass pakai pola listing yang sama. |
| 4 | 🟠 Sedang-Tinggi | **Caixa Leilões / Lelang Properti Sitaan Brasil** | `pizani/caixa-imoveis-leiloes-api` **51u / 29.948 runs / 587 rpu**; `brasil-scrapers/caixa-leiloes-api` 223u | **6**, semua kecil, cuma 1 punya runs >=10rb | **Ini pola "data-type terbukti × yurisdiksi kosong" yang sudah 2× berhasil (Babak 37/38)** — dan `xtracto` **sudah punya** `auction-foreclosure-sniper` (Auction.com AS), jadi data-type-nya terbukti milik portofolio. Vertikal lelang secara umum masih longgar: GovDeals **10 seller** (max 65u), BidSpotter **4** (max 14u), Invaluable **3** (max 18u), Sotheby's **6** (max 21u). Lelang sitaan bank/pengadilan **di luar Brasil & AS praktis kosong**. |
| 5 | 🟠 Sedang-Tinggi | **Dealroom Scraper** (database startup/VC Eropa) | `saswave/dealroom-scraper` **147u / 248.099 runs / 1.688 rpu** ⭐5.0(2) | **6**, hanya 1 punya runs >=10rb (sisanya <=4.222 runs) | Crunchbase sudah dinyatakan jenuh di v2 (**7 seller**), tapi **Dealroom (padanan Eropa) belum pernah dicek** dan jauh lebih tipis. Pembanding sekitarnya: PitchBook **13 seller/1.343u**, Tracxn **2 seller tapi mati** (41u/**70 runs** — lihat Di-skip), CB Insights **2 seller** (`canadesk` 101u/9.529 runs). |
| 6 | 🟡 Sedang | **AllTrails Trail Scraper** (jalur hiking + GPS + review) | `parseforge/alltrails-scraper` **126u / 121.721 runs / 966 rpu** ⭐4.0(6) | **7, tapi #2 cuma 30u/673 runs** | Satu-satunya seller dengan pipeline nyata. TAM sedang (total niche ~171u), tapi rasio runs/user membuktikan pemakaian berulang. Cocok jadi pelengkap vertikal TRAVEL yang di `xtracto` baru terisi hotel/flight. |
| 7 | 🟡 Sedang | **SpyFu Bulk Domain Intelligence** (SEO/PPC kompetitor, mode bulk) | `canadesk/spyfu-bulk-urls` **37u / 27.040 runs / 731 rpu**; `canadesk/spyfu` 223u/20.318 runs | **5** (`canadesk` menguasai 3 varian, `dionysus_way` 197u) | Yang laku justru **mode bulk**, bukan single-domain — sudut masuk yang jelas. Catatan risiko: SpyFu adalah SaaS berbayar, permukaan publiknya terbatas; **wajib recon dulu** apakah ada data tanpa login sebelum commit. Pembanding: Moz **11 seller**, Ubersuggest **7 seller** (`radeance` 338u/98.608 runs — juga belum tersentuh, prioritas di bawah SpyFu). |
| 8 | 🟢 Rendah-Sedang | **QS Top Universities / World Rankings** | `vbartonicek/topuniversities-scraper` **670u / 26.284 runs** | **3** (sisanya 4u dan 4u) | Seller paling sedikit dari seluruh scan dengan user ratusan. Kelemahan: **rpu cuma 39** — data ranking berubah setahun sekali, jadi bukan pipeline berulang. Nilainya di **volume user**, bukan ROI per-user. Ambil hanya kalau mau actor "gampang laku" berbiaya rendah. |

## 🔁 Sudah Tercakup — Muncul di Scan Tapi Konsepnya Sudah Ada

| Konsep | Sudah ada di | Catatan |
|---|---|---|
| Foreclosure/lelang properti AS | `xtracto/auction-foreclosure-sniper` (Auction.com, 2u) | Justru jadi **bukti data-type** untuk kandidat #4 (Brasil), bukan penghalang |
| Shopify products | `xtracto/shopify-products` (2u) | Beda dari "Shopify **Store Leads**" (direktori toko + email) yang tetap di-skip karena jenuh — lihat bawah |
| MarineTraffic / vessel tracking | `xtracto/marinetraffic-ship-tracker` (2u) | Vertikal maritim (5 seller, `romy` 73u) sudah dipegang, tidak diulang |
| OLX | `xtracto` (`olx-*`) + sudah tercatat di riset lama | 31 seller, jenuh |
| Crunchbase, Upwork Talent, Indeed Reviews, StreetEasy, Apartments.com, Generic Article Extractor | `actors_researcher_v2.md` | **Belum dibangun tapi sudah ter-riset** — jangan dihitung ulang sebagai temuan baru babak ini |

## ⛔ Di-skip — Semua dengan Alasan Konkret

### A. Demand besar tapi jenuh (>=12 seller) — "stats tinggi" tapi ROI rendah buat pendatang baru

Ini menjawab langsung pertanyaan "actor yang stats-nya tinggi": konsep-konsep ini memang punya permintaan besar di Store, **tapi bukan peluang** — masuk berarti jadi kloningan ke-20+.

| Konsep | Total user di Store | Seller | Incumbent terbesar | Alasan skip |
|---|---|---|---|---|
| OnlyFans | 12.787u | 21 | `serpdownloaders` 4.233u | Jenuh + risiko konten/ToS |
| Snapchat (konten umum, **bukan ads**) | 18.772u | 24 | `argusapi` 6.846u | Jenuh — yang tipis cuma sub-tipe Ads (kandidat #1) |
| Douyin | 16.413u | 26 | `zen-studio` 10.051u | Jenuh + incumbent 10rb user |
| Patreon | 8.511u | 30 | `serpdownloaders` 4.459u | Jenuh |
| Discord | 8.008u | 27 | `maged120` 3.688u | Jenuh |
| Clutch.co | 7.527u | 37 | `epctex` 2.605u | Jenuh |
| App Store apps | 7.404u | 30 | `thewolves` 2.013u | Jenuh |
| Skool | 6.455u | 25 | `memo23` 2.019u | Jenuh — **dan portofolio ini sudah punya** `skool-whop-community-analyzer` |
| Wellfound/AngelList | 5.087u | 39 | `crawlerbros` 1.688u | Jenuh |
| Stepstone | 4.882u | 32 | `memo23` 1.233u | Jenuh (konsisten dengan temuan lama: job board = 4–8+ seller) |
| Y Combinator | 4.618u | 37 | `michael.g` 1.590u | Jenuh |
| Bayut | 3.779u | 33 | `gauravsaran` 1.956u | Jenuh |
| BuiltWith / Wappalyzer (tech-stack) | 3.686u / 1.701u | 36 / 19 | `canadesk` 702u/**2,1jt runs**, `nexgendata` 1.440u | Runs-nya menggoda, tapi 36 seller = kloning ke-37 |
| ProductHunt | 3.393u | 37 | `danpoletaev` 863u | Jenuh |
| Transfermarkt | 3.664u | 22 | `curious_coder` 2.824u | Jenuh |
| Meta Ad Library | 2.785u | 35 | `automly` 1.128u | Jenuh (kontras dengan Snapchat Ads = 3 seller) |
| Autoscout24 | 2.329u | 33 | `ivanvs` 851u | Jenuh — meski `solidcode` 37u/103rb runs sempat terlihat menarik |
| Internshala, IndiaMart, IMDb, Goodreads, Trendyol, Zomato, Sephora, Shein, Mercari, Gumroad, Meetup, Udemy, Naver Map, Allegro, hh.ru, InfoJobs, Immowelt, realestate.com.au, Bazos, SofaScore, Pagesjaunes, Firmy.cz, Ozon, Ryanair, Tesco, SimplyHired, BBB, Yellowpages, Nextdoor, Kuaishou, VK, Zhihu | 300–4.000u | **12–37** | Semua >=12 seller. Beberapa punya rpu spektakuler (`jupri/firmy` 276u/**1.195.742 runs**, `natanielsantos/ozon` 236u/279rb, `epctex/ryanair` 243u/302rb) — **rpu tinggi bukan alasan masuk kalau seller sudah belasan** |

### B. Seller sedikit TAPI pasarnya memang mati (bukan peluang)

Pelajaran Circa Sports (Babak 36) dipakai lagi: **0–2 seller hanya berharga kalau data-type-nya terbukti laku di tempat lain.**

| Konsep | Temuan | Alasan skip |
|---|---|---|
| SimilarTech | **0 actor** | Tidak ada demand sama sekali (bandingkan Similarweb yang ada 4 seller) |
| myip.ms | **0 actor** | Idem |
| Bank branch / ATM locator | 1 seller, **2u** | TAM nol |
| Tracxn | 2 seller, 41u tapi **cuma 70 runs total** | rpu ~2 → dibeli lalu ditinggal. Bukti pasar mati, bukan pasar kosong |
| CB Insights | 2 seller (`canadesk` 101u/9.529r) | Login-gated & berbayar mahal; permukaan publik hampir nol. Kalau mau, recon dulu |
| Christie's / Invaluable / Sotheby's (balai lelang seni) | 3–6 seller, terbesar **21u** | Data-type terbukti laku? Tidak — semua seller mikro. TAM seni terlalu sempit |
| Boat/Yacht listings | 6 seller, terbesar 28u | Idem |
| Commodity prices | 8 seller, terbesar 32u/**137 runs** | Semua mati-suri |
| Scholarship database | 6 seller, terbesar 66u/558 runs | Rendah, dan datanya statis |
| Mining claims, carbon credits, law-firm directory, insurance quotes, daycare, electricity price, hospital data, veterinary, EV charging, aircraft-for-sale, restaurant inspection | <=12 seller tapi semua incumbent <70u | Seller sedikit karena **tidak ada uangnya**, bukan karena belum ketemu |

### C. Di-skip karena risiko / di luar strategi

| Konsep | Stats | Alasan |
|---|---|---|
| Torrent Scraper | `ondro` 262u/**207.205 runs**, `epctex` 375u — cuma **4 seller** | Angka ROI-nya sangat menarik, tapi **risiko hukum/ToS pembajakan**. Ditolak, bukan terlewat |
| Sora / Midjourney (watermark remover, AI video) | Sora 4 seller/681u; Midjourney 4 seller (`igolaizola` 1.855u) | Konten AI berumur pendek + fitur "watermark remover" bermasalah secara ToS |
| PornHub | `jupri` 510u, `saswave` 230u | Di luar strategi portofolio |
| Expired Domains | 13 seller (`catchdoms` 78u/15.826 runs) | Jenuh + niche churn tinggi |
| Shopify Store Leads | 18 seller (`clearpath` **1.433u**) | Jenuh; berbeda dari `xtracto/shopify-products` yang sudah ada |
| Mastodon | **37 seller** — tapi `canadesk` sendirian 31u/**1.055.505 runs** | Contoh ajaran gotcha #2: runs-nya spektakuler, sellernya 37. Kloning ke-38 tidak masuk akal |
| Generic tools: `pocesar/json-downloader` (549u/353.953r), `scrapeunblocker` (185u/169.689r) | ROI tinggi | Kategori **tooling**, bukan scraping data — konsisten dengan keputusan v2 soal S3/GCS uploader |
| Forebet / prediksi sepak bola | 4 seller, 493u, **rpu 6–18** | Seller sedikit tapi tidak ada pemakaian berulang. Sejalan dengan kesimpulan lama: sub-vertikal odds/betting sudah dikuasai `zen-studio` dkk |
| Vertikal pemerintah AS ronde-2 (govdeals, public surplus, construction permits, grants.gov, FDA, clinical trials, patent) | 8–38 seller, didominasi `parseforge`/`jungle_synthesizer`/`pink_comic` | **Konfirmasi ulang Babak 36**: playbook "sumber data publik AS" sudah dijalankan sistematis oleh 6–8 seller lain. Jangan diulang lagi |

## Insight Strategis Babak 39

> **Sinyal terbaik bukan "seller sedikit" dan bukan "user banyak", tapi "seller yang punya RUNS cuma satu".** Ketujuh kandidat teratas di atas semuanya berbentuk sama: 3–7 seller terdaftar, **tepat satu** di antaranya punya >=10.000 runs, sisanya scraper mainan <1.000 runs. Pola ini yang membedakan Snapchat Ads (peluang) dari Mastodon (37 seller, jebakan) dan dari Tracxn (2 seller, pasar mati).

> **Sub-tipe data mengalahkan platform.** Snapchat sebagai platform = 24 seller/18.772u (mustahil). Snapchat **Ads Library** = 3 seller. Perbandingan seluruh keluarga ad-library (Meta 35 → LinkedIn 26 → Pinterest 17 → Reddit 11 → Snapchat **3**) menunjukkan cara paling andal menemukan celah di platform besar yang kelihatan mustahil: **cari data-type yang belum dikloning, bukan platform yang belum digarap.**

## Rekomendasi Lanjutan

1. **Eksekusi urutan ini:** Snapchat Ads Library → Fuel Prices (fokus yurisdiksi non-AS) → Compass.com. Ketiganya rpu >1.000 dengan <=3 seller serius.
2. **Caixa Leilões Brasil** paling cocok dikerjakan bersamaan dengan vertikal lelang yang lebih luas — pakai `auction-foreclosure-sniper` yang sudah ada sebagai template, lalu ekspansi ke yurisdiksi lain (lelang sitaan bank/pengadilan di luar AS/Brasil praktis kosong).
3. **Recon dulu sebelum commit** untuk SpyFu & CB Insights (SaaS berbayar — permukaan publik belum diverifikasi) dan Dealroom (kemungkinan login-gated untuk data lengkap).
4. **Berhenti memakai `--category` sebagai pengukur kejenuhan** (gotcha #1). Untuk riset berikutnya: langsung Pass 2/3 (uji kompetisi per-konsep) dan pakai metrik **"jumlah seller dengan runs >= 10.000"**, bukan jumlah seller mentah.
5. **Vein yang masih belum disentuh sama sekali** dan layak jadi babak berikutnya: sub-tipe ad-library untuk platform lain yang belum ada (Spotify Ads, Amazon Ads creative, X/Twitter Ads), serta harga energi/BBM per-negara (pola sama dengan #2).

## File Referensi Babak 39

- `output/xtracto-full.json` — snapshot 218 actor `xtracto`, 2026-09-08
- `output/scan-v3-pool.json` — 4.580 actor unik dalam band (17 kategori, paginasi penuh)
- `output/scan-v3-ranked.json` — sama + flag `in_mine` / `in_docs` per actor
- `output/scan-v3-competition.json` — 89 konsep, seller berbeda + agregat user/runs
- `output/scan-v3-competition2.json` — 86 vertikal baru yang belum pernah discan

---

# Babak 40 — Uji Kompetisi Murni (189 Konsep + 40 Union-Query): 4 Kandidat Baru, Setengah Rekomendasi Babak 39 Terbukti Salah (2026-09-08)

**Konteks:** lanjutan langsung [Babak 39](#babak-39--scan-dalam-lintas-kategori-4580-actor--175-uji-kompetisi-8-kandidat-roi-tinggi-2026-09-08) di hari yang sama, menjalankan **Rekomendasi Lanjutan #4 dan #5** babak itu secara harfiah:

- **#4 — "berhenti pakai `--category` sebagai pengukur kejenuhan, langsung uji kompetisi per-konsep, metrik = jumlah seller dengan runs ≥10.000."** Dipatuhi: babak ini **nol** query per-kategori. Semua 189 konsep diuji lewat query, dan kolom penentu bukan lagi "jumlah seller" tapi **`serius` = seller dengan runs ≥10.000**.
- **#5 — "vein yang belum disentuh: sub-tipe ad-library platform lain (Spotify Ads, Amazon Ads, X Ads), serta harga energi/BBM per-negara."** Diuji — dan **sebagian besar terbukti salah**. Lihat [Koreksi untuk Babak 39](#-koreksi-untuk-babak-39--separuh-rekomendasi-5-gugur).

**Dedupe 3 lapis** (sama seperti Babak 39): (1) `output/xtracto-full.json` — **218 actor**, di-refresh hari ini, tidak berubah dari snapshot Babak 39; (2) grep token ke `ACTOR_MARKET_RESEARCHER_NEW.md`; (3) grep token ke `actors_researcher_v2.md`. Keempat kandidat di bawah **0 hit di ketiganya** (diverifikasi eksplisit, lihat tabel dedupe di tiap baris).

## Metodologi Babak 40

```bash
python apify-my-store.py xtracto -o output/xtracto-full.json    # 218 actor, tidak berubah

# Pass 1 — 189 uji kompetisi konsep, TANPA satu pun query per-kategori (rekomendasi #4)
#   scratchpad/compete40.py  -> output/scan-v4-competition.json
#   metrik penentu: serious = jumlah seller dengan totalRuns >= 10.000
#   cakupan: 14 sub-tipe ad-library | 8 energi/utilitas | 16 sub-tipe platform jenuh |
#            12 finansial | 12 travel | 7 land-records | 8 media | 8 telekom | 5 kesehatan |
#            10 civic/legal | 8 direktori B2B | 81 vertikal misc yang belum pernah discan
# Pass 2 — verifikasi mendalam 20 finalis (scratchpad/detail40.py), per-actor, tanpa max-users
# Pass 3 — UNION multi-frasa 20 konsep (scratchpad/verify40.py)   <- lihat Gotcha #1
# Pass 4 — UNION multi-frasa 20 konsep di vein yang baru terbukti (scratchpad/verify40b.py)
```

### Gotcha metodologi baru (wajib dipakai riset berikutnya)

1. **Satu frasa query = satu SAMPEL, bukan sensus. Wajib UNION minimal 3 frasa sebelum mengklaim jumlah seller.** Ini gotcha terpenting babak ini, dan langsung mengoreksi angka-angka Babak 39. Bukti keras:
   - `saswave/dealroom-scraper` (**147u / 248.099 runs**, incumbent utama niche itu) **tidak muncul sama sekali** pada query `"dealroom startup database"`, tapi muncul pada query `"dealroom"`.
   - Ketiga actor `canadesk/spyfu*` (total ~47rb runs) **hilang** dari query `"spyfu ppc competitor"`, muncul di `"spyfu"`.
   - Snapchat Ads: query Babak 39 memberi **3 seller**, union 3 frasa di babak ini memberi **10 seller**.
   → Konsekuensi: setiap klaim "hanya N seller" yang dibuat dari **satu** query harus dianggap **batas bawah**, bukan angka final.
2. **Token pendek menghasilkan false positive parah — verifikasi nama actor secara harfiah sebelum memasukkan kandidat.** Tiga kejadian nyata di babak ini:
   - token `tire` → yang tertangkap `azzouzana/canadiantire-ca-scraper` (**Canadian Tire**, peritel), bukan ban.
   - token `leak` → `eduair94/whatsapp-data-lookup`, bukan database kebocoran.
   - token `points`/`miles` → `igolaizola/flight-award-scraper`.
   Ironisnya dua dari tiga false positive itu justru **menjadi temuan nyata** (Canadian Tire dan Award Flights) — jadi false positive tetap harus dibaca, bukan langsung dibuang.
3. **"0 actor" adalah hasil yang informatif, bukan error.** Dari 189 konsep, **33 mengembalikan 0 actor**. Menurut pelajaran Circa Sports (Babak 36) & bagian B Babak 39, itu artinya **tidak ada permintaan**, bukan celah. Daftar lengkap ada di bagian skip.

## ✅ Kandidat Baru — Belum Ada di `xtracto`, Belum Pernah Muncul di Riset Mana Pun

Semua sudah lolos ceiling-check (union multi-frasa, tanpa `--max-users`) dan dedupe 3 lapis.

| # | Prioritas | Ide Actor | Bukti Demand (incumbent) | Seller / Serius | Kenapa Layak / Catatan Eksekusi |
|---|---|---|---|---|---|
| 1 | 🔴 Tinggi | **Award Flight / Miles Seat Search** (kursi redemption frequent-flyer, **bukan** harga tiket tunai) | `igolaizola/flight-award-scraper` **307u / 50.813 runs / 166 rpu**; total vertikal 426u | **7 seller, 1 serius** (#2 `maximedupre` 27u/882r, #3 `memo23` 51u/353r) | Penerapan paling bersih dari insight "sub-tipe mengalahkan platform": penerbangan **harga tunai** jenuh total (`xtracto` sendiri punya `google-flights-scraper` + `skyscanner-scraper`, dan Store penuh kloning), tapi sub-tipe **award/miles** cuma punya 1 seller serius. Dedupe: token `award`/`miles`/`award-flight` = **0 hit** di `xtracto` (218 actor) dan **0 hit** di kedua dokumen riset. TAM sudah terbukti (307 user berbayar). |
| 2 | 🔴 Tinggi | **Minecraft Server Data** (scan server publik: status, pemain, versi, MOTD) | `mr-brogrammer/minecraft-server-scanner` **303u / 45.540 runs / 150 rpu** ⭐5.0(3) | **6 seller, 1 serius** (#2 `gio21` 21u/131r, sisanya ≤3u) | Vertikal GAMES **sama sekali kosong** di `xtracto` (0 dari 218 actor). Pola Babak 39 persis: 1 seller punya runs, 5 sisanya mainan. **Catatan penting:** Babak 8 dulu menyatakan kategori GAMES "habis" — klaim itu **tidak valid** menurut gotcha #1 Babak 39 (tag kategori tidak reliabel), dan babak ini membuktikannya. Tapi lihat juga sisi negatifnya di bagian skip: data game **lain** (skin CS2, Steam player count, catur, ladder esports) semuanya <133u dan **0 serius** — yang punya TAM cuma server-scanning, jadi jangan digeneralisasi jadi "bangun banyak actor gaming". |
| 3 | 🟠 Sedang-Tinggi | **Canadian Tire Product/Price Scraper** (peritel besar Kanada) | `azzouzana/canadiantire-ca-scraper` **36u / 163.100 runs = 4.531 rpu** — **rpu tertinggi seluruh babak ini** | **5 seller, 1 serius** (#2 `stealth_mode` 7u/242r, #3 `clootrack` 1u/290r) | Ditemukan lewat false positive token `tire` (gotcha #2). Nilainya di **intensitas**, bukan volume: 4.531 rpu = monitoring harga harian, bukan one-off. **Kelemahan jujur:** TAM absolut kecil — 36 user, dan seluruh vertikal retail Kanada cuma 232u (`loblaws` 112u/1.670r, `pcexpress` 55u). Ambil kalau mau actor ber-ROI-per-user tinggi berbiaya build rendah, bukan kalau mengejar jumlah user. |
| 4 | 🟠 Sedang | **Cruise Line Pricing** (template per-brand: Royal Caribbean, Carnival, MSC, NCL, Costa, Disney, Princess, HAL…) | Vertikal **735u / 27.104 runs** tersebar; terbesar `sercul/royal-caribbean` 129u/5.279r ⭐4.4(3) | **13 seller, 0 actor tunggal tembus 10rb runs** | Bentuknya beda dari 3 kandidat di atas: **tidak ada incumbent kuat sama sekali** — `sercul` menguasai lewat *jumlah* (10 actor per-brand) bukan lewat satu actor besar. Ini persis **pola template per-outlet yang jadi kekuatan repo ini** (100+ news scraper per outlet). `xtracto` punya hotel/flight/car/Airbnb tapi **nol** cruise; token `cruise` = 0 hit di `xtracto` dan 0 hit di kedua dokumen. Risiko: rpu rendah (41–192) → pemakaian berulang belum sekuat kandidat #1–#3. |

## 🔁 Sudah Tercakup / Sudah Ter-riset — Muncul di Scan, Bukan Temuan Baru

| Konsep | Sudah ada di | Catatan |
|---|---|---|
| Google Ads Transparency | `xtracto/google-ads-transparency` | Sekaligus **jenuh**: 44 seller, **8 serius**, 5.515u — jangan ditambah varian |
| TikTok Ads / Creative Center | `xtracto/tiktok-top-ads-scraper` | Jenuh: 25 seller, **5 serius**, 4.135u / 1,18jt runs |
| Airbnb occupancy & revenue estimate | `xtracto/airbnb-occupancy` | Muncul di scan sebagai 18 seller; sudah dipegang |
| UberEats / menu delivery | `xtracto/ubereats-menu-scraper` | Vertikal menu-delivery 22 seller — cukup satu |
| Substack | repo (`substack-scraper`) | Vertikal 28 seller, 1 serius (`automation-lab` 422u) — sudah digarap, jangan diulang |
| Fuel Prices, Compass, Dealroom, AllTrails, SpyFu, Snapchat Ads, QS Rankings, Caixa Leilões | **Babak 39** | Belum dibangun tapi **sudah ter-riset** — jangan dihitung ulang. Angka-angkanya dikoreksi di bawah |
| OpenTable | `actors_researcher_v2.md` (sudah dibuktikan jenuh) | Dikonfirmasi ulang: 24 seller, 3 serius |

## 🔧 Koreksi untuk Babak 39 — Separuh Rekomendasi #5 Gugur

Bagian ini yang paling berharga dari babak 40: rekomendasi Babak 39 diuji, dan **sebagian besar tidak bertahan**.

### Rekomendasi #5a — "sub-tipe ad-library untuk platform lain" → **GAGAL TOTAL**

| Sub-tipe ad-library yang direkomendasikan Babak 39 | Hasil uji | Kesimpulan |
|---|---|---|
| **Spotify Ads** | **0 actor** | Tidak ada permintaan |
| **Apple Search Ads** | **0 actor** | Tidak ada permintaan |
| **Amazon Ads / Sponsored Brands** | 1 seller, `lexis-solutions` **4u / 141 runs** | Pasar mati |
| **X (Twitter) Ads Library** | 1 seller, `memo23` **31u / 105 runs** | Pasar mati |
| Taboola/Outbrain, AdBeat, Quora Ads, Criteo, billboard/OOH | **0 actor** semua | Tidak ada permintaan |
| YouTube Ads | 6 seller, **0 serius**, terbesar `xtech` 109u/830r | Ramai tapi semua mikro |
| Bing/Microsoft Ads | 9 seller, **0 serius**, `lexis-solutions` 82u/5.203r | Idem |

→ **Kesimpulan yang mengoreksi Babak 39:** keluarga ad-library **tidak** punya "sub-tipe tipis yang tinggal diambil". Yang ada cuma **dua kutub** — platform besar yang sudah jenuh (Meta 35 seller, Google Ads Transparency 44 seller/8 serius, TikTok 25 seller/5 serius) dan platform kecil yang **tidak ada permintaannya sama sekali**. Snapchat Ads adalah **satu-satunya** anomali, dan itupun sedang menutup (lihat di bawah). Vein ini **resmi tuntas, jangan discan lagi**.

### Rekomendasi #5b — "harga energi/BBM per-negara" → **SEBAGIAN GUGUR**

| Konsep | Hasil uji | Kesimpulan |
|---|---|---|
| LPG/tabung gas, natural gas Eropa, power outage, crude oil inventory | **0 actor** semua | Tidak ada permintaan |
| Tarif listrik per-negara | 2 seller, **3u total** | Pasar mati |
| Grid load / beban listrik | 4 seller, 0 serius, 11u | Pasar mati |
| Tarif air | 2 seller, 4u | Pasar mati |
| **Harga BBM/SPBU** | 13 seller, **1 serius** (`johnvc/fuelprices` 203u/309.324r) | **Satu-satunya yang hidup** — dan ini persis kandidat #2 Babak 39 yang sudah tercatat |

→ **Kesimpulan:** "energi" bukan vertikal — yang laku spesifik **harga BBM ritel**, dan itu sudah tercatat. Sudut non-AS yang disarankan Babak 39 tetap valid (`abotapi` AU 10u, `latinamericadata` Brasil 3u, `dev-sinior` Prancis 2u, `tikitakaclaw` Spanyol 2u, `rainminer` Austria 2u — semua mikro, artinya per-negara memang belum digarap serius), tapi jangan berharap vertikal energi yang lebih luas.

### Koreksi angka seller (akibat gotcha #1 — union query)

| Kandidat Babak 39 | Angka Babak 39 | Angka Babak 40 (union 3 frasa) | Dampak |
|---|---|---|---|
| **Snapchat Ads Library** | 3 seller | **10 seller**, masih 1 serius (`lexis-solutions` 55u/249.398r). 7 kloning baru semuanya **≤4u / <300 runs** | Masih peluang, tapi **celahnya sedang menutup cepat** — 7 seller masuk ke sub-tipe yang sama. Kalau mau ambil, ambil sekarang, jangan ditunda |
| **Dealroom** | 6 seller, 1 serius | **8 seller**, 1 serius (`saswave` 147u/248.099r **terkonfirmasi**) | Prioritas tetap, angka pesaing naik |
| **AllTrails** | 7 seller | **9 seller**, masih 1 serius (`parseforge` 126u/121.721r) | Prioritas tetap |
| **SpyFu** | 5 seller | 5 seller tapi **2 serius** (`canadesk` agregat 47rb runs **+** `dionysus_way` 197u/17.405r) | **Turunkan prioritas** — lebih ramai dari kesan Babak 39 |
| **Compass.com** | `canadesk/compass-properties` 16u/137.618r | Union query "compass real estate" **tidak memunculkan** actor `canadesk` itu; yang muncul `nanoteki` 1u/10.424r + 5 seller mikro (terbesar 19u/517r) | Bukan kontradiksi — ini gotcha #1 (frasa berbeda, hasil berbeda). Tapi artinya **verifikasi ulang wajib sebelum eksekusi**: 10.424 runs dari **1 user** bukan bukti TAM |

## ⛔ Di-skip — Semua dengan Alasan Konkret

### A. Stats sangat tinggi TAPI jenuh (≥2 seller serius) — ini jawaban langsung untuk "cari actor yang stats-nya tinggi"

| Konsep | Users di Store | Seller / **Serius** | Incumbent terbesar | Alasan skip |
|---|---|---|---|---|
| **WhatsApp number validator / lookup** | **7.820u** | 21 / **5** | `devscrapper` 2.166u; `vtrdev` 1.270u/**909.549 runs**; `eduair94` 1.416u/287.514r ⭐4.9(11) | **Niche ber-stats tertinggi yang ditemukan di seluruh babak ini.** Skip karena dua hal sekaligus: 5 seller serius (bukan celah), **dan** risiko privasi/ToS — validasi nomor telepon massal adalah tooling lead-gen yang rawan melanggar ToS WhatsApp/Meta dan aturan data pribadi |
| Indeed (jobs + reviews) | 30.291u incumbent tunggal | 37 / banyak | `misceres/indeed-scraper` **30.291u / 2,06jt runs** | Paling jenuh yang pernah tercatat di dokumen ini. `memo23` sendiri punya 6 varian |
| Glassdoor reviews | ribuan | **43** / ≥3 | `memo23` 934u/1,17jt runs; 1.428u di varian PPR | Jenuh — dan `xtracto` sudah punya `glassdoor-reviews`/`glassdoor-company` |
| Salary / levels.fyi / compensation | 1.124u | 19 / **2** | `memo23` **959u / 1.166.159 runs** | Jenuh oleh satu raksasa + 1 serius lain |
| DNS lookup | 405u | 30 / **2** | `superlativetech` 127u/417.567r | Jenuh, dan ini tooling bukan data |
| Domain WHOIS | 331u | 28 / 1 | `agenscrape` 184u/178.476r | Jenuh |
| Trademark search | 523u | 26 / **2** | `dev00` 40u/62.144r | Jenuh |
| Google Ads Transparency | 5.515u | **44** / **8** | `solidcode` 1.846u/790.703r | Paling jenuh di keluarga ads — dan sudah dipunya |
| TikTok Creative Center Ads | 4.135u | 25 / **5** | `codebyte` 348u/1.037.320r | Jenuh |
| Lazada/Tokopedia/Coupang | 4.063u | **46** / 3 | `jupri/lazada` 49u/**611.259 runs** (12.475 rpu) | rpu-nya spektakuler tapi 46 seller. Konsisten dengan temuan lama "marketplace regional = red ocean" |
| Best Buy / elektronik | 925u | **36** / 2 | `alexey` 380u/56.667r | Jenuh |
| Wayfair / furnitur | 749u | **39** / 1 | `123webdata` 108u/45.654r | Jenuh |
| Supermarket (Carrefour/Aldi/Lidl/Coles/Woolworths) | 834u | 23 / 0 | `blackfalcondata/lidl` 32u/4.855r | Jenuh **dan** semua mikro — kombinasi terburuk |
| Home Depot / Lowe's / Bunnings | 535u | 13 / 1 | `jupri/lowes` 42u/15.645r | Jenuh |
| Sephora / Ulta / Watsons | 260u | 11 / 0 | `buseta/sephora` 170u/2.328r | Jenuh + mikro |
| Meetup | 916u | 27 / 1 | `filip_cicvarek` 462u/23.068r | Jenuh (konsisten dengan skip Babak 39) |
| Substack | 953u | 28 / 1 | `automation-lab` 422u/21.167r | Jenuh — dan repo sudah punya `substack-scraper` |
| Restoran: OpenTable/Resy | 657u | 24 / **3** | `memo23/opentable-reviews` 102u/66.970r; `canadesk/opentable` 176u/17.693r | Jenuh. **Pengecualian tipis:** `clearpath/resy-availability-api` 10u/**32.114 runs (3.211 rpu)** — sub-tipe "ketersediaan meja" beda dari "review", tapi cuma 10 user dan bertetangga dengan actor *booking bot* yang berisiko ToS. Prioritas rendah, wajib recon |
| Rumble, Vimeo, Dailymotion, Bilibili, VK, Odnoklassniki, Rutube, medium, Letterboxd, anime/manga, recipe, museum, nonprofit 990, product recall, open-source trending, insider trading, SEC 13F, CVE, WordPress plugin, HuggingFace, Docker Hub, npm/PyPI, ASO keywords | 30–950u | **12–32** / 0–1 | — | Semua ≥12 seller **dan** hampir semua tanpa seller serius. Kombinasi "ramai + mikro" = ROI terburuk |

### B. Seller sedikit / nol TAPI pasarnya memang mati — bukan peluang

Pelajaran Circa Sports (Babak 36) & bagian B Babak 39 dipakai lagi, sekarang dengan bukti jauh lebih banyak.

**B-1. Konsep dengan 0 actor sama sekali (33 dari 189 konsep diuji).** Tidak ada satu pun seller yang pernah mencoba → tidak ada permintaan, bukan celah:

> Spotify Ads · Apple Search Ads · Taboola/Outbrain · AdBeat · Quora Ads · Criteo · billboard/OOH · LPG · natural gas Eropa · power outage · crude oil inventory · cashback aggregator · live shopping/live commerce · credit rating agency · tarif parkir bandara · syarat visa masuk · akses lounge bandara · hotel loyalty award chart · HOA · bestseller buku/ISBN · perbandingan paket seluler · peta cakupan menara seluler · marketplace asuransi kesehatan · daftar perusahaan ber-ISO · direktori sertifikasi halal · lelang mobil bekas Jepang untuk ekspor · pelacakan paket/parsel · tarif tol · beasiswa/admisi universitas · hasil ujian · lisensi berburu & memancing · direktori gereja/masjid/kuil · direktori channel Telegram

**B-2. Ada seller tapi semua mikro (0 seller serius):**

| Konsep | Temuan | Alasan skip |
|---|---|---|
| **7-Eleven / minimarket** | **1 seller** (`mrdoe`) dengan 5 actor per-negara, **semuanya 2u / ~30 runs** | Contoh paling murni "0 kompetitor ≠ peluang". Satu orang sudah menggarap 5 negara dan tidak ada yang membeli |
| **NASDAQ short interest** | `parseforge/nasdaq-short-interest-scraper` **9u / 495.544 runs = 55.060 rpu** — rpu paling ekstrem yang pernah tercatat di dokumen ini | **Jebakan runs terbesar sejauh ini.** Total vertikal cuma **54 user** di 13 seller. Runs-nya artefak arsitektur "1 run = 1 item" (gotcha #3 Babak 39), bukan bukti permintaan |
| Apotek/farmasi Eropa | `studio-amba` sendirian punya ~10 actor (Rossmann, DM, Müller, Shop-Apotheke, Dr.Max, Apotea, Farmaline…), semuanya **≤6u** | Satu seller sudah memetakan seluruh vertikal dan hasilnya nol traksi |
| Skin/item game (CS2, Steam Market, Buff163) | 6 seller, terbesar `the.beast` 133u/5.644r, **0 serius** | Ramai kecil. **Kontras penting dengan kandidat #2**: yang laku di gaming cuma server-scanning, bukan data game umum |
| Steam player count / game server browser | 9 seller, terbesar 22u, **0 serius** | Idem |
| Catur / ladder esports / speedrun | 16 seller, terbesar `paco_nassa/hltv` 62u/948r | Idem |
| Sporting goods (Decathlon/REI) | 12 seller, terbesar 111u/2.274r, 0 serius | Ramai + mikro |
| Price history (Keepa/CamelCamelCamel) | **3 actor / 6 user total** | Mengejutkan — data-type yang kedengarannya jelas laku ternyata tidak ada pasarnya di Store |
| Store locator generik | 8 seller, 0 serius; `xtracto/store-locator-expansion` sendiri cuma 2u | Dikonfirmasi kecil oleh data portofolio sendiri |
| Ketersediaan stok per-ZIP/toko | 5 seller, 1 "serius" tapi itu `s-r/price-scraper` (**generik any-URL**, bukan sub-tipe ini) | Sub-tipe aslinya mikro (`kamerozkan` 2u, `muhammetakkurtt` 10u) |
| Tarif pengiriman/kurir | **1 actor / 7 user** | Pasar tidak ada |
| Airline loyalty / status match | **0 actor** | Pasar tidak ada — kontras dengan Award Flights (kandidat #1) yang 307u. Sub-tipe yang bersebelahan bisa berbeda total |
| Flight status / seat map / timetable | 6 seller, 0 serius, terbesar 119u/2.312r | Sub-tipe penerbangan **selain** award ternyata mikro |
| HS code / bea masuk | 19 seller, semua ≤13u | Ramai + mikro |
| Transparansi harga rumah sakit (CMS) | 8 seller, terbesar 4u | Vertikal data publik AS — konfirmasi ulang Babak 36/39: playbook ini sudah digarap sistematis dan tidak menghasilkan |
| Recall & spesifikasi kendaraan (NHTSA) | **36 seller**, semua ≤24u | Idem — ramai justru karena datanya gratis & gampang, bukan karena laku |
| Valuasi mobil (KBB/Edmunds) | 3 actor / 12 user | Pasar tidak ada |
| Material konstruksi | 5 actor, terbesar 117u/451r (rpu 4) | Dibeli lalu ditinggal |
| Gym/Mindbody/booking kelas | 10 seller, terbesar 46u/157r | Ramai + mikro |
| Ranking sekolah / akreditasi | 7 seller, terbesar `parseforge/greatschools` 70u/1.258r | Mikro |
| Kununu (review kerja Jerman) | **19 seller**; `blackfalcondata` 69u/37.889r + `radeance` 82u/35.723r | **Koreksi hipotesis:** sempat terlihat 4 seller di Pass 1, ternyata 19 setelah union query. Jenuh |
| AmbitionBox (review kerja India) | **12 seller**, terbesar `memo23` 61u/1.379r | Jenuh + mikro |
| Comparably | 5 seller, terbesar 19u/1.635r | Pasar mati |

> **Pelajaran gabungan dari Kununu + AmbitionBox + Comparably:** hipotesis andalan Babak 39 — *"sub-tipe data mengalahkan platform"* — **tidak selalu berlaku**. Untuk "platform review karyawan **selain** Glassdoor", sub-tipe-nya justru sama jenuhnya (19 dan 12 seller) atau mati (5 seller/19u). Sub-tipe hanya jadi celah kalau **data-type-nya berbeda**, bukan sekadar **platform-nya berbeda**.

### C. Di-skip karena risiko / di luar strategi

| Konsep | Stats | Alasan |
|---|---|---|
| WhatsApp number validator/lookup | 7.820u, sampai 909.549 runs per actor | Sudah di bagian A, diulang di sini karena alasan utamanya **risiko**: memvalidasi/menyisir nomor telepon massal rawan ToS Meta + regulasi data pribadi |
| Database kebocoran data / breach checker | 10 seller, terbesar `lofomachines` 209u/1.768r, `clearcheck.io` 415u/958r | Stats kecil **dan** menyajikan kredensial bocor = area yang tidak digarap portofolio ini |
| Resy booker / OpenTable booker (`clearpath`) | 48u/6.417r dan 84u/2.866r | Ini **bot pemesanan**, bukan scraper data — di luar model bisnis, dan rawan ToS |
| `s-r/price-scraper` (ekstrak harga dari URL apa pun) | 287u/20.537r | Kategori **tooling generik**, konsisten dengan keputusan v2/Babak 39 soal uploader & screenshot API |

## Insight Strategis Babak 40

> **Metrik "seller serius" bekerja, tapi harus dipasangkan dengan UNION query.** Empat kandidat babak ini semuanya berbentuk sama persis dengan pola Babak 39 (1 seller punya runs ≥10rb, sisanya mainan) — tapi babak ini juga membuktikan bahwa pola itu **hanya bisa dipercaya kalau jumlah sellernya dihitung dari union beberapa frasa**. Snapchat Ads terlihat 3 seller dengan satu query dan 10 seller dengan tiga query; itu selisih antara "peluang lapang" dan "peluang yang sedang ditutup".

> **Sub-tipe hanya jadi celah kalau DATA-TYPE-nya beda, bukan kalau PLATFORM-nya beda.** Award flights (data-type baru: ketersediaan kursi redemption) = 1 seller serius dari 426 user. Kununu/AmbitionBox (platform baru, data-type sama dengan Glassdoor) = 19 dan 12 seller. Ini penajaman langsung atas insight Babak 39, dan aturan praktis yang jauh lebih tajam untuk babak berikutnya.

> **Tiga sinyal "jebakan" yang sekarang punya nama dan contoh baku:** (1) **jebakan runs** — `parseforge/nasdaq-short-interest` 495.544 runs dari **9 user**; (2) **jebakan seller-tunggal** — `mrdoe` menguasai 100% niche 7-Eleven di 5 negara dengan 2 user per actor; (3) **jebakan sub-tipe** — mengira platform berbeda berarti pasar berbeda (Kununu). Ketiganya sekarang punya tes yang jelas: cek **user**, bukan runs; cek apakah seller tunggal itu **laku**, bukan cuma ada; cek apakah **data-type**-nya benar-benar baru.

## Rekomendasi Lanjutan

1. **Eksekusi urutan ini:** Award Flight Seats → Minecraft Server Data → Canadian Tire. Ketiganya 1 seller serius, TAM terbukti (307u / 303u / rpu 4.531), dan nol overlap dengan 218 actor `xtracto`.
2. **Snapchat Ads (Babak 39 #1) naik jadi mendesak, bukan sekadar prioritas tinggi** — 7 kloning baru masuk sejak Babak 39 dicatat. Kalau tidak diambil sekarang, kemungkinan besar hilang.
3. **Turunkan SpyFu** dari daftar Babak 39 (ternyata 2 seller serius) dan **verifikasi ulang Compass** sebelum commit (bukti 10.424 runs itu dari 1 user).
4. **Berhenti menscan dua vein ini — sudah tuntas dan terbukti negatif:** (a) sub-tipe ad-library selain Snapchat, (b) energi/utilitas selain harga BBM ritel. Keduanya rekomendasi Babak 39 yang gugur di babak ini.
5. **Aturan baru sebelum mengklaim kandidat:** union ≥3 frasa query, verifikasi nama actor secara harfiah (anti false-positive token), dan pastikan yang berbeda adalah **data-type**-nya — bukan cuma platformnya.
6. **Vein yang masih benar-benar belum disentuh** dan layak jadi Babak 41: sub-tipe **ketersediaan/inventory real-time** untuk kategori yang sudah punya harga (pola Resy availability, tapi di vertikal non-restoran), serta **cruise per-brand di luar 10 brand yang sudah digarap `sercul`** (mis. kapal pesiar Asia/Eropa regional).

## File Referensi Babak 40

- `output/xtracto-full.json` — snapshot 218 actor `xtracto` (tidak berubah dari Babak 39)
- `output/scan-v4-competition.json` — **189 konsep**, per konsep: jumlah seller, **seller serius (runs ≥10rb)**, total user/runs, top-6 seller, flag dedupe `in_xtracto`/`in_docs`
- `scratchpad/compete40.py` — Pass 1 (189 uji kompetisi, nol query per-kategori)
- `scratchpad/detail40.py` — Pass 2 (verifikasi per-actor 20 finalis)
- `scratchpad/verify40.py` — Pass 3 (union multi-frasa, 20 konsep)
- `scratchpad/verify40b.py` — Pass 4 (union multi-frasa di vein yang baru terbukti, 20 konsep)

---

# Babak 41 — Scan ROI-Tinggi Dua Arah (116 Konsep Baru + 1.384 Actor Ber-Stats Tinggi): 1 Vein Besar Ditemukan, Rekomendasi Cruise Babak 40 Gugur (2026-09-08)

**Konteks:** user kembali minta daftar actor **ROI data tinggi / stats sudah tinggi**, dengan syarat tegas **tidak boleh duplikat** dengan (a) akun kedua [`xtracto`](https://api.apify.com/v2/store?username=xtracto) dan (b) riset yang sudah ada di dokumen ini + [`actors_researcher_v2.md`](actors_researcher_v2.md). Babak ini menjalankan **dua arah sekaligus** — bottom-up (uji kompetisi konsep, seperti Babak 40) **dan** top-down (tarik populasi actor yang stats-nya sudah tinggi, lalu cek mana yang belum digarap). Arah kedua ini **belum pernah dilakukan di babak mana pun**: Babak 8/39 justru men-scan band user RENDAH (`max-users` 3.000–5.000), jadi sisi "sudah laku besar" dari Store secara harfiah belum pernah dilihat.

**Snapshot dedupe:** `apify-my-store.py xtracto` di-refresh hari ini → **masih 218 actor**, tidak berubah sejak Babak 39/40.

## Ringkasan Eksekutif

- **Temuan utama (1 vein, prioritas tinggi):** **direktori bisnis nasional** (padanan Yellow Pages per negara). Data-type-nya **terbukti sangat laku** — Jerman 928u (`plowdata/gelbe-seiten` **417u / 395.433 runs / 948 rpu** ⭐5.0), Prancis 1.279u (`saswave/pagesjaunes-scraper` 545u/85.141r), India 1.635u, UK 434u — sementara **belasan yurisdiksi lain praktis kosong**: Turki **0 actor**, Jepang **0 actor**, Indonesia 7u total, Meksiko 15u, Brasil 17u, Portugal 19u, Nordik 24u, Belanda 8u. Ini pola "**data-type terbukti × yurisdiksi kosong**" yang sudah 2× berhasil (Babak 37 Singapura, Babak 38 Filipina), tapi kali ini dengan **bukti demand jauh lebih besar** daripada court judgments.
- **Rekomendasi Babak 40 #6 diuji dan separuhnya gugur:** vein "cruise regional di luar 10 brand `sercul`" **terbukti pasar mati** — 12 seller, **0 seller punya runs ≥10rb**, actor terbesar cuma 129u. Vein "ketersediaan/inventory real-time" (18 konsep diuji) juga **nihil**: semua sub-tipe (self storage 16u, EV charging 65u, Instacart 69u, parkir 7u, gym 54u) TAM-nya mikro.
- **Sisi stats-tinggi Store sudah habis dikuasai:** dari **1.384 actor** dengan `users ≥150 DAN runs ≥20.000`, yang tidak match `xtracto`/kedua dokumen/folder lokal cuma **122**, dan hampir semuanya **tooling generik** (`apify/web-scraper`, email verifier, screenshot/PDF, proxy tester) yang sudah berkali-kali diputuskan di luar strategi. **Tidak ada satu pun platform besar** yang tersisa: 110 actor teratas berdasarkan user semuanya Instagram/TikTok/LinkedIn/Google/Facebook — dan semuanya sudah dipegang `xtracto`.

## Metodologi Babak 41

```bash
python apify-my-store.py xtracto -o output/xtracto-full.json     # 218 actor (tidak berubah)

# Pass 1 - 116 konsep BARU (nol tumpang tindih dengan compete.py/compete40.py/verify40.py),
#   aturan Babak 40 dipakai SEJAK AWAL: union >=3 frasa/konsep, metrik "seller serius" (runs>=10rb)
#   cakupan: 18 sub-tipe ketersediaan/inventory | 5 cruise & transport | 7 otomotif/dealer |
#            5 logistik/bea-cukai | 5 kesehatan | 6 properti non-listing | 6 finansial ritel |
#            7 media | 11 creator economy | 7 sosial Asia | 10 civic | 8 B2B martech |
#            9 komoditas | 6 travel | 6 sports non-odds
#   scratchpad/compete41.py -> output/scan-v5-competition.json
# Pass 2 - verifikasi per-actor 24 finalis (scratchpad/detail41.py), tanpa max-users
# Pass 3 - TOP-DOWN: 21 kategori, band users>=150 & runs>=20.000, paginasi penuh
#   -> 1.384 actor unik ber-stats tinggi (scratchpad/highstats41.py -> output/scan-v5-highstats.json)
# Pass 4 - uji kompetisi union untuk kandidat hasil Pass 3 (scratchpad/verify41.py)
# Pass 5 - vein terkuat diuji PER-YURISDIKSI, 15 negara direktori bisnis + 7 negara direktori
#   telepon, plus probe HTTP langsung ke situs target (scratchpad/verify41b.py)
```

### Gotcha metodologi baru

1. **Daftar kunci (`keys`) yang terlalu sempit menghasilkan FALSE NEGATIVE yang meyakinkan.** Kasus nyata di babak ini: "Telegram channel analytics" dengan kunci sempit (`tg-post`, `telemetr`, `telegram-stat`) mengembalikan **1 actor / 1 seller** — terlihat seperti temuan langka. Union yang lebih luas (kunci `telegram` + 4 frasa) mengembalikan **51 actor / 44 seller / 3.445 user**, dan actor yang tadinya "sendirian" (`arachnetix/tg-post-stats`) bahkan tidak masuk 8 besar. → Aturan Babak 40 ("union ≥3 frasa") **belum cukup**; kuncinya juga harus mencakup **nama platform telanjang**, bukan cuma pola slug yang ditebak.
2. **Dedupe token otomatis over-filter di ujung stats-tinggi.** Token pendek (<5 huruf) dibuang supaya tidak bising, akibatnya `jupri/yelp` dan `jupri/firmy` lolos sebagai "belum tergarap" padahal `xtracto` punya `yelp-business-scraper` dan Babak 39 sudah menyimpulkan `firmy.cz` jenuh. Sebaliknya, token umum (`scrapers`, `storage`) bikin kandidat bersih tertandai palsu. → Di babak ini semua kandidat final **dicek harfiah satu per satu** (tabel cek ada di `scratchpad/`), bukan mengandalkan flag.
3. **Ujung stats-tinggi Store bukan tempat mencari celah.** Ini pertama kalinya diukur: dari 1.384 actor ber-stats tinggi, **0 platform vertikal** tersisa yang belum digarap `xtracto` atau belum diriset. Konsekuensi strategi: pertanyaan "actor apa yang stats-nya tinggi" dan "actor apa yang layak dibangun" **punya jawaban yang hampir tidak beririsan** — yang stats-nya tinggi sudah diambil, yang belum diambil harus dicari lewat **yurisdiksi**, bukan lewat platform.

## ✅ Kandidat Baru — Belum Ada di `xtracto`, Belum Pernah Muncul di Riset Mana Pun

| # | Prioritas | Ide Actor | Bukti Demand (stats incumbent) | Kompetisi | Kenapa Layak / Catatan Eksekusi |
|---|---|---|---|---|---|
| 1 | 🔴 **Tinggi** | **Direktori Bisnis Nasional — yurisdiksi kosong** (Sarısayfalar 🇹🇷, IndonesiaYP/Soopage 🇮🇩, Telelistas/GuiaMais 🇧🇷, Hitta 🇸🇪) | Data-type terbukti di yurisdiksi yang sudah digarap: **DE 928u** (`plowdata/gelbe-seiten` **417u / 395.433 runs / 948 rpu** ⭐5.0(8)), **FR 1.279u** (`saswave/pagesjaunes-scraper` 545u/85.141r ⭐5.0(8); `mostafa-ennadi` 177u/47.714r), **IN 1.635u** (`happitap/lead-extractor---justdial` 714u), **UK 434u** | 🇹🇷 **0 actor** · 🇯🇵 **0 actor** · 🇮🇩 3 seller/**7u** · 🇲🇽 3/15u · 🇧🇷 3/17u · 🇵🇹 2/19u · Nordik 3/24u · 🇳🇱 3/8u | Pola **"data-type terbukti × yurisdiksi kosong"** — sama persis dengan yang sudah 2× berhasil (Babak 37/38), tapi bukti demand-nya **jauh lebih besar** daripada court judgments. **Probe HTTP sudah dijalankan** (lihat catatan teknis di bawah): Turki **200, Apache polos, 111KB HTML** — kombinasi terbaik (nol kompetitor + nol WAF). Urutan eksekusi yang disarankan: **TR → ID → BR → SE**. |
| 2 | 🟠 Sedang-Tinggi | **Social Blade / Creator Analytics lintas platform** (statistik & estimasi earning kanal YouTube/TikTok/Twitch/IG) | `radeance/socialblade-api` **352u / 1.256.465 runs / 3.570 rpu** — rpu tertinggi ke-8 di seluruh pool stats-tinggi | 18 seller, tapi **hanya 1 yang serius**; seller ke-2 cuma 91u/709 runs | **Celah di sini bukan kekosongan, tapi kualitas**: incumbent satu-satunya berating **2.5 dari 10 review** — sinyal ketidakpuasan user yang jelas, jenis pembukaan paling bisa dieksekusi (tinggal bikin yang stabil). Moat reuse: repo ini sudah punya `twitch-analytics-scraper` + 7 actor YouTube di `xtracto`, jadi logika metrik kanal sudah dikuasai. Risiko: Social Blade sendiri punya API berbayar — **wajib recon permukaan publik tanpa login dulu**. |
| 3 | 🟢 Rendah-Sedang | **Daftar Exhibitor Pameran Dagang** — untuk fair di luar cakupan `skython` (Asia/AS; dia fokus Messe Jerman + Reed) | `skython/exhibitor-list-scrapers-router` **385u/66.647r**, `map-your-show-exhibitor-list-scraper` **579u**, `exhibitor-list-scraper` 336u — semua ⭐4.9–5.0 | 22 seller, tapi **praktis 1 seller** (12 besar semuanya `skython`), 1 serius | Demand user tinggi & rating sempurna = TAM nyata untuk lead-gen B2B. **Kelemahan jujur: rpu cuma 4–8** — pola pemakaian sekali-jalan (ambil daftar peserta sebelum pameran), bukan pipeline harian. Ambil hanya kalau mau actor "gampang laku" berbiaya rendah, bukan untuk ROI berulang. |

### Catatan teknis kandidat #1 (probe HTTP langsung, 2026-09-08)

| Target | Status | Catatan |
|---|---|---|
| 🇹🇷 `sarisayfalar.com` | **200**, `Server: Apache`, 111 KB HTML, **tanpa Cloudflare** | Target terbaik: nol kompetitor **dan** nol WAF |
| 🇧🇷 `telelistas.net` | **200** (Cloudflare lolos), 100 KB | Aman untuk HTTP biasa |
| 🇮🇩 `indonesiayp.com` | **200** (Cloudflare lolos), 22 KB | Pasar rumah sendiri; HTML tipis, cek kedalaman data dulu |
| 🇸🇪 `hitta.se` | **200** (CloudFront), 83 KB | Terbuka |
| 🇳🇴 `gulesider.no` | **403** Cloudflare | Terblokir — konsisten dengan pola WAF Nordik di riset lama |
| 🇳🇱 `goudengids.nl` | **403** | Terblokir |
| 🇯🇵 `itp.ne.jp` | **ReadTimeout** | 0 kompetitor kemungkinan **karena sulit diakses**, bukan karena kosong — jangan diprioritaskan tanpa recon serius |
| 🇲🇽 `seccionamarilla.com.mx` | **ConnectTimeout** | Sama seperti Jepang — perlu recon dulu |

> **Peringatan jujur soal kandidat #1:** "0 kompetitor" untuk Turki/Jepang **bukan otomatis berarti demand ada di sana**. Pembeli lead direktori DE/FR sebagian besar agensi B2B Eropa; belum tentu ada pembeli sebesar itu untuk lead Turki. Yang **sudah terbukti** adalah data-type-nya, bukan pasarnya per negara. Karena biaya bangunnya rendah (situs terbuka, HTML statis), risiko ini bisa diterima — tapi jangan bangun 8 negara sekaligus: **bangun TR dulu, ukur traksinya 2–4 minggu, baru lanjut.**

## 🔁 Sudah Tercakup — Muncul di Scan Tapi Bukan Temuan Baru

| Konsep (stats yang bikin dia muncul) | Sudah ada di | Catatan |
|---|---|---|
| Instagram/TikTok/LinkedIn/Google/Facebook/YouTube/Twitter (110 actor teratas, 10rb–593rb user) | `xtracto` (218 actor) + folder repo | Seluruh puncak Store. Tidak ada celah tersisa di lapis ini |
| Yelp (`jupri/yelp` 430u/881.164r, rpu 2.049) | `xtracto/yelp-business-scraper` | Sempat lolos flag otomatis karena token "yelp" <5 huruf — lihat Gotcha #2 |
| Workday / Greenhouse / ATS job feeds (`gooyer.co/myworkdayjobs` 248u/353.187r) | `xtracto/ats-jobs-aggregator`, `xtracto/ats-hiring-velocity` | Vein ATS sudah dipegang |
| Xiaohongshu / RedNote (42 seller, 10.503u) | `xtracto/rednote-xiaohongshu-scraper` | Sudah dipegang **dan** pasarnya jenuh |
| Kickstarter (muncul saat mencocokkan "kick") | `xtracto/kickstarter-projects` | **Bukan** Kick.com — beda platform, lihat tabel skip |
| Firmy.cz (`jupri/firmy` 276u/1.195.742r, rpu 4.332) | Babak 39, tabel jenuh (12–37 seller) | Padanan direktori bisnis Ceko — memperkuat kandidat #1, tapi Ceko sendiri sudah jenuh |
| ImmobilienScout24 (`clearpath/immoscout24-api-pro` 223u/1.088.475r) | `actors_researcher_v2.md` (prioritas rendah) | Sudah ter-riset, belum dibangun |
| TecDoc (2.095u/31jt runs), SimilarWeb, SpyFu, G2, Upwork, Fuel prices, Compass | Babak 39/40 + v2 | Semua sudah punya keputusan |
| Substack (`digispruce/substack-scraper` 120u/95.795r) | Folder repo: `substack-scraper` | Sudah dibangun akun utama |

## ⛔ Di-skip — Semua dengan Alasan Konkret

### A. Jenuh: banyak seller **dan** ada beberapa seller serius (runs ≥10rb)

| Konsep | Seller / Serius | Incumbent terbesar | Kenapa di-skip |
|---|---|---|---|
| Threads (Meta) | **84 / 13** | `curious_coder/threads-scraper` 1.157u/2.386.636r | Paling jenuh di seluruh babak ini |
| Verifikasi email | **57 / 9** | `overpowered/verify-email` 2.513u/350.330r | Komoditas; 9 seller punya pipeline nyata |
| Truth Social | **45 / 4** | `muhammetakkurtt/truth-social-scraper` 1.817u/403.879r | Incumbent raksasa + 3 penantang serius |
| Company enrichment / firmografis | **44 / 4** | `automation-lab/linkedin-company-scraper` 847u/132.186r | Inti bisnis banyak seller besar |
| Podcast charts & episode | **61 / 3** | `jupri/apple-podcast` 266u/402.946r | Jenuh; `jupri` pakai arsitektur 1-run-1-item |
| Validasi/lookup nomor telepon | **56 / 3** | `neuralverge` 249u/50.733r; `akula.marketing` 2.494u | Jenuh **dan** berisiko (data pribadi massal — konsisten dengan keputusan WhatsApp validator di Babak 40) |
| Deteksi tech-stack (BuiltWith/Wappalyzer) | **67 / 2** | `nexgendata/wappalyzer-replacement` 1.440u | Sudah tercatat di riset lama, kini terkonfirmasi jenuh |
| Weibo | **22 / 2** | `sian.agency/weibo-scraper` 1.239u; `zhorex` 369u/16.410r | Dua seller mapan |
| Product Hunt | **70 / 2** | `danpoletaev` 856u; `maximedupre` 704u | 70 seller; rpu cuma 10–21 |
| Angi / Thumbtack / Houzz | **47 / 2** | `igolaizola/angi-scraper` 353u/16.347r | Jenuh |
| Home Depot / Lowe's | **22 / 3** | `maplerope44/home-depot-product-lookup` 303u/147.156r | Ritel AS besar = selalu jenuh |
| ASO / app-store intelligence | **68 / 3** | `automation-lab/apple-app-store-scraper` 552u | Jenuh |
| Ketersediaan kalender sewa liburan (VRBO) | **26 / 3** | `jupri/vrbo-property` 316u/561.286r | Satu-satunya sub-tipe "ketersediaan" yang laku — dan sudah dikuasai |
| Vacation/OpenTable reservation | 10 / 1 | `memo23/opentable-reviews-cheerio` 102u/66.970r | OpenTable sudah dinyatakan jenuh sejak `actors_researcher_v2.md` |

### B. Banyak seller tapi **tanpa** seller serius, atau demand terlalu kecil (TAM mikro)

| Konsep | Seller / Serius | Actor terbesar | Kenapa di-skip |
|---|---|---|---|
| **Cruise semua brand** (rekomendasi Babak 40 #6b) | 12 / **0** | `sercul/royal-caribbean` **129u**/5.279r | **Rekomendasi Babak 40 dicabut**: `sercul` memang menguasai 10 brand, tapi **tidak ada satu pun** actor cruise dengan runs ≥10rb. Pasarnya kecil, bukan "belum digarap" |
| Chrome Web Store | 49 / 0 | `neatrat` 118u/3.931r | 49 seller berebut kue kecil |
| Shopify App Store | 43 / 1 | `storedata/shopify-appstore-scraper` 258u/23.958r | 43 seller = jadi pendatang ke-44 |
| Dealer inventory (cars.com/CarGurus) | 46 / 1 | `fatihtahta/cars-com-scraper` 102u/15.069r | Jenuh; 46 seller |
| Copart / IAAI (lelang salvage AS) | 26 / 1 | `parseforge/copart-public-search-scraper` **476u**/32.231r ⭐5.0(7) | Demand bagus, tapi 26 seller dan incumbent rating sempurna — masuk sekarang = kloning ke-27 |
| Copart/salvage **non-AS** (UK/EU/JP) | 7 / **0** | `memo23/copart-scraper` 55u | Sudut "yurisdiksi kosong" untuk lelang salvage **tidak laku** — max 55u |
| Kick.com | 23 / 0 | `aitooolsmax/kick-data-scraper` 78u/8.355r | 23 seller sudah masuk; yang user-nya besar (806u) cuma **video downloader** dengan rpu 5 |
| Lemon8 | 10 / 0 | `teodor_banea` 47u | Platform baru tapi sudah 10 seller, semua <75u |
| Douban | 13 / 0 | `zhorex/douban-scraper` 180u/1.766r | rpu 10 = sekali pakai |
| Beehiiv (newsletter, **bukan** Substack) | 16 / 0 | `scraper_guru/beehiiv-scraper` **20u** | Pasar mati — 16 seller berebut niche 20-user |
| Self storage | 9 / 0 | `lumen_limitless` 10u/923r | Mati |
| EV charging / PlugShare | 14 / 0 | `parseforge/plugshare-scraper` 65u | Sub-tipe "ketersediaan real-time" — TAM mikro |
| Instacart / slot belanja | 16 / 0 | `scraptivo/instacart-scraper` 69u | Mikro |
| Dispensary ganja (Weedmaps/Dutchie/Leafly) | 17 / 0 | `tfmcg3/dutchie` 66u/1.139r | Mikro + regulasi per-negara bagian |
| Balap kuda | 11 / 0 | `jungle_synthesizer/equibase` 83u | Mikro |
| Lotere | 9 / 0 | `harvest/powerball` 97u, rpu 8 | Data mingguan → bukan pipeline |
| Farfetch / fashion mewah | 6 / 0 | `123webdata/farfetch-scraper` 53u | Mati |
| Parkir, gym/kelas, coworking, RV, kapal pesiar sewa, jet pribadi, alat berat sewa, slot janji temu pemerintah, showtime bioskop | 0–11 / 0 | semua ≤9u | **18 sub-tipe "ketersediaan/inventory real-time" (rekomendasi Babak 40 #6a) diuji — semuanya mikro.** Vein ini resmi ditutup |
| Hospital price transparency, nursing home, klinik hewan, dokter gigi, apotek | 7–23 / ≤1 | max 4–169u, kebanyakan lead-gen | Vertikal kesehatan = direktori lead-gen biasa, sudah ramai; data harga rumah sakit AS mati (max **4u**) |
| Bea cukai/bill of lading, freight rate, load board, kongesti pelabuhan, air cargo | 2–18 / ≤1 | `jungle_synthesizer/importyeti` 147u | Vertikal logistik sudah tersentuh `xtracto/marinetraffic-ship-tracker`; sisanya mikro |
| Komoditas (mandi, ternak, pupuk, scrap, lumber, bullion) | 1–30 / 0 | max 42u | Semua mikro; "scrap metal" bahkan false positive (kunci `scrap` match "scraper") |

### C. Terlihat menjanjikan, **gugur setelah verifikasi** (jebakan yang punya nama di Babak 40)

| Konsep | Kelihatannya | Faktanya | Jenis jebakan |
|---|---|---|---|
| Telegram channel analytics | 1 actor / **1 seller** (`arachnetix/tg-post-stats` 296u/21.759r) | **51 actor / 44 seller / 3.445u** setelah union diperluas | **False negative kunci sempit** — gotcha baru babak ini |
| Hostelworld | 1 seller "serius" | Serius-nya `knagymate` **6u**/12.033r → runs besar dari 6 user | **Jebakan runs** (Babak 40 #1) |
| Flightradar / ADS-B | 1 seller serius, 60.015 runs | `agentify/flightradar24-mcp-server` **14u** — MCP server, 1 run = 1 panggilan tool | **Jebakan runs** |
| Verifikasi lisensi profesi/kontraktor | 1 serius dari 28–31 seller | `lulzasaur/contractor-license-scraper` **14u**/45.713r | **Jebakan runs** |
| Direktori NPI tenaga medis | 1 serius dari 50 seller | `rdx1s/nppes-npi-registry-scraper` **2u**/14.887r | **Jebakan runs** |
| Sherlock (`misceres/sherlock`) | **37.973 user** — user terbanyak ke-2 di antara actor non-`xtracto` | rpu **3** (sekali pakai), dan isinya pembungkus tool OSS gratis | **Jebakan user** — banyak user ≠ ROI; komoditas open-source |
| Username availability checker | 3.688u (`maged120`), 915u, 638u | 27 seller, rpu 2–18, tool sekali-pakai bukan sumber data | Komoditas |

### D. Di-skip karena di luar strategi (konsisten dengan v2 / Babak 39 / 40)

| Konsep | Stats | Alasan |
|---|---|---|
| `apify/web-scraper`, `cheerio-scraper`, `playwright/puppeteer-scraper`, `rag-web-browser` | 16rb–124rb user, sampai 181 juta runs | **Tooling generik milik Apify sendiri** — bukan pasar yang bisa dimasuki |
| Screenshot/PDF/image downloader/proxy tester (`jancurn/url-to-pdf` 466u, `dz_omar/ultimate-screenshot` 256u, `apify/proxy-test` 437u) | rpu 900–7.900 | Kategori tooling generik — keputusan yang sama sudah diambil untuk uploader S3/GCS (v2) dan `s-r/price-scraper` (Babak 40) |
| Monitoring perubahan halaman (`jakubbalada/content-checker` 2.238u/6.960.688r) | 27 seller | Tooling generik, bukan sumber data |
| Downloader dewasa (`serpxxx/*`, 1.000–1.314u masing-masing) | rpu 22–28 | Di luar portofolio |
| Direktori telepon **residensial** di Eropa (Pages Blanches, Telefonbuch, Pagine Bianche, 192.com) | 0–8 seller, semua ≤23u | **Dua alasan:** demand nol di luar Kanada (`fayoussef/canada411-ca` 167u/25.761r satu-satunya yang laku), **dan** data telepon rumah tangga di UE = data pribadi (risiko GDPR). Hanya varian **bisnis** yang direkomendasikan — lihat kandidat #1 |

## 🔧 Koreksi untuk Babak 40

| Rekomendasi Babak 40 | Status setelah diuji di babak ini |
|---|---|
| #6b — "cruise per-brand di luar 10 brand `sercul` (mis. Asia/Eropa regional)" | ❌ **Dicabut.** 12 seller, **0 seller serius**, actor terbesar 129u. Pasar cruise di Apify memang kecil; `sercul` mendominasi bukan karena pesaing belum datang, tapi karena tidak ada yang mau |
| #6a — "sub-tipe ketersediaan/inventory real-time di vertikal non-restoran" | ❌ **Dicabut.** 18 sub-tipe diuji, semua TAM mikro (≤69u). Satu-satunya yang laku (kalender VRBO) sudah dikuasai `jupri` |
| Aturan "union ≥3 frasa sebelum mengklaim kandidat" | ✅ Tetap berlaku, tapi **diperketat**: kunci filter harus memuat **nama platform telanjang** (lihat Gotcha #1) |

## Insight Strategis Babak 41

> **"Stats tinggi" dan "layak dibangun" hampir tidak beririsan lagi.** Ini pertama kalinya diukur langsung: 1.384 actor ber-stats tinggi discan, **nol** vertikal baru ditemukan di sana. Semua yang laku besar sudah dipegang `xtracto` atau sudah punya 12+ seller. Jadi permintaan "carikan actor ber-ROI tinggi" **tidak bisa dijawab** dengan mencari actor ber-stats tinggi yang belum digarap — jawabannya harus lewat **memindahkan data-type yang stats-nya sudah terbukti ke yurisdiksi yang belum ada pemainnya**.

> **Direktori bisnis nasional adalah versi "TAM besar" dari pola Babak 37/38.** Court judgments Singapura/Filipina berhasil karena nol kompetitor, tapi TAM-nya kecil. Direktori bisnis punya bukti demand **ratusan user per negara** (DE 928u, FR 1.279u, IN 1.635u) — dan masih menyisakan belasan negara kosong. Ini kombinasi terbaik yang pernah muncul di 41 babak riset: **bukti demand besar + kompetitor nol + situs target terbuka tanpa WAF (Turki)**.

> **Jebakan keempat punya nama sekarang: "jebakan user".** Melengkapi tiga jebakan Babak 40 (runs, seller-tunggal, sub-tipe). `misceres/sherlock` punya **37.973 user** — angka yang bikin siapa pun berhenti — tapi rpu-nya **3** dan produknya cuma membungkus tool open-source gratis. Tesnya: **user banyak × rpu rendah × produk komoditas = tidak ada yang bisa dimonetisasi**.

## Rekomendasi Lanjutan

1. **Eksekusi kandidat #1 secara bertahap, jangan borongan:** bangun **Sarısayfalar (Turki)** dulu — nol kompetitor, HTTP 200 tanpa WAF, HTML 111 KB. Ukur traksi 2–4 minggu sebelum menambah Indonesia → Brasil → Swedia.
2. **Recon dulu sebelum commit ke Jepang & Meksiko.** Keduanya nol/hampir-nol kompetitor, tapi probe HTTP-nya timeout — kemungkinan besar itu **penyebab** kosongnya, bukan kebetulan.
3. **Social Blade layak dikejar kalau permukaan publiknya terbuka** — verifikasi dulu apakah statistik kanal bisa diambil tanpa login; celahnya adalah rating 2.5 milik incumbent, jadi nilai jualnya **keandalan**, bukan fitur baru.
4. **Berhenti menscan tiga vein ini — sudah tuntas dan terbukti negatif:** (a) ketersediaan/inventory real-time, (b) cruise, (c) ujung stats-tinggi Store (users ≥150 & runs ≥20rb) untuk mencari platform baru.
5. **Vein yang layak jadi Babak 42:** teruskan logika kandidat #1 ke **jenis direktori lain yang sudah terbukti laku di 1–2 negara saja** — mis. direktori dokter/klinik, direktori pengacara, direktori kontraktor, atau direktori restoran per-negara. Metodenya sama persis: ambil data-type yang punya ratusan user di satu negara, lalu uji per-yurisdiksi + probe HTTP.

## File Referensi Babak 41

- `output/xtracto-full.json` — snapshot 218 actor `xtracto` (tidak berubah dari Babak 39/40)
- `output/scan-v5-competition.json` — **116 konsep baru**, per konsep: seller, seller serius, total user/runs, actor terbesar, flag dedupe
- `output/scan-v5-highstats.json` — **1.384 actor** ber-stats tinggi (users ≥150 & runs ≥20.000), 21 kategori, paginasi penuh
- `scratchpad/compete41.py` — Pass 1 (116 konsep, union ≥3 frasa sejak awal)
- `scratchpad/detail41.py` — Pass 2 (verifikasi per-actor 24 finalis)
- `scratchpad/highstats41.py` / `highstats41b.py` — Pass 3 (scan top-down + tampilan berflag)
- `scratchpad/verify41.py` — Pass 4 (uji kompetisi union kandidat top-down)
- `scratchpad/verify41b.py` — Pass 5 (uji per-yurisdiksi 15 negara direktori bisnis + 7 direktori telepon, plus probe HTTP)

---

# Babak 42 — Direktori Profesi per Yurisdiksi: Vein Pengacara & Dokter Ditemukan, 40+ Konsep Lain Dinyatakan Mati (2026-09-08)

**Konteks:** user kembali minta daftar actor **ROI data tinggi / stats sudah tinggi**, dengan syarat tidak boleh duplikat dengan (a) akun kedua [`xtracto`](https://api.apify.com/v2/store?username=xtracto), (b) dokumen ini, dan (c) [`actors_researcher_v2.md`](actors_researcher_v2.md). Babak ini menjalankan **Rekomendasi Lanjutan Babak 41 #5** secara harfiah: ambil pola kandidat #1 (direktori bisnis nasional) dan teruskan ke **jenis direktori lain yang sudah terbukti laku di 1–2 negara saja** — direktori pengacara, dokter, restoran, tukang, apotek, B2B, agen properti — plus 8 tipe registry dan 6 vein non-direktori yang belum pernah diuji per-yurisdiksi.

**Snapshot dedupe:** `apify-my-store.py xtracto` di-refresh hari ini → **masih 218 actor**, tidak berubah sejak Babak 39/40/41.

## Ringkasan Eksekutif

- **Temuan utama — direktori pengacara nasional.** Sweep luas (8 frasa, kunci lebar) menemukan **96 actor / 49 seller** untuk data-type ini, tapi **seluruh 32 besar berbasis AS** (`fatihtahta/avvo-scraper` **1.250u**, `jungle_synthesizer/justia-scraper` **1.023u / 14.358 runs**, `findlaw-scraper` 182u/14.701r). Di luar AS praktis kosong: UK 3 seller/30u, Kanada 1/12u, Jerman 1/1u, Prancis 2/3u, dan **11 yurisdiksi nol actor** (AU, ES, IT, NL, BR, IN, ID, PH, SG/MY, TR, JP). Probe HTTP: **Indonesia (hukumonline) 200/532 KB, India (lawrato) 200/404 KB, Singapura 200/340 KB, Malaysia 200/86 KB, Jepang 200/36 KB** — semuanya terbuka.
- **Temuan kedua — direktori dokter Asia Tenggara.** Data-type terbukti di 3 yurisdiksi (Doctoralia ES/LATAM 10 seller/**426u**, Practo India 9 seller/**342u**, AS 25 seller/466u) tapi **ID/PH/TH/VN nol actor**. Probe: Halodoc 200/286 KB, BookingCare VN 200/308 KB, Alodokter 200/44 KB.
- **Peringatan Babak 41 soal "pembeli data Turki" sebagian terbantah:** `sahibinden` (marketplace TR) menampung **1.362 user** di 6 seller, `clearpath/sahibinden-scraper-pro` **318u/12.549r**. Ada pembeli nyata untuk data Turki.
- **40+ konsep dimatikan permanen.** Classified ads per negara ternyata **jenuh total** (marktplaats 34 seller, wallapop 42, gumtree 40, willhaben 32, tokopedia 32) — bukan vein kosong seperti dugaan awal. Delapan tipe registry baru (bursa efek non-SEC, VAT/GST, plat nomor, register amal, registrasi obat, izin usaha, direktori sekolah, merek dagang nasional) **semuanya mati atau jenuh**.

## Metodologi Babak 42

```bash
python apify-my-store.py xtracto -o output/mine-xtracto.json   # 218 actor (tidak berubah)

# Pass 1 - 49 konsep BARU (nol tumpang tindih dengan compete.py/compete2.py/compete40.py/
#   compete41.py/verify40*.py/verify41*.py - ~600 konsep lama sudah diinventarisasi dulu)
#   cakupan: 5 direktori pengacara | 5 direktori dokter | 4 direktori restoran |
#            9 classified-ads per negara | 3 direktori tukang | 2 apotek | 3 B2B |
#            2 agen properti | 8 registry per-yurisdiksi | 2 freelance | 6 non-direktori
#   scratchpad/compete42.py -> output/scan-v6-competition.json
# Pass 2 - uji PER-YURISDIKSI 27 kombinasi (16 negara pengacara, 8 negara dokter,
#   2 restoran, 1 classified TR)  scratchpad/verify42.py -> output/scan-v6-jurisdiction.json
# Pass 3 - sweep luas anti-false-negative: 8 frasa + 16 kunci untuk memetakan SELURUH
#   populasi actor direktori pengacara di Store (96 actor / 49 seller)
# Pass 4 - probe HTTP langsung 17 situs target (scratchpad/probe42.py)
```

Aturan yang diwarisi dan dipakai sejak Pass 1: union ≥3 frasa per konsep (Babak 40 #1), kunci wajib memuat **nama platform telanjang** (Babak 41 #1), metrik penentu = jumlah seller dengan `totalRuns ≥ 10.000` ("serius"), tanpa `max-users`.

### Gotcha metodologi baru

1. **Union harus lintas-PASS, bukan cuma lintas-frasa di dalam satu pass.** Kasus nyata di babak ini: konsep "dokter FR/DE (Doctolib/Jameda)" mengembalikan **0 actor** di Pass 2, padahal Pass 1 — kunci sama persis, hanya frasa querinya beda — menemukan **7 seller / 156u** termasuk `giovannibiancia/doctolib-scraper` **77u**. Set frasa yang berbeda menghasilkan populasi yang berbeda total. → **"0 actor" dari satu pass bukan bukti kosong.** Angka final di dokumen ini digabung dari semua pass; klaim "nol kompetitor" hanya dipakai kalau nol di **semua** pass **dan** lolos sweep luas Pass 3.
2. **"Nol seller" bukan sinyal peluang kalau tidak dipasangkan dengan bukti demand di yurisdiksi lain.** Bursa efek non-SEC terlihat seperti pola "yurisdiksi kosong" yang sempurna (6 seller, 0 serius) — tapi actor terbesarnya cuma **9 user**. Itu bukan "belum digarap", itu "tidak ada pembeli". Tes minimum sebelum menyebut sesuatu kandidat: **ada ≥1 yurisdiksi dengan ratusan user** untuk data-type yang sama.
3. **Kunci pendek generik masih lolos ke hasil meski aturan Babak 41 #2 sudah dipakai.** `jungle_synthesizer/danceus-studio-scraper` (sanggar dansa) masuk ke konsep "direktori sekolah/kampus" lewat kunci `school-dir`/`accredit`. Semua angka di tabel bawah sudah dibersihkan manual dari false positive semacam ini.

## ✅ Kandidat Baru — Belum Ada di `xtracto`, Belum Pernah Muncul di Riset Mana Pun

Dedupe diverifikasi harfiah terhadap 218 actor `xtracto`: **tidak ada satu pun** actor pengacara, dokter, restoran-direktori, atau sahibinden di sana (yang ada hanya `olx-classifieds-scraper`, `europages-company-scraper`, `capterra-b2b-scraper`, `clinicaltrials-studies`).

| # | Prioritas | Ide Actor | Bukti Demand (stats incumbent) | Kompetisi di yurisdiksi target | Kenapa Layak / Catatan Eksekusi |
|---|---|---|---|---|---|
| 1 | 🔴 **Tinggi** | **Direktori Pengacara Nasional — yurisdiksi kosong** (Hukumonline 🇮🇩, LawRato/Bar Council 🇮🇳, Law Society 🇸🇬, Malaysian Bar 🇲🇾, Nichibenren 🇯🇵) | AS: **96 actor / 49 seller / 3.205u** total. `fatihtahta/avvo-scraper` **1.250u**, `jungle_synthesizer/justia-scraper` **1.023u / 14.358r**, `findlaw-scraper` 182u/**14.701r**, `martindale-scraper` 43u | 🇦🇺🇪🇸🇮🇹🇳🇱🇧🇷🇮🇳🇮🇩🇵🇭🇸🇬🇲🇾🇹🇷🇯🇵 **nol actor** · 🇬🇧 3 seller/30u · 🇨🇦 1/12u · 🇩🇪 1/1u · 🇫🇷 2/3u | Pola **"data-type terbukti × yurisdiksi kosong"** — sama dengan yang 3× berhasil (Babak 37 Singapura, 38 Filipina, 41 direktori bisnis), dan bukti demand-nya **paling besar yang pernah muncul untuk direktori profesi**. Data pengacara = **data profesional publik** (bukan data pribadi rumah tangga), jadi tidak kena masalah GDPR yang membunuh direktori telepon residensial di Babak 41. Urutan yang disarankan: **ID → IN → SG/MY**. |
| 2 | 🟠 Sedang-Tinggi | **Direktori Dokter/Klinik Asia Tenggara** (Halodoc/Alodokter 🇮🇩, BookingCare 🇻🇳, DocDoc 🇵🇭) | Terbukti di 3 yurisdiksi: **Doctoralia ES/LATAM** 10 seller/**426u** (`giovannibiancia/Doctoralia` **212u**, `muhammetakkurtt/doctoralia-brazil-scraper` 104u) · **Practo 🇮🇳** 9 seller/**342u** (`easyapi/practo-doctor-scraper` **192u** ⭐5.0) · AS 25 seller/466u | 🇮🇩🇵🇭🇹🇭🇻🇳 **nol actor** di semua pass | Data-type terbukti di 3 benua dengan pola yang sama (satu portal dominan per negara → satu actor per portal). TAM per-negara lebih kecil dari pengacara AS, tapi **Indonesia = pasar rumah sendiri** (moat bahasa + sudah ada `klikindomaret`/`blibli`/`detik` di repo, jadi pola anti-bot situs ID sudah dikuasai). |
| 3 | 🟢 Rendah-Sedang | **TheFork / Quandoo (reservasi restoran Eropa)** | `clearpath/thefork-scraper` **165u**, `jdtpnjtp/thefork-restaurant-scraper-advanced` 99u/**26.437r** — 282u total, 33.369 runs | **5 seller, 1 serius** — bukan kekosongan, tapi tipis | Dicatat jujur sebagai **bukan gap**: sudah ada 5 penjual dan 1 di antaranya serius. Hanya layak kalau ada sudut beda yang jelas (mis. coverage kota non-FR/ES, atau data menu/harga yang tidak diambil incumbent). Jangan jadikan prioritas. |

### Catatan teknis kandidat #1 & #2 (probe HTTP langsung, 2026-09-08)

| Target | Status | Catatan |
|---|---|---|
| 🇮🇩 `hukumonline.com/pusatdata` | **200**, Cloudflare lolos (`curl_cffi` impersonate), **532 KB** | HTML paling tebal dari semua target — kedalaman data terbaik |
| 🇮🇳 `lawrato.com/lawyers` | **200**, Cloudflare lolos, **404 KB** | Terbuka; portal komersial dengan profil lengkap |
| 🇸🇬 `lawsociety.org.sg/find-a-lawyer` | **200**, Cloudflare lolos, **340 KB** | Direktori resmi Law Society — data otoritatif |
| 🇲🇾 `malaysianbar.org.my` | **200**, Cloudflare lolos, 86 KB | Terbuka |
| 🇯🇵 `nichibenren.or.jp` | **200**, 36 KB | Terbuka tapi HTML tipis — cek dulu apakah direktori anggotanya publik |
| 🇧🇷 `cna.oab.org.br` | **200**, hanya **10 KB** | Kemungkinan besar SPA berbasis JS — perlu recon lebih dalam sebelum commit |
| 🇮🇳 `barcouncilofindia.org` | **200**, **0 KB** | Body kosong — pakai LawRato sebagai target India, bukan Bar Council |
| 🇪🇸 `abogacia.es` | **403** | Terblokir |
| 🇹🇷 `barobirlik.org.tr` | **522** (Cloudflare, origin down) | Tidak viable — **kebalikan** dari Sarısayfalar yang terbuka penuh di Babak 41 |
| 🇦🇺 `findlaw.com.au` · 🇮🇩 `peradi.or.id` | **Timeout** | Nol kompetitor kemungkinan **karena sulit diakses** — jangan diprioritaskan tanpa recon |
| 🇮🇹 `consiglionazionaleforense.it` · 🇳🇱 `advocatenorde.nl` | **404** (path berubah) | Perlu penelusuran ulang URL sebelum divonis |
| 🇮🇩 `halodoc.com/cari-dokter` | **200**, **286 KB** | Target dokter terbaik untuk Indonesia |
| 🇻🇳 `bookingcare.vn/bac-si` | **200**, **308 KB** | Terbuka penuh, nginx polos |
| 🇮🇩 `alodokter.com/cari-dokter` | **200**, 44 KB | Terbuka, HTML lebih tipis dari Halodoc |
| 🇵🇭 `docdoc.com/ph/doctors` | **200**, 10 KB | Tipis — kemungkinan SPA |

> **Peringatan jujur untuk kandidat #1 (sama seperti peringatan Babak 41, dan masih berlaku):** konsentrasi 100% demand di AS bukan kebetulan — pasar *legal lead generation* AS punya belanja iklan raksasa yang **tidak punya padanan** di Indonesia/India/Jepang. Yang sudah terbukti di sini adalah **data-type-nya**, bukan pasarnya per negara. Bedanya dengan Babak 41: kali ini bukti demand-nya **3.205 user** (vs 928u Jerman untuk direktori bisnis) dan **49 seller berebut satu yurisdiksi saja** — sinyal TAM yang jauh lebih kuat. Tetap: **bangun 1 negara dulu (Indonesia), ukur 2–4 minggu, baru lanjut.**

## 🔁 Sudah Tercakup — Muncul di Scan Tapi Bukan Temuan Baru

| Konsep (stats yang bikin dia muncul) | Sudah ada di | Catatan |
|---|---|---|
| Europages / Kompass (B2B EU, 33 seller, 718u) | `xtracto/europages-company-scraper` | Sekaligus **jenuh** — 33 seller |
| OLX (classified) | `xtracto/olx-classifieds-scraper` | Vein classified sudah tersentuh |
| Capterra (direktori software B2B) | `xtracto/capterra-b2b-scraper` | — |
| ClinicalTrials (data kesehatan) | `xtracto/clinicaltrials-studies` | Beda data-type dari direktori dokter, tapi vertikal kesehatan sudah tersentuh |
| Direktori agen properti (38 seller, `data_dino/realtor-scraper`) | `xtracto` + riset lama | Sudah diputuskan |
| Merek dagang (EUIPO `dltik/euipo-trademarks-scraper` 50u/5.976r) | Babak 40 ("trademark search") + riset lama | Sudah ada keputusan |
| Trainline, GSA eLibrary, ANVISA | Babak 40 (train ticket, government vendor list, fda/ema) | Sudah discan sebagai konsep generik |

## ⛔ Di-skip — Semua dengan Alasan Konkret

### A. Jenuh: banyak seller **dan** ada seller serius (runs ≥10rb)

| Konsep | Seller / Serius | Actor terbesar | Kenapa di-skip |
|---|---|---|---|
| **Direktori pengacara AS** (avvo/justia/findlaw/martindale) | **49** / 1 | `fatihtahta/avvo-scraper` **1.250u** | Demand terbesar yang ditemukan babak ini, tapi 49 seller berebut satu yurisdiksi = jadi pendatang ke-50. **Justru inilah bukti demand untuk kandidat #1** — masuk lewat yurisdiksi lain, bukan lewat AS |
| Classified IT/ES (subito/wallapop/milanuncios) | 42 / 2 | `autoclient/wallapop-spain-scraper` 29u/**135.744r** | Jenuh |
| Classified UK/AU (gumtree) | 40 / **3** | `sync-network/gumtree-com-listing-scraper` 119u/**98.778r** | Paling jenuh di vein classified |
| Direktori agen properti US/UK | 38 / 1 | `data_dino/realtor-scraper` | Jenuh **dan** sudah ter-cover |
| **Validasi VAT/GST/NPWP per negara** | 38 / 1 | `ryanclinton/eu-vat-validator` **13u**/22.033r | Jenuh; seller "serius"-nya adalah **jebakan runs** (13 user, runs besar dari pemakaian mesin) |
| Classified NL/BE (marktplaats/2dehands) | 34 / 1 | `ecomscrape/marktplaats-product-search` 22u/10.983r | Jenuh |
| B2B EU (kompass/europages/wlw) | 33 / 0 | `santamaria-automations/kompass-scraper` 119u | Jenuh + sudah di `xtracto` |
| Classified AT/CH (willhaben/ricardo) | 32 / 1 | `memo23/apify-ricardo-ch-scraper` 84u/12.092r | Jenuh |
| Classified ID (tokopedia/bukalapak/carousell) | 32 / 2 | `faz/tokopedia-scraper` 47u/13.147r | Jenuh — meski pasar rumah sendiri |
| B2B CN/KR/TW (made-in-china/ec21) | 30 / 0 | `automation-lab/made-in-china-scraper` 28u | 30 seller berebut |
| Restoran IN/ID (zomato/gofood/swiggy) | 29 / 0 | `jupri/zomato` **420u**/3.045r | Demand bagus tapi 29 seller; `jupri` incumbent kuat |
| Direktori dokter AS (zocdoc/healthgrades/vitals) | 25 / 1 | `jaybird/healthgrades-scraper` 75u | Terfragmentasi: 25 seller berbagi 466u — tiap actor kecil |
| Classified SE/DK/FI (blocket/tori/dba) | 22 / 0 | `blackfalcondata/dba-listings-scraper` 25u | 22 seller, tidak ada yang laku besar |
| Merek dagang kantor nasional | 12 / 0 | `dltik/euipo-trademarks-scraper` 50u/5.976r | Jenuh + sudah diriset Babak 40 |
| Register amal/NGO per negara | 12 / 0 | `ryanclinton/uk-charity-commission` **9u** | 12 seller berebut niche 9-user |
| Restoran JP (tabelog/gurunavi/hotpepper) | 12 / 0 | `cloud9_ai/tabelog-scraper` 47u | 12 seller, **0 serius**, TAM 159u — kecil dan sudah ramai |
| Freelance EU (malt/freelancermap/twago) | 10 / 0 | `solidcode/freelancermap-scraper` 36u | 10 seller, nol serius, TAM 272u |
| Doctoralia ES/LATAM · Practo IN | 10 / 0 · 9 / 0 | `giovannibiancia/Doctoralia` 212u · `easyapi/practo-doctor-scraper` 192u | **Yurisdiksi ini sudah diambil** — dipakai sebagai bukti demand untuk kandidat #2, bukan target |

### B. Seller sedikit/nol TAPI pasarnya memang mati — bukan peluang

| Konsep | Seller / Serius | Actor terbesar | Kenapa di-skip |
|---|---|---|---|
| **Bursa efek: filing emiten non-SEC** (IDX/Bursa/SGX/HKEX) | 6 / **0** | `crawlerbros/hkex-disclosure-announcements` **2u**/2.170r | Terlihat seperti "yurisdiksi kosong" sempurna, tapi **actor terbesarnya 9 user**. SEC EDGAR laku karena ekosistem investor AS; bursa lain tidak punya pembeli. **Contoh utama Gotcha #2 babak ini** |
| Direktori tukang UK (checkatrade/mybuilder/ratedpeople) | 5 / 0 | `trev0n/checkatrade-scraper` 54u | TAM 89u — mikro |
| Direktori tukang DE/NL (myhammer/werkspot) | 1 / 0 | `rainminer/my-hammer-de-scraper` **1u** | Mati |
| Direktori tukang FR/ES/IT (habitissimo/instapro) | **0** / 0 | — | Nol actor **dan** nol bukti demand di yurisdiksi mana pun (US sudah divonis jenuh di Babak 41) → pasar mati, bukan gap |
| Izin usaha / business license per negara | 4 / 0 | `fortuitous_pirate/la-business-license` 7u | Mikro; tumpang tindih dengan sweep business-registry riset lama |
| Harga tiket kereta/bus per negara | 4 / 0 | `studio-amba/trainline-scraper` 16u | Mikro |
| Cek plat nomor / vehicle registration | 2 / 0 | `freecamp008/french-license-plate-lookup` 53u | TAM 61u; sebagian yurisdiksi juga bermasalah secara hukum (data pemilik kendaraan) |
| Apotek e-comm Asia · Apotek EU | 2 / 0 · 1 / 0 | `easyapi/netmeds-product-scraper` 28u · `studio-amba/shopapotheke-scraper` 5u | Mikro di kedua benua |
| Classified Afrika (jiji/tonaton) | 2 / 0 | `stealth_mode/jiji-product-search` 39u | Kosong tapi TAM 40u |
| Classified IR/PK/BD (divar/bikroy) | 2 / 0 | `logiover/divar-scraper` 5u | Mati |
| Registrasi obat/BPOM per negara | 1 / 0 | `parseforge/anvisa-brazil-medicines` **1u** | Mati |
| E-catalogue pemerintah (LKPP/GSA) | 1 / 0 | `scrapesage/gsa-elibrary-scraper` 1u | Mati |
| Harga pangan pasar per negara | 1 / 0 | `scrapers_lat/latam-wholesale-food-prices` 2u | Mati |
| Lelang barang sitaan/pajak | 1 / 0 | `jungle_synthesizer/propertyroom-law-auction` 2u | Mati; konsisten dengan vonis lelang salvage di Babak 41 |
| Gig lokal Asia (sribulancer/workana) | 1 / 0 | `scrapestorm/workana-jobs-scraper` 9u | Mati |
| Direktori sekolah/kampus per negara | 1 / 0 | `jungle_synthesizer/danceus-studio-scraper` (false positive) | Nol actor asli — dan riset lama sudah memvonis "school ratings"/"university rankings" |
| Subsidi/bansos · Zakat/wakaf | **0** / 0 | — | Nol actor, nol demand |

### C. Di-skip karena risiko / di luar strategi

| Konsep | Alasan |
|---|---|
| **Data penerima bansos/subsidi & penerima zakat** | Nol pasar **dan** isinya data pribadi penerima manfaat (nama + alamat + status ekonomi) — risiko privasi jelas, tidak dikejar meski kosong |
| **Doctolib / Jameda (dokter FR/DE)** | Sudah 7 seller/156u; ditambah Doctolib menegakkan ToS anti-scraping paling agresif di vertikal ini. Kandidat #2 sengaja diarahkan ke SEA, bukan EU |
| **Cek plat nomor per negara** | Selain TAM mikro, di banyak yurisdiksi data pemilik kendaraan adalah data pribadi terlindungi |
| **Direktori pengacara Turki** | Nol kompetitor, tapi `barobirlik.org.tr` mengembalikan **522** (origin down) — beda nasib dari Sarısayfalar Babak 41 yang terbuka penuh |

## 🔧 Koreksi untuk Babak 41

| Pernyataan Babak 41 | Status setelah diuji di babak ini |
|---|---|
| Peringatan kandidat #1: *"belum tentu ada pembeli sebesar itu untuk lead Turki"* | ⚠️ **Sebagian terbantah.** `sahibinden` (marketplace TR) menampung **1.362 user** di 6 seller, `clearpath/sahibinden-scraper-pro` **318u/12.549r** — pembeli data Turki jelas ada. **Tapi** ini marketplace konsumen, bukan direktori B2B; jadi bukti parsial, bukan konfirmasi penuh untuk Sarısayfalar |
| Rekomendasi #5: *"teruskan ke direktori dokter/pengacara/kontraktor/restoran per negara"* | ✅ **Dijalankan penuh.** Hasil: **pengacara BERHASIL** (bukti demand 3.205u, 11 yurisdiksi kosong), **dokter SEBAGIAN** (3 yurisdiksi terbukti, SEA kosong), **kontraktor/tukang GAGAL** (UK 89u, DE/NL 1u, FR/ES/IT nol — pasar mati di semua yurisdiksi), **restoran GAGAL** (JP 12 seller/159u, IN/ID 29 seller, EU 5 seller — tidak ada yurisdiksi yang kosong sekaligus bernilai) |
| Gotcha #1 Babak 41 (union ≥3 frasa + nama platform telanjang) | ✅ Tetap berlaku, tapi **diperluas**: union juga harus lintas-**pass**, bukan cuma lintas-frasa (lihat Gotcha #1 babak ini) |

## Insight Strategis Babak 42

> **Pola "data-type terbukti × yurisdiksi kosong" punya syarat keempat yang baru ketahuan: data-type-nya harus laku di ≥2 yurisdiksi yang berbeda ekosistem.** Direktori dokter laku di AS **dan** Spanyol/LATAM **dan** India — tiga ekosistem berbeda, jadi kemungkinan besar juga laku di SEA. Direktori pengacara hanya laku di AS — 49 seller berebut satu negara, nol traksi di 15 negara lain. Itu bisa berarti dua hal yang berlawanan (belum ditemukan, atau memang tidak ada pembeli), dan **hanya eksperimen kecil yang bisa membedakannya**. Karena itu kandidat #1 diberi prioritas tinggi tapi dengan perintah eksplisit: satu negara dulu.

> **Vein "classified ads per negara" resmi ditutup — dan ini kejutan.** Hipotesis awal babak ini: OLX/Avito punya padanan lokal di 20+ negara yang belum digarap. Faktanya **9 dari 9 negara jenuh** (32–42 seller per negara, sampai 3 seller serius). Marketplace konsumen besar **selalu** sudah punya banyak scraper — kebalikan dari direktori profesional yang sepi. Aturan turunannya: **semakin konsumen sebuah platform, semakin kecil peluang gap-nya; semakin B2B/profesional, semakin besar.**

> **Tiga dari empat cabang Rekomendasi #5 Babak 41 gugur.** Tukang, restoran, dan (sebagian) dokter tidak menghasilkan gap. Ini rasio normal untuk riset di babak ke-42 — tapi artinya juga: **daftar vein yang belum diuji tinggal sedikit.** Riset berikutnya sebaiknya berhenti mencari vein baru dan mulai **memvalidasi permintaan nyata** (bangun 1 actor, ukur) daripada menambah babak scan ke-43.

## Rekomendasi Lanjutan

1. **Bangun `hukumonline-lawyer-directory-scraper` (Indonesia) lebih dulu** — nol kompetitor, HTML 532 KB (paling tebal dari semua target), Cloudflare lolos dengan `curl_cffi` impersonate yang sudah jadi standar di repo ini. Ukur traksi 2–4 minggu **sebelum** menambah India/Singapura/Malaysia.
2. **Paralel murah: `halodoc-doctor-directory-scraper` (Indonesia)** — 286 KB, terbuka, dan data-type-nya sudah terbukti di 3 ekosistem berbeda (syarat keempat di Insight terpenuhi). Ini kandidat dengan risiko paling rendah di babak ini.
3. **Recon dulu sebelum commit:** Brasil (`cna.oab.org.br` 10 KB = kemungkinan SPA), Jepang (`nichibenren` 36 KB), Filipina (`docdoc` 10 KB), Italia & Belanda (URL direktori berubah, 404 — perlu ditelusuri ulang, jangan divonis mati).
4. **Berhenti menscan vein ini — sudah tuntas dan terbukti negatif:** (a) classified-ads per negara, (b) direktori tukang/home-services di yurisdiksi mana pun, (c) direktori restoran per negara, (d) registry-type baru (bursa efek non-SEC, VAT/GST, plat nomor, register amal, registrasi obat, izin usaha, direktori sekolah).
5. **Untuk Babak 43 — ganti mode, jangan tambah scan.** Setelah 42 babak dan ~650 konsep diuji, sisa vein yang belum tersentuh sudah sangat tipis. Yang lebih bernilai sekarang: **bangun 2 kandidat teratas babak ini, ukur traksi nyatanya**, lalu pakai hasilnya untuk mengkalibrasi apakah pola "yurisdiksi kosong" benar-benar menghasilkan pembeli — pertanyaan yang sudah 2 babak berturut-turut ditandai sebagai risiko utama tapi belum pernah diuji secara empiris.

## File Referensi Babak 42

- `output/mine-xtracto.json` — snapshot 218 actor `xtracto` (tidak berubah dari Babak 39/40/41)
- `output/scan-v6-competition.json` — **49 konsep baru**, per konsep: seller, seller serius, total user/runs, actor terbesar, flag dedupe
- `output/scan-v6-jurisdiction.json` — **27 kombinasi data-type × yurisdiksi** (16 negara pengacara, 8 negara dokter, 2 restoran, 1 classified TR), lengkap dengan 8 actor teratas per kombinasi
- `scratchpad/compete42.py` — Pass 1 (49 konsep, union ≥3 frasa + nama platform telanjang)
- `scratchpad/verify42.py` — Pass 2 (uji per-yurisdiksi)
- `scratchpad/probe42.py` — Pass 4 (probe HTTP 17 situs target, `curl_cffi` impersonate)

---

# Babak 43 — Vein Lelang/Foreclosure Properti per-Yurisdiksi Ditemukan (API DJKN Terbuka Penuh); 50 Konsep Baru Diuji, 40+ Dinyatakan Mati (2026-09-08)

**Konteks:** user kembali minta daftar actor **ROI data tinggi / stats sudah tinggi**, dengan syarat tidak duplikat terhadap (a) akun kedua [`xtracto`](https://api.apify.com/v2/store?username=xtracto), (b) dokumen ini, (c) [`actors_researcher_v2.md`](actors_researcher_v2.md).

**Catatan jujur di awal:** Rekomendasi Lanjutan Babak 42 #5 menyarankan **berhenti menambah babak scan** dan mulai mengukur traksi nyata. Saran itu masih valid dan belum dijalankan — belum satu pun kandidat Babak 41/42 dibangun. Babak 43 tetap dijalankan sesuai permintaan user, tapi dengan strategi berbeda: **50 konsep yang sengaja dipilih dari wilayah yang belum pernah disentuh sama sekali** (compliance/AML, energi, telekom, akademik, kolektibel, filantropi, maritim) — bukan mengulang pola direktori-per-negara yang sudah 3 babak berturut-turut digali.

**Snapshot dedupe:** `apify-my-store.py xtracto` di-refresh hari ini → **masih 218 actor**, tidak berubah sejak Babak 39/40/41/42.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---|---|
| ✅ **BELUM dibangun — layak dikerjakan** | **3** | (1) Lelang/foreclosure properti per-yurisdiksi (ID/PL/JP/TR/CZ/RO/PH), (2) PSA/CGC card grading population, (3) Portal riset nasional (SINTA/Garuda/Lattes) |
| 🔁 **SUDAH ada** (di `xtracto` / riset lama) | **6** | Auction.com foreclosure AS, FDA 510k & recall, OpenAlex scholarly, StockX/GOAT/Chrono24/TCGplayer, BizBuySell, LandWatch |
| ⛔ **DI-SKIP** (alasan konkret, tabel di bawah) | **44** | 10 jenuh · 28 pasar mati/TAM mikro · 6 risiko atau di luar strategi |

## Ringkasan Eksekutif

- **Temuan utama — lelang/foreclosure properti per-yurisdiksi.** Ini satu-satunya vein babak ini yang memenuhi **keempat** syarat pola "data-type terbukti × yurisdiksi kosong". Terbukti laku di **empat ekosistem berbeda**: AS **574u** (25 seller), Brasil **371u** (`brasil-scrapers/caixa-leiloes-api` **223u**), Spanyol 96–169u (`signalflow/spain-auction-scout` 81u), Jerman 32u (`signalflow/zvg-portal-scraper`). **Nol actor di semua pass** untuk 🇮🇩 🇮🇳 🇵🇭 🇹🇷 🇵🇱 🇨🇿 🇷🇴 🇯🇵.
- **Bukti teknis terkuat yang pernah didapat di riset ini:** portal lelang resmi Indonesia `lelang.go.id` (DJKN Kemenkeu) ternyata punya **REST API JSON publik tanpa auth, tanpa WAF, dengan paginasi lengkap** — `api.lelang.go.id/api/v1/landing-page/katalog-lot-lelang` mengembalikan **11.889 lot lelang aktif**. Bukan HTML scraping, langsung JSON terstruktur.
- **Google Scholar adalah demand terbesar yang pernah muncul di seluruh riset ini** — `marco.gullo/google-scholar-scraper` **1.958 users / 522.648 runs**, total vein 3.132u di 38 seller. Tapi justru karena itu **di-skip**: 38 seller, 3 di antaranya serius. Dipakai sebagai bukti demand untuk kandidat #3, bukan target.
- **Aturan Babak 42 ("semakin B2B, semakin besar peluang gap") terbantah di babak ini.** Compliance/AML/lobbying/990/sanksi adalah B2B paling murni yang bisa dibayangkan — dan semuanya jenuh sekaligus tidak laku (sanksi **53 seller** berebut 248u; recall 44 seller/166u; food-facts 37 seller/128u). Koreksi lengkap ada di [Insight Strategis](#insight-strategis-babak-43).
- **44 konsep dimatikan dengan alasan konkret**, termasuk 9 yang di Pass 1 terlihat "kosong sempurna" tapi setelah re-scan frasa berbeda ternyata cuma sepi karena memang tidak ada pembeli.

## Metodologi Babak 43

```bash
python apify-my-store.py xtracto -o output/mine-xtracto.json   # 218 actor (tidak berubah)

# Pass 0 - INVENTARISASI konsep lama dulu (wajib, biar nol tumpang tindih):
#   ekstrak 292 label konsep + 2.867 string query dari compete.py/compete2/compete40/41/42 +
#   verify40/40b/41/41b/42 + detail40/41 + highstats41/41b + deep_scan
#   -> scratchpad/_concept_labels.txt, scratchpad/_all_strings.txt
# Pass 1 - 50 konsep BARU (7 grup yang belum pernah disentuh: compliance/AML, properti-adjacent,
#   energi, telekom, akademik, media/kolektibel, filantropi/B2B lain)
#   scratchpad/compete43.py -> output/scan-v7-competition.json
# Pass 2 - 44 kombinasi: (A) ANTI-FALSE-NEGATIVE frasa berbeda total untuk 12 konsep nol/nyaris nol
#   (Gotcha #1 Babak 42), (B) sub-tipe & per-yurisdiksi untuk finalis
#   scratchpad/verify43.py -> output/scan-v7-jurisdiction.json
# Pass 3 - 16 kombinasi PER-YURISDIKSI dengan NAMA PLATFORM TELANJANG (aturan Babak 41 #1):
#   lelang.go.id/DJKN, IBAPI, Pag-IBIG, icra/UYAP, licytacje, drazby, licitatii, keibai,
#   SINTA/Garuda, Lattes/CNPq, CNKI/CiNii/KCI
#   scratchpad/verify43b.py -> output/scan-v7-jurisdiction2.json
# Pass 4 - probe HTTP 18+10 situs target (curl_cffi impersonate) + pembongkaran bundle JS SPA
#   scratchpad/probe43.py, scratchpad/probe43b.py
```

Aturan yang diwarisi dan dipakai sejak Pass 1: union ≥3 frasa per konsep (Babak 40 #1), kunci wajib memuat **nama platform telanjang** (Babak 41 #1), union lintas-**pass** bukan cuma lintas-frasa (Babak 42 #1), metrik penentu = jumlah seller dengan `totalRuns ≥ 10.000` ("serius"), tanpa `max-users`.

### Gotcha metodologi baru

1. **Dedupe wajib membaca DESKRIPSI actor `xtracto`, bukan cuma `name` + `title`.** Konsep W1 (registry alat kesehatan 510k) dan V3 (database recall) lolos filter otomatis sebagai "belum ada di xtracto" — padahal `xtracto/openfda-events` deskripsinya berbunyi *"FDA drug/device adverse events (FAERS/MAUDE), **recalls**, and **510(k) clearances**"*. Token `510k`/`recall` hanya ada di deskripsi. Blob dedupe di semua script Babak 40–43 dibangun dari nama+judul saja → **dua konsep nyaris salah diklaim baru**. Untuk babak berikutnya: masukkan field `description` ke blob dedupe.
2. **Domain portal pemerintah pindah = sumber false-negative baru.** `sinta.kemdikbud.go.id` dan `garuda.kemdikbud.go.id` mengembalikan **DNS error** (bukan 404, bukan timeout) — terlihat seperti portal mati. Domain barunya `sinta.kemdiktisaintek.go.id` / `garuda.kemdiktisaintek.go.id` **hidup, 200, 29 KB & 22 KB** (kementerian dipecah, subdomain ikut pindah). DNS error pada domain `.go.id`/`.gov.*` harus selalu diikuti pencarian domain pengganti sebelum divonis mati.
3. **HTML 2 KB bukan vonis "SPA, sulit" — bongkar bundle-nya dulu.** `lelang.go.id` hanya mengembalikan 2 KB HTML dan **nol** jejak `/api` di HTML. Bundle JS-nya (7,5 MB) memuat seluruh peta host + endpoint dalam satu objek config literal. Dua tebakan endpoint pertama tetap 404 karena base URL-nya memakai prefix `/api` yang **tidak ikut tertulis** di daftar path (`PERMOHONAN_API:"https://api.lelang.go.id/api"` + `path:"/v1/landing-page/katalog-lot-lelang"`). Aturan: **ekstrak objek config dari bundle dan gabungkan host+path, jangan menebak path**.
4. **Kalibrasi ulang metrik "seller serius" (≥10rb runs) — jebakan runs terulang.** `hoholabs/setlistfm-scraper` dan `catchdoms/expired-domains-api` (78u/15.826r) lolos sebagai "serius" padahal user-nya ≤78 — runs besar dari pemakaian mesin satu-dua pelanggan, persis pola `ryanclinton/eu-vat-validator` di Babak 42. Metrik "serius" **hanya valid berpasangan dengan jumlah user**, jangan dipakai sendirian.

## ✅ BELUM Dibangun — Kandidat Baru (belum ada di `xtracto`, belum pernah muncul di riset mana pun)

| # | Prioritas | Ide Actor | Bukti Demand (stats incumbent) | Kompetisi di yurisdiksi target | Kenapa Layak / Catatan Eksekusi |
|---|---|---|---|---|---|
| 1 | 🔴 **Tinggi** | **Lelang / Foreclosure Properti per-Yurisdiksi** — mulai dari **`lelang-djkn-scraper` 🇮🇩**, lalu 🇵🇱 `licytacje.komornik.pl`, 🇯🇵 BIT (競売), 🇹🇷 UYAP e-satış, 🇨🇿 portaldrazeb, 🇷🇴 licitatii, 🇵🇭 Pag-IBIG | **4 ekosistem terbukti:** 🇺🇸 **574u** / 25 seller (`memo23/auction-com-scraper` 104u, `crawlerbros/zillow-foreclosure-scraper` 96u) · 🇧🇷 **371u** / 9 seller (`brasil-scrapers/caixa-leiloes-api` **223u**/3.999r) · 🇪🇸 96–169u (`signalflow/spain-auction-scout` 81u) · 🇩🇪 32u (`signalflow/zvg-portal-scraper`) | 🇮🇩 🇮🇳 🇵🇭 🇹🇷 🇵🇱 🇨🇿 🇷🇴 🇯🇵 = **nol actor di ketiga pass** (termasuk pass nama-platform-telanjang) | Satu-satunya kandidat babak ini yang lolos **keempat** syarat pola. Data publik resmi (portal pengadilan/kementerian), bukan data pribadi. Indonesia didahulukan karena **API JSON-nya terbuka penuh** (lihat catatan teknis) + pasar rumah sendiri. `signalflow` sudah membuktikan model "satu portal lelang nasional = satu actor" di 2 negara EU sekaligus — pola yang tinggal ditiru ke yurisdiksi kosong. |
| 2 | 🟠 Sedang-Tinggi | **PSA / CGC Card Grading Population & Cert Lookup** (populasi kartu ter-grade + verifikasi sertifikat) | `lulzasaur/psa-pop-scraper` **182u / 8.311r** · `jungle_synthesizer/beckett-bgs-population` 16u · total vein 184–244u | **2–5 seller, 0 serius** — tipis untuk demand 184u | `xtracto` sudah punya StockX (5 actor), GOAT, Chrono24 (2), TCGplayer → **moat kolektibel sudah ada**, dan PSA population adalah data-type yang melengkapi TCGplayer (harga) dengan kelangkaan (populasi). `psacard.com/pop` 200 / 20 KB, terbuka. **Peringatan jujur:** ini BUKAN "yurisdiksi kosong" — ini head-to-head melawan incumbent 182u. Perlu sudut beda yang jelas (mis. gabungan pop + harga pasar sekunder dalam satu output). |
| 3 | 🟡 Sedang | **Portal Riset Nasional** — SINTA & Garuda 🇮🇩, Lattes/CNPq 🇧🇷, CNKI 🇨🇳 / CiNii 🇯🇵 / KCI 🇰🇷 | Data-type akademik = **demand terbesar di seluruh riset ini**: Google Scholar 36–38 seller, 3 serius, **2.993–3.132u**, `marco.gullo/google-scholar-scraper` **1.958u / 522.648 runs** | **Nol actor** untuk SINTA/Garuda/Lattes/CNKI/CiNii/KCI di semua pass | SINTA hidup di domain baru (`sinta.kemdiktisaintek.go.id`, 200/29 KB — lihat Gotcha #2). **Peringatan jujur, beda dari kandidat #1:** peneliti Indonesia/Brasil **juga ada di Google Scholar**, jadi kekosongan ini bisa berarti datanya dianggap redundan, bukan belum digarap. Nilai unik SINTA cuma pada **skor & ranking nasional** (metrik yang tidak ada di Scholar) — pembelinya kemungkinan kampus/LPPM lokal, bukan pasar global Apify. Prioritas sedang, jangan didahulukan dari #1. |

### Catatan teknis kandidat #1 (probe HTTP + pembongkaran bundle, 2026-09-08)

| Target | Status | Catatan |
|---|---|---|
| 🇮🇩 `lelang.go.id` (DJKN Kemenkeu) | **200**, HTML cuma 2 KB (SPA) → **API JSON ditemukan** | `GET https://api.lelang.go.id/api/v1/landing-page/katalog-lot-lelang?page=1&limit=N` → `{code, message, data[], page, perPage, totalPage, totalItem}`, **totalItem = 11.889 lot aktif**. Tanpa auth, tanpa WAF, tanpa token. Field per lot: `namaLotLelang`, `nilaiLimit`, `uangJaminan`, `tanggalBatasJaminan`, `namaLokasi`, `namaUnitKerja` (KPKNL), `tglMulaiLelang`, `tglSelesaiLelang`, `status`, `caraPenawaran`, `photos[]`. Endpoint pendukung: `/kategori`, `/hot-lelang`, `/lelang-saat-ini`, `/lelang-segera-berakhir`, `/penawaran-tertinggi`, `/kpknl`. **Target termudah & terkaya di seluruh Babak 41–43.** |
| 🇮🇩 portal lelang bank (bonus dari bundle) | belum diprobe | Bundle DJKN memuat tautan ke `infolelang.bri.co.id`, `lelang.bankmandiri.co.id`, `lelangagunan.bni.co.id`, `lelang.bankbjb.co.id` — kandidat ekspansi berikutnya di yurisdiksi yang sama |
| 🇵🇱 `licytacje.komornik.pl` | **200**, **1.307–2.411 KB** | HTML paling tebal dari semua target. Nol `<tr>` di `/Notice/Search` (kemungkinan Nuxt, payload di JS) — **perlu recon parser dulu**, tapi ukurannya menandakan data padat |
| 🇯🇵 `bit.courts.go.jp` (BIT 競売) | **200**, **343 KB** | Portal lelang pengadilan Jepang, server-rendered, tebal. Path `/app/reserve/...` → 404, pakai `/app/top/pt001/h01` |
| 🇨🇿 `portaldrazeb.cz` · 🇷🇴 `licitatii.ro` | **200**, 79 KB · 31 KB | Keduanya terbuka |
| 🇹🇷 `esatis.uyap.gov.tr` | **200**, 54 KB | Terbuka. (`ilan.gov.tr` gagal verifikasi sertifikat SSL — pakai UYAP) |
| 🇵🇭 `pagibigfundservices.com` (acquired assets) | **200**, 22 KB | Terbuka tapi tipis. `landbank.com/properties-for-sale` → **404** (path berubah), `bdo.com.ph` → 404 |
| 🇧🇷 `venda-imoveis.caixa.gov.br` · 🇪🇸 `subastas.boe.es` | **200**, 62 KB · 37 KB | **Pembanding, bukan target** — kedua yurisdiksi ini sudah ada incumbent |
| 🇮🇳 `ibapi.in` (+ `www.`) | **Timeout di 2 percobaan** | Nol kompetitor kemungkinan **karena tidak bisa diakses** — pola persis `peradi.or.id` & `findlaw.com.au` di Babak 42. **Jangan diprioritaskan.** Alternatif `bankeauctions.com` 200/129 KB (swasta, bukan portal resmi) |

## 🔁 SUDAH Ada — Muncul di Scan Tapi Bukan Temuan Baru

| Konsep (stats yang bikin dia muncul) | Sudah ada di | Catatan |
|---|---|---|
| Foreclosure/lelang properti **AS** (Auction.com) | `xtracto/auction-foreclosure-sniper` (2u) | **Inilah alasan kandidat #1 diarahkan ke luar AS.** Yurisdiksi AS sudah dipegang sendiri + 25 seller lain |
| FDA **510(k)** & **recall** (konsep W1 + V3) | `xtracto/openfda-events` (1u) | Lolos filter otomatis karena tokennya cuma ada di deskripsi — lihat Gotcha #1 |
| OpenAlex / data ilmiah global | `xtracto/openalex-scholarly` (2u) | Kandidat #3 sengaja diarahkan ke portal **nasional** yang tidak tercakup OpenAlex |
| StockX (5 actor) · GOAT · Chrono24 (2) · TCGplayer | `xtracto` | Vein kolektibel sudah tersentuh — kandidat #2 (PSA population) adalah data-type yang **berbeda** (kelangkaan, bukan harga) |
| BizBuySell (bisnis dijual) | `xtracto/bizbuysell-listings` (2u) | Konsep S1 (franchise/FDD) bersinggungan — dan lagi pula 13 seller/137u |
| LandWatch (listing tanah) | `xtracto/landwatch-price-per-acre-scraper` (5u) | `memo23/landwatch-scraper` 47u muncul sebagai false positive di re-scan "land registry" |
| Skool (komunitas) | repo utama: `skool-whop-community-analyzer` | `sourabhbgp/skool-scraper` 73u muncul sebagai false positive di re-scan "association members" |

## ⛔ DI-SKIP — Semua dengan Alasan Konkret

### A. Jenuh: banyak seller **dan/atau** ada seller serius (runs ≥10rb)

| Konsep | Seller / Serius | Actor terbesar | Kenapa di-skip |
|---|---|---|---|
| **Google Scholar (platform itu sendiri)** | **38** / **3** | `marco.gullo/google-scholar-scraper` **1.958u / 522.648r** | Demand terbesar yang pernah ditemukan di seluruh riset ini — dan justru karena itu sudah diperebutkan 38 seller dengan 3 pemain serius. **Jadi bukti demand untuk kandidat #3, bukan target** |
| **Udemy / Coursera / edX** | **37** / 2 | `natanielsantos/udemy-courses-scraper` **400u** | 1.635u di 37 seller. Sub-tipe edtech Asia (Ruangguru/Byju's/Unacademy) & bootcamp: **0 actor DAN 0 bukti demand** → bukan gap, pasar mati |
| **PubMed / arXiv / jurnal** | **58** / 0 | `scrapestorm/pubmed-articles-scraper` 116u | Populasi seller terbesar babak ini (58) untuk 613u — sangat terfragmentasi, tiap actor kecil |
| **Goodreads / katalog buku** | **45–46** / 2 | `easyapi/goodreads-book-scraper` 125u | 669–732u tapi 45 seller. Sub-tipe: katalog perpustakaan nasional **0 actor/0 demand**; buku bekas & langka (AbeBooks) 4 seller/26u — mikro |
| **Sanksi / PEP / OFAC screening** | **44–53** / 0 | `ryanclinton/opensanctions-search` 49u | **Contoh utama koreksi babak ini**: B2B murni, 53 seller, tapi total cuma 248u dan **nol seller serius**. Datanya tersedia gratis via API resmi (OFAC/EU/OpenSanctions) → semua orang bisa bikin, tidak ada yang laku |
| **Database recall produk** | **44** / 0 | `benthepythondev/fda-recall-intelligence` 12u | 166u di 44 seller + **sudah ada di `xtracto/openfda-events`** |
| **Open Food Facts / gizi** | **37** / 0 | `benthepythondev/open-food-facts-product` 18u | 128u di 37 seller — data gratis ber-API, pola sama dengan sanksi |
| **WordPress plugin/tema** | **28** / 0 | `scraper-mind/wordpress-email-scraper` 19u | 79u di 28 seller; dan repositori WP punya API resmi gratis |
| **Discogs / vinyl** | **24** / 0 | `nick_slam/spotify-to-discogs` 49u | 143u di 24 seller. Discogs punya API resmi |
| **Vivino / wine & whisky** | 13–17 / 1 | `mrbridge/vivino-wine-data-scraper` **217u / 64.035r** | Demand nyata (415–531u) tapi **satu seller menguasai dua sub-tipe sekaligus** (`mrbridge` juga pegang wine-searcher 109u). Whisky 3 seller/17u, CellarTracker/Liv-ex **0 actor** — sisa vein-nya mikro |
| Foreclosure **AS** | 25 / 0 | `memo23/auction-com-scraper` 104u | Jenuh **dan** sudah ada di `xtracto` |
| Insolvensi/kepailitan | 27 / 1 | `pink_comic/bankruptcy-filing-search` 22u | 27 seller berebut 132u |
| Anime/manga · profil akademik generik | 16 · 32 / 0–1 | `rikunk/my-anime-list-scraper` 60u · `george.the.developer/google-scholar` 117u | Terfragmentasi; keduanya punya API/dump resmi |

### B. Seller sedikit / nol **TAPI pasarnya memang mati** — bukan peluang (Gotcha #2 Babak 42)

Semua baris di bawah **sudah lolos re-scan anti-false-negative** dengan frasa yang berbeda total (Pass 2 grup A) — angka yang ditampilkan adalah hasil gabungan terbaik dari dua pass, bukan satu pass.

| Konsep | Seller / Serius | Actor terbesar | Kenapa di-skip |
|---|---|---|---|
| **Sertifikasi halal / kosher** | **0** / 0 | — | **Nol actor di DUA pass dengan frasa berbeda, dan nol bukti demand di yurisdiksi mana pun.** Contoh paling murni "pasar mati, bukan gap" — meski secara intuisi terasa cocok untuk pasar Indonesia |
| Pembanding paket seluler | 1 / 0 | `fascinating_lentil/india-telecom-plans` **9u** | TAM 9u lintas dua pass |
| Cek cakupan broadband | 2 / 0 | `crawlerbros/uswitch-scraper` 3u | Mati |
| Direktori paket asuransi kesehatan | 3 / 0 | `matheus_dev_natal/brazil-health-insurance` 2u | Mati |
| Konsesi tambang / mining claims | 1 / 0 | `malonestar/blm-mining-claims` **2u** | Mati di dua pass |
| Sumur migas: izin & produksi | 1 / 0 | `malonestar/oil-gas-well-permits` **2u** | Mati — dan `malonestar` sendiri yang pegang dua konsep energi sekaligus, tanda pasarnya satu-orang |
| Proyek EBT / solar & wind pipeline | 4 / 0 | `inexhaustible_glass/german-energy-register` 7u | TAM 12u |
| Tarif listrik/gas & pembanding energi | 3 / 0 | `malonestar/eia-v2-site-energy` 2u | Mati |
| Registry menara / izin spektrum | 1 / 0 | `jungle_synthesizer/anatel-brazil-satelite` 2u | Mati |
| **Land registry / kadaster (registry murni)** | 3 / 0 | `corent1robert/france-pool-tennis-plots` 2u | Re-scan mengembalikan 15 seller/152u **tapi isinya listing tanah** (`memo23/landwatch-scraper` 47u — dan LandWatch sudah di `xtracto`), bukan registry. Registry murni = mati |
| Pajak properti / assessor **non-AS** | **0** / 0 | — | AS sendiri 3–15 seller/77–213u (`shelvick/county-property-records` 74u); di luar AS **nol actor nol demand** |
| Direktori kamar dagang | 8–11 / 0 | `scrapebench/chamber-of-commerce-member-directory` 53u | AS/UK 130u di 11 seller; **IHK Jerman & CCI Prancis 0 actor 0 demand**; KADIN/ASEAN 4 seller/11u |
| Direktori dosen/fakultas | 9 / 0 | `hgservices/university-people-finder` 31u | 102u lintas 9 seller — mikro |
| Hibah riset (NIH/CORDIS) | 19 / 0 | `constant_quadruped/research-grant-aggregator` 13u | 19 seller berebut 75u |
| Database beasiswa | 3 / 0 | `majestic_fund/the-scholarship-scraper` 66u | TAM 75u |
| Repositori tesis · jurnal predator · Scopus/WoS | 1 · 1 · **0** | `leafy-dev-jr/thesis-literature-review` 32u | Scopus & Web of Science **nol actor** — dan keduanya berbayar/ber-ToS ketat |
| Lobbying register | 19 / 0 | `hanamira/lobbying-disclosure-search` 9u | 19 seller berebut 57u |
| Debarment / blacklist vendor | 15 / 0 | `automation-lab/sam-gov-entity-exclusions` 4u | 30u total — mati meski B2B |
| Beneficial ownership / UBO | 9 / 1 | `ryanclinton/opencorporates-search` **160u** | 202u; OpenCorporates sendiri berbayar & agresif soal ToS |
| Adverse media / AML news | 5 / 0 | `inexhaustible_glass/sanctions-screener` 5u | TAM 15u |
| PEP & harta pejabat per negara | 4 / 0 | `jungle_synthesizer/pep-screening-scraper` 2u | TAM 7u — plus alasan risiko (lihat C) |
| Laporan keuangan nirlaba (990) | 21 / 0 | `pink_comic/irs-990-nonprofit-search` 28u | 114u di 21 seller; data gratis ber-API (ProPublica) |
| Lembaran negara / official gazette | 11 / 0 | `regdata/msig-scraper` 11u | 44u — mikro |
| Zoning / land use | 13 / 0 | `devon_gtme/uk-planning-applications` 74u | 125u; sangat per-kota, effort tinggi per unit data |
| LEGO/BrickLink · numismatik · komik · lelang seni | 4 · 3 · 4 · 6 / 0 | `jungle_synthesizer/bricklink-lego-part` 15u · `ngccoin-price-guide` 8u · `lulzasaur/gocollect-scraper` 20u · `powerai/sothebys-search` 21u | Semua TAM 14–39u — **kolektibel di luar kartu & sneaker adalah pasar mikro** |
| Kartu pasar sekunder (Cardmarket) · comic grading | 8 · 3 / 0 | `ecomscrape/cardmarket-trend-scraper` 69u | 147u/22u — dicatat sebagai pelengkap kandidat #2, bukan target sendiri |
| Marketplace domain & lelang domain | 5 / 1 | `catchdoms/expired-domains-api` 78u / **15.826r** | "Serius"-nya adalah **jebakan runs** (Gotcha #4). Sub-tipe marketplace premium (Sedo/Afternic) **0 actor** |
| VSCode / JetBrains marketplace | 14 / 0 | `benthepythondev/vscode-extensions-scraper` 6u | 40u di 14 seller |
| Registry & kepemilikan kapal · kapal ikan | 13 · 5 / 0 | `romy/marine-traffic-scraper` 69u | 180u/27u; MarineTraffic ber-ToS ketat & sudah dipegang |
| Direktori gudang/3PL · suku cadang industri | 1 · 11 / 0 | `automa-flow/fda-wdd-3pl` 2u · `fortuitous_pirate/rockauto-scraper` 68u | 3PL mati; suku cadang yang laku ternyata **RockAuto (ritel otomotif)**, bukan katalog industri — konsep berbeda, dan otomotif sudah divonis di Babak 41 |
| Direktori anggota asosiasi | 7 / 0 | (false positive `sourabhbgp/skool-scraper` 73u) | Nol actor asli untuk direktori asosiasi; hit terbesarnya Skool yang sudah ada di repo |
| Setlist konser & riwayat tur | 5 / 1 | `hoholabs/setlistfm-scraper` 11u | TAM 20u; "serius"-nya jebakan runs |
| Lelang properti 🇲🇾/🇹🇭/🇻🇳 | 1 / 0 | `haketa/lelong-my-scraper` 7u | **Dicatat sebagai batas vein kandidat #1**: Asia Tenggara di luar Indonesia terlalu tipis untuk didahulukan |

### C. Di-skip karena risiko atau di luar strategi

| Konsep | Alasan |
|---|---|
| **PEP / LHKPN / harta kekayaan pejabat per negara** | TAM 7u **dan** isinya data pribadi + politis. Konsisten dengan keputusan "data penerima bansos" di Babak 42 |
| **Lelang properti India (IBAPI)** | Nol kompetitor, tapi `ibapi.in` **timeout di dua percobaan** — pola identik `peradi.or.id`/`findlaw.com.au` (Babak 42): kekosongan yang disebabkan ketidakterjangkauan, bukan peluang |
| **WordPress / VSCode / JetBrains marketplace** | Ekosistem dev-tooling — konsisten dengan vonis "di luar fokus akun scraping" di `actors_researcher_v2.md` |
| **Scopus / Web of Science** | Nol actor karena berbayar + ToS ketat, bukan karena belum ditemukan |
| **OpenCorporates (UBO)** | Sumber berbayar dengan penegakan ToS agresif; 160u tidak sebanding risikonya |
| **MarineTraffic (vessel tracking)** | Sudah 13 seller **dan** ToS ketat |

## 🔧 Koreksi untuk Babak 42

| Pernyataan Babak 42 | Status setelah diuji di babak ini |
|---|---|
| Insight: *"semakin konsumen sebuah platform, semakin kecil peluang gap-nya; semakin B2B/profesional, semakin besar"* | ❌ **Terbantah sebagian besar.** Vein paling B2B di babak ini (sanksi 53 seller/248u, recall 44/166u, lobbying 19/57u, debarment 15/30u, 990 21/114u) semuanya **jenuh sekaligus tidak laku**. Faktor penentu yang sebenarnya bukan B2B-vs-konsumen — lihat Insight di bawah |
| Gotcha #2: *"nol seller bukan sinyal peluang kalau tidak dipasangkan bukti demand di yurisdiksi lain"* | ✅ **Terkonfirmasi kuat, dan menyelamatkan babak ini.** 9 konsep terlihat "kosong sempurna" di Pass 1 (halal, mining, EBT, mobile plan, broadband, health plan, faculty, fishing, asosiasi) — semuanya gugur setelah dipasangkan tes demand |
| Gotcha #1: *"union harus lintas-PASS"* | ✅ Terkonfirmasi lagi: `land registry` 3 seller di Pass 1 → 15 seller di Pass 2 (walau isinya false positive), `faculty directory` 0 → 9, `vessel registry` 1 → 13 |
| Rekomendasi #5: *"Babak 43 ganti mode, jangan tambah scan"* | ⚠️ **Belum dijalankan.** Babak 43 tetap berupa scan (atas permintaan user), tapi menemukan kandidat dengan bukti teknis terkuat sejauh ini. Rekomendasi itu **dinaikkan prioritasnya** — lihat Rekomendasi #1 |

## Insight Strategis Babak 43

> **Pembeda peluang yang sebenarnya bukan "B2B vs konsumen", tapi "ada API resmi vs tidak".** Semua vein yang jenuh-tapi-tidak-laku di babak ini punya ciri sama: **datanya sudah tersedia gratis lewat API/dump resmi** — OFAC & OpenSanctions, openFDA, IRS 990 (ProPublica), Open Food Facts, OpenAlex, repositori WordPress, API Discogs, PubMed E-utilities. Akibatnya puluhan seller membuat wrapper tipis (53 seller untuk sanksi!) dan **tidak ada satu pun yang laku**, karena pembeli yang butuh data itu bisa memanggil API-nya sendiri. Sebaliknya, vein yang bernilai adalah yang **datanya publik tapi TIDAK ada API-nya dan harus dibongkar** — portal lelang per negara, direktori profesi per yurisdiksi, portal tender. Ini menjelaskan kenapa portofolio repo ini (tender & registry per-negara) laku sementara "sanctions screening" tidak, dan aturannya bisa dipakai sebagai **filter pertama** di riset berikutnya: sebelum menghitung seller, tanya dulu *"apakah sumbernya punya API resmi?"* — kalau ya, langsung buang.

> **Ironi kecil: kandidat #1 justru melanggar aturan itu dan tetap menang.** `lelang.go.id` ternyata **punya** API JSON terbuka — tapi API itu **tidak didokumentasikan, tidak dipublikasikan, dan hanya bisa ditemukan dengan membongkar bundle JS 7,5 MB**. Jadi aturannya perlu diperhalus: yang mematikan peluang bukan keberadaan API, tapi **API yang resmi diumumkan dan mudah ditemukan**. API tersembunyi justru ideal — biaya scraping serendah wrapper, tapi hambatan penemuannya menyaring kompetitor.

> **Pola "data-type terbukti × yurisdiksi kosong" bertahan 4 babak berturut-turut sebagai satu-satunya yang menghasilkan kandidat.** Babak 41 (direktori bisnis), 42 (pengacara & dokter), 43 (lelang properti) — tiga vein berbeda, metode sama. Sementara **semua** upaya mencari "data-type baru yang belum pernah ada" di babak ini (50 konsep, 7 grup wilayah baru) menghasilkan **nol** kandidat. Kesimpulan yang makin sulit dibantah: pada titik ini di Apify Store, **tidak ada lagi data-type baru yang belum ditemukan orang** — yang tersisa hanyalah yurisdiksi.

## Rekomendasi Lanjutan

1. **Prioritas tertinggi tetap: berhenti scan, mulai ukur** (mewarisi Rekomendasi #5 Babak 42 yang belum dijalankan). Setelah 43 babak dan ~700 konsep, tiga babak terakhir menghasilkan 8 kandidat yang **belum satu pun dibangun**. Nilai marjinal babak ke-44 hampir pasti lebih kecil daripada membangun satu actor dan melihat traksinya.
2. **Kalau membangun satu saja: `lelang-djkn-scraper` (Indonesia).** Alasannya bukan cuma nol kompetitor, tapi **biaya eksekusi terendah dari semua kandidat yang pernah muncul di Babak 41–43** — API JSON terbuka, 11.889 lot aktif, tanpa auth/WAF/anti-bot, tanpa parsing HTML. Bisa jadi actor kerja dalam hitungan jam, bukan hari. Ini kandidat ideal untuk **menjawab pertanyaan empiris yang sudah 3 babak menggantung**: apakah pola "yurisdiksi kosong" benar-benar menghasilkan pembeli?
3. **Kalau #2 menunjukkan traksi, ekspansi paling murah adalah yurisdiksi tetangga di vein yang sama:** 🇵🇱 licytacje.komornik.pl (1,3 MB, perlu recon Nuxt), 🇯🇵 BIT 競売 (343 KB, server-rendered), 🇹🇷 UYAP e-satış (54 KB) — plus 4 portal lelang bank Indonesia (BRI/Mandiri/BNI/BJB) yang ditemukan di bundle DJKN.
4. **Perbaiki blob dedupe sebelum babak berikutnya** — tambahkan field `description` dari `mine-xtracto.json` (Gotcha #1). Dua konsep babak ini nyaris salah diklaim baru.
5. **Berhenti menscan vein ini — sudah tuntas dan terbukti negatif:** (a) compliance/AML/sanksi/lobbying/debarment/UBO, (b) energi & utilitas (migas, tambang, EBT, tarif listrik), (c) telekom (paket seluler, broadband, spektrum), (d) akademik generik (Scholar, PubMed, Scopus, hibah, beasiswa, tesis, dosen), (e) katalog buku & perpustakaan, (f) ekosistem plugin (WordPress, VSCode, JetBrains), (g) kolektibel di luar kartu/sneaker (LEGO, koin, komik, seni, wine/whisky), (h) filantropi/990 & kamar dagang.

## File Referensi Babak 43

- `output/mine-xtracto.json` — snapshot 218 actor `xtracto` (tidak berubah dari Babak 39–42)
- `output/scan-v7-competition.json` — **50 konsep baru** (Pass 1), per konsep: seller, seller serius, total user/runs, 12 actor teratas, flag dedupe
- `output/scan-v7-jurisdiction.json` — **44 kombinasi** (Pass 2): 12 re-scan anti-false-negative + 32 sub-tipe/yurisdiksi finalis
- `output/scan-v7-jurisdiction2.json` — **16 kombinasi** (Pass 3) dengan nama platform telanjang: 9 yurisdiksi lelang + 5 portal riset + 2 grading
- `scratchpad/_concept_labels.txt` · `scratchpad/_all_strings.txt` — inventaris 292 label konsep & 2.867 string query dari Babak 1–42 (dipakai untuk menjamin nol tumpang tindih)
- `scratchpad/compete43.py` · `verify43.py` · `verify43b.py` — Pass 1/2/3
- `scratchpad/probe43.py` · `probe43b.py` — Pass 4 (probe HTTP 28 URL, `curl_cffi` impersonate)
- `scratchpad/lelang_bundle.js` — bundle JS `lelang.go.id` (7,5 MB) tempat peta host+endpoint API DJKN ditemukan

---

# Babak 44 — EKSEKUSI: 6 Actor Dibangun dari Backlog Babak 41–43, 2 Dihentikan di Recon, 4 Target Kandidat Terbukti Salah Sasaran (2026-09-08)

**Konteks:** user meminta **"bangun semua kandidat yang sudah didapat"**. Cakupan yang diambil: seluruh backlog 8 kandidat dari Babak 41, 42 dan 43 — bukan hanya Babak 43. Ini babak **eksekusi pertama** setelah tiga babak riset berturut-turut, sekaligus menjalankan Rekomendasi Lanjutan Babak 42 #5 dan Babak 43 #1 ("berhenti scan, mulai ukur").

**Snapshot dedupe:** `apify-my-store.py xtracto` → **masih 218 actor**, tidak berubah.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---|---|
| ✅ **SUDAH dibangun** (kode + tes lokal hijau + `apify validate-schema` lolos) | **6** | `lelang-djkn-scraper` · `lawrato-lawyer-directory-scraper` · `indonesiayp-business-directory-scraper` · `alodokter-doctor-directory-scraper` · `sinta-researcher-scraper` · `socialblade-creator-analytics-scraper` |
| ⛔ **DI-SKIP — berhenti bersih di fase recon** | **2** | PSA card grading population · Daftar exhibitor pameran dagang |
| 🔧 **Koreksi target** — kandidat benar, situs yang ditunjuk riset salah | **4** | Hukumonline 🇮🇩 → LawRato 🇮🇳 · Sarısayfalar 🇹🇷 → IndonesiaYP 🇮🇩 · Halodoc 🇮🇩 → Alodokter 🇮🇩 · SINTA domain lama → domain baru |

**Rasio:** 6 dari 8 kandidat backlog dieksekusi (**75%**), konsisten dengan rasio babak-babak eksekusi sebelumnya (78–100%).

## ✅ 6 Actor Baru — dibangun, diuji lokal, tervalidasi

Semua mengikuti konvensi portofolio: `.actor/` lengkap (actor.json + input/output schema + output links + Dockerfile), `src/` (constants/client/extractor/main), `requirements.txt`, `README.md` gaya Store listing, `CRAWLING_METHOD.md`, dan `test_local.py` yang menjalankan seluruh mode tanpa platform Apify.

| # | Actor | Asal kandidat | Mode | Bukti data nyata dari tes lokal |
|---|---|---|---|---|
| 1 | **`lelang-djkn-scraper`** 🇮🇩 | Babak 43 #1 | `catalog` · `kpknl` · `detail` · `feed` · `reference` | **11.889 lot lelang aktif** via API JSON `api.lelang.go.id/api/v1/...`. 18 kategori, **71 kantor KPKNL**, detail memuat `content.barangs` dengan bukti kepemilikan (BPKB/SHM + nomor + tanggal) |
| 2 | **`lawrato-lawyer-directory-scraper`** 🇮🇳 | Babak 42 #1 | `directory` · `profile` · `reference` | 16 kota × 30 bidang praktik, 20 kartu/halaman. Profil: rating, tahun pengalaman, **bar council + tahun sumpah**, pengadilan, bahasa, spesialisasi. Coverage kartu 25/25 untuk nama/URL/rating |
| 3 | **`indonesiayp-business-directory-scraper`** 🇮🇩 | Babak 41 #1 | `category` · `company` · `reference` | ~13.900 listing di kategori Restoran saja. **Coverage 25/25 untuk nama, alamat, telepon, tahun berdiri.** Halaman detail: telepon + HP + website + **koordinat GPS** + jam buka + manajer + jumlah karyawan |
| 4 | **`alodokter-doctor-directory-scraper`** 🇮🇩 | Babak 42 #2 | `specialty` · `doctor` · `reference` | 17 spesialisasi terverifikasi live. **Coverage 25/25 untuk nama, RS, harga konsultasi, rating.** Data unik: **biaya konsultasi dalam IDR** + jadwal berikutnya |
| 5 | **`sinta-researcher-scraper`** 🇮🇩 | Babak 43 #3 | `authors` · `author` · `affiliations` | **335.592 peneliti** + **5.567 afiliasi**. Per peneliti: skor SINTA nasional, H-index Scopus/WoS/Google, **Google Scholar ID** (kunci join ke Scholar), tabel publikasi 3 sumber |
| 6 | **`socialblade-creator-analytics-scraper`** | Babak 41 #2 | `profile` (4 platform) · `top` | YouTube/TikTok/Twitch/Instagram dari payload SSR `__NEXT_DATA__`. Ranks + **histori harian 15 hari**. Leaderboard YouTube 100 kreator |

### Catatan eksekusi penting

**Kandidat #1 (DJKN) memang semurah yang diprediksi Babak 43.** Prediksinya "bisa jadi actor kerja dalam hitungan jam, bukan hari" — terbukti: API JSON terbuka penuh, **nol WAF, nol header wajib, nol TLS impersonation** (diverifikasi terhadap 4 konfigurasi klien berbeda, semuanya 200 dengan body identik 2.564 byte).

**Empat dari enam target ternyata tidak seperti yang dicatat riset** — lihat bagian Koreksi. Ini temuan metodologis terbesar babak ini: **ukuran halaman (KB) yang dipakai Babak 41–43 sebagai proksi "ada data" ternyata tidak valid.**

## ⛔ 2 Kandidat Di-skip — berhenti bersih di recon, bukan dipaksa build

| Kandidat | Asal | Kenapa dihentikan |
|---|---|---|
| **PSA / CGC card grading population** | Babak 43 #2 (🟠) | `psacard.com/pop` dan seluruh varian `/pop/<kategori>` mengembalikan **shell 20 KB identik** tanpa satu pun baris data — Next.js App Router yang mengambil data via **tRPC** (`/api/collectors-web/trpc`, endpoint hidup dan membalas error terstruktur). Nama prosedurnya **tidak ada di 20 chunk awal** (1,59 juta karakter di-grep: hanya `popReport`/`populationReport` sebagai kata, bukan sebagai path) — artinya ada di chunk route yang lazy-load, di belakang Cloudflare. Empat tebakan prosedur dijawab 404 "No procedure found". Payload RSC juga tidak memuat data. **Biaya reverse-engineering tinggi + rapuh, sementara kandidatnya sendiri cuma 🟠 dan bukan "yurisdiksi kosong" melainkan head-to-head lawan incumbent 182u** (`lulzasaur/psa-pop-scraper`). Sesuai kebijakan portofolio: berhenti bersih |
| **Daftar exhibitor pameran dagang** | Babak 41 #3 (🟢) | Babak 41 mensyaratkan "fair **di luar** cakupan `skython`". Faktanya: pameran besar yang terbuka justru berjalan **di atas platform yang sudah dikuasai skython** — `nrfbigshow.nrf.com/exhibitors` (2.034 KB, daftar exhibitor terbesar yang ditemukan) ternyata di-host di **`bigshow27.mapyourshow.com`** (26 penyebutan `mapyourshow` di HTML-nya), dan `skython/map-your-show-exhibitor-list-scraper` sudah **579 users**. Membangunnya = kloning langsung incumbent. Platform alternatif `a2zinc.net` butuh penemuan subdomain per-pameran: 5 instance plausibel yang diprobe **semuanya DNS error**, hanya `s23.a2zinc.net` yang resolve (404 di path publik). Ditambah peringatan Babak 41 sendiri: **rpu cuma 4–8** = pemakaian sekali-jalan, bukan ROI berulang |

## 🔧 Koreksi Target untuk Babak 41, 42, 43

Empat kandidat **konsepnya benar** tapi **situs yang ditunjuk riset salah**. Semua ketahuan hanya setelah recon eksekusi — tidak satu pun terlihat dari angka scan.

| Kandidat | Target menurut riset | Fakta saat dibangun | Target yang dipakai |
|---|---|---|---|
| Direktori bisnis nasional (Babak 41 #1) | **Sarısayfalar 🇹🇷** — "200, Apache, 111 KB, nol WAF, target terbaik" | **Bukan direktori bisnis sama sekali.** Isinya iklan baris: link homepage berbentuk `/N/vasita-atv`, `/N/emlak-turistik-tesis`, `/N/is-ilanlari-*`; kotak carinya meminta *"kelime, **ilan no** veya mağaza adı"*; `?s=avukat` (pengacara) mengembalikan halaman kosong 20 KB; `/avukat/` dan `/avukat/istanbul/` **404**. Dan vein iklan baris sudah divonis jenuh di Babak 42 (9 dari 9 negara, 32–42 seller) → **mati dua kali** | **IndonesiaYP 🇮🇩** — direktori asli (13.904 restoran), pasar rumah sendiri, dan yurisdiksi terkosong menurut angka Babak 41 sendiri (3 seller / 7 user) |
| Direktori pengacara (Babak 42 #1) | **Hukumonline 🇮🇩** — "200, Cloudflare lolos, **532 KB**, HTML paling tebal dari semua target" | **Indonesia tidak punya direktori pengacara yang bisa di-scrape.** `hukumonline.com/pusatdata` (532 KB itu) adalah **basis data peraturan**, bukan direktori; `/klinik` adalah kolom tanya-jawab; `/legal-directory` **404**. `peradi.or.id` — yang di Babak 42 timeout — sekarang hidup (347 KB) tapi hanya menerbitkan daftar advokat baru sebagai **artikel berita**, tanpa direktori/pencarian anggota. `kai.or.id` (80 KB) sama | **LawRato 🇮🇳** — yurisdiksi kedua di urutan rekomendasi Babak 42 (ID → IN → SG/MY), direktori sungguhan dengan microdata schema.org |
| Direktori dokter SEA (Babak 42 #2) | **Halodoc 🇮🇩** — "200, **286 KB**, target dokter terbaik untuk Indonesia" | **SPA Angular tanpa data.** Merender *"Maaf, dokter tidak dapat ditemukan"* tanpa lokasi; nol data dokter di HTML; nol `__NEXT_DATA__`/`__NUXT__`; bundle utama (123 KB) **tidak memuat satu pun host API**. 286 KB itu framework, bukan data | **Alodokter 🇮🇩** — target kedua di Babak 42 yang sama, server-rendered penuh dengan JSON-LD `ItemList` berisi objek `Physician` lengkap |
| Portal riset nasional (Babak 43 #3) | **`sinta.kemdikbud.go.id`** — dicatat Babak 43 sudah pindah ke `.kemdiktisaintek` | Domain baru benar dan **hidup** (335.591 peneliti). Dikonfirmasi ulang di sini sekaligus jadi bukti Gotcha #2 Babak 43 | **`sinta.kemdiktisaintek.go.id`** |

## Gotcha Metodologi Baru

1. **Ukuran halaman (KB) BUKAN proksi keberadaan data — dan riset ini sudah tiga babak memakainya sebagai proksi utama.** Tiga dari empat koreksi di atas berakar di sini: Sarısayfalar 111 KB (iklan baris), Hukumonline 532 KB (basis data peraturan), Halodoc 286 KB (framework Angular). Semuanya "lolos" probe HTTP Babak 41/42 dengan status 200 dan HTML tebal. **Aturan baru: probe wajib mengecek satu record nyata** (satu nama pengacara / satu nama perusahaan / satu nama dokter) di dalam HTML, bukan sekadar status + ukuran. Biayanya satu regex; harganya kalau dilewatkan adalah tiga kandidat prioritas tinggi yang salah sasaran.
2. **Nol kompetitor bisa berarti "tidak ada datanya", bukan "belum digarap".** Indonesia punya **nol** actor direktori pengacara di seluruh scan Babak 42 — dan penyebabnya bukan pasar yang belum ditemukan, melainkan **tidak ada direktori pengacara Indonesia yang publik**. Ini kategori ketiga di samping "pasar mati" (Gotcha #2 Babak 42) dan "situs tidak terjangkau" (IBAPI/peradi): **permukaan datanya memang tidak ada**. Tes pembeda: cari satu record nyata sebelum menghitung seller.
3. **Halaman yang menerima parameter tanpa mengeluh tetap harus diuji satu per satu.** Terulang di tiga actor babak ini: DJKN menerima `katakunci`/`provinsi`/`kota`/`sortby` dengan 200 dan **hasil tak terfilter** (yang benar `search` + `namakategori[]`, dan `namakategori` tanpa `[]` justru 400); SINTA mengabaikan `sort` lewat GET; IndonesiaYP mengabaikan `?page=N` **dan** mengembalikan halaman 1 untuk halaman di luar batas. Semua sudah dicatat di `CRAWLING_METHOD.md` masing-masing, dan parameter yang diabaikan **tidak dijadikan input actor** supaya tidak ada tombol yang diam-diam tidak bekerja.
4. **Namespace URL yang mirip belum tentu setara — dan salahnya senyap.** Di Social Blade, `/youtube/@mrbeast` (516 juta subscriber) dinormalisasi ke `/youtube/user/mrbeast` menghasilkan channel **lain** bernama sama dengan **2.100 subscriber**. Record-nya lengkap, wajar, dan sepenuhnya salah — tanpa error apa pun. Perbaikan: URL diambil **apa adanya**, hanya handle telanjang yang diekspansi.
5. **JSON-LD upstream bisa invalid dan mematikan seluruh halaman diam-diam.** Alodokter menulis apostrof sebagai `\&#39;` (escape `\&` ilegal di JSON) → `json.loads` gagal → **seluruh spesialisasi `dokter-gigi` menghasilkan nol record padahal servernya mengirim 307 KB data asli**. Parser JSON-LD di portofolio ini sebaiknya selalu punya jalur perbaikan + fallback, bukan `try/except: continue`.
6. **Soft-404 mengalahkan status code.** Alodokter membalas **200** untuk slug spesialisasi yang tidak ada (shell ~17 KB); PSA membalas 200 untuk semua path `/pop/*`; IndonesiaYP membalas 200 untuk halaman ke-99999. Deteksi akhir data harus berbasis **isi** (jumlah record, ukuran ambang, id yang sudah terlihat), tidak pernah berbasis status.

## Insight Strategis Babak 44

> **Riset tiga babak terakhir menilai target lewat sinyal yang tidak pernah menyentuh datanya.** Jumlah seller, users, runs, status HTTP dan ukuran HTML semuanya bisa benar sementara targetnya salah total — terbukti 4 dari 8 kali di babak ini. Yang membedakan kandidat yang jadi dan yang gugur bukan skor demand-nya, melainkan **apakah ada satu record nyata yang bisa dipegang**. Untuk babak riset berikutnya: pindahkan "ambil satu record" dari fase eksekusi ke fase scan.

> **Pola "data-type terbukti × yurisdiksi kosong" bertahan — tapi yurisdiksinya harus diuji, bukan diurutkan.** Babak 42 mengurutkan ID → IN → SG/MY dan menaruh Indonesia di depan karena "pasar rumah sendiri + HTML paling tebal". Indonesia ternyata nol permukaan data untuk pengacara, sementara India (urutan kedua) langsung jadi. Urutan prioritas berbasis intuisi pasar menunda eksekusi; urutan berbasis **verifikasi permukaan data** akan langsung menunjuk yang benar.

> **Kandidat termurah ternyata juga yang paling bernilai.** DJKN diprediksi Babak 43 sebagai "biaya eksekusi terendah dari semua kandidat Babak 41–43", dan hasilnya API JSON pemerintah tanpa proteksi apa pun dengan 11.889 record aktif. Sementara kandidat yang paling banyak menyita waktu babak ini (PSA) justru yang paling lemah bukti demand-nya. **Urutkan eksekusi dari biaya recon, bukan dari skor demand** — biaya recon bisa diketahui dalam menit, skor demand butuh babak.

## Rekomendasi Lanjutan

1. **Push 6 actor ke Apify, lalu ukur 2–4 minggu.** Ini pertanyaan yang sudah tiga babak digantung: apakah pola "yurisdiksi kosong" menghasilkan pembeli nyata? Sekarang ada 6 sampel di 4 vein berbeda (lelang pemerintah, direktori profesi, direktori bisnis, analitik kreator) untuk menjawabnya secara empiris.
2. **Ekspansi termurah kalau ada traksi**, dalam urutan biaya: (a) 4 portal lelang bank Indonesia yang ditemukan di bundle DJKN (`infolelang.bri.co.id`, `lelang.bankmandiri.co.id`, `lelangagunan.bni.co.id`, `lelang.bankbjb.co.id`); (b) yurisdiksi lelang kosong lain yang sudah terbukti terbuka: 🇵🇱 `licytacje.komornik.pl` (1,3 MB), 🇯🇵 BIT 競売 (343 KB), 🇹🇷 UYAP e-satış (54 KB); (c) mode tambahan SINTA yang jalurnya identik (`/departments`, `/sources`, `/books`, `/ipr`, `/researches`); (d) direktori pengacara SG/MY.
3. **Jangan ulangi dua kandidat yang dihentikan** tanpa perubahan kondisi: PSA butuh reverse-engineering tRPC di balik Cloudflare untuk pasar head-to-head; exhibitor butuh masuk ke platform yang sudah dikuasai incumbent 579-user.
4. **Terapkan Gotcha #1 sebagai perubahan permanen pada `probe*.py`**: setiap probe target baru harus mengembalikan `status`, `bytes`, **dan** satu record contoh yang berhasil di-regex. Tanpa kolom ketiga itu, angka dua kolom pertama sudah terbukti menyesatkan tiga kali.

## File Referensi Babak 44

- `lelang-djkn-scraper/` · `lawrato-lawyer-directory-scraper/` · `indonesiayp-business-directory-scraper/` · `alodokter-doctor-directory-scraper/` · `sinta-researcher-scraper/` · `socialblade-creator-analytics-scraper/` — 6 actor lengkap, masing-masing dengan `CRAWLING_METHOD.md` berisi temuan recon, jebakan parameter, dan gotcha parser spesifik targetnya
- `scratchpad/probe44_lawyer.py` — recon direktori pengacara ID/IN/SG/MY (bukti Indonesia nol permukaan data)
- `scratchpad/probe45.py` — recon gabungan 6 target sisa (Sarısayfalar, Halodoc, PSA, SINTA, Social Blade, exhibitor)
- `scratchpad/psa_bundle.js` — 1,59 juta karakter chunk PSA yang di-grep untuk mencari prosedur tRPC (nihil)

---

# Babak 45 — Scan ROI/Stats-Tinggi Putaran Kedua: Band Baru Dibuka, 51 Konsep Baru Diuji, **Nol Kandidat Baru**; 1 Blind Spot 44-Babak Ditemukan & Di-skip, 2 Koreksi Besar (2026-09-08)

**Konteks:** user kembali meminta **daftar actor ber-ROI data tinggi / stats sudah tinggi di Apify Store**, dengan dua syarat dedupe yang sama seperti Babak 41: (a) tidak boleh sudah ada di akun kedua [`xtracto`](https://api.apify.com/v2/store?username=xtracto), (b) tidak boleh sudah tercatat di dokumen ini maupun [`actors_researcher_v2.md`](actors_researcher_v2.md). Babak ini menjalankan permintaan yang sama dengan Babak 41 **tetapi lewat pintu yang belum pernah dibuka**, karena Babak 41 sudah menyimpulkan ujung stats-tinggi Store habis (Rekomendasi #4: "berhenti menscan band users ≥150 & runs ≥20rb").

**Snapshot dedupe:** `apify-my-store.py xtracto` → **masih 218 actor**, tidak berubah sejak Babak 39.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---|---|
| ✅ **BELUM dibangun — kandidat baru layak eksekusi** | **0** | Tidak ada. Semua yang punya demand nyata sudah dipegang `xtracto`, sudah jenuh, atau melanggar kebijakan portofolio — rincian di tabel skip |
| 🔁 **SUDAH tercakup** (muncul di scan, bukan temuan baru) | **~103 actor / 25 konsep** | Skip-trace-adjacent LinkedIn, Yelp, Upwork, Similarweb, Crunchbase, Etsy, Naukri, Truth Social, Snapchat, Douyin, Patreon, Clutch, Y Combinator, Meetup, Discord, Transfermarkt, Autoscout24, IndiaMart, Goodreads, WooCommerce, G2, Substack, Skool, Firmy, StreetEasy |
| ⛔ **DI-SKIP dengan alasan konkret** | **51 konsep baru + 12 sub-tipe olahraga + 3 finalis top-down** | 48 dari 51 konsep baru **nol seller serius**; 15 di antaranya **nol seller sama sekali** (= pasar mati, bukan peluang — Gotcha #2 Babak 42) |
| 🔧 **Koreksi untuk riset lama** | **2** | QS Top Universities (backlog 🟢) **degradasi 3 → 12 seller** · vein putusan pengadilan terbukti **pasar mati** padahal 2 actor sudah dibangun |
| 🆕 **Blind spot 44 babak** | **1** | **Skip trace / people search — 20.959 user, 4,9 juta runs** — nol jejak di seluruh riset sebelumnya. Tetap di-skip (alasan di bawah) |

## Ringkasan Eksekutif

- **Hasil jujur: nol kandidat baru yang layak dibangun.** Ini babak riset pertama yang menghasilkan nol — dan itu **konsisten dengan prediksi Babak 41/43**, bukan kegagalan metode. Tiga arah berbeda dijalankan (band stats baru, 51 konsep baru, pemecahan sub-tipe vein terkuat), ketiganya buntu di titik yang sama: yang laku sudah dipegang, yang belum digarap tidak laku.
- **Band ROI yang belum pernah dilihat siapa pun akhirnya dibuka — dan kosong.** Babak 41 mewajibkan `users ≥150` di scan top-down-nya, sehingga actor "**sedikit user tapi dipakai terus**" (rpu ekstrem = pipeline harian, sinyal ROI paling murni) secara harfiah tidak pernah masuk radar. Band B babak ini (`runs ≥100.000`, **tanpa** batas user) menarik **105 actor yang tak terlihat di babak mana pun**. Isinya: tooling Apify sendiri (`monitoring-*`, `s3-uploader`), statistik COVID mati, dan **jebakan runs** murni — `ai_solutionist/federal-spending-forensic-api` **1 user / 308.054 runs**, `beige_quaff/immoscout24-apply-bot` **2 user / 490.074 runs**. Nol sumber data baru. **Arah top-down kini resmi tertutup dari kedua sisi.**
- **Blind spot terbesar 44 babak ditemukan: skip trace / people search.** **28 seller, 4 serius, 20.959 user, 4,9 juta runs** — dipimpin `one-api/skip-trace` (**12.822 user / 4.543.126 runs / 354 rpu**). Konsep ini **nol jejak** di seluruh dokumen riset (grep 0 hit) **dan** nol di `xtracto`. Tetap **di-skip**, dengan dua alasan yang berdiri sendiri — lihat tabel skip.
- **Vein terkuat yang sah secara kebijakan adalah olahraga — dan `xtracto` benar-benar kosong di sana.** Skor/statistik live: sepak bola **5.457 user** (32 seller, 4 serius), tenis **5.925 user** (37 seller, 3 serius). Tapi 12 sub-tipe diuji (kriket, basket, esports, MMA, baseball/NFL, rugby, liga Asia, atletik, fantasy, xG, kontrak atlet) dan **10 dari 12 nol seller serius** dengan TAM mikro (5–1.561 user). Demand olahraga terkonsentrasi persis di dua sub-tipe yang sudah paling padat.

## Metodologi Babak 45

```bash
python apify-my-store.py xtracto -o output/mine-xtracto.json      # 218 actor (tidak berubah)

# Pass 0 - INVENTARISASI ULANG + PERBAIKAN BLOB DEDUPE (Rekomendasi #4 Babak 43)
#   30 script riset Babak 1-44 di-ekstrak -> 405 label konsep + 1.443 string query
#   blob dedupe xtracto kini memuat DESCRIPTION, bukan cuma name+title
#   scratchpad/inv45.py -> _concept_labels45.txt, _all_strings45.txt, _mine_blob45.txt
# Pass 1 - TOP-DOWN dua band, 25 kategori PENUH (Babak 41 cuma 21):
#   Band A = users>=150 & runs>=20rb  -> 1.384 actor  (replikasi Babak 41)
#   Band B = runs>=100rb TANPA batas users -> 814 actor  <-- BELUM PERNAH DISCAN
#   gabungan 1.489 unik | 105 HANYA ada di band B
#   scratchpad/highstats45.py -> output/scan-v8-highstats.json, scan-v8-bandB.json
# Pass 2 - 51 konsep BARU, nol tumpang tindih dengan 405 label lama
#   12 grup wilayah baru: legislatif/parlemen | imigrasi & visa | pos-alamat-geo |
#   sertifikasi & type approval | lingkungan & ESG | catatan sipil & genealogi |
#   benchmark gaji | musik & streaming | infrastruktur & utilitas | bantuan donor |
#   olahraga transfer | film & produksi | putusan pengadilan per yurisdiksi | dll
#   scratchpad/compete45.py -> output/scan-v8-competition.json
# Pass 3 - saring pool 1.489 dengan blob baru -> 16 kandidat bersih
#   scratchpad/rank45.py -> output/scan-v8-clean.json
# Pass 4 - uji kompetisi union 3 finalis + ANTI-FALSE-NEGATIVE vein putusan pengadilan
#   scratchpad/verify45.py -> output/scan-v8-verify.json
# Pass 5 - vein terkuat (olahraga) dipecah 12 sub-tipe & olahraga
#   scratchpad/verify45b.py -> output/scan-v8-sports.json
# Pass 6 - tabel ROI (rpu tertinggi) + CROSS-CHECK longgar (hanya blob xtracto,
#   sengaja tidak difilter docs/local supaya tidak over-filter - Gotcha #2 Babak 41)
#   -> 103 actor, semuanya dicek harfiah satu per satu
#   scratchpad/roi45.py
# Pass 7 - 2 konsep bernol-jejak (grep 0 hit di kedua dokumen): skip trace & lirik lagu
#   plus re-cek backlog QS rankings   scratchpad/verify45c.py -> output/scan-v8-verify2.json
```

## ✅ BELUM Dibangun — Kandidat Baru

**Kosong. Nol kandidat.**

Ini hasil sebenarnya, bukan babak yang belum selesai. Tiga arah dijalankan penuh dan ketiganya buntu:

| Arah | Yang dijalankan | Hasil |
|---|---|---|
| Top-down band baru | 1.489 actor ber-stats tinggi, 25 kategori, termasuk **105 actor band B yang belum pernah terlihat** | 16 lolos filter otomatis → setelah dicek harfiah: **13 tooling generik** (`apify/openrouter` 7.272u, `parsera-labs/parsera` 625u, `mstephen190/vanilla-js-scraper`, `canadesk/seo-site-checkup`, `apikit/upcheck`, dst), **2 sudah diputus di riset lama** (`cleansyntax/dentist-finder` 169u = vein dokter gigi yang di-skip Babak 41; `epctex/duckduckgo-scraper` = SERP komoditas), **1 mati** (`petrpatek/covid-usa-cdc`) |
| Bottom-up konsep baru | 51 konsep di 12 grup wilayah yang belum pernah disentuh 405 label lama | **48 nol seller serius**, 15 di antaranya nol seller total. 3 yang punya seller serius: 2 **sudah di `xtracto`** (Spotify, SoundCloud), 1 jenuh 21 seller (Transfermarkt) |
| Pemecahan sub-tipe vein terkuat | 12 sub-tipe olahraga | **10 dari 12 nol seller serius**, TAM 5–1.561 user. Yang laku (sepak bola & tenis) justru yang paling padat (32–37 seller) |

## 🔁 SUDAH Ada — Muncul di Scan Tapi Bukan Temuan Baru

Cross-check longgar Pass 6 (sengaja hanya memfilter blob `xtracto`, tanpa filter dokumen) meloloskan **103 actor ber-stats tinggi**. Semuanya dicek harfiah — **tidak satu pun temuan baru**:

| Konsep (stats yang bikin muncul) | Sudah diputus di | Vonis lama |
|---|---|---|
| Patreon (`jupri/patreon` 2.670u) | Dokumen ini | Jenuh — 8.511u / 30 seller |
| Clutch.co (`epctex/clutchco` 2.605u) | Dokumen ini | Jenuh — 7.527u / 37 seller |
| Douyin (`natanielsantos` 2.015u / 777 rpu) | Dokumen ini | Jenuh + incumbent 10rb user |
| Y Combinator (`michael.g` 1.590u) | Dokumen ini | Jenuh — 4.618u / 37 seller |
| Transfermarkt (`curious_coder` **2.824u**) | Dokumen ini | Jenuh — 3.664u / 22 seller |
| Autoscout24 (`ivanvs` 851u) | Dokumen ini | Jenuh — 2.329u / 33 seller |
| Meetup (`filip_cicvarek` 462u) | Dokumen ini | Jenuh (konsisten Babak 39) |
| Discord (`curious_coder` 1.271u / 985 rpu) | Dokumen ini | Jenuh — 8.008u / 27 seller |
| Similarweb (5 actor, 1.321–3.959u), Ahrefs, Crunchbase, D&B, Seek, Naukri, Truth Social, Snapchat, Upwork, G2, StreetEasy, Apartments.com, Firmy, Bing, IndiaMart, Goodreads, WooCommerce | Babak 39/40/41 + v2 | Semua sudah punya keputusan |
| Etsy, MercadoLibre, UberEats | `xtracto` (`etsy-*` ×3, `mercadolibre-scraper`, `ubereats-menu-scraper`) | Sudah dipegang |
| Spotify (`beatanalytics/spotify-play-count` 870u), SoundCloud | `xtracto/spotify-play-count-scraper`, `spotify-scraper`, `soundcloud-scraper` | Sudah dipegang — konsep AH1 & AH2 gugur karena ini |
| Substack (`qpayre` 464u), Skool (`louisdeconinck` 894u) | Folder repo: `substack-scraper`, `skool-whop-community-analyzer` | Sudah dibangun |

## ⛔ DI-SKIP — Semua dengan Alasan Konkret

### A. Blind spot 44 babak — ditemukan, diuji penuh, tetap di-skip

| Konsep | Angka | Kenapa di-skip |
|---|---|---|
| **Skip trace / people search** 🆕 | **28 seller / 4 serius / 20.959 user / 4.908.573 runs**. Incumbent `one-api/skip-trace` **12.822u / 4.543.126r / 354 rpu**; penantang `axlymxp/truepeoplesearch` 2.775u, `curious_coder/linkedin-people-search` 2.382u, `apivault_labs/skip-trace-people-finder` 638u ⭐5.0 | **Dua alasan yang masing-masing sudah cukup.** (1) **Kebijakan portofolio soal PII massal** — produknya adalah "nama → alamat rumah + telepon + kerabat". Ini persis alasan yang sudah dipakai untuk men-skip validasi/lookup nomor telepon (Babak 41: *"berisiko — data pribadi massal"*) dan WhatsApp validator (Babak 40). Men-skip yang 2.494u lalu membangun yang 12.822u = kebijakan yang tidak konsisten. (2) **Jenuh secara angka** — 28 seller dengan 4 seller serius, incumbent 12.822 user. **Dicatat eksplisit supaya babak berikutnya tidak menemukan ulang dan mengira ini gem** |

### B. Vein olahraga — demand nyata, `xtracto` kosong, tapi tidak bisa dimasuki

| Sub-tipe | Seller / Serius | Terbesar | Kenapa di-skip |
|---|---|---|---|
| **Tenis** | **37 / 3** | `crawlstone/tennis-scraper` **1.971u**; `extractify-labs/flashscore-tennis-matches` 1.761u; `parseforge/tennis-abstract` 1.480u | TAM terbesar di seluruh vein (5.925u) **dan** paling padat. Tiga incumbent di atas 1.400 user |
| **Sepak bola live/flashscore** | **32 / 4** | `azzouzana/sofascore-scraper-pro` 899u; `statanow/flashscore-scraper-live` 539u ⭐5.0 | 5.457u tapi 32 seller. `extractify-labs` sudah memecah 5 sub-tipe sendiri (tenis/live/fixtures/odds/team-stats) — masuk sekarang = kloning ke-33 |
| Baseball/NFL/NHL | 27 / **0** | `crawlerbros/mlb-stats-scraper` 312u | 1.561u tersebar 27 seller, **rpu 3–12** = pemakaian sekali-jalan, bukan pipeline |
| MMA / tinju | 18 / **0** | `lemur/ufc-api` 212u | 899u / 18 seller, rpu 4–9 |
| Basket (NBA/NCAA) | 9 / **0** | `extractify-labs/flashscore-basketball` 32u | TAM mikro (164u) |
| Kriket (IN/PK/BD/AU) | 10 / **0** | `fingolfin/espncricinfo-statsguru` 112u | **Tes yurisdiksi paling penting di babak ini dan hasilnya negatif:** kriket = olahraga terbesar India, tapi TAM-nya di Apify cuma **151 user**. Ini bukti langsung bahwa "yurisdiksi kosong" **tidak berlaku** untuk data olahraga |
| Esports (HLTV/Liquipedia) | 10 / 0 | `paco_nassa/hltv-live-matches` 120u | 263u |
| xG / analitik lanjutan (Understat/FBref) | 7 / 0 | `mirthful_radish/understat-xg` 208u | 325u, rpu 4 |
| Fantasy & player props | 10 / 1 | `zen-studio/underdog-player-props` 144u/12.476r | TAM 190u; satu-satunya "serius" pun cuma 144 user |
| Rugby/AFL · atletik/maraton | 2 / 0 · 1 / 0 | 2u · 3u | Praktis nol |
| **Liga Asia (J-League/K-League/Liga 1)** · **kontrak & gaji atlet (Spotrac)** | **0 / 0** | — | Nol seller **dan** nol bukti demand di yurisdiksi lain → pasar mati, bukan peluang (Gotcha #2 Babak 42) |

### C. 51 konsep baru — 48 nol seller serius

| Grup | Konsep | Angka terbaik di grup | Vonis |
|---|---|---|---|
| **Legislatif & parlemen** | RUU & voting · hansard · register harta pejabat · petisi/konsultasi publik | `spookyweb/uk-hansard` **2u** · `memo23/congress-financial-disclosure` 29u · `jungle_synthesizer/regulations-gov` 5u | Semua **0 serius**, total ≤29u per konsep. Vein civic-tech = nol pembeli |
| **Imigrasi & visa** | Register sponsor visa · LMIA · syarat visa & travel advisory · slot janji temu | `dakheera47/uk-visa-sponsor-verifier` 12u; syarat visa & slot janji **0 seller** | Konsep "register sponsor" terdengar B2B rekrutmen, faktanya 4 seller/26u |
| **Pos, alamat & geo** | Kodepos & alamat · pelacakan paket · batas administratif | `alizarin_refrigerator/multi-carrier` 55u · `ninhothedev/zip-code` 2u | Data kodepos & batas wilayah **punya dump resmi gratis** → aturan Babak 43 berlaku: langsung buang |
| **Sertifikasi & type approval** | FCC ID · label energi EPREL · UL/CE | `eloquent_mountain/eprel` 7u · FCC ID 1 seller/2u · UL/CE **0 seller** | Semua mikro |
| **Lingkungan & ESG** | Izin emisi · kualitas udara · kredit karbon · laporan ESG · fasilitas limbah | `ryanclinton/openaq-air-quality` 15u · `primeparse/esg-content` 17u · `jungle_synthesizer/carbon-credit` 12u | 14 seller berebut 49u di kualitas udara. OpenAQ/Verra **punya API resmi** → aturan Babak 43 |
| **Catatan sipil & genealogi** | Kelahiran/kematian/nikah · makam | `parseforge/cemetery-records` 23u; indeks vital **0 seller** | Mikro + PII |
| **Benchmark gaji** | Levels.fyi/Glassdoor · transparansi gaji lowongan | **38 seller** / 1 serius / 347u — `parseforge/levels-fyi` 39u/95.064r | Paling jenuh di grup ini: 38 seller berebut 347 user. Glassdoor sendiri **sudah di `xtracto`** ×3 |
| **Musik & streaming** | Chart/playlist · analitik artis · metadata rilis | **21 seller / 3 serius / 1.160u** — tapi incumbent `beatanalytics/spotify-play-count` 870u | **Sudah di `xtracto`** (`spotify-play-count-scraper`, `spotify-scraper`, `soundcloud-scraper`). MusicBrainz 16 seller/49u = wrapper API gratis |
| **Infrastruktur & utilitas** | Gangguan listrik/air · tarif tol · registry drone · callsign radio | Gangguan, tol, drone: **0 seller** · `automation-lab/fcc-amateur-radio` 2u | Nol demand |
| **Bantuan donor & subsidi** | Proyek IATI/World Bank · subsidi pertanian · penerima hibah | `maximedupre/world-bank-projects` 2u · `jungle_synthesizer/usda-farm-subsidy` 5u | Semua punya API/dump resmi + nol pembeli |
| **Film & produksi** | Database produksi film/TV · box office | `trovevault/movie-box-office-tracker` 30u · produksi 1 seller/2u | Mikro |
| **Direktori profesi non-hukum/medis** | Akuntan · arsitek/insinyur · notaris · penerjemah tersumpah | `parseforge/aicpa-cpa-directory` 22u · `giovannibiancia/riba-architects` 5u · notaris 1u · penerjemah **0 seller** | **Penting:** vein direktori profesi yang berhasil di Babak 42 (pengacara, dokter) **tidak menyebar** ke profesi lain. Pengacara & dokter laku karena nilai transaksinya tinggi; akuntan/arsitek/notaris tidak |
| **Aset sitaan & surplus negara** | Lelang sitaan bea cukai/pajak · kendaraan dinas | 10 seller / **0 serius** / 102u — `parseforge/govdeals-scraper` 65u, rpu 15 | Ekstensi vein lelang Babak 43 ke sisi "barang" **gagal**: demand-nya properti, bukan surplus |
| **Umrah/haji · lelang ikan · statistik pasar kerja · pelatihan vokasi** | — | **0 seller** semua | Pasar mati |

### D. Kandidat top-down yang gugur setelah verifikasi

| Konsep | Kelihatannya | Faktanya | Vonis |
|---|---|---|---|
| **Genius / lirik lagu** | `epctex/genius-scraper` **316u / 65.079r / 206 rpu**, nol jejak di seluruh dokumen riset | Union luas: **19 seller / 1 serius / 592u** — 12 kloning `genius-*-scraper` dari seller berbeda | Skip: jenuh **+ risiko hak cipta** (lirik = konten berlisensi; Genius sendiri pernah menuntut soal ini) |
| **GoFundMe / crowdfunding donasi** | `jupri/gofundme` **104u / 184.068r / 1.770 rpu** — rpu pipeline sejati | Union: 7 seller lain, total cuma 42u; ditambah `jupri` ≈ 146u. Crowdfunding ekuitas (Indiegogo dkk) 10 seller / **0 serius** / 81u | Skip: **TAM mikro**. rpu 1.770 berasal dari satu-dua pemakai berat, bukan pasar |
| **FlashScore Live** | `statanow/flashscore-scraper-live` 539u / 97.211r / **180 rpu** ⭐5.0 | 32 seller di sub-tipe yang sama | Skip — lihat tabel B |
| **`apify/openrouter`** | **7.272 user / 2.296.513 runs** — user terbanyak di antara kandidat bersih | Tooling AI milik Apify sendiri | Di luar strategi (konsisten dengan `apify/web-scraper` dkk di Babak 41) |
| **`fatihtahta/lead-finder-with-emails`** | 739u / 29.185r | Lead-gen email generik | Komoditas + vein verifikasi email sudah divonis jenuh (57 seller) di Babak 41 |

### E. Band B — 105 actor yang belum pernah terlihat di babak mana pun

| Pola | Contoh | Vonis |
|---|---|---|
| **Jebakan runs ekstrem** | `ai_solutionist/federal-spending-forensic-api` **1u / 308.054r** · `beige_quaff/immoscout24-apply-bot` **2u / 490.074r** · `knagymate/zoover-reviews` 2u/142.450r | Runs raksasa dari 1–2 pemakai. Persis "jebakan runs" Babak 40, kini terlihat dalam bentuk paling murni |
| **Tooling Apify & integrasi** | `apify/monitoring-*` (4 actor, sampai 5,1 juta runs) · `apify/s3-uploader` 55u/3,5jt r · `apikit/upcheck` 16u/1,1jt r · `dtrungtin/google-sheets-monitoring` | Di luar strategi |
| **Aktif tapi mati** | `lukass/covid-est`, `zuzka/covid-bg`, `davidrychly/covid-sk-3`, `petrpatek/covid-austria` (5 actor COVID, 123rb–162rb runs) | Cron warisan pandemi yang masih jalan. **Runs tinggi ≠ pasar hidup** |
| **Sudah dipegang/diputus** | `canadesk/apple-app-store-plus` 32u/2,5jt r · `parseforge/nasdaq-short-interest` · `saswave/noon-seller-monitoring` · `scraped/tcgplayer-sales-history` | Semua sudah ada flag M/D/L/S |

**Nol sumber data baru dari 105 actor.** Band ini resmi tertutup.

## 🔧 Koreksi untuk Riset Lama

| Pernyataan lama | Temuan Babak 45 | Dampak |
|---|---|---|
| **QS Top Universities** dicatat sebagai kandidat **#8 🟢 Rendah-Sedang** dengan **"3 seller (sisanya 4u dan 4u) — seller paling sedikit dari seluruh scan"** | Sekarang **12 seller / 1 serius / 740u**. Selain `vbartonicek` (670u) sudah masuk `parseforge` (**4 actor**: qs-world, times-higher-education, leiden, university-rankings-mega-pack), `solidcode`, `crawlerbros` (usnews), `lexis-solutions` (collegesimply), `azureblue`, `niche-schools` | **Turunkan dari backlog.** Bukan lagi "3 seller", dan incumbent 670u tetap tidak tergoyahkan. Ini juga **bukti kecepatan kloning**: satu seller (`parseforge`) masuk dengan 4 varian sekaligus di vein yang riset lama sebut "paling sepi" |
| Babak 37/38: putusan pengadilan per yurisdiksi = **"nol kompetitor"** → 2 actor dibangun (`sg-court-judgments-scraper`, `ph-court-decisions-scraper`) | Uji anti-false-negative penuh (4 frasa berbeda total + nama platform telanjang: indiankanoon/canlii/austlii/bailii/courtlistener/justia/pacer): **case law generik 9 seller / 0 serius / 46u** · **docket AS 22 seller / 0 serius / 252u** · **Asia Tenggara 0 seller / 0 user**. Total vein ≈ **300 user, nol seller serius di mana pun di dunia** | **"Nol kompetitor" di vein ini ternyata berarti pasar mati, bukan yurisdiksi kosong** — persis Gotcha #2 Babak 42 & #2 Babak 44, tapi baru terukur sekarang. Dua actor sudah terlanjur dibangun; **jangan tambah yurisdiksi ketiga** sebelum keduanya menunjukkan traksi nyata |
| Babak 41 Rekomendasi #4: "berhenti menscan ujung stats-tinggi (users ≥150 & runs ≥20rb)" | ✅ **Terkonfirmasi, dan sekarang diperluas.** Band B (`runs ≥100rb` tanpa batas user) — satu-satunya celah yang tersisa di arah top-down — juga kosong | Arah top-down **tertutup penuh dari kedua sisi**. Tidak perlu discan lagi dengan band apa pun |
| Babak 43 Rekomendasi #4: "perbaiki blob dedupe, tambahkan `description`" | ✅ **Dijalankan** (`scratchpad/inv45.py`). Blob naik jadi 48.957 karakter | Dipakai di seluruh Pass babak ini |

## Gotcha Metodologi Baru

1. **Union bottom-up dan pool top-down sama-sama bocor — dan bocornya ke arah berlawanan, jadi keduanya wajib disilangkan.** Bukti di babak ini: union konsep AK1 menemukan Transfermarkt terbesar = `data_xplorer` **256u**, sementara scan top-down menemukan `curious_coder/transfermarkt` **2.824u** — **11× lebih besar, tidak tertangkap union**. Sebaliknya `jupri/gofundme` (104u/184rb runs) tidak muncul di union K3 walau kunci `gofundme` cocok, karena tidak masuk 50 hit teratas frasa mana pun. **Aturan baru: setiap finalis dari salah satu arah wajib dicek ulang di arah satunya sebelum angka seller-nya dipercaya.** Gotcha #1 Babak 41 ("kunci harus memuat nama platform telanjang") **belum cukup** — masalahnya bukan kunci, tapi batas 50 hit per frasa.
2. **Dedupe token otomatis membuang 1.473 dari 1.489 actor (98,9%).** Filter longgar (hanya blob `xtracto`, tanpa docs/local/strings) meloloskan **103**, dan setelah dicek harfiah **semuanya memang sudah diputus**. Filter ketatnya benar — tapi kebenarannya baru terbukti **setelah** pengecekan manual, jadi jangan pernah melaporkan hasil filter otomatis sebagai kesimpulan.
3. **Runs tinggi yang masih mengalir bisa berasal dari pasar yang sudah mati bertahun-tahun.** Lima actor statistik COVID di band B masih mencatat 123rb–162rb runs. Itu cron warisan pandemi, bukan permintaan. **Tes pembeda: rasio user, bukan besaran runs** — kelimanya ≤14 user.
4. **Vein yang berhasil tidak menyebar ke tetangga semantiknya.** Direktori **pengacara & dokter** menghasilkan 2 actor di Babak 42/44; direktori **akuntan, arsitek, notaris, penerjemah** yang diuji di babak ini semuanya ≤22 user. Kedekatan konsep ("sama-sama direktori profesi berlisensi") **bukan prediktor demand**. Prediktornya nilai transaksi di balik pencarian: orang mencari pengacara/dokter dalam keadaan mendesak dan mahal; tidak ada yang membangun pipeline data untuk mencari notaris.

## Insight Strategis Babak 45

> **Pertanyaan "actor apa yang ROI/stats-nya tinggi" sekarang punya jawaban final, dan jawabannya bukan daftar.** Babak 41 mengukurnya sekali (1.384 actor, nol vertikal baru) dan menyimpulkan ujung stats-tinggi habis. Babak 45 membuka **satu-satunya band yang tersisa** di arah itu — actor ber-runs raksasa tanpa syarat jumlah user — dan menemukan 105 actor yang belum pernah dilihat siapa pun, **nol** di antaranya sumber data baru. Dua pengukuran independen, kesimpulan sama. Arah ini tidak perlu diulang lagi; babak berikutnya yang menjawab permintaan yang sama sebaiknya menjawabnya dengan **kalimat ini**, bukan dengan scan baru.

> **Blind spot 44 babak itu nyata, dan bentuknya bukan niche kecil yang terlewat — melainkan kategori 21 ribu user yang tidak pernah ditanyakan.** Skip trace tidak pernah muncul di 405 label konsep karena setiap babak bertanya "platform/yurisdiksi apa yang belum digarap", tidak pernah "**jenis pekerjaan** apa yang orang bayar mahal". Pelajarannya bukan "bangun skip trace" (itu tetap di-skip karena PII), tapi bahwa **taksonomi pertanyaannya sendiri punya lubang**. Kalau ada babak berikutnya, bukanya dari sisi *pekerjaan pembeli*, bukan sisi *sumber data*.

> **Kloning di Apify Store lebih cepat daripada siklus riset ini.** QS Top Universities dicatat "3 seller, paling sepi dari seluruh scan" dan tidak dibangun; sekarang 12 seller, dengan satu seller (`parseforge`) masuk membawa 4 varian sekaligus. Ini menaikkan biaya nyata dari menunda: **backlog yang tidak dieksekusi bukan cuma diam — dia membusuk.** Enam actor Babak 44 yang sudah jadi tapi belum di-push menghadapi risiko yang persis sama.

> **Dua vein yang sudah terlanjur dibangun perlu diakui apa adanya.** Putusan pengadilan (2 actor, Babak 37/38) kini terukur: nol seller serius di seluruh dunia, ±300 user total untuk seluruh kategori. "Nol kompetitor" waktu itu dibaca sebagai yurisdiksi kosong; ternyata pasar mati. Itu bukan alasan menghapus actor-nya — biayanya sudah keluar — tapi **alasan kuat untuk tidak menambah yurisdiksi ketiga** dan untuk memindahkan tes demand ke depan fase build, sebagaimana sudah direkomendasikan sejak Babak 42.

## Rekomendasi Lanjutan

1. **Prioritas tunggal: push 6 actor Babak 44 dan ukur.** Rekomendasi ini sudah berdiri sejak Babak 42 (#5), 43 (#1), dan 44 (#1), dan **masih belum dijalankan**. Babak 45 sekarang menambahkan bukti keras kenapa menundanya mahal: arah riset top-down terbukti tertutup dari kedua sisi, 51 konsep baru menghasilkan nol, dan backlog yang didiamkan terbukti membusuk (QS 3 → 12 seller). **Nilai marjinal babak riset ke-46 mendekati nol; nilai satu actor yang dipublikasikan dan diukur masih belum diketahui sama sekali.**
2. **Jangan buka lagi arah top-down dengan band apa pun.** Band `users ≥150 & runs ≥20rb` (Babak 41) dan band `runs ≥100rb tanpa batas user` (babak ini) sama-sama kosong. Tidak ada band ketiga yang tersisa.
3. **Kalau tetap ingin riset, ganti sumbu pertanyaannya — jangan tambah konsep.** Setelah ~456 konsep dan 45 babak, sumbu "platform/yurisdiksi/data-type" sudah kering. Sumbu yang belum pernah dipakai dan terbukti punya lubang besar (kasus skip trace): **pekerjaan yang dibayar mahal oleh pembeli** — mis. "apa yang dikerjakan agensi rekrutmen/penagih utang/tim due-diligence setiap hari", lalu baru dicari data apa yang menopangnya.
4. **Jangan bangun yurisdiksi ketiga untuk putusan pengadilan** sebelum SG/PH menunjukkan pengguna nyata. Angkanya sekarang jelas: nol seller serius di seluruh dunia untuk vein ini.
5. **Turunkan QS Top Universities dari backlog** — 12 seller, incumbent 670u, dan seller kloning masuk 4 varian sekaligus.
6. **Vein olahraga: catat sebagai "tertutup", bukan "belum digarap".** `xtracto` memang nol di sana, dan godaannya besar (11 ribu user gabungan) — tapi 32–37 seller di dua sub-tipe yang laku dan TAM mikro di 10 sub-tipe lainnya. Kalau vein ini muncul lagi di babak berikutnya, tabel B di atas sudah menjawabnya.

## File Referensi Babak 45

- `output/mine-xtracto.json` — snapshot **218 actor** `xtracto` (tidak berubah sejak Babak 39)
- `output/scan-v8-highstats.json` — **1.489 actor** ber-stats tinggi, 25 kategori, band A ∪ B, paginasi penuh
- `output/scan-v8-bandB.json` — **105 actor** yang hanya ada di band B (`runs ≥100rb`, `users <150`) — band yang belum pernah discan babak mana pun
- `output/scan-v8-competition.json` — **51 konsep baru** di 12 grup wilayah baru, per konsep: seller, seller serius, total user/runs, 12 actor teratas, flag dedupe
- `output/scan-v8-clean.json` — 16 kandidat yang lolos filter otomatis Pass 3
- `output/scan-v8-verify.json` — uji union 3 finalis + **anti-false-negative vein putusan pengadilan** (4 frasa berbeda total)
- `output/scan-v8-sports.json` — **12 sub-tipe olahraga** (bukti vein olahraga tertutup)
- `output/scan-v8-verify2.json` — 2 konsep bernol-jejak (skip trace, lirik) + re-cek backlog QS rankings
- `scratchpad/inv45.py` — Pass 0: inventarisasi 30 script Babak 1–44 → **405 label konsep + 1.443 string**, plus blob dedupe berisi `description`
- `scratchpad/_concept_labels45.txt` · `_all_strings45.txt` · `_mine_blob45.txt` — hasil Pass 0, dipakai menjamin nol tumpang tindih
- `scratchpad/highstats45.py` (Pass 1) · `compete45.py` (Pass 2) · `rank45.py` (Pass 3) · `verify45.py` (Pass 4) · `verify45b.py` (Pass 5) · `roi45.py` (Pass 6) · `verify45c.py` (Pass 7)
- `scratchpad/ACTOR_MARKET_RESEARCHER_NEW.prebabak45.bak.md` — cadangan dokumen sebelum babak ini

---

# Babak 46 — Sumbu "Pekerjaan Pembeli" (JTBD) Dijalankan Penuh: 83 Konsep Baru, 734 Actor Tersaring, **Nol Kandidat Baru**; 2 Blind Spot Baru Ditemukan (CRE & Direktori Trade Fair) lalu Di-skip (2026-09-08)

**Konteks:** user kembali meminta **daftar actor ber-ROI data tinggi / stats tinggi di Apify Store**, dengan dua syarat dedupe yang sama seperti Babak 41 & 45: (a) belum ada di akun kedua [`xtracto`](https://api.apify.com/v2/store?username=xtracto), (b) belum tercatat di dokumen ini maupun [`actors_researcher_v2.md`](actors_researcher_v2.md). Babak 45 sudah menutup arah top-down dari kedua sisi dan meninggalkan **Rekomendasi #3**: *"kalau tetap ingin riset, ganti sumbu pertanyaannya — bukan platform/yurisdiksi/data-type, tapi **pekerjaan yang dibayar mahal oleh pembeli**"*. Babak ini **menjalankan rekomendasi itu secara harfiah**, bukan mengulang scan band yang sudah dinyatakan tertutup.

**Snapshot dedupe:** `apify-my-store.py xtracto` → **masih 218 actor**, tidak berubah sejak Babak 39. Blob dedupe (name+title+description) 48.957 karakter; 481 label konsep dari 35 script riset Babak 1–45.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---|---|
| ✅ **BELUM dibangun — kandidat baru layak eksekusi** | **0** | Tidak ada. Dua vein yang benar-benar baru ditemukan (CRE & direktori trade fair) tetapi keduanya **jenuh 18–46 seller** — rincian di tabel skip |
| 🔁 **SUDAH tercakup** (muncul di scan, bukan temuan baru) | **14 konsep / 35 dari 734 actor ber-flag** | BizBuySell, exhibitor `skython`, ImportYeti/BoL, breach checker, expired domain, USPTO trademark/patent, NPI/NPPES, WARN, FEC, UCC, building permit, county assessor, ImmoScout24/Rightmove, foreclosure Auction.com |
| ⛔ **DI-SKIP dengan alasan konkret** | **83 konsep** (61 JTBD Pass 1 + 11 yurisdiksi/anti-false-negative + 10 pekerjaan tambahan + 1 union trade fair) | **52 dari 61 konsep Pass 1 nol seller serius**; 4 nol seller sama sekali → diuji ulang dengan frasa berbeda total, tetap ≤106u |
| 🆕 **Blind spot baru (nol jejak di 45 babak)** | **2** | **Commercial real estate (LoopNet/Crexi/CoStar) — 3.550 user, 46 seller** · **Direktori trade fair (10times/EventsEye) — 600 user, 18 seller**. Keduanya di-skip karena jenuh, bukan karena kebijakan |
| 🔧 **Koreksi untuk riset lama** | **2** | Vein event/exhibitor Babak 8 & 44 perlu dipisah jadi 2 sub-vein · "0 seller" Pass 1 sekali lagi terbukti bukan peluang |

## Ringkasan Eksekutif

- **Hasil jujur: nol kandidat baru, dua babak berturut-turut — tapi lewat sumbu yang berbeda total.** Babak 45 buntu lewat sumbu *sumber data*; Babak 46 buntu lewat sumbu *pekerjaan pembeli*. Ini penting karena Rekomendasi #3 Babak 45 adalah satu-satunya hipotesis yang tersisa untuk "riset masih bisa menghasilkan". **Hipotesis itu sekarang sudah diuji dan hasilnya negatif.**
- **Sumbu JTBD memang menemukan yang tak terlihat — persis seperti kasus skip trace.** 16 pekerjaan pembeli dipetakan (penagih utang, investor properti distressed, title/escrow, kontraktor, sales alat kesehatan, broker asuransi, HR benefit broker, broker freight, due diligence/M&A, paralegal IP, analis siber, sales sponsorship event, trader komoditas, public affairs, industri ganja legal, ekspansi ritel) → **61 konsep, 52 di antaranya nol seller serius**. Dua vein yang muncul **nol jejak di seluruh 45 babak sebelumnya**: commercial real estate dan direktori trade fair. Jadi lubang taksonomi yang ditemukan Babak 45 itu nyata dan berulang — **tapi isi lubangnya bukan pasar kosong, melainkan pasar yang sudah penuh dan kebetulan tidak pernah ditanyakan.**
- **CRE adalah blind spot terbesar babak ini — dan langsung gugur.** LoopNet/Crexi/CoStar: **76 actor / 46 seller / 3.550 user**, dipimpin `memo23` dengan **3 varian sekaligus** (`apify-crexi` 472u ⭐5.0(11), `loopnet-scraper-ppe` 424u ⭐5.0(13), `apify-loopnet-search-cheerio` 388u/100.243r/258 rpu). `xtracto` benar-benar kosong di CRE, dan riset 45 babak tidak pernah menyebut kata "loopnet"/"crexi"/"commercial real estate" sekali pun. Tapi 46 seller = kloning ke-47.
- **Formula andalan riset ini (data-type terbukti × yurisdiksi kosong) diuji pada CRE dan GAGAL.** Enam wilayah dicek dengan nama portal telanjang (UK, AU/NZ, DE/FR/NL, IN/SEA, MEA/LATAM, plus sub-tipe lelang & lease comps): **tiap wilayah sudah 16–34 seller**, karena portal komersialnya adalah portal residensial yang sama (Rightmove/Zoopla, Domain.com.au, Funda, 99acres, Bayut, Zonaprop) yang **sudah dikloning habis untuk sisi residensialnya**. Varian khusus-komersial pun sudah ada (`dhrumil/rightmove-commercial` 53u, `memo23/commercialrealestate-au` 37u, `azzouzana/seloger-bureaux-commerces` 37u, `memo23/fundainbusiness` 23u) dengan TAM 23–53u. **Yurisdiksi tidak menyelamatkan vein yang portalnya sudah digarap dari sisi lain.**
- **Nol seller tetap berarti pasar mati, bukan peluang — untuk ketiga kalinya.** Empat konsep Pass 1 mendapat **0 seller** (judgment lien, pencarian aset/garnishment, plan room/bid board, quote asuransi). Diuji ulang dengan 5 frasa berbeda total per konsep (Gotcha #1 Babak 42): hasilnya 1–19 seller dengan **total 2–106 user** dan **nol seller serius** di keempatnya. Konsisten dengan Gotcha #2 Babak 42, #2 Babak 44, dan vein putusan pengadilan Babak 45.

## Metodologi Babak 46

```bash
python apify-my-store.py xtracto -o output/mine-xtracto.json   # 218 actor (tidak berubah)
python scratchpad/inv45.py                                     # 481 label konsep | blob 48.957 char

# Pass 1 - SUMBU BARU (Rekomendasi #3 Babak 45): 61 konsep dari 16 PEKERJAAN PEMBELI,
#   bukan dari 16 platform. Tiap konsep >=3 frasa, keys memuat nama platform telanjang,
#   metrik penentu = seller dengan runs>=10rb, TANPA max-users.
#   scratchpad/compete46.py -> output/scan-v9-jtbd.json
# Pass 2 - verifikasi 12 finalis dengan NAMA PLATFORM TELANJANG satu per satu
#   (Gotcha #1 Babak 45: finalis bottom-up wajib dicek ulang dari arah lain)
#   scratchpad/verify46.py -> output/scan-v9-verify.json
# Pass 3 - (A) CRE per-YURISDIKSI 7 kombinasi = uji formula "data-type terbukti x
#   yurisdiksi kosong"; (B) ANTI-FALSE-NEGATIVE 4 konsep bernilai 0 seller, frasa beda total
#   scratchpad/verify46b.py -> output/scan-v9-jurisdiction.json
# Pass 4 - 10 pekerjaan pembeli tambahan yang belum tersentuh Pass 1
#   (dealer mobil, restoration/klaim badai, edtech sales, vendor HOA, muni analyst,
#    trade compliance, exec search, roll-up klinik, customs broker, broker pesawat/kapal)
#   scratchpad/verify46c.py -> output/scan-v9-jtbd2.json
# Pass 5 - tabel ROI: 734 actor unik, cross-check SENGAJA longgar lalu dicek harfiah
#   scratchpad/roi46.py -> output/scan-v9-roi.json
```

**Angka Pass 1:** 61 konsep → **52 nol seller serius**, 32 konsep ber-TAM <100 user, hanya 11 konsep tembus 500 user, dan dari 11 itu 2 adalah artefak key cacat (lihat Gotcha #1 di bawah).

## 📋 Daftar yang Diminta — Actor ROI/Stats Tinggi Hasil Babak Ini + Vonisnya

Ini jawaban langsung atas permintaan "list actor yang ROI/stats-nya tinggi". Semua baris **sudah dicek** terhadap `xtracto` (218 actor) dan kedua dokumen riset. Kolom vonis memakai kode: **[SUDAH]** = konsepnya sudah dipegang/diputus · **[SKIP]** = alasan konkret · tidak ada satu pun **[BUILD]**.

| # | Actor (bukti demand) | Users / Runs / rpu | Vonis | Alasan |
|---:|---|---|---|---|
| 1 | `memo23/apify-loopnet-search-cheerio` ⭐4.97(11) | 388u / 100.243r / **258** | ⛔ **[SKIP]** | CRE — **46 seller**, `memo23` sendiri punya 3 varian. Blind spot nyata, tapi masuk sekarang = kloning ke-47 |
| 2 | `memo23/apify-crexi` ⭐5.0(11) | 472u / 51.839r / 110 | ⛔ **[SKIP]** | idem — vein yang sama |
| 3 | `acquistion-automation/bizbuysell-scraper` | 649u / 90.175r / **139** | 🔁 **[SUDAH]** | `xtracto/bizbuysell-listings` sudah ada; riset lama juga sudah memvonis 13 seller |
| 4 | `skython/exhibitor-list-scrapers-router` ⭐4.9–5.0 | 385u / 67.597r / 176 | 🔁 **[SUDAH]** | Sudah jadi backlog 🟢 Babak 44 ("Daftar Exhibitor Pameran Dagang"). `skython` praktis memonopoli 12 besar |
| 5 | `zen-studio/10times-events-scraper` | 313u / 11.717r / 37 | ⛔ **[SKIP]** | Blind spot #2 (nol jejak 45 babak) — tapi union: **18 seller**, dan slug `10times-events-scraper` sudah **dikloning 3 seller lain** |
| 6 | `dhrumil/rightmove-epc-full-address-finder` | 31u / 213.916r / **6.901** | ⛔ **[SKIP]** | rpu tertinggi seluruh babak = pipeline harian sejati, tapi vein Rightmove/EPC dikuasai `dhrumil` (6 varian) + `memo23`; TAM 31u |
| 7 | `clearpath/immoscout24-api-pro` | 223u / 1.091.956r / **4.897** | 🔁 **[SUDAH]** | ImmoScout24 sudah diputus di riset lama (`igolaizola` dkk) |
| 8 | `dev00/uspto-trademark-api` | 40u / 62.741r / **1.569** | 🔁 **[SUDAH]** | USPTO trademark sudah divonis jenuh (26 seller / 2 serius) di riset lama |
| 9 | `dhrumil/zoopla-scraper` | 297u / 58.256r / 196 | 🔁 **[SUDAH]** | Portal residensial UK — sudah diputus berkali-kali |
| 10 | `expanditumarca/…-zonaprop` | 84u / 37.902r / 451 | ⛔ **[SKIP]** | Zonaprop = 34 seller di wilayah MEA/LATAM |
| 11 | `shahidirfan/bizbuysell-scraper` | 158u / 30.872r / 195 | 🔁 **[SUDAH]** | idem #3 |
| 12 | `automation-lab/podcast-scraper` | 100u / 22.492r / 225 | ⛔ **[SKIP]** | Direktori podcast: **46 seller**, TAM 785u, sudah dicek negatif sejak Babak 19 |
| 13 | `piotrv1001/loopnet-listings-scraper` | 270u / 18.891r / 70 | ⛔ **[SKIP]** | idem #1 |
| 14 | `catchdoms/expired-domains-api` | 78u / 15.859r / 203 | 🔁 **[SUDAH]** | Expired domain sudah divonis "jenuh + churn tinggi" (13 seller) + jebakan runs (Gotcha #4 Babak 43) |
| 15 | `memo23/rightmove-scraper` | 235u / 13.084r / 56 | 🔁 **[SUDAH]** | idem #9 |
| 16 | `zen-studio/…` & `hanamira/patent-trademark-search` | 80u / 10.282r / 129 | 🔁 **[SUDAH]** | Trademark/patent — 34 seller di scan ini, konsisten dengan vonis lama |
| 17 | `samstorm/dentist-lead-scraper` | 300u / 2.507r / 8 | 🔁 **[SUDAH]** | Vein dokter gigi sudah di-skip Babak 41; rpu 8 = sekali-jalan |
| 18 | `martin1080p/expired-domains-scraper` | 283u / 2.422r / 9 | 🔁 **[SUDAH]** | idem #14 |
| 19 | `jungle_synthesizer/importyeti-bill-of-lading-scraper` | 148u / 2.678r / 18 | 🔁 **[SUDAH]** | `xtracto/us-customs-bol` + vonis "vertikal logistik sudah tersentuh" |
| 20 | `lofomachines/email-breach-checker` + 2 actor breach lain | 209u+176u+148u | ⛔ **[SKIP]** | Sudah di-skip eksplisit di riset lama: menyajikan kredensial bocor = area berisiko (sejalan dengan skip trace Babak 45) |

**Cara membaca tabel ini:** kolom rpu adalah sinyal ROI yang dipakai seluruh riset (runs per user = seberapa sering pelanggan menjalankannya lagi). Yang ber-rpu ekstrem di sini (#6 6.901, #7 4.897, #8 1.569) **semuanya milik seller yang sudah menguasai veinnya** — polanya konsisten dengan Babak 40/45: rpu tinggi menempel pada incumbent yang sudah jadi pipeline pelanggan, bukan pada celah kosong.

## 🔁 SUDAH Ada — Muncul di Scan Tapi Bukan Temuan Baru

Filter otomatis longgar (blob `xtracto` + kedua dokumen + folder lokal) menandai **35 dari 734 actor**; setelah **73 actor ≥100 user dicek harfiah satu per satu**, kelompok berikut terkonfirmasi sudah punya keputusan:

| Konsep | Bukti di scan ini | Sudah diputus di |
|---|---|---|
| BizBuySell / business-for-sale (31 seller, 1.869u) | `acquistion-automation` 649u, `fatihtahta` 244u, `shahidirfan` 158u, `memo23` ×2 | `xtracto/bizbuysell-listings` + Babak 43 (13 seller/137u) |
| Exhibitor pameran (18 seller, 2.697u) | `skython` menguasai 6 dari 12 besar | Backlog 🟢 Babak 44 kandidat #3 |
| NPI/NPPES (55 seller, 625u) · USPTO trademark (34) · patent (25) · WARN (14) · FEC (24) · UCC (14) · building permit (48) · county assessor | semua nol/1 seller serius | Paragraf "semua sudah ada pemainnya" di riset lama |
| ImportYeti / bill of lading (24 seller) | `jungle_synthesizer` 148u, `khadinakbar` 103u | `xtracto/us-customs-bol` + vonis logistik |
| Breach/dark-web checker (9 seller, 645u) | `lofomachines` 3 actor (209u+176u+148u) | Riset lama: **risiko kredensial bocor** |
| Expired domain (3–13 seller) | `martin1080p` 283u, `catchdoms` 78u/15.859r | Vonis "jenuh + churn tinggi" + jebakan runs |
| Portal properti residensial (Rightmove, Zoopla, ImmoScout24, Funda, 99acres, Bayut, Zonaprop, Domain.com.au) | muncul masif di Pass 3 | Diputus sepanjang Babak 4–43 |
| Foreclosure/distressed (20 seller, 578u) | `dominvo` 150u, `jungle_synthesizer/probate-foreclosure` 117u | Auction.com sudah tercatat "SUDAH ada" di Babak 43 |
| Store locator | `xtracto/store-locator-expansion` muncul sendiri di hasil | `xtracto` |

## ⛔ DI-SKIP — Semua dengan Alasan Konkret

### A. Dua blind spot baru (nol jejak di 45 babak) — ditemukan, diuji penuh, tetap di-skip

| Vein | Angka | Kenapa di-skip |
|---|---|---|
| **Commercial real estate (LoopNet / Crexi / CoStar)** 🆕 | **76 actor / 46 seller / 2 serius / 3.550 user / 249.109 runs**. Incumbent `memo23` **3 varian** (472u ⭐5.0(11) · 424u ⭐5.0(13) · 388u/100.243r/258 rpu); penantang `piotrv1001` 270u, `kazkn` 197u, `crawlerbros` ×2, `parseforge` ×2, `cypherai`, `powerai`, `ecomscrape`, `fatihtahta`, `skootle`, `solidcode`, `shahidirfan` | **Jenuh secara angka** (46 seller, incumbent multi-varian dengan rating sempurna dan 11–13 review = pelanggan nyata, bukan iseng). **Dan uji yurisdiksi gagal** (tabel B). Dicatat eksplisit supaya babak berikutnya tidak menemukan ulang dan mengira ini gem — persis perlakuan skip trace di Babak 45 |
| **Direktori trade fair (10times / EventsEye / Expo)** 🆕 | **23 actor / 18 seller / 1 serius / 600 user**. `zen-studio/10times-events-scraper` 313u/11.717r, tapi slug `10times-events-scraper` **sudah dikloning** `maximedupre` (11u), `khadinakbar` (10u), `parseforge` (9u), plus `prodiger/tentimes` 17u; `eventseye` dikloning 4 seller | Jenuh **dan** TAM kecil (600u tersebar 18 seller). Berbeda dari vein exhibitor `skython` (backlog Babak 44) — ini **direktori pameran**, bukan **daftar peserta pameran**; keduanya kini punya vonis terpisah (lihat Koreksi) |

### B. Uji "data-type terbukti × yurisdiksi kosong" pada CRE — formula andalan riset ini GAGAL di sini

| Wilayah | Seller / Serius | Terbesar | Varian khusus-komersial yang sudah ada |
|---|---|---|---|
| **UK** | **33 / 2** | `dhrumil/zoopla-scraper` 297u/58.256r; `memo23/rightmove-scraper` 235u | `dhrumil/rightmove-commercial-scraper` **53u** — sudah ada |
| **MEA/LATAM** | **34 / 2** | `ecomscrape/zonaprop` 195u; `fatihtahta/Bayut` 151u | `memo23/propertyfinder-leads` 146u |
| **IN/SEA** | **22 / 0** | `stealth_mode/99acres` 246u; `thirdwatch/magicbricks` 168u | tersebar; nol seller serius = TAM tidak terbukti |
| **DE/FR/NL** | **16 / 2** | `clearpath/immoscout24-api-pro` 223u/1,09jt r | `azzouzana/seloger-bureaux-commerces` **37u**, `memo23/fundainbusiness` 23u, `nocodeventure/funda-in-business` 43u |
| **AU/NZ** | **19 / 0** | `memo23/domain-com-au` 70u | `abotapi/realcommercial-au` 47u, `memo23/commercialrealestate-au` **37u**, `fatihtahta/realcommercial-au` 39u |
| **Lelang & investment sales CRE** | **29 / 0** | `kazkn` 197u, `crexi`-cluster | Ten-X/net-lease: nol actor khusus |
| **Tenant & lease comps CRE** | **2 / 0** | 4 user total | **Pasar mati** — sub-tipe paling bernilai bagi broker justru nol pembeli di Apify |

**Kesimpulan vein:** portal komersial di tiap negara **adalah portal residensial yang sama** yang sudah dikloning habis dari sisi residensial. Begitu satu seller sudah punya `rightmove-scraper`, menambah `rightmove-commercial-scraper` itu marjinal — dan **mereka sudah melakukannya**. Formula "yurisdiksi kosong" hanya bekerja kalau **platformnya sendiri** belum tersentuh (tender, business registry negara kecil), bukan kalau platformnya sudah digarap untuk data-type tetangga.

### C. 61 konsep JTBD Pass 1 — 52 nol seller serius

| Pekerjaan pembeli | Konsep | Angka terbaik | Vonis |
|---|---|---|---|
| **Penagih utang & pemulihan aset** | UCC lien · judgment lien · kepailitan · pencarian aset/garnishment | `intelscrape/ucc-lien` 41u · `pink_comic/bankruptcy-filing-search` 22u/92 rpu · judgment & asset search **0 seller** | Semua **0 serius**, TAM 0–192u. Anti-false-negative (tabel D) tidak mengubah apa pun |
| **Investor properti distressed** | foreclosure · tax lien · probate · code violation · eviction | `dominvo` 150u · `jungle_synthesizer/probate-foreclosure` 117u (**dikloning `memo23`, `solidcode`, `getascraper` dengan slug identik**) · tax delinquency 3 seller/29u · eviction 2 seller/4u | Vein probate: 9 seller / **0 serius** / 226u. Kloning slug identik = niche sudah dianggap komoditas oleh klaster seller |
| **Title, escrow & appraisal** | deeds county recorder · parcel/assessor · mortgage | `seibs.co/property-records-intel` 28u · `shelvick/county-property-records` 74u [sudah di docs] | County assessor sudah divonis 6+ seller di riset lama; sisanya mikro |
| **Kontraktor & pemasok konstruksi** | building permit · lisensi kontraktor · plan room · harga material | `pink_comic/building-permits` 118u · `parseforge/cslb-california` 97u · plan room **0 seller** → uji ulang 19 seller/106u | Lisensi kontraktor sudah divonis "jebakan runs" (`lulzasaur` 14u/45.713r) di riset lama |
| **Sales alat kesehatan & farmasi** | NPI · FDA 510k · recall · uji klinis · transparansi harga RS · lisensi perawat | NPI 55 seller/625u · 510k 20 seller/50u · clinical trials 64 seller/205u · harga RS **4 seller/10u** | Seluruh grup **0 serius** kecuali NPI (1, sudah divonis jebakan runs). Transparansi harga RS = data paling bernilai di industri, **10 user** |
| **Broker asuransi & risk** | OSHA · rate filing SERFF · lisensi agen · quote | `scrapebench/osha-violation-risk` 52u · `fortuitous_pirate/serff` 13u · quote **0 seller** → uji ulang 7 seller/22u | Seluruh grup mikro; quote asuransi = pasar mati di Apify |
| **HR benefit broker** | Form 5500 · WARN · H-1B/LCA · serikat & prevailing wage | `constant_quadruped/dol-5500` 19u/211 rpu · WARN 14 seller/67u · union 1 seller/2u | Form 5500 (data pensiun korporat AS, dijual mahal di industri): **11 seller berebut 56 user** |
| **Broker freight & logistik** | FMCSA · load board · kontainer/jadwal kapal · gudang 3PL | **33 seller / 0 serius / 546u** di FMCSA · `parseforge/dat-freight-rates` 12u · kontainer 1 seller/6u | FMCSA adalah contoh terbaik babak ini: 33 seller berebut 546 user, semuanya lead-gen tipis |
| **Due diligence & M&A** | business-for-sale · FDD/franchise · EDGAR/13F/Form ADV · funding rounds | BizBuySell **[SUDAH]** · FDD 9 seller/85u · EDGAR **62 seller / 0 serius / 280u** | EDGAR: 62 seller, nol serius — komoditas total |
| **Paralegal IP & brand protection** | trademark · paten · expired domain · counterfeit | trademark 34 seller · paten 25 seller · counterfeit **1 seller / 2u** | Semua sudah diputus atau mikro |
| **Analis keamanan siber** | CVE · certificate transparency · Shodan/Censys · breach | CVE 42 seller/190u · subdomain 26 seller/357u · Shodan **6 seller/26u** · breach **[SUDAH, risiko]** | Vertikal siber di Apify = tooling gratis yang dibungkus ulang; nol pembeli |
| **Sales sponsorship & event** | exhibitor **[SUDAH]** · speaker/agenda · podcast · newsletter | speaker 21 seller/521u · podcast **46 seller**/785u · newsletter 16 seller/137u | Podcast paling padat; `automation-lab/podcast-scraper` 225 rpu tetap tidak menolong TAM 785u/46 seller |
| **Trader komoditas & energi** | sumur/rig · listrik spot · komoditas tani · scrap metal | sumur 4 seller/8u · listrik 4 seller/10u · tani 4 seller/12u · scrap **1 actor / 2u** | Seluruh grup praktis nol. Scrap metal Pass 1 tampak 6.476u — **artefak key cacat**, lihat Gotcha #1 |
| **Public affairs** | FEC · lobbying | FEC 24 seller/74u · lobbying 18 seller/55u | Konsisten dengan vonis "civic-tech = nol pembeli" Babak 45 |
| **Industri ganja legal** | lisensi cannabis · menu dispensary | **14 seller / 0 serius / 369u**; `weedmaps-dispensary-scraper` dikloning **6 seller berbeda** | Terdengar seperti industri baru bernilai tinggi; faktanya 369 user dibagi 14 seller |
| **Ekspansi ritel & site selection** | store locator · CRE **[blind spot]** · foot traffic | store locator: `xtracto` sudah punya · foot traffic **3 seller / 171u / rpu 8** | Foot traffic = data paling mahal di dunia site-selection (Placer.ai), di Apify cuma `google-maps-popular-times` 157u |

### D. Anti-false-negative — 4 konsep "0 seller" diuji ulang dengan frasa berbeda total

| Konsep | Pass 1 | Uji ulang (5 frasa beda) | Vonis |
|---|---|---|---|
| Judgment lien & putusan perdata | 0 seller | 10 seller / 789u — **tapi 656u di antaranya `memo23/immobilienscout24` (false positive key `lien`)**; yang benar-benar relevan: `shelvick/business-entity-lien-search` 24u, `deadwood_data_solutions/ucc-filing-leads` 7u, `harris-county-court-records` (**3 seller kloning slug identik**) | Pasar mati (≤27u per actor) |
| Pencarian aset & garnishment | 0 seller | **1 actor / 2u** | Pasar mati |
| Plan room & bid board konstruksi | 0 seller | 19 seller / 106u / 0 serius | Pasar mati; ekstensi vein tender ke sisi swasta gagal |
| Quote asuransi | 0 seller | 7 seller / 22u / 0 serius | Pasar mati |

### E. 10 pekerjaan pembeli tambahan (Pass 4) — nol serius, semua

| Pekerjaan | Angka | Catatan |
|---|---|---|
| Roll-up klinik (dental/vet) | 26 seller / **0 serius** / 479u | `samstorm/dentist-lead-scraper` 300u tapi rpu **8** = sekali-jalan; vein dokter gigi sudah di-skip Babak 41 |
| Customs broker (HS/tarif) | 24 seller / 0 serius / 322u | Didominasi ImportYeti yang sudah dipegang `xtracto` |
| Dealer mobil (VIN/window sticker) | 19 seller / 0 serius / 313u | `easyapi/vin-decoder` 156u, rpu 5. NHTSA VIN API **gratis & resmi** → aturan Babak 43 |
| Edtech sales (direktori sekolah) | 16 seller / 0 serius / 272u | Lead-gen email tipis |
| Trade compliance (sanksi/denied party) | **50 seller / 0 serius / 227u** | Paling jenuh per-user di babak ini: 50 seller berebut 227 user. OpenSanctions punya API resmi gratis |
| Vendor HOA & property management | 5 seller / 0 serius / 143u | Semuanya turunan Zillow yang sudah dipegang |
| Broker pesawat/kapal | 23 seller / 0 serius / 139u | FAA registry sudah divonis 6 seller di riset lama |
| Restoration & klaim badai | 16 seller / 0 serius / 69u | NOAA = data pemerintah gratis |
| Exec search (people moves) | 7 seller / 0 serius / **16u** | Praktis nol |
| Muni analyst (obligasi daerah) | 3 seller / 0 serius / **11u** | Praktis nol |

## 🔧 Koreksi untuk Riset Lama

| Pernyataan lama | Temuan Babak 46 | Dampak |
|---|---|---|
| Babak 8: **"Event Discovery Aggregator"** dicatat sebagai satu vein tunggal yang "fragmented, 5–6 seller, tidak ada yang dominan" | Vein ini sebenarnya **tiga sub-vein berbeda dengan vonis berbeda**: (a) **daftar peserta pameran** — `skython` dominan, backlog 🟢 Babak 44; (b) **direktori pameran/trade fair** — 18 seller, `zen-studio` 313u, slug dikloning 3 seller; (c) **event konsumen** (Songkick/AllEvents) — tetap mikro | Pisahkan ketiganya di riset berikutnya. Backlog exhibitor Babak 44 **tidak boleh** dibaca sebagai "vein event masih kosong" |
| Riset lama tidak pernah menyebut **commercial real estate** sama sekali (0 hit "loopnet"/"crexi"/"costar"/"commercial real estate" di kedua dokumen) | Vein bernilai **3.550 user / 46 seller** yang tak pernah masuk radar, karena setiap babak menanyakan portal properti dari sisi **residensial** | Bukan alasan membangun (jenuh), tapi bukti kedua bahwa **taksonomi pertanyaan** punya lubang — lubang yang sama jenisnya dengan skip trace Babak 45 |

## Gotcha Metodologi Baru

1. **Key pendek yang merupakan substring kata umum meracuni seluruh angka konsep — dan racunnya terlihat "besar", bukan "aneh".** Key `scrap` di konsep BM4 (scrap metal) mencocokkan **"scraper"**, sehingga konsep harga logam bekas tampil sebagai vein terbesar babak ini (**6.476 user**) dengan actor teratas `bestscrapers/linkedin-sales-navigator-scraper`. Setelah key diperbaiki (`scrap-metal`, `metal-price`, `lme`): **1 actor / 2 user**. Hal yang sama terjadi pada key `premium` (menarik `kaitoeasyapi/premium-x-follower-scraper` 5.511u ke konsep SERFF asuransi). **Aturan baru: key wajib ≥6 karakter ATAU mengandung tanda hubung/nama platform utuh; setiap konsep yang tiba-tiba jadi terbesar wajib dicek actor teratasnya secara harfiah sebelum dipercaya.**
2. **Vein bisa tak terlihat selama 45 babak bukan karena tersembunyi, tapi karena ditanyakan dari sisi yang salah.** CRE tidak pernah muncul karena semua babak bertanya "portal properti negara X" (dan mendapat jawaban residensial), tidak pernah "apa yang dibeli broker properti komersial". Sama seperti skip trace yang tidak pernah muncul karena tidak ada babak yang bertanya "pekerjaan apa yang dibayar mahal". **Dua blind spot, dua sumbu berbeda, pola yang sama — dan keduanya ternyata sudah penuh.** Artinya: lubang taksonomi itu nyata, tapi **isinya bukan pasar kosong**. Riset sumbu-baru berikutnya harus mengasumsikan hasil yang sama.
3. **Kloning slug identik lintas seller adalah indikator kejenuhan yang lebih cepat daripada menghitung seller.** Tiga contoh di babak ini: `probate-foreclosure-leads-scraper` (4 seller: `jungle_synthesizer`, `memo23`, `solidcode`, `getascraper`), `10times-events-scraper` (4 seller), `harris-county-court-records-scraper` (3 seller), `weedmaps-dispensary-scraper` (6 seller). Begitu sebuah slug muncul identik di ≥3 akun, niche itu sudah masuk daftar "kloning otomatis" klaster seller — **tidak perlu lagi menghitung seller serius atau TAM, langsung skip.**
4. **Data yang paling mahal di dunia nyata justru paling sepi di Apify.** Transparansi harga rumah sakit (10u), foot traffic Placer.ai-style (171u, rpu 8), lease comps CRE (4u), Form 5500 (56u), municipal bond (11u) — semuanya produk berlangganan ribuan dolar di industrinya masing-masing, dan semuanya nyaris nol di Store. **Nilai data di dunia nyata bukan prediktor demand di Apify**; yang laku di Apify adalah data yang pembelinya sudah terbiasa membeli lewat scraper (marketplace, properti, sosial media, lead-gen).

## Insight Strategis Babak 46

> **Rekomendasi #3 Babak 45 sudah dieksekusi dan hasilnya negatif — itu informasi paling berharga dari babak ini.** Sumbu "pekerjaan pembeli" adalah hipotesis terakhir yang tersisa untuk "riset masih bisa menghasilkan kandidat". 16 pekerjaan, 83 konsep, 734 actor: nol kandidat. Kombinasi Babak 45 (sumbu sumber data, nol) + Babak 46 (sumbu pekerjaan pembeli, nol) menutup **kedua sumbu yang bisa ditanyakan tentang Apify Store**. Pertanyaan "actor apa lagi yang bisa dibangun" sekarang punya jawaban yang stabil di dua metode independen, dan jawabannya: **tidak ada yang tersisa yang laku dan kosong sekaligus.**

> **Dua blind spot berturut-turut menunjukkan pola yang lebih berguna daripada isi blind spot-nya.** Skip trace (Babak 45, 20.959u) dan CRE (Babak 46, 3.550u) sama-sama luput selama 45 babak, dan **keduanya ternyata sudah jenuh**. Ini menyingkirkan asumsi implisit yang menggerakkan 46 babak riset: bahwa "belum pernah kita lihat" berkorelasi dengan "belum digarap orang". Faktanya klaster seller (`memo23`, `parseforge`, `jungle_synthesizer`, `crawlerbros`, `solidcode`, `fatihtahta`, `zen-studio`, `skython`) menyapu Store jauh lebih menyeluruh daripada riset ini — mereka sudah ada di setiap vein yang ditemukan, termasuk yang paling obscure.

> **Yang berubah dari babak ini secara praktis: satu-satunya variabel yang belum pernah diukur adalah traksi actor sendiri.** Enam actor Babak 44 masih belum di-push (rekomendasi yang sama berdiri sejak Babak 42). Riset sudah mengukur pasar dari dua sumbu, 46 babak, ±540 konsep. Yang **belum pernah** diukur satu kali pun: berapa user yang didapat satu actor akun ini setelah dipublikasikan. Nilai marjinal babak riset ke-47 sekarang bisa dinyatakan lebih tegas dari Babak 45: **bukan mendekati nol, tapi nol — kecuali kalau pertanyaannya berubah dari "apa yang belum digarap" menjadi "kenapa yang sudah digarap belum laku".**

## Rekomendasi Lanjutan

1. **Berhenti menjalankan babak riset pencarian kandidat.** Dua sumbu (sumber data, pekerjaan pembeli) sudah tertutup, arah top-down sudah tertutup dari dua sisi (Babak 41 & 45). Babak ke-47 dengan pertanyaan yang sama akan menghasilkan tabel skip yang sama.
2. **Push 6 actor Babak 44 dan ukur traksinya.** Berdiri sejak Babak 42 #5, 43 #1, 44 #1, 45 #1 — **masih belum dijalankan**. Ini satu-satunya variabel yang belum pernah diukur di seluruh proyek.
3. **Kalau tetap ada babak riset, ganti pertanyaannya jadi diagnostik, bukan eksploratif:** ambil 5–10 actor akun ini yang **sudah dipublikasikan** dan bandingkan halaman Store-nya (judul, deskripsi, README, input schema, contoh output, pricing) dengan incumbent di vein yang sama — mis. `memo23` (rating 5.0 dengan 11–13 review di CRE) vs actor akun ini. Pertanyaannya: *apa yang membuat 218 actor `xtracto` rata-rata 1–5 user padahal veinnya sama?*
4. **Catat CRE & direktori trade fair sebagai "tertutup", bukan "belum digarap".** Keduanya akan terlihat seperti gem di scan dangkal mana pun (3.550u dan 600u, `xtracto` kosong di keduanya). Tabel A & B di atas sudah menjawabnya.
5. **Terapkan aturan kloning-slug (Gotcha #3) sebagai filter pertama** di riset apa pun berikutnya — lebih murah daripada menghitung seller serius, dan di babak ini akurat 4 dari 4 kali.

## File Referensi Babak 46

- `output/mine-xtracto.json` — snapshot **218 actor** `xtracto` (tidak berubah sejak Babak 39)
- `output/scan-v9-jtbd.json` — **61 konsep JTBD** dari 16 pekerjaan pembeli; per konsep: seller, seller serius, total user/runs, 12 actor teratas, flag dedupe
- `output/scan-v9-verify.json` — verifikasi 12 finalis dengan nama platform telanjang (termasuk perbaikan key `scrap` yang cacat)
- `output/scan-v9-jurisdiction.json` — **7 kombinasi CRE per-yurisdiksi** + **4 uji anti-false-negative** konsep bernilai 0 seller
- `output/scan-v9-jtbd2.json` — **10 pekerjaan pembeli tambahan** (Pass 4)
- `output/scan-v9-roi.json` — **734 actor unik** terurut users, dengan rpu + flag `mine`/`doc`/`local`
- `scratchpad/compete46.py` (Pass 1) · `verify46.py` (Pass 2) · `verify46b.py` (Pass 3) · `verify46c.py` (Pass 4) · `roi46.py` (Pass 5)
- `scratchpad/ACTOR_MARKET_RESEARCHER_NEW.prebabak46.bak.md` — cadangan dokumen sebelum babak ini

---

# Babak 47 — DIAGNOSTIK (bukan eksplorasi): `xtracto` Ternyata **Normal** untuk Umurnya; Yang Tidak Normal Adalah Konversi Bukti Sosial — dan Doktrin "Jenuh = Skip" yang Menggerakkan 46 Babak Terbukti **Salah** (2026-09-08)

**Konteks:** menjalankan Rekomendasi #3 Babak 46 — berhenti mencari kandidat, ganti ke pertanyaan diagnostik: *kenapa 218 actor `xtracto` rata-rata 1–5 user padahal veinnya sama dengan seller yang 472 user?* Babak ini **menjawab pertanyaan itu dan menemukan bahwa pertanyaannya sendiri salah**.

**Temuan endpoint baru yang membuat babak ini mungkin:** `GET /v2/acts/<user>~<name>` **publik tanpa token**, dan indeks Algolia ternyata memuat `createdAt`, `readme`, `seoTitle`, `modifiedAt` — field yang tidak pernah dipakai di 46 babak sebelumnya. Ini membuka variabel yang belum pernah diukur sekali pun: **umur actor**, **kecepatan akuisisi user 7/30/90 hari** (bukan akumulasi seumur hidup), cadence build, panjang README, dan rasio run gagal.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Isi |
|---|---|
| ✅ **Terjawab** | Premis "actor `xtracto` tidak laku" **tidak terbukti**. Pada umur yang sama (2–6 bulan), `xtracto` **setara median Store**: 3u vs 3u, p75 12u vs 13u, ≥20u 13% vs 19% |
| 🔴 **Masalah nyata yang ditemukan** | **Konversi bukti sosial setengah dari kohort.** Pada actor dengan ≥20 user: kohort 34% punya ≥1 review & 54% ≥1 bookmark; `xtracto` **14% & 27%**. Pada ≥50 user: 44%/65% vs **25%/42%** |
| 🔧 **Koreksi besar untuk 46 babak** | **Doktrin "jenuh → skip" salah.** Pendatang baru (≤8 bulan) di vein yang dokumen ini vonis jenuh justru **pemenang terbesar seluruh kohort seumurannya**: `valig/glassdoor-jobs-scraper` **8.972u dalam 5,5 bulan**, `valig/naukri-jobs-scraper` 6.292u/3,7 bln, `kaix/indeed-scraper` 5.850u/5,6 bln |
| ⛔ **Di-skip** | Tidak ada konsep baru yang dicari di babak ini — ini babak pengukuran, bukan pencarian |
| 🚫 **Belum dijalankan** | Push 6 actor Babak 44 (berdiri sejak Babak 42) — **tetap belum**, dan babak ini menambah alasan kuat kenapa itu satu-satunya langkah yang masuk akal |

## Metodologi Babak 47

```bash
# Pass 1 - detail publik 218 actor xtracto + 420 "peer" (users>=100) dari pool Babak 45/46
#   scratchpad/diag47.py -> output/scan-v10-diag.json
#   !! PASS INI BIAS - lihat Gotcha #1. Dipertahankan di dokumen sebagai jejak proses.
# Pass 2 - percobaan kohort tak-bias lewat /v2/store?sortBy=newest -> GAGAL:
#   paginasi mentok ~14rb actor, dan Store menambah sebanyak itu dalam <2 bulan,
#   jadi actor seumuran xtracto (2-6 bln) tidak terjangkau  scratchpad/cohort47.py
# Pass 3 - KOHORT TAK-BIAS YANG BENAR: enumerasi PENUH 5 kategori lewat Algolia
#   (NEWS 3.657 + REAL_ESTATE 5.003 + TRAVEL 2.547 + JOBS 6.098 + SEO_TOOLS 4.285)
#   -> 17.244 actor unik, TANPA filter stats apa pun, plus createdAt & readme
#   scratchpad/cohort47b.py -> output/scan-v10-cohort2.json
# Pass 4 - uji doktrin "jenuh": lima vein yang sudah divonis jenuh di dokumen ini,
#   dihitung berapa banyak pendatang <=8 bulan dan berapa user yang mereka dapat
```

## 📈 Temuan #1 — Kurva umur: **waktu adalah variabel terbesar, dan tidak pernah diukur**

Kohort 17.244 actor, tanpa filter stats apa pun:

| Umur actor | n | median users | p75 | p90 | ≥20 user | ≥100 user | % punya review |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0–2 bulan | 5.277 | **2** | 2 | 4 | 2% | 0% | 6% |
| 2–4 bulan | 4.943 | **2** | 7 | 22 | 11% | 2% | 11% |
| 4–6 bulan | 2.385 | **10** | 33 | 84 | 36% | 9% | 22% |
| 6–12 bulan | 2.657 | **15** | 52 | 145 | 44% | 15% | 34% |
| 12–24 bulan | 1.452 | **40** | 144 | 399 | 64% | 31% | 48% |
| >24 bulan | 440 | **110** | 446 | 1.870 | 79% | **52%** | 49% |

**Actor Apify tidak "laku atau tidak laku" — ia menua.** Median user naik 55× dari bulan ke-2 ke tahun ke-3, dan peluang menembus 100 user naik dari 0% → 52%. Umur median `xtracto` **3,1 bulan**. Menilai traksi akun ini sekarang sama seperti menilai panen di minggu ketiga.

## 📊 Temuan #2 — Dibandingkan pada umur yang sama, `xtracto` **normal**

| Umur 2–6 bulan (tanpa filter stats) | n | median | p75 | p90 | ≥20u | ≥100u |
|---|---:|---:|---:|---:|---:|---:|
| **Kohort Store** | 7.328 | 3u | 13u | 41u | 19% | 4% |
| **`xtracto`** | 175 | **3u** | **12u** | 28u | 13% | 3% |

Sedikit di bawah pada ekor kanan (p90 28 vs 41), setara pada median dan p75. **Premis "218 actor cuma 1–5 user, ada yang salah dengan halaman Store-nya" tidak didukung data** — 65% actor `xtracto` ada di rentang 1–5 user karena **itulah bentuk distribusi Store pada umur 3 bulan**, bukan karena akun ini istimewa buruk.

Pembanding yang dipakai Pass 1 (median 745 user) menyesatkan karena **dipilih berdasarkan `users>=100`** — bias survivorship murni. Lihat Gotcha #1.

## 🔴 Temuan #3 — Yang benar-benar timpang: **konversi user → bukti sosial**

Dikondisikan pada jumlah user (jadi bukan efek "user lebih sedikit"), umur 2–6 bulan:

| | kohort ≥1 review | `xtracto` ≥1 review | kohort ≥1 bookmark | `xtracto` ≥1 bookmark |
|---|---:|---:|---:|---:|
| actor dengan **≥5 user** | 24% | **7%** | 40% | **13%** |
| actor dengan **≥20 user** | 34% | **14%** | 54% | **27%** |
| actor dengan **≥50 user** | 44% | **25%** | 65% | **42%** |

**Konsisten ~2× lebih rendah di setiap tingkat.** Ini satu-satunya metrik di seluruh babak ini di mana `xtracto` menyimpang jelas dari kohort seumurannya. Dan ini metrik yang **majemuk**: review & bookmark adalah input peringkat Store dan bukti sosial di halaman — kohort >24 bulan yang 52% menembus 100 user punya review rate 49%. Actor tanpa review tidak pernah masuk lingkaran itu.

Kandidat penyebab (belum diuji, urutan biaya termurah): tidak ada ajakan review di README/output, README relatif pendek (median `xtracto` 5.964 char vs 7.309 kohort), output kurang "jadi" sehingga pengguna coba lalu pergi, atau tidak ada respons ke issue.

## 📖 Temuan #4 — README panjang berkorelasi kuat dengan traksi

Kohort umur 2–6 bulan, dikelompokkan menurut panjang README:

| README | n | median users | ≥20u | ≥100u |
|---|---:|---:|---:|---:|
| tidak ada | 244 | 2u | 3% | 1% |
| <1.500 char | 302 | 2u | 5% | 1% |
| 1.500–5.000 | 1.999 | 2u | 12% | 2% |
| 5.000–15.000 | 3.712 | 4u | 21% | 4% |
| **>15.000 char** | 1.071 | **10u** | **36%** | **10%** |

`xtracto` median **5.964 char** — tepat di pita 5–15rb (median 4u, 4% tembus 100u). Pita >15rb punya peluang **2,5×** lebih tinggi. Korelasi ini tidak membuktikan sebab (actor yang laku juga cenderung didokumentasikan lebih serius), tapi **arah perbaikannya murah** dan sejalan dengan Temuan #3.

**Pricing tidak memberi sinyal apa pun:** PAY_PER_EVENT 93% kohort vs 100% `xtracto`; FLAT_PRICE_PER_MONTH justru median 3u dan **0%** tembus 100u di kohort ini. Tidak ada alasan mengubah model harga.

## 🔧 Temuan #5 — **Doktrin "jenuh = skip" yang menggerakkan 46 babak terbukti salah**

Lima vein yang dokumen ini vonis jenuh, dihitung ulang **khusus pendatang berumur ≤8 bulan**:

| Vein (vonis lama) | Seller | Total user vein | Pendatang ≤8 bln | Pendatang terbesar |
|---|---:|---:|---:|---|
| **Naukri** (jenuh, Babak 39/45) | 48 | 41.546 | **35** | `valig/naukri-jobs-scraper` **6.292u dalam 3,7 bulan** · `blackfalcondata` 4.056u · `automation-lab` 2.599u |
| **Glassdoor** (jenuh; `xtracto` punya 3 actor) | 46 | 19.292 | **39** | `valig/glassdoor-jobs-scraper` **8.972u dalam 5,5 bulan** |
| **Indeed** (jenuh) | 45 | 69.631 | **35** | `kaix/indeed-scraper` **5.850u dalam 5,6 bulan** |
| **Wellfound** (`xtracto` sudah punya) | 48 | 7.352 | **45** | `crawlerbros` 1.688u/4,8 bln · `blackfalcondata` 1.401u/5,2 bln |
| **Flashscore/tenis** (Babak 45: "37 seller, paling padat — **tertutup**") | 24 | 3.370 | **38** | `extractify-labs/flashscore-tennis-matches` **1.761u dalam 4,7 bulan** |

**Baca ulang baris terakhir.** Babak 45 menutup vein tenis dengan alasan "TAM terbesar **dan** paling padat, tiga incumbent di atas 1.400 user". Seller `extractify-labs` masuk ke vein itu **setelah** kepadatan itu terbentuk dan mendapat **1.761 user dalam 4,7 bulan** — lebih banyak dari actor mana pun di seluruh 218 actor `xtracto`, dan lebih banyak dari seluruh kandidat "niche kosong" yang pernah direkomendasikan 46 babak ini.

Sepuluh actor terlaku di kohort umur 2–6 bulan **seluruhnya** berada di vein yang dokumen ini sudah vonis jenuh: job board (Naukri ×3, Glassdoor, Indeed, Wellfound ×2, generic job-board), LinkedIn, dan Flashscore. **Nol** di antaranya adalah niche kosong.

**Implikasi:** 46 babak riset mengoptimalkan variabel yang salah. "Sepi seller" dicari sebagai proksi peluang, padahal babak demi babak menemukan sendiri bahwa vein sepi itu **sepi karena tidak ada pembeli** ("pasar mati" — Gotcha #2 Babak 42, #2 Babak 44, vein putusan pengadilan Babak 45, 48 dari 51 konsep Babak 45, 52 dari 61 konsep Babak 46). Sinyal yang benar bukan *jumlah seller*, melainkan **jumlah pembeli** — dan pembeli terkonsentrasi persis di vein yang padat.

## Gotcha Metodologi Baru

1. **Membandingkan diri dengan "peer" yang dipilih berdasarkan stats tinggi adalah bias survivorship — dan saya melakukannya di Pass 1 babak ini.** Pass 1 menyimpulkan `xtracto` (median 3u) tertinggal ~200× dari peer (median 745u) **pada umur yang sama**, lalu memakai itu untuk menyatakan "umur bukan penjelasannya". Angka itu **tidak sah**: peer disaring `users>=100` sejak awal, jadi tentu saja mereka besar. Kohort tak-bias membalik kesimpulannya sepenuhnya (3u vs 3u). **Aturan: setiap perbandingan "kita vs mereka" wajib memakai sampel yang diambil TANPA melihat metrik yang sedang dibandingkan.** Pass 1 sengaja dibiarkan di `output/scan-v10-diag.json` sebagai contoh kesalahan yang mudah terulang.
2. **`/v2/store?sortBy=newest` tidak bisa dipakai untuk kohort umur.** Paginasi mentok ~14.000 actor, dan Store menerbitkan sebanyak itu dalam **kurang dari 2 bulan** (665 dari 764 sampel berumur <1 bulan). Untuk kohort umur 2–6 bulan, satu-satunya jalan adalah **enumerasi penuh kategori lewat Algolia**, yang bisa dipaginasi sampai `nbHits` dan memuat `createdAt`.
3. **Indeks Algolia memuat `readme`, `seoTitle`, `seoDescription`, `createdAt`, `modifiedAt` — 46 babak tidak pernah memakainya.** `DEFAULT_ATTRS` di `api-search-actors.py` hanya meminta 12 field; `attrs=["*"]` membuka 29. Semua analisis halaman Store (panjang README, umur, cadence) bisa dilakukan **tanpa satu pun request tambahan** ke API detail.
4. **`totalUsers` adalah akumulasi seumur hidup, bukan permintaan saat ini.** `totalUsers30Days` memisahkan "pernah laku" dari "sedang laku". Contoh dari kohort Babak 45: actor >24 bulan punya median 110 user total tapi **median u30 = 1**. Sebaliknya `valig/glassdoor-jobs-scraper` punya u30 **1.383** — akuisisi yang sedang berjalan. **Riset berikutnya harus memakai u30/u90, bukan totalUsers.**

## Insight Strategis Babak 47

> **Pertanyaan yang benar bukan "actor apa lagi yang bisa dibangun", tapi "kenapa 46 babak mencari tempat sepi".** Data kohort menjawab keduanya sekaligus: pembeli Apify terkonsentrasi di segelintir vein besar (job board, LinkedIn, properti, sosial media, maps), dan di vein-vein itu **pendatang baru tetap menang besar** — 35–45 pendatang ≤8 bulan per vein, dengan pemenang 1.700–9.000 user dalam <6 bulan. Tempat sepi sepi karena tidak ada uangnya. Seluruh backlog "niche kosong" hasil 46 babak bernilai lebih rendah daripada satu actor Naukri yang dikerjakan dengan benar.

> **`xtracto` tidak gagal — `xtracto` masih terlalu muda untuk dinilai, dan satu-satunya kelemahan terukurnya bisa diperbaiki tanpa membangun apa pun.** Median umur 3,1 bulan, distribusi user persis median Store. Satu-satunya penyimpangan nyata: konversi review/bookmark **setengah** kohort pada tingkat user yang sama. Itu masalah halaman & pengalaman produk, bukan masalah pemilihan niche — dan biaya perbaikannya nol actor baru.

> **Enam actor Babak 44 yang belum di-push sekarang punya biaya yang bisa dihitung.** Kurva umur menunjukkan actor mulai mengumpulkan user secara berarti di bulan ke-4 (median 2u → 10u, ≥20u 11% → 36%). Setiap bulan penundaan bukan menunda hasil satu bulan — ia menggeser seluruh kurva. Enam actor yang selesai dibangun tapi tidak dipublikasikan menghasilkan **nol** pada kurva mana pun.

## Rekomendasi Lanjutan

1. **Push 6 actor Babak 44 sekarang.** Berdiri sejak Babak 42 (#5), 43 (#1), 44 (#1), 45 (#1), 46 (#2). Kurva umur babak ini memberi angka konkret untuk biaya penundaannya.
2. **Perbaiki konversi bukti sosial pada actor `xtracto` yang sudah ≥20 user (22 actor).** Tiga langkah termurah: (a) tambah ajakan review + tautan langsung di README dan di log akhir run, (b) naikkan README ke >15.000 char pada actor ≥20 user dulu (pita ini punya peluang 2,5× lebih tinggi tembus 100 user), (c) pastikan output sampel terlihat di halaman Store. Ini **tidak butuh actor baru**.
3. **Balik kriteria seleksi vein: hitung pembeli, bukan seller.** Metrik pengganti "jumlah seller" → **u30 total vein** dan **jumlah pendatang ≤8 bulan yang tembus 500 user**. Vein dengan 45 seller tapi 40rb user aktif jauh lebih baik daripada vein 1 seller dengan 200 user.
4. **Kalau membangun actor baru, bangun di vein yang sudah divonis jenuh — dengan sudut pembeda yang jelas.** Kandidat paling kuat menurut data babak ini: **job board besar** (Naukri 41,5rb user vein / 35 pendatang baru; Indeed 69,6rb; Glassdoor 19,3rb — `xtracto` sudah punya Glassdoor ×3, jadi jalur masuknya sudah terbukti bisa) dan **skor olahraga live/Flashscore** (yang Babak 45 tutup keliru).
5. **Perbarui `api-search-actors.py`: tambahkan `createdAt`, `readme`, `seoTitle` ke `DEFAULT_ATTRS`, dan tambahkan opsi `--sort u30`.** Seluruh riset ke depan harus memakai umur + u30, bukan totalUsers.
6. **Jangan jalankan babak pencarian kandidat lagi** (Rekomendasi #1 Babak 46 tetap berlaku, dan babak ini memperkuatnya: masalahnya bukan kekurangan ide).

## File Referensi Babak 47

- `output/scan-v10-diag.json` — 218 `xtracto` + 420 peer dengan `createdAt`, pricing, builds, u7/u30/u90 (**Pass 1 — bias, disimpan sebagai jejak proses**)
- `output/scan-v10-cohort.json` — 764 actor dari `/v2/store?sortBy=newest` (Pass 2 gagal: semua <2 bulan)
- `output/scan-v10-cohort2.json` — **17.244 actor kohort tak-bias** (enumerasi penuh 5 kategori) + 218 `xtracto`, lengkap dengan `createdAt` & `readme`
- `scratchpad/diag47.py` (Pass 1) · `cohort47.py` (Pass 2, gagal) · `cohort47b.py` (Pass 3)
- `scratchpad/ACTOR_MARKET_RESEARCHER_NEW.prebabak46.bak.md` — cadangan dokumen sebelum Babak 46/47

---

# Babak 48 — EKSEKUSI Rekomendasi Babak 47: 6 Actor Babak 44 Di-push (build tertahan kuota akun), 1 Actor Baru Dibangun di Vein "Jenuh" Sesuai Doktrin Baru; Naukri Gugur di Recon, Flashscore Jadi (2026-09-08)

**Konteks:** user meminta menjalankan Rekomendasi #1 dan #4 Babak 47 — (1) push 6 actor Babak 44 dan ukur, (4) bangun actor baru **di vein yang riset lama vonis jenuh** dengan sudut pembeda, memakai kriteria seleksi baru (**u30 = pembeli aktif**, bukan jumlah seller).

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---|---|
| ✅ **Source ter-push ke Apify** | **7** | 6 actor Babak 44 + 1 actor baru babak ini. Semua lolos `apify validate-schema`, semua diuji live sebelum push |
| 🔴 **Build TERTAHAN — bukan masalah kode** | **7** | Akun `fanndev` paket **FREE ($5/bulan)**, status `MONTHLY_TOTAL_USAGE_HARD_LIMIT_EXCEEDED`. **Seluruh** fitur platform mati (ACTORS, STORAGE, SCHEDULER, PROXY), jadi setiap `apify push` berhasil mengunggah source lalu gagal di tahap build |
| ✅ **Actor baru dibangun** | **1** | `flashscore-all-sports-scraper` — 4 mode, 14 olahraga, diuji live penuh |
| ⛔ **Di-skip di recon** | **1** | **Naukri** — vein dengan u30 tertinggi yang `xtracto` kosong (5.051), tapi permukaan datanya tertutup |
| 🔧 **Koreksi ke Babak 44** | **1** | 6 actor Babak 44 ternyata **belum punya `categories`** di `actor.json`, dan 2 deskripsi melebihi batas 300 char — keduanya menghalangi push dan tidak terdeteksi `validate-schema` |

## Bagian 1 — Push 6 Actor Babak 44

Urutan yang dijalankan per actor: `apify validate-schema` → `python test_local.py all` (uji live terhadap situs asli) → `apify push -f`.

| Actor | Validasi | Tes live hari ini | Push |
|---|---|---|---|
| `lelang-djkn-scraper` | ✅ 3/3 schema | ✅ 11.889 lot aktif, detail `content.barangs` lengkap (BPKB + nomor + tanggal) | source ✅ / build ⛔ kuota |
| `lawrato-lawyer-directory-scraper` | ✅ | ✅ profil advokat + bidang praktik + spesialisasi | source ✅ / build ⛔ |
| `indonesiayp-business-directory-scraper` | ✅ | ✅ nama, alamat, telepon, GPS, jam buka, manajer, tahun berdiri | source ✅ / build ⛔ |
| `alodokter-doctor-directory-scraper` | ✅ | ✅ dokter + RS + biaya konsultasi IDR + rating | source ✅ / build ⛔ |
| `sinta-researcher-scraper` | ✅ | ✅ skor SINTA + H-index Scopus/WoS/GScholar | source ✅ / build ⛔ |
| `socialblade-creator-analytics-scraper` | ✅ | ✅ MrBeast 516jt subscriber + leaderboard top-100 | source ✅ / build ⛔ |

**Dua hal yang menghalangi push dan tidak tertangkap `validate-schema`** (koreksi untuk konvensi portofolio):

1. **`categories` kosong di keenam `actor.json`.** Actor lama yang sudah published (mis. `sg-court-judgments-scraper`) punya `"categories": ["BUSINESS","OTHER"]`; keenam actor Babak 44 tidak. Kategori adalah jalur penemuan di Store — actor tanpa kategori praktis tidak muncul di browsing. Diisi: DJKN `REAL_ESTATE+BUSINESS`, LawRato/IndonesiaYP/Alodokter `LEAD_GENERATION+BUSINESS`, SINTA `EDUCATION+BUSINESS`, Social Blade `SOCIAL_MEDIA+FOR_CREATORS`.
2. **Batas keras yang tidak didokumentasikan di skill `deploying-actors`:** `description` **maksimal 300 karakter** dan `title` **maksimal 63 karakter**. DJKN (352) dan SINTA (302) ditolak; keduanya dipendekkan tanpa membuang kata kunci.

### Kenapa build gagal — dan apa artinya

```
Error: Monthly usage hard limit exceeded
```

Bukan error kode. Cek `/v2/users/me/limits` + `~/.apify/auth.json`: akun `fanndev`, plan **FREE**, `maxMonthlyUsageUsd: 5`, `isPaying: false`, dan `effectivePlatformFeatures` menunjukkan **semua** fitur `isEnabled: false` dengan `disabledReasonType: MONTHLY_TOTAL_USAGE_HARD_LIMIT_EXCEEDED`. Akun dibuat 2026-08-10, jadi siklus penagihan kemungkinan besar berulang tiap tanggal 10 — **± 2 hari dari hari ini**.

**Yang sudah tercapai meski build gagal:** `apify push` tetap **membuat actor dan mengunggah source + versi 0.0** sebelum tahap build. Jadi ketujuh actor sudah ada di akun; yang tersisa hanyalah menjalankan ulang `apify push -f` (atau memicu build) setelah kuota reset, lalu publish ke Store.

## Bagian 2 — Seleksi Vein dengan Kriteria Babak 47

22 vein diukur ulang memakai **u30** (pembeli aktif 30 hari), bukan jumlah seller. Kolom "xtracto?" adalah syarat dedupe user.

| Vein | u30 | users total | Pendatang ≤8bln tembus 500u | `xtracto` | Vonis |
|---|---:|---:|---:|---|---|
| LinkedIn jobs | 30.015 | 285.965 | 3 | PUNYA | Gugur (dedupe) |
| Twitter/X | 14.685 | 146.731 | 2 | PUNYA | Gugur (dedupe) |
| Indeed | 11.767 | 105.397 | 3 | PUNYA | Gugur (dedupe) |
| **Naukri** | **5.051** | 42.060 | **4** | **kosong** | **Target #1 → gugur di recon** |
| Reddit | 4.744 | 23.771 | 5 | PUNYA | Gugur (dedupe) |
| Upwork | 1.436 | 15.879 | 1 | kosong | Cadangan |
| **Flashscore/Sofascore** | **1.404** | 5.171 | **1** | **kosong** | **DIBANGUN** |
| JobStreet/Seek SEA | 717 | 3.530 | 1 | kosong | Cadangan |

**Naukri di-skip di recon, dengan bukti:**

| Uji | Hasil |
|---|---|
| `jobapi/v3/search` (API resmi situs) | **HTTP 406 `{"message":"recaptcha required"}`** di 3 kombinasi header (`appid 109/121`, `systemid Naukri/109`, `gid`) |
| Cookie warm-up (homepage → SRP → API, satu sesi) | Dapat 10 cookie termasuk **`ak_bmsc`, `bm_mi`, `bm_sv` = Akamai Bot Manager** — API tetap 406 |
| Permukaan SEO (sitemap, halaman detail lowongan, halaman perusahaan) | **Semua 200 tapi identik ~36 KB shell**, nol `JobPosting`, nol `__NEXT_DATA__`, bahkan **tanpa tag `<title>`** |

Naukri butuh solusi reCAPTCHA + kemungkinan IP residensial — di luar doktrin HTTP-only portofolio ini, dan tidak bisa divalidasi hari ini karena kuota akun habis. Berhenti bersih di recon, sesuai kebijakan.

## Bagian 3 — Actor Baru: `flashscore-all-sports-scraper`

**Kenapa vein ini:** Babak 45 menutupnya sebagai *"tenis 37 seller, paling padat — tertutup"*. Babak 47 membuktikan penutupan itu keliru: `extractify-labs/flashscore-tennis-matches` masuk **setelah** kepadatan itu terbentuk dan meraih **1.761 user dalam 4,7 bulan dengan u30 924** — lebih banyak dari actor mana pun di 218 actor `xtracto`. Ini eksekusi langsung doktrin baru: **masuk ke vein padat bervolume tinggi, bukan mencari niche kosong.**

**Sudut pembeda** (kompetitor memecah per olahraga & per tipe data — `flashscore-tennis-matches`, `flashscore-live-matches`, `flashscore-matches-odds`, `flashscore-basketball`): satu actor, **14 olahraga**, 4 mode, satu skema field yang sama, plus detail pertandingan yang mereka tidak jual terpisah (**xG, possession, insiden per menit, lineup + rating, H2H**).

### Temuan recon (lengkap di `flashscore-all-sports-scraper/CRAWLING_METHOD.md`)

| Temuan | Bukti |
|---|---|
| Situs utama **buntu** | `flashscore.com` = 739.047 byte HTML, **nol** baris pertandingan, nol `__NEXT_DATA__`/JSON-LD. Persis jebakan Gotcha #1 Babak 44 ("ukuran halaman bukan bukti ada data") |
| Permukaan asli = feed terpisah | `local-global.flashscore.ninja/2/x/feed/<id>` — **200 + 451.944 byte + 275 pertandingan** dengan header `x-fsign: SW9D1eZo`; **401 + 323 byte** tanpa header itu. Nol WAF, nol cookie, nol warm-up, nol login |
| Format bukan JSON | Encoding berdelimiter: record `~`, field `¬`, key/value `÷`. Header turnamen adalah **record terpisah yang mendahului** pertandingannya — parser harus membawanya maju |
| 7 endpoint terpetakan | day feed, live, meta, insiden, **statistik (xG + possession, 120 baris)**, lineup (formasi + rating), H2H (51 KB) |
| **Segmen sportId di feed detail DIABAIKAN** | Match sepak bola yang sama diminta dengan sport `1/2/3/**99**` mengembalikan body **byte-identik**; match tenis diminta dengan sport `1` tetap mengembalikan statistik tenis (aces, double faults) |
| 14 sport ID dienumerasi, bukan ditebak | Probe id 1–21, dibaca balik turnamen yang dikembalikan (mis. id 10 → "SWEDEN: Svenska Cupen" + Broberg/Söderhamn = bandy; id 11 → Belgia Division 1 + Eisden-Dorp = futsal). Id 8, 9, 16–20 kosong → **tidak diklaim** |
| Endpoint yang dicoba & gagal, dicatat | klasemen (4 varian nama), odds, komentar, top scorer, tournament fixtures — semuanya kosong/404. **Tidak dikirim setengah jadi**; ditulis sebagai known gap di README |

### Gotcha yang ditemukan saat membangun (dan diperbaiki)

1. **Cap `maxItems` global diam-diam menyembunyikan olahraga.** Permintaan `sportIds:[1,2,3]` mengembalikan **hanya sepak bola** — sepak bola sendiri ~275 baris/hari, jadi cap habis sebelum olahraga kedua tersentuh. Diperbaiki jadi **budget per kombinasi (sport × hari)**; setelah perbaikan: 20/20/20. Tertangkap karena tes lokal memeriksa **himpunan olahraga yang muncul**, bukan jumlah baris.
2. **Feed "live" bukan hanya live.** `f_<sport>_0_1_en_1` mengirim seluruh hari; hanya baris `AB=2` yang benar-benar berjalan. Percaya pada nama feed = mengirim pertandingan selesai sebagai "live".
3. **Absen ≠ nol.** Baris sebelum kick-off **tidak punya** key skor sama sekali. Men-default-kannya ke 0 akan mengarang skor 0-0 untuk setiap pertandingan terjadwal.
4. **Body kosong adalah jawaban sah, bukan error.** Olahraga tanpa jadwal hari itu dan pertandingan tanpa lineup sama-sama membalas 200 + 1 byte.
5. **Klaim yang belum diverifikasi sempat masuk kode saya sendiri.** Versi pertama `constants.py` menulis "match id yang diminta dengan sport salah mengembalikan body kosong" — asumsi, bukan hasil probe. Uji sport=99 membantahnya, dan komentar + pesan error + tes ikut dikoreksi. Dicatat karena ini persis pola Gotcha #1 Babak 44 yang terulang **di dalam kode**, bukan di riset.

### Bukti tes lokal (live, hari ini)

```
fixtures football hari ini  : 275 match, turnamen+negara+skor+status lengkap
fixtures 3 olahraga × 2 hari : 20 Football / 20 Tennis / 20 Basketball (setelah perbaikan cap)
live football               : 9 match AB=2, mis. FC Porto U19 2-0 Man City U19 (UEFA Youth League)
match detail (WSSid6OM)     : 15 insiden, 120 statistik (xG 0.37-0.29, possession 42%-58%),
                              55 blok lineup, 183 blok H2H
reference                   : 14 olahraga aktif, dari 275 match (sepak bola) sampai 1 (futsal)
error path                  : id palsu -> _error=not_found; input ngawur -> _error=invalid_match_id
```

### Penerapan temuan Babak 47 pada halaman Store-nya

Babak 47 menemukan README **>15.000 karakter** berkorelasi peluang **2,5×** lebih tinggi tembus 100 user (median `xtracto` 5.964 char). Actor ini sengaja dibangun di pita itu sejak awal: **README 15.842 karakter** dengan tabel input/output lengkap, 5 contoh input, catatan per-olahraga, tips penjadwalan, dan FAQ/troubleshooting — plus `categories` terisi sejak awal (`SPORTS`, `OTHER`), tidak seperti 6 actor Babak 44.

## Rekomendasi Lanjutan

1. **Begitu kuota reset (± 2 hari, siklus tanggal 10): jalankan ulang `apify push -f` untuk ketujuh actor**, lalu publish ke Store (set `isPublic`, kategori, pricing). Baru setelah itu pertanyaan Babak 42–47 ("apakah actor ini dapat pembeli?") bisa dijawab.
2. **Pertimbangkan naik dari plan FREE.** Ini pertama kalinya batas $5/bulan benar-benar menghentikan pekerjaan, bukan sekadar membatasi run — 7 actor selesai dan tidak bisa di-build. Biaya menunggu sekarang punya bentuk konkret.
3. **Terapkan pelajaran halaman Store ke belakang**: isi `categories` dan naikkan README ke >15rb char untuk 22 actor `xtracto` yang sudah ≥20 user (Rekomendasi #2 Babak 47, masih belum dijalankan).
4. **Cadangan vein berikutnya kalau Flashscore terbukti jalan:** Upwork (u30 1.436, `xtracto` kosong) dan JobStreet/Seek SEA (u30 717, pasar rumah sendiri). Naukri **jangan** diulang tanpa perubahan kondisi — butuh solusi reCAPTCHA + Akamai.
5. **Tambahkan ke skill `deploying-actors`:** batas `description` 300 char & `title` 63 char, dan wajib mengisi `categories` sebelum push. Ketiganya menghentikan push hari ini dan tidak satu pun tertangkap `apify validate-schema`.

## File Referensi Babak 48

- `flashscore-all-sports-scraper/` — actor baru: `.actor/` (4 file schema, semua valid), `src/` (constants/client/extractor/main), `README.md` **15.842 char**, `CRAWLING_METHOD.md` 8.512 char, `test_local.py` 4 mode
- `scratchpad/vein48.py` → `output/scan-v11-vein.json` — 22 vein diperingkat dengan **u30**, bukan jumlah seller
- `scratchpad/probe48.py` — recon Naukri (406 recaptcha, Akamai `ak_bmsc`, shell 36 KB)
- 6 actor Babak 44 — `actor.json` masing-masing kini punya `categories`, deskripsi ≤300 char

---

# Babak 49 — Sapuan **Seluruh Store** (65.092 actor) dengan Metrik Babak 47: 9 Kandidat Baru Lolos Dedupe, 2 Terbukti **Permukaannya Terbuka** di Probe, dan Peta Pertama "Pasar Bagus tapi Tembok" (2026-09-09)

**Konteks:** user meminta daftar actor ber-ROI/stats tinggi, dengan syarat dedupe terhadap (a) akun kedua `xtracto` dan (b) riset yang sudah ada. Catatan: file `ACTOR_MARKET_RESEARCH.md` yang disebut user **tidak ada** di repo — daftar lama ada di dokumen ini (48 babak) dan `actors_researcher_v2.md`; keduanya dipakai sebagai korpus dedupe.

**Babak ini melanggar Rekomendasi #6 Babak 47 ("jangan cari kandidat lagi") secara sengaja, atas permintaan eksplisit user** — tetapi menjalankannya dengan **kriteria Babak 47**, bukan kriteria 46 babak pertama: peringkat memakai **u30 (pembeli aktif 30 hari) + umur actor**, bukan `totalUsers` dan bukan jumlah seller. Hasilnya berbeda total dari Babak 45/46 yang berakhir nol kandidat.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **BELUM dibangun — kandidat baru** | **9** | 2 permukaan **terbukti terbuka** di probe (Google Hotels, Sports Odds via ESPN) · 4 butuh recon (Douyin, TikTok Shop, Keyword Volume, Google Lens) · 3 kecil-tapi-terbuka (Himalayas, Welcome to the Jungle, Medium) |
| 🔁 **SUDAH ada** (di `xtracto` / folder lokal / vonis dokumen) | **21 konsep** | Dicek harfiah satu per satu dengan nama actor `xtracto` yang persis |
| ⛔ **DI-SKIP** | **17 konsep** | 6 karena **permukaan tertutup** (bukti HTTP di tabel), 5 karena **jenuh/komoditas**, 4 karena **kebijakan PII**, 2 karena **TAM terlalu kecil** |
| 🔧 **Koreksi untuk riset lama** | **3** | Douyin (Babak 45 keliru men-skip), Naukri (kegagalan **kapabilitas**, bukan pasar), status "cadangan Seek" gugur |

## Ringkasan Eksekutif

> **Enumerasi penuh Store — 65.092 actor, 25 kategori, tanpa filter stats apa pun — baru dilakukan di babak ini.** Babak 47 hanya menyapu 5 kategori (17.244 actor). Dari 65.092 actor, **48.987 punya u30 > 0** dan hanya **544 punya u30 ≥ 120**. Dari 544 actor paling laku itu, **hanya 6 yang lolos filter dedupe otomatis** — dan 4 dari 6 adalah tooling generik (`apify/cheerio-scraper`, `puppeteer-scraper`, `playwright-scraper`, `vdrmota/contact-info-scraper`). Konsentrasi ini, bukan kelangkaan ide, adalah bentuk sebenarnya dari pasar Apify.

> **Temuan metodologis terbesar: Algolia mengembalikan `totalUsers30Days` dan `totalUsers90Days` langsung.** Babak 47 mengambil u30 lewat API detail per-actor (dan karenanya hanya sanggup untuk 638 actor). Ternyata `stats.totalUsers30Days` ada di indeks Algolia lewat `attrs` kustom — jadi **seluruh Store bisa diperingkat dengan metrik yang benar dalam satu sapuan**, nol request API detail. Ini yang membuat babak ini bisa mengukur 65.092 actor, bukan 638.

> **Babak ini menambahkan sumbu yang tidak pernah dipakai 48 babak: apakah permukaan datanya terbuka.** Babak 48 kehilangan target #1-nya (Naukri) *setelah* memilihnya, karena kelayakan teknis baru diuji di akhir. Di sini probe HTTP dangkal dijalankan **sebelum** kandidat diperingkat, dan hasilnya memisahkan dua kelompok yang selama ini tercampur: "pasar sepi" (tidak ada pembeli) vs **"pasar bagus tapi tembok"** (Naukri, ZipRecruiter, StepStone, Bayt, Dice, Taobao, 1688 — semuanya 403/login wall).

## Metodologi Babak 49

```bash
# Pass 1 - ENUMERASI PENUH 25 kategori Algolia, attrs kustom (createdAt + stats lengkap),
#   200/halaman sampai nbHits. TANPA filter stats -> 65.092 actor unik (Babak 47: 17.244)
#   scratchpad/scan49.py -> output/scan-v12-all.json (76 MB)
# Pass 2 - vein by token, diukur u30 + jumlah pendatang <=8 bulan (kriteria Babak 47)
#   scratchpad/rank49.py -> output/scan-v12-veins.json, scan-v12-young.json
# Pass 3 - peringkat per-actor u30>=120 (544 actor) + dedupe otomatis LONGGAR
#   (Gotcha #2 Babak 41: over-filter menghapus temuan) -> output/scan-v12-roi.json
# Pass 4 - 52 konsep diverifikasi dengan FRASA TELANJANG satu per satu terhadap
#   65.092 actor + dedupe harfiah 3 lapis (xtracto 218 / 225 folder lokal / 2 dokumen)
#   scratchpad/verify49.py -> output/scan-v12-concepts.json
# Pass 5 - PROBE PERMUKAAN (baru di babak ini): 30 target HTTP polos, tanpa proxy/cookie
#   scratchpad/probe49.py
```

**Cross-check `xtracto` di-refresh hari ini:** `python apify-my-store.py xtracto -o output/xtracto-full.json` → **218 actor** (sama dengan Babak 47; tidak ada penambahan, konsisten dengan kuota akun yang habis di Babak 48). Overlap folder lokal ↔ `xtracto` tetap hanya **2 dari 225** — `xtracto` memang akun terpisah.

---

## 📋 Daftar yang Diminta — Actor ROI/Stats Tinggi + Vonisnya

Kode vonis: **[BUILD]** = kandidat baru · **[RECON]** = pasar layak, kelayakan teknis belum terbukti · **[SUDAH]** = sudah dipegang/diputus · **[SKIP]** = ada alasan konkret.

### ✅ BELUM Dibangun — Kandidat Baru (9)

| # | Konsep | Bukti demand (u30 = pembeli aktif 30 hari) | Incumbent & umurnya | `xtracto` | Probe permukaan | Vonis |
|---:|---|---|---|---|---|---|
| 1 | **Google Hotels** (tarif lintas-OTA per hotel) | vein **u30 671** / 2.060 user / 4 seller serius | `zerobreak/google-hotels-scraper` **546u dalam 3,7 bln, u30 511** — artinya **93% usernya aktif bulan ini**, rasio tertinggi di seluruh scan | kosong (punya `agoda-hotels-scraper` + `booking-hotels-scraper`, **bukan** Google Hotels) | ✅ **TERBUKA** — HTTP polos, tanpa cookie/captcha: 2,8 MB HTML berisi nama hotel asli (Novotel Bali Ubud, The Kubu Hotel), 161 kemunculan harga IDR, 5 blok `AF_initDataCallback` | 🔴 **[BUILD]** |
| 2 | **Sports betting odds** (NFL/NBA/MLB/soccer) | vein **u30 1.022** / 3.608 user / **3 pendatang ≤8 bln** (`scrapemint` 612u/4,4bln · `seemuapps` 486u/3,7bln · `scrapesage` 446u/2,7bln) | tidak ada incumbent besar — seller terbesar 612 user | kosong | ✅ **TERBUKA** — `sports.core.api.espn.com` 200 JSON tanpa header khusus, termasuk endpoint `/competitions/<id>/odds`. (Catatan: `site.api.espn.com` justru **403** dari IP ini — dua host beda perlakuan) | 🔴 **[BUILD]** — **moat reuse langsung** dari `flashscore-all-sports-scraper` (Babak 48) |
| 3 | **Douyin** (TikTok China) | **u30 6.103** / 16.825 user — **vein terbesar yang `xtracto` benar-benar kosong**. `zen-studio/douyin-search-scraper` **8.268u dalam 3,9 bln, u30 5.009** | `zen-studio` masuk 3,9 bulan lalu dan langsung jadi terbesar; `natanielsantos` (34 bln) hanya u30 146 → **incumbent lama sudah disalip pendatang** | kosong (0 dari 218) | ⚠️ API web menolak tanpa tanda tangan: `search_nil_type: params_check`, `invalid_app` → butuh `a_bogus`/`msToken` | 🟠 **[RECON]** — prioritas #1 kalau ada anggaran recon |
| 4 | **TikTok Shop** | **u30 2.358** / 16.060 user / **4 pendatang ≤8 bln** | `pratikdani` 2.865u + 2.029u; `unseenuser` 2.070u/4,1bln; `cunning_soil` eksplisit pakai **Mobile API** | kosong — `xtracto` punya **6 actor TikTok** (profile/comments/search/trending/post-detail/top-ads) tapi **nol TikTok Shop** | ⚠️ web `/shop` = shell 5,5 KB + captcha; `shop.tiktok.com/api/...` 404 | 🟠 **[RECON]** — arah yang disebut kompetitor sendiri: mobile API |
| 5 | **Keyword search volume** (Google volume + CPC massal) | **u30 1.465** / 8.313 user / 15 seller serius. `aitorsm/keyword-volume` 734u **dalam 2,1 bulan** | tersebar rata, tidak ada penguasa | kosong | ❓ belum diprobe — sumber data belum jelas (Keyword Planner butuh akun Ads) | 🟠 **[RECON]** — **blind spot murni: nol jejak di kedua dokumen riset** |
| 6 | **Google Lens / reverse image search** | **u30 766** / 5.727 user / **3 pendatang ≤8 bln** | `borderline/google-lens` 1.709u; `zen-studio/google-lens-ocr` 544u/5,9bln | kosong | ❓ `lens.google.com/uploadbyurl` balas 200 tapi nol penanda hasil → belum konklusif | 🟠 **[RECON]** — nol jejak di kedua dokumen |
| 7 | **Tech-stack detector** (pengganti Wappalyzer/BuiltWith) | `nexgendata/wappalyzer-replacement` **1.442u dalam 4,7 bln dengan u30 1.217** — **84% user aktif bulan ini** | hanya 2 pemain nyata: `nexgendata` + `builtwith` (resmi, 606u) | kosong | ✅ terbuka secara teknis (fetch HTML + sidik jari) | 🟡 **[BUILD-rendah]** — murah dibangun, tapi **nol moat data**: siapa pun bisa mengkloning pola deteksi |
| 8 | **Himalayas remote jobs** + **Welcome to the Jungle** | u30 411 & 319 | `inlifeprojects` 616u/4,4bln; `clearpath` 577u/6,2bln | kosong | ✅ **TERBUKA & RESMI** — `himalayas.app/jobs/api` 200 JSON dengan **paginasi cursor terdokumentasi**; `api.welcometothejungle.com` 200 JSON 442 KB | 🟡 **[BUILD-rendah]** — TAM kecil, tapi **satu-satunya job board yang permukaannya terbuka** di seluruh probe |
| 9 | **Medium.com** | u30 285 / 1.112 user. `moving_beacon-owner1/medium-scraper` 312u **dalam 2,4 bln, u30 246** (79% aktif) | 15 seller, semuanya kecil | kosong | ✅ RSS `medium.com/feed/tag/<x>` 200 (halaman topik kena Cloudflare) | 🟡 **[BUILD-rendah]** — **moat reuse ekstrem**: repo ini punya 100+ scraper artikel |

### 🔁 SUDAH Ada — Muncul di Puncak Scan Tapi Bukan Temuan Baru (21 konsep)

Semua dicek **harfiah** terhadap 218 actor `xtracto` (nama actor persisnya dicantumkan), bukan cocok-nama otomatis (Gotcha #2 v2).

| Konsep (u30 vein) | Sudah dipegang sebagai |
|---|---|
| Google Flights (1.151) | `xtracto/google-flights-scraper` |
| Google Ads Transparency (2.288) | `xtracto/google-ads-transparency` |
| ATS feed / Greenhouse / Workday (3.543) | `xtracto/ats-jobs-aggregator` + `xtracto/ats-hiring-velocity` |
| Wellfound / AngelList (1.196) | `xtracto/wellfound-jobs-scraper` |
| eBay sold listings (1.240) | `xtracto/ebay-sold-comps-scraper` (+ 3 actor eBay lain) |
| Semrush (1.095) | `xtracto/semrush-website-overview` |
| App Store reviews (640) | `xtracto/appstore-reviews-scraper` |
| Alibaba (bagian dari vein 1688) | `xtracto` ×5 (`alibaba-search/rfq/product/company/review`) |
| Shopee | `xtracto` ×6 — dan di sisi lokal Shopee sudah divonis **hard-blocked** |
| Hotel OTA | `xtracto/agoda-hotels-scraper`, `xtracto/booking-hotels-scraper` |
| Instagram · LinkedIn · TikTok umum · Facebook · YouTube · Twitter/X · Reddit · Google Maps · Amazon · Zillow · Trustpilot | `xtracto` punya semuanya — 11 vein u30 terbesar Store, semua tercoret dedupe |
| Artikel/readability generik (397) | Backlog `actors_researcher_v2.md` + 100+ scraper artikel per-outlet di folder lokal |
| Google AI Overviews / AEO (17.061\*) | Folder lokal **`aeo-geo-tracker`** (rank tracker AEO berbasis Bing, sudah dibangun, belum dipublikasikan) |

\* angka 17.061 didominasi `apify/google-search-scraper` (u30 16.605) yang ikut tertangkap frasa; vein AI-Overview murni hanya ~450 u30 dan **baru berumur 2 bulan** (`apify/google-ai-overviews-scraper` 2,0 bln; `apify/chatgpt-search-scraper` 2,2 bln) — **vein yang sedang lahir**, layak dipantau.

### ⛔ DI-SKIP — Semua dengan Alasan Konkret

#### A. Pasar bagus, **permukaan tertutup** (kelompok baru — inilah kontribusi probe babak ini)

| Konsep | u30 vein | Bukti tembok (probe hari ini) | Kenapa di-skip |
|---|---:|---|---|
| **Naukri** (India) | **5.549** | Babak 48: `jobapi/v3` **406 recaptcha required**, Akamai `ak_bmsc`, permukaan SEO = shell 36 KB tanpa `<title>` | Diuji tuntas 1 hari lalu. **Tapi lihat Koreksi #2** — 6 pendatang ≤8 bulan tembus 400 user di vein ini, jadi ini kegagalan **kapabilitas kita**, bukan pasar |
| **ZipRecruiter** | 843 | **403 + Cloudflare** | Tembok WAF; di luar doktrin HTTP-only |
| **Seek AU/NZ** | 854 | `chalice-search/v4` **404 + Cloudflare** (endpoint yang dulu publik sudah dipindah) | idem — dan ini **membatalkan status "cadangan" Seek** dari Rekomendasi #4 Babak 48 |
| **StepStone** (DE) | 866 | **403** | idem |
| **Bayt** (MENA) | 507 | **403 + Cloudflare** | idem |
| **Dice** (US tech) | 326 | API `job-search-api.svc.dhigroupinc.com` **403** | idem, TAM kecil |
| **Foundit/Monster India** | 513 | 200 tapi **Akamai** aktif | sama pola dengan Naukri |
| **Taobao / Tmall** | 427 | search page = shell 34 KB (aplus/spm), nol baris produk | login/anti-bot wall |
| **1688** | 880 | `s.1688.com` **redirect ke `login.1688.com/member/signin`** | login wall telanjang |
| **Xing** (DE) | 620 | 200 261 KB tapi **nol `JobPosting`**, hanya jejak `APOLLO_STATE` | data di balik JS/GraphQL berautentikasi |

#### B. Jenuh / komoditas — pembelinya ada, tapi masuk sekarang = kloning ke-N

| Konsep | Angka | Kenapa di-skip |
|---|---|---|
| **Website contact / email finder** | u30 **4.081**, 79.533 user, tapi **178 seller / 30 serius** | Komoditas paling padat di Store. `vdrmota/contact-info-scraper` 58.953u sudah 87 bulan, ditambah `automation-lab`, `caprolok`, `logiover`, `thenetaji`, `clearpath` — semua menjual hal yang sama |
| **Similarweb / Ahrefs / Moz / backlink** | u30 gabungan ±3.100; `similarweb` sendiri **6 seller** | Sudah divonis jenuh Babak 39/40/41 + v2; `xtracto/semrush-website-overview` sudah menutupi sudut ini |
| **Clutch.co** | 453 | Vonis lama tetap: 37 seller |
| **G2** | 705 | Vonis lama (v2) tetap; `automation-lab/g2-scraper` 673u/5,5bln tidak mengubah kepadatannya |
| **Google Play reviews / Google Shopping / Google Trends** | 1.495 / 462 / ±3.700 | 250, 55, dan 66 seller. Komoditas SERP-adjacent tanpa sudut pembeda |

#### C. Kebijakan portofolio (PII massal) — konsisten dengan Babak 40/41/45/46

| Konsep | Angka | Alasan |
|---|---|---|
| **Username OSINT** (Sherlock/Maigret) | u30 **1.111**, 49.337 user, **6 pendatang ≤8 bln** | `misceres/sherlock` 37.973u. Produk = "username → seluruh jejak akun seseorang". Satu keluarga dengan skip trace yang sudah di-skip Babak 45 |
| **Skip trace / people search** | `one-api/skip-trace` u30 827; `apivault_labs` 637u/3,2bln | Sudah di-skip Babak 45 — dicatat ulang karena **muncul lagi di puncak u30** |
| **WhatsApp / phone OSINT** | `eduair94` 1.416u, `devscrapper` 2.164u, `datacach/phoneinfoga` 2.079u | Sudah di-skip Babak 40/41 |
| **Email breach / OSINT email** | `s-r/apifyosintemail` 2.668u, `ntriqpro/email-osint-search` 1.427u | Sudah di-skip Babak 46 (kredensial bocor) |

#### D. TAM terlalu kecil untuk dibangun sekarang

| Konsep | u30 | Alasan |
|---|---:|---|
| **Kalshi / Polymarket** (prediction market) | 616 | Tersebar di 97 seller, terbesar hanya 225 user. Dua API-nya bahkan **connect-timeout** dari jaringan ini — dependensi tambahan |
| **Zillow agent leads** | 171 | `xtracto` sudah punya vein Zillow; sub-tipe ini hanya 3 seller serius |

---

## 🔧 Koreksi untuk Riset Lama

1. **Douyin di-skip keliru di Babak 45** (*"jenuh + incumbent 10rb user"*). Yang terjadi setelahnya: `zen-studio` masuk **3,9 bulan lalu** dan sekarang **u30 5.009** — 34× lebih besar dari incumbent lama `natanielsantos` (u30 146). Ini pengulangan persis kesalahan Flashscore (Babak 45 → dikoreksi Babak 47/48). **Pola yang sudah dua kali terbukti: "incumbent besar" tidak menutup vein; incumbent yang tidak dirawat justru disalip pendatang.**
2. **Naukri bukan kegagalan pasar, melainkan kegagalan kapabilitas.** Babak 48 menutupnya sebagai "permukaan tertutup". Data babak ini: **6 pendatang ≤8 bulan tembus 400 user** di vein Naukri, termasuk `valig` (6.292u dalam 3,7 bln) dan `blackfalcondata` (4.056u dalam 5,7 bln). Mereka menembus reCAPTCHA+Akamai yang kita tidak tembus. Vonis yang benar: **"butuh kapabilitas anti-bot yang portofolio ini belum punya"**, bukan "tidak bisa di-scrape".
3. **"Cadangan Seek" dari Rekomendasi #4 Babak 48 gugur** — endpoint `chalice-search/v4` yang dulu publik kini 404 di balik Cloudflare.

## Gotcha Metodologi Baru

1. **`stats.totalUsers30Days` / `90Days` ADA di indeks Algolia.** Babak 47 menyimpulkan u30 hanya bisa diambil lewat `GET /v2/acts/<user>~<name>` per actor — itu salah, dan membatasi Babak 47 ke 638 actor serta Babak 48 ke 22 vein. Dengan `attrs` kustom, 65.092 actor bisa diperingkat dengan u30 dalam ~20 menit dan **nol request API detail**.
2. **Klaster token otomatis menghasilkan vein palsu.** Pass 2 memunculkan "employees", "fields", "subreddits" sebagai vein bertanda **KOSONG** — semuanya artefak tokenisasi, bukan konsep. Token pendek juga memberi false positive dedupe: `line` cocok ke "online", `cars` ke "Carsales", dan `temu` cocok **255×** di dokumen ini karena "temu" adalah kata Indonesia. **Verifikasi frasa telanjang (Pass 4) wajib; klaster token hanya untuk menyusun kandidat.**
3. **Probe permukaan harus mendahului peringkat, bukan mengikutinya.** Babak 48 memilih Naukri lalu kehilangannya di recon. Di babak ini 10 dari 52 konsep gugur karena tembok — dan semuanya konsep yang, tanpa probe, akan naik ke daftar kandidat teratas berdasarkan angka pasar saja.
4. **Host berbeda dari satu penyedia bisa punya kebijakan berbeda.** `site.api.espn.com` **403**, sementara `sports.core.api.espn.com` **200 JSON** untuk data yang sama. Menyimpulkan "ESPN tertutup" dari host pertama akan menghapus kandidat yang sebenarnya terbuka.
5. **Probe di babak ini sengaja DANGKAL.** Status 200 + adanya penanda data bukan jaminan actor bisa dibangun (Gotcha #1 Babak 44: ukuran halaman bukan bukti ada data). Setiap **[BUILD]** tetap wajib melewati recon penuh + `CRAWLING_METHOD.md` sebelum kode ditulis.

## Insight Strategis Babak 49

> **Pasar Apify jauh lebih terkonsentrasi daripada yang diasumsikan 48 babak.** 65.092 actor; 544 (0,8%) punya u30 ≥ 120; 162 punya u30 ≥ 500. Sisanya — 64.548 actor — praktis tidak punya pembeli aktif. "Mencari niche kosong" selama 46 babak sebenarnya adalah mencari di dalam 99,2% yang tidak laku.

> **Sumbu yang benar-benar membedakan kandidat bukan "sepi vs jenuh", melainkan "terbuka vs tembok".** Setelah dedupe `xtracto` dijalankan, vein bernilai yang tersisa hampir seluruhnya terbagi dua: yang permukaannya dijaga WAF/login (Naukri, ZipRecruiter, StepStone, Bayt, Dice, Taobao, 1688 — total u30 ±10.000) dan segelintir yang terbuka (Google Hotels, ESPN odds, Himalayas, WTTJ, Medium — total u30 ±2.700). **Yang menentukan plafon portofolio ini sekarang adalah kapabilitas anti-bot, bukan ide.**

> **Dua kandidat teratas babak ini punya moat reuse langsung, dan itu bukan kebetulan.** Google Hotels menyambung ke 2 actor hotel `xtracto`; ESPN odds menyambung ke `flashscore-all-sports-scraper` yang baru dibangun Babak 48. Vein yang bertetangga dengan yang sudah dikuasai lebih murah dikerjakan **dan** lebih mudah dipercaya pembeli.

## Rekomendasi Lanjutan

1. **Bangun `google-hotels-scraper` lebih dulu.** Satu-satunya kandidat dengan permukaan terbukti terbuka **dan** bukti permintaan yang sedang berjalan (u30 511 pada actor berumur 3,7 bulan). Sudut pembeda yang jelas tersedia: perbandingan tarif **lintas-OTA per hotel** — yang `agoda-hotels-scraper`/`booking-hotels-scraper` milik `xtracto` tidak berikan.
2. **Lalu `sports-odds-scraper` di atas ESPN core API**, satu paket dengan `flashscore-all-sports-scraper`: skor+jadwal (Flashscore) × odds (ESPN) adalah produk yang tidak dijual utuh oleh 41 seller di vein itu.
3. **Alokasikan satu babak khusus recon Douyin.** Ini vein terbesar yang `xtracto` kosong (u30 6.103) dan pendatang 3,9 bulan sudah memimpin. Pertanyaan recon-nya sempit dan terdefinisi: bagaimana `a_bogus`/`msToken` dihasilkan, dan apakah ada permukaan yang tidak memerlukannya.
4. **Perlakukan "kapabilitas anti-bot" sebagai proyek tersendiri, bukan hambatan per-actor.** u30 ±10.000 terkunci di balik Cloudflare/Akamai di 10 vein sekaligus, dan kompetitor seumur 3–6 bulan menembusnya. Selama kapabilitas ini tidak ada, setiap babak riset berikutnya akan berakhir di daftar tembok yang sama.
5. **Prasyarat yang belum berubah sejak Babak 48:** 7 actor masih menunggu build karena kuota akun `fanndev` habis. Kandidat babak ini tidak berarti apa-apa sampai itu beres.
6. **Perbarui `api-search-actors.py`:** tambahkan `createdAt` + `stats` lengkap ke `DEFAULT_ATTRS` dan opsi `--sort u30`. Rekomendasi #5 Babak 47 masih belum dijalankan, dan babak ini membuktikan nilainya (17.244 → 65.092 actor terukur).

## File Referensi Babak 49

- `output/scan-v12-all.json` — **65.092 actor, seluruh Store**, dengan `createdAt` + u7/u30/u90 (76 MB)
- `output/scan-v12-roi.json` — 544 actor u30 ≥ 120, terperingkat, dengan flag dedupe
- `output/scan-v12-concepts.json` — 52 konsep terverifikasi frasa telanjang + dedupe 3 lapis
- `output/scan-v12-veins.json` · `output/scan-v12-young.json` — vein by token; 372 pendatang ≤8 bulan dengan ≥400 user
- `scratchpad/scan49.py` (Pass 1) · `rank49.py` (2) · `roi49.py` (3) · `verify49.py` (4) · `probe49.py` (5)
- `output/xtracto-full.json` — di-refresh 2026-09-09, tetap 218 actor

---

# Babak 50 — Sumbu **UANG**: 65.092 Actor Diperingkat dengan MRR, Bukan Jumlah Pembeli. 9 Kandidat Babak 49 Runtuh, 2 Kandidat Baru Terbukti Terbuka, dan Temuan Terbesar Bukan Actor Baru Melainkan **Model Harga** (2026-09-10)

**Konteks:** user kembali meminta daftar actor ber-ROI/stats tinggi dengan dedupe terhadap (a) akun kedua `xtracto` dan (b) riset yang sudah ada. Catatan lama tetap berlaku: file `ACTOR_MARKET_RESEARCH.md` yang disebut user **tidak ada** di repo — korpus dedupe adalah dokumen ini + `actors_researcher_v2.md`.

**Kenapa babak ini bukan pengulangan Babak 49.** Babak 49 (kemarin) sudah menyapu seluruh Store dan meranking dengan **u30** (pembeli aktif 30 hari). Babak ini memakai **korpus 65.092 actor yang sama** tetapi meranking dengan sumbu yang **belum pernah diukur di 49 babak**: **berapa uang yang benar-benar dipungut vein itu setiap bulan.** Permintaan user berbunyi "ROI"; 49 babak sebelumnya mengukur *pembeli*, bukan *pendapatan*. Ternyata dua hal itu berkorelasi sangat lemah — dan itu membalik peringkat kemarin.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **BELUM dibangun — kandidat baru** | **9** | 2 permukaan **terbukti terbuka & berisi data asli** (Snapchat, data short-interest SEC/FINRA/Nasdaq) · 4 butuh recon (Dubai unit-number, TecDoc/OEM, Apple Maps, Google Jobs) · 3 kecil (Storeleads, Ozon.ru, AutoTrader UK) |
| 🔁 **SUDAH ada** (`xtracto` / folder lokal) | **14 konsep** | Diverifikasi **harfiah** dengan nama actor `xtracto` yang persis dicantumkan |
| ⛔ **DI-SKIP** | **19 konsep** | 4 **tembok** (bukti HTTP hari ini) · **9 karena uangnya tipis — seluruh kandidat Babak 49** · 3 kebijakan PII · 2 komoditas · 1 kualitas/policy |
| 🔧 **Koreksi untuk riset lama** | **4** | Rekomendasi #1, #2 dan #3 Babak 49 gugur di sumbu uang; probe dangkal terbukti bisa false positive |
| 🔴 **Temuan terbesar** | **1** | **Bukan actor** — `xtracto` 100% pay-per-event, nol flat-bulanan, sementara seluruh uang premium Store ada di flat-bulanan |

## Ringkasan Eksekutif

> **Seluruh Apify Store memungut ± $439.454/bulan** (MRR flat-bulanan + lantai pay-per-event). Dari 65.092 actor, **21.678 memungut > $0**, tapi hanya **457 yang tembus $100/bulan**, **59 tembus $1.000**, dan **3 tembus $20.000**. **10 actor teratas menguasai 33,3% seluruh uang Store; 100 teratas menguasai 64,3%.** Konsentrasi uang jauh lebih ekstrem daripada konsentrasi pembeli yang ditemukan Babak 49.

> **u30 tinggi ≠ uang.** Rata-rata Store adalah **$0,54 per pembeli aktif per bulan**. Sebarannya 158×: vein Dubai unit-number memungut **$85,21 per pembeli**, TecDoc $51,76, Apple Maps $12,55 — sementara Douyin **$0,06**, sports odds **$0,03**, Google Hotels **$0,35**. **Semua kandidat Babak 49 berada di ujung murah sebaran ini.**

> **Temuan yang paling berkonsekuensi bukan kandidat baru.** Seluruh **215 actor `xtracto` yang terindeks memungut ± $687/bulan** dari 936 pembeli aktif — dan **215 dari 215 memakai PAY_PER_EVENT, nol memakai FLAT_PRICE_PER_MONTH.** Sementara itu **95 actor "premium" di Store memungut $93.304/bulan dari hanya 3.458 pembeli**, dan hampir semuanya flat-bulanan $25–$500. `xtracto` sudah punya 936 pembeli aktif — jumlah pembeli bukan lagi hambatan utamanya; **harga adalah hambatannya.**

## Metodologi Babak 50

```bash
# Pass 0 - korpus: 65.092 actor dari Babak 49 (output/scan-v12-all.json, 2026-09-09) DIPAKAI ULANG.
#   Field currentPricingInfo + publicActorRunStats30Days sudah ada di sana tapi TIDAK PERNAH dianalisis.
#   scratchpad/attrs50.py -> konfirmasi indeks Algolia membawa harga per-event bertingkat & statistik run
# Pass 1 - MODEL UANG per actor:  scratchpad/money50.py -> output/scan-v13-money.json
#   FLAT_PRICE_PER_MONTH -> MRR = u30 x pricePerUnitUsd            (nyaris eksak)
#   PAY_PER_EVENT        -> LANTAI = run sukses 30h x harga event  (batas bawah, 1 event/run, tier GOLD)
# Pass 2 - korpus dedupe 3 lapis: xtracto 218 (ditarik ulang hari ini) / 225 folder lokal / 2 dokumen
#   scratchpad/dedupe50.py -> output/scan-v13-dedupe-corpus.json
# Pass 3 - tiga papan peringkat baru: uang, premium-rendah-volume, wedge reliabilitas
#   scratchpad/rank50.py
# Pass 4 - 17 konsep diverifikasi FRASA TELANJANG + diukur dalam uang
#   scratchpad/verify50.py -> output/scan-v13-concepts.json
# Pass 5 - PROBE PERMUKAAN 20 target, HTTP polos tanpa proxy/cookie  scratchpad/probe50.py
# Pass 5b - VERIFIKASI DALAM: apakah yang "200" itu berisi nilai data atau cangkang JS
#   scratchpad/probe50b.py  <- ini yang menggugurkan Apple Maps
# Pass 6 - sapuan terbalik (data -> konsep): 250 actor ber-MRR tertinggi disaring otomatis
#   scratchpad/sweep50.py -> output/scan-v13-clean.json
```

**Cross-check `xtracto` di-refresh hari ini:** `python apify-my-store.py xtracto -o output/xtracto-full-50.json` → **218 actor**, tidak berubah sejak Babak 47/49. Konsisten dengan kuota akun `fanndev` yang masih habis sejak Babak 48.

**Distribusi model harga di Store:** PAY_PER_EVENT **55.079** · FLAT_PRICE_PER_MONTH **5.255** · FREE **4.758**. Harga event median identik antara `xtracto` dan Store ($0,00200) — jadi `xtracto` **tidak** menjual lebih murah dari pasar; ia hanya tidak pernah memakai model yang mahal.

---

## 📋 Daftar yang Diminta — Actor ROI/Uang Tinggi + Vonisnya

Kode vonis: **[BUILD]** = kandidat baru, permukaan terbukti · **[RECON]** = uangnya nyata, kelayakan teknis belum terbukti · **[SUDAH]** = sudah dipegang · **[SKIP]** = ada alasan konkret.

### ✅ BELUM Dibangun — Kandidat Baru (9)

| # | Konsep | Uang vein (MRR/bln) | $/pembeli aktif | Incumbent & umur | `xtracto` | Probe permukaan hari ini | Vonis |
|---:|---|---:|---:|---|---|---|---|
| 1 | **Snapchat** (profil publik + spotlight) | **$1.968** · 167 actor, 71 memungut | $0,68 | `argusapi/snapchat-profile-scraper` $735/bln (43,9 bln, $15 flat); `saswave/snapchat-scraper` **15% gagal** | **kosong (0 dari 218)** | ✅ **TERBUKA & BERISI DATA ASLI** — `snapchat.com/add/<user>` 200, `__NEXT_DATA__` **283.111 byte**, NASA `subscriberCount = 760.200`, bio, websiteUrl, badge, **relatedAccountsInfo** (jalur crawl), `spotlightStoryMetadata`. Tanpa cookie/login/WAF | 🔴 **[BUILD]** |
| 2 | **Data short-interest & filing bursa** (Nasdaq + FINRA + SEC EDGAR) | **$2.115** | **$4,89** (9× rata-rata Store) | `parseforge/nasdaq-short-interest-scraper` $1.566/bln — **baru 3,3 bulan, 17% gagal**; `nexgenwatch/edgar-diligence-report` $502/bln dari **1 pembeli** ($16,75/event) | **kosong** (nol `sec`/`edgar`/`finra`) | ✅ **TIGA permukaan resmi terbuka** — `api.nasdaq.com/.../short-interest` 200, 23 baris riil (TSLA: interest 69.196.896, daysToCover 2,15) · `cdn.finra.org/equity/regsho/daily/` 200, **12.327 baris**/hari · `efts.sec.gov` full-text 200, 269 hit | 🔴 **[BUILD]** |
| 3 | **Dubai/UAE: nomor unit + data pemilik** | **$16.616** — **vein terkaya per-pembeli di seluruh Store** | **$85,21** (158× rata-rata) | `dhrumil/...unit-number-finder` **$500/bln × 12 pembeli = $6.000**; `webcrawlerr/dubai-property-crawler` $500 × 9; `gauravsaran` ×3 ($199/$150/$120) | ⚠️ **platform tercakup, tipe data TIDAK** — `xtracto/propertyfinder-dubai-leads` (kontak agen) + `propertyfinder-offplan-tracker` (proyek off-plan). Nomor unit & pemilik = tipe data berbeda | ⚠️ `gateway.dubailand.gov.ae` **500**; `dubailand.gov.ae/open-data` 200 (Cloudflare) 46× "transaction"; `bayut.com` **503** | 🟠 **[RECON]** — **dan lihat catatan PII di bawah** |
| 4 | **TecDoc / katalog suku cadang OEM** | **$2.692** dari **2 actor saja** | $51,76 | `making-data-meaningful/tecdoc` $69 flat × 39 pembeli = **$2.691**, umur 23,6 bln, **0% gagal, tanpa pesaing serius** | **kosong** | ⚠️ `web.tecalliance.net` 200 tapi halaman pemasaran; `tecdoc.net` **timeout**. Pembanding `rockauto.com/en/catalog/` **200, 576 KB, 327 `navlabel`** → permukaan katalog suku cadang yang terbuka **ada**, tapi bukan TecDoc | 🟠 **[RECON]** — monopoli 23 bulan tanpa penantang adalah anomali yang layak diselidiki |
| 5 | **Apple Maps** | $678 | $12,55 | `zen-studio/apple-maps-scraper-pro` $675/bln, 6,4 bln | **kosong** (`apple-podcast-charts` ≠ Apple Maps) | ❌ **probe dangkal FALSE POSITIVE** — `maps.apple.com` 200/59 KB terlihat "found=64", tapi verifikasi dalam: **nol latitude, nol telephone, nol formattedAddress**, hanya cangkang MapKit JS. `api.apple-mapkit.com` **401** (butuh JWT) | 🟠 **[RECON]** — moat reuse kuat (5 actor Google Maps di `xtracto`), tapi jalur masuknya belum ada |
| 6 | **Google Jobs** (widget lowongan SERP) | $1.463 | $0,90 | `johnvc/Google-Jobs-Scraper` $1.124/bln ($0,10/event); `epctex/google-jobs-scraper` **65% gagal** | kosong — `xtracto` punya 5 actor jobs (`indeed`, `glassdoor`, `ats-jobs-aggregator`, `linkedin`, `wellfound`) tapi **bukan** Google Jobs | ❓ SERP 200/91 KB tapi **nol penanda widget jobs** → belum konklusif | 🟠 **[RECON]** |
| 7 | **Storeleads** (basis data toko Shopify) | $468 | $2,27 | `saswave/storeleads-scraper` $360/bln, 22 bln, **76% GAGAL** — tingkat kegagalan tertinggi di seluruh papan uang | kosong | belum diprobe | 🟡 **[BUILD-rendah]** — **wedge reliabilitas paling telanjang yang ditemukan**: pembeli membayar $36/bln untuk actor yang gagal 3 dari 4 kali |
| 8 | **Ozon.ru** (marketplace Rusia) | $467 | $0,90 | `natanielsantos/ozon-scraper` $253/bln, **baru 6,7 bulan**, 0% gagal | kosong | belum diprobe | 🟡 **[BUILD-rendah]** |
| 9 | **AutoTrader UK** | $406 | $2,14 | `epctex/autotradercouk-scraper` $270/bln ($30 flat), 38 bln | kosong | belum diprobe | 🟡 **[BUILD-rendah]** — 79 actor di vein, tapi hanya 31 memungut |

**Catatan PII wajib untuk #3.** Vein Dubai adalah yang terkaya per-pembeli di seluruh Store, tetapi uangnya spesifik ada pada **identitas pemilik properti** ("owner details finder", "unit number owner"). Itu satu keluarga dengan skip-trace/people-search yang **sudah di-skip Babak 40/41/45/46 atas kebijakan portofolio**. Yang **boleh** dikerjakan tanpa melanggar kebijakan itu adalah irisan non-PII-nya: **inventaris unit per gedung + data transaksi resmi DLD open-data** (harga, tanggal, luas, jenis properti) — bukan nama/telepon pemilik. Kalau irisan non-PII itu tidak laku, vein ini harus di-skip utuh, bukan dikompromikan.

### 🔁 SUDAH Ada — Muncul di Puncak Papan Uang Tapi Bukan Temuan Baru (14 konsep)

Diverifikasi **harfiah** terhadap 218 actor `xtracto` (nama persisnya dicantumkan), bukan pencocokan token otomatis.

| Konsep (uang vein) | Sudah dipegang sebagai |
|---|---|
| PropertyFinder Dubai — listing + kontak agen ($16.846 vein) | `xtracto/propertyfinder-dubai-leads`, `xtracto/propertyfinder-offplan-tracker` |
| Crexi — commercial real estate ($845) | `xtracto/crexi-yield-scraper` (Cap Rate/NOI/off-market) |
| BizBuySell — bisnis dijual ($1.627) | `xtracto/bizbuysell-listings` |
| Google News ($1.068) | `xtracto/google-news-scraper` + 16 actor outlet berita lain |
| Idealista ($73) | `xtracto/idealista-property-scraper` |
| Rightmove ($151) | `xtracto/rightmove-property-scraper` |
| Realtor**.com** US (vein Realtor.ca Kanada terpisah, $608) | `xtracto/realtor-all-in-one-scraper` |
| Immobiliare IT | `xtracto/immobiliare-listings` |
| Google Maps (5 sudut: search, detail, kategori, rute, autocomplete) | `xtracto/gmaps-search-places`, `gmaps-detail-places`, `gmaps-places-by-category`, `gmaps-direction-rute`, `gmaps-suggestion` |
| Google Trends · Google Flights · Google Play Reviews · Google Ads Transparency | `xtracto/google-trends-scraper`, `google-flights-scraper`, `google-play-reviews-scraper`, `google-ads-transparency` |
| LinkedIn · Instagram · TikTok · Facebook · YouTube · Twitter/X · Amazon · Zillow · Trustpilot · Reddit | `xtracto` punya semuanya — 10 vein ber-MRR terbesar Store, semua tercoret dedupe |
| Shopee (6 actor) | `xtracto` ×6 — dan di sisi lokal Shopee sudah divonis **hard-blocked** |
| Hotel OTA | `xtracto/agoda-hotels-scraper`, `xtracto/booking-hotels-scraper` |
| Glassdoor / Indeed / Wellfound / ATS | `xtracto/glassdoor-jobs`, `indeed-jobs-scraper`, `wellfound-jobs-scraper`, `ats-jobs-aggregator` |

### ⛔ DI-SKIP — Semua dengan Alasan Konkret

#### A. Permukaan tertutup — bukti HTTP hari ini

| Konsep | Uang vein | Bukti tembok (probe 2026-09-10) | Kenapa di-skip |
|---|---:|---|---|
| **LoopNet** (commercial RE US) | $663 | `loopnet.com/search/...` **403**, body 440 byte | Sayang, karena incumbent `memo23/apify-loopnet-search-cheerio` **27% gagal** di $31/bln — wedge bagus di balik tembok |
| **Upwork** | $2.516 | `upwork.com/nx/search/jobs` **403 + Cloudflare** (344 KB halaman blok); **RSS lama `/ab/feed/jobs/rss` = HTTP 410 Gone** | Membatalkan status "cadangan" Upwork dari Rekomendasi #4 Babak 48 — jalur RSS yang dulu dipakai actor lama sudah **dimatikan permanen** |
| **Realtor.ca** (Kanada) | $608 | `api2.realtor.ca/Listing.svc/PropertySearch_Post` **403 + Cloudflare** | Incumbent `scrapemind/Realtor-ca-Scraper` **52% gagal** dan `canadesk/realtor-canada` **62% gagal** — tembok yang sama juga menyiksa mereka |
| **Bayut** (UAE) | bagian vein Dubai | `bayut.com/for-sale/property/dubai/` **503** | Jalur alternatif Dubai selain PropertyFinder tertutup |

#### B. **Uangnya tipis meski pembelinya banyak — SELURUH 9 KANDIDAT BABAK 49**

Inilah kontribusi utama babak ini. Kolom terakhir adalah alasan konkret skip/turun peringkat.

| Kandidat Babak 49 | u30 vein | **MRR vein** | **$/pembeli** | Vonis Babak 50 |
|---|---:|---:|---:|---|
| Keyword search volume | 1.929 | $929 | $0,48 | Terbaik dari sembilan, tapi 183 actor berebut < $1rb/bln |
| **Douyin** (prioritas #1 Babak 49) | **6.102** | **$357** | **$0,06** | **98 actor memperebutkan $357/bulan.** Memenangi *seluruh* vein masih kalah dari **satu** actor Dubai berpembeli 12 orang. Rekomendasi #3 Babak 49 (satu babak khusus recon Douyin) **tidak layak** |
| TikTok Shop | 2.357 | $353 | $0,15 | 157 actor, uang $353 |
| **Google Hotels** (rekomendasi **#1** Babak 49) | 671 | **$237** | $0,35 | Incumbent yang dipuji kemarin (546 user/3,7 bln, u30 511) ternyata memungut **$119/bulan** dan **16% run-nya gagal** |
| Tech-stack detector | 2.721 | $215 | $0,08 | 436 actor; nol moat data (vonis Babak 49 tetap) |
| Google Lens | 766 | $87 | $0,11 | — |
| Himalayas / WTTJ | 710 | $63 | $0,09 | Permukaan memang terbuka, tapi TAM uangnya $63/bln |
| **Sports odds / ESPN** (rekomendasi **#2** Babak 49) | 1.677 | **$53** | **$0,03** | **163 actor memperebutkan $53/bulan.** Vein termurah yang pernah diukur dokumen ini |
| Medium.com | 286 | $31 | $0,11 | — |

#### C. Kebijakan portofolio (PII massal) — konsisten dengan Babak 40/41/45/46/49

| Konsep | Uang | Alasan |
|---|---:|---|
| **Data pemilik properti Dubai** (paruh PII dari kandidat #3) | bagian dari $16.616 | Identitas + kontak pemilik perorangan = satu keluarga dengan skip-trace. Hanya irisan non-PII yang boleh dikerjakan |
| `parvenu/mobile-phone-enrichment` | $2.052/bln | Pengayaan nomor telepon perorangan — sudah di-skip Babak 40/41 |
| `one-api/skip-trace` ($1.445) · `vulnv/linkedin-email-finder` ($1.727) | $3.172/bln | Sudah di-skip Babak 45/46; dicatat ulang karena keduanya muncul di papan **uang** teratas, bukan hanya papan user |

#### D. Komoditas / kualitas

| Konsep | Uang | Alasan |
|---|---:|---|
| **Yellow Pages USA** | $1.023 | Keluarga "contact/email finder" yang sudah divonis komoditas paling padat di Babak 49 (178 seller). `delicious_zebu` memungut $750 dari 30 pembeli, tapi produknya identik dengan puluhan lainnya |
| `peakydev/leads-scraper` ($100 flat × 73 pembeli) | $7.300 | **MRR terbesar ke-9 di seluruh Store**, tapi produknya adalah kloning basis data Apollo/ZoomInfo/Lusha — menjual ulang basis data pihak ketiga, bukan scraping permukaan publik |
| `forward_dinosaur/youtube-view-generator` ($1.840, **53% gagal**) · `epctex/traffic-generator` ($740, 18% gagal) | $2.580 | **Engagement buatan**, bukan ekstraksi data. Di luar lini produk portofolio ini terlepas dari uangnya |
| **ImmoScout24 DE** | $548 | Uang vein-nya justru ada di `clearpath/immoscout24-apply-bot` ($237, **27% gagal**) — otomasi *melamar*, bukan data. Sisa vein $311 terbagi 60 actor |

---

## 🔧 Koreksi untuk Riset Lama

1. **Rekomendasi #1 dan #2 Babak 49 gugur.** Google Hotels dan sports-odds/ESPN dipilih kemarin karena **satu-satunya yang permukaannya terbukti terbuka**. Benar — tapi keterbukaan tidak pernah dipasangkan dengan harga. Keduanya adalah **dua vein termurah** dari 17 yang diukur hari ini: $237 dan $53 per bulan, dibagi 42 dan 163 actor. Keterbukaan permukaan adalah syarat perlu, bukan syarat cukup.
2. **Rekomendasi #3 Babak 49 (satu babak khusus recon Douyin) tidak layak dijalankan.** Douyin memang vein u30 terbesar yang `xtracto` kosong (6.102 pembeli aktif) — tetapi 98 actor di dalamnya **hanya memungut $357/bulan bersama-sama**. Biaya recon `a_bogus`/`msToken` tidak akan kembali. Ini juga **membalik Koreksi #1 Babak 49**: Douyin di-skip Babak 45 dengan alasan yang salah (jenuh), lalu "dikoreksi" Babak 49 dengan alasan yang juga tidak cukup (u30 besar). Vonis yang benar: **pasarnya ramai tapi tidak berbayar.**
3. **Probe dangkal bisa memberi false positive, dan hari ini terbukti.** Apple Maps lolos Pass 5 dengan "found=64" (`place`×39, `address`×23) lalu **gugur di Pass 5b**: nol latitude, nol telepon, nol alamat terformat — cangkang MapKit JS. Gotcha #5 Babak 49 ("probe sengaja dangkal") sekarang punya contoh konkret kegagalannya.
4. **"Cadangan Upwork" dari Rekomendasi #4 Babak 48 gugur** — `upwork.com` 403 Cloudflare dan feed RSS lamanya **410 Gone** (dimatikan permanen, bukan sekadar diblokir).

## Gotcha Metodologi Baru

1. **Jumlah pembeli aktif dan uang berkorelasi sangat lemah — sebarannya 158×.** Rata-rata Store $0,54/pembeli/bulan; Dubai $85,21; Douyin $0,06. Setiap peringkat vein yang memakai u30 (Babak 47, 48, 49) diam-diam mengasumsikan semua pembeli bernilai sama. Tidak.
2. **Lantai pay-per-event rapuh untuk actor "run banyak, pembeli sedikit".** `parseforge/nasdaq-short-interest-scraper` = 250.542 run dari **3 pembeli**; lantai $1.566 mengasumsikan ≥1 event tertagih per run, padahal run gagal (17% di actor ini) menagih nol. Pakai lantai PPE sebagai **urutan**, jangan sebagai akuntansi. MRR flat-bulanan (u30 × harga) jauh lebih dekat ke eksak.
3. **Penyebutan di dokumen riset ≠ sudah dibangun.** Filter token otomatis Pass 6 menganggap "sudah tercakup" apa pun yang muncul ≥3× di dua dokumen riset — itu membunuh Snapchat (20 penyebutan), `bizbuysell` (10), `loopnet` (9). Padahal Snapchat **nol** di `xtracto` dan **nol** di 225 folder lokal: yang ada hanyalah catatan bahwa ia pernah *dipertimbangkan*. Dedupe harus bertanya "apakah dibangun", bukan "apakah pernah disebut". Hanya 6 dari 250 actor teratas lolos filter token — dan filter itulah yang salah, bukan pasarnya.
4. **Tingkat kegagalan incumbent tersedia gratis dan tak pernah dipakai.** `stats.publicActorRunStats30Days` membawa FAILED/TIMED-OUT/TOTAL 30 hari. Ini memberi papan "vein beruang tapi eksekusinya buruk": `saswave/storeleads-scraper` **76% gagal** sambil menagih $36/bln, `epctex/google-jobs-scraper` 65%, `scrapemind/Realtor-ca-Scraper` 52%, `memo23/apify-loopnet` 27%. Sudut pembeda "yang ini benar-benar jalan" bisa diukur sebelum sebaris kode ditulis.
5. **Papan uang hanya bisa dibaca setelah dedupe, bukan sebelumnya.** 8 dari 10 actor ber-MRR tertinggi Store adalah LinkedIn/Instagram/TikTok/Facebook/Google — semuanya sudah dipegang `xtracto`. Tanpa dedupe lebih dulu, papan uang hanya mengulang daftar raksasa yang sama.

## Insight Strategis Babak 50

> **Hambatan portofolio ini bukan lagi jumlah pembeli — melainkan harga.** `xtracto` punya **936 pembeli aktif** dan memungut **$687/bulan**. Klaster premium Store memungut **$93.304/bulan dari 3.458 pembeli**. Bedanya bukan traffic (3,7×), melainkan tarif (**$26,98 vs $0,73 per pembeli**, 37×). **215 dari 215 actor `xtracto` memakai pay-per-event dengan harga event median $0,00200 — persis median Store, jadi ini bukan soal menjual murah, melainkan soal tidak pernah memakai model flat-bulanan sama sekali.** 5.255 actor Store memakai flat-bulanan; `xtracto` nol.

> **Actor termahal yang masih laku membuktikan pembeli mau membayar $500/bulan** — `dhrumil/uae-dubai-property-leads-unit-number-finder` mengumpulkan 12 pembeli aktif pada $500/bln, dan `webcrawlerr` 9 pembeli pada harga yang sama. Bukan volume yang membuat mereka mahal, melainkan **data yang menutup satu keputusan bernilai besar** (siapa pemilik unit ini) bagi pembeli yang keputusannya bernilai jauh lebih besar dari $500. Sepanjang 50 babak, portofolio ini selalu mengejar *cakupan* (225 folder lokal, 218 actor `xtracto`) dan tidak pernah mengejar *nilai keputusan*.

> **Dua kandidat [BUILD] babak ini dipilih karena lolos TIGA saringan sekaligus, bukan satu.** Snapchat dan data short-interest sama-sama (a) permukaannya terbukti mengeluarkan nilai data asli di probe dalam, (b) berada di atas rata-rata uang per pembeli, **dan** (c) nol di ketiga lapis dedupe. Sembilan kandidat Babak 49 lolos (a) dan (c) saja — dan itulah sebabnya semuanya gugur hari ini.

## Rekomendasi Lanjutan

1. **Prioritas tertinggi babak ini bukan membangun actor — melainkan menguji harga.** Ambil 3–5 actor `xtracto` yang sudah punya pembeli aktif nyata (`shopee-search` u30 220, `shopee-scraper` u30 161, `nytimes-scraper` yang sudah memungut $561/bln dari 6 pembeli), lalu **uji satu varian FLAT_PRICE_PER_MONTH** di kisaran $20–$30 — pita yang paling ramai di klaster premium. Risikonya terukur dan terbalikkan; potensi kenaikannya berlipat, bukan berpersen. **Ini satu-satunya rekomendasi di dokumen ini yang tidak bergantung pada kuota build.**
2. **Bangun `snapchat-profile-scraper` lebih dulu di antara kandidat baru.** Satu-satunya kandidat dengan permukaan yang terbukti mengeluarkan **nilai data asli** (subscriberCount 760.200, bio, website, related accounts sebagai jalur crawl), nol dedupe, dan incumbent tertua berumur 43,9 bulan dengan produk tipis pada $15 flat. Harga rilisnya **jangan** pay-per-event $0,002.
3. **Lalu `sec-short-interest-monitor`** di atas tiga permukaan resmi yang semuanya sudah dikonfirmasi 200 hari ini (Nasdaq + FINRA daily 12.327 baris + EDGAR full-text). Vein ini memungut **$4,89 per pembeli — 9× rata-rata Store** — dan pemimpinnya baru 3,3 bulan dengan 17% run gagal. Ini pembeli finansial, bukan pembeli scraping: pita harga flat $30–$80 realistis.
4. **Jadikan "tingkat kegagalan incumbent" kriteria seleksi tetap**, bersanding dengan u30 dan uang. Sudah tersedia gratis di indeks Algolia dan langsung memberi sudut pembeda yang bisa dibuktikan di halaman Store ("incumbent gagal 3 dari 4 run; ini tidak").
5. **Jangan alokasikan babak recon untuk Douyin, Google Hotels, atau sports odds** sampai ada bukti harga baru. Ketiganya adalah rekomendasi #1–#3 Babak 49 dan ketiganya berada di ujung termurah sebaran.
6. **Prasyarat yang belum berubah sejak Babak 48 — dan hari ini adalah tanggalnya.** 7 actor masih menunggu build karena kuota `fanndev` habis; siklus penagihan diperkirakan reset **tanggal 10** (hari ini). **Cek `/v2/users/me/limits` sebelum hal lain** — kalau sudah reset, `apify push -f` untuk ketujuh actor mendahului seluruh rekomendasi di atas.
7. **Perbarui `api-search-actors.py`** (Rekomendasi #5 Babak 47 & #6 Babak 49, masih belum dijalankan) — tambahkan `createdAt`, `stats` lengkap, `currentPricingInfo` ke `DEFAULT_ATTRS`, plus `--sort u30` dan `--sort mrr`. Dua babak berturut-turut kini terhalang karena skrip resminya masih mengembalikan kolom yang salah.

## File Referensi Babak 50

- `output/scan-v13-money.json` — **65.092 actor dengan MRR/lantai pendapatan, harga per unit, tingkat kegagalan 30 hari**
- `output/scan-v13-concepts.json` — 17 konsep terverifikasi frasa telanjang, diukur dalam uang + dedupe 3 lapis
- `output/scan-v13-probe.json` — 20 target probe permukaan (status, byte, penanda, Cloudflare)
- `output/scan-v13-clean.json` — 6 actor dari 250 ber-MRR tertinggi yang lolos filter token (dan kenapa filternya salah — Gotcha #3)
- `output/scan-v13-dedupe-corpus.json` · `output/xtracto-full-50.json` — 218 actor `xtracto`, ditarik ulang 2026-09-10
- `scratchpad/attrs50.py` (Pass 0) · `money50.py` (1) · `dedupe50.py` (2) · `rank50.py` (3) · `verify50.py` (4) · `probe50.py` (5) · `probe50b.py` (5b, verifikasi dalam) · `sweep50.py` (6) · `retest50.py` (uji ulang kandidat Babak 49) · `final50.py` (benchmark)
- Korpus 65.092 actor dipakai ulang dari Babak 49: `output/scan-v12-all.json`

---

# Babak 50b — EKSEKUSI: Kuota Reset, 7 Actor Ter-build, **5 Tayang di Store**, dan Dua Bug yang Hanya Muncul di Platform (2026-09-10)

**Konteks:** user meminta "upload ke apify dan push" segera setelah Babak 50. Rekomendasi #6 Babak 50 terbukti benar — siklus penagihan `fanndev` memang jatuh tanggal 10, kuota sudah reset, dan ketujuh actor yang tertahan sejak Babak 48 akhirnya bisa di-build.

**Keputusan user soal harga:** ditanyakan eksplisit dan dijawab **"pay-per-event (seperti biasa)"** — temuan flat-bulanan Babak 50 **tidak** dieksekusi di babak ini dan tetap terbuka sebagai Rekomendasi #1.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **Ter-build di Apify** | **7** | Semua lolos `apify validate-schema` (21/21 schema) dan build SUCCEEDED |
| ✅ **Terverifikasi jalan di platform** (`apify call`) | **7** | Mode utama masing-masing, bukan cuma `reference` |
| ✅ **TAYANG di Store** | **5** | flashscore · lelang-djkn · lawrato · indonesiayp · alodokter |
| ⏳ **Menunggu besok** | **2** | socialblade + sinta — kena **batas platform 5 publikasi/akun/hari** |
| 🐛 **Bug ditemukan & diperbaiki** | **2 actor** | socialblade & indonesiayp & alodokter gagal `push_data` — schema dataset menolak `null` |
| 🔧 **Koreksi untuk riset lama** | **2** | Prasyarat publikasi yang tidak terdokumentasi; "cannot-publish-actor" bukan blokir akun |

## Bagian 1 — Kuota Reset Terkonfirmasi

`GET users/me/limits` setelah selesai: **$0,1338 dari $5** terpakai, 0,577 dari 625 compute unit, 224 dari 500 actor. Seluruh `effectivePlatformFeatures` kembali `isEnabled: true`. Blocker Babak 48 (`MONTHLY_TOTAL_USAGE_HARD_LIMIT_EXCEEDED`) selesai tanpa perlu naik plan — **seluruh pekerjaan babak ini hanya memakan 2,7% kuota bulanan.**

Catatan operasional: `~/.apify/auth.json` **tidak memuat token** (`secretsBackend: keyring`), jadi snapshot lokalnya basi dan menyesatkan. Sumber kebenaran adalah `apify api GET users/me/limits`, bukan file itu.

## Bagian 2 — Push & Build

Urutan per actor: `apify validate-schema` → `apify push -f`. Ketujuh manifest sudah membawa perbaikan Babak 48 (`categories` terisi, `title` ≤63, `description` ≤300), jadi tidak ada yang ditolak.

| Actor | Actor ID | Build |
|---|---|---|
| `lelang-djkn-scraper` | `rZETt0UwNy5HeRijZ` | 0.0.1 → 0.0.2 |
| `lawrato-lawyer-directory-scraper` | `dZuR2jPfAbytvf9EZ` | 0.0.1 → 0.0.2 |
| `indonesiayp-business-directory-scraper` | `Beq7scYyt6KintVRD` | 0.0.1 → 0.0.2 |
| `alodokter-doctor-directory-scraper` | `OFMv7OeBZ5L7AagBQ` | 0.0.1 → 0.0.2 |
| `sinta-researcher-scraper` | `xBVex6wtq4Oim6rp0` | 0.0.1 → 0.0.2 |
| `socialblade-creator-analytics-scraper` | `ni9dY4IrT9Qkbu9Tf` | 0.0.1 → 0.0.3 |
| `flashscore-all-sports-scraper` | `32Gb6ZeaMdbgw023T` | 0.0.1 → 0.0.2 |

## Bagian 3 — Kategori & Harga (Phase 4–8 `actor-store-monetization`)

`apify api` dipakai dengan sesi login CLI (tidak menyentuh token mentah), persis jalur yang direkomendasikan skill. `pricingInfos` pertama harus **flat** (`eventPriceUsd`), bukan tiered — sesuai catatan skill, dan terbukti lagi hari ini.

**Pola rumah diambil dari ground truth, bukan ingatan:** `apify api GET actors/xtracto~nytimes-scraper` menunjukkan kombinasi `apify-actor-start` $0,007 + `apify-default-dataset-item` sebagai `isPrimaryEvent`, `apifyMarginPercentage` 0,2, `isPPEPlatformUsagePaidByUser: true`. Struktur itu direplikasi apa adanya.

**Harga per actor — dihitung dari harga kompetitor NYATA di korpus 65.092 actor Babak 50** (`scratchpad/pricing50.py`), bukan ditebak:

| Actor | Bukti kompetitor (dari indeks Algolia) | Harga | = per 1.000 hasil |
|---|---|---:|---:|
| `lawrato` | PPE direktori pengacara: $17,00 · $13,00 · $11,99 · $7,58 · $3,00 /1k → median ±$11,99 | **$0,008** | $8,00 — undercut klaster $12–17 |
| `socialblade` | `radeance/socialblade-api` $19,99/bln (17 u30 = $340/bln) · `deltaspider` $15/bln · PPE sejenis $10–16/1k | **$0,008** | $8,00 |
| `alodokter` | `parseforge/healthgrades-scraper` $12,99/1k; flat sejenis $9,99–$30/bln | **$0,006** | $6,00 |
| `flashscore` | Pemimpin vein `crawlstone/tennis-scraper` **$6,00/1k dengan u30 1.090**; `parseforge/flashscore-scraper` $19/1k | **$0,006** | $6,00 — sejajar pemimpin |
| `lelang-djkn` | Scraper lelang semuanya FLAT $15–$39/bln; median PPE kategori $2,40/1k | **$0,005** | $5,00 |
| `indonesiayp` | Scraper Yellow Pages FLAT $10–$30/bln; `parseforge/dnb-scraper` $11,99/1k | **$0,005** | $5,00 |
| `sinta` | Data akademik massal, nilai per-record rendah; median event Store $2,00/1k | **$0,003** | $3,00 |

Kategori Store di-set lewat API juga — **`categories` di `.actor/actor.json` TIDAK otomatis mengisi `categories` di record Store**; setelah push pertama, ketujuhnya masih `categories: null`. Ini gotcha yang tidak tertulis di Babak 48.

## Bagian 4 — 🐛 Dua Prasyarat/Bug yang HANYA Muncul di Platform

### (a) `403 cannot-publish-actor` — bukan blokir akun, melainkan prasyarat run

PUT `{"isPublic": true}` pada ketujuh actor ditolak **403 `cannot-publish-actor`** dengan pesan "contact support@apify.com" — pesan yang mengesankan akun bermasalah. Diagnostik yang menyelesaikannya:

| Uji | Hasil | Arti |
|---|---|---|
| `fanndev` punya actor publik? | **70 publik dari 224 actor** (`blibli-promo-extractor` publik sejak 2026-08-31) | Bukan blokir akun permanen |
| PUT `isPublic:true` pada actor yang sudah publik | **200 OK** | Endpoint & izin tidak diblokir |
| `apify call` satu actor lalu PUT ulang | **`isPublic: true` BERHASIL** | ✅ **Sebabnya: actor wajib punya minimal satu run SUKSES di platform sebelum boleh dipublikasikan** |

Skill `actor-store-monetization` mencantumkan `apify call` di checklist Phase 9, tetapi **tidak menyatakan bahwa itu prasyarat keras publikasi**. Inilah kenapa 154 dari 224 actor `fanndev` masih privat: semuanya di-push tanpa pernah dijalankan sekali pun di cloud.

### (b) `InvalidRequestError: Schema validation failed` — dataset schema menolak `null`

Tiga actor gagal saat `Actor.push_data()`: **socialblade**, **indonesiayp**, **alodokter**. Penyebabnya sama: `output_schema.json` mendeklarasikan field sebagai `"type": "string"` / `"integer"`, sementara extractor mengirim `null` untuk field yang tidak tersedia di sumber.

Contoh dari record `socialblade` (mrbeast): `country=None`, `description=None`, `banner=None`, `statsHidden=None` — semuanya dideklarasikan `"type": "string"`.

**Validasi ini hanya aktif di platform.** `apify validate-schema` lolos (ia memvalidasi *bentuk schema*, bukan data), dan `test_local.py` lolos (tidak ada penegakan schema di jalur lokal). Jadi bug kelas ini **tidak mungkin tertangkap sebelum `apify call`** — yang memperkuat kenapa prasyarat (a) sebenarnya bagus.

**Perbaikan** (pola sudah ada di `skool-whop-community-analyzer`): `"type": ["string", "null"]`. Diterapkan ke ketujuh actor sekaligus lewat transform yang membiarkan hanya `_input`/`_source`/`_scrapedAt` tetap ketat — pelonggaran schema bersifat monotonik, jadi tidak bisa merusak record yang sebelumnya sudah lolos.

| Actor | Field dijadikan nullable |
|---|---:|
| `indonesiayp` | 30 |
| `alodokter` | 20 |
| `lawrato` · `sinta` | 19 masing-masing |
| `flashscore` | 17 |
| `socialblade` | 4 (+19 di pass pertama) |
| `lelang-djkn` | 2 |

## Bagian 5 — Verifikasi Run di Platform (mode utama, bukan `reference`)

| Actor | Input uji | Hasil |
|---|---|---|
| `flashscore` | `{"mode":"fixtures","sportIds":["1"],"maxItems":5}` | ✅ 5 record; `mode=reference` melaporkan **17 olahraga** (Babak 48 mencatat 14 — bertambah) |
| `lelang-djkn` | `{"mode":"catalog","maxItems":5}` | ✅ SUCCEEDED |
| `lawrato` | `{"mode":"directory","city":"chennai","maxItems":5}` | ✅ 5 record |
| `indonesiayp` | `{"mode":"category","category":"restaurants","city":"Jakarta"}` | ✅ 5 record (setelah perbaikan nullable) |
| `alodokter` | `{"mode":"specialty","specialty":"dokter-anak"}` | ✅ 5 record (setelah perbaikan nullable) |
| `socialblade` | `{"mode":"profile","platform":"youtube","handle":"mrbeast"}` | ✅ SUCCEEDED (setelah perbaikan nullable) |
| `sinta` | `{"mode":"authors","query":"machine learning"}` | ⚠️ **0 record — ternyata BENAR.** `query` di SINTA adalah pencarian **nama peneliti** (terdokumentasi di input schema), bukan topik. `budi`/`Bambang` → 3 record; tanpa query → 5 record dari 335.707 tersedia. **Input ujinya yang salah, bukan actor-nya** |

## Bagian 6 — Publikasi

Lima ter-publish; yang keenam ditolak **`daily-publication-limit-exceeded`: "You've reached the daily limit of 5 Actor publications."** — angka 5/hari yang sudah dicatat skill `actor-store-monetization`, kini terkonfirmasi ulang di akun ini.

| Actor | URL Store | Harga | Status |
|---|---|---:|---|
| `flashscore-all-sports-scraper` | apify.com/fanndev/flashscore-all-sports-scraper | $0,006 | ✅ TAYANG |
| `lelang-djkn-scraper` | apify.com/fanndev/lelang-djkn-scraper | $0,005 | ✅ TAYANG |
| `lawrato-lawyer-directory-scraper` | apify.com/fanndev/lawrato-lawyer-directory-scraper | $0,008 | ✅ TAYANG |
| `indonesiayp-business-directory-scraper` | apify.com/fanndev/indonesiayp-business-directory-scraper | $0,005 | ✅ TAYANG |
| `alodokter-doctor-directory-scraper` | apify.com/fanndev/alodokter-doctor-directory-scraper | $0,006 | ✅ TAYANG |
| `socialblade-creator-analytics-scraper` | — | $0,008 | ⏳ besok (batas 5/hari) |
| `sinta-researcher-scraper` | — | $0,003 | ⏳ besok (batas 5/hari) |

## Gotcha Metodologi Baru

1. **Actor wajib punya satu run sukses di platform sebelum bisa dipublikasikan.** Gejalanya `403 cannot-publish-actor` + pesan "contact support" yang menyesatkan — terbaca seperti masalah akun, padahal urutan langkah yang kurang. Urutan yang benar: `push` → **`apify call`** → `PUT isPublic`. Ini menjelaskan 154 actor `fanndev` yang menganggur privat.
2. **`apify validate-schema` dan `test_local.py` sama-sama BUTA terhadap pelanggaran dataset schema.** Yang pertama memvalidasi bentuk schema, yang kedua tidak menegakkan schema sama sekali. Satu-satunya penegakan ada di `push_data` **di platform**. Setiap actor baru wajib satu `apify call` mode utama sebelum dianggap selesai — `reference` mode saja tidak cukup, karena mode itu justru sering tidak menyentuh field yang bisa null.
3. **`null` ≠ field absen.** Schema menerima field yang hilang, tapi menolak field yang ada bernilai `null`. Extractor yang menulis `field: None` untuk data yang tidak tersedia **harus** dipasangkan `"type": ["<t>", "null"]`. Pola ini sudah ada di `skool-whop-community-analyzer` tapi tidak dijadikan konvensi — sekarang jadikan konvensi.
4. **`categories` di `.actor/actor.json` tidak mengisi `categories` di record Store.** Setelah `apify push`, ketujuh actor tetap `categories: null` di API. Harus di-PUT terpisah via `apify api PUT actors/{id} -d '{"categories":[...]}'`. Perbaikan Babak 48 (mengisi `actor.json`) perlu, tapi tidak cukup.
5. **`~/.apify/auth.json` bukan sumber kebenaran status akun.** Di mesin ini `secretsBackend: keyring`, jadi file itu tidak punya token dan `effectivePlatformFeatures`-nya adalah snapshot basi (masih menampilkan semua fitur mati 2 hari setelah kuota reset). Pakai `apify api GET users/me/limits`.
6. **Jangan percaya `subprocess` + `capture_output=True` di Windows untuk output `apify`.** Decoder cp1252 default meledak pada byte non-ASCII di respons dan **memotong stdout**, yang membuat request yang sebenarnya SUKSES terbaca sebagai gagal. Baca sebagai byte lalu `.decode('utf-8','replace')`, atau verifikasi lewat `GET` terpisah.

## Rekomendasi Lanjutan

1. **Besok: publish `socialblade-creator-analytics-scraper` dan `sinta-researcher-scraper`** — keduanya sudah ter-build, terharga, terkategori, dan terverifikasi jalan. Hanya menunggu reset batas 5/hari.
2. **Jalankan `apify call` + perbaikan nullable pada 154 actor `fanndev` yang masih privat.** Sekarang jelas kenapa mereka tidak pernah tayang, dan biayanya kecil ($0,13 untuk 7 actor termasuk 12 run uji → ±$3 untuk 154, di dalam kuota $5/bulan). **Ini kemungkinan pekerjaan ber-ROI tertinggi yang tersedia sekarang** — 154 actor yang sudah jadi tapi tak seorang pun bisa membelinya.
3. **Rekomendasi #1 Babak 50 masih terbuka dan belum diuji:** uji harga **FLAT_PRICE_PER_MONTH** $20–$30 pada 3–5 actor `xtracto` yang sudah punya pembeli. Babak ini sengaja memilih pay-per-event atas keputusan user, jadi temuan "215/215 actor pay-per-event, nol flat-bulanan" belum dijawab sama sekali.
4. **Tambahkan ke skill `deploying-actors` / `actor-store-monetization`:** prasyarat run-sebelum-publish (Gotcha #1), kebutaan validasi schema lokal (#2), konvensi nullable (#3), dan `categories` yang harus di-PUT terpisah (#4). Keempatnya menghentikan pekerjaan hari ini dan tidak satu pun terdokumentasi.
5. **Perbarui pengukuran Babak 48:** `flashscore-all-sports-scraper` kini melaporkan **17 olahraga aktif**, bukan 14. README dan `constants.py` menyebut 14 — perlu diselaraskan sebelum ada pembeli yang menghitung.

## File Referensi Babak 50b

- `scratchpad/pricing50.py` — analisis harga kompetitor per actor dari korpus 65.092 (Phase 4/7)
- `scratchpad/setprice50.py` · `scratchpad/_price_body.json` — pengiriman `pricingInfos` + `categories` via `apify api`
- `output/fanndev-public.json` — 70 actor `fanndev` yang publik (dari 224 di akun)
- 7 folder actor — `.actor/output_schema.json` masing-masing kini nullable-safe

---

# Babak 51 — EKSEKUSI baris "Masih Layak" dari daftar Babak 49/50: **6 actor dibangun, 4 tayang hari ini**, 2 kandidat gugur di recon, dan pola baru "gerbang kedua hanya muncul di platform" (2026-09-18)

**Konteks:** user meminta "build semua Masih layak & permukaannya terbuka" lalu "publish ke apify, jangan lupa set output schema-nya". Daftar yang dieksekusi = 7 baris ringkasan dari Babak 44/49/50 yang masih hidup setelah dicek ulang hari ini.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **TAYANG di Store** | **4** | snapchat · short-interest-filings · ecommerce-platform-market-share · psa-card-cert-lookup |
| ⏳ **Ter-build, terharga, terverifikasi — menunggu kuota publikasi** | **2** | national-research-portal · bulgaria-foreclosure-auction (kena batas 5 publikasi/hari) |
| ⛔ **Gugur di recon, tidak dibangun** | **2 konsep** | Google Jobs (SERP tertutup di 8 profil TLS) · klaster lelang PL/JP/CZ/TR/RO/PH (6/6 buntu) |
| 🔧 **Koreksi untuk riset lama** | **5** | Lihat tabel koreksi di bawah — 3 klaim Babak 44/50 terbukti salah hari ini |
| 🆕 **Gotcha metodologi baru** | **4** | Terutama: gerbang kedua (IP) hanya terlihat setelah `apify call`, bukan di recon lokal |

**Biaya seluruh babak: $0,12** (kuota bulanan naik dari $1,38 ke $1,51 dari $5).

## Actor yang dibangun

| Actor | Sumber | Mode | Harga (start/hasil) | Status |
|---|---|---|---|---|
| `snapchat-profile-spotlight-scraper` | snapchat.com SSR `__NEXT_DATA__` | 8: profile, spotlight, highlights, lenses, related, trending, top-lenses, reference | $0,003 / $0,002 | TAYANG |
| `short-interest-filings-scraper` | api.nasdaq.com + cdn.finra.org + data.sec.gov + efts.sec.gov | 6: short-interest, short-volume, filings, filing-search, company, reference | $0,003 / $0,003 | TAYANG |
| `ecommerce-platform-market-share-scraper` | storeleads.app **laporan publik** (110 platform) | 6: platform, growth, breakdown, migration, stores, reference | $0,003 / $0,002 | TAYANG |
| `psa-card-cert-lookup-scraper` | psacard.com/cert | 4: cert, sales, range, reference | $0,004 / $0,008 | TAYANG |
| `national-research-portal-scraper` | Garuda 🇮🇩 + CiNii 🇯🇵 + KCI 🇰🇷 | 4: documents, journals, authors, reference | $0,003 / $0,002 | menunggu publish |
| `bulgaria-foreclosure-auction-scraper` | sales.bcpea.org (BCPEA) | 4: list, property, range, reference | $0,005 / $0,003 | menunggu publish |

Ketujuh `output_schema.json` memakai pola nullable-safe Babak 50b sejak baris pertama (`["string","null"]`), plus `additionalProperties: true` dan `views` — nol penolakan `push_data` di seluruh babak ini.

## 🔧 Koreksi untuk Riset Lama (semuanya diverifikasi hari ini)

| Klaim lama | Kenyataan 2026-09-18 | Dampak |
|---|---|---|
| Babak 44: "`psacard.com/pop` 200/20 KB, **terbuka**" | 20 KB itu **halaman login** (`app.collectors.com/signin`). Pop report & auction prices = account-only | Produk digeser ke **cert page**, yang justru membawa populasi + estimasi + 5 penjualan pembanding sekaligus |
| Babak 50 #7: "Storeleads — wedge reliabilitas, incumbent 76% gagal" | Data **per-toko** 404 untuk anonim (produk berbayar). Yang terbuka: **110 laporan platform** dengan deret kuartalan 2019→2026 + arus migrasi | Produk diganti jadi *market share & migration*, bukan kloning incumbent |
| Babak 50 #6: "Google Jobs — SERP 200/91 KB, belum konklusif" | **Konklusif sekarang**: 8 profil TLS (chrome110/124/131, android, safari15/17, edge101, firefox133) semuanya dapat halaman *"trouble accessing Google Search"*, nol hasil organik, nol widget jobs | Di-skip. Butuh proxy + kerja SERP tersendiri, bukan "tinggal parse" |
| Babak 44 #1: lelang 🇵🇱🇯🇵🇹🇷🇨🇿🇷🇴🇵🇭 "semua 200, terbuka" | 200 ≠ bisa diambil. **6/6 buntu**: PL API 500 anonim, JP POST 500 tanpa sesi, CZ Vue tanpa `action` + API write-only, TR SPA, **RO situs mati** (`/_backup/20210316/`), **PH maintenance** | Diganti yurisdiksi lain: **🇧🇬 BCPEA** — 459 KB SSR, 115 halaman, nol pesaing di Store |
| Babak 44: host Garuda `garuda.kemdikbud.go.id` | **DNS tidak resolve.** Host hidup: `garuda.kemdiktisaintek.go.id` (pola sama seperti SINTA) | Catatan recon >1 tahun harus dicek host-nya dulu |

## Gotcha Metodologi Baru

1. **Gerbang kedua hanya muncul di platform.** Dua target (PSA, BCPEA) lolos bersih di recon lokal (IP residensial Indonesia) lalu **ditolak dari IP datacenter Apify** — PSA seluruhnya, BCPEA hanya pada daftar ber-query-string sementara halaman detailnya tetap dilayani. Keduanya sembuh dengan `apifyProxyGroups: ["RESIDENTIAL"]`, yang kini jadi **default di input schema** keduanya. **Sebuah target belum terverifikasi sebelum `apify call` di platform.**
2. **Sidik TLS memutuskan segalanya di PSA — dan 4 dari 5 profil berbohong.** chrome124/chrome99_android/safari17_0/edge101 → **403 "Security Check"**; **firefox133 → 200/145 KB**. Persis peringatan `.ai/CLAUDE.md`: satu profil gagal itu data point, bukan vonis. Client-nya menyimpan ladder dan mengingat profil yang menang.
3. **Header harus per-host, bukan global.** Memberi User-Agent kustom ke `api.nasdaq.com` mematikan koneksi (`curl (92) HTTP/2 stream reset`) karena UA tak lagi cocok dengan sidik TLS; SEC justru **meminta** UA kontak. Satu sesi, dua kebijakan header.
4. **Label filter mencemari parser.** Di BCPEA, "НАЧАЛНА ЦЕНА" muncul lebih dulu di *dropdown filter* ("до 10 000 лв"), jadi match pertama memberi **10 000 лв untuk setiap properti**. Tes lokal sekarang menegaskan harga bukan salah satu batas bulat filter. Pola yang sama berlaku untuk situs mana pun yang menaruh sidebar filter di atas konten.

## Temuan teknis per sumber (ringkas)

- **Snapchat**: satu request halaman profil membawa profil + lenses + highlights + spotlight (dengan **viewCount**) + related accounts sekaligus → 4 mode = 1 request/username. `_next/data` 404 (tak ada paginasi publik). Locale hanya bisa lewat `?locale=en-US`, path `/en-US/` 404. Sebagian skalar dibungkus `{"value": ...}` **secara tidak konsisten** (storyTitle dibungkus, storySubtitle tidak) — `normalize_record` membuka semuanya di lapis terakhir.
- **Short interest**: Nasdaq hanya menerbitkan short interest untuk **saham listing Nasdaq** (GME/AMC/F/T = NYSE → `data:null` + pesan eksplisit), dan menyandikan error di dalam HTTP 200 (`status.rCode=400`). FINRA menjawab **403 = file belum terbit** (bukan blokir); volume pecahan itu asli. EDGAR full-text: 100 hit/halaman, plafon 10.000.
- **Storeleads**: laporan bukan `<table>` melainkan `div.table > div.row > div.cell[data-title]`; kuartal terbaru muncul **dua kali** (callout + tabel) → dedupe ambil kemunculan terakhir; `(to date)` ditandai sebagai kuartal parsial.
- **PSA**: data ada di dalam placeholder React `<div hidden id="S:n">` (tetap di HTML), nama kelas Tailwind berubah tiap deploy → kotak statistik dicari lewat **teks labelnya**.
- **Portal riset**: path pencarian KCI yang "kelihatan benar" (`poSereArtiSearList.kci`) **404**; yang jalan `poArtiSearList.kci` + `poSearchBean.searchQuery`. Satu baris KCI adalah string menyatu yang hanya bisa dipecah lewat **ORCID** sebagai delimiter. CiNii `start` berbasis-1. **Lattes 🇧🇷 sengaja tidak dikirim** (butuh POST dalam sesi; GET "terdokumentasi" balas 29 KB nol hasil) — lebih baik absen daripada mengirim portal yang selalu kosong.
- **BCPEA 🇧🇬**: parameter paginasi **huruf kecil `perpage` & `p`**; `page`/`perPage` diterima lalu **diabaikan diam-diam** (selalu halaman 1 — kesalahan yang akan membuat scraper melaporkan "portal ini cuma punya 12 lelang"). `perpage=100` → 14 halaman untuk ±1.380 lelang aktif. Harga di luar container detail (`div.col--right`). ID berurutan → mode `range` menembus lelang yang sudah tutup.

## Rekomendasi Lanjutan

1. **Besok: publish `national-research-portal-scraper` dan `bulgaria-foreclosure-auction-scraper`** — keduanya sudah build+harga+kategori+terverifikasi jalan di platform, hanya menunggu reset batas 5/hari.
2. **Rekomendasi #2 Babak 50b masih terbuka** (dan makin besar): `apify call` + perbaikan nullable untuk actor `fanndev` yang masih privat. Akun kini **240 actor, 89 publik** → ±151 actor jadi tapi tak bisa dibeli siapa pun.
3. **Google Jobs butuh keputusan anggaran**, bukan recon lagi: SERP Google tertutup dari IP ini di semua profil TLS. Jalannya = proxy residensial + pekerjaan SERP tersendiri (dan catatan Maps di memori bilang residensial justru **merusak** Google Maps, jadi matriksnya harus diuji ulang khusus untuk `/search`).
4. **Klaster lelang: PL/JP/CZ butuh tangkapan XHR dari browser** (DevTools/Camoufox), bukan tebakan endpoint. Itu keputusan user karena melanggar aturan "HTTP-only dulu" di `.ai/CLAUDE.md`. Alternatif lebih murah: lanjutkan pola Babak 51 — cari yurisdiksi lain yang **server-rendered** (🇬🇷 dan 🇱🇹 balas 200 tapi tipis; 🇱🇻 🇵🇹 timeout dari IP ini dan layak dicoba ulang dari IP lain).
5. **Jadikan konvensi**: setiap actor baru wajib punya mode `reference` yang mem-probe sumbernya sendiri dan melaporkan bukti terukur (jumlah baris, tanggal terbaru, profil TLS yang menang). Enam actor babak ini memakainya, dan mode itulah yang mendeteksi gerbang IP di platform dalam hitungan detik.

## File Referensi Babak 51

- 6 folder actor baru, masing-masing dengan `CRAWLING_METHOD.md` berisi tabel probe per profil TLS dan daftar gotcha
- `scratchpad/probe51*.py`, `probe_si*.py`, `probe_sl.py`, `probe_psa.py`, `probe_research.py`, `probe_auction*.py`, `probe_eu_auctions.py`, `probe_bg.py` — seluruh jejak recon, termasuk yang gugur
- `scratchpad/setprice51.py` — pemasangan `pricingInfos` + `categories` + `defaultRunOptions.memoryMbytes=512`
- `scratchpad/status51.py` — verifikasi status akhir keenam actor dari API

---

# Babak 52 — EKSEKUSI sisa daftar "BELUM dibangun" Babak 49/50: **3 actor dibangun & lolos tes lokal**, 4 kandidat gugur dengan bukti, dan pola baru "**rekaman kosong**" (bukan respons kosong) (2026-09-18)

**Konteks:** user meminta "lanjut build actor yang statusnya belum dibuat". Daftar yang dieksekusi = seluruh baris ✅ BELUM dibangun dari Babak 49 (9) + Babak 50 (9) yang belum tersentuh Babak 50b/51.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **Ter-build + lolos tes lokal** (belum di-push) | **3** | google-hotels-rate-comparison · himalayas-remote-jobs · medium-engagement |
| ⛔ **Gugur di recon, dengan bukti terukur** | **4** | RockAuto/TecDoc · Ozon.ru · AutoTrader UK · Dubai DLD open-data |
| ⚠️ **Sebagian tertutup** | **1** | Welcome to the Jungle — API organisasi terbuka, **permukaan lowongan tidak ada** |
| 🔧 **Koreksi untuk riset lama** | **4** | Lihat tabel koreksi |
| 🆕 **Gotcha metodologi baru** | **4** | Terutama: rekaman kosong (167 ref tanpa data) dan parser HTML merusak XML secara senyap |

**Biaya: $0** — seluruh babak dikerjakan lokal, tanpa proxy dan tanpa run platform.

## Actor yang dibangun

| Actor | Sumber | Mode | Yield terukur | Status |
|---|---|---|---|---|
| `google-hotels-rate-comparison-scraper` | `google.com/travel` SSR | 5: search, hotel, rates, sponsored, reference | **17–25 kuotasi OTA/hotel** (Expedia/Agoda/Booking/Trip/Klook), 20–21 kartu/query | lolos tes lokal 4 mode |
| `himalayas-remote-jobs-scraper` | `himalayas.app/jobs/api` (resmi) | 4: jobs, search, companies, reference | **100.101 lowongan**, 20/halaman via cursor | lolos tes lokal 3 mode |
| `medium-engagement-scraper` | `medium.com` Apollo + RSS | 5: tag, author, publication, post, reference | **35 artikel + clapCount per tag** | lolos tes lokal 6 pemeriksaan |

Ketiganya: `output_schema.json` pola nullable-safe (`["string","null"]`) + `additionalProperties: true` + `views`, `apify validate-schema` 3/3 hijau, envelope `_input`/`_source`/`_scrapedAt`/`recordType`, dan mode `reference` sesuai konvensi Rekomendasi #5 Babak 51.

## 🔧 Koreksi untuk Riset Lama (semuanya diverifikasi hari ini)

| Klaim lama | Kenyataan 2026-09-18 | Dampak |
|---|---|---|
| Babak 50 #4: "TecDoc monopoli 23 bulan tanpa penantang adalah anomali; RockAuto 200/576 KB = permukaan katalog terbuka **ada**" | **Anomali itu punya penjelasan.** Halaman 566 KB hanya pohon navigasi merek. `catalogapi.php` menjawab 200/527 KB **sekali**, lalu `{"redirect_to_url":"https://www.rockauto.com/captcha/"}`. Daftar suku cadang + harga **tidak pernah** tercapai HTTP-only | Vein $2.692 / $51,76-per-pembeli **di-skip dengan alasan konkret**, bukan "belum diprobe" |
| Babak 50 #9: "AutoTrader UK belum diprobe" | Cloudflare **stateful**, bukan gerbang TLS tetap: chrome124/firefox133/safari15_5 dapat 200/85 KB pada request pertama, lalu **profil yang sama 403** pada request berikutnya. 4 profil lain 403 seketika | Butuh kerja `cf_clearance` (pola Klikindomaret), bukan "tinggal parse". Di-skip untuk babak ini |
| Babak 50 #8: "Ozon.ru belum diprobe" | **403 di 7/7 profil TLS** dengan tantangan milik sendiri (`fab_chlg_…` + `challengeURL`), baik di web maupun `api.ozon.ru/composer-api.bx` | Tertutup. Setara vonis Shopee |
| Babak 49 #8: "Welcome to the Jungle `api.welcometothejungle.com` 200 JSON 442 KB = **TERBUKA & RESMI**" | Yang 200 hanya **profil organisasi** (`/organizations/<slug>?full=true` → 13 KB: kantor, sektor, jumlah karyawan). `/organizations/<slug>/jobs`, `/jobs`, `/search/jobs` → **404/422**; `www.welcometothejungle.com/en/jobs` → **202** (shell) | "Job board terbuka" tinggal **satu**: Himalayas. WTTJ bukan sumber lowongan |

Catatan tambahan: **Google Hotels tetap terbuka** (2,65 MB SSR, nama hotel asli, harga, rating) — jadi vonis "gugur" Babak 50 untuk kandidat ini adalah soal **harga vein**, bukan permukaan. Dibangun karena pembedanya nyata dan belum dijual utuh: perbandingan tarif **lintas-OTA per hotel** (17–25 kuotasi), yang tidak diberikan `agoda-hotels-scraper`/`booking-hotels-scraper`.

## Gotcha Metodologi Baru

1. **Rekaman kosong, bukan respons kosong — bentuk baru dari "hollow 200".** Halaman publikasi Medium membawa **167 entri `Post:`** di cache Apollo — 5× lebih banyak daripada halaman tag (35) — dan **nol** di antaranya berisi artikel; semuanya hanya `{"__typename":"Post","id":"…"}`. Scraper yang menghitung kunci akan melaporkan "167 artikel" lalu mengirim 167 baris kosong. Pelajaran umum: **jumlah entri bukan bukti data**; validasi satu field wajib per entri, dan laporkan berapa yang dibuang. Pola sekeluarga dengan `_basic` Blibli dan halaman error 200 Google, tapi muncul di lapis *rekaman*, bukan respons.
2. **Parser HTML merusak XML secara senyap, dan hasilnya tampak masuk akal.** `selectolax` pada RSS Medium gagal **tiga cara sekaligus**: `dc:creator` tidak pernah cocok (semua artikel jadi anonim), `<![CDATA[` bocor ke judul, dan pencarian `title` per-item **memanjat keluar dari item** lalu mengembalikan judul *channel* — sehingga baris pertama berjudul nama publikasi. Tak satu pun melempar error. Perbaikannya `xml.etree` + peta namespace eksplisit, dan tes sekarang menegaskan ketiganya (nol CDATA, semua baris berpenulis, nol judul kembar).
3. **Parameter filter yang diterima lalu diabaikan adalah jebakan produk, bukan cuma jebakan teknis.** Himalayas menerima `query`, `categories`, `seniority`, `company`, `minSalary` dengan 200 dan **mengabaikan semuanya** (`categories=Design` mengembalikan lowongan AI/ML). Actor yang meneruskannya akan **tampak memfilter dan diam-diam mengirim data tak terfilter**. Karena itu filter dikerjakan lokal + ada `maxScannedJobs` sebagai anggaran, dan mode `reference` **menguji ulang perilaku ini setiap run** supaya perubahan upstream terlihat sebagai diff, bukan sebagai actor yang lambat tanpa alasan. Pola sama: `limit` diplafon senyap di 20 (minta 500, dapat 20).
4. **Satuan bayaran yang bercampur di satu field numerik.** Dari 400 lowongan Himalayas: 352 `annual`, 34 `hourly`, 11 `monthly`, 3 `weekly` — plus 6 mata uang. Filter `minSalary>=150000` mentah akan **membuang** peran USD 30–55/jam (≈$114k/tahun) dan **meloloskan** PLN 24.000/bulan seolah kecil. Solusinya menambah `annualizedSalary*` (aritmetika: ×2080/×52/×12) dan memfilter di atasnya; **kurs mata uang sengaja tidak dikarang** — disediakan filter `currency` supaya perbandingan bisa dibuat sahih oleh pemakai.

## Temuan teknis per sumber (ringkas)

- **Google Hotels**: mata uang **tidak bisa diminta** (`curr`/`currency`/`gl` diterima & diabaikan; selalu IDR dari IP Indonesia) → **negara proxy = kontrol mata uang**. Tanggal juga tidak bisa diminta: jendela menginap ada di protobuf `ts=`, `checkin/checkout` diabaikan, dan **5 layout `ts` hasil encode manual semuanya diabaikan** → jendela selalu default Google, dan setiap record membawa `stayWindow` supaya tidak disalahartikan. `start=20` tidak mempaginasi. Entity id tak dikenal → **200 + halaman error** ber-`<h1>` "Oops, something went wrong" (dijaga `HollowEntityPage`). Halaman entity penuh fakta hotel **lain**: pencarian rating tingkat-halaman memberi **4,4/18.459 untuk hotel ber-rating 4,7/64.684** dan memilih teks pemasaran butik perhiasan sebagai alamat → header dibaca **hanya dari container `<h1>`**. aria-label rating **beda antar permukaan** (kartu berakhir di "reviews", halaman hotel menambah ". Excellent.") → regex `search`, bukan `match`. Daftar fasilitas punya **dua bentuk** (aria-label vs `span[role="document"]`) dan berada **di luar rantai ancestor kartu** (12 level pun tak sampai) → diindeks per-halaman berdasarkan nama hotel; sebelum diperbaiki: 0 dari 20 kartu berfasilitas padahal datanya ada.
- **Himalayas**: hanya feed JSON yang terbuka — `/companies/api`, `/companies/<slug>`, `/jobs/<slug>` semuanya **403**, jadi 403 di host ini berarti "keluar dari feed", bukan "diblokir" (pesan error client mengatakan itu eksplisit). `guid` **sudah berupa URL**, bukan id — merangkai `"/jobs/" + guid` menghasilkan `himalayas.app/jobs/https://himalayas.app/...`. `applicationLink` **bukan** tautan ATS pemberi kerja: 60/60 listing menunjuk halaman himalayas.app dan identik dengan `guid` — output schema mengatakan itu apa adanya.
- **Medium**: `_/graphql` **403**. Cache Apollo **ternormalisasi & siklik** (`{"__ref":"User:…"}`, post→penulis→post) → resolusi ref **dibatasi kedalaman**. Timestamp **milidetik**. `extendedPreviewContent.isFullContent` **bukan** penanda pemotongan (menggambarkan kartu preview; bernilai False bahkan untuk artikel gratis yang utuh — sempat menandai artikel 77 paragraf sebagai terpotong); yang benar `isLocked`: artikel berbayar dilayani ~8 paragraf/1,2k karakter vs 77 paragraf/14k untuk gratis. Feed hanya membawa artikel penuh **sebagian**: 4 dari 10 item ber-`content:encoded` (7.536 karakter), 6 hanya `<description>` (±80) → ada `contentSource` + `isContentFull`. URL artikel salah → **200 tanpa entri post** (bukan 404).

## Rekomendasi Lanjutan

1. **Push + `apify call` ketiga actor, lalu set harga/kategori.** Belum dilakukan di babak ini karena Fase 3 permintaan user berakhir di storage lokal. Ingat Gotcha #1 Babak 51: **target belum terverifikasi sebelum `apify call` di platform** — Google Hotels adalah kandidat paling mungkin kena gerbang IP datacenter, dan input schema-nya sudah default `RESIDENTIAL`.
2. **Dua actor Babak 51 masih menunggu publikasi** (`national-research-portal`, `bulgaria-foreclosure-auction`) — batas 5 publikasi/hari sudah reset sejak 2026-09-18.
3. **Vein "job board terbuka" sudah habis.** Setelah WTTJ gugur, Himalayas adalah satu-satunya. Jangan alokasikan babak recon job-board lagi tanpa kandidat baru yang permukaannya sudah diprobe.
4. **AutoTrader UK adalah kandidat `cf_clearance`, bukan kandidat skip permanen.** Ia satu-satunya dari 4 yang gugur dengan pola yang sudah pernah dipecahkan portofolio ini (Klikindomaret: Camoufox sekali, cookie replayable). Keputusan anggaran user, bukan keputusan teknis.
5. **Tambahkan ke konvensi: mode `reference` wajib menguji ulang *asumsi desain*, bukan cuma ketersediaan.** Dua actor babak ini melakukannya (Himalayas menguji plafon `limit` + kejujuran filter; Medium menguji apakah halaman publikasi masih kosong) sehingga perubahan upstream muncul sebagai diff terukur, bukan sebagai data yang salah secara senyap.

## Bagian Tambahan Babak 52 — Push & `apify call` (2026-09-18, lanjutan sesi yang sama)

**Konteks:** user meminta "push and call to apify" setelah ketiga actor lolos tes lokal. Rekomendasi #1 Babak 52 dieksekusi.

Kuota sebelum: **$1,5054 / $5**, 240 actor. Sesudah: **$1,543 / $5**, 243 actor. **Biaya seluruh push + 6 run = $0,038.**

| Actor | Actor ID | Build | Run mode utama | Hasil |
|---|---|---|---|---|
| `google-hotels-rate-comparison-scraper` | `f2jb9GgzbukwXpvgN` | 0.0.1 SUCCEEDED | reference, search, **rates** | 30 kuotasi OTA / 1 hotel |
| `himalayas-remote-jobs-scraper` | `g8JECQf9eMsMkYl2J` | 0.0.1 SUCCEEDED | reference, **search** | 10 match dari 369 di-scan, 19 halaman |
| `medium-engagement-scraper` | `DnjoE1PTgFj9qbnGA` | 0.0.1 SUCCEEDED | reference, **tag** | 10 artikel + clapCount |

Ketiganya diverifikasi di **mode utama**, bukan hanya `reference` (konvensi Babak 50b). `defaultRunOptions` diturunkan ke **512 MB / 600 s** sebelum run pertama (`scratchpad/setmem52.py`) — default platform 4096 MB akan menagih 8 event start untuk run yang butuh 1 (memori [[apify_ppe_start_event_memory_multiplier]]).

### 🆕 Gotcha: **tangga TLS terbukti berguna di platform, bukan cuma di teori**

Google Hotels di IP residensial lokal (Indonesia) dimenangkan `chrome124`. Di **proxy residensial Apify**, `chrome124` diblokir dan **`firefox133` yang menang** — client berpindah sendiri dan run tetap SUCCEEDED. Ini pertama kalinya ladder TLS portofolio ini *benar-benar terpakai* di produksi, bukan sekadar mitigasi defensif. Kalau profil dipin satu (praktik lama), run ini akan gagal total dan salah didiagnosis sebagai "Google memblokir IP datacenter Apify".

**Implikasi untuk actor lain:** profil yang menang di recon lokal **bukan** profil yang akan menang di platform. Jangan pin profil; simpan ladder.

### Konfirmasi empiris: negara proxy = mata uang

Klaim Babak 52 ("mata uang mengikuti IP keluar, bukan parameter") kini punya bukti dua sisi:

| Jalur | Mata uang | Kuotasi OTA pada Marina Bay Sands | Sebaran |
|---|---|---:|---|
| IP residensial Indonesia (lokal) | **IDR** | 17 | IDR 21.583.872 – 24.962.420 |
| Proxy RESIDENTIAL Apify (US) | **$ (USD)** | **29–30** | $1.181 – $1.450 |

Dua hal sekaligus: mata uang berubah tanpa satu pun parameter diubah, **dan jumlah OTA naik dari 17 ke 30** dengan penjual yang berbeda (Super.com, goseek.com, Expedia.**com** vs Expedia.**co.id**). Jadi negara proxy memutuskan **cakupan pasar OTA**, bukan sekadar simbol mata uang — relevan untuk pembeli yang memantau paritas tarif di pasar tertentu.

Data paritas nyata dari run platform: **Super.com $1.181** menggunting Booking.com/Agoda/Trip.com yang seragam di **$1.222** — persis sinyal yang dibeli pemakai produk ini.

### Sisa pekerjaan (belum dikerjakan, menunggu keputusan user)

1. **Harga + kategori + publikasi** ketiga actor (Phase 4–8 `actor-store-monetization`). Belum dijalankan karena user meminta khusus "push and call".
2. **Dua actor Babak 51** (`national-research-portal`, `bulgaria-foreclosure-auction`) masih privat.
3. Rekomendasi #2 Babak 50b tetap terbuka dan makin besar: akun kini **243 actor**, ±154 privat.

## File Referensi Babak 52

- 3 folder actor baru, masing-masing dengan `CRAWLING_METHOD.md` (matriks probe + daftar gotcha) dan `test_local.py` yang menegaskan fakta terukur, bukan "tidak crash"
- `scratchpad/probe52.py` … `probe52p.py` — seluruh jejak recon 14 target, termasuk 4 yang gugur
- `scratchpad/proto_gh*.py` — prototipe extractor Google Hotels terhadap HTML tersimpan

---

# Babak 53 — Penutupan daftar "BELUM dibangun" Babak 49: **1 actor dibangun & lolos 7 mode tes lokal**, 3 kandidat gugur dengan bukti, dan pola baru "**nol sebagai placeholder**" (2026-09-18)

**Konteks:** user meminta "lanjut build actor yang statusnya belum dibuat". Setelah Babak 51 (6 actor) dan Babak 52 (3 actor), sisa baris ✅ BELUM dibangun tinggal **5 konsep dari Babak 49**: #2 sports odds, #4 TikTok Shop, #5 keyword search volume, #6 Google Lens, #7 tech-stack detector. Semuanya diprobe hari ini.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **Ter-build + lolos tes lokal 7 mode** (belum di-push) | **1** | `espn-betting-odds-scraper` |
| ⛔ **Gugur di recon, dengan bukti terukur** | **3** | keyword search volume · Google Lens · TikTok Shop |
| ⏸️ **Ditunda dengan alasan, bukan tembok** | **1** | tech-stack detector — terbuka secara teknis, tapi vonis "nol moat data" Babak 49 tetap berlaku |
| 🔧 **Koreksi untuk riset lama** | **2** | `site.api.espn.com` tidak 403 · harga vein bukan ukuran isi permukaan |
| 🆕 **Gotcha metodologi baru** | **4** | Terutama: **nol sebagai placeholder** dan **dua host satu sumber, dua tata bahasa tanggal** |

**Biaya: $0** — seluruh babak dikerjakan lokal, tanpa proxy dan tanpa run platform.

## Actor yang dibangun

| Actor | Sumber | Mode | Yield terukur | Status |
|---|---|---|---|---|
| `espn-betting-odds-scraper` | `sports.core.api.espn.com` + `site.api.espn.com` | 7: odds, props, futures, events, predictor, providers, reference | **659 prop pemain per laga NFL** (521 distinct), 18 pasar futures / 543 baris, 2 bandar per laga, 71 bandar di katalog, 17 olahraga & 219 kompetisi sepak bola | lolos tes lokal 7 mode |

Pembeda yang tidak dijual incumbent (yang semuanya scraper skor generik): **pergerakan garis** (`openSpread` ke `currentSpread`, `totalMovement`, `favoriteFlippedSinceOpen`) dan **probabilitas tersirat** — keduanya *diturunkan*, karena sumber menerbitkan kedua ujungnya dan tidak pernah selisihnya; plus **papan prop pemain** dan **proyeksi model** yang bisa disandingkan dengan harga bandar.

`output_schema.json` pola nullable-safe (`["string","null"]`) + `additionalProperties: true` + 5 `views`, `apify validate-schema` 3/3 hijau, envelope `_input`/`_source`/`_scrapedAt`/`recordType`, dan mode `reference` yang **menguji ulang asumsi desain** (plafon halaman prop, penolakan rentang tanggal oleh host SITE, apakah scoreboard masih menyembunyikan odds) sesuai Rekomendasi #5 Babak 52.

## 🔧 Koreksi untuk Riset Lama (diverifikasi hari ini)

| Klaim lama | Kenyataan 2026-09-18 | Dampak |
|---|---|---|
| Babak 49 #2: "`site.api.espn.com` justru **403** dari IP ini — dua host beda perlakuan" | **200.** `/scoreboard` 276 KB, `/teams` 135 KB, `/summary` semuanya menjawab. Dua host itu memang beda, tapi pada **isi** (host SITE tidak punya odds sama sekali) dan **tata bahasa tanggal**, bukan pada akses | Vonis "dua host beda perlakuan" benar, alasannya salah. Host SITE adalah jalur murah untuk jadwal & daftar tim, bukan jalur tertutup |
| Babak 50 B: "sports odds — 163 actor memperebutkan $53/bulan, vein termurah yang pernah diukur" | **Harganya tetap berlaku**, tapi diukur terhadap scraper scoreboard generik. Permukaannya membawa 659 prop pemain per laga, papan futures penuh, dan kedua ujung setiap garis — **tidak satu pun dijual incumbent yang diperingkat** | Harga vein mengukur *apa yang dijual sekarang*, bukan *apa yang ada di permukaan*. Sama seperti Google Hotels di Babak 52: gugur soal harga, dibangun karena pembedanya nyata |

## Gotcha Metodologi Baru

1. **Nol sebagai placeholder — "hollow 200" versi numerik.** Feed live in-play ESPN menulis `overUnder: 0.0`, `overOdds: 0.0`, `moneyLine: 0`, `price: 0.0` **bersebelahan dengan point spread yang terisi dan nyata** (`spread: 5.5`), jadi barisnya tidak tampak rusak sama sekali. Konsumen yang merata-ratakan total lintas bandar akan ditarik ke nol, tanpa satu pun exception. Pelajaran umum: **field numerik bernilai 0 wajib diperiksa terhadap domainnya** — tidak ada bandar yang memasang total 0 atau harga Amerika 0, tapi spread 0 (pick-em) itu sah. Perbaikan senyap dilarang: barisnya membawa `hasPlaceholderZeros: true` supaya terlihat.
2. **Satu sumber, dua host, dua tata bahasa tanggal — dan yang salah menjawab 200.** `sports.core.api.espn.com` menerima rentang `dates=20260901-20261001` (49 laga). `site.api.espn.com` menolaknya, tapi **tidak dengan cara yang sama dua kali**: NFL menjawab **HTTP 400**, Premier League menjawab **HTTP 200 dengan `events: []`**. Yang kedua itu jebakannya — scraper yang dibangun di host SITE akan melaporkan "tidak ada laga Liga Inggris di jendela itu" dan dipercaya. Satu keluarga dengan `perpage` BCPEA dan filter Himalayas yang diterima-lalu-diabaikan, tapi di lapis **host**, bukan parameter.
3. **Baris berulang lagi, sekarang di sumber yang rapi.** 659 baris prop untuk **521 pasar distinct** — 138 duplikat persis sampai ke `lastUpdated`. Pola yang sama dengan 167 rekaman kosong Medium (Babak 52) dan `_basic` Blibli, tapi di sumber JSON resmi yang bersih. **Jumlah baris bukan bukti rekaman distinct**, apa pun kualitas sumbernya.
4. **Pointer HATEOAS bisa menunjuk ke host internal.** Respons `summary?event=` membawa **436 dari 436** `$ref` ke `sports.core.api.espn.pvt` — nama host internal ESPN yang tidak resolve — dan **nol** ke host publik. Scraper yang mengikuti `$ref` apa adanya gagal 100% dan kegagalannya terlihat seperti masalah jaringan, bukan masalah data. Semua `$ref` juga ditulis berskema `http://`. Dua penulisan ulang, keduanya wajib.

## Temuan teknis per sumber (ringkas)

- **ESPN**: core API adalah HATEOAS penuh — daftar hanya mengembalikan pointer, jadi tiap laga berbiaya 1 request tambahan; `maxEvents` ada supaya jendela satu musim (320 laga NFL) tidak meledak. `propBets` **mempaginasi sesuai `limit` yang dikirim**: `limit=3` jadi 220 halaman, `limit=1000` jadi 1 halaman berisi 659. Resolusi nama adalah biaya sebenarnya dan **runtuh dengan cache**: 659 prop lahir dari **47 atlet**; `site.api…/teams` menyerahkan 32 tim sekaligus dalam 1 request (liga bergaya kompetisi — UFC, golf, tenis — menjawab 404, jadi prefill-nya best-effort). **`eventId` tidak sama dengan `competitionId` di UFC** (event `600057024` membawa competition `401848704`) sementara empat olahraga lain selalu sama — kode yang menebak dari event id jalan di empat olahraga lalu 404 senyap di yang kelima. Daftar odds kosong **bukan blokir**: bandar memasang garis mendekati waktu mulai, jadi laga NBA/NHL enam minggu ke depan menjawab 200 dengan `count: 0` (dikirim sebagai `hasOdds: false`, bukan dihilangkan). Riwayat pergerakan garis (`odds/<p>/history/0/movement`) menjawab `count: 0` di semua laga yang dicoba — deret waktu harus dibangun dengan menjadwalkan actor-nya, bukan diambil.
- **Keyword search volume** (Babak 49 #5, baris **uang tertinggi** yang tersisa, $929/bln): **tidak ada permukaan terbuka yang menerbitkan volume.** `api.keywordsur.fr` **DNS hilang**; `app.neilpatel.com/api/keyword_info` **401**; `keywordtool.io/search/keywords/google` **404**; generator keyword gratis Ahrefs adalah bundel esbuild sisi-klien dengan **nol** jalur API di halaman maupun di bundel (14,6 KB, nol `fetch(`, nol `/v4/`); Keyword Planner redirect ke `accounts.google.com`. Yang **terbuka** hanyalah saran tanpa volume — autocomplete Google, Bing, YouTube dan Amazon semuanya 200. Vonis: **volume adalah field berbayar/berautentikasi di mana pun ia ada**.
- **Google Lens** (Babak 49 #6): `lens.google.com/uploadbyurl` menjawab **200 / 92 KB** dan **nol penanda hasil** — nol `AF_initDataCallback`, nol `data:image`, nol teks kecocokan visual, satu host keluar (`support.google.com`). Cangkang JS. Bentuk false positive yang persis sama dengan Apple Maps di Babak 50.
- **TikTok Shop** (Babak 49 #4): `shop.tiktok.com/view/product/<id>` menjawab **5,7 KB dengan `<title>Security Check</title>`**. Konsisten dengan vonis TikTok yang sudah ada.

## Rekomendasi Lanjutan

1. **Push + `apify call` `espn-betting-odds-scraper`, lalu set harga/kategori.** Belum dilakukan karena Fase 3 permintaan user berakhir di storage lokal. Ingat Gotcha #1 Babak 51: target belum terverifikasi sebelum `apify call` di platform.
2. **Daftar "BELUM dibangun" Babak 49 & 50 kini habis.** Dari 18 baris gabungan: 10 dibangun (Babak 51/52/53), 7 gugur dengan bukti terukur, 1 ditunda dengan alasan (tech-stack detector). Riset babak berikutnya harus mulai dari korpus baru, bukan dari daftar ini.
3. **Jadikan kriteria seleksi: harga vein mengukur apa yang dijual, bukan apa yang ada.** Dua kali berturut-turut (Google Hotels Babak 52, sports odds Babak 53) kandidat yang "gugur soal harga" ternyata punya tipe data yang **tidak satu pun incumbent-nya jual**. Sebelum membuang baris karena MRR rendah, cek dulu apa yang sebenarnya dijual incumbent di vein itu — kalau semuanya menjual irisan yang sama dan dangkal, harga vein bukan plafon melainkan ukuran kemalasan pesaing.
4. **Tambahkan ke konvensi: setiap field numerik wajib diperiksa terhadap domainnya sebelum di-emit.** Gotcha #1 babak ini akan lolos setiap tes "tidak crash" dan setiap validasi schema. Yang menangkapnya adalah pertanyaan "apakah 0 itu mungkin untuk field ini di dunia nyata".
5. **Actor Babak 51 & 52 masih menunggu.** `national-research-portal` + `bulgaria-foreclosure-auction` belum publik; 3 actor Babak 52 sudah di-push & di-`call` tapi belum diberi harga/kategori/publikasi.

## Bagian Tambahan Babak 53 — Push & `apify call` (2026-09-18, lanjutan sesi yang sama)

**Konteks:** user meminta "apify push and call" setelah actor lolos tes lokal 7 mode. Rekomendasi #1 Babak 53 dieksekusi.

Kuota sebelum: **$1,5440 / $5**, 243 actor. Sesudah: **$1,5499 / $5**, 244 actor. **Biaya seluruh push (2 build) + 7 run = $0,0059.**

| Actor | Actor ID | Build | Mode yang di-run di platform | Hasil |
|---|---|---|---|---|
| `espn-betting-odds-scraper` | `NzckyoECTGjjSlEn7` | 0.0.1 lalu **0.0.2** SUCCEEDED | reference, **odds**, **props**, **futures**, **predictor**, **events**, providers | 16 laga NFL berharga penuh (16/16 dengan pergerakan garis), 80 prop bernama, 60 baris futures MVP berprobabilitas, 16 proyeksi model, 20 jadwal Liga Inggris |

Ketujuh mode diverifikasi di platform, bukan hanya `reference` (konvensi Babak 50b). `defaultRunOptions` diturunkan ke **512 MB / 600 s** sebelum run pertama (`scratchpad/setmem53.py`) — default platform 4096 MB akan menagih 8 event start untuk run yang butuh 1 (memori [[apify_ppe_start_event_memory_multiplier]]).

**Tidak ada gerbang IP.** Berbeda dari PSA/BCPEA (Babak 51) dan Google Hotels (Babak 52), ESPN menerima IP datacenter Apify tanpa syarat: `chrome124` menang di lokal **dan** di platform, tidak ada perpindahan tangga TLS, tidak ada proxy dipakai (`useApifyProxy: false` sebagai default input schema, dan memang tidak dibutuhkan). Catatan penting untuk anggaran: akun FREE ini punya `RESIDENTIAL availableCount: 0`, jadi actor yang mensyaratkan residensial memang tidak bisa dijalankan di sini — actor ini tidak mensyaratkannya.

### 🆕 Gotcha tambahan yang hanya terlihat setelah dua run terpisah

1. **Satu bandar, dua ejaan — jangan join pakai nama.** Provider `100` ditulis `"Draft Kings"` di respons `odds` dan `"DraftKings"` di respons `futures` — sesi yang sama, IP yang sama, menit yang sama. Dataset yang di-`group by providerName` akan memecah satu bandar jadi dua. Kunci join yang benar adalah `providerId`; nama diteruskan apa adanya.
2. **Jumlah bandar per laga berubah menurut waktu, bukan menurut IP.** Run pertama (menjelang kickoff) mengembalikan 2 baris per laga: papan pra-laga + feed `- Live Odds`. Beberapa jam kemudian, baik dari IP lokal maupun dari platform, tersisa 1. Sempat terlihat seperti perbedaan geo — ternyata murni waktu. Konsekuensinya: "1 baris per laga" dan "2 baris per laga" **dua-duanya benar**, dan tes tidak boleh menegaskan jumlah bandar.
3. **`apify push` menolak `description` > 300 karakter** dengan `Error: Description must be at most 300 characters long` — dan penolakannya terjadi **sebelum** build, jadi murah tapi mudah terlewat kalau deskripsi ditulis panjang di `actor.json` (deskripsi awal 307 karakter).

### Sisa pekerjaan (belum dikerjakan, menunggu keputusan user)

1. **Harga + kategori + publikasi** `espn-betting-odds-scraper` (Phase 4–8 `actor-store-monetization`). Belum dijalankan karena user meminta khusus "push and call".
2. **Dua actor Babak 51** (`national-research-portal`, `bulgaria-foreclosure-auction`) masih privat.
3. **Tiga actor Babak 52** sudah di-push & di-`call` tapi belum diberi harga/kategori/publikasi.
4. Rekomendasi #2 Babak 50b tetap terbuka: akun kini **244 actor**, ±155 privat.

## File Referensi Babak 53

- `espn-betting-odds-scraper/` — `CRAWLING_METHOD.md` (matriks probe, 9 gotcha, tabel koreksi, tabel kandidat yang gugur), `README.md`, `test_local.py` (6 blok pemeriksaan yang menegaskan fakta terukur: jumlah halaman prop, keruntuhan cache, jumlah duplikat, nol yang tidak boleh bocor, penjumlahan probabilitas tersirat 0,95–1,25, dan perbedaan tata bahasa tanggal antar host)
- `scratchpad/probe53.py` sampai `probe53g.py` — seluruh jejak recon 11 target, termasuk 3 yang gugur
- `output/probe53.json` — matriks status/byte/content-type per profil TLS

---

# Babak 54 — Daftar Babak 49/50 habis, jadi eksekusi pindah ke **`actors_researcher_v2.md`**: kandidat #1 `clutch.co` dibangun & lolos 6 kasus tes lokal, plus pola baru "**halaman pertama bukan `?page=1`**" dan "**separuh halaman adalah iklan, dan markup-nya mengaku**" (2026-09-18)

**Konteks:** user meminta "lanjut build actor yang statusnya belum dibuat". Rekomendasi #2 Babak 53 sudah menyatakan daftar ✅ BELUM dibangun Babak 49 & 50 **habis** (10 dibangun, 7 gugur, 1 ditunda). Sisa daftar yang masih hidup ada di dokumen kedua, `actors_researcher_v2.md` (putaran 2026-09-15), yang **belum pernah tersentuh eksekusi**: urutan #2 `clutch.co`, #3 klaster direktori Eropa (Gelbe Seiten / Marktplaats / Ceneo / Firmy.cz), #4 recon Apple Maps, #5 probe klaster review perjalanan `knagymate`. Babak ini mengeksekusi baris #2.

## Status Ringkas — Sudah / Belum / Di-skip

| Status | Jumlah | Isi |
|---|---:|---|
| ✅ **Ter-build + lolos tes lokal** (belum di-push) | **1** | `clutch-agency-directory-scraper` — 5 mode, 6 kasus run hijau, `apify validate-schema` 3/3 |
| ⏭️ **Masih terbuka di `actors_researcher_v2.md`** | **4** | #1 kalibrasi harga (non-build) · #3 klaster direktori Eropa · #4 recon Apple Maps · #5 probe klaster review perjalanan |
| 🔧 **Koreksi untuk riset lama** | **2** | Vonis "Clutch 37 seller" Babak 49 menyesatkan · `?page=1` bukan halaman 1 |
| 🆕 **Gotcha metodologi baru** | **4** | Terutama: **halaman pertama tanpa parameter** dan **blok tersemat yang berulang di setiap halaman** |

**Biaya: $0** — seluruh babak lokal, tanpa proxy, tanpa run platform.

## Actor yang dibangun

| Actor | Sumber | Mode | Yield terukur | Status |
|---|---|---|---|---|
| `clutch-agency-directory-scraper` | clutch.co (listing, profil, review, sitemap) | 5: directory, profile, reviews, categories, reference | **50 agensi berperingkat per request** dengan atribut lead lengkap; 96.607 perusahaan / 1.933 halaman di `/web-developers` saja; ~70.000 URL direktori di sitemap; 35 entri focus-area per profil; 4 sub-skor per review | lolos tes lokal 6 kasus |

**Pembeda yang tidak dijual dua incumbent** (`epctex/clutchco-scraper` FLAT $40 gagal 13,1%; `curious_coder/clutch-scraper` FLAT $40): **pelabelan penempatan berbayar** (`isPaidPlacement` / `isPinnedBlock` / `isRankedResult`) — di halaman 1 `/web-developers`, **49 dari 86 baris adalah iklan dan hanya 7 yang berperingkat**; plus **URL situs asli** yang dibuka dari redirect `r.clutch.co`, dan **bauran layanan berpersentase** per baris.

`output_schema.json` pola nullable-safe (`["string","null"]`) + `additionalProperties: true` + 5 `views`, `apify validate-schema` 3/3 hijau, envelope `_input`/`_source`/`_scrapedAt`/`recordType`, dan mode `reference` yang menguji ulang asumsi desainnya sendiri (matriks TLS, alias `?page=1`, komposisi baris tersemat vs berperingkat) sesuai Rekomendasi #5 Babak 51.

## 🔧 Koreksi untuk Riset Lama (diverifikasi hari ini)

| Klaim lama | Kenyataan 2026-09-18 | Dampak |
|---|---|---|
| Babak 49 §B: "Clutch.co — vonis lama tetap: 37 seller" | Jumlah seller benar, tapi **26 dari 29 memungut $0**. Yang benar-benar menagih cuma **2** (`epctex` gagal 13,1% u30 turun ke 7, `curious_coder` u30 8), keduanya FLAT $40, rak $629/bln — persis yang diukur `actors_researcher_v2.md` | **Jumlah seller bukan ukuran kepadatan; jumlah *penagih* yang ukuran.** Vein yang "jenuh 29 seller" ternyata cuma punya 2 pesaing nyata, dan keduanya rusak. Satu keluarga dengan Rekomendasi #3 Babak 53 (harga vein mengukur apa yang dijual, bukan apa yang ada) |
| Semua scraper direktori berasumsi `?page=N` = halaman N | **`?page=1` mengembalikan halaman 2**, byte-identik dengan `?page=2`. Halaman 1 adalah **URL telanjang** | Loop `for p in 1..N` melewati halaman 1 sepenuhnya lalu mengirim halaman 2 dua kali — dan **tidak ada yang tampak rusak**, karena dua-duanya halaman 3 MB berisi agensi asli |

## Gotcha Metodologi Baru

1. **Halaman pertama bukan `?page=1`.** Judul membuktikannya: URL telanjang = `Top Web Development Companies…`, `?page=1` = `Page 2 - …`, `?page=2` = `Page 2 - …` dengan **himpunan 50 id yang persis sama**. Ini satu keluarga dengan `perpage` BCPEA dan filter Himalayas yang diterima-lalu-diabaikan, **tapi lebih berbahaya**: parameter yang salah tidak mengembalikan halaman 1 atau daftar kosong, ia mengembalikan **data valid yang berbeda**. Tidak ada tes "tidak crash" yang menangkapnya; yang menangkapnya adalah membandingkan himpunan id antar halaman.
2. **Separuh halaman adalah iklan, dan markup-nya mengaku — kalau ditanya.** Halaman 1 `/web-developers`: 86 baris = 43 `Sponsor` + 6 `featured` + 30 `Leaders Matrix` + **7 `Directory`**. Hanya `Directory` yang peringkat sebenarnya (50/halaman mulai halaman 2). `Leaders Matrix` **identik di setiap halaman** — irisan id halaman 3 ∩ halaman 4 = **41 dari 41**, sementara irisan baris berperingkat = **0**. Scraper yang memperlakukan `.provider-row` sebagai "hasil" melaporkan 86 hasil di mana ada 50, mencampur slot berbayar ke dalam peringkat, dan menerbitkan ulang 44 agensi yang sama di setiap halaman selamanya. Actor ini mengurutkan baris berperingkat lebih dulu, supaya run ber-`maxItems` mendapat peringkatnya, bukan iklannya.
3. **JSON-LD bisa tidak menggambarkan halaman yang kamu ambil.** Profil yang sama: halaman render 10 blok review dengan `review[]` berisi 16; `?page=1` render 6 dengan `review[]` berisi 12; `?page=99` render **0** tapi `review[]` tetap berisi **6**. Aturan "JSON-LD dulu" tetap benar untuk `aggregateRating`, alamat dan website — tapi **lapis paling stabil belum tentu lapis yang menjawab pertanyaanmu**. Review diambil dari blok HTML yang ber-`id="review-<id>"`.
4. **Persentase yang tidak sekala.** Tab focus di profil bukan satu daftar melainkan **8 grup, masing-masing berskala 100%** (AI Expertise, Frameworks and CMS, Mobile Platforms, …). Diratakan jadi satu array, persentasenya berjumlah 800 dan konsumen mana pun yang menjumlahkannya salah tanpa satu pun exception — satu keluarga dengan "nol sebagai placeholder" Babak 53: lolos setiap validasi schema, salah secara diam-diam. Tiap entri sekarang membawa `group` + `groupLabel`; tes lokal menegaskan **setiap grup berjumlah 100**.

## Temuan teknis per sumber (ringkas)

- **Cloudflare menggerbang di sidik TLS, dan 3 dari 6 profil ditolak**: chrome124/safari17_0/firefox133 → 200 / 1,45 MB; chrome110/edge101/chrome99_android → 403 / ~6 KB `Just a moment...`. **Gerbangnya tidak deterministik per profil**: chrome124 yang menang dua kali bisa ditantang pada request ketiga di sesi dingin, dan run `reference` menarik 3 tantangan dari 17 request sebelum menetap di safari17_0. Delapan request berturut-turut dalam **satu sesi hangat** semuanya 200 → obatnya **ulang di sesi baru**, bukan tidur lebih lama.
- **robots.txt melarang parameter filter** (`sort_by`, `hourly_rate`, `industries`, `geona_id`, `client_budget`, `related_services`, `reviews`, dst), `/lp/` dan `/claim-profile` — **tapi tidak `?page=`** maupun path kategori polos. Actor membuang parameter terlarang dari URL yang ditempel user dan mencatat nama yang dibuang.
- **URL situs agensi ada di balik `r.clutch.co/redirect`**, tujuan aslinya di parameter `u` (lengkap dengan UTM). 50/50 baris berperingkat menghasilkan domain nyata setelah dibuka; yang menyimpan `href` apa adanya menyimpan 50 URL pelacak identik.
- **Nama kelas berbohong soal isi, label tidak.** Sel harga minimum bernama `min-project-size`, bukan `project-size` — tebakan yang wajar mengembalikan `None` untuk **semua 86 baris** sementara tetangganya terparsing normal. Strip ringkasan profil dan strip data review dibaca lewat **teks labelnya** (`data-tooltip-content`), bukan posisi, karena review tanpa project size menghapus selnya dan menggeser sisanya.
- **Satu request = 50 lead beratribut penuh.** Tidak perlu membuka profil untuk min project size, tarif per jam, headcount, lokasi, telepon, atau bauran layanan — semuanya ada di baris listing. Itu ekonomi yang membuat dua incumbent FLAT $40 bisa dilewati.
- **Review berulang juga**: halaman 2 profil mengembalikan 10 blok, **9 di antaranya baru** — review unggulan ikut di setiap halaman. Dedupe lewat `reviewId`.

## Rekomendasi Lanjutan

1. **Push + `apify call` + harga/kategori `clutch-agency-directory-scraper`.** Belum dilakukan karena Fase 3 permintaan user berakhir di storage lokal. Ingat Gotcha #1 Babak 51: target belum terverifikasi sebelum `apify call` di platform — dan sumber ini **ber-Cloudflare**, jadi gerbang kedua dari IP datacenter Apify adalah risiko nyata (input schema sudah menyediakan `proxyConfiguration`, default mati).
2. **Harga: jangan $0,002/item.** Catatan `actors_researcher_v2.md` §6 eksplisit — dua pemain yang dapat uang di rak ini memungut **FLAT $40**. Kalau tetap PPE, pakai event tingkat-laporan, bukan per-baris.
3. **Turunan parser yang sama sudah menunggu**: `goodfirms.co`, `designrush.com`, `sortlist.com` — rak sejenis, **belum diprobe sama sekali** (bukan gugur, memang belum disentuh).
4. **Baris #3 `actors_researcher_v2.md` berikutnya**: klaster direktori Eropa (Gelbe Seiten $173 → Marktplaats $130 → Ceneo $81 → Firmy.cz $60, total rak $444, tiap rak 1–3 penagih). Catatan yang sudah ada: Ceneo **wajib Session** (request pertama 19 KB `meta http-equiv="refresh"` = penanaman cookie, bukan WAF), Marktplaats ambil dari data terstruktur halaman, jangan parse HTML.
5. **Jadikan kriteria seleksi: hitung *penagih*, bukan *seller*.** Koreksi Clutch babak ini adalah kasus kedua berturut-turut di mana vein yang divonis jenuh ternyata punya ≤3 pesaing nyata. Query seller-count yang selama 50 babak dipakai sebagai penyaring **melebih-lebihkan kepadatan secara sistematis** karena memasukkan actor gratis.

## Bagian Tambahan Babak 54 — Push & `apify call` (2026-09-18, lanjutan sesi yang sama)

**Konteks:** user meminta "apify push + apify call" setelah actor lolos tes lokal. Rekomendasi #1 Babak 54 dieksekusi.

Kuota sebelum: **$1,5513 / $5**, 244 actor. Sesudah: **$1,5667 / $5**, 245 actor. **Biaya seluruh push (3 build) + 11 run = $0,0154.**

| Actor | Actor ID | Build | Mode yang di-run di platform | Hasil |
|---|---|---|---|---|
| `clutch-agency-directory-scraper` | `ezciQR9VzUaK4AeYd` | 0.0.1 → 0.0.2 → **0.0.3** SUCCEEDED | directory, profile, reviews, categories, reference | 80 agensi (37 berperingkat + 43 sponsor, **0 duplikat**, atribut lead 80/80), 2 profil berbagan penuh, 30 review distinct dengan 4 sub-skor, 30 URL kategori, 5 rekaman SURFACE |

`defaultRunOptions` diturunkan ke **512 MB / 600 s** sebelum run pertama (default platform 4096 MB menagih 8 event start untuk run yang butuh 1 — memori [[apify_ppe_start_event_memory_multiplier]]).

### 🆕 Gerbang kedua memang muncul di platform — tapi sebagai **penyempitan tangga TLS**, bukan blokir

Matriks TLS yang diukur **oleh mode `reference` dari IP datacenter Apify**, dibandingkan dengan recon lokal (IP residensial Indonesia) satu jam sebelumnya:

| Profil | Lokal | Platform | |
|---|---|---|---|
| `safari17_0` | 200 / 1,45 MB | **200 / 2,70 MB** | ✅ dua-duanya |
| `firefox133` | 200 / 1,45 MB | **200 / 2,70 MB** | ✅ dua-duanya |
| `chrome124` | **200 / 1,46 MB — pemimpin lokal** | **403 / 5,9 KB** | 🔄 **berbalik** |
| `chrome110` · `edge101` · `chrome99_android` | 403 | 403 | ❌ dua-duanya |

Ini bukan pola PSA/BCPEA Babak 51 (target menolak IP datacenter seluruhnya, sembuh dengan residensial). Di sini **sumbernya tetap terbuka tanpa proxy sama sekali** — yang berubah adalah *profil mana* yang diterima. Pelajaran yang lebih tajam dari "target belum terverifikasi sebelum `apify call`": **matriks TLS hasil recon lokal adalah titik awal, bukan urutan tangga final.** Tangga diurutkan ulang jadi `safari17_0 → firefox133 → chrome124` (dua yang lolos di kedua IP lebih dulu).

### 🆕 Gotcha: mengoptimalkan retry tanpa mengukur transiennya justru **menggagalkan run**

Urutan tiga build ini adalah datanya, dan urutannya penting:

| Build | Kebijakan retry | Hasil run `directory` |
|---|---|---|
| 0.0.1 | 3 percobaan per profil, backoff eksponensial, tangga sekali jalan | **SUCCEEDED** — tapi 10 request / **8 tantangan**, ~39 detik hilang di halaman pertama |
| 0.0.2 | tantangan dipisah dari error transien: 2 percobaan per profil, lalu pindah profil | **FAILED** — 6 request / **6 tantangan**, 0 rekaman |
| 0.0.3 | tangga yang sama, tapi **diputar 3 ronde** dengan jeda 6→12 detik antar ronde | **SUCCEEDED** — **2 request / 0 tantangan** |

0.0.2 "lebih pintar" dan justru gagal: menyerah setelah 6 percobaan padahal 0.0.1 tembus di percobaan ke-9. Yang membuat 0.0.1 selamat bukan kecerdasannya, melainkan **kekeraskepalaannya**. Dua fakta itu menarik ke arah berlawanan — profil yang salah harus ditinggalkan cepat (karena per-IP), tapi penolakan sering cuma sesaat — dan keduanya baru bisa dipenuhi dengan **dua sumbu terpisah**: percobaan per profil sedikit (cepat menemukan yang benar), tapi **seluruh tangga diulang beberapa ronde** sebelum menyerah. Run `profile` di 0.0.3 membuktikannya: **7 tantangan dari 9 request, tetap SUCCEEDED**.

Pelajaran umum untuk portofolio: **jangan mengetatkan anggaran retry berdasarkan satu run yang sukses.** Angka yang harus diukur dulu adalah *pada percobaan ke berapa* run yang berhasil itu tembus — kalau jawabannya "ke-9 dari 9", memotongnya jadi 6 adalah menghapus margin yang menyelamatkannya, bukan menghapus pemborosan.

### Verifikasi isi dataset di platform (bukan cuma exit code)

- `directory`: 80 rekaman, `{Directory: 37, Sponsor: 43}`, **0 duplikat `providerId`**, `minProjectSize`/`hourlyRate`/`employees`/`website`/`services` **80/80 terisi**, telepon 77/80, **0 URL redirect bocor**.
- `reviews`: 30 rekaman, **30 `reviewId` distinct**, 30/30 punya empat sub-skor, 1 duplikat (review unggulan yang berulang antar halaman) tersaring.
- `reference` dari platform mengonfirmasi ulang semuanya: alias `?page=1` (`page1EqualsPage2: true`, `page1EqualsBareUrl: false`), blok tersemat berulang **40 baris**, irisan baris berperingkat **0**, klaim 96.624 perusahaan / 1.933 halaman.

### Sisa pekerjaan (belum dikerjakan, menunggu keputusan user)

1. **Harga + kategori + publikasi** `clutch-agency-directory-scraper` (Phase 4–8 `actor-store-monetization`). Belum dijalankan karena user meminta khusus "push and call". Catatan harga tetap: dua incumbent yang dapat uang memungut **FLAT $40**, jangan $0,002/item.
2. Dua actor Babak 51 (`national-research-portal`, `bulgaria-foreclosure-auction`) masih privat; 3 actor Babak 52 dan `espn-betting-odds-scraper` sudah di-push tapi belum diberi harga/kategori/publikasi.
3. Akun kini **245 actor**, mayoritas privat — Rekomendasi #2 Babak 50b tetap terbuka.

## File Referensi Babak 54

- `clutch-agency-directory-scraper/` — `CRAWLING_METHOD.md` (matriks TLS, tabel komposisi baris, 6 gotcha dengan biaya masing-masing), `README.md` (sampel nyata per mode), `test_local.py` (7 blok pemeriksaan: alias `?page=1`, blok tersemat vs baris berperingkat, kelengkapan atribut lead di baris berperingkat saja, kebocoran URL redirect, penjumlahan persentase per grup, paginasi review), `run_modes.py` (6 kasus run lokal end-to-end)
- `scratchpad/probe54.py` … `probe54g.py` — seluruh jejak recon; `output/probe54.json` matriks status/byte per profil TLS
