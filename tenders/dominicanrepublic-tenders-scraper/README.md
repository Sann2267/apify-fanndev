# Dominican Republic Government Tenders Scraper

Extracts public procurement records from the Dominican Republic's official
DGCP (Direccion General de Contrataciones Publicas) open-data platform —
built by DGCP's own Data Science department specifically for public,
no-login access to the country's tender/procurement data.

## Why use this actor

- No account, login, or API key required — every record here is public
  open data, served from DGCP's own documented REST API.
- Browse or filter tender/procurement processes by status, procurement
  modality, buyer institution, date range, or process code.
- Full lifecycle detail in one record: the process itself, plus the
  contracts awarded (with winning supplier name and value), the offers
  received, and the requested line items — DGCP exposes these as four
  separate endpoints; this actor bundles them together per process.
- Data refreshes every 8 hours from DGCP's own Data Warehouse — genuinely
  current, not a stale export.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## How it works

1. Choose **List** mode to browse/filter DGCP's `/procesos` API by status,
   modality, buyer, date range, or a specific process code — or **Detail**
   mode to fetch full detail for one or more process codes you already
   know.
2. The actor queries DGCP's own open-data endpoints — the same REST API
   documented on the open-data portal's own API-docs page.
3. In detail mode (or list mode with "fetch full detail" enabled), each
   process is enriched with its contracts, offers received, and requested
   line items — genuine transparency data, not summarized or redacted.
4. Automatic retries handle temporary hiccups on DGCP's end, so you don't
   have to babysit failed requests.

## Input

**List mode** — browse or filter recent processes:

```json
{
  "mode": "list",
  "estado": "Proceso publicado",
  "modalidad": "",
  "unidadCompra": null,
  "startDate": "",
  "endDate": "",
  "procesoCode": "",
  "maxResults": 25,
  "fetchDetail": false
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `estado` | string | Optional exact-match status filter, e.g. `"Proceso publicado"` (open for bids), `"Proceso adjudicado y celebrado"` (awarded), `"Proceso desierto"` (no bids), `"Cancelado"`. Blank = all statuses. |
| `modalidad` | string | Optional exact-match procurement modality filter (e.g. `"Licitacion Publica Nacional"`, `"Comparacion de Precios"`). Blank = all modalities. |
| `unidadCompra` | integer | Optional filter to one buyer institution's internal DGCP code. |
| `startDate` / `endDate` | string | Optional publish-date range, inclusive, `YYYY-MM-DD`. |
| `procesoCode` | string | Optional exact-match filter to a single process code. |
| `maxResults` | integer | Caps how many records this run returns. |
| `fetchDetail` | boolean | When `true`, enriches each list row with contracts/offers/line items (up to 3 extra requests per row — slower). |

**Detail mode** — fetch specific processes by code:

```json
{
  "mode": "detail",
  "procesoCode": "SUPERATE-CCC-CP-2026-0012",
  "procesoCodes": [],
  "maxConcurrency": 3
}
```

| Field | Type | Description |
|---|---|---|
| `procesoCode` | string | A single process code (find one from a "list" mode run's `codigo_proceso` field). |
| `procesoCodes` | array | Multiple process codes to fetch in one run. |
| `maxConcurrency` | integer | How many processes to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run
(`estado="Proceso publicado"`, still open for bids — truncated to the key
fields, the real output includes ~35 fields per process):

```json
{
  "_input": "list:estado=Proceso publicado",
  "_source": "S1-api-procesos",
  "_scrapedAt": "2026-08-27T16:35:22Z",
  "codigo_proceso": "SUPERATE-CCC-CP-2026-0012",
  "unidad_compra": "Direccion de Desarrollo Social Superate",
  "modalidad": "Comparacion de Precios",
  "titulo": "ADQUISICION DE MOBILIARIOS PARA LA DIRECCION DE DESARROLLO SOCIAL SUPERATE",
  "estado_proceso": "Proceso publicado",
  "divisa": "DOP",
  "monto_estimado": 4021146.95,
  "fecha_publicacion": "2026-08-26T18:00:01.61Z",
  "fecha_fin_recepcion_ofertas": "2026-09-08T09:00:00Z",
  "objeto_proceso": "Bienes",
  "url": "https://comunidad.comprasdominicana.gob.do//Public/Tendering/OpportunityDetail/Index?noticeUID=DO1.NTC.1761054"
}
```

Real sample from a **detail** run (`HFMP-DAF-CD-2026-0442`, an already
-awarded process — truncated, `articulos` shows 1 of 3 line items):

```json
{
  "_input": "HFMP-DAF-CD-2026-0442",
  "_source": "S1-api-procesos+contratos+ofertas+articulos",
  "_scrapedAt": "2026-08-27T16:42:38Z",
  "codigo_proceso": "HFMP-DAF-CD-2026-0442",
  "unidad_compra": "Hospital Docente Universitario Doctor Francisco E, Moscoso Puello",
  "modalidad": "Compras por Debajo del Umbral",
  "titulo": "COMPRA DE DESECHABLESPARA EL AREA DE DESPENSA DEL HOSPITAL",
  "estado_proceso": "Proceso adjudicado y celebrado",
  "divisa": "DOP",
  "monto_estimado": 184600,
  "contratos": [
    {
      "codigo_contrato": "HFMP-2026-00688",
      "estado_contrato": "Activo",
      "valor_contratado": 217828,
      "metodo_pago": "Transferencia",
      "rpe": "135415",
      "razon_social": "Moonwolf Business Association, S.R.L."
    }
  ],
  "contratosCount": 1,
  "contratosTotalUpstream": 1,
  "ofertas": [],
  "ofertasCount": 0,
  "articulos": [
    {
      "descripcion_articulo": "Agitadores desechables para uso domestico",
      "descripcion_usuario": "FARDO VASO FOAM 12 ONZ",
      "cantidad": 6,
      "unidad_medida": "Caja",
      "precio_unitario_estimado": 3100,
      "precio_total_estimado": 18600
    },
    "... 2 more"
  ],
  "articulosCount": 3,
  "articulosTotalUpstream": 3
}
```

| Field | Type | Description |
|---|---|---|
| `codigo_proceso` | string | DGCP's stable identifier for the process. |
| `unidad_compra` | string | The purchasing government institution's name. |
| `titulo` / `descripcion` | string | The process's title/description, as published. |
| `modalidad` | string | Procurement modality (e.g. `Licitacion Publica Nacional`, `Comparacion de Precios`, `Procesos de Excepcion`). |
| `estado_proceso` | string | Current status — open for bids, awarded, cancelled, etc. |
| `monto_estimado` / `divisa` | number / string | Estimated value and currency (DOP — Dominican peso — in every record observed). |
| `fecha_publicacion` / `fecha_fin_recepcion_ofertas` / `fecha_apertura_ofertas` / ... | string | Key dates in the process timeline. |
| `contratos` | array | Awarded contracts (detail records) — winning supplier (`razon_social`/`rpe`), contracted value, status, payment terms. Empty for processes not yet awarded. |
| `ofertas` | array | Offers/bids submitted (detail records). |
| `articulos` | array | Requested line items with UNSPSC classification and estimated pricing (detail records). |
| `url` | string | Link to the process on the Comprasdominicana portal. |
| `_error` | string | Present only when a record couldn't be retrieved (`not_found` for an unknown process code). |

A list row fetched with `fetchDetail: true` has the same `contratos`/
`ofertas`/`articulos` fields as a detail record, merged onto it.

## Notes

- All filters in list mode are optional — leaving everything blank browses
  the full public archive (600,000+ historical processes as of this
  writing), ordered roughly by publish date (see `CRAWLING_METHOD.md` for
  an honest note on a minor within-page ordering quirk).
- `estado`/`modalidad` are exact-match filters on DGCP's own Spanish-language
  text — see the input field descriptions for the values observed live.
- `contratos`/`ofertas` are genuinely empty (not an error) for any process
  still open for bidding — DGCP hasn't run an award yet.
- Data refreshes every 8 hours from DGCP's Data Warehouse (00:00, 07:00,
  14:00, 21:00 Dominican time), so very-recent changes on the live bidding
  portal can lag here by up to ~8 hours.
- This actor never touches the separate "Comprasdominicana" transactional/
  bidding portal (`comunidad.comprasdominicana.gob.do`), which requires a
  supplier account to log in — only the public open-data API.

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Nigeria
(NOCOPO), Ghana (GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP),
Papua New Guinea (NPC), Sierra Leone (NPPA), Nepal (Bolpatra), Eswatini
(ESPPRA), Rwanda (Umucyo), Namibia (CPBN), Trinidad & Tobago (ProcureTT),
Botswana (ministry sites), Malawi (MANEPS/PPDA), Tanzania (NeST),
Bangladesh (CPTU), Pakistan (PPRA-EPMS), Vietnam (VNEPS), Sri Lanka
(Treasury), Zimbabwe (PRAZ), Liberia (PPCC), Madagascar (ARMP), Cameroon
(ARMP), Indonesia (SPSE Nasional), Ethiopia (eGP), DR Congo (SIGMAP),
Algeria (Ministry of Defense), Tunisia (TUNEPS), Ecuador (SERCOP OCDS), and
Honduras (HonduCompras).
