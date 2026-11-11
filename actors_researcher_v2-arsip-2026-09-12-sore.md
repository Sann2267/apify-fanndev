# Riset Pasar Apify Store — v2 (putaran 2026-09-12 sore)

**Tanggal riset:** 2026-09-12
**Akun pembanding (dedupe wajib):**
- [`xtracto`](https://api.apify.com/v2/store?username=xtracto) — **218 actor published** (tidak berubah sejak Babak 47/49/50), snapshot `output/xtracto-full.json`
- [`fanndev`](https://api.apify.com/v2/store?username=fanndev) — **75 actor published** dari 229 folder di repo ini, snapshot `output/fanndev-full.json`

**Dokumen sebelumnya:**
- [`ACTOR_MARKET_RESEARCHER_NEW.md`](ACTOR_MARKET_RESEARCHER_NEW.md) — 50 babak, 608 KB. Babak 50 = sumbu uang.
- [`actors_researcher_v2-arsip-2026-09-12-pagi.md`](actors_researcher_v2-arsip-2026-09-12-pagi.md) — putaran pagi hari ini (arsip). Status carry-over-nya di [§9](#9-status-carry-over-dari-putaran-pagi).
- [`actors_researcher_v2-arsip-2026-09-07.md`](actors_researcher_v2-arsip-2026-09-07.md) — v2 lama.

**Data mentah putaran ini:**

| File | Isi |
|---|---|
| `output/scan-v4-corpus.json` | **23.779 actor unik** — 21 kategori × **7 band user** × offset 0–900. Korpus terbesar dalam seluruh riset ini (4× korpus pagi yang 5.773). |
| `output/scan-v4-veins.json` | **384 vein** lolos filter uang (MRR ≥ $60 **dan** ≤3 seller yang benar-benar memungut) |
| `output/scan-v4-verify-employer.json` | 20 brand review/direktori, query single-token |
| `output/scan-v4-verify-batch2.json` | 20 brand properti/e-commerce/komunitas |
| `output/scan-v4-verify-events.json` | 20 brand event & musik — ini yang melahirkan rekomendasi #1 |
| `output/scan-v4-veins-OLDCORPUS.json` | lensa yang sama di korpus pagi, sebagai kontrol |

Skrip: `scratchpad/scan_v4.py`, `money_v4.py`, `verify_v4.py`, `probe_v4*.py`.

---

## 1. Ringkasan eksekutif

Putaran ini **membalik urutan kerja**: bukan "cari pola rpu/seller dulu lalu ukur uang" (cara pagi tadi dan Babak 50), tapi **hitung uang untuk seluruh 23.779 actor sekaligus, lalu baca polanya**. Tiga hal keluar dari situ, dan dua di antaranya tidak pernah muncul di 50 babak sebelumnya.

**A. Koreksi metodologi yang membatalkan sebagian kesimpulan harga sebelumnya.** Event PPE primer di Apify adalah **`apify-default-dataset-item` — per ITEM, bukan per run**. Model uang yang dipakai Babak 50 dan putaran pagi menghitung `run_sukses × harga_event`, jadi actor PPE diremehkan sebesar rata-rata item/run (bisa 10–1.000×), sementara actor FLAT dihitung tepat. Kesimpulan "FLAT menang 10–100× dari PPE" **sebagian adalah artefak model**, bukan temuan pasar. Detail + cara kalibrasinya di [§2](#2-koreksi-metodologi-model-uang-ppe-salah-satuan).

**B. Ekonomi `xtracto` akhirnya terukur, dan angkanya jauh lebih buruk dari perkiraan.** 218 actor, **218/218 PAY_PER_EVENT, nol flat**, harga event median **$0,002/item**. Lantai pungutan **$131,89/bulan dari 958 pembeli aktif = $0,138 per pembeli.** Store rata-rata $0,35 (PPE) / $24,17 (FLAT). Perkiraan lama $687/bln terlalu tinggi. [§3](#3-ekonomi-xtracto-terukur)

**C. Kandidat build baru: klaster EVENT LANGSUNG (live music).** Bandsintown + Songkick + Dice.fm + Resident Advisor + Shotgun = **$674/bln**, **$4,88 per pembeli**, dan **tiap brand hanya punya 1–2 seller yang memungut** sementara 5–14 seller lain di rak yang sama memungut $0. **Tiga dari lima permukaannya sudah saya probe hari ini dan terbukti terbuka dengan data asli** (Pass 5 + 5b lolos). Nol di `xtracto`, nol di `fanndev`. [§4](#4-rekomendasi-1--klaster-event-langsung-live-music)

> **Pembeda penting dari putaran pagi:** rekomendasi #1 pagi (cluster review hotel `knagymate`, $943/bln) **belum diprobe** dan uangnya bertumpu pada ≈7 pembeli. Klaster event ini lebih kecil ($674) tapi **permukaannya sudah terverifikasi terbuka** dan pembelinya tersebar di 5 brand × 2 seller. Keduanya tidak saling menggugurkan — lihat urutan eksekusi di [§10](#10-status--note-untuk-build-ke-depan).

---

## 2. Koreksi metodologi: model uang PPE salah satuan

Diperiksa langsung dari `currentPricingInfo` milik `xtracto/shopee-search` dan `xtracto/glassdoor-reviews`:

```
"apify-default-dataset-item": { "eventTitle": "result",
   "eventDescription": "Single result in the default dataset.",
   "isOneTimeEvent": false,            <-- ditagih SETIAP item
   "eventTieredPricingUsd": { "GOLD": { "tieredEventPriceUsd": 0.002 } },
   "isPrimaryEvent": true }
"apify-actor-start": { "isOneTimeEvent": true, "eventPriceUsd": 0.005 }
```

`isOneTimeEvent: false` pada event primer = **ditagih per item dataset**. Rumus `MRR = run_sukses × harga_event` karena itu **melantai di 1 item per run**.

| Akibatnya | Penjelasan |
|---|---|
| Actor **FLAT** dihitung **tepat** | `u30 × harga_bulanan` — tidak ada variabel tersembunyi |
| Actor **PPE** dihitung **terlalu rendah** | faktor kesalahan = rata-rata item per run, tidak ada di indeks Algolia |
| Perbandingan FLAT vs PPE | **tidak valid** dalam satuan sekarang |

Yang **tetap valid**: peringkat *sesama* FLAT, peringkat *sesama* PPE (kalau item/run sebanding), dan seluruh sinyal non-uang (seller, rpu, fail-rate). Yang **harus dicabut**: klaim "5 dari 6 pemenang uang pakai FLAT karena FLAT lebih unggul" — actor FLAT naik ke puncak sebagian karena merekalah satu-satunya yang diukur penuh.

**Kalibrasi yang bisa dikerjakan tanpa riset tambahan:** buka Apify Console akun `xtracto`, ambil pendapatan riil 30 hari terakhir, bagi dengan **$131,89**. Hasilnya = faktor item/run portofolio sendiri. Kalikan ke seluruh kolom MRR PPE di dokumen ini dan di Babak 50, lalu ranking-nya bisa dibaca ulang dengan benar. **Ini satu-satunya angka yang hilang dari seluruh model, dan hanya pemilik akun yang bisa mengambilnya.**

### Struktur harga Store (korpus 23.779, satuan seperti apa adanya — baca dengan peringatan di atas)

| Model | Jumlah actor | % actor | MRR terukur | % uang | u30 | $/pembeli |
|---|---:|---:|---:|---:|---:|---:|
| PAY_PER_EVENT | 19.148 | 80,5% | $258.514 | 64,8% | 740.915 | $0,349 |
| FLAT_PRICE_PER_MONTH | 2.749 | 11,6% | $140.156 | 35,2% | 5.799 | $24,169 |
| FREE | 1.882 | 7,9% | $0 | 0% | 58.554 | — |

**Total terukur: $398.670/bln** (Babak 50 memperkirakan $439.454 dengan model yang sama di korpus lebih kecil — konsisten). Hanya **405 actor tembus $100/bln**, **54 tembus $1.000**, dan **top-10 memegang 37,4%** seluruh uang. Harga FLAT median **$19**; harga event PPE median **$0,002**, persentil-90 **$0,012**.

---

## 3. Ekonomi `xtracto` terukur

| Metrik | Nilai |
|---|---|
| Actor published | **218** |
| Model harga | **218 PAY_PER_EVENT / 0 FLAT** (pagi tadi tercatat 215/218 — sekarang 218/218) |
| Harga event | median **$0,002/item** = persis median Store |
| Pembeli aktif 30 hari | **958** |
| Lantai pungutan | **$131,89/bln** |
| **$ per pembeli** | **$0,138** — di bawah rata-rata PPE Store ($0,349), 175× di bawah rata-rata FLAT ($24,17) |

Enam actor teratas (lantai): `shopee-search` $47,27 · `shopee-scraper` $13,68 · `shopee-product-detail` $7,56 · `facebook-post-detail` $4,76 · `forbes-scraper` $4,73 · `reuters-scraper` $3,86. **Sisa 212 actor bersama-sama di bawah $55.**

**Yang paling mahal dari angka ini bukan totalnya, tapi contoh-contoh berikut** — produk sudah ada, rak sudah dimasuki, yang hilang cuma harga:

| Vein | Actor `xtracto` | Pungutan `xtracto` | Pesaing di rak yang sama | Pungutan pesaing |
|---|---|---:|---|---:|
| Glassdoor reviews | `glassdoor-reviews` (3u) | **$0,06** | `memo23/apify-glassdoor-reviews-scraper` FLAT **$32/bln** | **$1.120** |
| Trustpilot | `trustpilot-reviews` (2u) | **$0,01** | `casper11515/trustpilot-reviews-scraper` FLAT $20 | **$1.100** |
| Northdata | `northdata-companies-scraper` (13u) | **$0,14** | `silentflow/northdata-scraper` PPE | **$354** |
| Amazon reviews | `amazon-reviews-scraper` (2u) | **$0,12** | `delicious_zebu/…advanced-filters` FLAT $35 | **$1.050** |
| Skool (akun `fanndev`) | `skool-whop-community-analyzer` (2u) | **$0,10** | `louisdeconinck/skool-scraper` FLAT $19 | **$171** |

Sebagian selisih ini adalah artefak satuan (§2) dan sebagian lagi memang selisih traffic — tapi **selisih 10.000×–100.000× tidak bisa dijelaskan oleh item/run saja**. Perbedaan nyatanya: pesaing punya pembeli berbayar; actor `xtracto` di vein yang sama punya 2–3 user.

---

## 4. Rekomendasi #1 — klaster EVENT LANGSUNG (live music)

Uang di dunia event **tidak ada di resale tiket** — ada di **penemuan/listing event**. Ini terbaca tajam sekali dari data:

| Slice | Brand | MRR gabungan |
|---|---|---:|
| Resale tiket | Ticketmaster + StubHub + SeatGeek + Viagogo + Vivid Seats | **$19** total |
| **Penemuan event** | Bandsintown + Songkick + Dice.fm + Resident Advisor + Shotgun | **$674** |

### Rincian vein

| Brand | MRR | Seller memungut | Seller total | u30 | $/pembeli | Incumbent teratas | Model |
|---|---:|---:|---:|---:|---:|---|---|
| **Dice.fm** | **$234** | 2 | 7 | 23 | **$10,16** | `lexis-solutions/dice-fm` | FLAT **$29** |
| **Resident Advisor** | **$214** | 2 | 12 | 56 | $3,81 | `chalkandcheese/ra-events-scraper` ($195) | FLAT **$15** |
| **Bandsintown** | **$176** | 1 | 8 | 33 | $5,34 | `lexis-solutions/bandsintown-scraper` | FLAT **$29** |
| **Songkick** | **$31** | 1 | 14 | 20 | $1,54 | `chalkandcheese/songkick-events-scraper` | FLAT **$15** |
| **Shotgun** | **$19** | 1 | 1 | 6 | $3,10 | `hypebridge/shotgun-live` | PPE |
| **Total** | **$674** | — | 42 nominal | 138 | **$4,88** | — | — |

42 seller nominal di rak, **7 di antaranya memungut ≥$5**, sisanya $0,00–$1,60. Pola persis Gotcha #3 mode (a) — tapi kali ini **uangnya ada**, tidak seperti Waze ($3) atau AllTrails ($4) yang dibatalkan putaran pagi.

### Probe permukaan — Pass 5 + Pass 5b, dijalankan hari ini

| Target | Status HTTP | Isi (Pass 5b) | Vonis |
|---|---|---|---|
| **Bandsintown** `rest.bandsintown.com/artists/<a>/events?app_id=web` | **200** chrome & safari | JSON asli: metallica **26 event**, tiap event ada `datetime`, `venue.name`, `street_address`, lat/lon. Endpoint kota `bandsintown.com/api/event/dates?city=london` juga **200, 468 KB** | ✅ **TERBUKA — API publik, tanpa WAF** |
| **Songkick** `songkick.com/artists/<id>`, `/metro-areas/<id>` | **200** | **51 blok `ld+json` MusicEvent per halaman**, nama artis + venue + tanggal. Paginasi diuji sampai `?page=6` — tetap 200, tetap 51 blok | ✅ **TERBUKA — data di ld+json** |
| **Dice.fm** `dice.fm/browse` | **200, 542 KB** | `__NEXT_DATA__` → `pageProps.events` (**348 KB**), plus `city{lat,lng,country}` dan **`nextCursor`** untuk paginasi | ✅ **TERBUKA — `__NEXT_DATA__` + cursor** |
| **Resident Advisor** `ra.co/events/uk/london` | **403** | — tapi **`POST ra.co/graphql` → 200** (`{"data":{"__typename":"Query"}}`), dan `chalkandcheese/ra-events-scraper` memungut $195/bln, jadi jalur itu **jelas bisa ditembus** | 🟠 **HTML tertutup, GraphQL hidup** — perlu satu sesi menyusun query |
| **Shotgun** `shotgun.live/en/cities/paris` | **200, 370 KB** | 5 blok `ld+json` | 🟡 Terbuka, tapi vein-nya cuma $19 |

**Dedupe:** `bandsintown`, `songkick`, `dice`, `resident`, `ra.co`, `shotgun`, `ticketmaster`, `meetup` — **nol** di `xtracto` (218), **nol** di `fanndev` (75), **nol** di 229 folder lokal. Yang ada cuma `xtracto/eventbrite-events`.

**Kenapa ini cocok dengan portofolio yang sudah ada:** akun utama sudah punya `luma-scraper` dan `partiful-scraper` — dua actor event. Bandsintown/Songkick/Dice/RA adalah **sisi lain dari domain yang sama** (event publik berskala kota, bukan undangan pribadi), dan parser-nya satu keluarga: tiga dari empat mengeluarkan JSON terstruktur, jadi **3–4 actor bisa lahir dari satu basis kode** dengan biaya per-actor sangat rendah.

**Risiko yang harus disadari:** vein-nya kecil dalam angka absolut ($674/bln adalah **seluruh** uang di rak, bukan bagian yang akan didapat). Yang membuatnya layak bukan besarnya, tapi **$/pembeli 9× rata-rata PPE Store** + permukaan sudah terbukti terbuka + biaya build terbagi 4 actor.

---

## 5. Kandidat lain yang lolos saringan uang

| # | Ide | MRR vein | $/pembeli | Seller memungut / total | Permukaan | Status |
|---|---|---:|---:|---|---|---|
| 2 | **Indeed Reviews** (review perusahaan, bukan lowongan) | **$396** | **$33,00** | 1 / 7 | belum diprobe | 🔴 **Menjawab pertanyaan terbuka putaran pagi** ("belum diukur uangnya"). `memo23/apify-indeed-reviews` FLAT **$33**, 12 pembeli, 319.293 run, fail 0%. `xtracto` punya `indeed-jobs-scraper` — **beda data-type, gap nyata.** |
| 3 | **kununu** (review employer Jerman) | **$251** | $2,62 | 1 / 20 | ❌ **202 challenge** | 🟠 `radeance/kununu-reviews-scraper` FLAT $24,99 sendirian memungut $250; 19 seller lain $0,00–$0,50. Tapi `kununu.com` balas **202 + 2 KB, tanpa `__NEXT_DATA__`** di chrome & safari = anti-bot. **Butuh riset bypass dulu, jangan commit.** |
| 4 | **StoreLeads** | **$466** | **$23,31** | 2 / **2** | 🟠 landing 200, data butuh login | 🟠 Rak paling kosong di seluruh scan (**2 seller total**) dan $/pembeli 43× rata-rata Store. Incumbent `saswave/storeleads-scraper` **fail 75,8%** — rusak. Tapi storeleads.app itu SaaS berbayar; datanya di balik login. **RECON, bukan BUILD.** |
| 5 | **Trip.com / Ctrip reviews** | **$311** | $2,38 | 3 / 29 | ⚠️ **cangkang** | 🟡 `knagymate/trip-com-reviews-scraper` $270 — **anggota kelima cluster review perjalanan `knagymate`** yang jadi rekomendasi #1 putaran pagi (HRS/Zoover/Despegar/Kurzurlaub). Halaman hotel 200 tapi **`reviewList` & `commentScore` tidak ada, kata "review" cuma 5×** → review dimuat lewat XHR. Perlu temukan endpoint-nya dulu. |
| 6 | **Mindbody / lead vertikal studio fitness** | **$400** | **$66,67** | 1 / 2 | belum diprobe | 🟡 `lead.gen.labs/whatsapp-fitness-studio-leads---powered-by-mindbody-scraper` FLAT **$100/bln × 4 pembeli**. Seller kedua $0. **Pola produknya yang menarik: bukan "scraper Mindbody", tapi "daftar lead studio fitness dari Mindbody".** |
| 7 | **Magento store finder** | **$150** | **$25,01** | 1 / **3** | belum diprobe | 🟡 `jupri/magento-scraper` FLAT $30, fail 13,5%. Rak nyaris kosong. Tapi ini kategori tech-stack detector yang riset lama tandai di luar fokus. |

### Vein besar yang diukur tapi TIDAK direkomendasikan

| Vein | MRR | Kenapa tidak |
|---|---:|---|
| **Dubai unit-number / property owner** | **$12.166** ($67,59/pembeli) | Vein terkaya di Store, **tetap ditolak**: data pemilik properti = PII massal. Kebijakan portofolio menolaknya di Babak 40/41/45/46/49/50. Konsisten. |
| **TecDoc + katalog suku cadang** | **$2.346** ($69/pembeli, rpu **14.954**) | `making-data-meaningful/tecdoc` FLAT sendirian. TecDoc adalah **database berlisensi B2B berbayar** — menjualnya ulang berisiko hukum, bukan sekadar ToS. Klaster `toyota/yamaha/vauxhall-parts-catalog` @$38 dari seller yang sama. RECON legal dulu, jangan build. |
| **skip-trace / mobile-phone-enrichment / Truecaller / TruePeopleSearch** | $1.675 / $2.630 / $391 | PII orang per orang. Tolak. |
| **Tinder / Hinge profile & email scraper** | $721 / $110 ($14,13/pembeli) | Profil kencan + email. PII + ToS. Tolak, walaupun rak-nya cuma 2 seller. |
| **YouTube view generator / traffic generator** (`forward_dinosaur` $1.920, `epctex` $700, `bebity` $225) | $2.845 gabungan | Manipulasi metrik. Di luar bisnis. Catat saja bahwa ini **kategori PPE/FLAT paling menguntungkan ketiga di Store** — dan seluruhnya fail-rate 14–53%. |
| **Sales Navigator / Apollo-ZoomInfo-Lusha clone** (`pipelinelabs` $3.538, `muhammad_usama` $1.650) | $5.188 | LinkedIn — jenuh permanen + ToS keras. Riset lama sudah menutup. |
| **Laporan terpaket `nexgenwatch`** (ASO audit $502, app-review competitive $502, tender pipeline $292, grant funding $292) | $1.588 | **Bukan kandidat, tapi pelajaran harga** — lihat §6. |

---

## 6. Temuan harga: "laporan" vs "scraper"

`nexgenwatch` memakai PAY_PER_EVENT seperti `xtracto`, tapi **satu event-nya berharga $16,75**, bukan $0,002:

```
nexgenwatch/aso-audit-report      event "aso-audit-report"  = $16,75  (primary)
nexgenwatch/app-review-competitive-report  event "competitive_report" = $16,75
nexgenwatch/tender-pipeline-report         event "tender-pipeline-report" = $10,05
```

30 run sukses × $16,75 = **$502/bln dari 1–2 pembeli**. Bandingkan `xtracto/glassdoor-reviews`: 30 run sukses × $0,002 = **$0,06**.

**Selisihnya 8.375× dan sama sekali bukan soal traffic — run-nya sama-sama 30.** Yang berbeda: satu menjual **satu laporan jadi per run**, satu lagi menjual **baris dataset mentah per item**. Ini bukti keempat berturut-turut bahwa hambatan portofolio `xtracto` ada di **bentuk produk & harga, bukan di traffic atau di jumlah actor**.

⚠️ Kehati-hatian: `nexgenwatch` cuma punya 1–2 pembeli per actor, jadi ini **bukti konsep harga, bukan bukti permintaan pasar**. Yang boleh disimpulkan: Apify **mengizinkan** event bernilai $10–17 dan ada yang membayarnya. Yang belum terbukti: apakah bisa diskalakan ke puluhan pembeli.

---

## 7. Pola A — "runs banyak, user sedikit" (yang kamu minta)

Filter: user ≥20 **dan** total runs ≥100.000, diurutkan runs-per-user, dari korpus 23.779.

| Actor | Users | Runs | runs/user | MRR | $/pembeli | Baca |
|---|---:|---:|---:|---:|---:|---|
| `alien_force/facebook-scraper-pro-rental` | 211 | 23.491.294 | **111.333** | $100 | $25,00 | "rental" = model sewa, bukan niche |
| `canadesk/apple-app-store-plus` | 32 | 2.511.094 | 78.472 | $36 | $12,00 | App Store — 100+ seller |
| `apify/monitoring-checker-*`, `s3-uploader`, `mongodb-import`, `legacy-phantomjs-crawler` | 36–142 | 0,6–5,1 jt | 15.440–74.737 | **$0** | — | **Infrastruktur Apify sendiri, gratis.** Pengotor terbesar pola ini. |
| `thescrappa/google-maps-advanced-search-scraper` | 61 | 2.494.679 | 40.896 | **$0** | — | Google Maps, jenuh |
| `devisty/google-search` | 333 | 13.037.304 | 39.151 | $28 | $7,00 | Google SERP, jenuh total |
| `build_matrix/company-employees-scraper` | 872 | 25.551.483 | 29.302 | **$0** | — | rpu raksasa, pungutan nol |
| `knagymate/hrs-reviews-scraper` | 20 | 464.457 | 23.223 | **$499** | **$499** | ✅ Rekomendasi #1 putaran pagi — tetap berdiri |
| `muhammad_usama/Github-Apify-Linkedin-data-scraper` | 1.078 | 22.963.507 | 21.302 | $50 | $50,00 | LinkedIn, tutup |
| `macrocosmos/reddit-scraper` | 1.031 | 20.553.649 | 19.936 | **$0** | — | 20 juta run, nol pungutan |
| `making-data-meaningful/tecdoc` | 2.096 | 31.344.259 | 14.954 | **$2.346** | **$69,00** | ⚠️ Data berlisensi (§5) |
| `scraped/tcgplayer-sales-history` | 61 | 924.819 | 15.161 | **$0** | — | Sudah dibatalkan putaran pagi |
| `saswave/noon-seller-monitoring` | 62 | 903.140 | 14.567 | $12 | $1,48 | rpu spektakuler, uang biasa |

**Vonis pola A: dari 22 teratas, hanya 2 yang punya uang nyata** — `knagymate/hrs-reviews-scraper` (sudah jadi rekomendasi) dan `tecdoc` (terganjal lisensi). Sisanya infrastruktur gratis, vein jenuh, atau nol pungutan. **Runs-per-user tinggi adalah alat penemuan yang bagus untuk menemukan "actor dipakai terus-menerus", tapi 9 dari 10 kalinya menunjuk actor yang tidak memungut apa pun.** Ini konsisten dengan Babak 50 dan putaran pagi — sekarang di korpus 4× lebih besar.

---

## 8. Pola B — "user banyak, saingan sedikit" (yang kamu minta)

Filter: token dengan sum users ≥1.500 **dan** ≤8 seller, dari korpus 23.779.

| Token | Seller | Users | Runs | MRR | $/pembeli | Dedupe | Baca |
|---|---:|---:|---:|---:|---:|---|---|
| `unit` | 8 | 12.882 | 558.289 | **$11.689** | **$89,23** | XTRACTO | Dubai PII — ditolak (§5) |
| `upto` | 2 | 10.659 | 353.124 | **$4.277** | $26,40 | BARU | Token sampah (`…upto-300k-leads…`), bukan niche |
| `many`, `sherlock`, `manager`, `fail`, `base`, `example`, `merge`, `transform`, `dedup`, `send` | 1–8 | 4.500–43.847 | — | $0–$700 | ≤$10 | — | **Kata generik**, bukan brand: `actor-fail-manager`, `dataset-join-merge`, `example-mcp-server` |
| `enterprise` / `grade` | 7–8 | 29.131 | 858.571 | $104 | **$0,06** | BARU | Keduanya cuma menangkap `fatihtahta/reddit-scraper-search-fast` |
| `puppeteer` | 6 | 16.793 | 8.522.086 | **$0** | — | OLD | 8,5 juta run, nol pungutan |
| `webrocket` / `animation` / `pageview` / `wscrp` | 1 | 5.100–15.182 | — | $0–$225 | — | BARU | Traffic generator & gif tool |
| `ninja`, `openrouter`, `adder`, `stress`, `scroll` | 1–5 | 5.400–8.144 | — | $0–$220 | ≤$12 | OLD | Sudah tertutup di riset lama |

**Vonis pola B: nol kandidat baru.** Di korpus 23.779, "users banyak + seller sedikit" **tidak menghasilkan satu pun vein bersih**. Penyebabnya dua, dan keduanya struktural:

1. **Token generik mendominasi.** Kata dengan sedikit seller dan banyak user hampir selalu kata bahasa Inggris umum yang kebetulan ada di judul (`many`, `base`, `send`, `example`), bukan nama brand. Brand nyata selalu punya banyak seller.
2. **Rak yang benar-benar kosong biasanya kosong karena alasan.** Kalau 15.000 user memakai sesuatu dan cuma 1 seller menyediakannya, penyebab paling umum adalah actor itu **gratis atau infrastruktur** — bukan celah pasar.

> **Konsekuensi untuk riset berikutnya:** pola B (user banyak / seller sedikit) sudah diuji di dua ukuran korpus (5.773 dan 23.779) dan **tidak pernah menghasilkan kandidat**. Pola A menghasilkan 2 dari 22. **Pola yang benar-benar produktif di putaran ini adalah pola baru: "MRR vein ≥$60 DAN ≤3 seller yang memungut ≥$5"** — itu yang melahirkan klaster event, Indeed Reviews, kununu, StoreLeads, dan Mindbody. Filter itu sudah tertanam di `scratchpad/money_v4.py`.

---

## 9. Status carry-over dari putaran pagi

| Kandidat pagi | Prioritas pagi | Angka/probe hari ini | Status baru |
|---|---|---|---|
| **Cluster review hotel `knagymate`** (HRS/Zoover/Despegar/Kurzurlaub) | 🔴 #1, $943 | HRS terkonfirmasi di korpus baru ($499, rpu 23.223). **Anggota kelima ditemukan: Trip.com/Ctrip $270.** Halaman Trip.com = cangkang, review lewat XHR. Keempat domain asli masih belum diprobe. | ✅ **Dipertahankan sebagai #2**, sekarang 5 brand. Tetap belum diprobe — itu yang menurunkannya di bawah klaster event. |
| **Uji harga FLAT $25–$30 di actor `xtracto`** | 🔴 #2 | Dasar buktinya **berubah**: klaim "FLAT 10–100× PPE" sebagian artefak satuan (§2). Tapi bukti penggantinya lebih kuat — `xtracto` memungut **$0,138/pembeli** dan `nexgenwatch` memungut **$16,75/event** dengan run yang sama banyaknya. | ✅ **Naik jadi #1 prioritas non-build.** Lakukan kalibrasi Console (§2) **sebelum** ubah harga, supaya tahu titik berangkatnya. |
| **Kleinanzeigen Immobilien** | 🔴 #3, $367 | Korpus baru: **$465, 20 seller, 2 memungut**, `clearpath` FLAT $45 → $270 | ✅ Dipertahankan, angkanya naik |
| **Cek kesehatan `xtracto/skyscanner-scraper`** | 🟠 #4 | Actor sendiri: **165 run/30 hari, 98 sukses = fail 40,6%**, 120 user, memungut $0,20 | ⚠️ **Actor sendiri ternyata juga rusak.** Bukan "ambil pasar tanpa bangun apa pun" — harus diperbaiki dulu. |
| **Dealroom / GoFundMe / Snapchat Ads** | 🟠 #5–#6 | Tidak berubah di korpus baru | 🟡 Dipertahankan di prioritas rendah |
| **Indeed Reviews** | 🟡 "belum diukur uangnya" | **Diukur: $396/bln, $33/pembeli, FLAT $33, fail 0%** | ⬆️ **Naik ke rekomendasi #3** (§5) |
| **Generic Article Extractor** | ⚠️ Sedang | Korpus baru mengonfirmasi vein ramai | ⚠️ Tetap sedang |
| **Apartments.com, Upwork, ImmobilienScout24, Realtor.ca, LoopNet, Bayut** | ❌ Tutup | Tidak berubah | ❌ Tetap tutup |

---

## 10. Status & note untuk build ke depan

### Urutan eksekusi

**#1 — Kalibrasi harga (nol engineering, dampak terbesar).**
Buka Console `xtracto` → pendapatan riil 30 hari → bagi $131,89 → dapat faktor item/run. Lalu:
- naikkan harga event 3–5 actor yang **sudah punya pembeli** (`shopee-search` 217 pembeli, `shopee-scraper` 165, `shopee-shop-scraper` 68) dari $0,002 ke arah persentil-90 Store **$0,012**, atau
- uji **satu** actor dengan FLAT $19 (median Store) sebagai pembanding terkontrol.
*Note:* jangan ubah 218 actor sekaligus — ubah 3–5, tunggu satu siklus 30 hari, baca `totalUsers30Days` sebelum/sesudah. Satu-satunya eksperimen di dokumen ini yang hasilnya bisa dibaca bulan depan.

**#2 — Build klaster event langsung (§4).**
Urutan dalam klaster, dari yang termurah dibangun:
1. **Bandsintown** — API JSON publik, `app_id=web`, sudah terverifikasi mengembalikan 26 event + venue + geo. Paling murah.
2. **Dice.fm** — `__NEXT_DATA__` + `nextCursor`, 348 KB data per halaman kota.
3. **Songkick** — 51 `ld+json` MusicEvent per halaman, paginasi terbukti sampai page 6.
4. **Resident Advisor** — HTML 403 tapi GraphQL 200; sisakan untuk terakhir, butuh satu sesi menyusun query.

*Note build:* satu parser event bersama (nama, artis, venue, tanggal, kota, lat/lon, harga tiket, URL) → 3–4 actor dari satu basis kode. **Harga: jangan $0,002/item.** Incumbent di rak ini memungut FLAT $15–$29 dan mereka satu-satunya yang dapat uang. Kalau tetap PPE, pakai event tingkat-laporan (§6), bukan per-baris.

**#3 — Indeed Reviews** ($396, $33/pembeli, 1 seller memungut dari 7). `xtracto` sudah punya `indeed-jobs-scraper`, jadi domain dan target sudah dikenal — yang dibangun cuma data-type baru. Probe `indeed.com/cmp/<company>/reviews` dulu; Indeed memasang anti-bot di jalur lowongan, belum tentu sama di jalur review.

**#4 — Probe cluster review perjalanan `knagymate`** (HRS, Zoover, Despegar, Kurzurlaub, **+Trip.com**). Pass 5 + 5b. Kalau terbuka → ini vein terbesar di dua putaran terakhir ($943 + $311). Kalau butuh anti-bot berat → tinggalkan; uangnya bertumpu ≈7 pembeli.
*Note:* Trip.com sudah diprobe hari ini — **halaman hotel adalah cangkang**, review datang lewat XHR. Cari endpoint-nya via DevTools sebelum menghitungnya masuk.

**#5 — RECON, bukan build:** kununu (anti-bot 202), StoreLeads (login, tapi $23,31/pembeli dan incumbent fail 75,8%), Mindbody-lead-vertikal ($66,67/pembeli), TecDoc (cek lisensi dulu).

### Aturan proses — perubahan untuk putaran berikutnya

1. **Model uang PPE harus dikalikan faktor item/run sebelum dibandingkan dengan FLAT.** Selama faktor itu belum diukur, **jangan** membuat klaim "FLAT lebih menguntungkan dari PPE". Seluruh dokumen Babak 50 dan arsip pagi mengandung klaim ini — tandai sebagai belum terverifikasi.
2. **Filter penemuan yang dipakai mulai sekarang: `MRR vein ≥ $60` DAN `≤3 seller yang memungut ≥$5`.** Pola "rpu tinggi" (§7) dan "user banyak/seller sedikit" (§8) sudah diuji di korpus 23.779 dan masing-masing menghasilkan 2/22 dan 0/25 kandidat. Pakai keduanya sebagai penjelas, bukan sebagai penyaring.
3. **Korpus band-slice (7 band user per kategori) menggantikan band tunggal.** 23.779 vs 5.773 actor dari kategori yang sama — Gotcha #1 (under-count seller) berkurang drastis walau belum hilang.
4. **Dedupe tiga lapis wajib:** `xtracto` (218) + `fanndev` (75) + 229 folder lokal. Putaran ini menemukan `fanndev/skool-whop-community-analyzer` di vein Skool lewat scan pasar — bukti lapis kedua memang perlu.
5. **Heredoc Bash menelan satu level backslash.** Regex `\\b` di file JSON yang ditulis lewat heredoc berubah jadi karakter backspace dan **diam-diam mencocokkan nol actor** (G2, Seek, Resy sempat terlihat "0 seller" karena ini). Tulis file query lewat Python/Write, jangan heredoc.
6. Verifikasi seller tetap **satu brand = satu query single-token** (Gotcha #2 putaran pagi, masih berlaku).
7. **Selalu Pass 5b.** Trip.com dan FurnishedFinder keduanya balas 200 dengan halaman ratusan KB, dan keduanya **tidak memuat data yang dicari**. Status 200 bukan bukti.

### Tembok yang terbukti hari ini (probe langsung, chrome + safari)

| Target | Hasil |
|---|---|
| `realestate.com.au` | **429** kedua profil TLS — vein AU property $302 tidak bisa diambil |
| `domain.com.au` | **403** kedua profil — vein $260 tutup |
| `buildzoom.com` | **403** |
| `inmuebles24.com` | **403** |
| `kununu.com` | **202** + 2 KB, tanpa `__NEXT_DATA__` = challenge |
| `furnishedfinder.com/housing/…` | redirect ke home (200) atau **403**; ld+json yang muncul milik halaman depan |
| `trip.com` hotel detail | 200 tapi **tanpa `reviewList`/`commentScore`** = cangkang |
| `ra.co` HTML | **403** — tapi `POST /graphql` **200** |

Delapan probe ini menutup empat kandidat ($302 + $260 + $164 + $107) dengan biaya beberapa detik — jauh lebih murah daripada menemukannya setelah actor dibangun.
