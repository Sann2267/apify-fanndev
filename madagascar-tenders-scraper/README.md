# Madagascar Government Tenders Scraper (ARMP e-GP)

Scrapes Madagascar's official public procurement regulator, ARMP (Autorite de Regulation des Marches Publics), for live calls for tender, the multi-year tender archive, and awarded contracts. No account or login needed.

## Why use this actor

- Pulls from Madagascar's real, official procurement platform — not a third-party tender-alert aggregator
- Three views in one actor: **live calls for tender** across every region, a **searchable multi-year archive** back to 2015, and **awarded contracts** with supplier name, tax ID, and contract amount
- Rare transparency data: awarded contracts include the winning supplier's declared beneficial owner(s), not just the company name
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting pipeline
- Content is in French, exactly as published by the regulator — every field is passed through unchanged so nothing gets lost in translation

## How it works

1. Pick a list type: `avis` for what's open for bidding right now, `dossiers` to search the historical archive by year, or `contrats` for finished, awarded contracts by year.
2. For `dossiers` and `contrats`, set the year you want (defaults to the current year).
3. The actor fetches the matching results and returns up to the limit you set.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage sessions, retries, or French-language forms — the actor handles all of it.

## Input

**Live calls for tender (default):**
```json
{
  "listType": "avis",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Search the historical archive:**
```json
{
  "listType": "dossiers",
  "year": "2026",
  "maxResults": 100
}
```

**Awarded contracts:**
```json
{
  "listType": "contrats",
  "year": "2026",
  "maxResults": 100
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"avis"` (default) — live calls for tender across every region (~450 at a time). `"dossiers"` — search the archive by year (2015-present). `"contrats"` — awarded contracts by year (2015-present). |
| `year` | string | `dossiers`/`contrats` only. Which year to search. Defaults to the current year. Ignored for `avis`. |
| `maxResults` | integer | Caps how many rows are kept in the output. Default 100, max 10,000. Older/full years can hold thousands of records — start small to preview. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "avis", "maxResults": 1}`:

```json
{
  "_input": "list:avis",
  "_source": "S1-index-by-region",
  "_scrapedAt": "2026-08-27T06:31:01Z",
  "recordType": "TENDER_AVIS",
  "region": "CENTRALE",
  "entite": "MINISTERE DE L'EDUCATION NATIONALE",
  "reference": "68-2026/MEN/PRMP/DCO",
  "modePassation": "ACO",
  "numero": "2600188-3CPX001",
  "objet": "Entretien de véhicule adminitratif de marque NISSAN PATROL N°0911 TBK",
  "dateDu": "2026-08-26",
  "dateAu": "2026-09-08",
  "noticePdfUrl": "http://154.126.93.219/SIGMP/pdf/ASAPC_SUB.php?num_dos=2600188-3CPX001"
}
```

Real output for `{"listType": "dossiers", "year": "2026", "maxResults": 1}`:

```json
{
  "_input": "list:dossiers",
  "_source": "S1-dossier-archive-search",
  "_scrapedAt": "2026-08-27T06:31:45Z",
  "recordType": "TENDER_DOSSIER",
  "institution": "MINISTERE DE LA JUSTICE",
  "modePassationLabel": "Consultation de Prix par voie d`affichage",
  "natureMarche": "Fournitures",
  "reference": "001/2026-DRAP.AMM/PRMP/UGPM",
  "numero": "2600001-10CPX001",
  "objet": "FOURNITURE ET LIVRAISON DES AUTRES COMBUSTIBLES [BOIS DE CHAUFFAGE] DE LA DIRECTION REGIONALE DE L ADMINISTRATION PENITENTIAIRE AMORON I MANIA",
  "dateDossier": "05/01/2026",
  "financement": "RPI, ,",
  "prmpNom": "ANDRIAMASY Ainirina Jhercel"
}
```

Real output for `{"listType": "contrats", "year": "2026", "maxResults": 1}` — note the beneficial-owner field, disclosed per Madagascar's transparency requirements:

```json
{
  "_input": "list:contrats",
  "_source": "S1-contrat-action-json",
  "_scrapedAt": "2026-08-27T06:32:14Z",
  "recordType": "TENDER_CONTRAT",
  "ENTITE_CODE": "9001",
  "ENTITE_LIBELLE": "AEROPORTS DE MADAGASCAR",
  "ENT_CAT_LIBELLE": "SOCIETE D'ETAT",
  "TYPE_MARCHE_LIBELLE": "Fournitures",
  "MODE_PASS_LIBELLE": "APPEL D'OFFRE OUVERT INTERNATIONAL",
  "MODALITE_EXECUTION": "QUANTITE FIXE",
  "CONTRAT_CODE": "26005297AOOI002001",
  "CONTRAT_OBJET": "Fourniture d'agents extincteurs répartie en deux (02) lots: Lot n°1: Fourniture émulseur sans Fluor - type B",
  "MTT_TTC": "848113200.00",
  "UNITE_MONNAIE": "MGA",
  "TITULAIRE_NIF": "1000013507",
  "TITULAIRE_NOM": "DINEC TECNOALARM",
  "BENEFICIAIRE_EFFECTIF": "HIRIDJEE HALIMA KHATOUNE; HIRIDJEE HALIMA KHATOUNE; MOHAMMAD ALI ABBAS",
  "PRMP_NOM": "ANDRIANIAINA Jean Germain"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:avis"`, `"list:dossiers"`, or `"list:contrats"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `TENDER_AVIS`, `TENDER_DOSSIER`, or `TENDER_CONTRAT`. |
| `entite` / `institution` / `ENTITE_LIBELLE` | The government body running the procurement (field name varies by list type). |
| `objet` / `CONTRAT_OBJET` | What is being procured. |
| `numero` / `CONTRAT_CODE` | ARMP's internal dossier/contract number. |
| `dateDu` / `dateAu` | Bid submission opening/deadline dates (`avis` only). |
| `dateDossier` / `financement` / `prmpNom` | Registration date, financing source, and procurement officer (`dossiers` only). |
| `TITULAIRE_NOM` / `TITULAIRE_NIF` / `BENEFICIAIRE_EFFECTIF` | Winning supplier's name, tax ID, and declared beneficial owner(s) (`contrats` only). |
| `MTT_TTC` / `UNITE_MONNAIE` | Contract amount and currency, almost always Malagasy ariary (`contrats` only). |

## Notes

- The archive (`dossiers`) and awarded-contracts (`contrats`) lists can each hold thousands of records for a full year — start with a small `maxResults` to preview before scraping in bulk.
- All content is published in French by the regulator itself; field values (dates, amounts, names) are passed through exactly as shown on the official site.
- See `CRAWLING_METHOD.md` for the full technical writeup, including how the official ARMP platform was confirmed against multiple independent sources.
