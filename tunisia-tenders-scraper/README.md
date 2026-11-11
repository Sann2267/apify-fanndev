# Tunisia Government Tenders Scraper

Extracts public tender ("Appel d'offres") listings and full detail records
from TUNEPS, Tunisia's official national e-procurement system, run by the
Haute Instance de la Commande Publique (HAICOP).

## Why use this actor

- No account, login, or API key required — every record here is public data.
- Full trilingual detail in one record: French, Arabic, and English titles
  and coded-value labels (procedure type, business kind, financing method,
  evaluation method, and more), plus the submission window, contact staff,
  and buyer registration info.
- Filter to only currently-open tenders (deadline not yet passed), sorted by
  soonest deadline first — or browse everything most-recently-published
  first.
- Optional keyword search on the tender title.
- Stable, structured JSON output ready for spreadsheets, databases, or
  reporting pipelines.

## How it works

1. Choose **List** mode to browse tenders (optionally filtered to open-only
   and/or by keyword), or **Detail** mode to fetch one or more specific
   tenders you already know the bid id for.
2. The actor pulls each record directly from TUNEPS's own public tender
   feed — the same data that powers the public "Appel d'offres" listing on
   `tuneps.tn`.
3. Every field TUNEPS publishes for that record is included in the output.
4. Automatic retries handle temporary hiccups on TUNEPS's end.

## Input

**List mode** — browse tenders:

```json
{
  "mode": "list",
  "openOnly": false,
  "keyword": "",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `openOnly` | boolean | When `true`, only tenders whose submission deadline hasn't passed, sorted soonest-deadline-first. When `false` (default), all published tenders, most-recent-first. |
| `keyword` | string | Optional case/accent-insensitive substring filter on the French tender title. |
| `maxResults` | integer | Caps how many tenders this run returns. |
| `proxyConfiguration` | object | Apify Proxy settings (Residential recommended). |

**Detail mode** — fetch specific tenders by id:

```json
{
  "mode": "detail",
  "bidId": "134251",
  "bidIds": [],
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `bidId` | string | A single tender's internal TUNEPS id (find one from a "list" mode run's `epBidMasterId` field). |
| `bidIds` | array | Multiple bid ids to fetch in one run. |
| `maxConcurrency` | integer | How many bid ids to fetch in parallel. |

## Output

One dataset item per tender. Real sample from a **list** run:

```json
{
  "_input": "list:openOnly=False,keyword=None",
  "_source": "S1-portail-bid-master-list",
  "_scrapedAt": "2026-08-27T07:22:23Z",
  "bdRecvEndDt": "2026-10-07 08:30:00.0",
  "bidInstNm": "Groupe Chimique Tunisien",
  "bidNmEn": "GEI2610057 Fourniture de dix de pièces de rechange pour pompes suivant plans pour les usines du GCT à Gabès",
  "publicDt": "2026-08-26 14:34:29.408804",
  "publicYn": "Y",
  "bidModSeq": "00",
  "bidNo": "20260805146",
  "bidNmAr": "GEI2610057 Fourniture de dix de pièces de rechange pour pompes suivant plans pour les usines du GCT à Gabès",
  "bidNmFr": "GEI2610057 Fourniture de dix de pièces de rechange pour pompes suivant plans pour les usines du GCT à Gabès",
  "epBidMasterId": 134250
}
```

Real sample from a **detail** run (truncated — the full record has ~90 fields,
including French/Arabic/English label variants for every coded value):

```json
{
  "_input": "134251",
  "_source": "S1-portail-bid-master-detail",
  "_scrapedAt": "2026-08-27T07:23:22Z",
  "epBidMasterId": 134251,
  "bidNo": "20260805154",
  "refNo": "MPS14-2026",
  "bidInstNm": "Hôpital d'Enfants",
  "bidNmFr": "«LA MISE A LA DISPOSITION D'UN AUTOMATE D'IMMUNOANALYSE AVEC ACQUISITION DES REACTIFS ET CONSOMMABLES» « MARCHE CADRE »",
  "bidNmAr": "«LA MISE A LA DISPOSITION D'UN AUTOMATE D'IMMUNOANALYSE AVEC ACQUISITION DES REACTIFS ET CONSOMMABLES» « MARCHE CADRE »",
  "bdRecvStartDt": "2026-08-27 08:00:00.0",
  "bdRecvEndDt": "2026-09-25 09:30:00.0",
  "bdOpenDt": "2026-09-25 10:30:00.0",
  "procedureTypeStrFr": "Appel d'offres ouvert",
  "procedureTypeStrEn": "Open Bidding",
  "bizKindStrFr": "Fournitures des biens",
  "bizKindStrEn": "Supplies",
  "priceTypeStrFr": "Marché à prix unitaire",
  "financialMethodStrFr": "Budget ",
  "guaranteeTypeStrFr": "Cautionnement",
  "evalMethodStrFr": "Moins disant",
  "executionPlaceStrFr": "TUNIS",
  "frameworkYn": "Y",
  "staffNm": "Sonia Sidia",
  "bdRecvAddrsFr": "hôpital enfants Bachir hamza  "
  // ... ~75 more fields: bidExpiredDays, biddingDocPrice, consorYn,
  // internationalBidYn, regId, bidInstCd, and every *StrAr/*StrEn label
}
```

| Field | Type | Description |
|---|---|---|
| `epBidMasterId` | integer | Stable internal id for this tender — the `detail` mode input. |
| `bidNo` / `refNo` | string | TUNEPS's own reference number / the buyer's internal reference. |
| `bidInstNm` | string | The government buyer/institution running the tender. |
| `bidNmFr` / `bidNmAr` / `bidNmEn` | string | Tender title in French / Arabic / English. |
| `publicDt` | string | When published to the public portal (SQL timestamp, not ISO 8601). |
| `bdRecvEndDt` | string | Submission deadline. |
| `bdRecvStartDt` / `bdOpenDt` | string | Submission opens / scheduled bid-opening date (detail only). |
| `procedureTypeStrFr` / `bizKindStrFr` / `priceTypeStrFr` / `financialMethodStrFr` / `guaranteeTypeStrFr` / `evalMethodStrFr` | string | Human-readable French labels for coded fields (each also has an `*StrAr` and `*StrEn` variant). |
| `_error` | string | Present only when a record couldn't be retrieved (`not_found` or `blocked_or_transient`). |

## Notes

- `openOnly=false` list runs return tenders in a live, constantly-updated
  feed order (most-recently-published-first) — the actor de-duplicates by
  `epBidMasterId` across pages and reports honestly if fewer than
  `maxResults` genuinely remain.
- All timestamps from TUNEPS are plain SQL-style strings
  (`YYYY-MM-DD HH:MM:SS`), not ISO 8601 — passed through as TUNEPS returns
  them rather than reformatted.
- For heavier usage, Residential proxies are recommended (set by default).

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ghana
(GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP), Papua New Guinea
(NPC), Sierra Leone (NPPA), Nepal (Bolpatra), Nigeria (NOCOPO), Tanzania
(NeST), and more.
