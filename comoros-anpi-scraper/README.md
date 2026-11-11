# Comoros ANPI Business Registry Scraper

Search or browse Comoros' official public business directory — run by ANPI (Agence Nationale pour la Promotion des Investissements), the country's national investment promotion agency — and get every company record on file: name, island, registration year, headquarters, legal form, and more.

## Why use this actor

- No account, login, or API key needed — the directory is open to the public
- Search by company name (even a partial one), or browse by island, year, city, sector, or RCCM number
- Combine filters, or leave everything blank to pull the entire national directory
- Stable JSON output suitable for pipelines, spreadsheets, or market-research workflows
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor a company name to search for (or leave it blank and use the island/year/city filters instead — or leave everything blank to list every company on file).
2. The actor queries the official directory and collects every matching record, paging through results automatically.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to know the exact legal name, and you don't need to manage retries or pagination — the actor handles all of that.

## Input

```json
{
  "query": "SARL",
  "island": "any",
  "sector": "any",
  "maxResultsPerQuery": 200,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company name (or partial name) to search for. Leave blank to browse using only the filters below. |
| `queries` | array | Multiple name searches to run in one job. |
| `island` | string | Restrict results to one island: `any` (default), `grande_comore`, `anjouan`, `moheli`. |
| `year` | string | Filter by registration year on file (e.g. `2024`). |
| `city` | string | Filter by a text match against the registered headquarters/address (e.g. `Moroni`). |
| `sector` | string | Restrict results to one business sector. As of this writing, ANPI's own directory has this field empty for every company on file, so any value other than `any` currently returns zero results — kept here for when ANPI populates it. |
| `rccm` | string | Filter by RCCM (Registre du Commerce et du Crédit Mobilier) number. As of this writing, this field is empty for every company on file, so any non-blank value currently returns zero results — kept here for when ANPI populates it. |
| `maxResultsPerQuery` | integer | Maximum matches returned per search/browse job. Default 200, max 6400. |
| `maxConcurrency` | integer | How many jobs/pages to have in flight at once. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per matched company. This is real output for a search on `"SARL"` (2,786 matches on file; showing the first record):

```json
{
  "_input": "SARL",
  "_source": "S1-anpi-rest",
  "_scrapedAt": "2026-08-27T01:47:46Z",
  "id": "3331",
  "nom": "\"BECIP2D\" SARL",
  "rccm": "",
  "ile": "grande_comore",
  "secteur": "",
  "annee": "2020",
  "siege": "Foumbouni",
  "ville": "",
  "dirigeant": "",
  "capital": "",
  "forme_juridique": "SARL",
  "description": null,
  "date_creation": "2026-03-14 08:03:46",
  "date_maj": "2026-03-14 08:03:46"
}
```

A handful more matches from the same search, for context:

```json
[
  { "nom": "\"BERC\" SARL", "ile": "grande_comore", "annee": "2020", "siege": "Moroni Hamramba" },
  { "nom": "2 A SOCIETIES SARL", "ile": "grande_comore", "annee": "2022", "siege": "OUZIOINI MBADJINI" },
  { "nom": "2I COM CONSTRUCTION SARL", "ile": "grande_comore", "annee": "2023", "siege": "Founga" },
  { "nom": "2M CONSULTING SARLU", "ile": "grande_comore", "annee": "2024", "siege": "moroni sahara" }
]
```

| Field | Description |
|---|---|
| `_input` | The search term you gave, or a description of the filters used, or `"(all companies)"` for an unfiltered browse. |
| `_source` | `S1-anpi-rest` for a successful record, `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `id` | ANPI's internal record ID. |
| `nom` | Registered company name. |
| `ile` | Island: `grande_comore`, `anjouan`, or `moheli`. |
| `annee` | Registration year on file. |
| `siege` | Registered headquarters/address, free text. |
| `forme_juridique` | Legal form, e.g. `SARL`, `SARLU`, `EI`, `SAS`, `PP`. |
| `rccm` / `secteur` / `ville` / `dirigeant` / `capital` | Present in every record's schema, but empty for every company on file as of this writing — this is a gap in ANPI's own data entry, not a scraping gap. |
| `description` | Free-text activity description, where present (usually `null`). |
| `date_creation` / `date_maj` | When ANPI's own database record was created/last updated (not the company's registration date — see `annee` for that). |

A record with `_error` instead of company fields means that job didn't produce a usable result: `"no_results"` when the search/filters matched nothing, or `"blocked_or_transient"` for a temporary network issue.

## A note on data completeness

ANPI's directory currently holds **6,376 companies**, split roughly 4,725 in Grande Comore, 1,194 in Anjouan, and 452 in Mohéli. Every record reliably has a name, island, registration year, headquarters text, and legal form. Fields like RCCM number, sector, city, manager name, and share capital exist in the schema but are not yet filled in for any company — this actor returns them as-is (empty) rather than guessing, so your dataset accurately reflects what's publicly on file today.
