# Cameroon Government Tenders Scraper (ARMP)

Scrapes Cameroon's official government tenders and procurement notices from ARMP (Agence de Régulation des Marchés Publics), the country's public procurement regulator. No account or login needed.

## Why use this actor

- Pulls from Cameroon's real, official procurement regulator — not a third-party tender-alert aggregator
- Covers every stage of the procurement lifecycle in one actor: open national and international tenders, requests for quotation/proposal, expressions of interest, award decisions, and award notices (with winning company and contract amount)
- Full publication text on demand — every numbered section a tender notice publishes (scope, cost estimate, eligibility, submission deadline, evaluation criteria, and more)
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline

## How it works

1. Pick a mode: browse a listing (`mode: "list"`), or fetch the full text for specific publications you already know (`mode: "detail"`).
2. For listings, choose which one: the latest publications of every kind, or one specific procurement category (national tenders, international tenders, quotations, proposals, expressions of interest, restricted tenders, or agreements).
3. The actor fetches and paginates through the results automatically, up to the limit you set.
4. Every listing row includes its own ID and link, so you can follow up with `mode: "detail"` for the complete publication text.
5. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage pagination or retries — the actor handles all of it.

## Input

**Browse the latest publications (default):**
```json
{
  "mode": "list",
  "listType": "latest",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Fetch full text for specific publications:**
```json
{
  "mode": "detail",
  "resourceIds": ["AO:64638", "DEC-ATTR:23168"],
  "maxConcurrency": 3
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` (default) — browse a listing page. `"detail"` — fetch full text for specific publications. |
| `listType` | string | `mode: "list"` only. `"latest"` (default) — every publication type mixed, newest first. Or one category: `"national"` (~7,038), `"quotation"` (~1,143), `"expression_of_interest"` (~557), `"international"` (~172), `"proposal"` (~20), `"restricted"` (~5), `"agreement"` (~3). |
| `maxResults` | integer | `mode: "list"` only. Max rows to return, across as many pages as needed. Default 50, max 5000. `"latest"` and `"national"` are very large — raise this only as high as you need. |
| `resourceId` | string | `mode: "detail"` only. A single publication's full link, or a `"TYPE:ID"` pair (e.g. `"AO:64638"`) — both found in a `"list"` mode run's `detailsUrl`/`typePublication`/`idPublication` fields. |
| `resourceIds` | array | `mode: "detail"` only. Multiple publications (links or `"TYPE:ID"` pairs) to fetch in one run. |
| `maxConcurrency` | integer | `mode: "detail"` only. How many publications to fetch in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"mode": "list", "listType": "latest", "maxResults": 1}`:

```json
{
  "_input": "list:latest",
  "_source": "S1-listing",
  "_scrapedAt": "2026-08-27T06:34:15Z",
  "recordType": "TENDER_LIST",
  "listType": "latest",
  "_page": 1,
  "_totalAvailable": null,
  "_lastPageSeen": 382,
  "typePublication": "AO",
  "idPublication": "64665",
  "title": "AVIS D'APPEL D'OFFRES NATIONAL OUVERT N° 06/AONO/CIPM/C-DIZ/SIGAMP/2026 DU 21 AOUT 2026 ... POUR LES TRAVAUX DE CONSTRUCTION D'UNE DECHARGE MUNICIPALE DANS LA COMMUNE DIZANGUE",
  "procuringEntity": "MAIRE DE DIZANGUE",
  "type": "Appels d'Offres National",
  "region": "LITTORAL",
  "amount": "40 000 000 FCFA",
  "publishedAt": "26-08-2026 21:09:39",
  "closingDate": "26-08-2026",
  "closingTime": "11:00:00",
  "noticePdfUrl": "http://pridesoft.armp.cm//0903_publications_dl?type_publication=AO&id_publication=64665",
  "daoPdfUrl": "http://pridesoft.armp.cm//0903_dao_dl?type_publication=AO&id_publication=64665",
  "detailsUrl": "https://armp.cm/details?type_publication=AO&id_publication=64665"
}
```

Real output for `{"mode": "detail", "resourceId": "AO:64638"}` — a tender notice (truncated, this one has 17 sections in total):

```json
{
  "_input": "AO:64638",
  "_source": "S1-detail-structured",
  "_scrapedAt": "2026-08-27T06:35:35Z",
  "recordType": "TENDER_DETAIL",
  "typePublication": "AO",
  "idPublication": "64638",
  "detailsUrl": "https://armp.cm/details?type_publication=AO&id_publication=64638",
  "procuringEntity": "COMMUNE DE DIANG",
  "title": "AVIS D'APPEL D'OFFRES NATIONAL OUVERT N° 008/AONO/C.DIANG/SIGAMP/CIPM/2026 DU 18/08/2026 POUR LA REHABILITATION EN ENDUIT SUPERFICIEL BICOUCHE DU TRONCON DE ROUTE HOTEL DE VILLE-LYCEE TECHNIQUE (800 ml)...",
  "sourceFinancement": "BUDGET INVESTISSEMENT PUBLIC(BIP)",
  "noticePdfUrl": "https://pridesoft.armp.cm//0903_publications_dl?type_publication=AO&id_publication=64638",
  "daoPdfUrl": "http://pridesoft.armp.cm//0903_dao_dl?type_publication=AO&id_publication=64638",
  "sections": {
    "objet": "Le Maire de la Commune de Diang, Maître d'Ouvrage et Autorité Contractante, lance un appel d'offres pour la réhabilitation en enduit superficiel bicouches du tronçon de route Hôtel de Ville-Lycée Technique de Diang long de 800 ml.",
    "consistanceDesPrestations": "Les travaux comprennent les opérations suivantes : -Installation ; -Nettoyage - terrassements ; -Chaussée ; -Assainissement-Drainage ...",
    "coutPrVisionnel": "Le montant prévisionnel des travaux est de 100 000 000 (cent millions) Francs FCFA toutes taxes comprises ;",
    "remisesDesOffres": "l'offre devra être déposée par le soumissionnaire au plus tard le 16/09/2026 à 10 heures..."
  },
  "sectionList": [
    { "number": 1, "label": "Objet", "text": "Le Maire de la Commune de Diang..." },
    { "number": 2, "label": "Consistance des prestations", "text": "Les travaux comprennent..." }
  ]
}
```

Real output for `{"mode": "detail", "resourceId": "DEC-ATTR:23168"}` — an award decision (a different, free-form shape, since these are published as full legal-decision text rather than a numbered notice):

```json
{
  "_input": "DEC-ATTR:23168",
  "_source": "S1-detail-freeform",
  "_scrapedAt": "2026-08-27T06:38:26Z",
  "recordType": "TENDER_DETAIL",
  "typePublication": "DEC-ATTR",
  "idPublication": "23168",
  "detailsUrl": "https://armp.cm/details?type_publication=DEC-ATTR&id_publication=23168",
  "procuringEntity": "CAMEROON WATER UTILITIES CORPORATION",
  "title": "DECISION N° 000032 /CW/DG/2026 DU 17 AOUT 2026 PORTANT ATTRIBUTION DE L'APPEL D'OFFRES INTERNATIONAL OUVERT N°00002/AOIO/CAMWATER/PforR IMPACT/CIPM/2026...",
  "sourceFinancement": null,
  "noticePdfUrl": "https://pridesoft.armp.cm//0903_publications_dl?type_publication=DEC-ATTR&id_publication=23168",
  "daoPdfUrl": null,
  "bodyText": "LE DIRECTEUR GENERAL\nVu\nLa Loi N° 2017/011 du 12 Juillet 2017 portant Statut général des Entreprises Publiques ;\n... N° du Lot\nEntreprise\nMontant FCFA\nLot unique\nHANGZHOU LAISON TECHNOLOGY Company Limited\n721 763 601 FCFA TTC (sept cent vingt et un millions...)"
}
```

A publication ID that doesn't exist produces one error record instead:

```json
{
  "_input": "AO:1",
  "_source": "none",
  "_scrapedAt": "2026-08-27T06:35:38Z",
  "_error": "not_found_or_restricted",
  "_errorDetail": ""
}
```

| Field | Description |
|---|---|
| `_input` | What produced this record — `"list:<listType>"` for listing rows, or `"TYPE:ID"` for detail records. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on failed/inaccessible records. |
| `recordType` | `TENDER_LIST` or `TENDER_DETAIL`. |
| `typePublication` / `idPublication` | ARMP's own document-type code (e.g. `AO` tender notice, `DC` quotation, `AMI` expression of interest, `DEC-ATTR` award decision, `COMM` award notice, `ADDITIF` addendum) and numeric ID — feed either as `"TYPE:ID"` into a `mode: "detail"` run for the full text. |
| `title` / `procuringEntity` | Publication title and the government body running it. |
| `type` / `region` / `amount` / `publishedAt` / `closingDate` | Listing-mode columns — procurement category, region, estimated/awarded amount, and dates. |
| `sections` / `sectionList` | Detail mode, tender/quotation notices — every numbered section ARMP itself publishes. |
| `bodyText` | Detail mode, award decisions/notices/addenda — the full publication text (these don't use numbered sections). |

## Notes

- `"latest"` and `"national"` listings are large (3,800+ and 7,000+ entries) — start with a small `maxResults` to preview before scraping in bulk.
- A procurement category's listing includes not just its original tender notices, but also the award decisions and notices later published for those same tenders — `typePublication` tells you which is which.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the real ARMP platform was confirmed against a look-alike site.
