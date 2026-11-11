"""Endpoints, headers, and recon summary for Panama's official public-procurement
OCDS API (Direccion General de Contrataciones Publicas -- DGCP).

Recon summary (2026-08-27): The main citizen-facing portal,
`www.panamacompra.gob.pa` (PanamaCompra, DGCP's Angular SPA), has a
`robots.txt` that `Disallow:`'s everything except its bare root shell and
sitemap for `User-agent: *` -- effectively blocking crawl of any deep content
on that domain. This actor does NOT scrape that domain.

Instead it uses a SEPARATE, also-DGCP-owned host:
`ocdsv2dev.panamacompraencifras.gob.pa` -- "PanamaCompraenCifras"
("PanamaCompra in Figures"), DGCP's own OCDS (Open Contracting Data Standard)
transparency portal, explicitly described in its own page metadata as "un
portal para poder visualizar los datos que se encuentran transformados en el
estandar OCDS ... Puedes explorar y visualizar las contrataciones del
gobierno de Panama" (a portal to explore/visualize Panama government
procurement data transformed into the OCDS standard). Every API response's
`publisher` field reads "Direccion General de Contrataciones Publicas
(DGCP)", `license` is CC-BY 4.0, with a linked publication policy PDF
(`/downloads/politica_publicacion.pdf`) -- genuinely open public data, not a
side channel or a leak.

`robots.txt` on THIS domain does not exist as a distinct resource: both
`ocdsv2dev.panamacompraencifras.gob.pa/robots.txt` and the sibling
`www.panamacompraencifras.gob.pa/robots.txt` return the SPA's own
`index.html` (200, Content-Type: text/html) or a plain IIS 404 respectively
-- Angular's client-side catch-all router and IIS both correctly report "no
such resource", not a restriction. No mention of Claude/anthropic-ai/AI
crawlers anywhere (there is no robots.txt file to mention anything in).

No login wall: every endpoint below was fetched cold, zero cookies/prior
auth, and returned real data on the first request.

No WAF/TLS-fingerprint gate observed: plain `curl` with no impersonation at
all got clean `200`s immediately; the front server is `nginx` (not
Cloudflare/Akamai/PerimeterX/DataDome -- no challenge headers or cookies of
any kind seen). `curl_cffi` `chrome124` is used below for portfolio-wide
consistency regardless.

Two real quirks found during recon:

1. **The TLS certificate chain is incomplete server-side.** `curl_cffi`'s
   bundled OpenSSL cert store fails every request with
   `CertificateVerifyError: unable to get local issuer certificate`, while
   Windows-native `curl` (schannel-backed, more permissive about fetching
   missing intermediates) succeeds silently on the identical URL. Confirmed
   this is a server misconfiguration, not a local/proxy artifact -- the same
   portfolio-wide pattern already seen on Nepal/Tunisia/Eswatini government
   sites. `verify=False` is set explicitly in `client.py`; no other
   workaround exists short of skipping verification.
2. **`Accept: application/json` must be sent explicitly.** Without it,
   `curl_cffi`'s `chrome124` impersonation profile sends a browser-typical
   `Accept: text/html,...` header, and the Angular server's catch-all route
   returns the SPA's `index.html` shell (200 OK, but HTML, ~148KB) instead of
   the real API response. Confirmed by comparing an unset-Accept request
   against an explicit `Accept: application/json` request against the
   identical URL (53KB of real JSON).

## The API -- a real OCDS bulk-export feed, cursor-paginated, NOT search/filterable

`GET /api/v1/records` (and its sibling `/api/v1/releases`, not used by this
actor) returns a standard OCDS record package: `version`, `publisher`,
`license`, `publicationPolicy`, `publishedDate`, and a `records` array (fixed
page size of 10 -- `?limit=`/`?pageSize=` query params are silently ignored,
confirmed during recon). Forward pagination is cursor-based via
`links.next`, a full URL carrying an opaque
`searchAfter=<source>,<tenderId>,<epoch>,<epoch>,<id>` token -- there is no
page-number scheme.

**No server-side filtering exists.** `?year=`, `?source=`, `?sort=`,
`?order=`, `?descending=` were all tried during recon and silently ignored
(byte-identical response every time) -- this confirms the endpoint is a flat
bulk dump in a fixed internal order (grouped by tender code, NOT by date),
not a search API. There is consequently no way to ask the server for "only
2026 tenders" or "newest first" -- `list` mode simply pages forward from
wherever the feed currently starts (or from a `startCursor` carried over from
a previous run) and returns whatever it yields, exactly like the upstream
feed itself. This is a genuine upstream data-source limitation, not a
scraping gap -- documented plainly in the README.

`GET /api/v1/record/{ocid}` fetches ONE tender by its OCDS `ocid` (as
returned by `list` mode, e.g. `ocds-emvi6n-2024-6-15-01-08-CM-000025-1`) --
same package shape, `records` array with exactly one entry. An unknown ocid
returns a clean `404` with a small JSON body
(`{"detail":"No se encontraron resultados.","error":true}`), not an HTML
error page -- easy to detect and NOT retried as if it were transient.

## Encoding note

The response body is correctly UTF-8 (verified at the byte level: an
accented name round-tripped as the correct 2-byte UTF-8 sequences for
"i-acute" and "a-acute", e.g. "Politicos", "Panama"). Any mojibake seen while
debugging in a terminal was purely a Windows console codepage display
artifact, not a real data problem -- `client.py` decodes response bytes as
UTF-8 explicitly rather than relying on `curl_cffi`'s charset auto-detection
(the `Content-Type: application/json` header carries no explicit charset).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://ocdsv2dev.panamacompraencifras.gob.pa"
RECORDS_URL = f"{BASE_URL}/api/v1/records"
RECORD_DETAIL_URL = f"{BASE_URL}/api/v1/record/{{ocid}}"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "es-PA,es;q=0.9,en;q=0.8",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0
REQUEST_TIMEOUT = 30

LIST_PAGE_SIZE = 10  # fixed by the API -- ?limit=/?pageSize= are ignored
MAX_LIST_PAGES_SAFETY_CAP = 200
LIST_PAGE_DELAY = 0.5
