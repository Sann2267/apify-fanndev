"""Endpoints, headers, and recon summary for Nicaragua's SISCAE
(Sistema de Contrataciones Administrativas Electronicas) public procurement
portal.

Recon summary (2026-08-27): SISCAE is administered by the Direccion General
de Contrataciones del Estado (DGCE), Ministerio de Hacienda y Credito
Publico. The public-facing marketing/info site is
`www.nicaraguacompra.gob.ni` (Plone-based); the actual application --
search, listings, everything this actor uses -- lives on a different
subdomain, `www.gestion.nicaraguacompra.gob.ni/siscae/portal`, a JBoss
Portal (Apache Pluto portlet container) app built on Apache MyFaces (JSF)
portlets, JBoss Web/2.1.3.SNAPSHOT.

**Reachability**: this session's own network and Anthropic's own web-fetch
infrastructure both got immediate TCP-level connection resets/timeouts on
EVERY nicaraguacompra.gob.ni host tried directly. This looked at first like
the same "regional peering" issue documented for Ecuador (which needed a
country-pinned residential proxy) -- but the real test, run through the
actual Apify Cloud actor (both with NO proxy/datacenter IP, and with
generic/NI-pinned Residential), showed `www.gestion.nicaraguacompra.gob.ni`
(the actual SISCAE app) is reachable from Apify's plain datacenter IP with
zero proxy needed at all. Only `www.nicaraguacompra.gob.ni` (the unrelated
Plone marketing site) itself was flaky from the cloud too. This actor
therefore does NOT default to a country-pinned or even Residential proxy --
plain datacenter reliably works, confirmed live on Apify Cloud, not just
assumed by analogy to Ecuador.

**robots.txt**: `www.nicaraguacompra.gob.ni/robots.txt` (the Plone
marketing site, not used by this actor) consistently SSL-resets/times out on
every proxy/no-proxy combination tried -- an infra quirk on an unrelated
host, not a policy block (compare Ecuador's NetScaler robots.txt
signature-block quirk). `www.gestion.nicaraguacompra.gob.ni/siscae/robots.txt`
(the actual host this actor talks to) returns a clean JBoss Web 404 "the
requested resource is not available" -- i.e. no robots.txt file exists at
all, so there is no policy to violate and no Claude/ClaudeBot/anthropic-ai
mention anywhere (there is nothing to mention anything in).

**Login**: browsing/searching tenders needs zero authentication -- confirmed
by fetching the search form and results pages cold, with no prior session.
The portal's `LoginSmallPortlet` (visible on `/siscae/portal`) is for
registered government users and suppliers to manage their own accounts
(publish notices, submit bids) -- a BIDDING/publishing gate, not a viewing
gate, exactly the "fine if only BIDDING requires login" carve-out.

**No WAF/TLS gate observed** -- `curl_cffi` `chrome124` got clean 200s
immediately on every path tried, no challenge page of any kind.

## Two ways to list procedures, both plain HTML (no ViewState, no JSON API)

1. **Quick browse by status** -- `busquedaProcedimientosVigentes` portlet,
   a stateless `GET` with a `proc_estado` query param (VIGENTE/EJECUCION/
   CANCELADO/CERRADO/DESIERTO/ADJUDICADO/SUSPENDIDO). Fast (~5-10s), always
   returns whatever currently matches that single status -- observed 10 rows
   per status during recon (a small country's currently-live tender volume,
   not an artificial page-size cutoff enforced by this actor).

2. **Full search form** -- `busqueda?accion=todos` portlet
   (`inicioBusqForm`), a classic "carry every hidden/select field forward"
   POST -- like this portfolio's Honduras ASP.NET actor, but genuinely
   simpler: there is NO `__VIEWSTATE`/`javax.faces.ViewState` token anywhere
   in this form (confirmed: only `<form>_SUBMIT`, `autoScroll`, and
   `_link_hidden_` hidden fields exist). This actor extracts the full
   current field set generically (`extractor.extract_form_fields`, mirroring
   Honduras) and overlays keyword/institution/department/year/status/
   page-size before POSTing back to the form's own (session-scoped) action
   URL on the SAME session (curl_cffi persists the JSESSIONID cookie
   automatically). Supports up to **100 results per page**
   (`resultadosItems=CIEN`) and multiple status values at once (checkbox
   field, repeatable) -- confirmed live: a POST for VIGENTE+EJECUCION+
   ADJUDICADO with `resultadosItems=CIEN` returned exactly 100 real rows in
   763KB of HTML, same row/table structure as endpoint #1 above, so one
   shared parser (`extractor.parse_procedure_rows`) handles both.

Both list mechanisms render the SAME nested-table row shape (JSF portlet
component `listadoProcedimientos`, deeply auto-ID'd like Honduras'
Infragistics grids) -- see `extractor.py`.

## The server is occasionally slow, not blocking

One POST search attempt during recon hit a clean 40s timeout with 0 bytes
received; retried immediately afterward at a 90s timeout and got a normal
200 in under 30s. No 403/429/challenge marker was ever observed -- this
reads as an occasionally slow/loaded JBoss box (consistent with the
public-sector Java-portal era this app is from), not a block.
`REQUEST_TIMEOUT` is set generously and `MAX_RETRIES` covers this.

## "Mas Datos" detail expansion -- investigated, not implemented

Each row's "Acciones" column has a "Mas Datos" (More Data) link that is a
client-side JS `onclick` -- it sets a hidden `_link_hidden_` field to that
row's specific JSF component id and re-submits the SAME results form
in-place (a portlet partial-postback pattern), not a navigable URL. There is
consequently no stable "detail page URL" a user could pass back into this
actor the way Honduras' `ProcesoHistorico.aspx?Id0=...` links work. One
attempt to simulate this postback (same session, full field set plus the
target row's `_link_hidden_` id) returned HTTP 200 but rendered the plain
search form again rather than an expanded detail view -- the simulation is
missing some piece of server-side portlet-window state this session did not
crack in the time available. Given the two list mechanisms above already
surface rich per-tender fields (institution, procedure type and number,
UNSPSC-style classification code, title/object, publish/close/last-updated
dates, status), this actor ships **list mode only** and does not claim a
"detail mode" it could not get working reliably. Worth revisiting in a
future session.

## Currency / language

All content is Spanish. No currency/budget amount field was observed on the
list rows themselves (unlike Honduras/Ecuador) -- SISCAE's public list view
surfaces classification/dates/status/institution but not a monetary value
per procedure at this level; passed through as None rather than guessed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.gestion.nicaraguacompra.gob.ni"
STATUS_LIST_URL = f"{BASE_URL}/siscae/portal/adquisiciones-gestion/busquedaProcedimientosVigentes"
SEARCH_FORM_URL = f"{BASE_URL}/siscae/portal/adquisiciones-gestion/busqueda?accion=todos"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-NI,es;q=0.9,en;q=0.8",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0
REQUEST_TIMEOUT = 90  # this JBoss-era server can occasionally take 30-40s+

# Status (Estado) values, scraped live from both the busquedaProcedimientosVigentes
# proc_estado query param and the search form's estadoAdqPuId checkboxes.
ESTADO_VALUES = {
    "vigente": "VIGENTE",
    "ejecucion": "EJECUCION",
    "cancelado": "CANCELADO",
    "cerrado": "CERRADO",
    "desierto": "DESIERTO",
    "adjudicado": "ADJUDICADO",
    "suspendido": "SUSPENDIDO",
}

# resultadosItems select options on the search form -- Spanish number words,
# not digits, this is the literal upstream value.
RESULTS_PER_PAGE_VALUES = {
    10: "DIEZ",
    25: "VEINTICINCO",
    50: "CINCUENTA",
    100: "CIEN",
}
