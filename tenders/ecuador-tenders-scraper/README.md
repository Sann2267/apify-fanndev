# Ecuador Government Tenders Scraper

Extracts public procurement records from Ecuador's official SERCOP
(Servicio Nacional de Contratacion Publica) open-data platform,
"Contrataciones Abiertas Ecuador" — built by SERCOP together with the Open
Contracting Partnership and CAF specifically for public, no-login access to
Ecuador's procurement data.

## Why use this actor

- No account, login, or API key required — every record here is public
  open data (CC BY 3.0 Ecuador license).
- Search by keyword and year, or fetch full OCDS (Open Contracting Data
  Standard) detail for a specific record you already know the OCID for.
- Full lifecycle detail in one record: procurement planning, tender,
  award (with winning supplier and value), and — for auctioned processes —
  a full bid-by-bid electronic reverse-auction history.
- Stable, structured OCDS JSON output ready for spreadsheets, databases, or
  reporting pipelines.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## How it works

1. Choose **List** mode to search SERCOP's public `search_ocds` API by
   keyword and year (both required — SERCOP's own API has no "browse
   everything" call) — or **Detail** mode to fetch one or more specific
   records you already know the OCID for.
2. The actor queries SERCOP's own open-data endpoints — the same API that
   powers the platform's own search page.
3. Every OCDS release SERCOP publishes for a record (planning, tender,
   award, and — where applicable — a full electronic-auction bid history)
   is included in the output, plus a handful of summary fields for quick
   reading.
4. Automatic retries handle temporary hiccups on SERCOP's end, so you don't
   have to babysit failed requests.

## A note on connectivity

SERCOP's open-data host was unreachable (plain TCP connection timeouts) from
several outside networks during this actor's development, while sibling
`gob.ec` hosts on the same domain answered normally — a pattern consistent
with regional network routing rather than a deliberate block (no WAF
challenge, no 403, just no response). This actor defaults
`proxyConfiguration` to **Residential proxies geolocated to Ecuador**
(`apifyProxyCountry: "EC"`) for reliability. See `CRAWLING_METHOD.md` for
the full investigation.

## Input

**List mode** — search recent records by keyword and year:

```json
{
  "mode": "list",
  "year": 2020,
  "searchQuery": "hospital",
  "buyer": "",
  "supplier": "",
  "maxResults": 25,
  "fetchDetail": false,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"], "apifyProxyCountry": "EC" }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `searchQuery` | string | **Required.** Keyword filter, at least 3 characters (matches titles/descriptions/buyer names). SERCOP's API has no "browse everything" call. |
| `year` | integer | The procurement year to search within (2015 or later). |
| `buyer` | string | Optional keyword to narrow to a specific purchasing institution. |
| `supplier` | string | Optional keyword to narrow to a specific supplier/contractor. |
| `maxResults` | integer | Caps how many records this run returns. |
| `fetchDetail` | boolean | When `true`, enriches each list row with the full OCDS release history (one extra request per row — slower). |
| `proxyConfiguration` | object | Apify Proxy settings (Ecuador-geolocated Residential recommended — see above). |

**Detail mode** — fetch specific records by OCID:

```json
{
  "mode": "detail",
  "ocid": "ocds-5wno2w-001-LICO-GPLR-2020-2805",
  "ocids": [],
  "maxConcurrency": 2,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"], "apifyProxyCountry": "EC" }
}
```

| Field | Type | Description |
|---|---|---|
| `ocid` | string | A single record's OCID (find one from a "list" mode run's `ocid` field). |
| `ocids` | array | Multiple record OCIDs to fetch in one run. |
| `maxConcurrency` | integer | How many records to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run
(`year=2020, searchQuery="hospital"`):

```json
{
  "_input": "list:year=2020:search=hospital",
  "_source": "S1-search-ocds",
  "_scrapedAt": "2026-08-27T07:26:51Z",
  "id": 82943,
  "ocid": "ocds-5wno2w-CE-20200001758366-102124",
  "date": "2020-01-03T00:00:00-05:00",
  "buyerId": null,
  "buyerName": null,
  "title": "Orden de compra CE-20200001758366",
  "description": "Orden de compra para adquirir los siguientes productos: SERVICIO DE ALIMENTACION PERMANENTE - PARA PACIENTES Y PERSONAL DE HOSPITALES Y UNIDADES DE SALUD",
  "year": 2020,
  "internalType": "Catalogo electronico - Compra directa",
  "singleProvider": null
}
```

Real sample from a **detail** run (`ocds-5wno2w-SIE-003-SLUCAS-2022-129262`,
an electronic reverse-auction for construction materials — truncated, the
full record also includes the complete bid-by-bid auction history, buyer/
supplier party details with RUC identifiers and addresses, and the buyer-
bidder enquiry Q&A thread):

```json
{
  "_input": "ocds-5wno2w-SIE-003-SLUCAS-2022-129262",
  "_source": "S1-record-ocds",
  "_scrapedAt": "2026-08-27T07:44:50Z",
  "tenderId": "SIE-003-SLUCAS-2022-129262",
  "tenderTitle": "SIE-003-SLUCAS-2022-129262",
  "tenderStatus": "active",
  "procurementMethod": "open",
  "buyerName": "GOBIERNO AUTONOMO DESCENTRALIZADO PARROQUIAL DE SAN LUCAS",
  "budgetAmount": null,
  "budgetCurrency": null,
  "tags": ["award", "planning", "tender"],
  "awardsCount": 1,
  "contractsCount": 0,
  "totalAwardAmount": 7540.84,
  "awardCurrency": "USD",
  "suppliers": ["JOSE CEVALLOS JOCE CIA. LTDA."],
  "latestReleaseDate": "2023-02-10T05:49:35-05:00",
  "ocid": "ocds-5wno2w-SIE-003-SLUCAS-2022-129262",
  "releases": [ /* full OCDS release: tender, awards, parties, auctions (bid-by-bid), planning, enquiries */ ],
  "uri": "https://portal.compraspublicas.gob.ec/sercop/datos_abiertos/",
  "version": "1.1",
  "publisher": { "uid": "ocds-5wno2w", "name": "Servicio Nacional de Contratacion Publica (SERCOP)", "scheme": "OCDS" },
  "extensions": [ "...ocds_enquiry_extension...", "...ocds_lots_extension...", "...ocds_auctions_extension...", "... 5 more" ],
  "publishedDate": "2023-02-10T05:49:35-05:00",
  "license": "https://creativecommons.org/licenses/by/3.0/ec/",
  "publicationPolicy": "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/documentos/politica-publicacion-SERCOP-OCDS.pdf"
}
```

| Field | Type | Description |
|---|---|---|
| `ocid` | string | Stable ID for this procurement process, unchanged from planning through tender, award, and contract. |
| `buyerName` | string | The government institution running this procurement. |
| `title` / `tenderTitle` | string | The process's title or reference code. |
| `internalType` | string | SERCOP's Spanish-language procurement modality (e.g. `Licitacion`, `Subasta Inversa Electronica`, `Menor Cuantia`, `Contratacion directa`, `Catalogo electronico - Compra directa`). |
| `tenderStatus` / `procurementMethod` | string | e.g. `active`, `complete`; `open`, `limited`, `direct`. |
| `budgetAmount` / `budgetCurrency` | number / string | The planning-stage budget, when present (often absent — many records' planning block only carries an internal budget line code). |
| `awardsCount` / `contractsCount` | integer | How many award/contract entries exist on this record. |
| `totalAwardAmount` / `awardCurrency` | number / string | Combined award value and its currency (USD — Ecuador's official currency). |
| `suppliers` | array | Names of all winning suppliers across this record's awards. |
| `tags` | array | Union of OCDS stage tags seen (`planning`, `tender`, `award`, `contract`). |
| `releases` | array | Every upstream OCDS release event for this OCID, verbatim — tender terms, awards, parties, and (for electronic-auction processes) the full bid-by-bid history. |
| `_error` | string | Present only when a record couldn't be retrieved (`not_found` for an unknown OCID, or a small-value "electronic catalog" purchase order that never got a full OCDS release compiled). |

A list row fetched with `fetchDetail: true` has the same additional fields
as a detail record, merged onto it.

## Notes

- `searchQuery` and `year` are both required for list mode — SERCOP's search
  API has no "browse everything" call.
- List mode returns however many records genuinely match your search —
  fewer than `maxResults` simply means fewer records currently exist for
  that filter; nothing is padded.
- `buyerId`/`buyerName` on list rows are frequently `null` upstream,
  especially for electronic-catalog direct-purchase orders — passed through
  as-is rather than guessed.
- Some OCIDs (mainly small electronic-catalog purchase orders) never get a
  full OCDS release compiled and return `_error: "not_found"` in detail
  mode — this is a real upstream data-coverage gap, not a bug.
- `tenderId`/`totalAwardAmount`/etc. are this actor's own summary fold
  across the raw `releases` array (SERCOP's API has no server-side merged
  "compiled record" view) — the full unmodified `releases` array is always
  included too, so nothing is lost.
- Residential proxies geolocated to Ecuador are set by default — see
  `CRAWLING_METHOD.md` for why.

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Nigeria
(NOCOPO), Ghana (GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP),
Papua New Guinea (NPC), Sierra Leone (NPPA), Nepal (Bolpatra), Eswatini
(ESPPRA), Rwanda (Umucyo), Namibia (CPBN), Trinidad & Tobago (ProcureTT),
Botswana (ministry sites), Malawi (MANEPS/PPDA), Tanzania (NeST),
Bangladesh (CPTU), Pakistan (PPRA-EPMS), Vietnam (VNEPS), Sri Lanka
(Treasury), Zimbabwe (PRAZ), Liberia (PPCC), Madagascar (ARMP), and
Cameroon (ARMP).
