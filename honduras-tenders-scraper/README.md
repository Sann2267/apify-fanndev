# Honduras Government Tenders Scraper

Search Honduras' official government procurement register for tenders (licitaciones) and get institution, object of purchase, stage, dates, contact person, line items, documents, bidders, and award info. No account, login, or API key needed.

## Why use this actor

- No account, login, or API key needed — the register is open to the public
- Search all tenders, or filter by institution, stage (open/awarded/failed/etc.), modality, acquisition type, exact record number, or date range
- Get the full picture per tender: buyer institution and purchasing unit, key dates, funding source, a named contact person with phone and email, requested line items (with quantities and full specifications), attached documents, bidders, and award details
- Covers both currently-open tenders and Honduras' historical procurement record
- Handles the register's quirks for you: a legacy ASP.NET form-postback protocol, session cookies, and generous retries for a slow government server

## How it works

1. Choose `list` mode to search (optionally filtered), or `detail` mode to fetch full information for specific tender links.
2. The actor searches Honduras' official ONCAE procurement register (`sicc.honducompras.gob.hn`) and collects matching tenders.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

**List mode** — search and get list-level fields for every match:

```json
{
  "mode": "list",
  "etapa": "recepcion_ofertas",
  "maxResults": 50,
  "fetchDetail": false,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Detail mode** — fetch full information for specific tenders (use a `detailUrl` from a `list` run):

```json
{
  "mode": "detail",
  "urls": ["http://sicc.honducompras.gob.hn/HC/procesos/ProcesoHistorico.aspx?Id0=...&Id1=...&Id2=..."]
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `list` (search) or `detail` (fetch specific tender URLs). Default `list`. |
| `entidad` | string | *(list)* Institution name contains — case-insensitive substring match, e.g. `"Salud"` matches the Ministry of Health. |
| `etapa` | string | *(list)* Stage filter: `todas` (all), `elaboracion`, `revisado`, `recepcion_ofertas`, `evaluacion`, `adjudicado`, `desierto`, `fracasados`. |
| `modalidad` | string | *(list)* Modality filter: `todas`, `licitacion_o_concurso`, `compra_menor`, `precalificacion`. |
| `tipoAdquisicion` | string | *(list)* Acquisition type: `todas`, `suministro_bienes_servicios`, `obras`, `consultoria`. |
| `expediente` | string | *(list)* Look up one exact record number. |
| `fechaInicio` / `fechaFin` | string | *(list)* Optional date range on the process start date, format `dd/mm/yyyy`. |
| `maxResults` | integer | *(list)* Max tenders to return. Default 50, max 1000. |
| `fetchDetail` | boolean | *(list)* Also fetch each tender's full detail page and merge it in. Slower. |
| `url` / `urls` | string / array | *(detail)* One or more tender detail page URLs. |
| `maxConcurrency` | integer | Parallel detail-page fetches. Default 3, max 6 — keep low, the register's server is slow. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

This is real output from a `list` search filtered to `etapa: "recepcion_ofertas"` (currently receiving offers):

```json
{
  "_input": {
    "entidad": null,
    "entidadValue": "0",
    "etapa": "3",
    "modalidad": "0",
    "tipoAdquisicion": "0",
    "expediente": null,
    "fechaInicio": null,
    "fechaFin": null
  },
  "_source": "S1-aspnet-gridview",
  "_scrapedAt": "2026-08-27T07:36:51Z",
  "expediente": "LPN No. 08-2026-SEAPI-UNAH",
  "entidad": "Universidad Nacional Autónoma de Honduras (UNAH)",
  "unidadCompra": "Secretaría Ejecutiva de Administración de Proyectos de Infraestructura",
  "objetoCompra": "Mejoramiento Edificio No. 1 y Construcción de Edificio de Aulas y Área Administrativa, Campus UNAH-CURC, Comayagua...",
  "etapa": "Recepción de Ofertas",
  "modalidad": "Licitación pública nacional",
  "fechaInicio": "17/08/2026",
  "fechaCierre": "20/10/2026",
  "detailUrl": "http://sicc.honducompras.gob.hn/HC/procesos/ProcesoHistorico.aspx?Id0=OAAAADcAAAAyAAAA-1rKykAr89vs%3d&Id1=..."
}
```

And this is real output from `detail` mode on that same tender's `detailUrl`:

```json
{
  "_input": "http://sicc.honducompras.gob.hn/HC/procesos/ProcesoHistorico.aspx?Id0=OAAAADcAAAAyAAAA-1rKykAr89vs%3d&Id1=...",
  "_source": "S1-aspnet-detail",
  "_scrapedAt": "2026-08-27T07:37:09Z",
  "Expediente": "LPN No. 08-2026-SEAPI-UNAH",
  "Entidad": "Universidad Nacional Autónoma de Honduras (UNAH)",
  "Unidad de Compra": "Secretaría Ejecutiva de Administración de Proyectos de Infraestructura",
  "Objeto": "Mejoramiento Edificio No. 1 y Construcción de Edificio de Aulas y Área Administrativa, Campus UNAH-CURC, Comayagua",
  "Fecha de Inicio": "17/08/2026 09:07:00 a.m.",
  "Fecha Recepción Ofertas": "20/10/2026 10:00:00 a.m.",
  "Fecha Cierre Aclaratorias": "12/10/2026 03:30:00 p.m.",
  "Tipo Fuente": "Recursos Nacionales",
  "Fuente": "Entidad",
  "Modalidad": "Licitación pública nacional",
  "Etapa": "Recepción de Ofertas",
  "Tipo Adquisición": "Obras",
  "Lugar Recepción Ofertas": "Salón de Reuniones No. 8, Piso No. 10, Edificio Alma Mater, Ciudad Universitaria José Trinidad Reyes, UNAH",
  "Valor Pliegos": "Lps. 0.00",
  "Contacto": "Ing. René Andrés Girón Vargas 2216-6100 Ext 110550 seapi@unah.edu.hn",
  "contactoEmail": "seapi@unah.edu.hn",
  "productos": [
    {
      "UNSPSC": "81101513",
      "Descripción en Español": "Gestión de construcción de edificios",
      "Especificaciones": "El proyecto consiste en la construcción del edificio de aulas y área administrativa con un área de 2,469 m2 ...",
      "Cantidad Solicitada": "0"
    }
  ],
  "documentos": [],
  "participantes": [],
  "adjudicadoA": []
}
```

`documentos`, `participantes`, and `adjudicadoA` are empty arrays whenever the register itself has nothing in that section yet (e.g. a tender still receiving offers has no bidders/award listed) — this is a faithful reflection of the source, not a scraping gap.

## Data source

Honduras' Oficina Normativa de Contratación y Adquisiciones del Estado (ONCAE) — specifically the still-active legacy "HonduCompras 1.0" search tool at `sicc.honducompras.gob.hn`. See `CRAWLING_METHOD.md` for why this URL (not the modern-looking `honducompras.gob.hn`) is used.
