# Indonesia Researcher Index Scraper (SINTA)

Extract researcher and institution records from **SINTA** — Indonesia's national Science and Technology Index, run by the Ministry of Higher Education, Science and Technology. No account, login, or API key needed.

## Why use this actor

- **335,000+ researchers and 5,500+ institutions** in one structured dataset
- **The national scores you cannot get anywhere else** — SINTA Score Overall and 3-year, plus each researcher's affiliation score. These are Indonesia's own ranking metrics, not derived from Google Scholar
- **Three citation sources side by side** — Scopus, Google Scholar and Web of Science article counts, citations, cited documents, H-index, i10-index and G-index on a single record
- **Joinable identifiers** — every researcher carries a SINTA ID, their affiliation ID, and their **Google Scholar user ID**, so records link cleanly to Scholar and to institution records
- **Affiliation and department attached** to each researcher — useful for university benchmarking, recruitment and research-collaboration mapping
- **Honest counters** — every record reports how many records exist upstream for your scope, so you always know what a capped run left behind
- Stable JSON output with automatic retries — no scrapers or browsers to babysit

## How it works

Pick a `mode`:

1. **`authors`** — walk or search the national researcher index (ranked by SINTA score). Turn on `enrichProfiles` to also fetch each researcher's full profile.
2. **`author`** — a full researcher profile by SINTA ID, including the complete publication-metrics table.
3. **`affiliations`** — the institution index with aggregate scores.

## Input

**Search researchers by name:**

```json
{
  "mode": "authors",
  "query": "zainul",
  "maxItems": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Top 500 researchers nationally, with full metrics:**

```json
{
  "mode": "authors",
  "maxItems": 500,
  "enrichProfiles": true,
  "maxConcurrency": 4
}
```

**One researcher:**

```json
{
  "mode": "author",
  "sintaId": "5980682"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `authors`, `author`, or `affiliations`. |
| `query` | string | `authors`: free-text name search. Blank walks the whole index. |
| `enrichProfiles` | boolean | Also fetch each listed researcher's full profile. |
| `sintaId` / `sintaIds` | string / array | `author` mode: numeric ID or profile address. |
| `maxItems` | integer | Records to collect (10 per page, followed automatically). |
| `maxConcurrency` | integer | Profiles fetched in parallel (default 4). |
| `proxyConfiguration` | object | Apify Proxy settings; Residential on by default. |

## Output

**`authors` mode** — real output:

```json
{
  "_input": "authors:*",
  "_source": "S1-html",
  "_scrapedAt": "2026-09-08T07:03:51Z",
  "recordType": "AUTHOR_CARD",
  "sintaId": "5980682",
  "name": "RAHADIAN ZAINUL",
  "profileUrl": "https://sinta.kemdiktisaintek.go.id/authors/profile/5980682",
  "googleScholarId": "1sohgHgAAAAJ",
  "affiliation": "Universitas Negeri Padang",
  "affiliationId": "497",
  "department": "Pendidikan Kimia (S2)",
  "subjects": ["Chemistry", "Bioinformatics", "Computational Chemistry", "Information Technology", "Technology in Education"],
  "sintaScoreOverall": 12748,
  "sintaScore3Yr": 2716,
  "scopusHIndex": 26,
  "wosHIndex": 13,
  "googleHIndex": 0,
  "_totalRecordsAvailable": 335592
}
```

**`author` mode** — real output, publication table truncated:

```json
{
  "recordType": "AUTHOR_PROFILE",
  "sintaId": "5980682",
  "name": "RAHADIAN ZAINUL",
  "affiliation": "Universitas Negeri Padang",
  "department": "S2 - Pendidikan Kimia",
  "sintaScoreOverall": 12748,
  "sintaScore3Yr": 2716,
  "affilScore": 16008,
  "affilScore3Yr": 3942,
  "publications": {
    "Scopus Article": 256,
    "Scopus Citation": 2505,
    "Scopus Cited Document": 223,
    "Scopus H-Index": 26,
    "Scopus i10-Index": 77,
    "WOS Article": 104,
    "WOS Citation": 661,
    "WOS H-Index": 13,
    "GScholar Article": 0
  }
}
```

**`affiliations` mode** — real output:

```json
{
  "recordType": "AFFILIATION",
  "affiliationId": "380",
  "name": "Universitas Airlangga",
  "profileUrl": "https://sinta.kemdiktisaintek.go.id/affiliations/profile/380",
  "sintaScoreOverall": 3624707,
  "sintaScore3Yr": 1334044,
  "metaText": "Universitas Airlangga UNAIR KOTA SURABAYA - JAWA TIMUR, ID ID : 380 | CODE : 001004 194 Department 2,240 Authors",
  "_totalRecordsAvailable": 5567
}
```

| Field | Type | Description |
|---|---|---|
| `recordType` | string | `AUTHOR_CARD`, `AUTHOR_PROFILE`, or `AFFILIATION`. |
| `sintaId` | string | National researcher ID. |
| `name` | string | Researcher or institution name. |
| `googleScholarId` | string | Google Scholar user ID — join key to Scholar. |
| `affiliation` / `affiliationId` / `department` | string | Institution, its ID, and department. |
| `subjects` | array | Declared subject areas. |
| `sintaScoreOverall` / `sintaScore3Yr` | integer | National scores. |
| `affilScore` / `affilScore3Yr` | integer | Contribution to the institution's score. |
| `scopusHIndex` / `wosHIndex` / `googleHIndex` | integer | H-index per source (listing rows). |
| `publications` | object | Full metrics table per source (profile records). |
| `metaText` | string | Institution abbreviation, location, code, department and author counts. |
| `_totalRecordsAvailable` | integer | How many records exist upstream for this scope. |
| `_error` / `_errorDetail` | string | Present only on failures. |

## Notes & limits

- **Numbers use Indonesian formatting upstream** (`12.748` means 12,748). They are converted to real integers in the output, so `sintaScoreOverall` is `12748` — no silent decimal mangling.
- **Listing pages hold 10 records.** Walking the full index means 33,560 pages, so set `maxItems` deliberately; the run always reports the true upstream total.
- **The site's own sort control does not work over a plain request**, so it is not offered as an input rather than shipped as a knob that quietly does nothing. The default order is by SINTA Score 3Yr.
- **Google Scholar H-index is often 0** for researchers whose Scholar profile is not linked; Scopus figures are the more complete series.
- All data is published openly by the ministry for public consultation.
