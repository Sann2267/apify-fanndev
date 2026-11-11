# Malawi CRIPC Business Registry Scraper

Search Malawi's official company and business register — run by CRIPC, the
Companies, Registrations and Intellectual Property Centre (successor to the
Registrar General's Department) — by company/business name or by an
individual owner's name, and get back the public registry record for every
match.

## Why use this actor

- No account, login, or API key needed — the register's search is open to the public
- Search by company/business name (even a partial one), or by an individual owner's name
- Covers both incorporated companies (`COY-` registration numbers) and registered business names/sole traders (`BRN-` registration numbers)
- For individual-owner searches, optionally pulls every business each person is registered against
- Stable JSON output suitable for pipelines, spreadsheets, or KYC/compliance workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more names to search for, and pick a search type: `entity` (companies/business names) or `individual` (owners/proprietors).
2. The actor searches CRIPC's public register and collects every matching result, paging through automatically.
3. For `individual` searches, it also fetches each matched owner's public detail page (name, ID type, and every business they own) unless you turn that off.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "queries": ["Limited", "Stanbic"],
  "searchType": "entity",
  "includeOwnerDetails": true,
  "maxResultsPerQuery": 20,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company/business name (or partial name), or a person's name when `searchType` is `individual`. |
| `queries` | array | Multiple names to search for in one run. |
| `searchType` | string | `entity` (default) searches companies/business names. `individual` searches registered owners. |
| `includeOwnerDetails` | boolean | Only applies to `individual` searches. When on (default), fetches each matched owner's detail page and includes their ID type and every business they own. |
| `maxResultsPerQuery` | integer | Maximum matches returned per query. Default 20, max 500. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Entity search** — one record per matched company/business name. Real output captured from a live run for the query `"Limited"`:

```json
{
  "_input": "Limited",
  "_source": "S1-html-search",
  "_scrapedAt": "2026-08-26T19:24:09Z",
  "searchType": "entity",
  "registrationNumber": "COY-QDUKYGD",
  "name": "JISA CONSTRUCTION LIMITED AND NDABO CONSTRUCTION LIMITED JOINT VENTURE LIMITED",
  "registeredDate": "2024-11-25",
  "status": "active"
}
```

**Individual search** (with `includeOwnerDetails` on) — one record per matched owner, including every business they're registered against. Real output for the query `"John"`:

```json
{
  "_input": "John",
  "_source": "S1-html-search+owner-detail",
  "_scrapedAt": "2026-08-26T19:24:19Z",
  "searchType": "individual",
  "name": "JOHN  PETER",
  "status": "active",
  "ownerId": "84f31aed-02dc-406c-86ab-b907cf0614e6",
  "ownerDetailUrl": "https://mbrs.gov.mw/search/84f31aed-02dc-406c-86ab-b907cf0614e6?type=owner",
  "ownerIdType": "citizen",
  "businesses": [
    {
      "registrationNumber": "BRN-EGSANRE",
      "name": "MAPANGA BUSINESS TRAINING AND INFORMATION CENTER",
      "registeredDate": "2025-11-10",
      "status": "active",
      "ownerType": "Proprietor"
    },
    {
      "registrationNumber": "BRN-R6SY6NW",
      "name": "EVERLIGHT ACADAMY",
      "registeredDate": "2026-01-28",
      "status": "active",
      "ownerType": "Proprietor"
    }
  ]
}
```

| Field | Description |
|---|---|
| `_input` | The query you requested, for traceability. |
| `_source` | `S1-html-search` for a plain search-result row, `S1-html-search+owner-detail` when owner-detail enrichment was applied, or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `searchType` | `entity` or `individual`, matching your input. |
| `registrationNumber` | CRIPC's registration number — `COY-` for incorporated companies, `BRN-` for registered business names/sole traders. |
| `name` | Registered company/business name (entity records), or the owner's own name (individual records). |
| `registeredDate` | ISO date the entity was registered, where shown. |
| `status` | Current register status, e.g. `active`. |
| `ownerId` / `ownerDetailUrl` | Individual records only — CRIPC's internal ID and the public detail page for that owner. |
| `ownerIdType` / `businesses` | Individual records only, present when `includeOwnerDetails` is on — the owner's ID type (e.g. `citizen`) and every business they own (each with its own `registrationNumber`, `name`, `registeredDate`, `status`, and `ownerType` such as `Proprietor`). |

A record with `_error` instead of result fields means that query didn't produce a match: `"not_found"` when the search matched nothing, or `"blocked_or_transient"` for a temporary network issue. A record with `_warning: "pagination_truncated_by_page_cap"` means a very broad query hit this actor's safety page-depth cap before `maxResultsPerQuery` was reached (more results may exist — narrow your query or accept the cap). A record with `_warning: "owner_detail_fetch_partially_failed"` means the owner-detail lookup failed for at least one matched individual in that batch — the base search fields are still included, and the affected record(s) carry `_ownerDetailError` instead of `ownerIdType`/`businesses`.

## Notes / limits

- **This actor covers CRIPC's free public search only.** Full company detail — directors, shareholders, share capital, registered office address, filing history, and certified extracts — requires logging into an MBRS account directly on CRIPC's own site, which is outside the scope of this actor (this project does not automate logins).
- For `individual` searches, the owner-detail page (name, ID type, and linked businesses) genuinely is public and requires no login — this actor uses it as its detail mode. There is no equivalent public detail page for companies/entities themselves; the search-result row (registration number, name, date, status) is the full extent of what's available for a company without an account.
- Entity search matches on literal substring of the registered name — it is not a fuzzy "similar names" search, so an unusual/short query can correctly return zero results if no registered name literally contains it.
- Only `active` status has been observed in samples pulled so far; other statuses (if any exist on the register) would pass through as-is.
