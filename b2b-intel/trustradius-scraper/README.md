# TrustRadius Scraper: Reviews, Products, Categories & Comparisons

Extract verified B2B software reviews, product profiles, ranked category lists, alternatives and head-to-head comparisons from [TrustRadius](https://www.trustradius.com) — as clean, structured JSON.

## Why use this actor

- **Every review of a product**, not just the first page — with pros, cons, rating, the reviewer's role, department, company size and industry, and how the review was sourced (incentivized or not).
- **The full review questionnaire on request**: feature-by-feature scores, usability, return on investment, alternatives the reviewer evaluated, other software they use, their country and buying role.
- **Product intelligence in one record**: trScore, 30+ feature ratings against the category average, pricing editions, awards, competitors, aggregated pros and cons, and the install base by industry.
- **Category rankings** with filters for company size, published pricing, free options, operating system and Top Rated winners.
- **Cheap monitoring**: reviews come newest first, so "only reviews since date X" stops as soon as it reaches older ones.
- No account, no login, no API key. Export to JSON, CSV or Excel, or schedule it on Apify.

## How it works

1. Pick a mode: **Reviews**, **Product details**, **Category products**, **Alternatives**, **Compare products** or **Category tree**.
2. Paste product slugs or TrustRadius URLs (`hubspot-crm` or `https://www.trustradius.com/products/hubspot-crm/reviews`), category slugs (`crm`) or comparisons (`hubspot-crm-vs-pipedrive`).
3. Run. Each result lands in the dataset as one row, tagged with a `recordType`.
4. Inputs that don't exist come back as an `ERROR` row saying so, instead of silently disappearing.

There are no scrapers, browsers or blocks to babysit — refused pages are retried automatically.

## Input

```json
{
    "mode": "reviews",
    "products": ["hubspot-crm"],
    "maxItems": 50,
    "reviewsNewerThan": "2026-09-01",
    "includeReviewDetails": true,
    "proxyConfiguration": {"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}
}
```

```json
{
    "mode": "categoryProducts",
    "categories": ["crm"],
    "maxItems": 100,
    "companySize": "enterprise",
    "hasPricingOnly": true
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `reviews`, `products`, `categoryProducts`, `alternatives`, `compare` or `categories`. |
| `products` | array | Product slugs or URLs — for Reviews, Product details and Alternatives. |
| `categories` | array | Category slugs or URLs — for Category products. Run **Category tree** to list every slug. |
| `comparisons` | array | `product-a-vs-product-b`, `product-a, product-b`, or a comparison URL. |
| `maxItems` | integer | Reviews per product, or products per category (default 100). |
| `reviewsNewerThan` | date | Reviews: stop at the first review published before this date. |
| `includeReviewDetails` | boolean | Reviews: add the full questionnaire (one extra page per review). |
| `includePricing` | boolean | Product details: add the pricing page (price quotes from reviewers, support, deployment). Default on. |
| `companySize` | string | Category products: `any`, `small-business`, `mid-sized`, `enterprise`. |
| `topRatedOnly`, `hasPricingOnly`, `freeOptionOnly` | boolean | Category products filters. |
| `operatingSystem` | string | Category products: `any`, `windows`, `mac`, `linux`. |
| `deepPagination` | boolean | Category products: go past TrustRadius's 1,000-product listing limit (see Notes). |
| `maxConcurrency` | integer | Pages fetched in parallel (default 3). |
| `proxyConfiguration` | object | Residential proxy recommended. |

## Output

Every row has `_input`, `_source`, `_scrapedAt` and `recordType`.

### Reviews (`recordType: REVIEW`)

Real output, long text truncated:

```json
{
  "_input": "hubspot-crm",
  "recordType": "REVIEW",
  "productSlug": "hubspot-crm",
  "productName": "HubSpot CRM",
  "reviewId": "6a9acd7749470e91003cfdfc",
  "url": "https://www.trustradius.com/reviews/hubspot-crm-2026-09-04-08-53-58",
  "title": "You can't miss HubSpot if you are considering a CRM",
  "rating": 8,
  "datePublished": "2026-09-09T15:50:19.121Z",
  "source": {"trusted": true, "incentive": "TrustRadius", "source": "RaaS"},
  "reviewer": {
    "isPublic": false,
    "title": "Marketing & Sales director",
    "jobType": "Manager",
    "department": "Sales",
    "companySize": "11-50 employees",
    "yearsExperience": 3,
    "verification": {"isVerified": false, "verifiedBy": "LinkedIn"}
  },
  "verification": {"isVerified": false, "isVetted": true, "isReseller": false},
  "pros": ["Simple UI", "Integration abilities", "Easy configuration and customisation"],
  "cons": ["Pricing can be adapted to smaller companies", "Rights management can be tricky to master", "Marketing module should be more powerful in standard"],
  "answers": [
    {"question": "Use Cases and Deployment Scope", "type": "text", "text": "I used HubSpot and deployed it in my previous company as there was no CRM in place. HubSpot seemed to be the easiest and most powerful CRM amongst all the potential candidates…"},
    "… 3 more"
  ],
  "details": {
    "wordCount": 340,
    "reviewerProfile": {
      "companySize": "11-50 employees",
      "industry": "Computer Software",
      "countryCode": "FRA",
      "roles": {"user": true, "manager": true, "decisionMaker": true, "implementer": false},
      "currentExperience": "recent"
    },
    "alsoReviewedProducts": [{"slug": "freshsales", "name": "Freshsales"}],
    "details": [
      {"section": "Overall Satisfaction", "slug": "likelihood-to-recommend", "question": "Likelihood to Recommend", "type": "slider", "value": 8},
      {"section": "Overall Satisfaction", "slug": "feature-ratings", "question": "HubSpot CRM Feature Ratings", "type": "features",
       "value": [{"feature": "Customer data management / contact management", "value": 8}, {"feature": "Workflow management", "value": 8}, "… 25 more"]},
      {"section": "Overall Satisfaction", "slug": "alternatives-evaluated", "question": "Alternatives Considered", "type": "competitors", "value": ["Freshsales"]},
      "… 7 more"
    ]
  }
}
```

| Field | Description |
| --- | --- |
| `rating` | The reviewer's score out of 10. |
| `source` | How TrustRadius sourced the review — `incentive` tells you whether it was incentivized. |
| `reviewer` | Role, department, company size, industry, years of experience. Name, company, photo and LinkedIn appear **only when the reviewer published the review under their name**. |
| `pros`, `cons` | The reviewer's own bullet lists. |
| `answers` | Every question/answer shown on the review. |
| `details` | With `includeReviewDetails`: every answered question of the full questionnaire, feature ratings by name, reviewer country and buying role. |

### Product details (`recordType: PRODUCT_DETAILS`)

```json
{
  "_input": "hubspot-crm",
  "recordType": "PRODUCT_DETAILS",
  "slug": "hubspot-crm",
  "name": "HubSpot CRM",
  "rating": {"avg": 8.4, "count": 5522},
  "featureRatings": [
    {"name": "Customer data management / contact management", "score": 8.9, "count": 1661, "categoryAverage": 8.6},
    {"name": "Workflow management", "score": 8.4, "count": 1631, "categoryAverage": 8.3},
    "… 29 more"
  ],
  "industryInstallShare": {
    "totalInstalls": 41520,
    "industries": [
      {"naicsCode": "54", "naicsName": "Professional, Scientific, and Technical Services", "companyCount": 10549, "installSharePct": 25.4},
      "… 2 more"
    ]
  },
  "awards": [{"title": "Top Rated 2022", "awardType": "toprated"}, "… 28 more"],
  "prosAndCons": {"pros": ["Easy to use", "User friendly", "… 8 more"], "cons": ["Mobile app", "Email address", "… 8 more"]},
  "pricingPage": {
    "editionPricing": [{"name": "Free Forever", "price": "$0", "otherTerms": "Per Month [Unlimited Users]"}, {"name": "CRM Bundle", "price": "$50", "terms": {"period": "per month"}}],
    "freeAvailable": true,
    "trialAvailable": true,
    "support": {"channelsFree": ["Live Chat", "Forum/Community", "… 2 more"], "channelsPaid": ["Phone", "Live Chat", "… 5 more"]},
    "pricingAlternatives": [{"name": "Sugar Sell (SugarCRM)", "editionPricing": [{"name": "Essentials", "price": "$19"}, "… 3 more"]}, "… 2 more"],
    "pricingQuotes": ["… what reviewers say about the price, with the review it came from"]
  }
}
```

The record also carries `vendor`, `categories`, `competitors`, `featureGroupRatings`, `screenshots`, `faq`, `interviews` (featured reviews) and more, as TrustRadius publishes them.

### Category products (`recordType: PRODUCT`)

```json
{
  "_input": "crm",
  "recordType": "PRODUCT",
  "rank": 1,
  "categorySlug": "crm",
  "categoryName": "Customer Relationship Management (CRM)",
  "slug": "bigin-by-zoho-crm",
  "name": "Bigin by Zoho CRM",
  "url": "https://www.trustradius.com/products/bigin-by-zoho-crm",
  "vendorName": "Zoho",
  "trScore": 8.832,
  "ratingAvg": 8.8,
  "ratingCount": 285,
  "reviewCount": 167,
  "startingPrice": 9,
  "trialAvailable": true,
  "product": {"… full product object: vendor, feature ratings, pros and cons, awards, pricing editions": "…"}
}
```

With a filter set, `rank` is empty and `filterRank` holds the position in the filtered list.

### Alternatives (`recordType: ALTERNATIVE`)

```json
{
  "_input": "hubspot-crm",
  "recordType": "ALTERNATIVE",
  "forProduct": "hubspot-crm",
  "slug": "zoho-crm",
  "name": "Zoho CRM",
  "vendorName": "Zoho",
  "ratingAvg": 8.4,
  "ratingCount": 1038,
  "reviewCount": 314,
  "featureRatings": [{"name": "Customer data management / contact management", "trScore": 8.731, "count": 280}, "… 30 more"],
  "lists": {"competitors": 1}
}
```

`lists` says where the product appears: `competitors` (TrustRadius's curated list) and `alternatives_all`, `alternatives_small`, `alternatives_medium`, `alternatives_large` (alternatives per company size), with its position in each.

### Compare products (`recordType: COMPARISON`)

```json
{
  "_input": "hubspot-crm-vs-pipedrive",
  "recordType": "COMPARISON",
  "products": [
    {
      "slug": "hubspot-crm", "name": "HubSpot CRM", "avg": 8.9, "ratingsCount": 1513,
      "insights": {"buyAgain": {"yesCount": 1607, "noCount": 55}, "valuePrice": {"yesCount": 1204, "noCount": 34}},
      "pricingEditions": [{"edition": "Free Forever", "price": "$0", "terms": "Per Month [Unlimited Users]"}, {"edition": "CRM Bundle", "price": "$50", "terms": "per month"}]
    },
    {"slug": "pipedrive", "name": "Pipedrive", "avg": 7.5, "ratingsCount": 49, "pricingEditions": [{"edition": "Essential", "price": "$24", "terms": "per month per seat"}, "… 4 more"]}
  ],
  "featureGroups": [
    {
      "heading": "Sales Force Automation",
      "features": [
        {"name": "Customer data management / contact management", "cells": [{"slug": "hubspot-crm", "avg": 8.9, "isWinner": true}, {"slug": "pipedrive", "avg": 8.7, "isWinner": false}]},
        "… 8 more"
      ]
    },
    "… 9 more"
  ],
  "testimonials": ["… 25 reviewer quotes comparing the two products"]
}
```

### Category tree (`recordType: CATEGORY`)

```json
{
  "recordType": "CATEGORY",
  "slug": "crm",
  "name": "Customer Relationship Management (CRM)",
  "url": "https://www.trustradius.com/categories/crm",
  "path": ["Customer Relationship Management (CRM)"],
  "groups": ["Revenue Operations - Sales"]
}
```

946 categories at the time of writing.

## Notes and limits

- **Reviews**: no depth limit — every review of a product can be collected (HubSpot CRM: all 1,762). Ten reviews per page, newest first.
- **Review details** add one page per review and take longer; leave them off when you only need pros, cons and ratings.
- **Category lists stop at 1,000 products** on TrustRadius, and its pages overlap slightly (duplicates are removed, so a 1,000 walk yields ~890 unique products on CRM). `deepPagination` re-reads the category in its other orderings and filters and merges the results: on CRM it reached 1,060 unique products, at about six times the page requests. Use it only when you need the long tail.
- **Reviewer identity** follows what TrustRadius shows: anonymous reviews never include a name, company, photo or LinkedIn link.
- Residential proxy is recommended for large runs.
