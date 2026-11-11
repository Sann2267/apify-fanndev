# Tech in Asia Scraper

Extract articles, startup and investor profiles, and job postings from [Tech in Asia](https://www.techinasia.com/) — Asia's leading technology and startup publication — as clean, structured JSON.

## Why use this actor

- **No account, no login, no API key.** Nothing to sign up for and nothing to configure.
- **Three datasets in one actor.** The newsroom (79,000+ articles), the startup and investor database (120,000+ companies with funding histories), and the job board — each addressable from the same run.
- **Funding intelligence you can filter.** Find every Series A company in Indonesia, every investor with more than $1M deployed, or every startup in a given industry — with round amounts, dates, participating investors and exit counts attached.
- **Salary data on job postings.** Pay ranges, currency, period, equity flag, required experience and skills.
- **Search that actually reaches the archive.** Full-text search across the whole article archive with category, author, article-type and date-range filters.
- **Stable, predictable JSON.** Every record carries the same small set of tracking fields, so runs drop straight into a database, spreadsheet or analytics pipeline.
- **Automatic retries** and export to JSON, CSV or Excel. Schedule it and forget it.

## How it works

1. Choose a mode — what you want to collect.
2. Fill in the handful of inputs that mode uses (a search phrase, a category slug, a country, or nothing at all).
3. Set **Maximum records** to cap the run.
4. Press **Run**. Records stream into the dataset as they are collected, so you can watch results arrive.

You don't manage scrapers, browsers, accounts or blocks — the actor handles retries and recovers on its own if the site changes how search is wired up.

## Modes

| Mode | What you get |
| --- | --- |
| `latestPosts` | The newsroom feed, newest first |
| `searchPosts` | Full-text article search with filters — **the deepest reach into the archive** |
| `categoryPosts` | Articles in one or more categories |
| `tagPosts` | Articles under one or more tags |
| `videoPosts` | Video articles |
| `postDetail` | Specific articles by URL, slug or id |
| `taxonomies` | Every category, the curated topic map, and a sample of tags |
| `trendingQuestions` | The trending-questions leaderboard with pageview counts |
| `companies` | The startup and investor database, filterable by country, funding stage, industry and amount raised |
| `companyDetail` | Full profiles for specific companies |
| `jobs` | The job board, with salaries |

## Input

### Search articles

```json
{
  "mode": "searchPosts",
  "searchQueries": ["fintech indonesia"],
  "postTypes": ["post"],
  "filterCategories": ["Fintech"],
  "publishedAfter": "2026-01-01",
  "maxItems": 200,
  "includeArticleContent": false
}
```

### Find funded startups

```json
{
  "mode": "companies",
  "companyCountries": ["Indonesia"],
  "fundingStages": ["Series A"],
  "minAmountRaised": 1000000,
  "maxItems": 500
}
```

### Sweep the whole company database

```json
{
  "mode": "companies",
  "maxItems": 20000
}
```

### Job board

```json
{
  "mode": "jobs",
  "remoteJobsOnly": true,
  "maxItems": 300
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | Which dataset to read. See the table above. |
| `maxItems` | integer | Stop after this many records. Default 200. |
| `includeArticleContent` | boolean | Adds the full article body to article records. Off by default. |
| `searchQueries` | array | One search phrase per line (`searchPosts`). Empty sweeps the archive newest-first. |
| `postTypes` | array | Filter by article type: `post`, `short`, `visual-story`. |
| `filterCategories` | array | Filter by category display name, e.g. `Fintech`. Exact spelling. |
| `filterAuthors` | array | Filter by author display name. The only way to list one writer's work. |
| `publishedAfter` / `publishedBefore` | string | Date bounds, `YYYY-MM-DD` or a unix timestamp. |
| `categorySlugs` | array | Category slugs, e.g. `fintech` (`categoryPosts`). A full category URL also works. |
| `tagSlugs` | array | Tag slugs, e.g. `indonesia` (`tagPosts`). |
| `postUrls` | array | Article URLs, slugs or numeric ids (`postDetail`). |
| `includeCategories` / `includeTags` | boolean | What the `taxonomies` mode emits. |
| `companyQuery` | string | Free-text company search. Leave empty to sweep the whole database. |
| `companyCountries` | array | Full country names as the database spells them, e.g. `Indonesia`. |
| `fundingStages` | array | `Seed`, `Series A`, `Series B`, `Series C`, `Series D`, `Pre-series A`, `Bridge`, `Debt`, `M&A`, `Early stage`, `Strategic investment`, `Unspecified Stage`. |
| `companyIndustries` | array | Industry names as the database spells them. |
| `investorsOnly` | boolean | Keep only entities flagged as investors. |
| `minAmountRaised` | integer | Minimum lifetime total raised, in USD. |
| `companySlugs` | array | Company slugs (`companyDetail`). |
| `jobQuery` | string | Free-text job search. Empty lists the whole board. |
| `remoteJobsOnly` | boolean | Remote postings only. |
| `proxyConfiguration` | object | Optional. Off by default — this source needs no proxy. |

## Output

Every record carries `_input` (what produced it), `_source` (which collection strategy answered), `_scrapedAt` (UTC timestamp) and `recordType`.

### Article (`latestPosts`, `searchPosts`, `categoryPosts`, `tagPosts`, `postDetail`)

```json
{
  "_input": "latest",
  "_source": "S1-wp-posts",
  "_scrapedAt": "2026-09-20T17:48:05Z",
  "recordType": "POST",
  "id": "1023947",
  "date_gmt": "2026-09-19T01:39:35",
  "modified_gmt": "2026-09-19T01:39:35",
  "title": "Apple Pay plans India launch with Axis Bank: sources",
  "slug": "apple-pay-plans-india-launch-axis-bank-sources",
  "status": "publish",
  "type": "short",
  "link": "https://www.techinasia.com/news/apple-pay-plans-india-launch-axis-bank-sources",
  "excerpt": "UPI handles 84% of India's digital payment volume.",
  "read_time": 1,
  "author": {
    "id": "1183040",
    "display_name": "Diya Lal",
    "author_url": "https://www.techinasia.com/profile/diya-lal",
    "is_staff": true
  },
  "categories": [{ "id": "48628", "name": "Fintech", "slug": "fintech" }],
  "tags": [{ "id": "39521", "name": "Apple Pay", "slug": "apple-pay" }, "… 3 more"],
  "companies": [],
  "featured_image": {
    "source": "https://cdn.techinasia.com/wp-content/uploads/2026/09/…",
    "attachment_meta": { "width": 2560, "height": 1762 }
  },
  "short_items": { "short_source_name": "Reuters" },
  "is_sponsored": false,
  "is_subscriber_exclusive": false,
  "comments_count": 0
}
```

| Field | Type | Description |
| --- | --- | --- |
| `title` / `slug` / `link` | string | Headline, URL slug and canonical URL. |
| `excerpt` | string | The publisher's own summary line. |
| `date_gmt` / `modified_gmt` | string | Publication and last-edit timestamps. |
| `type` | string | `post`, `short` or `visual-story`. |
| `read_time` | integer | Estimated reading minutes. |
| `author` | object | Byline: name, profile URL, avatar, staff flag. |
| `categories` / `tags` | array | Taxonomy objects with id, name and slug. |
| `companies` | array | Companies the newsroom linked to this article. |
| `featured_image` | object | Image URL plus dimensions and derived sizes. |
| `is_sponsored` | boolean | True for paid placement; `sponsor` carries the advertiser. |
| `is_subscriber_exclusive` | boolean | True when the article sits behind the subscription. |
| `content` | string | Full article HTML. Only when `includeArticleContent` is on. |

### Company (`companies`, `companyDetail`)

```json
{
  "_input": "filtered-companies",
  "_source": "S2-algolia-companies",
  "_scrapedAt": "2026-09-20T17:48:05Z",
  "recordType": "COMPANY",
  "name": "Floq",
  "entity_slug": "floq",
  "description": "Floq is a licensed digital asset exchange built with ease of use, a community-first approach, and trust at its core.",
  "date_founded": "2025-05-01",
  "employee_count": "51 - 200",
  "avatar": "https://cdn.techinasia.com/data/images/CJ9bhKvQoVOU5zXDGqb6UhduSMA5OMSz5YJYx1w7.jpg",
  "entity_locations": [
    { "city_name": "Jakarta", "country_name": "Indonesia", "type": "hq" }
  ],
  "entity_industries": [
    { "name": "Financial exchanges", "slug": "financial-exchanges", "vertical_name": "Financial tech" }
  ],
  "entity_sites": [
    { "site_name": "Website", "url": "https://floq.co.id" },
    { "site_name": "LinkedIn", "url": "https://id.linkedin.com/company/floq_id" },
    "… 1 more"
  ],
  "funding_stages": [
    {
      "amount": 11300000,
      "rounds": [
        {
          "amount": 11300000,
          "date_ended": "2026-06-04",
          "source_url": "https://www.techinasia.com/news/indonesian-crypto-platform-floq-raises-11-3m",
          "participants": [{ "investor_slug": "md-capital" }, "… 1 more"]
        }
      ]
    }
  ],
  "is_investor": false,
  "number_investments": 0,
  "number_exits": 0,
  "job_posting_count": 0,
  "claimed": 1
}
```

| Field | Type | Description |
| --- | --- | --- |
| `name` / `entity_slug` | string | Company name and the slug `companyDetail` expects. |
| `description` / `pitch` | string | Long and short company blurbs. |
| `date_founded` | string | Founding date. |
| `employee_count` | string | Headcount band. |
| `entity_locations` | array | Cities and countries, with HQ flagged. |
| `entity_industries` | array | Industry and vertical classification. |
| `entity_sites` | array | Website and social profile URLs. |
| `funding_stages` | array | Rounds with amounts, dates, source articles and participating investors. |
| `total_amount_raised` | number | Lifetime funding in USD (search results). |
| `last_funding_stage` | string | Most recent stage reached. |
| `is_investor` / `number_investments` / `number_exits` | mixed | Investor side of the record. |
| `job_posting_count` | integer | Live roles this company has on the board. |

### Job (`jobs`)

```json
{
  "_input": "remote-jobs",
  "_source": "S3-laravel-jobs",
  "_scrapedAt": "2026-09-20T17:48:05Z",
  "recordType": "JOB",
  "id": "5f889196-3a89-42d2-a329-ae0a2636f5a4",
  "status": "published",
  "title": "Business Intelligence (Remote)",
  "is_remote": true,
  "work_arrangement": "remote",
  "tz_offset_min": 7,
  "tz_offset_max": 12,
  "is_salary_visible": true,
  "salary_min": 4000000,
  "salary_max": 5000000,
  "period": "MONTHLY",
  "currency": { "currency_code": "IDR", "currency_symbol": "Rp" },
  "has_equity": false,
  "vacancy_count": 3,
  "experience_min": 0,
  "experience_max": 3,
  "published_at": "2026-09-18 10:27:25",
  "expires_at": "2026-11-17 10:27:25",
  "company": {
    "name": "Deliveree On-Demand Logistics (Southeast Asia)",
    "employee_min_count": 201,
    "employee_max_count": 500
  },
  "job_skills": [{ "name": "Recruiting" }, "… 4 more"],
  "job_type": { "name": "Full-time" },
  "position": { "name": "Human Resources" }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `title` | string | Job title. |
| `salary_min` / `salary_max` | number | Pay range — **read with `period` and `currency`**, which vary per posting. |
| `period` | string | `MONTHLY` or `YEARLY`. The range means nothing without it. |
| `is_salary_visible` | boolean | False when the employer hid the range. |
| `is_remote` / `work_arrangement` | mixed | `onsite`, `hybrid` or `remote`. |
| `tz_offset_min` / `tz_offset_max` | number | Timezone band a remote hire must sit in. |
| `has_equity` | boolean | Whether equity is offered. |
| `experience_min` / `experience_max` | integer | Years of experience wanted. |
| `company` | object | Full hiring-company profile, embedded. |
| `city` | object | City, state and country. Null for fully remote roles. |
| `job_skills` / `job_type` / `position` | array/object | Skills, contract type and job family. |
| `expires_at` | string | When the posting comes down. |

### Trending question (`trendingQuestions`)

```json
{
  "_input": "trending-questions",
  "_source": "S2-algolia-trending",
  "_scrapedAt": "2026-09-20T17:48:05Z",
  "recordType": "TRENDING_QUESTION",
  "position": 1,
  "previous_position": 2,
  "question_title": "How will NVIDIA and Intel respond to Celestial AI's optical interconnect…",
  "pageviews": 1043,
  "lookback_days": 7,
  "link": "https://www.techinasia.com/…"
}
```

### Error rows

A failed input produces a row rather than disappearing, so nothing is silently lost:

```json
{
  "_input": "grab",
  "_source": "none",
  "_scrapedAt": "2026-09-20T17:48:05Z",
  "recordType": "ERROR",
  "_error": "not_found",
  "_errorDetail": "No company at /companies/grab. The slug must match the database's entity_slug exactly."
}
```

## Notes and limits

- **Article list modes return at most 900 records each.** That is Tech in Asia's own ceiling, not a limit of this actor — the site stops serving after 30 pages, even though it reports far more available. To go deeper into the archive, use `searchPosts`, or split the work across several categories and tags.
- **Each search query returns at most 1,000 records.** Several narrow queries reach much further than one broad one — split by category, country, year or funding stage.
- **The company database has no such ceiling.** A `companies` sweep with no filters walks all 120,649 records. Filters, on the other hand, run through search and so bring the 1,000-record limit with them. Sweep unfiltered when you want everything; filter when you want precision.
- **Company slugs must match the database exactly.** `gojek` resolves; `grab` does not. Run `companies` first to find the right slug.
- **Filter values are spelling- and case-exact** — `Indonesia`, `Series A`, `Fintech`. Run `taxonomies` to see valid category names.
- **Salary figures are meaningless without `period` and `currency`.** Postings mix monthly and yearly pay across several currencies.
- **`is_subscriber_exclusive` is the field that tells you whether an article is behind the subscription.** A separate `is_paywalled` field also appears in the data, but it is true on essentially every record and does not discriminate.
- **No proxy needed.** This source has no regional or access restrictions, so proxy support is off by default. Turn it on only if a very long run starts being rate-limited.
- **Article bodies are off by default.** Tech in Asia is a subscription publication. `includeArticleContent` adds the full text when you need it — check your licence before republishing or redistributing article text.
