# Nigeria Government Tenders Scraper

Extracts public tender, award, and contract records from Nigeria's official
Open Contracting Portal (NOCOPO), run by the Bureau of Public Procurement
(BPP) under the Public Procurement Act, 2007.

## Why use this actor

- No account, login, or API key required — every record here is public data.
- Full lifecycle detail in one record: procurement planning, tender,
  award (with winning supplier and value), and contract stages, all under
  one stable Open Contracting ID (OCID).
- Browse by keyword (project title, procuring entity/buyer name) or fetch
  specific records you already have the OCID for.
- Stable, structured OCDS (Open Contracting Data Standard) JSON output
  ready for spreadsheets, databases, or reporting pipelines.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## How it works

1. Choose **List** mode to browse NOCOPO's public Published Records table,
   newest first, optionally filtered by a keyword — or **Detail** mode to
   fetch one or more specific records you already know the OCID for.
2. The actor pulls each record from NOCOPO's own listing and OCDS export
   endpoints — the same data that powers the portal's public "Open Data"
   page.
3. Every OCDS release NOCOPO publishes for a record (planning, tender,
   award, contract, implementation) is included in the output, plus a
   handful of summary fields for quick reading.
4. Automatic retries handle temporary hiccups on NOCOPO's end, so you don't
   have to babysit failed requests.

## Input

**List mode** — browse recent records:

```json
{
  "mode": "list",
  "searchQuery": "",
  "maxResults": 25,
  "fetchDetail": false,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `searchQuery` | string | Optional keyword filter (matches project title, procuring entity/buyer name, etc.). Leave blank to browse everything, newest first. |
| `maxResults` | integer | Caps how many records this run returns. |
| `fetchDetail` | boolean | When `true`, enriches each list row with the full OCDS release history (one extra request per row — slower). |
| `proxyConfiguration` | object | Apify Proxy settings (Residential recommended). |

**Detail mode** — fetch specific records by OCID:

```json
{
  "mode": "detail",
  "ocid": "ocds-gyl66f-215050001-000418",
  "ocids": [],
  "maxConcurrency": 2,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `ocid` | string | A single record's OCID (find one from a "list" mode run's `ocid` field). |
| `ocids` | array | Multiple record OCIDs to fetch in one run. |
| `maxConcurrency` | integer | How many records to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run:

```json
{
  "_input": "list",
  "_source": "S1-published-record-handler",
  "_scrapedAt": "2026-08-27T06:26:20Z",
  "id": 205731,
  "ocid": "ocds-gyl66f-215050001-000418",
  "procuringEntity": "NIGERIA STORED PRODUCTS RESEARCH, ILORIN",
  "projectTitle": "PROVISION OF LAPTOPS AND DESKTOP COMPUTERS, AND ACCESSORIES FOR NSPRI HEADQUARTERS AND  ZONAL OFFICES",
  "datePublished": "2026-08-21T12:59:55.073",
  "packageNumber": "NSPRI2023050",
  "lotNumber": "LOT BQ7",
  "budgetYear": "2025"
}
```

Real sample from a **detail** run (`ocds-gyl66f-521049001-00065`, a
completed hospital medical-gas-plant contract — truncated, the full record
also includes every OCDS release event with parties, milestones, and item
lists):

```json
{
  "_input": "ocds-gyl66f-521049001-00065",
  "_source": "S1-ocdsjson-detail",
  "_scrapedAt": "2026-08-27T06:27:43Z",
  "tenderId": "1",
  "tenderTitle": "Invitation to Tender for Construction of Medical Gas Plant",
  "tenderStatus": "complete",
  "procurementMethod": "open",
  "buyerName": "NATIONAL HOSPITAL",
  "budgetAmount": 10606467.0,
  "budgetCurrency": "NGN",
  "tags": ["award", "contract", "implementation", "planning", "tender"],
  "awardsCount": 1,
  "contractsCount": 1,
  "totalAwardAmount": 129453710.3,
  "awardCurrency": "NGN",
  "latestReleaseDate": "2021-05-03T22:44:00Z",
  "ocid": "ocds-gyl66f-521049001-00065",
  "releases": [
    { "id": "2", "date": "2021-05-03T22:44:00Z", "tag": ["planning", "tender", "award", "contract", "implementation"] }
    // ... full release object, with tender items, parties, awards (with winning supplier), and contract period
  ],
  "publisher": { "name": "The Bureau of Public Procurement", "scheme": "NG-BPP", "uid": "BPP-01" },
  "license": "http://nocopo.bpp.gov.ng/license",
  "publicationPolicy": "http://nocopo.bpp.gov.ng/policy"
}
```

| Field | Type | Description |
|---|---|---|
| `ocid` | string | Stable ID for this procurement process, unchanged from planning through tender, award, and contract. |
| `procuringEntity` / `buyerName` | string | The government Ministry/Department/Agency (MDA) running this procurement. |
| `projectTitle` / `tenderTitle` | string | The project or tender's title. |
| `tenderStatus` / `procurementMethod` | string | e.g. `complete`; `open`, `limited`, `direct`. |
| `budgetAmount` / `budgetCurrency` | number / string | The planning-stage budget, when present. |
| `awardsCount` / `contractsCount` | integer | How many award/contract entries exist on this record. |
| `totalAwardAmount` / `awardCurrency` | number / string | Combined award value and its currency (NGN). |
| `tags` | array | Union of OCDS stage tags seen (`planning`, `tender`, `award`, `contract`, `implementation`). |
| `releases` | array | Every upstream OCDS release event for this OCID, verbatim — line items, parties, awards, contract terms. |
| `_error` | string | Present only when a record couldn't be retrieved (`not_found` for an unknown OCID). |

A list row fetched with `fetchDetail: true` has the same additional fields
as a detail record, merged onto it.

## Notes

- List mode returns however many records genuinely match your search —
  fewer than `maxResults` simply means fewer records currently exist for
  that filter; nothing is padded.
- `budgetAmount`/`totalAwardAmount`/etc. are this actor's own summary fold
  across the raw `releases` array (NOCOPO's API has no server-side merged
  "compiled record" view) — the full unmodified `releases` array is always
  included too, so nothing is lost.
- For heavier usage, Residential proxies are recommended (set by default).

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ghana
(GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP), Papua New Guinea
(NPC), Sierra Leone (NPPA), Nepal (Bolpatra), Eswatini (ESPPRA), Rwanda
(Umucyo), Namibia (CPBN), Trinidad & Tobago (ProcureTT), Botswana (ministry
sites), Malawi (MANEPS/PPDA), and Tanzania (NeST).
