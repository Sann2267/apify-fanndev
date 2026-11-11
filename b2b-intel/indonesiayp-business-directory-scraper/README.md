# Indonesia Business Directory Scraper (IndonesiaYP)

Extract Indonesian business listings from **IndonesiaYP** — name, address, phone, website, GPS coordinates, opening hours and more. No account, login, or API key needed.

## Why use this actor

- **Contact-ready B2B lead data for Indonesia** — landline *and* mobile phone, full street address, city and province for every listing
- **Coordinates included** — latitude/longitude on each business page, so listings drop straight onto a map or into a radius search
- **Operational detail most directories hide** — opening hours per day, establishment year, employee band, named company manager, and the business's own description
- **Big categories** — the Restaurants category alone held ~13,900 listings at the time of writing; Lawyers, Doctors & Clinics, Estate Agents, Construction Services, Employment Agencies, Schools, Shopping Centres and Vehicle Services are all covered, plus sub-categories
- **City targeting** — scope any category to Jakarta, Surabaya, Bandung, Medan and more
- **Two-stage by design** — list cheaply first, then optionally enrich every row with its full page in the same run
- Stable JSON output for CRMs and spreadsheets, with automatic retries — no scrapers or browsers to babysit

## How it works

Pick a `mode`:

1. **`category`** — list every business in a category, optionally scoped to one `city`. Pages are followed automatically up to `maxItems`. Turn on `enrichProfiles` to also pull each business's full page.
2. **`company`** — full detail for specific businesses, by address or numeric ID.
3. **`reference`** — the live category and city lists.

## Input

**All restaurants in Jakarta:**

```json
{
  "mode": "category",
  "category": "restaurants",
  "city": "Jakarta",
  "maxItems": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Lawyers nationwide with full contact detail:**

```json
{
  "mode": "category",
  "category": "lawyers",
  "enrichProfiles": true,
  "maxItems": 200,
  "maxConcurrency": 4
}
```

**One business:**

```json
{
  "mode": "company",
  "companyUrl": "https://www.indonesiayp.com/company/836133/spaccanapoli_di_ubud"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `category`, `company`, or `reference`. |
| `category` | string | Category slug, e.g. `restaurants`, `lawyers`, `doctors_and_clinics`. |
| `city` | string | Optional city scope, e.g. `Jakarta`. |
| `enrichProfiles` | boolean | Also fetch each listed business's full page. |
| `companyUrl` / `companyUrls` | string / array | `company` mode: business address or numeric ID. |
| `maxItems` | integer | Max businesses to list (20 per page, followed automatically). |
| `maxConcurrency` | integer | Business pages fetched in parallel (default 4). |
| `proxyConfiguration` | object | Apify Proxy settings; Residential on by default. |

## Output

**`category` mode** — real output:

```json
{
  "_input": "category:lawyers/city:Jakarta",
  "_source": "S1-html",
  "_scrapedAt": "2026-09-08T06:46:21Z",
  "recordType": "BUSINESS_CARD",
  "companyId": "838729",
  "name": "Smart Legal",
  "profileUrl": "https://www.indonesiayp.com/company/838729/Smart_Legal",
  "address": "Legalo Virtual Office,18 Office Park, Lt. 10, Jl. TB. Simatupang No. 18 Kebagusan, Pasar Minggu, RT.2/RW.1, Kebagusan, Ps. Minggu, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12520, Java, Indonesia",
  "city": "Jakarta",
  "phone": "02180674920",
  "isVerified": true,
  "yearsListed": 8,
  "establishedYear": 2012,
  "rating": 5.0,
  "reviewCount": 1,
  "photoCount": 1,
  "hasWebsite": true,
  "hasEmail": true,
  "_listingScope": "category:lawyers/city:Jakarta"
}
```

**`company` mode** — real output, description truncated:

```json
{
  "recordType": "BUSINESS_PROFILE",
  "companyId": "836133",
  "name": "Spaccanapoli di Ubud",
  "streetAddress": "jalan pengosekan 108  Ubud",
  "city": "Denpasar",
  "region": "Bali",
  "country": "ID",
  "phone": "03619080197",
  "mobilePhone": "081237614638",
  "website": "http://www.spaccanapoliubud.com/",
  "latitude": -8.52266657305169,
  "longitude": 115.262914001941,
  "rating": 5.0,
  "reviewCount": 3,
  "workingHours": "Monday: 11-23 Tuesday: 11-23 Wednesday: 11-23 Thursday: 11-23 Friday: 11-23 Saturday: 11-23 Sunday: 11-23",
  "manager": "I Gede Mariano",
  "establishedYear": 2012,
  "employees": "11-15",
  "description": "not only a restaurant .... but a place for those who love truth and reality .. Ristorante Spaccanapoli di Ubud is a traditional italian restaurant located at ubud …"
}
```

| Field | Type | Description |
|---|---|---|
| `recordType` | string | `BUSINESS_CARD`, `BUSINESS_PROFILE`, `CATEGORY`, or `CITY`. |
| `companyId` | string | Stable numeric ID — use it to deduplicate. |
| `name` | string | Business name. |
| `address` / `streetAddress` | string | Full address line (listing) / street part (profile). |
| `city` / `region` / `country` | string | Location fields. |
| `phone` / `mobilePhone` | string | Landline and mobile numbers. |
| `website` | string | Business website. |
| `latitude` / `longitude` | number | GPS coordinates (profile records). |
| `rating` / `reviewCount` | number / integer | Rating out of 5 and review count. |
| `workingHours` | string | Opening hours per day. |
| `manager` | string | Named company manager. |
| `establishedYear` | integer | Year established. |
| `employees` | string | Employee count band. |
| `description` | string | Business description. |
| `categories` | string | All categories the business is listed in. |
| `isVerified` / `yearsListed` / `photoCount` | boolean / integer | Listing quality signals. |
| `hasWebsite` / `hasEmail` | boolean | Whether the listing has those on file. |
| `_error` / `_errorDetail` | string | Present only when a page could not be fetched. |

## Notes & limits

- **Listing pages hold 20 businesses.** `maxItems` decides how many pages are walked.
- **Only ~12% of listings carry a rating** — most Indonesian businesses in the directory have no reviews yet, so `rating` and `reviewCount` are often null. Phone, address and establishment year were present on every row in testing.
- **E-mail addresses are not published.** The directory routes mail through its own enquiry form, so the output flags `hasEmail` rather than inventing an address.
- **City spelling must match the source** (`Jakarta`, not `DKI Jakarta`). Run `reference` mode to see the exact values.
- Every field is business contact information published by the directory itself.
