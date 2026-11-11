# Nicaragua Government Tenders Scraper

Search Nicaragua's official government procurement portal, SISCAE (Sistema de Contrataciones Administrativas Electrónicas), for tenders and get institution, procedure type and number, classification, title, status, and key dates. No account, login, or API key needed.

## Why use this actor

- No account, login, or API key needed — SISCAE's search and results are open to the public
- Search all currently active tenders, or filter by keyword, procedure number, institution, department (region), and status (open, awarded, cancelled, etc.) — combine several statuses in one search
- Get the buyer institution, procedure type and reference number, UNSPSC-style classification code(s), the free-text object/title, and publication / closing / last-updated dates
- Handles SISCAE's quirks for you: a Java portlet (JSF) search form, session cookies, and generous retries for an occasionally slow government server

## How it works

1. Set your filters — keyword, institution, department, status, or leave them empty to browse everything currently open.
2. The actor submits Nicaragua's official SISCAE search form (`gestion.nicaraguacompra.gob.ni`) and collects matching procedures.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "estados": ["vigente"],
  "keyword": "",
  "institucion": "",
  "departamento": "",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `estados` | array | One or more statuses to search: `vigente` (open), `ejecucion` (in execution), `cancelado`, `cerrado`, `desierto` (void), `adjudicado` (awarded), `suspendido`. Default `["vigente"]`. |
| `keyword` | string | Optional free-text keyword (Spanish), matched against the procurement object/title. |
| `numero` | string | Optional. Filters to a specific procedure number, e.g. `"16/2026"`. |
| `institucion` | string | Optional. Institution name contains — case-insensitive substring match, e.g. `"ENACAL"` or `"Alcaldia"`. |
| `departamento` | string | Optional. Department/region contains, e.g. `"Managua"`. |
| `maxResults` | integer | Max procedures to return. Default 50, max 100 — SISCAE's own search form supports up to 100 results per request; no further pagination was confirmed working. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default, though plain datacenter was also confirmed working during development — see `CRAWLING_METHOD.md`. |

## Output

This is real output from a search with `estados: ["vigente"]` (no other filters):

```json
{
  "_input": {
    "keyword": null,
    "numero": null,
    "estados": ["VIGENTE"],
    "institucion": null,
    "institucionValue": "-1",
    "departamento": null,
    "departamentoValue": "-1",
    "resultadosItems": "DIEZ"
  },
  "_source": "S1-jsf-portlet-grid",
  "_scrapedAt": "2026-08-27T17:32:19Z",
  "tipoProcedimiento": "LICITACION SELECTIVA",
  "numeroProcedimiento": "2/2026",
  "estado": "Vigente",
  "codigoSigaf": "#",
  "publicacion": "25/08/2026",
  "cierre": "03/09/2026 10:15:00 AM",
  "ultimaActualizacion": "25/08/2026 07:18:41 PM",
  "institucion": "Alcaldía San Ramón (Alcaldía San Ramón) - Unidad de Adquisición SAN RAMON",
  "clasificaciones": [
    "Vías (95110000)",
    "Servicios de mantenimiento y reparaciones de construcciones e instalaciones (72100000)"
  ],
  "objeto": "MANTENIMIENTO Y CONSTRUCCIÓN DE OBRAS EN CALLES DEL CASCO URBANO Y PERIFERIA"
}
```

And this is real output filtered by `institucion: "Managua"` with `estados: ["vigente", "adjudicado"]`:

```json
{
  "_input": {
    "keyword": null,
    "numero": null,
    "estados": ["VIGENTE", "ADJUDICADO"],
    "institucion": "Managua",
    "institucionValue": "70",
    "departamento": null,
    "departamentoValue": "-1",
    "resultadosItems": "DIEZ"
  },
  "_source": "S1-jsf-portlet-grid",
  "_scrapedAt": "2026-08-27T17:28:54Z",
  "tipoProcedimiento": "LICITACION PUBLICA",
  "numeroProcedimiento": "215/2026",
  "estado": "Adjudicado",
  "codigoSigaf": "#",
  "publicacion": "24/06/2026",
  "cierre": "14/07/2026 02:00:00 PM",
  "ultimaActualizacion": "24/08/2026 07:40:15 PM",
  "institucion": "Alcaldía Managua (Alcaldía Managua) - Unidad de Adquisición MANAGUA",
  "clasificaciones": ["Equipos deportivos para campos y canchas (49160000)"],
  "objeto": "SUMINISTRO E INSTALACION DE CANCHA DE FUTBOL TRIPLE - COMPLEJO DEPORTIVO HUGO CHAVEZ"
}
```

`_input.institucionValue`/`departamentoValue` show the numeric ID SISCAE resolved your `institucion`/`departamento` text to (`-1` means "all" — no match narrowed it, or none was requested).

## Notes

- `codigoSigaf` is frequently `"#"` upstream (not yet assigned to that procedure) — passed through as-is, not blanked out.
- No monetary/budget amount field is exposed on SISCAE's public list view (unlike some other countries in this collection) — this actor does not guess one.
- `clasificaciones` can hold more than one category when a procedure spans several UNSPSC-style classifications.
- A search that matches nothing returns a single record with `_error: "not_found"` rather than an empty dataset, so you can tell "ran successfully, found nothing" apart from "run failed."
- This actor does not offer a separate "detail" mode — SISCAE's own "Más Datos" per-procedure expansion is a JavaScript-driven in-place postback with no stable detail URL; see `CRAWLING_METHOD.md` for what was tried.

## Data source

Nicaragua's Dirección General de Contrataciones del Estado (DGCE), via SISCAE — specifically the public search application at `www.gestion.nicaraguacompra.gob.ni/siscae/portal` (not the separate `www.nicaraguacompra.gob.ni` marketing site). See `CRAWLING_METHOD.md` for the full recon writeup, including why no country-pinned proxy is needed here.

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Honduras (HonduCompras), Ecuador (SERCOP OCDS), Nigeria (NOCOPO), Ghana (GHANEPS), Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP), Papua New Guinea (NPC), Sierra Leone (NPPA), Nepal (Bolpatra), Eswatini (ESPPRA), Rwanda (Umucyo), Namibia (CPBN), Trinidad & Tobago (ProcureTT), Botswana (ministry sites), Malawi (MANEPS/PPDA), Tanzania (NeST), Bangladesh (CPTU), Pakistan (PPRA-EPMS), Vietnam (VNEPS), Sri Lanka (Treasury), Zimbabwe (PRAZ), Liberia (PPCC), Madagascar (ARMP), Cameroon (ARMP), Indonesia (SPSE), Ethiopia (eGP), DR Congo (SIGMAP), Algeria (MDN), and Tunisia (TUNEPS).
