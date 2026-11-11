# India Lawyer Directory Scraper (LawRato)

Extract lawyer and advocate profiles from **LawRato** — India's largest consumer legal directory. Browse by city or practice area, or pull complete profiles. No account, login, or API key needed.

## Why use this actor

- **Structured legal lead data for India** — name, city and neighbourhood, rating, number of user ratings, and years in practice for every listed advocate
- **Full profiles when you need depth** — bar council of enrolment and enrolment year, practice areas with their skill lists, specific services offered, courts the lawyer appears before, languages spoken, verified badge and public Q&A activity
- **Two ways to slice the directory** — 16 cities (Delhi, Mumbai, Bangalore, Chennai, Kolkata, Pune, Hyderabad, Ahmedabad, Jaipur, Lucknow, Nagpur, Chandigarh, Faridabad, Ghaziabad, Gurgaon, Noida) or 30 practice areas (divorce, criminal, property, corporate, tax, cyber crime, immigration, GST…)
- **One-click enrichment** — list a city, then optionally fetch every lawyer's full profile in the same run
- **Honest about counts** — upstream publishes rating counts in rounded buckets ("100+"), and the output flags that explicitly instead of pretending it's exact
- Stable JSON output for CRMs, lead pipelines or spreadsheets, with automatic retries — no scrapers or browsers to babysit

## How it works

Pick a `mode`:

1. **`directory`** — list lawyers across all of India, or narrowed to one `city` or one `practiceArea`. Pages are followed automatically up to your `maxItems`. Turn on `enrichProfiles` to also fetch each lawyer's full profile.
2. **`profile`** — full detail for specific lawyer pages, by address or bare slug.
3. **`reference`** — the live list of cities and practice areas you can pass to `directory`.

## Input

**Every lawyer in Delhi:**

```json
{
  "mode": "directory",
  "city": "delhi",
  "maxItems": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Divorce lawyers nationwide, with full profiles:**

```json
{
  "mode": "directory",
  "practiceArea": "divorce",
  "enrichProfiles": true,
  "maxItems": 60,
  "maxConcurrency": 4
}
```

**One profile:**

```json
{
  "mode": "profile",
  "profileUrl": "https://lawrato.com/advocate-sunil-kumar-bakshi"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `directory`, `profile`, or `reference`. |
| `city` | string | `directory`: one of the 16 cities, or blank for all India. |
| `practiceArea` | string | `directory`: one of the 30 practice areas. If both `city` and `practiceArea` are set, the city wins (they are separate listings upstream). |
| `enrichProfiles` | boolean | `directory`: also fetch each listed lawyer's full profile. |
| `profileUrl` / `profileUrls` | string / array | `profile`: profile address or bare slug. |
| `maxItems` | integer | `directory`: max lawyers to list (20 per page, followed automatically). |
| `maxConcurrency` | integer | How many profiles to fetch in parallel (default 4). |
| `proxyConfiguration` | object | Apify Proxy settings; Residential on by default. |

## Output

**`directory` mode** — real output:

```json
{
  "_input": "area:divorce",
  "_source": "S1-html",
  "_scrapedAt": "2026-09-08T06:34:22Z",
  "recordType": "LAWYER_CARD",
  "name": "Advocate Madhuri Bakshi",
  "profileUrl": "https://lawrato.com/advocate-madhuri-bakshi",
  "slug": "advocate-madhuri-bakshi",
  "rating": 4.8,
  "ratingCount": 25,
  "ratingCountIsMinimum": true,
  "experienceYears": 11,
  "locality": "Sector 16, Faridabad",
  "imageUrl": "https://lawrato.com/expert_images/thumb/advocate-madhuri-bakshi.jpg",
  "cardText": "Advocate Madhuri Bakshi 4.8 | 25+ user ratings Sector 16, Faridabad 11 years Experience Divorce + 3 more …",
  "_listingScope": "area:divorce"
}
```

**`profile` mode** — real output, arrays truncated:

```json
{
  "recordType": "LAWYER_PROFILE",
  "name": "Advocate Sunil Kumar Bakshi",
  "profileUrl": "https://lawrato.com/advocate-sunil-kumar-bakshi",
  "isVerified": true,
  "rating": 4.9,
  "ratingCount": 100,
  "city": "Faridabad",
  "experienceYears": 39,
  "languages": ["English", "Hindi", "Punjabi"],
  "practiceAreas": [
    "Family Law",
    "Divorce, Family, Wills / Trusts, Child Custody, Domestic Violence, Succession Certificate, Court Marriage, Dowry Case",
    "… 14 more"
  ],
  "specializations": [
    "File for Divorce",
    "Reply / Send Legal Notice for Divorce",
    "Contest / Appeal in Divorce Case",
    "… more"
  ],
  "courts": ["Delhi High Court", "District Court, Faridabad", "… 4 more"],
  "barCouncil": "Bar Council of Punjab and Haryana",
  "enrolledYear": 1987,
  "answeredQuestions": 25
}
```

| Field | Type | Description |
|---|---|---|
| `recordType` | string | `LAWYER_CARD`, `LAWYER_PROFILE`, `CITY`, or `PRACTICE_AREA`. |
| `name` | string | Lawyer's name as published. |
| `profileUrl` | string | Public profile address. |
| `rating` | number | Average user rating out of 5. |
| `ratingCount` | integer | Number of user ratings — a floor when `ratingCountIsMinimum` is true. |
| `experienceYears` | integer | Years in practice. |
| `locality` / `city` | string | Neighbourhood + city (listing) / city (profile). |
| `isVerified` | boolean | Whether the directory marks the lawyer verified. |
| `languages` | array | Languages spoken. |
| `practiceAreas` | array | Practice area groups with their skill lists. |
| `specializations` | array | Specific services offered. |
| `courts` | array | Courts the lawyer appears before. |
| `barCouncil` / `enrolledYear` | string / integer | Bar council of enrolment and year. |
| `answeredQuestions` | integer | Public Q&A answers. |
| `_error` / `_errorDetail` | string | Present only when a page could not be fetched. |

## Notes & limits

- **Listing pages hold 20 lawyers.** `maxItems` decides how many pages are walked; the run stops early when a page comes back short.
- **City and practice area cannot be combined** — the source has no combined listing. Run one axis, or run twice.
- **Rating counts are buckets.** "100+ user ratings" is published instead of an exact figure, so `ratingCount` is a minimum whenever `ratingCountIsMinimum` is true.
- **Phone numbers are not published on the public pages** — the directory routes contact through its own call/chat buttons, so no phone field is emitted rather than a fabricated one.
- Contact details that do appear are business contact information for practising professionals, published by the directory itself.
