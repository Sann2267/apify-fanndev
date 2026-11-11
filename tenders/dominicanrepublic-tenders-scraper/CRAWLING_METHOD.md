# Crawling Method — Dominican Republic Government Tenders (DGCP)

**Last verified:** 2026-08-27

## Target discovery — two separate DGCP systems, only one of which is public

The Dominican Republic's public procurement is regulated by **DGCP**
(Direccion General de Contrataciones Publicas), a dependency of the Ministry
of Finance created by Law No. 340-06. DGCP runs (at least) two distinct web
systems, and they behave completely differently:

1. **"Comprasdominicana" — the transactional/bidding portal**
   (`comunidad.comprasdominicana.gob.do`) — where suppliers register, submit
   offers, and institutions administer procurement processes. Confirmed by
   direct fetch: this host returns a **hard 401 "Access is denied due to
   invalid credentials"** login page on every path tested, including
   `/robots.txt`. The bare `comprasdominicana.gob.do` domain (no `www.`/
   `comunidad.` prefix) additionally has an **expired TLS certificate**,
   consistent with the platform being flagged as "under maintenance" in
   independent search results at recon time.
2. **DGCP's own open-data portal**
   (`datosabiertos.dgcp.gob.do`) — a **separate, explicitly public** React
   SPA plus REST API, built by DGCP's own "Departamento de Ciencia de
   Datos" specifically so third parties (MSMEs, researchers, journalists,
   civil society) can query procurement data without an account. DGCP is
   also on record (via a 2020 press release and the Open Contracting
   Partnership's own Data Registry, `data.open-contracting.org/en/
   publication/22`) as having published an OCDS (Open Contracting Data
   Standard) bulk dataset since April 2020 — this REST API is the platform's
   current, actively maintained incarnation of that same public-data
   commitment.

**This actor only uses system #2.** The login wall on system #1 is a
BIDDING system's account gate (submitting/administering offers), not a
block on viewing procurement data — exactly the "fine if only BIDDING
requires login" carve-out. All of the actual tender/contract/offer *data*
this actor needs lives on the open-data platform and needs no account.

## robots.txt — clean on every host that matters

- `www.dgcp.gob.do/robots.txt` — a real robots.txt, no blanket
  `Disallow: /`, no mention of `Claude`/`ClaudeBot`/`anthropic-ai`/`GPTBot`/
  any AI crawler under any `User-agent:` group (checked every group, not
  just the last one before a `Disallow:`). It only excludes admin-ish
  paths unrelated to this actor (`/calendar/`, `/foro/`, `/mail/`,
  `/sign-in/`, `/sign-up/`, old-site archive paths).
- `datosabiertos.dgcp.gob.do/robots.txt` — there is **no actual robots.txt
  file**: the request returns HTTP 200 with the SPA's `index.html` (a
  React app that catches all unmatched routes client-side), not a
  robots-format text response. No crawl policy is published for this host
  at all, which is the default-allow case, not a block.

## No WAF/TLS gate observed

Every request in this actor's recon and testing — `robots.txt` probes, the
SPA's JS bundle, and every `/api-dgcp/v1/*` endpoint call — succeeded on the
**first attempt** with plain `curl_cffi` `chrome124` impersonation, no
retries, no challenge page, no Cloudflare/Akamai/PerimeterX/DataDome
signature of any kind. `datosabiertos.dgcp.gob.do` does load a Cloudflare
Insights beacon script client-side (`static.cloudflareinsights.com/beacon.min.js`),
indicating Cloudflare sits in front as a CDN/analytics layer, but it is not
configured to challenge or block plain HTTP clients on this host.

## No login required to view or query data

Confirmed live: every endpoint this actor uses (`/procesos`, `/contratos`,
`/ofertas`, `/procesos/articulos`) returned real, current data (records
dated 2026-08-26, one day before this actor was built) with **no
Authorization header, no API key, no cookies, no session handshake of any
kind** — a bare `GET` with an ordinary browser User-Agent is sufficient.
This matches the platform's own stated purpose ("cualquier usuario ...
puede conectarse en tiempo real a las oportunidades", from the open-data
landing page).

## Finding the API — reverse-engineered from the SPA's own bundled docs page

`datosabiertos.dgcp.gob.do` is a Vite/React SPA. Its main JS bundle
(`/assets/index-*.js`) contains a hardcoded `baseURL:
"https://datosabiertos.dgcp.gob.do/api-dgcp/v1"` for its Axios client, and a
route (`/apidgcp/docs`) that lazy-loads a **complete Swagger-style API-docs
page as its own JS chunk**
(`/assets/api-dgcp-schema-*.js`) — effectively an embedded, unauthenticated
OpenAPI spec describing every GET endpoint, every query parameter, and its
description, in Spanish. This is a much cleaner discovery path than the
"reverse-engineer from network trace" pattern used for most SPA targets in
this portfolio (e.g. Tanzania NeST): the schema chunk documents the full API
surface without needing to trigger and capture live requests first, and was
fetched and parsed directly (not screen-scraped).

Confirmed live against the running API, not just the docs text: 7 GET
endpoints under `/api-dgcp/v1` —

| Endpoint | Purpose | Used by this actor |
|---|---|---|
| `/procesos` | Tender/procurement processes | mode=list, and the base of mode=detail |
| `/procesos/articulos` | Requested line items for a process | mode=detail enrichment |
| `/contratos` | Awarded contracts | mode=detail enrichment |
| `/ofertas` | Offers/bids submitted | mode=detail enrichment |
| `/pacc` + `/pacc/adquisiciones` | Annual Procurement Plan (PACC) | not used |
| `/proveedores` | Registered supplier directory | not used |
| `/unidades_compra` | Buyer/purchasing-unit directory | not used |
| `/catalogo` | Standard item catalog (UNSPSC) | not used |

This actor focuses on the tender lifecycle (`/procesos` +
`/contratos`/`/ofertas`/`/procesos/articulos`); the supplier directory,
buyer directory, and catalog endpoints are separate reference-data resources
better suited to a future dedicated actor if ever needed.

### Response envelope — consistent across all 7 endpoints, confirmed live

```json
{
  "code": 200, "hasError": false,
  "payload": { "content": [ /* array of rows, or null when zero match */ ] },
  "page": 1, "limit": 100, "totalResults": 624514, "pages": 312257
}
```

A filter matching **zero** rows still returns **HTTP 200** with
`payload.content: null` — never an empty array, never a 4xx. This actor's
client treats a `null`/missing `content` as zero rows, not as an error
(`_get()` only raises when the transport itself fails, the body isn't valid
JSON, or the envelope's own `hasError` flag is `true`).

`limit` is silently capped upstream at **1000** — requesting `limit=99999`
comes back with `"limit": 1000` and exactly 1000 rows (confirmed live), not
an error. This actor's client mirrors that cap client-side too (`MAX_PAGE_LIMIT
= 1000` in `constants.py`) so it never sends a request the API would silently
downgrade.

### `/procesos` — the list endpoint

Query params (all optional, confirmed against the schema and tested live):
`page`, `limit`, `proceso` (exact code match), `unidad_compra` (buyer's
internal integer code), `modalidad`, `estado`, `mipyme` (bool),
`mipyme_mujer` (bool), `startdate`/`enddate` (both `YYYY-MM-DD`, filtering
on `fecha_publicacion`). Omitting every filter browses the full public
archive — 624,514 processes as of 2026-08-27, refreshed "every 8 hours from
DGCP's Data Warehouse" per the docs page's own description (00:00, 07:00,
14:00, 21:00 Dominican time) — this is a read replica of DGCP's internal
data warehouse, not the live transactional database, so very-recent changes
on the bidding portal can lag by up to ~8 hours here.

**Ordering quirk, reported honestly rather than assumed away:** the docs
describe `/procesos` as "por orden de fecha publicacion" (ordered by
publish date). Confirmed live across two consecutive pages with no filter:
**page-to-page ordering is descending** (page 1's rows are all more recent
than page 2's), but **within a single page, rows were not in strict
descending order** (timestamps went 17:20 → 17:30 → 17:58 → 18:00 → 18:00
across page 1's 5 rows, i.e. ascending). This actor does not depend on
strict per-row ordering for correctness: pagination trusts the upstream
`pages`/`totalResults` counters (always present in the envelope, confirmed
live) rather than assuming monotonic dates, and a caller who needs a
reliable date cutoff should use `startdate`/`enddate` rather than relying on
page position.

### `/contratos`, `/ofertas`, `/procesos/articulos` — detail enrichment

All three accept a `proceso` filter (exact `codigo_proceso` match) plus
`page`/`limit`, same envelope shape. Confirmed live on two different
processes:

- A process still open for bidding (`estado_proceso: "Proceso publicado"`)
  returns `contratos: null` and `ofertas: null` — no award yet, not an
  error.
- An already-awarded process (`HFMP-DAF-CD-2026-0442`) returns a full
  contract row: winning supplier name and registry number
  (`razon_social`/`rpe`), contracted value (`valor_contratado`), status
  (`estado_contrato`/`estado_adjudicacion`), and payment terms
  (`metodo_pago`/`plazo_pago_factura`) — genuine transparency data, not
  summarized/redacted.
- `/procesos/articulos` returns UNSPSC-classified line items with
  quantities and estimated unit/total pricing — useful for anyone analyzing
  what's actually being procured, not just the headline process metadata.

`mode=detail` in this actor fetches `/procesos` (to confirm the code exists
— `RecordNotFound` if not, since an unknown code also comes back
`content: null`), then `/contratos`+`/ofertas`+`/procesos/articulos`
concurrently via `asyncio.gather`, and bundles all four into one record —
DGCP's own API has no server-side "compiled record" view joining these,
exactly like this portfolio's other multi-endpoint tender integrations
(Ecuador SERCOP's `record` OCDS release history, Nigeria NOCOPO).

## Encoding — a false alarm, not a real data issue

Printing API responses directly in a Windows terminal (cp1252 code page)
showed `�` in place of accented characters (e.g. `ADQUISICI�N`). Verified
this is **purely a terminal-display artifact, not corrupted upstream data**:
the raw response bytes for that same field are valid UTF-8
(`\xc3\x93` = `Ó`), and writing the decoded string to a UTF-8 file round-trips
correctly to `ADQUISICIÓN`. `curl_cffi`'s `.json()` already decodes UTF-8
correctly; this actor pushes data through Apify's dataset API as native
Python strings (`Actor.push_data`), which serializes as UTF-8 JSON
regardless of the host terminal's code page, so this has no effect on
actual output.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default. No
WAF/fingerprint gate was observed on any path tested (see above) — no
country-specific residential proxy pin was needed either (contrast with
Indonesia/Ecuador in this vertical's Babak 28 round): every request
succeeded from this session's ordinary network without a proxy.

## Market check

Searched the Apify Store (`api-search-actors.py --query "dominican
republic tenders"`, `"compras dominicana"`, `"DGCP dominicana"`) — no real
competitor found; all hits were unrelated (OLX, MercadoLibre, Zillow,
generic job-board scrapers). The seller `scrapers_lat`, confirmed to
already own most major Latin American national tender platforms (SEACE
Peru, SECOP Colombia, CompraNet Mexico, Comprar Argentina, DNCP Paraguay,
Mercado Publico Chile — per this portfolio's Babak 28 findings), was
checked independently via their public storefront (`apify.com/scrapers_lat`,
699 public actors) and their own catalog site (`scrapers.lat`) — no
Dominican Republic-specific tender/procurement actor was found in either
listing, only a generic MercadoLibre scraper that happens to support `DO`
as one of many countries (unrelated e-commerce data, not tenders). This
independently confirms the task brief's own prior finding that the
Dominican Republic is not yet in that seller's tender-vertical portfolio.
