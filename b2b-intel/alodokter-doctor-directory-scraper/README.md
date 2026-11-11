# Indonesia Doctor Directory Scraper (Alodokter)

Extract Indonesian doctor listings from **Alodokter** — specialty, hospital, consultation price, patient rating and next availability. No account, login, or API key needed.

## Why use this actor

- **Consultation prices in rupiah** on every listing row — the field most healthcare-market datasets are missing
- **Hospital and address per doctor**, including every clinic a doctor practises at (profiles routinely list two or more)
- **Patient satisfaction and review counts** as published, plus the next available appointment text ("Tersedia Hari Ini", "Jadwal Berikutnya : Besok, 16.00 Siang")
- **17 specialties** — paediatrics, obstetrics, general practice, dentistry, dermatology, cardiology, neurology, ENT, ophthalmology, internal medicine, surgery, pulmonology, nutrition, orthopaedics, urology, psychiatry
- **City targeting** — scope any specialty to Jakarta, Bali, Balikpapan and more
- **Verified inputs** — `reference` mode checks every specialty slug against the live site, so a typo returns a clear error instead of an empty run
- Stable JSON output for market research, pricing analysis or provider databases, with automatic retries

## How it works

Pick a `mode`:

1. **`specialty`** — list doctors in one or more specialties, optionally scoped to a `city`. Pages are followed automatically up to `maxItems`. Turn on `enrichProfiles` to also fetch each doctor's own page.
2. **`doctor`** — full detail for specific doctors, by address or bare slug.
3. **`reference`** — live specialty and city lists.

## Input

**Paediatricians in Jakarta:**

```json
{
  "mode": "specialty",
  "specialty": "dokter-anak",
  "city": "jakarta",
  "maxItems": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Several specialties at once, with full profiles:**

```json
{
  "mode": "specialty",
  "specialties": ["dokter-jantung", "dokter-saraf", "dokter-penyakit-dalam"],
  "enrichProfiles": true,
  "maxItems": 50
}
```

**One doctor:**

```json
{
  "mode": "doctor",
  "doctorUrl": "https://www.alodokter.com/cari-dokter/dr-rifan-fauzie-spa-k"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `specialty`, `doctor`, or `reference`. |
| `specialty` / `specialties` | string / array | Which specialty slug(s) to list. |
| `city` | string | Optional city slug, e.g. `jakarta`. |
| `enrichProfiles` | boolean | Also fetch each listed doctor's own page. |
| `doctorUrl` / `doctorUrls` | string / array | `doctor` mode: address or bare slug. |
| `maxItems` | integer | Max doctors per specialty (10 per page, followed automatically). |
| `maxConcurrency` | integer | Doctor pages fetched in parallel (default 4). |
| `proxyConfiguration` | object | Apify Proxy settings; Residential on by default. |

## Output

**`specialty` mode** — real output:

```json
{
  "_input": "specialty:dokter-anak/jakarta",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-09-08T06:54:15Z",
  "recordType": "DOCTOR_CARD",
  "name": "dr. Markus Mualim Danusantoso, Sp.A",
  "slug": "dr-markus-mualim-danusantoso-spa",
  "profileUrl": "https://www.alodokter.com/cari-dokter/dr-markus-mualim-danusantoso-spa?sku_id=630829fca6839d7867009974",
  "specialty": "Dokter Anak - Ahli Neonatologi",
  "hospital": "Mayapada Hospital Kuningan",
  "hospitalAddress": "Mayapada Hospital Kuningan, Setiabudi, Jakarta",
  "consultationPrice": 350000,
  "priceCurrency": "IDR",
  "rating": "89%",
  "reviewCount": 18,
  "nextSchedule": "Jadwal Berikutnya : Besok, 16.00 Siang",
  "listName": "Dokter Anak",
  "_listingScope": "specialty:dokter-anak/jakarta"
}
```

**`doctor` mode** — real output, arrays truncated:

```json
{
  "recordType": "DOCTOR_PROFILE",
  "name": "dr. Rifan Fauzie, Sp.A (K)",
  "specialty": "Pediatrics",
  "specialtyLabel": "Dokter Anak - Ahli Respirologi",
  "hospital": "RSIA Bunda Jakarta",
  "hospitals": [
    { "name": "RSIA Bunda Jakarta", "address": "Jl. Teuku Cik Ditiro No.28 Menteng Jakarta Pusat, Menteng, Gondangdia, Kota Jakarta Pusat" },
    { "name": "Brawijaya Hospital Saharjo", "address": "Jl. Dr. Saharjo No.199, Tebet Bar., Kec. Tebet, Kota Jakarta Selatan" }
  ],
  "addresses": [
    { "streetAddress": "Jl. Teuku Cik Ditiro No.28 …", "locality": "Jakarta", "region": "Daerah Khusus Ibukota Jakarta", "country": "ID" },
    "… 1 more"
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `recordType` | string | `DOCTOR_CARD`, `DOCTOR_PROFILE`, `SPECIALTY`, or `CITY`. |
| `name` | string | Doctor's name with title. |
| `specialty` / `specialtyLabel` | string | Specialty as published. |
| `hospital` / `hospitalAddress` | string | Primary hospital and its address. |
| `hospitals` | array | Every hospital the doctor practises at. |
| `addresses` | array | Full postal addresses with locality and region. |
| `consultationPrice` / `priceCurrency` | integer / string | Consultation fee and currency. |
| `rating` | string | Patient satisfaction as a percentage, e.g. `"98%"`. |
| `reviewCount` | integer | Number of patient reviews. |
| `nextSchedule` | string | Next availability text. |
| `profileUrl` | string | Public doctor page. |
| `_error` / `_errorDetail` | string | Present only when a page could not be fetched. |

## Notes & limits

- **Listing pages hold 10 doctors.** `maxItems` decides how many pages are walked; an empty page ends the run.
- **Rating is a percentage, not a 5-point score** — the source publishes patient satisfaction as `"98%"`, so it is passed through as text rather than converted.
- **Prices come from listing rows.** A doctor's own page does not always repeat the fee, so run `specialty` mode (or `enrichProfiles`, which keeps both) when you need pricing.
- **Availability text is time-sensitive** — "Tersedia Hari Ini" reflects the moment of the run; schedule a recurring run if you are tracking it.
- **Specialty slugs are Indonesian** (`dokter-anak`, `dokter-jantung`…). An unknown slug returns a clear `not_found` error rather than an empty dataset.
- Only publicly published professional listings are collected; no patient data is involved.
