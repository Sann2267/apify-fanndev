# Crawling Method — Bolivia Government Tenders (SICOES)

**Last verified:** 2026-08-27

## Target discovery

Bolivia's national e-procurement portal is **SICOES** (Sistema de
Contrataciones Estatales), run by the Ministerio de Economia y Finanzas
Publicas at `www.sicoes.gob.bo`, governed by Ley No. 1178 (Administracion y
Control Gubernamentales). Confirmed via the official portal itself plus its
own published "Manual de Operaciones del Sistema de Contrataciones
Estatales" (hosted at `economiayfinanzas.gob.bo`) — SICOES is where every
public entity in Bolivia is required to publish procurement notices
(Convocatorias). This is the only official source used by this actor —
third-party mirror/aggregator sites turned up in search (`sicoes.info`,
`licitaciones.com.bo`, `sicoesmonitor.com`, `infosiscon.com`) were not used.

## Market check

Searched the Apify Store for "Bolivia tenders", "SICOES", and "Bolivia
procurement" before building. The only existing `scrapers_lat` (the seller
cluster confirmed to already own most major LatAm tender portals — Peru
SEACE, Colombia SECOP, Mexico CompraNet, Argentina Comprar, Paraguay DNCP,
Chile Mercado Publico) actor touching Bolivia is `seprec-bolivia-scraper`,
which scrapes **SEPREC** (the business/company registry) — a completely
different system, not tenders. No SICOES/Bolivia-tenders actor was found
from any seller. Confirms Babak 28's note that Bolivia was unverified but
likely open — independently verified here.

## robots.txt — WAF blocks the literal path, not a bot policy

Every attempt to fetch `https://www.sicoes.gob.bo/robots.txt` — plain
`curl`, `curl_cffi` (chrome124/chrome131/safari17_0/edge101), with and
without a session, over HTTP and HTTPS, with a session cookie, with full
browser-style headers — returns the same signature-based WAF block:

```
HTTP/1.1 403
<html><body>
<h1>Access Denied</h1><p>Signature ID: 1030010002<br>...</p>
</body></html>
```

curl_cffi's TLS-impersonated requests to this exact path even get the raw
TCP connection reset (`CurlError 56: Connection closed abruptly`) rather
than a clean 403. No Wayback Machine snapshot of this robots.txt has ever
been captured (`archive.org/wayback/available` returns an empty
`archived_snapshots`), so there is no historical version to check either.
**No robots.txt content is retrievable from any client, by any method** —
consistent with a WAF signature keyed to the literal string `robots.txt`
(the same "block the well-known recon path itself" pattern documented for
Ecuador's NetScaler AppFW in that actor's CRAWLING_METHOD.md), not a
deliberately published `Disallow` policy naming any bot. Every other path
tested on the same host — the homepage, the search page, every static JS/CSS
asset, the JSON listing endpoint — returns clean 200s with no WAF challenge
at all, across all four TLS profiles. This is reported transparently rather
than treated as a silent pass.

## No login required to browse — CAPTCHA only gates document downloads

The homepage, the Convocatorias search page, and the JSON search results
are all reachable with no account. A `<script src=".../recaptcha/api.js">`
tag is present sitewide but unused on any page tested. The **only** CAPTCHA
encountered live is a Cloudflare Turnstile widget on
`/portal/contrataciones/ficha/fichaProceso.php` — the page that generates a
one-page PDF "ficha" summary for download — and the same download-gating
pattern (a scrambled-hex image CAPTCHA, per `downloadserpub.min.js`) applies
to the raw "Convocatoria"/"Documento Base de Contratacion" PDF attachments
linked from each search result row. This actor does not attempt either
download — it matches this portfolio's "fine if only BIDDING/downloading
requires an account or CAPTCHA" carve-out, since **browsing/searching the
tender listing itself needs neither.**

## The real obstacle: a deliberately obfuscated, session-scoped SPA shell

This was the hard part of this build, worth documenting in full since it is
a genuinely unusual anti-scraping design (not just a WAF or a login wall):

1. **Every `/portal/*.php` URL renders the same homepage shell on a bare
   GET/POST.** `www.sicoes.gob.bo/portal/index.php` and
   `.../busqueda/convocatorias.php?tipo=convNacional` return byte-identical
   dashboard HTML (32,581 bytes) regardless of query string or HTTP method.
   This looks like a client-side-router SPA at first, but it is not one —
   there is no `fetch`/`XHR`-based router anywhere in the JS bundle.
2. **The real router is `irLink(link)`**, found in
   `/lib/js/app/portal/portal.js`: `location.replace(link + "?token=" +
   $("#token").val())` — a **full page navigation**, not an AJAX call. The
   missing ingredient was simply the `token` query parameter: without a
   valid one, the server always serves the homepage shell instead of the
   requested page's real content. Appending the current session's
   `id="token"` hidden-input value (read from any already-loaded page, e.g.
   the homepage) as `&token=<value>` makes the server render the actual
   search form + results table.
3. **The listing JSON endpoint's field keys are randomized per session.**
   `operacion.php` (POST) returns rows like
   `{"iz8cNB9P": "26-1251-...", "nOk6dDI1": "Gobierno Autonomo..."}` — eight
   random alphanumeric characters as keys, not stable field names. The
   *order* of these keys for a given session is published in a hidden input
   on the search page itself: `<input id="colsConvocatoriasSimple"
   type="hidden" value='["iz8cNB9P","nOk6dDI1",...]'>`. That order exactly
   matches the fixed `<thead>` column order of the visible results table
   (CUCE / Entidad / Tipo Contratacion / Modalidad / Objeto de Contratacion
   / Subasta / Fecha Publicacion / Fecha Presentacion / Estado / Archivos /
   Formularios / Reportes) — confirmed by reading the live `<thead>` HTML
   directly. `src/constants.COLUMN_ORDER` encodes this fixed semantic order;
   `src/client.handshake()` reads the *current* session's randomized key
   list and `src/extractor.build_list_record()` zips the two together
   positionally. A fresh session gets a fresh random key set, so this
   handshake must be repeated at the start of every run (but not before
   every page — see below).

## Handshake sequence used by this actor

1. `GET /portal/index.php` (new session/cookies) → read `id="token"` →
   `home_token`.
2. `GET /portal/contrataciones/busqueda/convocatorias.php?tipo=<tipo>&token=<home_token>`
   on the **same session** → read the form's `name="token"` (`form_token`,
   distinct from `home_token` — a fresh CSRF value minted per page render)
   and `colsConvocatoriasSimple` (the session's column-key order).
3. `POST /portal/contrataciones/operacion.php` with `token=<form_token>`
   plus the visible form's field names (`entidad`, `objetoContrato`, date
   ranges, CUCE parts, `r1` for vigentes-only, `subasta`, and one
   `bienes`/`obras`/`servicios`/`consultoria` key per selected contracting
   type — matching exactly how jQuery's `.serialize()` omits unchecked
   checkboxes) plus the DataTables-style pagination params (`operacion`,
   `draw`, `start`, `length`, `nroRegistros`).

**Confirmed live: `form_token` and `colsConvocatoriasSimple` both stay valid
across many sequential paginated POSTs on the same session/cookies** — this
actor performs the handshake once per run (per `tipo`) and reuses it for
every page, rather than re-handshaking before each page (verified with three
consecutive pages at `start=0,10,20` on one token — all three succeeded with
correctly shifting CUCEs).

Discovering this required reading through `/lib/js/app/portal/portal.js`
(`irLink`), `/lib/js/app/portal/busqueda.js` (`busquedaPagina` →
`buscarConvocatorias`), `/lib/js/app/portal/contrataciones/convocatorias.js`
(the actual `buscarConvocatorias` definition — a separate, page-specific
file only loaded once a valid token renders the real search page, not the
homepage-shell fallback), and `/lib/js/app/comun.js`
(`getOpcionesPaginacionnuevo`, which builds the POST body from
`$("#"+idForm).serialize()` plus the pagination/operacion fields).

## Fixed page size

SICOES's own frontend hardcodes the page size to exactly 10 rows per
request (`buscarConvocatorias()` always calls
`getOpcionesPaginacionnuevo(..., 10, ..., 0, 10, ...)`). Confirmed live:
posting `length=100`/`nroRegistros=100` still returns exactly 10 rows. This
actor paginates by incrementing `start` by 10 (`PAGE_SIZE`) rather than
requesting a larger page.

## TLS profile

`curl_cffi` `chrome124`. No WAF/fingerprint gate was observed on any of the
homepage, search page, or `operacion.php` paths across chrome124/
chrome131/safari17_0/edge101 — the only blocking behavior found anywhere on
this host is the `robots.txt`-path WAF signature and the CAPTCHA on document
downloads, both described above.

## What this actor does NOT do

- **Does not fetch the "ficha" PDF or the "Convocatoria"/"Documento Base de
  Contratacion" attachment PDFs** — both are gated behind CAPTCHA
  (Cloudflare Turnstile for the ficha; a scrambled-image code for the raw
  attachments). It surfaces which document labels exist per tender
  (`documentLabels`) and a `sourceUrl` so a user can look the CUCE up
  manually in a browser.
- **Does not implement a separate "detail" mode.** The only per-tender
  detail page (`fichaProceso.php`) is itself just a CAPTCHA-gated PDF
  download form with no extra structured fields beyond what the list
  endpoint already returns — there is nothing additional to scrape there
  without solving a CAPTCHA, which this portfolio does not do.
