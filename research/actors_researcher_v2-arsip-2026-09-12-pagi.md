# Riset Pasar Apify Store — v2 (refresh 2026-09-12)

**Tanggal riset:** 2026-09-12
**Akun pembanding (dedupe wajib):** [`xtracto`](https://api.apify.com/v2/store?username=xtracto) — di-refresh hari ini via `python apify-my-store.py xtracto -o output/xtracto-full.json` → **218 actor published** (tidak berubah sejak Babak 47/49/50).
**Riset sebelumnya yang WAJIB dibaca dulu:**
- [`ACTOR_MARKET_RESEARCHER_NEW.md`](ACTOR_MARKET_RESEARCHER_NEW.md) — **50 babak**, 608 KB. Baca **Babak 50 (sumbu UANG, 2026-09-10)** sebelum apa pun — babak itu membatalkan seluruh 9 kandidat Babak 49 karena diranking pakai pembeli, bukan uang.
- [`actors_researcher_v2-arsip-2026-09-07.md`](actors_researcher_v2-arsip-2026-09-07.md) — v2 sebelumnya (arsip, tidak dihapus). Status carry-over di [§8](#8-status-carry-over-kandidat-v2-2026-09-07).

**Data mentah riset ini:**

| File | Isi |
|---|---|
| `output/scan-v3-merged.json` | **5.773 actor unik**, 15 kategori × 6 halaman (band 5–8.000 users) |
| `output/scan-v3-competition2.json` / `3` / `4` | **147 query single-token** — hitungan seller yang dipakai di dokumen ini |
| `output/scan-v3-money.json` | **30 vein diukur dalam UANG** (model Babak 50) — ini yang menentukan peringkat akhir |
| `output/scan-v3-competition.json` | 65 keyword-**gabungan** (metodologi salah, lihat Gotcha #2) — disimpan sebagai bukti, jangan dipakai |
| `output/xtracto-full.json` | 218 actor `xtracto`, snapshot 2026-09-12 |

---

## 1. Ringkasan eksekutif — dan koreksi terhadap draf pertama riset ini

Riset ini awalnya meranking dengan dua pola yang diminta (runs-per-user tinggi, dan seller sedikit). **Setelah 30 vein teratas diukur ulang dengan model uang Babak 50, peringkat itu runtuh persis seperti Babak 49 runtuh di Babak 50.** Contoh paling tajam:

| Kandidat draf pertama | Alasan dipilih | MRR vein sebenarnya | Vonis |
|---|---|---:|---|
| **Waze** (incumbent gagal 100%) | 5 seller, incumbent 100% FAILED | **$3/bln** | ❌ Seluruh vein bernilai $3. Incumbent "rusak" itu memang tidak memungut apa-apa. |
| **AllTrails** | 7 seller, 121.768 runs | **$4/bln** | ❌ |
| **TCGplayer Sales History** | 15.161 runs/user | **$5/bln** | ❌ |
| **Telefonbuch.de / Canadian Tire / Compass.com** | 5–8 seller | **$0/bln** | ❌ Nol, bukan "kecil". |
| **Fuel prices / Yad2 / Spitogatos / Naver Shopping** | seller sedikit | **$1–$4/bln** | ❌ |

**Yang bertahan setelah disaring uang — 6 vein:**

| # | Ide Actor | MRR vein | $/pembeli | Seller nyata | Model harga incumbent | Status |
|---|---|---:|---:|---|---|---|
| 1 | **Cluster review hotel EU/LATAM** — HRS + Zoover + Despegar + Kurzurlaub | **$943** gabungan | **$14–$33** | 4–11 nominal, tapi **hanya `knagymate` yang memungut ≠ $0** | PAY_PER_EVENT volume raksasa | 🔴 Kandidat terkuat. Baca peringatan whale di §3. |
| 2 | **Kleinanzeigen Immobilien** (slice properti saja) | **$367** | $5,39 | 20 di slice; `clearpath` memegang $322 | **FLAT $45/bln** | 🔴 Satu-satunya vein di daftar ini yang uangnya datang dari >1 pembeli nyata |
| 3 | **StreetEasy** | **$261** | $3,04 | 14 | **FLAT $30 + $25/bln** | 🟠 Carry-over v2 lama; klaim "1 seller"-nya salah, tapi uangnya nyata |
| 4 | **Dealroom** (funding/startup DB) | **$147** | $4,75 | 8 | **FLAT $49/bln** | 🟠 Mengisi gap "sub-niche funding" yang v2 lama identifikasi tapi tidak isi |
| 5 | **GoFundMe** | **$61** | $5,05 | 9 | **FLAT $30/bln** | 🟡 Kecil tapi bersih: `jupri` sendirian, 8 seller sisanya $0 |
| 6 | **Snapchat Ads Gallery** | **$60** | $3,02 | 7 di slice *ads* | **FLAT $30/bln** | 🟡 `xtracto` sudah punya moat ad-library (Meta, TikTok, Google) — Snapchat platform yang hilang |

**Temuan struktural yang lebih penting dari keenam vein di atas:**

> **Lima dari enam pemenang uang memakai `FLAT_PRICE_PER_MONTH` $25–$49.** `clearpath` memungut $270 dari **6 pembeli**, `saswave` $147 dari **3**, `jupri` $180 dari **6**, `lexis-solutions` $60 dari **2**. Sementara **215/218 actor `xtracto` memakai PAY_PER_EVENT dan nol flat-bulanan** (temuan Babak 50 yang sampai sekarang belum diuji). Scan ini adalah bukti ketiga berturut-turut bahwa **hambatannya harga, bukan traffic** — dan kali ini buktinya datang dari vein yang rak-nya benar-benar kosong, bukan dari raksasa yang tak terkejar.

---

## 2. Metodologi & 3 gotcha

```bash
# 0) refresh dedupe baseline — WAJIB duluan
python apify-my-store.py xtracto -o output/xtracto-full.json

# 1) Pass lebar: 15 kategori x offset 0..500, band 5<=users<=8000  -> 5.773 actor unik
python scratchpad/scan_v3.py      # -> output/scan-v3-merged.json

# 2) Ranking 4 pola PENEMUAN (bukan pola keputusan)
python scratchpad/rankA.py        # A: runs banyak / user dikit
python scratchpad/concepts2.py    # B: cluster token -> seller distinct
python scratchpad/live.py         # C: fail-rate 30d
python scratchpad/growth.py       # D: momentum u30/totalUsers

# 3) Verifikasi kompetisi — 147 query SINGLE-TOKEN, regex-filter per brand
python scratchpad/verify2.py ; python scratchpad/verify3.py ; python scratchpad/verify4.py

# 4) PENENTU: 30 vein diukur dengan model uang Babak 50
python scratchpad/money_v3.py     # -> output/scan-v3-money.json
```

### Gotcha #1 — band-scan **selalu under-count seller**

Scan berband (`--max-users 8000`) + relevance-order memotong ekor panjang:

| Konsep | Seller menurut band-scan | Seller sebenarnya | Sum users sebenarnya |
|---|---|---|---|
| RedNote/Xiaohongshu | 6 | **56** | 21.317 |
| Wellfound/AngelList | 3 | **73** | 9.682 |
| Clutch.co | 2 | **81** | 9.418 |
| Google Play reviews | 1 | **169** | 10.571 |
| Bilibili | 1 | **49** | 3.606 |
| Mercadolibre | 2 | **57** | 8.844 |
| Flipkart | 3 | **45** | 2.056 |

### Gotcha #2 — query **multi-kata** juga under-count (baru)

Query `"avvo justia lawyer directory"` menaruh `voyn (136u)` di puncak dan **melewatkan `fatihtahta/avvo-scraper` yang 1.250 users** — relevance Algolia memecah skor ke semua kata sehingga brand-nya tenggelam. Query `"avvo"` saja → 15 seller, 1.588 users, `fatihtahta` teratas. **Satu brand = satu query.**

### Gotcha #3 — jumlah seller adalah sinyal PENEMUAN, bukan sinyal KEPUTUSAN

Ini pengulangan pelajaran Babak 50 dalam bentuk baru. Riset ini menemukan tiga cara "seller sedikit" berbohong:

1. **Seller yang tidak memungut apa-apa.** Waze punya 5 seller dan incumbent-nya 100% gagal — tapi seluruh vein bernilai $3/bln. "Rak kosong" tidak sama dengan "ada uang di rak".
2. **Seller sedikit = monopoli, bukan celah.** GMGN: 6 seller, `muhammetakkurtt` memegang 2.204 dari 2.248 users (98%).
3. **Users tinggi tanpa rekurensi.** Yupoo 1.553 users tapi **11 runs/user** → user coba sekali lalu pergi.

Silang-cek wajib: **MRR vein + $/pembeli + runs/user + share seller teratas.** Keempatnya, bukan salah satu.

> Catatan: pola C (fail-rate) dan D (momentum) di §5–§6 **bukan temuan baru** — `publicActorRunStats30Days` sudah dipakai di Babak 50. Yang baru di sini cuma penerapannya ke korpus kategori, dan hasilnya konsisten: fail-rate menunjuk actor yang rusak, **bukan** vein yang bernilai.

---

## 3. Vein pemenang #1 — cluster review hotel EU/LATAM (`knagymate`)

Satu seller memegang empat portal review perjalanan yang tidak disentuh siapa pun:

| Actor | Users | Runs (total) | runs/user | MRR (lantai PPE) | $/pembeli | Seller lain di vein |
|---|---:|---:|---:|---:|---:|---|
| `knagymate/hrs-reviews-scraper` | 20 | **464.457** | 23.223 | **$499** | $19,21 | 10 seller, **semua $0** |
| `knagymate/zoover-reviews-scraper` | 2 | 151.228 | 75.614 | **$195** | $32,55 | 5 seller, semua $0 |
| `knagymate/despegar-reviews-scraper` | 8 | 162.468 | 20.308 | **$190** | $23,81 | 4 seller, semua $0 |
| `knagymate/kurzurlaub-reviews-scraper` | 5 | 54.270 | 10.854 | **$58** | $14,55 | 3 seller, semua $0 |
| **Total cluster** | 35 | **832.423** | — | **≈$943/bln** | **$14–33** | — |

**Kenapa ini lolos saringan uang:** rata-rata Store cuma **$0,54 per pembeli aktif/bulan** (Babak 50). Vein ini $14–33 — **26–60× rata-rata pasar**, sekelas dengan klaster premium yang Babak 50 identifikasi ($26,98/pembeli). Bandingkan: Douyin $0,06, sports odds $0,03, Google Hotels $0,35.

**Kenapa ini belum boleh langsung dibangun — dua risiko nyata:**

1. **Whale.** HRS: **169.867 run dalam 30 hari dari 1 user aktif**. Zoover dan Kurzurlaub juga 1 user aktif. Jadi $943/bln itu datang dari **≈7 pembeli, sebagian besar dari 1–4 orang**. Kalau whale-nya pergi, vein-nya nol. Membangun kloning tidak otomatis memindahkan whale — dia sudah punya integrasi yang jalan.
2. **MRR di sini adalah LANTAI PPE** (run sukses × harga event, asumsi 1 event/run). Kalau actor `knagymate` mengenakan >1 event per run, angka aslinya lebih besar; kalau harga tier-nya beda dari GOLD, lebih kecil. Angka ini urutan, bukan akuntansi.

**Riset lama SUDAH melihat cluster ini dan menolaknya — dengan sumbu yang salah.** `ACTOR_MARKET_RESEARCHER_NEW.md` baris 848 (bagian TRAVEL) mencatat `hrs-reviews-scraper` dan `despegar-reviews-scraper` sebagai "outlier dengan rpu tertinggi di seluruh riset lintas-kategori", lalu **membatalkannya** karena "HRS reviews sudah 6 seller, Despegar reviews sudah 3 seller". Pengukuran uang hari ini menunjukkan **6 seller HRS itu memungut $0,00–$0,08/bln, dan 3 seller Despegar $0,03–$0,08** — mereka ada di rak, tapi tidak ada satu pun yang berjualan. Ini contoh konkret kesalahan yang persis dikoreksi Babak 50: **menghitung seller, bukan menghitung uang.** Zoover pernah disinggung sekali (2u/142.450r) tanpa ditindaklanjuti; Kurzurlaub nol hit.

**Yang harus diprobe sebelum commit:** apakah HRS/Zoover/Despegar/Kurzurlaub bisa diambil HTTP-polos tanpa WAF — prosedur Pass 5 + **Pass 5b** Babak 50 (verifikasi ada nilai data asli, bukan cangkang JS; ini yang menggugurkan Apple Maps). Keempat domain ini belum pernah masuk daftar probe di 50 babak, hanya pernah dinilai dari statistik Store.

---

## 4. Pola A & B — daftar penemuan lengkap, dengan kolom uang

Semua baris **tidak ada di `xtracto`** kecuali yang ditandai. Kolom MRR adalah penentu; kolom rpu/seller hanya menjelaskan bagaimana kandidatnya ditemukan.

| Ide | Incumbent | rpu | Seller | **MRR vein** | **$/pembeli** | Vonis |
|---|---|---:|---:|---:|---:|---|
| HRS / Zoover / Despegar / Kurzurlaub | `knagymate` ×4 | 10.854–75.614 | 4–11 | **$943** | $14–33 | ✅ §3 |
| Kleinanzeigen Immobilien | `clearpath/kleinanzeigen-immobilien-api-pro` 15u/150.244r | 10.016 | 20 | **$367** | $5,39 | ✅ Slice properti saja; Kleinanzeigen umum 68 seller |
| StreetEasy | `jupri/streeteasy-scraper` 214u/2.031.255r | 9.492 | 14 | **$261** | $3,04 | ✅ Carry-over, lihat §8 |
| Dealroom | `saswave/dealroom-scraper` 148u/248.179r | 1.677 | 8 | **$147** | $4,75 | ✅ |
| GoFundMe | `jupri/gofundme` 104u/184.072r | 1.770 | 9 | **$61** | $5,05 | ✅ |
| Snapchat Ads Gallery | `lexis-solutions/snapchat-ads-scraper` 57u/259.274r | 4.549 | 7 (slice *ads*) | **$60** | $3,02 | ✅ Moat ad-library `xtracto` nyambung |
| Wer-liefert-was (wlw) B2B DE | `codebyte/wer-liefert-was-b2b-marketplace` 138u/104.503r | 757 | 10 | $45 | $1,06 | 🟡 Marginal. Nyambung Europages + ThomasNet `xtracto`. |
| Noon.com seller monitoring | `saswave/noon-seller-monitoring` 62u/903.140r | 14.567 | 20 | $90 | $0,72 | 🟡 rpu spektakuler, uang biasa saja |
| DoorDash reviews | `e-commerce/doordash-reviews-scraper` 94u/785.840r | 8.360 | 24 | $163 | $1,75 | 🟡 Riset lama menandai cluster DoorDash/Grubhub/OpenTable sudah dikuasai |
| Propwire | `memo23/propwire-leads-scraper` | — | 9 | $28 | $0,23 | ❌ |
| Ryanair | `epctex/ryanair-scraper` 243u/303.046r | 1.247 | 16 | $26 | $0,69 | ❌ |
| Kiwi.com | `ecomscrape/kiwi-flight-search-scraper` 41u/296.117r | 7.222 | 7 | $20 | $0,84 | ❌ |
| Kaufland.de | `e-commerce/kaufland-reviews-scraper` | — | 5 | $6 | $0,38 | ❌ |
| TCGplayer Sales History | `scraped/tcgplayer-sales-history` 61u/924.819r | 15.161 | 18 | **$5** | $0,11 | ❌ ⚠️ `xtracto` punya `tcgplayer-price-scraper` (data-type beda) — tapi uangnya tidak ada |
| AllTrails | `parseforge/alltrails-scraper` 127u/121.768r | 959 | 7 | **$4** | $0,20 | ❌ |
| Naver Shopping | `delicious_zebu` 531u, rating 4,99★(41) | — | 8 | $4 | $0,02 | ❌ Rating tertinggi di seluruh scan, uang nol |
| **Waze** | `phantom_coder/waze-traffic-scraper` 168u, **fail 100%** | — | 5 | **$3** | $0,10 | ❌ **Kandidat #1 draf pertama — dibatalkan** |
| Yad2 | `amit123/YadScraper` | — | 9 | $1 | $0,01 | ❌ |
| Spitogatos | `fayoussef/spitogatos-scraper` | — | 8 | $1 | $0,02 | ❌ |
| Fuel prices | `johnvc/fuelprices` 206u/314.517r | 1.527 | 22 | $1 | $0,01 | ❌ |
| Telefonbuch.de | `santamaria-automations/telefonbuch-de-scraper` 24u/145.742r | 6.073 | 7 | **$0** | $0,04 | ❌ |
| Canadian Tire | `azzouzana/canadiantire-ca-scraper` 37u/163.598r | 4.422 | 5 | **$0** | $0,01 | ❌ ⚠️ Riset lama menaruh ini di urutan eksekusi #3 — **sumbu uang membatalkannya** |
| Compass.com | `canadesk/compass-properties` 17u/137.631r | 8.096 | 8 | **$0** | $0,01 | ❌ Riset lama juga sudah memuatnya |
| Mastodon | `canadesk/mastodon` 31u/1.056.999r | 34.097 | 41 nominal, sum 386u | — | — | ❌ Riset lama sudah memakai ini sebagai contoh anti-pola "36 seller mainan + 1 whale" |
| Apple Maps | `zen-studio/apple-maps-scraper-pro` 102u/714.126r | 7.001 | 16 | — | $12,55 (Babak 50) | ❌ Probe `maps.apple.com` *false positive*, gugur di Pass 5b Babak 50 |
| Dark web | `epctex/darkweb-scraper` 1.873u | 5 | 7 | — | — | ❌ Risiko ToS/legal + 5 runs/user |
| GMGN | `muhammetakkurtt` 2.204 dari 2.248u | — | 6 | — | — | ❌ Monopoli 98%, bukan celah |
| Yupoo | `pizani` 804u + `yupoo-scraper` 499u | 11 | 7 | — | — | ❌ 11 runs/user = coba sekali lalu pergi |

---

## 5. Pola C — incumbent rusak (penemuan, bukan keputusan)

`(FAILED + TIMED-OUT) / TOTAL` dari `publicActorRunStats30Days`, filter ≥3.000 run/30 hari dan ≥10 user aktif.

| Incumbent | Fail 30d | u30 | Runs 30d | Total user | Baca |
|---|---:|---:|---:|---:|---|
| `phantom_coder/waze-traffic-scraper` | **100,0%** | 10 | 22.414 | 168 | Mati total — **tapi vein-nya cuma $3/bln.** Bukti bahwa fail-rate saja bukan sinyal uang. |
| `jupri/expedia-hotels` | **99,8%** | 4 | 29.513 | 674 | Vein Expedia $193/bln, 33 seller, $0,64/pembeli. `xtracto` punya `expedia-cars` bukan hotels — gap data-type nyata, uangnya tipis. |
| `curious_coder/discord-data-scraper` | 76,9% | 41 | 63.931 | 1.279 | Discord login-gated; kemungkinan rusak permanen. |
| `automation-lab/instagram-scraper` | 76,3% | 106 | 6.403 | 1.031 | Konsisten dengan memori `instagram_api_v1_closed_2026` — `/api/v1` tutup, IG scraper patah massal. |
| `piotrv1001/alibaba-listings-scraper` | 62,4% | 47 | 4.817 | 641 | `xtracto` punya 5 actor Alibaba → moat langsung. |
| `scrapemind/Realtor-ca-Scraper` | 55,3% | 11 | 15.753 | 316 | ⚠️ Babak 50 sudah membuktikan **Realtor.ca 403** — temboknya, bukan actornya. |
| `crawlio/skyscanner-flights-scraper` | 49,2% | 34 | 9.685 | 56 | Vein Skyscanner **$258/bln**, `jupri` memegang $210. `xtracto` punya `skyscanner-scraper` (120u) — **cek kesehatan actor sendiri dulu**; kalau hijau, ini ambil pasar tanpa bangun apa pun. |
| `memo23/skyscanner-scraper` | 38,2% | 85 | 17.434 | 328 | Dua incumbent Skyscanner rusak sekaligus. |
| `zen-studio/trustpilot-review-scraper` | 40,5% | 130 | 4.747 | 672 | `xtracto` punya `trustpilot-reviews` (2u) — produk sudah ada, yang kurang QA + marketing. |
| `devscrapper/whatsapp-number-validator` | 33,2% | 244 | 97.764 | 2.392 | Niche ramai (27 seller / 10.917u); yang terbesar patah. |
| `zerobreak/google-hotels-scraper` | 26,9% | 511 | 54.242 | 551 | ❌ **Babak 50 sudah membatalkan Google Hotels**: vein $237/bln, $0,35/pembeli, incumbent ini memungut $119. Momentum 93% tidak mengubah itu. |

> Fail-rate tinggi bisa berarti (a) target memasang anti-bot baru, (b) input user salah, atau (c) actor patah. **Sinyal untuk diprobe, bukan bukti celah** — dan §4 membuktikan ia juga bukan sinyal uang.

---

## 6. Pola D — momentum (u30 / totalUsers)

| Actor | u30 / total | Baca |
|---|---|---|
| `zerobreak/google-hotels-scraper` | 511 / 551 = **93%** | ❌ Dibatalkan Babak 50 lewat sumbu uang. |
| `johnvc/workday-careers-api` | 69 / 74 = **93%** | Workday 92–111 seller. Yang naik pendekatan API-nya, bukan niche-nya. |
| `moving_beacon-owner1/medium-scraper` | 252 / 336 = 75% | ❌ Babak 50: vein Medium **$31/bln**, $0,11/pembeli. |
| `s-r/backlinks-checker` | 313 / 464 = 67% | SEO tooling, di luar fokus scraping. |
| `unseenuser/LinkedIn-Profile` | 1.087 / 1.780 = 61% | LinkedIn — jenuh permanen. |
| `johnvc/YoutubeTranscripts` | 1.808 / 3.024 = 60% | 58 seller di slice transcriber. |
| `extractify-labs/flashscore-tennis-matches` | 915 / 1.773 = 52% | ⚠️ Akun utama **sudah punya** `flashscore-all-sports-scraper` (2026-09-08). Konfirmasi timing, bukan kandidat. |
| `bigdavidson/kalshi-weather-markets` | 120 / 228 = 53% | 50 seller (banyak noise), runs rendah. |
| `shelvick/county-property-records` | 41 / 82 = 50% | 23 seller / 216u. Riset lama sudah menutup cluster data publik AS. |

**Kesimpulan pola D: nol kandidat lolos.** Momentum tinggi konsisten menunjuk vein bertarif rendah — pola yang sama yang membuat Babak 49 runtuh.

---

## 7. Temuan harga (lanjutan Rekomendasi #1 Babak 50)

Lima dari enam pemenang uang memakai **FLAT_PRICE_PER_MONTH**, dan uangnya datang dari segelintir pembeli:

| Incumbent | Model | Harga | Pembeli 30d | MRR |
|---|---|---:|---:|---:|
| `clearpath/kleinanzeigen-immobilien-api-pro` | FLAT | $45/bln | 6 | $270 |
| `jupri/streeteasy-scraper` | FLAT | $30/bln | 6 | $180 |
| `saswave/dealroom-scraper` | FLAT | $49/bln | 3 | $147 |
| `memo23/apify-streeteasy-cheerio` | FLAT | $25/bln | 3 | $75 |
| `lexis-solutions/snapchat-ads-scraper` | FLAT | $30/bln | 2 | $60 |
| `jupri/gofundme` | FLAT | $30/bln | 2 | $60 |
| `0nixion/KleinanzeigenScraper` | FLAT | $20/bln | 2 | $40 |

Bandingkan dengan seluruh kompetitor PAY_PER_EVENT di vein yang sama: **$0,00–$5,15/bln**. Selisihnya bukan 2×, tapi 10–100×.

**`xtracto`: 215/218 actor PAY_PER_EVENT, nol flat-bulanan** (Babak 50, dikonfirmasi ulang hari ini — 218 actor tidak berubah). Rekomendasi #1 Babak 50 — uji flat $20–$30 pada 3–5 actor yang sudah punya pembeli — **masih belum dijawab**, dan riset ini menambah bukti ketiga untuk itu.

Pengecualian yang penting: cluster `knagymate` (§3) memungut $943 justru **dengan PAY_PER_EVENT**, karena volume run-nya 832 ribu. Jadi PPE bukan salah secara mutlak — PPE salah untuk actor bervolume rendah, dan itulah mayoritas portofolio `xtracto`.

---

## 8. Status carry-over kandidat v2 (2026-09-07)

| Kandidat lama | Prioritas lama | Angka hari ini | Status baru |
|---|---|---|---|
| Generic Article/Readability Extractor | 🔴 Tinggi | Vein $302/bln tapi **55 seller**, $1,17/pembeli; `web.harvester/articles-extractor` 760u/902.927r memungut $195 | ⚠️ **Turun ke Sedang.** Moat-reuse-nya tetap terbaik di repo (100+ scraper artikel), tapi vein-nya ramai dan bertarif rendah. Layak hanya kalau dijual FLAT, bukan PPE. |
| StreetEasy | 🔴 Tinggi | **14 seller / 846u** (bukan 1), vein **$261/bln**, incumbent FLAT $30 | ✅ **Dipertahankan.** Klaim "1 seller" korban Gotcha #1, tapi uangnya lolos saringan. |
| Apartments.com | 🟠 Sedang-Tinggi | **35 seller / 2.428u**, `epctex` 1.376u | ❌ **Tutup.** Jauh lebih ramai dari perkiraan. |
| Indeed Reviews | 🟡 Sedang | `memo23/apify-indeed-reviews` 287u/319.293r + varian `-ppr` | 🟡 Belum diukur uangnya. Ukur dulu sebelum dieksekusi. |
| Upwork Talent/Freelancer | 🟡 Sedang | Babak 50: **Upwork 403 + RSS 410 Gone** | ❌ **Tutup** — temboknya, bukan kompetisinya. |
| Crunchbase sub-niche funding | 🟢 Rendah-Sedang | **Dealroom**: 8 seller, $147/bln, $4,75/pembeli, FLAT $49 | ⬆️ **Naik ke #4.** Eksekusi konkret dari saran itu. |
| ImmobilienScout24 | 🟢 Rendah | **32 seller / 2.280u** | ❌ **Tutup.** |
| Cloud Storage Uploader | ⚪ Catatan | — | ⚪ Tetap di luar strategi. |

---

## 9. Sudah ada di `xtracto` — dedupe positif

| Konsep dari scan | Actor `xtracto` yang sudah ada |
|---|---|
| Mercadolibre (57 seller, 8.844u) | `mercadolibre-scraper` (7u) |
| RedNote/Xiaohongshu (56 seller, 21.317u) | `rednote-xiaohongshu-scraper` (4u) |
| Bilibili (49 seller, 3.606u) | `bilibili-danmaku` (8u) |
| Wellfound/AngelList (73 seller, 9.682u) | `wellfound-jobs-scraper` (8u) |
| Google Play reviews (169 seller, 10.571u) | `google-play-reviews-scraper` (2u) |
| TCGplayer *harga* | `tcgplayer-price-scraper` (2u) — *sales history gap, tapi vein cuma $5* |
| Mobile.de (27 seller, 2.942u) | `mobilede-listings` (8u) |
| Leboncoin (56 seller, 4.427u) | `leboncoin-listings` (2u) |
| Wildberries (22 seller) | `wildberries-product-scraper` (3u) |
| Idealista / Zoopla / Rightmove / Daft.ie / Redfin / Zillow / Realtor | `idealista-property-scraper`, `zoopla-property-scraper`, `rightmove-property-scraper`, `daft-ie-property-scraper`, `redfin-listings`, `zillow-all-in-one-scraper`, `realtor-all-in-one-scraper` |
| PropertyFinder AE (56 seller, 6.074u) | `propertyfinder-dubai-leads`, `propertyfinder-offplan-tracker` |
| Trustpilot (incumbent fail 40%) | `trustpilot-reviews` (2u) |
| ATS Greenhouse/Lever/Workday | `ats-jobs-aggregator` (3u), `ats-hiring-velocity` (2u) |
| Etsy (102 seller, 57.840u) | `etsy-product-scraper`, `etsy-search-scraper`, `etsy-shop-scraper` |
| Quora (27 seller, 22.009u) | `quora-user-profile` (3u) |
| Skyscanner (2 incumbent rusak, vein $258) | `skyscanner-scraper` (120u) |
| Expedia (incumbent fail 99,8%) | `expedia-cars`, `expedia-brazil-car-rentals` — *hotels masih gap* |

Sudah dibangun **akun utama** (folder repo ini), bukan `xtracto` — jangan diulang:
`socialblade-creator-analytics-scraper`, `flashscore-all-sports-scraper`, `instagram-content-scraper`, semua `amazon-*`, `blibli-*`, `klikindomaret-scraper`, `luma-scraper`, `substack-scraper`, `bluesky-scraper`, `poshmark-scraper`, `point2homes-scraper`, `h1bdata-scraper`, `partiful-scraper`.

---

## 10. Di-skip, dengan alasan

| Niche | Alasan |
|---|---|
| **Waze, AllTrails, TCGplayer, Telefonbuch, Canadian Tire, Compass, Fuel prices, Yad2, Spitogatos, Naver Shopping, Kaufland, Propwire, Ryanair, Kiwi.com** | Rak kosong tapi **vein $0–$28/bln**. Semua diukur, bukan ditebak (`output/scan-v3-money.json`). |
| **Google Hotels, Medium, Douyin, sports odds, tech-stack detector, keyword volume, Google Lens, Himalayas/WTTJ, TikTok Shop** | Sudah dibatalkan Babak 50 lewat sumbu uang. Jangan diusulkan lagi. |
| **Apple Maps** | Probe `maps.apple.com` *false positive* (cangkang MapKit), gugur di Pass 5b Babak 50. |
| **Mastodon** | 41 seller mainan + 1 whale. Contoh anti-pola di riset lama. |
| **Realtor.ca, LoopNet, Upwork, Bayut** | Tembok terbukti di Babak 50: 403 / 403 / 403+410 Gone / 503. |
| **Dark web / Tor** | Risiko ToS & legal, 5 runs/user. |
| **GMGN, Yupoo** | Monopoli 98% (GMGN); 11 runs/user (Yupoo). |
| **Data pemilik properti Dubai** | Vein terkaya di Store ($85,21/pembeli) tapi **PII massal — kebijakan portofolio sudah menolaknya** di Babak 40/41/45/46/49/50. |
| **Naukri, Seek, Wellfound, Clutch, Google Play, RedNote, Etsy, Quora, Vinted, LinkedIn** | 45–169 seller. Jenuh total. |
| **Screenshot API, RSS reader, WHOIS/domain, email verifier** | 36–126 seller + kategori utility/dev-tools, di luar bisnis akun. |
| **SPORTS non-odds (MLB / ESPN / SofaScore / Transfermarkt)** | MLB 42 seller, ESPN 48, SofaScore 20, Transfermarkt 21. **Klaim "SPORTS = blue ocean" dari v2 lama resmi ditutup.** |
| **Ceneo, Cdiscount, Takealot, Falabella, Rakuten, Hepsiburada, Asda/Tesco, Dealabs** | sum users 15–227, runs <12.000. TAM terlalu kecil. |
| **Job board per-negara, business registry, tender, court records, secretary-of-state, Bundesagentur, Fragrantica, OpenTable, Similarweb, Upwork Job Postings** | Tuntas diverifikasi jenuh di riset lama + arsip v2. |

---

## 11. Status & Note untuk build ke depan

**Urutan eksekusi yang disarankan:**

1. **Probe cluster review hotel EU/LATAM** (HRS, Zoover, Despegar, Kurzurlaub) — $943/bln, $14–33/pembeli. Riset lama menolaknya di baris 848 karena "6 dan 3 seller"; **semua seller itu memungut ~$0** (§3).
   *Note build:* jalankan Pass 5 + **Pass 5b** dulu (HTTP polos → lalu verifikasi isinya data asli, bukan cangkang JS). Kalau keempatnya terbuka, ini satu keluarga produk dengan parser review yang sama — 4 actor dari 1 basis kode. **Risiko yang harus disadari: uang vein ini bertumpu pada ≈7 pembeli, sebagian besar 1 orang per actor.** Bangun kalau probe-nya murah, jangan bangun kalau butuh anti-bot berat.
2. **Uji harga FLAT $25–$30** pada 3–5 actor `xtracto` yang sudah punya pembeli — Rekomendasi #1 Babak 50, belum dijawab, dan §7 menambah bukti ketiga. **Ini nol effort engineering dan dampaknya paling besar di seluruh dokumen ini.**
3. **Kleinanzeigen Immobilien** — $367/bln, incumbent FLAT $45 dengan 6 pembeli nyata (bukan 1 whale). Slice properti saja; Kleinanzeigen umum 68 seller.
4. **Cek kesehatan `xtracto/skyscanner-scraper`** — dua incumbent Skyscanner rusak (49,2% dan 38,2%) di vein $258/bln. Kalau actor sendiri hijau, ini ambil pasar **tanpa membangun apa pun**.
5. **Dealroom** ($147, FLAT $49, 8 seller) dan **GoFundMe** ($61, FLAT $30, 9 seller) — kecil tapi bersih, dan keduanya mengisi gap yang v2 lama identifikasi.
6. **Snapchat Ads Gallery** ($60, FLAT $30) — melengkapi moat ad-library `xtracto` (Meta + TikTok + Google sudah ada). Catatan: Babak 50 sudah menandai **Snapchat profil** (`snapchat.com/add/<user>` → `__NEXT_DATA__`, tanpa WAF) sebagai kandidat hidup — **dua data-type berbeda di platform yang sama, keduanya kosong di `xtracto`.**

**Aturan proses yang berubah mulai sekarang:**

1. Refresh `output/xtracto-full.json` **sebelum** melihat market — selalu.
2. Tidak ada kandidat masuk shortlist tanpa **query single-token + seller distinct** (Gotcha #1 & #2).
3. **Tidak ada kandidat masuk rekomendasi tanpa MRR vein + $/pembeli** (`scratchpad/money_v3.py`). Runs-per-user, jumlah seller, fail-rate, dan momentum semuanya **alat penemuan**; hanya uang yang memutuskan. Riset ini adalah kali kedua berturut-turut peringkat non-uang runtuh — jangan ulangi ketiga kalinya.
4. Grep `ACTOR_MARKET_RESEARCHER_NEW.md` untuk nama platform **sebelum** mengklaim "kandidat baru". Hati-hati false positive bahasa Indonesia: `temu` cocok dengan "ditemukan" (269 hit palsu), `dun` dengan "dunia". Selalu pakai konteks: `grep -io ".\{70\}<kata>.\{90\}" ACTOR_MARKET_RESEARCHER_NEW.md`.
5. Seller sedikit **bukan** bukti pasar terbuka — tiga mode kegagalannya ada di Gotcha #3.
