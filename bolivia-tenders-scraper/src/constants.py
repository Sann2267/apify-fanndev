"""Shared constants for Bolivia's SICOES (Sistema de Contrataciones
Estatales) public tender-search platform.

See CRAWLING_METHOD.md for how the handshake and endpoints below were
discovered and verified. `www.sicoes.gob.bo` is Bolivia's official national
e-procurement portal, run by the Ministerio de Economia y Finanzas Publicas.
No login is needed to browse tenders -- only downloading a process's PDF
"ficha" or supporting documents is gated behind a Cloudflare Turnstile
CAPTCHA (see CRAWLING_METHOD.md), which this actor does not attempt.
"""

BASE = "https://www.sicoes.gob.bo"
HOME_URL = f"{BASE}/portal/index.php"
SEARCH_PAGE_URL = f"{BASE}/portal/contrataciones/busqueda/convocatorias.php"
OPERACION_ENDPOINT = f"{BASE}/portal/contrataciones/operacion.php"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-BO,es;q=0.9,en;q=0.8",
}

AJAX_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff
LIST_PAGE_DELAY = 1.0  # pause between sequential list-page requests

# SICOES's own frontend hardcodes the page size to 10 rows per request
# (buscarConvocatorias() in convocatorias.js always calls
# getOpcionesPaginacionnuevo(..., 10, ..., 0, 10, ...)) -- a larger `length`
# value is silently ignored server-side (confirmed live: length=100 still
# returned exactly 10 rows). See CRAWLING_METHOD.md.
PAGE_SIZE = 10
MAX_LIST_PAGES_SAFETY_CAP = 500

# Positional column order for the "Simple" search table, read from the
# <thead> of #tablaSimple on the search page (CUCE / Entidad / Tipo
# Contratacion / Modalidad / Objeto de Contratacion / Subasta / Fecha
# Publicacion / Fecha Presentacion / Estado / Archivos / Formularios /
# Reportes). The JSON response's own field keys are randomized per session
# (e.g. "iz8cNB9P") -- this fixed order is zipped against the session's own
# `colsConvocatoriasSimple` key list (read fresh every handshake) to recover
# stable field names. See CRAWLING_METHOD.md.
COLUMN_ORDER = [
    "cuce",
    "entidad",
    "tipoContratacion",
    "modalidad",
    "objetoContratacion",
    "subastaElectronica",
    "fechaPublicacion",
    "fechaPresentacionPropuestas",
    "estado",
    "archivosHtml",
    "formularioHtml",
    "fichaHtml",
]

TIPO_VALUES = ("convNacional", "convInternacional")
