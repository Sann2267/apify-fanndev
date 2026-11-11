# Suriname Government Tenders Scraper (gov.sr)

Scrapes Suriname's official government website, `gov.sr` ("Overheid van de
Republiek Suriname"), for public procurement notices: routine ministry-level
tenders across every government sector since 2022, and larger
internationally/donor-financed solicitations with full bid details. No
account or login needed.

## Why use this actor

- Pulls from Suriname's real, official government website — not a
  third-party tender-alert aggregator (several such aggregator domains, and
  one entirely non-existent "central e-procurement portal" name that
  circulates in AI search summaries, were checked and ruled out — see
  `CRAWLING_METHOD.md`)
- Two views in one actor: **Tenders** — every ministry's routine procurement
  notices, back to May 2022 — and **Notices** — larger, internationally/
  donor-financed solicitations with full bid text, deadlines, and document
  links
- Optional ministry/sector filter for the Tenders view
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline
- Content is published in Dutch (Tenders) or English (Notices), exactly as
  published by the government — every field is passed through unchanged so
  nothing gets lost in translation

## How it works

1. Pick a list type: `tenders` for the full multi-ministry archive since
   2022, or `notices` for currently-open, donor-financed solicitations with
   full bid details.
2. Optionally set a ministry/sector filter for `tenders` (e.g. "Public
   Works & Spatial Planning").
3. The actor fetches the matching results and returns up to the limit you
   set.
4. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

**Every ministry's tenders (default):**
```json
{
  "listType": "tenders",
  "maxResults": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**One ministry's tenders only:**
```json
{
  "listType": "tenders",
  "categorySlug": "openbare-werken-ruimtelijke-ordening",
  "maxResults": 50
}
```

**Donor-financed notices, full bid details:**
```json
{
  "listType": "notices",
  "maxResults": 50
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"tenders"` (default) — every ministry's routine notices since May 2022 (671+ at a time). `"notices"` — larger, internationally/donor-financed solicitations with full bid text (currently ~11 open at a time). |
| `categorySlug` | string | `tenders` only. Optional WordPress category slug to restrict to one ministry, e.g. `"openbare-werken-ruimtelijke-ordening"` (Public Works & Spatial Planning), `"landbouw-veeteelt-en-visserij"` (Agriculture, Livestock & Fisheries), `"olie-gas-en-milieu"` (Oil, Gas & Environment). Leave blank for every ministry. |
| `maxResults` | integer | Caps how many records are kept in the output. Default 100, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "tenders", "maxResults": 1}`:

```json
{
  "_input": "list:tenders",
  "_source": "S1-wp-rest-aanbestedingen-cpt",
  "_scrapedAt": "2026-08-27T16:41:11Z",
  "recordType": "TENDER",
  "id": 161545,
  "title": "Het opschonen van de hoofdlozing, het vernieuwen van de gesloten riolering en het bestraten van de wegen van het maretraiteproject in het district Wanica",
  "slug": "het-opschonen-van-de-hoofdlozing-het-vernieuwen-van-de-gesloten-riolering-en-het-bestraten-van-de-wegen-van-het-maretraiteproject-in-het-district-wanica",
  "link": "https://gov.sr/aanbestedingen/het-opschonen-van-de-hoofdlozing-het-vernieuwen-van-de-gesloten-riolering-en-het-bestraten-van-de-wegen-van-het-maretraiteproject-in-het-district-wanica/",
  "status": "publish",
  "publishedAt": "2026-08-27T14:04:54Z",
  "modifiedAt": "2026-08-27T14:04:54Z",
  "ministry": "Openbare Werken & Ruimtelijke Ordening",
  "ministrySlug": "openbare-werken-ruimtelijke-ordening",
  "ministryCategories": null,
  "categoryIds": [15]
}
```

Real output for `{"listType": "notices", "maxResults": 1}` (`contentText`
truncated here for readability — the actual field carries the full notice,
including the pre-bid meeting date, clarification/submission deadlines, and
contact email):

```json
{
  "_input": "list:notices",
  "_source": "S1-wp-rest-posts-category-aanbestedingen",
  "_scrapedAt": "2026-08-27T16:42:53Z",
  "recordType": "TENDER_NOTICE",
  "id": 161437,
  "title": "Supply of Equipment for School Renovation Works",
  "slug": "supply-of-equipment-for-school-renovation-works",
  "link": "https://gov.sr/supply-of-equipment-for-school-renovation-works/",
  "status": "publish",
  "publishedAt": "2026-08-25T11:51:33Z",
  "modifiedAt": "2026-08-25T11:51:36Z",
  "categories": ["Aanbestedingen"],
  "excerptText": "In February 2026, the Republic of Suriname issued a Social Bond to finance eligible social expenditures and priority social projects. The Ministry of Finance and Planning (Employer), for the benefit of the Ministry of Education, Science and Culture, now invites sealed bids from eligible bidders for the supply equipment for school renovation works under the Priority Social Projects Program.",
  "contentText": "Background\nIn February 2026, the Republic of Suriname issued a Social Bond to finance eligible social expenditures and priority social projects. ... Submission deadline 16 September 2026, 11:00 a.m. local time ... Email: procurement@oversightboard.gov.sr\nDownload",
  "contentHtml": "<p><strong>Background</strong></p> ... <a href=\"https://gov.sr/wp-content/uploads/2026/08/SPN_MESC_Equipment_23Aug26.pdf\">Download</a>"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:tenders"` or `"list:notices"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `TENDER` or `TENDER_NOTICE`. |
| `title` / `link` / `slug` | What is being procured, and its official gov.sr page. |
| `publishedAt` / `modifiedAt` | UTC timestamps. |
| `ministry` / `ministrySlug` | The procuring government body (`tenders` only). |
| `categories` | Category tags (`notices` only, currently always `["Aanbestedingen"]`). |
| `excerptText` / `contentText` / `contentHtml` | The notice's full bid text — background, procurement method, eligibility, deadlines, submission address — as plain text or original HTML (`notices` only). |

## Notes

- `tenders` mode can hold 600+ records across the full archive since 2022 —
  start with a small `maxResults` to preview, or use `categorySlug` to
  narrow to one ministry.
- `notices` mode reflects what's open for bidding *right now*; closed
  solicitations appear to be removed rather than archived by the
  government's own site, and this actor reports that honestly rather than
  fabricating a historical archive that doesn't exist upstream.
- All content is published exactly as the Surinamese government itself
  wrote it — Dutch for `tenders`, English for `notices` — nothing is
  translated or reworded.
- This actor respects gov.sr's `robots.txt` `Crawl-delay: 60` directive, so
  a run that needs to page through the full `tenders` archive (more than
  100 results) will take roughly one minute per 100 additional records.
- See `CRAWLING_METHOD.md` for the full technical writeup, including which
  third-party "Suriname e-procurement" names turned out not to exist.
