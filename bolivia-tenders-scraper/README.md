# Bolivia Government Tenders Scraper (SICOES)

Extracts public procurement notices from Bolivia's official national
e-procurement portal, **SICOES** (Sistema de Contrataciones Estatales, run
by the Ministerio de Economia y Finanzas Publicas) — the system every
Bolivian government entity is legally required to publish tenders on.

## Why use this actor

- No account, login, or API key required — the tender listing is fully
  public.
- Search by purchasing entity, keyword, contracting type (Bienes / Obras /
  Servicios Generales / Servicios de Consultoria), and national vs.
  international-modality tenders.
- Filter to only currently-open tenders, or include historical/closed ones.
- Real-time data straight from SICOES's own search backend — not a
  third-party mirror.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## Input

```json
{
  "tipo": "convNacional",
  "entidad": "",
  "objetoContrato": "",
  "soloVigentes": true,
  "tiposContratacion": ["B", "O", "S", "C"],
  "maxResults": 50,
  "proxyConfiguration": { "useApifyProxy": true }
}
```

| Field | Type | Description |
|---|---|---|
| `tipo` | string | `"convNacional"` (domestic tenders) or `"convInternacional"` (SICOES's modality flag for tenders also open to foreign bidders — still run by Bolivian entities). |
| `entidad` | string | Optional keyword to filter by purchasing government entity name (Spanish). |
| `objetoContrato` | string | Optional keyword matched against the tender's object/description (Spanish). |
| `soloVigentes` | boolean | When `true` (default), only tenders still accepting proposals. Set `false` to include historical/closed/awarded processes too. |
| `tiposContratacion` | array | Which of `B` (Bienes/Goods), `O` (Obras/Works), `S` (Servicios Generales), `C` (Servicios de Consultoria) to include. All four by default. |
| `maxResults` | integer | Caps how many tender records this run returns (1-5000). SICOES returns 10 rows per request server-side; this actor pages through as many requests as needed. |
| `proxyConfiguration` | object | Apify Proxy settings. |

## Output

One dataset item per tender. Real sample from a live run (`tipo=convNacional`,
default filters):

```json
{
  "_input": "list:tipo=convNacional",
  "_source": "S1-operacion-php",
  "_scrapedAt": "2026-08-27T16:51:44Z",
  "cuce": "26-1818-00-1684033-1-1",
  "entidad": "Gobierno Autonomo Municipal De Baures",
  "tipoContratacion": "Bienes",
  "modalidad": "ANPE",
  "objetoContratacion": "Adquisicion De Materiales E Instrumental Quirurgico Para El Centro De Salud Hugo Banzer Suarez",
  "subastaElectronica": "No",
  "fechaPublicacion": "27/08/2026",
  "fechaPresentacionPropuestas": "02/09/2026",
  "estado": "Vigente",
  "documentLabels": ["Documento Base de Contratacion", "Convocatoria"],
  "tipo": "convNacional",
  "sourceUrl": "https://www.sicoes.gob.bo/portal/contrataciones/busqueda/convocatorias.php?tipo=convNacional"
}
```

| Field | Type | Description |
|---|---|---|
| `cuce` | string | Codigo Unico de Contratacion Estatal — SICOES's unique ID for this process. |
| `entidad` | string | The purchasing government entity. |
| `tipoContratacion` | string | Bienes, Obras, Servicios Generales, or Servicios de Consultoria. |
| `modalidad` | string | SICOES's procedure code (e.g. `ANPE`, `ANPP`, `OF`, `CND1`). |
| `objetoContratacion` | string | The tender's free-text object/description (Spanish). |
| `subastaElectronica` | string | `"Si"` or `"No"` — whether this runs as an electronic reverse auction. |
| `fechaPublicacion` | string | Publication date, `dd/mm/yyyy`. |
| `fechaPresentacionPropuestas` | string | Proposal deadline, `dd/mm/yyyy`. |
| `estado` | string | e.g. `Vigente` (open), `Adjudicado` (awarded), `Desierto` (void). |
| `documentLabels` | array | Which supporting documents SICOES lists (e.g. `Convocatoria`, `Documento Base de Contratacion`) — see note below. |
| `_error` | string | Present only when a record couldn't be retrieved (`handshake_failed`, `blocked_or_transient`). |

## A note on document downloads

SICOES gates the actual PDF downloads (the process's "ficha" summary, and
the "Convocatoria"/"Documento Base de Contratacion" attachments) behind a
CAPTCHA. This actor does not solve CAPTCHAs, so it does not download these
files — it tells you which documents exist per tender (`documentLabels`)
and gives you a `sourceUrl` plus the tender's `cuce` so you can look it up
and download manually in a browser in seconds. See `CRAWLING_METHOD.md` for
the full detail.

## Notes

- Results reflect whatever is currently live on SICOES — fewer than
  `maxResults` simply means fewer tenders currently match your filters,
  nothing is padded.
- `entidad`/`objetoContrato` are free-text keyword filters, matched the same
  way SICOES's own search form matches them (Spanish, partial match).
- `robots.txt` on this host returns a WAF signature block from every client
  tested (no content retrievable by any means) — this is a documented
  infrastructure quirk, not a bot-exclusion policy; see
  `CRAWLING_METHOD.md`.

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ecuador
(SERCOP OCDS), Honduras, Nigeria (NOCOPO), Ghana (GHANEPS), Zambia (ZPPA),
Jamaica (GOJEP), Uganda (EGP), Papua New Guinea (NPC), Sierra Leone (NPPA),
Nepal (Bolpatra), Eswatini (ESPPRA), Rwanda (Umucyo), Namibia (CPBN),
Trinidad & Tobago (ProcureTT), Botswana (ministry sites), Malawi (MANEPS/
PPDA), Tanzania (NeST), Bangladesh (CPTU), Pakistan (PPRA-EPMS), Vietnam
(VNEPS), Sri Lanka (Treasury), Zimbabwe (PRAZ), Liberia (PPCC), Madagascar
(ARMP), Cameroon (ARMP), Algeria, Indonesia, Ethiopia, DR Congo, Tunisia,
Guatemala, and Angola.
