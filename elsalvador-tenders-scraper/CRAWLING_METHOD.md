# Crawling method

## The target: COMPRASAL, run by DINAC

El Salvador's mandatory national e-procurement system is **COMPRASAL**
(`www.comprasal.gob.sv`), operated by DINAC (Direccion Nacional de Compras
Publicas -- confirmed from sibling-domain references, `dinac.gob.sv` and
`comprasal.dinac.gob.sv`, inside the site's own JS bundle). Every institution
subject to El Salvador's LACAP (Ley de Adquisiciones y Contrataciones de la
Administracion Publica) is required to publish through it, so this is the
single authoritative source, not one of several competing portals.

## Market check before building

Verified no existing Apify Store competitor for El Salvador/COMPRASAL
(`python api-search-actors.py --query "el salvador tender"` and
`--query "COMPRASAL"` both returned only unrelated noise -- generic
worldwide/EU tender aggregators, MercadoLibre scrapers, etc.). Also verified
the `scrapers_lat` seller cluster -- already confirmed dominant across most
of Latin America's tender portals (Peru SEACE, Colombia SECOP, Mexico
CompraNet, Argentina Comprar, Paraguay DNCP, Chile Mercado Publico) in this
project's prior tender-vertical sessions -- does **not** have an El Salvador
product: its public actor list (`python api-search-actors.py --query "SECOP
Colombia"`, cross-referencing every `scrapers_lat`-authored hit) covers
Colombia/Peru/Mexico/Paraguay/Bolivia/Canada/Singapore/Taiwan/EU, no Central
America. El Salvador is open.

## Access checks -- all clean

- **`robots.txt` does not exist as a real file.** `GET
  https://www.comprasal.gob.sv/robots.txt` returns `HTTP 200` with
  `Content-Type: text/html` and a body that is literally the site's own
  `index.html` SPA shell (Vue Router history-mode serves every unmatched
  path this way). There is no robots.txt to restrict anything, and
  therefore nothing naming Claude/anthropic-ai/any bot either.
- **Viewing requires zero login.** Every endpoint used by this actor was
  fetched cold -- no cookies, no bearer token, no prior request on the
  session -- and returned a clean `200 application/json`. The SPA's own
  HTTP client only *attaches* an `Authorization: Bearer` header when a
  `token_procesos_libres` value already exists in `localStorage`; it never
  requires one for the `/api/v1/publico/...` routes this actor calls.
  Third-party overviews describe registering with a NIT/passport via RUPES
  (Registro Unico de Proveedores del Estado) to participate -- that's for
  **submitting a bid**, not for browsing/reading tenders, confirmed
  independently by successfully calling every endpoint below fully
  logged-out.
- **WAF**: Cloudflare-fronted (`Server: cloudflare`) but no challenge was
  ever encountered -- even a bare `urllib.request` call with no TLS
  impersonation and a generic User-Agent got clean 200s on every endpoint.
  `curl_cffi` `chrome124` is used anyway for portfolio-wide consistency.

## Finding the API -- reading the SPA's own JS bundle, no OCDS/RSS available

COMPRASAL is a pure client-rendered Vue.js SPA (no server-rendered HTML, no
OCDS feed, no RSS). The approach:

1. Fetched the homepage, found its two script tags: `chunk-vendors.<hash>.js`
   and `app.<hash>.js`.
2. Downloaded `app.<hash>.js` (~1.3MB minified) and grepped it for every
   quoted `"/api/..."`-shaped string literal -- this immediately surfaced
   the site's ENTIRE REST API surface (hundreds of endpoints, most of it the
   back-office workflow for procurement officers: creating processes,
   evaluating bids, managing appeals, etc.).
3. Filtered that list to the `/api/v1/publico/...` prefix -- COMPRASAL's own
   naming convention for its public-facing routes -- and cross-referenced
   against the exported services object in the same bundle (grep for
   `ProcesosPublicos:` found the minified variable holding the service
   object; grepping for `el={obtener` -- the object's own opening literal --
   printed the full method-name -> URL map in one shot). This confirmed each
   endpoint's HTTP method (all `GET`) without needing to guess.
4. Every candidate endpoint was then verified empirically with a plain
   request (see below) rather than trusted from the JS alone -- several
   turned out to have quirks (decoy/ignored query params, a non-existent
   documents sub-resource) only visible by actually calling them.

## The three endpoints this actor uses

### 1. `GET /api/v1/publico/obtener/procesos/disponibles` -- open tenders

Returns **all currently open/active processes in one response** -- a bare
JSON array (not wrapped in `{data: ...}` like every other endpoint here;
confirmed deliberately, not a bug to normalize away). 365-368 records
during recon (~1MB), each embedding its own full stage timeline (`etapas`)
and current stage (`EtapaPorProcesos`) with start/end datetimes.

No pagination is offered or needed. It DOES accept one real, verified
server-side filter, `?institucion=<id>` (the institution's numeric catalog
id) -- confirmed by requesting `?institucion=78` (Instituto Salvadoreno del
Seguro Social) and getting a genuinely narrowed 18-of-365 response, with
every returned row actually belonging to that institution.
`per_page`/`limit`/`id_institucion` were all tried and are silently
ignored (decoys) -- confirmed by requesting them and getting an unchanged
365-row response back every time. This actor resolves a user-typed
institution-name substring to its numeric id via the
`/obtener/instituciones` catalog first (mirroring the analogous resolver in
`honduras-tenders-scraper`), falling back to a client-side substring match
on each row's own `institucion` string if the name doesn't match anything
in the catalog.

### 2. `GET /api/v1/publico/obtener/procesos/publicos?page=<n>&per_page=<m>` -- awarded/historical ledger

Real, working `page`/`per_page` pagination -- confirmed by comparing record
`id`s across distant pages (page 1: ids ~491138 down to page 5000: ids
~426694, monotonically decreasing) -- this is a genuinely huge historical
dataset, at minimum tens of thousands of records.

Each row already embeds the awarded amount (`monto`), the parent process
(`proceso_compra`), the winning supplier (`proveedor`, including trade name
and shareholders/`accionistas`), and -- the standout find -- a declared
**beneficial owner** (`beneficiario`: full name broken into parts, plus
nationality) for the awarded company. This matches the pattern already
documented for `madagascar-tenders-scraper` in this project's tender
vertical: rare, genuine ownership-transparency data most countries in this
vertical do not publish.

**Important, honestly-documented limitation**: `institucion`, `fecha_inicio`,
`fecha_fin`, and `nombre` query parameters on THIS endpoint are decoys.
Verified by requesting `?institucion=31` and finding the 10 returned rows
belonged to institution ids 31, 12, 122, and 5998 -- i.e. the parameter had
zero effect on server-side filtering. This actor does not pretend otherwise:
its `entidad` input for `awarded` mode is applied **client-side**, after
fetching each page, by substring-matching `institucion.nombre` -- meaning a
search for a rarely-awarded institution can require scanning many pages
(bounded by `MAX_AWARDED_PAGES_SAFETY_CAP` in `constants.py`).

### 3. `GET /api/v1/publico/obtener/detalle/procesos/publicos/<id>` -- single-process detail

Keyed by the process's own **numeric internal `id`** (e.g. `135800`) --
**not** the human-readable `codigo_proceso` string (e.g.
`"3303-2026-P0282"`). Confirmed: passing the code string, or a nonexistent
numeric id, both return `HTTP 500` with a clean, structured JSON body
(`{"error":{"message":"Error al cargar el detalle de proceso publico.",
"code":400}}`) -- COMPRASAL's own app-level validation error, not a
crash/WAF page, so this actor treats `500` the same as any other clean
"not found"-shaped response: not retried, surfaced as an `_error` record.
The numeric id must come from a prior `open`-mode record's own `id` field,
or an `awarded`-mode record's `proceso_compra.id` field -- there is no way
to construct it from the human-readable code.

## Endpoints tried and NOT used

`GET /api/v1/publico/obtener/documentos/procesos/publicos/<id>` (attached
documents) was tried against both a currently-open and an awarded process id
and got a clean `404 {"message":"Recurso no encontrado"}` both times.
Deferred as out of scope rather than guessed at further -- neither of this
actor's two core modes needs it, and further reverse-engineering (maybe a
different id shape, or a POST) wasn't worth the time for a nice-to-have.

Read-only catalogs (`/obtener/instituciones`, `/obtener/modalidades`,
`/obtener/estados`) were fetched and confirmed clean but are used only
internally (institution-name resolution) rather than exposed as their own
actor mode -- they're small, static reference lists, not scrape targets in
their own right.

## Encoding note

Response bytes are valid UTF-8 (`Content-Type: application/json;
charset=utf-8`, verified at the byte level -- `\xc3\xb3` for the accented
"o" in "Adquisicion", the correct UTF-8 sequence). Real captured output
in `README.md` renders the accents correctly. Any `?`/mojibake seen while
debugging directly in a Windows terminal was purely a console codepage
display artifact, not a real data problem -- the same conclusion
independently reached while building `honduras-tenders-scraper`.
