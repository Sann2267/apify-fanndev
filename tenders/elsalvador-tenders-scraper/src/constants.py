"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): El Salvador's official e-procurement system is
COMPRASAL (`www.comprasal.gob.sv`), run by DINAC (Direccion Nacional de
Compras Publicas -- the JS bundle references `dinac.gob.sv` and
`comprasal.dinac.gob.sv` as sibling domains). This is a client-rendered Vue.js
SPA -- there is no server-rendered HTML and no OCDS/RSS feed -- but its
`app.<hash>.js` bundle hardcodes a full, versioned, unauthenticated public
REST API under `/api/v1/publico/...` (found by grepping the downloaded bundle
for `"/api/v1/publico"` path literals, then cross-referencing the exported
`ProcesosPublicos` service object's method-name -> URL map). No reverse
engineering of opaque tokens or WAF bypass was needed.

**`robots.txt` does not exist as a real file.** `GET /robots.txt` returns
HTTP 200 with `Content-Type: text/html` -- it is the SPA's own
`index.html` shell (Vue Router's history-mode catch-all serving every
unmatched path), not an actual robots.txt. There is nothing to disallow and
nothing naming Claude/anthropic-ai/any bot, because no robots.txt exists at
all.

**Viewing requires zero authentication.** Every endpoint below was fetched
with a bare `User-Agent` header only, no cookies, no bearer token -- and all
returned clean `200 application/json`. The SPA's own HTTP client
(`Lc` in the bundle) only attaches an `Authorization: Bearer` header when a
`token_procesos_libres` value already exists in `localStorage` -- i.e. it is
opportunistic, not required, for these `/publico/` routes. Third-party
summaries describe registering with a NIT/passport via RUPES (Registro Unico
de Proveedores del Estado) -- that registration is for SUBMITTING a bid, not
for browsing tenders; confirmed independently since every list/detail/catalog
call below succeeded fully logged-out.

**WAF**: the site is Cloudflare-fronted (`Server: cloudflare` header) but no
challenge was encountered on any request -- plain `urllib`, no TLS
impersonation, got clean 200s. `curl_cffi` `chrome124` is used anyway for
portfolio-wide consistency and future resilience.

## The public API surface

Two list endpoints cover the two things worth scraping, plus catalogs and a
per-process detail endpoint:

1. `GET /api/v1/publico/obtener/procesos/disponibles` -- **all currently
   open/active processes** in ONE response, a bare JSON array (not wrapped
   in `{data: ...}` like every other endpoint here -- confirmed, not a bug).
   365 records during recon (~1MB). Each record embeds its own stage/timeline
   history (`etapas`, `EtapaPorProcesos` -- start/end datetime per stage:
   publication, offer submission, clarifications, addenda, offer receipt,
   opening). No pagination is needed or offered for this endpoint. It DOES
   accept a real, verified server-side filter: `?institucion=<id>` (the
   institution's numeric id from the catalog below) -- confirmed by checking
   the returned institution ids actually narrow (365 -> 18 for one id).
   `per_page`/`limit`/`id_institucion` are silently ignored (decoys) --
   verified by requesting them and observing an unchanged 365-row response.

2. `GET /api/v1/publico/obtener/procesos/publicos?page=<n>&per_page=<m>` --
   the **historical/awarded-contract ledger**, real cursor-style pagination
   confirmed working (`page`/`per_page` genuinely advance -- record ids
   monotonically decrease from page 1 through page 5000+ during recon, i.e.
   many tens of thousands of records exist). Each row already embeds the
   AWARDED SUPPLIER and, remarkably, a declared **beneficial owner**
   (`beneficiario`: full name broken into name parts, plus nationality) --
   rare transparency data, matching the pattern already seen in this
   project's tender vertical for Madagascar. **`institucion`/`fecha_inicio`/
   `fecha_fin`/`nombre` query params on THIS endpoint are decoys** -- verified
   by requesting `?institucion=31` and finding the returned rows belong to
   several different institution ids, not just 31. Only `page`/`per_page`
   have a real effect here. This actor is honest about that: no server-side
   filter is exposed as a working input for `awarded` mode, only client-side
   post-filtering on the institution name after fetching.

3. `GET /api/v1/publico/obtener/detalle/procesos/publicos/<id>` -- full
   detail for ONE process, keyed by the process's own **numeric internal
   `id`** (e.g. `135800`) -- NOT the human-readable `codigo_proceso` string
   (e.g. `"3303-2026-P0282"`), confirmed: passing the code string or a
   nonexistent numeric id both return `HTTP 500` with a clean JSON body
   `{"error":{"message":"...", "code":400}}` -- a real (if oddly-coded)
   validation error, not a crash or a WAF page. The numeric `id` must come
   from a prior `open`/`awarded` list record (`id` field in `open` mode,
   `proceso_compra.id` in `awarded` mode).

4. Read-only catalogs, all `{"data": [...]}`-wrapped and small: `.../
   obtener/instituciones` (institution id/name/code -- ~39KB, used here to
   resolve a human-typed institution-name substring to its numeric id for
   `open` mode's real `institucion=<id>` filter), `.../obtener/modalidades`
   (procurement modality catalog), `.../obtener/estados` (process status
   catalog, only 5 values).

`GET .../obtener/documentos/procesos/publicos/<id>` (attached documents) was
tried against both a currently-open and an awarded process id and got a
clean `404 {"message":"Recurso no encontrado"}` both times -- deferred as
out of scope for this actor rather than guessed at further; not needed for
either core mode.

## Encoding note

Response bytes are valid UTF-8 (`Content-Type: application/json;
charset=utf-8`, verified at the byte level: `\\xc3\\xb3` for `o-acute`, the
correct UTF-8 encoding). Any `�` seen while debugging in a Windows terminal
is purely a console codepage display artifact (same conclusion reached
independently while building `honduras-tenders-scraper`) -- no special
decoding is needed in this actor.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.comprasal.gob.sv"
API_BASE = f"{BASE_URL}/api/v1/publico"

OPEN_URL = f"{API_BASE}/obtener/procesos/disponibles"
AWARDED_URL = f"{API_BASE}/obtener/procesos/publicos"
DETAIL_URL = f"{API_BASE}/obtener/detalle/procesos/publicos"
INSTITUTIONS_URL = f"{API_BASE}/obtener/instituciones"
MODALITIES_URL = f"{API_BASE}/obtener/modalidades"
STATES_URL = f"{API_BASE}/obtener/estados"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-SV,es;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/comprasalweb/procesos",
    "Origin": BASE_URL,
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
REQUEST_TIMEOUT = 60

AWARDED_PAGE_SIZE = 100
MAX_AWARDED_PAGES_SAFETY_CAP = 200  # 200 * 100 = 20,000 records ceiling per run
