# El Salvador Government Tenders Scraper

Search El Salvador's official COMPRASAL public procurement system for currently open tenders (licitaciones) or the historical awarded-contract ledger — including winning supplier and declared beneficial-owner information. No account, login, or API key needed.

## Why use this actor

- No account, login, or API key needed — COMPRASAL's public listing/detail API is open to everyone; registration is only required to actually *submit* a bid
- `open` mode: every currently active tender, with its full procurement-stage timeline (publication, offer submission, clarifications, addenda, offer receipt, opening, award)
- `awarded` mode: the historical awarded-contract ledger — award amount, winning supplier, and (when disclosed) the supplier's declared **beneficial owner** with name and nationality — rare transparency data
- `detail` mode: full record for any specific process
- Filter by institution (case-insensitive name match) in either list mode

## How it works

1. Choose `open` for currently active tenders, `awarded` for the historical award ledger, or `detail` for specific process IDs.
2. The actor calls COMPRASAL's own public JSON API (`www.comprasal.gob.sv/api/v1/publico/...`) directly.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

**Open mode** — currently active tenders, optionally filtered by institution:

```json
{
  "mode": "open",
  "entidad": "Instituto Salvadoreño del Seguro Social",
  "maxResults": 50,
  "fetchDetail": false,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Awarded mode** — historical awarded contracts, with supplier/beneficial-owner data:

```json
{
  "mode": "awarded",
  "entidad": "",
  "maxResults": 50
}
```

**Detail mode** — fetch full information for a specific process (use the `id` field from an `open` record, or `proceso_compra.id` from an `awarded` record):

```json
{
  "mode": "detail",
  "processId": 135800
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `open` (active tenders), `awarded` (historical/award ledger), or `detail` (specific process IDs). Default `open`. |
| `entidad` | string | *(open/awarded)* Institution name contains — case-insensitive substring match. In `open` mode this is a real server-side filter; in `awarded` mode COMPRASAL's own filter param is broken (ignored server-side — verified), so this is applied client-side after fetching, which can be slower for a rarely-awarded institution. |
| `maxResults` | integer | Max records to return. Default 50, max 5000. |
| `fetchDetail` | boolean | *(open/awarded)* Also fetch each process's full detail and merge it into a `detail` sub-object. Slower — one extra request per process. |
| `processId` / `processIds` | integer / array | *(detail)* One or more numeric process IDs. |
| `maxConcurrency` | integer | Parallel detail-page fetches. Default 3, max 6. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

This is real output from `open` mode filtered to `entidad: "ISSS"` (Instituto Salvadoreño del Seguro Social):

```json
{
  "_input": { "entidad": "ISSS", "institucionId": 78 },
  "_source": "S1-comprasal-api-disponibles",
  "_scrapedAt": "2026-08-27T16:52:06Z",
  "id": 135800,
  "nombre_proceso": "LC27DM0007 ADQUISICIÓN DE REACTIVOS DE LABORATORIO MICROBIOLOGICOS PARA VARIOS CENTROS DE ATENCIÓN DEL ISSS PARTE 1 NECESIDAD 2027",
  "codigo_proceso": "3303-2026-P0282",
  "institucion": "Instituto Salvadoreño del Seguro Social (ISSS)",
  "estado_actual": "En ejecución",
  "forma_contratacion": "Licitación competitiva",
  "codigo_forma_contratacion": "LC",
  "estado_proceso": "Activo",
  "EtapaPorProcesos": [
    {
      "id": 1849953,
      "nombre": "Recepción de ofertas",
      "fecha_hora_inicio": "2026-08-26T06:05:00.000Z",
      "fecha_hora_fin": "2026-08-27T17:00:00.000Z"
    }
  ],
  "etapas": [
    { "id": 1849954, "nombre": "Publicación de convocatoria en Comprasal", "fecha_hora_inicio": "2026-07-27T14:30:00.000Z", "fecha_hora_fin": "2026-08-27T15:00:00.000Z" },
    { "id": 1849960, "nombre": "Entrega de solicitud de oferta", "fecha_hora_inicio": "2026-07-27T14:30:00.000Z", "fecha_hora_fin": "2026-08-27T05:55:00.000Z" }
    // ... 10 more stages in this process's full timeline
  ]
}
```

And this is real output from `awarded` mode — note the winning supplier and its declared beneficial owner:

```json
{
  "_input": { "entidad": null },
  "_source": "S1-comprasal-api-publicos",
  "_scrapedAt": "2026-08-27T16:48:36Z",
  "id": 491162,
  "monto": 49500,
  "proceso_compra": {
    "id": 134128,
    "nombre_proceso": "ADQUISICION DE MEDICAMENTOS AÑO 2026",
    "codigo_proceso": "3215-2026-P0074",
    "fecha_adjudicacion": "2026-08-27",
    "Institucion": { "id": 96, "codigo": "3215", "nombre": "Hospital Nacional \"Dr. Juan José Fernández\", Zacamil, Mejicanos (San Salvador)" }
  },
  "institucion": { "id": 96, "codigo": "3215", "nombre": "Hospital Nacional \"Dr. Juan José Fernández\", Zacamil, Mejicanos (San Salvador)" },
  "proveedor": {
    "id": 14076,
    "nombre": "LANCO MEDICAL GROUP, LTDA. DE C.V.",
    "nombre_comercial": "DROGUERIA LANCO",
    "accionistas": [ { "id": 14670, "agente_legal": true }, { "id": 31505, "agente_legal": true } ]
  }
  // ... plus a "beneficiario" object (declared beneficial owner name + nationality) when disclosed
}
```

`beneficiario`/`accionistas` are empty/absent whenever COMPRASAL itself has nothing disclosed for that award yet — a faithful reflection of the source, not a scraping gap.

## Data source

El Salvador's COMPRASAL (`www.comprasal.gob.sv`), operated by DINAC (Dirección Nacional de Compras Públicas) — the mandatory national e-procurement system for all institutions subject to the LACAP procurement law. See `CRAWLING_METHOD.md` for how the public JSON API was found and verified.
