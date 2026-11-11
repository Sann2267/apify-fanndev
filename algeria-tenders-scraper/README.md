# Algeria Government Tenders Scraper (MDN)

Scrapes public tender notices published by Algeria's Ministry of National Defense (MDN) — public-works, hospital-equipment, and logistics tenders for military regions and affiliated public institutions. No account or login needed.

## Why this source, not BOMOP

Algeria's central procurement bulletin, BOMOP, was checked first. Its modern public portal (`bomop.anep.dz`) is currently unreachable (confirmed from three independent networks), the older legacy portal requires a paid subscription to view any content, the national e-procurement portal has been offline since 2023, and the energy-sector bulletin (BAOSEM) is also subscription-gated. This actor instead scrapes the Ministry of National Defense's own public tender-notice page — one of several Algerian ministries that publish their own notices directly and, unlike some others checked, is genuinely live and actively updated (newest notice at build time was 3 days old). See `CRAWLING_METHOD.md` for the full investigation.

## Why use this actor

- Pulls from a real, official Algerian government source — not a third-party tender-alert aggregator
- Two windows: **latest** (current rolling ~10 months, ~2,200 notices) and **archived** (older overflow window, ~2 months)
- Every notice includes the full official text plus a direct link to the official PDF
- Covers several notice types beyond plain tenders: deadline extensions, awards, cancellations, corrigenda, and formal default notices ("mise en demeure") naming contractors in breach
- No account, no API key, no CAPTCHA to solve
- Content is in French, exactly as published; every field is passed through unchanged

## How it works

1. Pick a mode: `latest` for the current rolling window, or `archived` for the older overflow window.
2. The actor fetches the matching page and returns up to the limit you set.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

**Latest notices (default):**
```json
{
  "mode": "latest",
  "maxResults": 200,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Archived (older overflow window):**
```json
{
  "mode": "archived",
  "maxResults": 200
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"latest"` (default) — current rolling window, roughly the last 10 months. `"archived"` — older overflow window, roughly 2 further months. |
| `maxResults` | integer | Caps how many notices are kept in the output. Default 200, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "latest", "maxResults": 1}`:

```json
{
  "_input": "mode:latest",
  "_source": "S1-mdn-accordion-current",
  "_scrapedAt": "2026-08-27T07:25:50Z",
  "recordType": "TENDER_NOTICE",
  "date": "2026-08-24",
  "dateRaw": "24 Août 2026",
  "noticeType": "TENDER_NOTICE",
  "reference": "158/2026/D4/T/5°RM",
  "description": "Avis d'Appel d'offre national ouvert avec exigence de capacités minimales N° 158/2026/D4/T/5°RM portant sur les TRAVAUX DE REMISE EN ETAT DE L'ECLAIRAGE EXTERIEUR, TRAVAUX DE REMISE EN ETAT DES STADES ET AIRES DE JEUX DEGRADES PAR LES INTEMPERIES. AU PROFIT DE DIFFERENTES CITES MILITAIRES DE LA CIM/OEB/5°RM.",
  "pdfUrl": "https://www.mdn.dz/site_principal/sommaire/appels/AppelsFr_24082026/Plac_Fr_1.pdf"
}
```

Real output for `{"mode": "archived", "maxResults": 1}` — a "mise en demeure" (formal default notice):

```json
{
  "_input": "mode:archived",
  "_source": "S1-mdn-accordion-archive",
  "_scrapedAt": "2026-08-27T07:26:14Z",
  "recordType": "TENDER_NOTICE",
  "date": "2026-01-29",
  "dateRaw": "29 Janvier 2026",
  "noticeType": "DEFAULT_NOTICE",
  "reference": "01",
  "description": "Mise en demeure N° 01 pour \" la société algerienne BENNACER GROUP \" titulaire du contrat n° 007/2024 du 19/12/2024, portant sur l'Acquisition de solutions de récupération de données et d'investigation numérique au profit de la direction Génerale de l'ingenierie et du management du ministere de la défense nationale.",
  "pdfUrl": "https://www.mdn.dz/site_principal/sommaire/appels/AppelsFr_29012026/Plac_Fr_1.pdf"
}
```

| Field | Description |
|---|---|
| `_input` | Which mode this record came from: `"mode:latest"` or `"mode:archived"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | Always `TENDER_NOTICE`. |
| `date` / `dateRaw` | Publication date, parsed to ISO 8601 and as originally published in French. |
| `noticeType` | Best-effort classification: `TENDER_NOTICE`, `DEADLINE_EXTENSION_NOTICE`, `AWARD_NOTICE`, `PROVISIONAL_AWARD_NOTICE`, `UNSUCCESSFUL_TENDER_NOTICE`, `CANCELLATION_NOTICE`, `CORRIGENDUM_NOTICE`, `DEFAULT_NOTICE`, `CONSULTATION_NOTICE`, or `OTHER`. |
| `reference` | Best-effort tender/notice reference number, extracted from the text. Null if not found. |
| `description` | The complete notice text as published (French) — the authoritative field. |
| `pdfUrl` | Direct link to the official notice PDF. |

## Notes

- All content is published in French by the ministry itself; field values are passed through exactly as shown on the official site.
- `noticeType` and `reference` are best-effort conveniences derived from the text — `description` always carries the full original wording regardless of whether classification succeeds.
- See `CRAWLING_METHOD.md` for the full technical writeup, including why BOMOP (Algeria's central bulletin) was ruled out and how this ministry source was chosen instead.
