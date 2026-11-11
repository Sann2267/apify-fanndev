# Djibouti Government Tenders Scraper (Marches Publics)

Scrapes Djibouti's national public procurement portal for currently
listed tenders and this week's contract-award notices, including the
winning supplier and awarded amount in Djibouti Francs (DJF). No account
or login needed.

## Why use this actor

- Pulls from the government's real, official procurement portal — not a
  third-party tender-alert aggregator
- Two views in one actor: **Current tenders** and **Awards**, the latter
  including the winning supplier's name and the awarded amount
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

1. Pick a list type: `current` for what's listed right now, or `awards`
   for this week's contract-award notices.
2. The actor fetches the matching listing page and returns up to the
   limit you set.
3. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

**Currently listed tenders (default):**
```json
{
  "listType": "current",
  "maxResults": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Contract awards (supplier + amount):**
```json
{
  "listType": "awards",
  "maxResults": 100
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"current"` (default) — tenders listed on the portal's first page (~7 at a time). `"awards"` — this week's contract-award notices (~9 at a time), with supplier and amount. |
| `maxResults` | integer | Caps how many records are kept in the output. Default 100, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "current", "maxResults": 1}`:

```json
{
  "_input": "list:current",
  "_source": "S1-livewire-html-marches",
  "_scrapedAt": "2026-08-27T19:43:58Z",
  "recordType": "CURRENT_TENDER",
  "title": "Prestations pour le nettoyage, ramassage et la collecte des ordures ménagères de la nouvelle cité de 520 appartements localisés au pôle urbain de balbala Nord au PK 13",
  "detailUrl": "https://marchespublics.gouv.dj/marche/1915",
  "code": null,
  "administrationContractante": "ARULOS",
  "nature": "Services",
  "modalite": "Nationale",
  "dateParution": "N/A",
  "dateLimiteRemiseOffres": "N/A",
  "lieuExecution": "Djibouti",
  "procedure": "Demande de cotation"
}
```

Real output for `{"listType": "awards", "maxResults": 1}`:

```json
{
  "_input": "list:awards",
  "_source": "S1-html-table-attribution",
  "_scrapedAt": "2026-08-27T19:44:07Z",
  "recordType": "TENDER_AWARD",
  "designation": "Prestations pour le nettoyage, ramassage et la collecte des ordures ménagères de la nouvelle cité de 520 appartements localisés au pôle urbain de balbala Nord au PK 13",
  "procedure": "Demande de cotation",
  "projet": "Aucun Projet",
  "institution": "ARULOS",
  "supplier": "SOCIETE OSKY (Djibouti)",
  "amountDJF": "8 160 000",
  "detailUrl": "https://marchespublics.gouv.dj/marche/1915"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:current"` or `"list:awards"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `CURRENT_TENDER` or `TENDER_AWARD`. |
| `title` / `designation` | What is being procured. |
| `administrationContractante` / `institution` | The contracting government body. |
| `nature` / `modalite` / `procedure` | Procurement type, national/international/amendment status, and procedure. |
| `dateParution` / `dateLimiteRemiseOffres` | Publication date and bid deadline (`current` only — the government publishes these as `"N/A"` for most tenders at recon time). |
| `projet` | The funding project, or `"Aucun Projet"` if none (`awards` only). |
| `supplier` / `amountDJF` | The winning company and the awarded amount in Djibouti Francs (`awards` only). |
| `detailUrl` | The tender's own portal page. |

## Notes

- The portal only exposes its first page of `current` tenders (~7) to a
  plain HTTP request — deeper pagination uses a client-side interactive
  protocol this actor doesn't replicate. `awards` reflects the current
  week's award notices only, with no historical archive found on the
  site. Both are reported honestly as "what the site shows right now",
  not a fabricated full history.
- `dateParution`/`dateLimiteRemiseOffres` are frequently published as the
  literal string `"N/A"` by the government itself — passed through as-is
  rather than converted to `null`, since that's genuinely what the
  government wrote.
- Every field is passed through exactly as published (in French) — no
  translation, no reformatting.
- See `CRAWLING_METHOD.md` for the full technical writeup.
