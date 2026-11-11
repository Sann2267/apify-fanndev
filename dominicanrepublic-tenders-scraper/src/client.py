"""HTTP client wrapper for DGCP's public "Sistema de Información de
Contrataciones Públicas" open-data REST API
(datosabiertos.dgcp.gob.do/api-dgcp/v1).

No login, no API key, no CSRF handshake -- see CRAWLING_METHOD.md. Every
endpoint returns the same envelope shape, confirmed live:

    {"code": 200, "hasError": false,
     "payload": {"content": [...] | null},
     "page": 1, "limit": 100, "totalResults": N, "pages": M}

A filter that matches nothing still comes back **200** with
`payload.content: null` (not an empty array, and not a 404/400) -- treated
as zero rows by this client, never as an error.
"""

import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    ARTICULOS_ENDPOINT,
    CONTRATOS_ENDPOINT,
    DEFAULT_PAGE_LIMIT,
    HEADERS,
    MAX_PAGE_LIMIT,
    MAX_RETRIES,
    OFERTAS_ENDPOINT,
    PROCESOS_ENDPOINT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)


class FetchFailed(Exception):
    """A GET never produced a usable 200 JSON response after retries."""


class RecordNotFound(Exception):
    """A detail lookup for a specific proceso code came back genuinely empty."""


def _clean(params: dict) -> dict:
    """Drop empty/None filters so the request matches what the platform's
    own UI sends when a field is left blank -- upstream treats an omitted
    param as "no filter", confirmed live (an explicit empty string was not
    tested against, and is avoided here to stay on the safe/documented
    side)."""
    return {k: v for k, v in params.items() if v not in (None, "")}


async def _get(url: str, params: dict, proxy_url: str | None = None) -> dict:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        session = AsyncSession(
            impersonate=TLS_PROFILE,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=60,
        )
        try:
            r = await session.get(url, headers=HEADERS, params=params)
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"GET {url} params={params!r} returned {r.status_code} ({len(r.content)} bytes)")
            try:
                data = r.json()
            except ValueError as e:
                raise FetchFailed(f"GET {url} params={params!r} returned non-JSON body: {e!r}") from e
            if not isinstance(data, dict) or data.get("hasError"):
                raise FetchFailed(f"GET {url} params={params!r} upstream hasError=true: {data!r}")
            return data
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError (raised
            # on a failed proxy CONNECT tunnel, DNS failure, TLS handshake
            # error, etc.) does NOT inherit from Python's builtin
            # ConnectionError -- its MRO is RequestException -> CurlError ->
            # OSError, a parallel hierarchy. Both are caught explicitly, per
            # the portfolio-wide Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        finally:
            await session.close()
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {url!r} params={params!r}: {last_exc!r}")


async def fetch_procesos(
    page: int = 1,
    limit: int = DEFAULT_PAGE_LIMIT,
    proceso: str = "",
    unidad_compra: int | None = None,
    modalidad: str = "",
    estado: str = "",
    mipyme: bool | None = None,
    mipyme_mujer: bool | None = None,
    startdate: str = "",
    enddate: str = "",
    proxy_url: str | None = None,
) -> dict:
    """One page of DGCP's /procesos listing -- tender/procurement processes,
    ordered by publish date upstream (see CRAWLING_METHOD.md for an honest
    note on ordering quirks). All filters are optional; omitting everything
    browses the full public archive (624k+ processes as of 2026-08-27)."""
    limit = max(1, min(limit, MAX_PAGE_LIMIT))
    params = _clean(
        {
            "page": page,
            "limit": limit,
            "proceso": proceso,
            "unidad_compra": unidad_compra,
            "modalidad": modalidad,
            "estado": estado,
            "mipyme": mipyme,
            "mipyme_mujer": mipyme_mujer,
            "startdate": startdate,
            "enddate": enddate,
        }
    )
    return await _get(PROCESOS_ENDPOINT, params, proxy_url=proxy_url)


async def fetch_contratos(proceso: str = "", page: int = 1, limit: int = MAX_PAGE_LIMIT, proxy_url: str | None = None) -> dict:
    params = _clean({"proceso": proceso, "page": page, "limit": limit})
    return await _get(CONTRATOS_ENDPOINT, params, proxy_url=proxy_url)


async def fetch_ofertas(proceso: str = "", page: int = 1, limit: int = MAX_PAGE_LIMIT, proxy_url: str | None = None) -> dict:
    params = _clean({"proceso": proceso, "page": page, "limit": limit})
    return await _get(OFERTAS_ENDPOINT, params, proxy_url=proxy_url)


async def fetch_articulos(proceso: str = "", page: int = 1, limit: int = MAX_PAGE_LIMIT, proxy_url: str | None = None) -> dict:
    params = _clean({"proceso": proceso, "page": page, "limit": limit})
    return await _get(ARTICULOS_ENDPOINT, params, proxy_url=proxy_url)


async def fetch_proceso_detail(codigo_proceso: str, proxy_url: str | None = None) -> dict:
    """Fetches everything this actor bundles into one detail record for a
    single proceso code: the process itself (/procesos?proceso=), plus its
    contracts (/contratos), offers/bids received (/ofertas), and requested
    line items (/procesos/articulos) -- four upstream endpoints DGCP itself
    exposes as separate resources with no server-side "compiled record" view.

    Raises RecordNotFound only if the process code itself doesn't exist.
    contratos/ofertas being empty is normal and expected for a process still
    open for bidding (no award yet) -- not an error."""
    proc_resp = await fetch_procesos(proceso=codigo_proceso, limit=5, proxy_url=proxy_url)
    proc_rows = (proc_resp.get("payload") or {}).get("content") or []
    if not proc_rows:
        raise RecordNotFound(codigo_proceso)

    contratos_resp, ofertas_resp, articulos_resp = await asyncio.gather(
        fetch_contratos(proceso=codigo_proceso, proxy_url=proxy_url),
        fetch_ofertas(proceso=codigo_proceso, proxy_url=proxy_url),
        fetch_articulos(proceso=codigo_proceso, proxy_url=proxy_url),
    )

    return {
        "proceso": proc_rows[0],
        "contratos": (contratos_resp.get("payload") or {}).get("content") or [],
        "contratos_total_upstream": contratos_resp.get("totalResults"),
        "ofertas": (ofertas_resp.get("payload") or {}).get("content") or [],
        "ofertas_total_upstream": ofertas_resp.get("totalResults"),
        "articulos": (articulos_resp.get("payload") or {}).get("content") or [],
        "articulos_total_upstream": articulos_resp.get("totalResults"),
    }
