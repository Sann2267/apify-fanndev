"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Honduras' official procurement portal domain,
`honducompras.gob.hn` (and `oncae.gob.hn`, the regulator ONCAE), is currently
UNREACHABLE from every network path tested (curl_cffi profile ladder + an
independent fetch tool both timed out / connection-refused). Wayback Machine
snapshots show the main domain was overtaken by generic WordPress boilerplate
content ("Hello world", "career", a web-dev-agency blog) sometime between
Jan 2026 and its most recent capture (May 2026) -- a domain/hosting lapse,
not a WAF block. `web.oncae.gob.hn` (which hosted ONCAE's daily-updated OCDS
open-data export per the Open Contracting Partnership registry) no longer
resolves in DNS at all (NXDOMAIN).

**Fallback found and used by this actor**: ONCAE's legacy "HonduCompras 1.0"
application is still live on a DIFFERENT, still-functioning subdomain:

    http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx

This is the same pattern seen repeatedly elsewhere in this project's tender
vertical (Sierra Leone, Malawi, Botswana): when a country's modern e-GP
front door fails, an older corporate/legacy system from the same regulator
often still publishes the same data. Here `h1.honducompras.gob.hn` (the
HonduCompras 1.0 homepage) links directly to this search tool as "Buscador
de Procesos" / historical search, confirming it is ONCAE's own real system,
not a decoy -- page metadata author tag reads "Oficina Normativa de
Contratacion y Adquisicion del Estado, ONCAE".

**HTTPS is not available** on this subdomain -- only `http://` responds;
`https://sicc.honducompras.gob.hn` times out on every TLS profile tried.

`robots.txt` on this subdomain returns a plain HTTP 404 (no file at all --
classic IIS "the page cannot be found") -- no restrictions, no Claude/AI-
crawler mention. The sibling homepage `h1.honducompras.gob.hn/robots.txt`
is even more explicit: `User-agent: * / Allow: /`.

No WAF or TLS-fingerprint gate observed -- plain IIS/ASP.NET WebForms
(2005-2017-era, Infragistics UI controls), `curl_cffi` `chrome124` got clean
200s immediately, no challenge page of any kind.

## Viewing is 100% public -- login only gates internal publishing tools

The homepage links to a **separate** login page,
`sicc.honducompras.gob.hn/DCC/webapp/login.aspx`, explicitly labelled
"Usuarios de Sistema (Difusion de procesos)" ("System Users -- process
publishing") -- that is for government procurement officers to CREATE/PUBLISH
notices, not to browse them. The public search, results grid, and every
individual tender's full detail page are served with zero authentication.
(Two OTHER legacy sub-pages under the same `/HC` app --
`Oportunidades_negocio/Default.aspx` and `Contratos/Default.aspx` -- return a
generic ASP.NET 500 runtime error; these are genuinely broken/decommissioned
sub-features, not auth walls, and are not used by this actor since
`busquedahistorico.aspx` alone covers both current and historical processes
via its "Etapa" (stage) filter.)

## The search flow -- classic ASP.NET WebForms postback, NOT a JSON API

1. `GET busquedahistorico.aspx` -- returns the search-form HTML embedding the
   ASP.NET postback tokens (`__VIEWSTATE`, `__VIEWSTATEGENERATOR`,
   `__EVENTVALIDATION`) plus every other hidden/select field the form itself
   carries (institution, stage, modality, acquisition-type, funding-source
   dropdowns; expediente/date-range text inputs). This actor extracts the
   COMPLETE current field set generically (`extractor.extract_form_fields`)
   rather than hand-listing field names -- a hand-typed subset was tried
   first during recon and got HTTP 500s, because the Infragistics
   date-chooser controls carry several extra hidden fields (calendar-state
   IDs) that must round-trip unchanged or the server-side control tree
   validation fails.
2. `POST` those same fields back, with the desired filter values overlaid
   and `ctl00$cphCuerpo$wpParametros$btnBuscar=Buscar` set, on the SAME
   session (curl_cffi persists cookies automatically). Response is a full
   HTML page (not an AJAX partial) containing an
   `id="...gvResultados"` `<table>` -- a plain ASP.NET `GridView`, one `<tr>`
   per tender, each cell built from labelled `<b>Label:</b><span>value</span>`
   pairs plus a "Ver Detalle" link to `ProcesoHistorico.aspx?Id0=...&Id1=...
   &Id2=...` (opaque, server-generated tokens -- there is no way to construct
   a detail URL by hand, it must come from a list-page row).
3. Pagination is a further `POST` with `__EVENTTARGET=ctl00$cphCuerpo$
   gvResultados` and `__EVENTARGUMENT=Page$<n>`, carrying forward the FULL
   field set (including the just-updated `__VIEWSTATE`) from the previous
   response -- confirmed working through page 2 during recon. This is
   inherently sequential per search (each page's postback needs the prior
   response's fresh `__VIEWSTATE`), so list-mode pagination is not
   parallelized.

An unfiltered search (all dropdowns at "(Todas)") returned **21 pages x 30
rows = ~630 records** during recon, spanning both currently-open processes
(e.g. a tender open through 24/09/2026) and historical ones -- there is no
separate "current only" endpoint; the `Etapa` (stage) filter is the
mechanism for narrowing to live processes (`Elaboracion`, `Revisado`,
`Recepcion de Ofertas`, `Evaluacion` = still active; `Adjudicado`,
`Desierto`, `Fracasados` = concluded).

## Individual tender detail pages -- rich, public, no login

`ProcesoHistorico.aspx` detail pages are plain `GET` requests (no session/
postback state needed -- confirmed by fetching one cold, with no prior
request on that client) and return a label/value table
(`id="...dvProceso"`) with the buyer's institution, purchasing unit, object,
key dates, funding source, modality, stage, acquisition type, delivery
location, document-fee value, and a named CONTACT PERSON with phone and
email (`mailto:` link) -- real transparency data, not redacted. Below that,
an Infragistics tabbed widget exposes up to four data grids per tender:
"Productos y/o Servicios Solicitados" (line items with UNSPSC code,
description, full specification text, quantity), "Documentos" (attached
files), "Participantes" (bidders), and "Adjudicado a" (award). Only tabs
with actual data render a populated grid -- e.g. a tender still in
"Elaboracion" stage has products but empty Documentos/Participantes/
Adjudicado grids, which is expected and not an extraction failure.

## The server is genuinely slow/flaky, not blocking

Multiple recon requests timed out at 20-40s with a partial response already
received (up to 202KB of a ~211KB page) -- a slow legacy IIS box under load,
not a WAF/rate-limit signature (no 403/429, no challenge marker, and a retry
on the same request reliably succeeds). `REQUEST_TIMEOUT` is set generously
and `MAX_RETRIES` covers this.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "http://sicc.honducompras.gob.hn"
LIST_URL = f"{BASE_URL}/HC/procesos/busquedahistorico.aspx"
DETAIL_BASE = f"{BASE_URL}/HC/procesos/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-HN,es;q=0.9,en;q=0.8",
    "Origin": BASE_URL,
    "Referer": LIST_URL,
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0
REQUEST_TIMEOUT = 90  # this legacy server can legitimately take 40s+ per request

LIST_PAGE_SIZE = 30
MAX_LIST_PAGES_SAFETY_CAP = 25  # observed ~21 pages for a fully unfiltered search
LIST_PAGE_DELAY = 1.0

# ddlEtapas (stage) options, scraped live from the search form -- exposed as
# an enum in the input schema so users pick a label, not a magic number.
ETAPA_VALUES = {
    "todas": "0",
    "elaboracion": "1",
    "revisado": "2",
    "recepcion_ofertas": "3",
    "evaluacion": "4",
    "adjudicado": "5",
    "desierto": "6",
    "fracasados": "7",
}

MODALIDAD_VALUES = {
    "todas": "0",
    "licitacion_o_concurso": "1",
    "compra_menor": "2",
    "precalificacion": "3",
}

TIPO_ADQUISICION_VALUES = {
    "todas": "0",
    "suministro_bienes_servicios": "1",
    "obras": "2",
    "consultoria": "3",
}
