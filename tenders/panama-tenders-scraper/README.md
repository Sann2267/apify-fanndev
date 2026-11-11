# Panama Government Tenders Scraper

Get Panama's official government procurement tenders (licitaciones) straight from DGCP's own public open-data feed — buyer, tender object, dates, status, line items, awards, signed-contract documents, and supplier info. No account, login, or API key needed.

## Why use this actor

- No account, login, or API key needed — this is Panama's own public transparency data
- Get the full picture per tender: buyer institution, tender title/description/status, procurement method, award value and line items (with UNSPSC classification), supplier name and tax ID, and direct download links to signed contract documents
- Look up any tender by its OCDS ID (`ocid`), or page through the general feed
- Real, current Panama government spending data — covers goods, services, and works procured under Panama's PanamaCompra system

## How it works

1. Choose `list` mode to page through the tender feed, or `detail` mode to fetch specific tenders by their OCDS `ocid`.
2. The actor reads Panama's DGCP (Direccion General de Contrataciones Publicas) public OCDS API at `panamacompraencifras.gob.pa`.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

**Note on `list` mode ordering:** the upstream feed has no date or keyword filter — it's a flat paginated dump, not a search API (see `CRAWLING_METHOD.md` for the recon that confirmed this). Each `list` run returns a page of tenders in whatever order the feed itself uses. To see more of the feed across multiple runs (instead of the same first page every time), copy the `_nextCursor` value from the last record of one run into the next run's `startCursor` input.

## Input

**List mode** — page through the feed:

```json
{
  "mode": "list",
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Detail mode** — fetch specific tenders (use an `ocid` from a `list` run):

```json
{
  "mode": "detail",
  "ocids": ["ocds-emvi6n-2024-6-15-01-08-CM-000025-1"]
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `list` (page the feed) or `detail` (fetch specific OCIDs). Default `list`. |
| `maxResults` | integer | *(list)* Max tenders to return. Default 50, max 500 (the feed returns 10 per page). |
| `startCursor` | string | *(list)* Optional. Resume from a previous run's `_nextCursor` value instead of starting from the beginning of the feed. |
| `ocid` | string | *(detail)* A single OCDS ocid to fetch. |
| `ocids` | array | *(detail)* Multiple OCDS ocids to fetch in one run. |
| `maxConcurrency` | integer | Parallel ocid fetches in `detail` mode. Default 3, max 6. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

This is real output from a `list` run (`maxResults: 1`):

```json
{
  "_input": { "startCursor": null },
  "_source": "S1-ocds-records-api",
  "_scrapedAt": "2026-08-27T16:47:29Z",
  "id": "ocds-emvi6n-2024-6-15-01-08-CM-000025-1-2024-07-23T14:20:54-05:00",
  "date": "2024-05-27T09:34:12-05:00",
  "ocid": "ocds-emvi6n-2024-6-15-01-08-CM-000025-1",
  "buyer": {
    "id": "25033931-3-2017",
    "name": "Centro Internacional de Estudio Políticos y Sociales-AIP Panamá"
  },
  "tender": {
    "id": "2024-6-15-01-08-CM-000025",
    "title": "Adquisición de Software Profesional Rotator Survey para encuesta del CIEPS",
    "description": "Adquisición de Software Profesional Rotator Survey para encuesta del CIEPS. Que incluya el Plan Research Teams...",
    "status": "complete",
    "statusDetails": "Adjudicado",
    "procurementMethod": "open",
    "procurementMethodDetails": "Compra menor hasta 10,000",
    "mainProcurementCategory": "services",
    "procuringEntity": { "id": "68", "name": "Departamento De Compras - CIEPS" },
    "uri": "https://www.panamacompra.gob.pa/Inicio/#/pliego-de-cargos/procesos-generados/..."
  },
  "awards": [
    {
      "id": "2024-6-15-01-08-CM-000025",
      "value": { "currency": "PAB", "amount": 990, "valueAddedTaxIncluded": false },
      "status": "active",
      "statusDetails": "Adjudicado",
      "items": [
        {
          "classification": { "scheme": "UNSPSC", "id": "43232305", "description": "Software de creación de informes de bases de datos" },
          "description": "Adquisición de Software Profesional Rotator Survey para encuesta del CIEPS...",
          "quantity": 1
        }
      ],
      "suppliers": [ { "id": "PE144528", "name": "Raul Andres Posada Maldonado" } ]
    }
  ],
  "contracts": [
    {
      "id": "2024-6-15-01-08-CM-000025",
      "value": { "currency": "PAB", "amount": 990, "valueAddedTaxIncluded": false },
      "status": "active",
      "documents": [
        {
          "documentType": "contractSigned",
          "title": "OC 310-2024 Software Rotator Profesional Survey Encuesta 2024",
          "url": "https://apisv3.panamacompra.gob.pa/procesos-contratacion-archivos/v2/ocds-3561AB3E-6D1C-EF11-80EA-0017A477FC74",
          "format": "application/pdf"
        }
      ]
    }
  ],
  "sources": [ { "id": "panamacompra_v3", "name": "PanamaCompra V3", "url": "https://www.panamacompra.gob.pa/" } ]
}
```

And real output from `detail` mode on a tender still awaiting an award (a lookup with no `_error`, just fewer populated sections):

```json
{
  "_input": "ocds-emvi6n-2024-6-15-01-08-CM-000021-1",
  "_source": "S1-ocds-record-detail",
  "_scrapedAt": "2026-08-27T16:47:59Z",
  "ocid": "ocds-emvi6n-2024-6-15-01-08-CM-000021-1",
  "buyer": { "id": "25033931-3-2017", "name": "Centro Internacional de Estudio Políticos y Sociales-AIP Panamá" },
  "tender": {
    "title": "Servicios de auditoria de los estados financieros 2023 del CIEPS",
    "status": "complete",
    "statusDetails": "Adjudicado"
  },
  "awards": [ { "value": { "currency": "PAB", "amount": 3240 }, "suppliers": [ { "name": "Nexia Auditores (Panama)" } ] } ]
}
```

A lookup for an ocid that doesn't exist returns, instead:

```json
{ "_input": "not-a-real-ocid", "_source": "none", "_scrapedAt": "...", "_error": "not_found", "_errorDetail": "no tender found for this ocid" }
```

## Data source

Panama's Direccion General de Contrataciones Publicas (DGCP) — specifically its public OCDS (Open Contracting Data Standard) transparency API at `panamacompraencifras.gob.pa`, licensed CC-BY 4.0. See `CRAWLING_METHOD.md` for why this host (not the main `panamacompra.gob.pa` portal, which disallows crawling in its `robots.txt`) is used, and for the feed's pagination/ordering quirks.
