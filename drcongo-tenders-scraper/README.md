# DR Congo Government Tenders Scraper (SIGMAP / ARMP)

Scrapes the Democratic Republic of Congo's official public procurement notices from SIGMAP (Système Intégré de Gestion des Marchés Publics), the e-procurement platform run by ARMP (Autorité de Régulation des Marchés Publics), DRC's public procurement regulator. No account or login needed.

## Why use this actor

- Pulls from DRC's real, official government procurement platform — not a third-party tender-alert aggregator
- Covers every publication type the platform itself defines: procurement plans, calls for tenders, expressions of interest, non-objection notices, special authorizations, approval decisions, award notices, cancellations, addenda, and more
- One run can crawl every publication type in a single pass
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick which publication type to browse, or leave it on "All types" to crawl everything in one run.
2. The actor opens that listing on the official platform and reads every publication card shown there — contracting authority, reference number, category, publication date, and a direct link to the official document.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries or navigate the site yourself — the actor handles all of it.

## Input

**Crawl every publication type (default):**
```json
{
  "listType": "all",
  "maxResults": 200,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Browse just one publication type:**
```json
{
  "listType": "procurement_plan",
  "maxResults": 200,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"all"` (default) — crawl every publication type in one run. Or one specific type: `"procurement_plan"`, `"call_for_tenders"`, `"expression_of_interest"`, `"non_objection_notice"`, `"special_authorization"`, `"approval_decision"`, `"levy_certificate"`, plus the postponement/cancellation/addenda/unsuccessful-bid/provisional-award/final-award/contract-termination variant of each tender or expression-of-interest lifecycle stage (see the dropdown in Apify Console for the full list). |
| `maxResults` | integer | Max records returned in total. Default 200, max 2000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "all", "maxResults": 200}` (run on 2026-08-27 — this is genuinely every publication on the platform at the time, spread across 2 of the 22 publication types; the other 20 types had nothing published yet):

```json
[
  {
    "_input": "list:procurement_plan",
    "_source": "S1-listing",
    "_scrapedAt": "2026-08-27T07:18:03Z",
    "recordType": "TENDER_LIST",
    "listType": "procurement_plan",
    "listGroup": "PPM",
    "categoryCode": "MF",
    "categoryLabel": "Marché de fournitures",
    "authority": "MINISTERE DU BUDGET",
    "reference": "PPM/MIN.BUDGET/MF/2026/00001",
    "description": "MINISTERE DU BUDGET - PPM/MIN.BUDGET/MF/2026/00001",
    "publishedAt": "24/07/2026",
    "pdfUrl": "https://marchepublic.cd/portail/rest/files/publication/flljj_1786127400136.pdf",
    "detailsAvailable": false
  },
  {
    "_input": "list:non_objection_notice",
    "_source": "S1-listing",
    "_scrapedAt": "2026-08-27T07:18:15Z",
    "recordType": "TENDER_LIST",
    "listType": "non_objection_notice",
    "listGroup": "ANO_AS",
    "categoryCode": "MF",
    "categoryLabel": "Marché de fournitures",
    "authority": "MINISTERE DU BUDGET",
    "reference": "N°0666/DGCMP/DG/DCP/D3/JMZ/202 ...",
    "description": "ANO PPM",
    "publishedAt": "24/07/2026",
    "pdfUrl": "https://marchepublic.cd/portail/rest/files/publication/xhgpn_1786127400034.pdf",
    "detailsAvailable": false
  }
]
```
*(... 2 more records — same shape, one more `procurement_plan` and one more `non_objection_notice`)*

| Field | Description |
|---|---|
| `_input` | `"list:<listType>"` this record (or error) came from. |
| `_source` | Always `S1-listing`, or `"none"` on error. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on failed records. |
| `recordType` | Always `TENDER_LIST`. |
| `listType` / `listGroup` | Which publication type this came from, and its top-level group (PPM, AAO, AMI, ANO_AS, APPROBATION, ATTESTATION_REDEVANCE). |
| `categoryCode` / `categoryLabel` | The platform's own procurement-category code (e.g. `MF` goods, `MT` works) and its label. |
| `authority` | The government body that issued this publication. |
| `reference` | The publication's own reference/dossier number. |
| `description` | Short description shown on the platform. |
| `publishedAt` | Publication date, as shown by the platform (dd/mm/yyyy). |
| `pdfUrl` | Direct link to download the official document. |
| `detailsAvailable` | Whether the platform currently exposes a richer detail view for this record (`false` for everything published so far). |

## Notes

- The platform is genuinely new and lightly used at the time of writing — only 4 publications existed across all 22 publication types combined. Re-run periodically as more government agencies start publishing through it.
- Every record's own "Details" button was inactive at recon time, so listing cards (with their document link) are the richest data currently available — see `CRAWLING_METHOD.md` for the full technical writeup.
