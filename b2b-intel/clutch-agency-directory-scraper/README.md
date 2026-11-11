# Clutch.co Agency Directory Scraper

Pull B2B agency leads from Clutch.co with the attributes buyers actually filter on — minimum project size, hourly rate band, headcount, location, service mix with percentages, rating, review count, and the agency's own website URL — plus full profiles, client reviews, and the list of every directory page on the site.

## Why use this actor

- **No account, no login, no API key.** Point it at a category and run.
- **Lead attributes, not just names.** Every row carries min. project size, hourly rate, headcount, city/region/country, phone, and the agency's real website — the fields that decide whether a lead is worth a call.
- **Paid placement is labelled, not hidden.** Half the rows on a busy category page are sponsors. Each record says `isPaidPlacement`, `isPinnedBlock` and `isRankedResult`, so you can separate the bought slots from the actual ranking. Most tools blend them together.
- **No duplicate rows.** Clutch repeats a "Leaders Matrix" block on every page of a category. This actor recognises it and emits each agency once.
- **Service mix with percentages.** `Web Development 30%, Custom Software Development 30%, AI Agents 5%` — how an agency actually splits its work, on every row.
- **Client reviews with the four sub-scores** (quality, schedule, cost, willing to refer), plus what the project cost and how long it ran.
- **Stable JSON** suitable for a CRM, a database or a spreadsheet, with automatic retries and export to JSON/CSV/Excel.

## How it works

1. You give it a directory slug (`web-developers`, `seo-firms`) or a full Clutch.co URL, including country and city cuts like `id/web-developers` or `web-designers/lagos`.
2. It walks the listing page by page, reading every agency row.
3. It labels each row by why it is on the page — ranked result, sponsor, or a pinned block — and drops the repeats.
4. Optionally it opens profiles for the full detail, or collects the client reviews.
5. Results land in the dataset as they are found.

You do not manage scrapers, browsers, accounts or blocks.

## Modes

| Mode | What you get | Typical cost |
|---|---|---|
| `directory` | One record per agency in a category, with all lead attributes | 1 request ≈ 50 ranked agencies |
| `profile` | One agency in full: founding year, full address, service / focus / industry splits, certifications | 1 request per agency |
| `reviews` | One record per client review, with four sub-scores, project size and length | 1 request ≈ 10 reviews |
| `categories` | Every directory URL on the site (~70,000), split into country and city cuts | 2 requests ≈ 10,000 URLs |
| `reference` | A health check: is the source live and still shaped the way this actor expects | ~17 requests |

## Input

```json
{
  "mode": "directory",
  "categories": ["web-developers"],
  "maxPages": 3,
  "includePinnedRows": false,
  "includePaidPlacements": true,
  "maxItems": 0,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `directory`, `profile`, `reviews`, `categories` or `reference`. Default `directory`. |
| `categories` | array | Directory slugs or full Clutch.co URLs. `web-developers` is the global ranking, `id/web-developers` the Indonesian cut, `web-designers/lagos` the city cut. |
| `maxPages` | integer | Listing pages to walk per category. A page holds about 50 ranked agencies; `web-developers` alone runs to 1,933 pages. |
| `includePinnedRows` | boolean | Off by default. Clutch repeats a 30-row "Leaders Matrix" and a featured block on every page; turning this on adds them once per category. |
| `includePaidPlacements` | boolean | On by default. Sponsor rows are kept but flagged, so you can filter them out downstream. |
| `profileUrls` | array | Profile slugs or URLs, e.g. `cleveroad`. Required by `profile` and `reviews`. |
| `maxReviewPages` | integer | Review pages per profile, about 10 reviews each. Stops early when a page brings nothing new. |
| `categoryFilter` | string | `categories` mode — keep only URLs containing this text, e.g. `seo` or `/id/`. |
| `maxSitemapShards` | integer | `categories` mode — the index is split into 7 shards of 10,000 URLs. One is usually plenty. |
| `maxItems` | integer | Hard cap on records for the whole run. `0` means no cap. |
| `proxyConfiguration` | object | Residential by default. Cloudflare challenges direct connections from Apify datacenter IPs. |

## Output

### `directory` — one agency row

```json
{
  "recordType": "PROVIDER",
  "providerId": "29455",
  "name": "Cleveroad",
  "profileUrl": "https://clutch.co/profile/cleveroad",
  "profileSlug": "cleveroad",
  "website": "https://www.cleveroad.com/offer/?utm_source=clutch.co&utm_medium=referral&utm_campaign=web-developers",
  "websiteDomain": "cleveroad.com",
  "summary": "Cleveroad is a versatile web development company known for its proficiency in Custom Website Development and Web Application Development. With a 100% positive feedback rate, clients commend their responsive project management and high-quality code across diverse projects…",
  "rowType": "Directory",
  "positionOnPage": 44,
  "pageNumber": 1,
  "isPaidPlacement": false,
  "isPinnedBlock": false,
  "isRankedResult": true,
  "rating": 4.9,
  "reviewCount": 81,
  "isVerified": true,
  "minProjectSize": "$10,000+",
  "hourlyRate": "$25 - $49 / hr",
  "priceRange": "$25 - $49",
  "employees": "250 - 999",
  "location": "New York, NY",
  "addressLocality": "New York",
  "addressRegion": "NY",
  "addressCountry": "US",
  "postalCode": "10016",
  "streetAddress": "2 Park Avenue",
  "telephone": "+14152313721",
  "services": [
    { "service": "Web Development", "percent": 30.0 },
    { "service": "Custom Software Development", "percent": 30.0 },
    { "service": "Mobile App Development", "percent": 10.0 },
    "… 6 more"
  ],
  "categoryUrl": "https://clutch.co/web-developers",
  "totalCompaniesClaim": 96607,
  "lastPageInPager": 1933,
  "_input": "web-developers",
  "_source": "clutch-directory",
  "_scrapedAt": "2026-09-18T07:02:03Z"
}
```

| Field | Type | Description |
|---|---|---|
| `providerId` | string | Clutch's own id for the agency, stable across categories and pages. |
| `name` / `profileUrl` / `profileSlug` | string | Agency name and its Clutch profile. The slug feeds straight back into `profile` or `reviews` mode. |
| `website` / `websiteDomain` | string | The agency's real site, and the bare domain for matching against your CRM. |
| `rowType` | string | `Directory` (the ranking), `Sponsor`, `featured`, or `Leaders Matrix`. |
| `isRankedResult` | boolean | True only for rows that are part of the category's actual ranking. |
| `isPaidPlacement` | boolean | True for sponsored and featured rows. |
| `isPinnedBlock` | boolean | True for rows Clutch repeats on every page. |
| `rating` / `reviewCount` / `isVerified` | number / integer / boolean | Reputation on Clutch. |
| `minProjectSize` | string | The floor the agency accepts, e.g. `$10,000+`. |
| `hourlyRate` / `priceRange` | string | Rate band, with and without the `/ hr` suffix. |
| `employees` | string | Headcount band, e.g. `250 - 999`. |
| `location`, `addressLocality`, `addressRegion`, `addressCountry`, `postalCode`, `streetAddress`, `telephone` | string | Where the agency is and how to reach it. |
| `services` | array | Service lines with the share of work each represents. |
| `totalCompaniesClaim` / `lastPageInPager` | integer | How big the category is and how deep it goes. |

### `profile` — one agency in full

```json
{
  "recordType": "PROFILE",
  "profileUrl": "https://clutch.co/profile/cleveroad",
  "providerUuid": "6b034f73-5ac1-4f6b-a88e-20b3883e6dc7",
  "name": "Cleveroad",
  "website": "https://www.cleveroad.com",
  "description": "Cleveroad is a custom software development and IT consulting company. Since 2011 we have built 300+ web, mobile, and AI-driven products for startups, scaleups, and enterprises across Healthcare, Fintech, Logistics, Education, Sports, and Media…",
  "telephone": "+14152313721",
  "foundingDate": "2011",
  "priceRange": "$25 - $49",
  "rating": 4.9,
  "reviewCount": 81,
  "addressLocality": "New York, United States",
  "minProjectSize": "$10,000+",
  "hourlyRate": "$25 - $49 / hr",
  "employees": "250 - 999",
  "locations": "New York, NY +4",
  "yearFounded": "Founded 2011",
  "languages": "3 Languages",
  "timezones": "38 Timezones",
  "servicesOffered": ["Custom Software Development", "Web Development", "Mobile App Development", "… 6 more"],
  "serviceLines": [
    { "name": "Custom Software Development", "percent": 30.0, "categoryUrl": "https://clutch.co/developers", "isCertified": true },
    { "name": "Web Development", "percent": 30.0, "categoryUrl": "https://clutch.co/web-developers", "isCertified": true }
  ],
  "focusAreas": [
    { "name": "AI Recommendation Systems", "percent": 20.0, "group": "group_ai_focus", "groupLabel": "AI Expertise" },
    { "name": "Angular", "percent": 25.0, "group": "group_pp_fw_group", "groupLabel": "Frameworks and CMS" }
  ],
  "reviewsOnPage": 10
}
```

| Field | Type | Description |
|---|---|---|
| `providerUuid` | string | Clutch's long-form id for the agency. |
| `description` | string | The agency's own pitch. |
| `foundingDate` / `yearFounded` | string | When it started. |
| `locations`, `languages`, `timezones` | string | Coverage, as the profile states it. |
| `servicesOffered` | array | The service catalogue. |
| `serviceLines` | array | Service split with percentages and the Clutch category for each line. |
| `focusAreas` | array | Finer breakdown — frameworks, platforms, AI expertise. Each group is scored out of 100 on its own, and `groupLabel` tells you which group an entry belongs to. |
| `industries` | array | Industry split with percentages. |
| `certification`, `credentials` | string / array | Clutch verification tier and per-service certifications with their dates. |

### `reviews` — one client review

```json
{
  "recordType": "REVIEW",
  "reviewId": "94870",
  "profileSlug": "cleveroad",
  "providerName": "Cleveroad",
  "title": "Quality Management Software for Medical Device Consultants",
  "isFeatured": true,
  "rating": 5.0,
  "ratingQuality": 5.0,
  "ratingSchedule": 5.0,
  "ratingCost": 5.0,
  "ratingWillingToRefer": 5.0,
  "services": ["Custom Software Development"],
  "projectSize": "$50,000 to $199,999",
  "projectLength": "July 2020 - Ongoing",
  "quote": "\"Cleveroad is fantastic at what they do.\"",
  "datePublished": "Oct 22, 2020",
  "reviewerPosition": "Sr. Solutions Lead, Medical Device Consultants",
  "reviewerName": "Anonymous",
  "isVerifiedReviewer": true,
  "providerReviewCount": 81
}
```

| Field | Type | Description |
|---|---|---|
| `reviewId` | string | Stable id for the review. |
| `ratingQuality`, `ratingSchedule`, `ratingCost`, `ratingWillingToRefer` | number | The four sub-scores behind the headline rating. |
| `projectSize` / `projectLength` | string | What the client spent and how long the engagement ran. `Confidential` when withheld. |
| `reviewerPosition` / `reviewerName` | string | Role and company of the reviewer, as published. `Anonymous` when the client withheld it. |
| `providerReviewCount` | integer | Total reviews the profile claims, so you can check coverage. |

### `categories` — a directory URL

```json
{
  "recordType": "CATEGORY",
  "categoryUrl": "https://clutch.co/kr/web-developers/seoul",
  "path": "/kr/web-developers/seoul",
  "countryCode": "kr",
  "categorySlug": "web-developers",
  "refinements": ["seoul"],
  "depth": 3,
  "isRootCategory": false
}
```

## Notes and limits

- **Page 1 is the first page of the listing.** Clutch's own `?page=1` link actually shows page 2 — this actor works around it, so `maxPages: 3` really means the first three pages.
- **Page 1 of a busy category is mostly advertising.** `/web-developers` page 1 carries 86 rows of which only 7 are ranked results; from page 2 on it settles at about 50 ranked rows per page. Ranked rows are emitted first, so a run with `maxItems` gets the ranking rather than the sponsors.
- **The Leaders Matrix repeats.** ~30 agencies appear on every page of a category. They are off by default and deduplicated when on.
- **Reviews are paginated about 10 at a time**, and the featured review repeats on each page. Duplicates are removed automatically.
- **Filtered listing URLs are not requested.** Clutch asks crawlers not to fetch its filter URLs (`sort_by`, `hourly_rate`, `industries`, and similar). If you paste one, those parameters are dropped and the run logs it.
- Keep the Residential proxy on. Without it, cloud runs are challenged on every request and fail.

## Other actors

| Actor | What it does |
|---|---|
| `shopify-store-analyzer` | Products, themes and apps of any Shopify store |
| `ecommerce-platform-market-share-scraper` | Platform market share and store migration trends |
| `google-maps-lead-generation-scraper` | Business leads with contact details from Maps |
