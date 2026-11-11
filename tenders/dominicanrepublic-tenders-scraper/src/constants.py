"""Shared constants for the Dominican Republic's DGCP (Dirección General de
Contrataciones Públicas) public open-data REST API.

See CRAWLING_METHOD.md for how these endpoints were discovered and verified.
This is DGCP's *own* open-data portal at `datosabiertos.dgcp.gob.do` -- a
React SPA whose bundled JS embeds a full API-docs page (Swagger-style schema,
served client-side, not behind auth) describing the REST API at
`/api-dgcp/v1` in detail. This is a *separate* system from the login-walled
"Comprasdominicana" transactional/bidding portal
(`comunidad.comprasdominicana.gob.do`) where suppliers submit bids -- this
actor never touches that system.
"""

BASE = "https://datosabiertos.dgcp.gob.do/api-dgcp/v1"

PROCESOS_ENDPOINT = f"{BASE}/procesos"
ARTICULOS_ENDPOINT = f"{BASE}/procesos/articulos"
CONTRATOS_ENDPOINT = f"{BASE}/contratos"
OFERTAS_ENDPOINT = f"{BASE}/ofertas"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff

LIST_PAGE_DELAY = 1.0  # pause between sequential list-page requests
MAX_LIST_PAGES_SAFETY_CAP = 200

# The API caps `limit` at 1000 server-side (documented, and confirmed live --
# requesting limit=99999 silently comes back capped at 1000).
DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 1000

# `estado_proceso` values observed live across a 200-row sample of /procesos
# (2026-08-27) -- documented here as examples for the input schema's
# description, NOT enforced as an exhaustive enum (the upstream field is
# free text and may have values this sample didn't cover).
KNOWN_ESTADOS = [
    "Proceso publicado",
    "Sobres abiertos o aperturados",
    "Proceso adjudicado y celebrado",
    "Proceso con etapa cerrada",
    "Proceso desierto",
    "Cancelado",
]

# `modalidad` values observed live in the same sample.
KNOWN_MODALIDADES = [
    "Comparación de Precios",
    "Compras por Debajo del Umbral",
    "Contratación Menor",
    "Licitación Pública Abreviada",
    "Licitación Pública Nacional",
    "Procesos de Excepción",
]
