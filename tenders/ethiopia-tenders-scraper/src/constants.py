"""Endpoints, headers, profile choices -- all in one place.

Target: Ethiopia's official electronic Government Procurement (eGP) portal,
`egp.gov.et`, operated by the Public Procurement and Property Administration
Agency (PPPAA/PPA). Built on **Perago Systems'** "procure-ai"/ERP e-GP
platform -- the same vendor family confirmed elsewhere in this portfolio for
Sierra Leone (NPPA, backend down at build time) and Malawi (MANEPS, SPA-only
with no working API found) -- Ethiopia is the first deployment of this
vendor where the JSON API was successfully cracked. See CRAWLING_METHOD.md
for the full recon writeup, including a documented upstream bug in the
"live open tenders" endpoint that this actor deliberately avoids.
"""

FRONTEND_URL = "https://egp.gov.et/egp/"
GATEWAY_BASE = "https://egp.gov.et/po-gw"

# CMS microservice -- "Publication Plan Lots" register. This is the actor's
# real data source: a fully public, actively-updated procurement-plan/lot
# register (~29,840+ records at recon time), NOT the buggy
# tendering-int/get-public-packages "live tenders" endpoint (see
# CRAWLING_METHOD.md "Known limits").
LIST_URL = f"{GATEWAY_BASE}/cms-v2/api/publication/get-publication-lots"
DETAIL_URL = f"{GATEWAY_BASE}/cms-v2/api/publication-lots/get-publication-lot"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.5

# Page size used when walking `list`/`latest` pagination (Skip/Top query
# params on the underlying CollectionQuery). 50 keeps individual responses
# small while still reaching maxItems quickly for large requests.
PAGE_SIZE = 50

# Safety cap on pages walked in "list" mode regardless of maxItems, so a
# parsing regression can't spin the actor into thousands of requests
# against a government server.
MAX_PAGES_HARD_CAP = 500

# The only OrderBy field confirmed to work reliably on this endpoint.
# Business-meaningful field names (status, organizationId, referenceNumber,
# id, ...) all trigger a server-side ArgumentNullException -- see
# CRAWLING_METHOD.md "Known limits" for the full list of field names tested.
ORDER_BY_FIELD = "timestamp"
