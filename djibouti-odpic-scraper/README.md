# Djibouti ODPIC Business Registry Scraper

Search or browse Djibouti's official company and business-name register — maintained by ODPIC, the government office in charge of the Registre du Commerce et des Sociétés (RCS) — and get registration details, filing dates, file numbers, owner names, addresses, and declared capital.

## Why use this actor

- No account, login, or API key needed — the register is open to the public
- Search by company/establishment name, or by a registered owner's name (even a partial match works)
- Or skip the search entirely and just browse the newest filings on the register — handy for tracking new company registrations in Djibouti as they happen
- Filter any search (or the browse mode) to a specific registration date range
- Stable JSON output suitable for pipelines, spreadsheets, or compliance/KYC workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more company/owner names to search for — or leave the search blank to browse the most recent filings instead.
2. Optionally narrow results to a registration date range.
3. The actor pulls matching filings straight from the official register and streams them into your dataset, newest first by default.

You don't need to know the exact legal name — a partial name works too. You don't need to manage pagination or retries — the actor handles all of that.

## Input

```json
{
  "queries": ["MOHAMED", "SARL"],
  "dateFrom": "",
  "dateTo": "",
  "orderBy": "date",
  "orderDirection": "desc",
  "maxResultsPerQuery": 100,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company/establishment name (or partial name) or owner's name to search for. Leave blank (with `queries` also empty) to browse the newest filings instead. |
| `queries` | array | Multiple names to search for in one run. |
| `dateFrom` | string | Only include filings registered on or after this date (`YYYY-MM-DD`). |
| `dateTo` | string | Only include filings registered on or before this date (`YYYY-MM-DD`). |
| `orderBy` | string | Sort by `date` (default) or `title` (name). |
| `orderDirection` | string | `desc` (default, newest/Z-A first) or `asc` (oldest/A-Z first). |
| `maxResultsPerQuery` | integer | Maximum filings returned per query (or, with no query, per browse run). Default 100, max 5000. |
| `maxConcurrency` | integer | How many queries to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Name search** — one record per matching filing. This is real output for a search on `"MOHAMED"` (827 total matches on the register at time of writing), truncated to the first two:

```json
{
  "_input": "MOHAMED",
  "_source": "S1-odpic-rest",
  "_scrapedAt": "2026-08-27T01:50:04Z",
  "id": 10364314,
  "title": "ETABLISSEMENT MOHAMED TAHA SAID SARL",
  "slug": "etablissement-mohamed-taha-said-sarl",
  "link": "https://odpic.dj/publication-registre/etablissement-mohamed-taha-said-sarl/",
  "date": "2025-11-24T00:00:00",
  "file_nbr": "23979",
  "file_ser": "2025",
  "registration_date": "2025-11-24",
  "filing_date": "2025-11-24",
  "main_owner_person_nbr": "1115580",
  "person_name": "MOHAMED TAHA SAID",
  "addresses": "",
  "disclaimers": "20 000 FDJ"
},
{
  "_input": "MOHAMED",
  "_source": "S1-odpic-rest",
  "_scrapedAt": "2026-08-27T01:50:04Z",
  "id": 10364135,
  "title": "QUINCAILLERIE WAEL MOHAMED",
  "slug": "quincaillerie-wael-mohamed",
  "link": "https://odpic.dj/publication-registre/quincaillerie-wael-mohamed/",
  "date": "2025-09-07T00:00:00",
  "file_nbr": "23804",
  "file_ser": "2025",
  "registration_date": "2025-09-07",
  "filing_date": "2025-09-07",
  "main_owner_person_nbr": "1118051",
  "person_name": "WAEL MOHMAED TARECHE",
  "addresses": "",
  "disclaimers": ""
}
```

**Browse mode** (no search term) — the newest filings on the register, real output from a live run:

```json
{
  "_input": "(latest)",
  "_source": "S1-odpic-rest",
  "_scrapedAt": "2026-08-27T01:49:13Z",
  "id": 10390250,
  "title": "ETABLISSEMENT TAREK WAGDALLE",
  "slug": "etablissement-tarek-wagdalle",
  "link": "https://odpic.dj/publication-registre/etablissement-tarek-wagdalle/",
  "date": "2026-08-26T00:00:00",
  "file_nbr": "24856",
  "file_ser": "2026",
  "registration_date": "2026-08-26",
  "filing_date": "2026-08-26",
  "main_owner_person_nbr": "1121844",
  "person_name": "TAREK WAGDALLE MOHAMED",
  "addresses": "BALBALA, CHEICK MOUSSA - DJIBOUTI",
  "disclaimers": ""
}
```

| Field | Description |
|---|---|
| `_input` | The name you searched for, or `(latest)` in browse mode. |
| `_source` | `S1-odpic-rest` for every successful record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `id` | Register's internal ID for this filing. |
| `title` | The registered company/establishment name as published. |
| `link` | A direct, shareable link to the filing's public page on the register. |
| `date` | The date this filing was published (matches `registration_date`/`filing_date`). |
| `file_nbr` / `file_ser` | The official RCS file number and the year/series it belongs to. |
| `registration_date` / `filing_date` | Key dates on file for this filing. |
| `main_owner_person_nbr` | The register's internal number for the filing's main owner. |
| `person_name` | Full name of the main owner/proprietor. |
| `addresses` | Address on file, when published — often blank for sole-trader filings. |
| `disclaimers` | Free-text field that, in practice, holds the declared share capital for company filings (e.g. `"10 000 FDJ"`) — blank for many sole-trader filings. |

A record with `_error` instead of filing fields means that query didn't produce a usable result: `"not_found"` when the search (or date range) matched nothing, or `"blocked_or_transient"` for a temporary network issue.

Some filings have sparse data on file (an empty address, or no declared capital) — this reflects what the register itself publishes, not a scraping gap. The register also does not expose lookup by exact file number — only by name or date range.
