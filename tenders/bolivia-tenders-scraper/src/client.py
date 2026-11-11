"""HTTP client for SICOES's public tender-search DataTables endpoint.

No login, no API key -- see CRAWLING_METHOD.md. SICOES's search page is
server-rendered per-session: a short-lived CSRF `token` (embedded in a
hidden `<input id="token">`) gates which page body the server actually
renders (a GET without a valid current token silently falls back to the
homepage shell instead of erroring), and the JSON listing endpoint's own
field keys are randomized per-session (e.g. "iz8cNB9P") -- a deliberate
anti-scraping measure. This client therefore performs a 2-hop handshake
(homepage -> search page) at the start of every list run to read the
*current* session's form token and column-key order, then reuses both for
every paginated POST within that same run (confirmed live: both stay valid
across many sequential POSTs on the same session/cookies -- see
CRAWLING_METHOD.md).
"""

import asyncio
import json
import re

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.constants import (
    AJAX_HEADERS,
    HEADERS,
    HOME_URL,
    MAX_RETRIES,
    OPERACION_ENDPOINT,
    PAGE_SIZE,
    RETRY_DELAY_BASE,
    SEARCH_PAGE_URL,
    TLS_PROFILE,
)

TOKEN_RE = re.compile(r'id="token"[^>]*value="([a-f0-9]+)"')
FORM_TOKEN_RE = re.compile(r'name="token" value="([a-f0-9]+)"')
COLS_SIMPLE_RE = re.compile(r'id="colsConvocatoriasSimple" type="hidden" value=\'(\[[^\]]+\])\'')


class FetchFailed(Exception):
    """A request never produced a usable response after retries."""


class HandshakeFailed(FetchFailed):
    """Could not extract the session token / column-key list from SICOES's own pages."""


async def _request(session: AsyncSession, method: str, url: str, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = await session.request(method, url, timeout=60, **kwargs)
            if r.status_code != 200 or not r.content:
                raise FetchFailed(f"{method} {url} returned {r.status_code} ({len(r.content)} bytes)")
            return r
        except (FetchFailed, RequestException, ConnectionError, TimeoutError) as e:
            # NOTE: curl_cffi's own RequestException/ConnectionError (raised on
            # a failed proxy CONNECT tunnel, DNS failure, TLS handshake error,
            # etc.) does NOT inherit from Python's builtin ConnectionError --
            # its MRO is RequestException -> CurlError -> OSError, a parallel
            # hierarchy. Both are caught explicitly, per the portfolio-wide
            # Babak 22b fix.
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
    raise FetchFailed(f"Exhausted {MAX_RETRIES} attempts for {method} {url!r}: {last_exc!r}")


async def handshake(session: AsyncSession, tipo: str) -> tuple[str, list[str]]:
    """Loads the homepage then the search page for `tipo`
    (convNacional/convInternacional) on `session`, returning
    (form_token, column_keys) for the operacion.php POSTs that follow. Must
    run on the same session whose cookies will be used for those POSTs --
    the token is bound to the session, not just echoed back."""
    r0 = await _request(session, "GET", HOME_URL, headers=HEADERS)
    m0 = TOKEN_RE.search(r0.text)
    if not m0:
        raise HandshakeFailed('could not find id="token" on the SICOES homepage -- page shape may have changed')
    home_token = m0.group(1)

    r1 = await _request(
        session, "GET", f"{SEARCH_PAGE_URL}?tipo={tipo}&token={home_token}", headers=HEADERS
    )
    m1 = FORM_TOKEN_RE.search(r1.text)
    m2 = COLS_SIMPLE_RE.search(r1.text)
    if not m1 or not m2:
        raise HandshakeFailed(
            f"could not find the form token / colsConvocatoriasSimple key list on the {tipo!r} search page "
            "-- SICOES may have changed its anti-scraping column-key scheme (see CRAWLING_METHOD.md)"
        )
    try:
        cols = json.loads(m2.group(1))
    except ValueError as e:
        raise HandshakeFailed(f"colsConvocatoriasSimple was not valid JSON: {e!r}") from e
    if not isinstance(cols, list) or len(cols) < 9:
        raise HandshakeFailed(f"colsConvocatoriasSimple had an unexpected shape: {cols!r}")
    return m1.group(1), cols


async def fetch_list_page(
    session: AsyncSession,
    form_token: str,
    tipo: str,
    start: int,
    *,
    entidad: str = "",
    objeto_contrato: str = "",
    solo_vigentes: bool = True,
    tipos_contratacion: tuple[str, ...] = ("B", "O", "S", "C"),
) -> dict:
    """One page (PAGE_SIZE rows) of SICOES's public Convocatorias search,
    "Simple" form -- see CRAWLING_METHOD.md for the discovered field set.
    `tipos_contratacion` selects which of Bienes/Obras/Servicios
    Generales/Consultoria to include (all four by default, matching the
    form's own default all-checked state)."""
    data = {
        "token": form_token,
        "entidad": entidad,
        "objetoContrato": objeto_contrato,
        "publicacionDesde": "",
        "publicacionHasta": "",
        "presentacionPropuestasDesde": "",
        "presentacionPropuestasHasta": "",
        "cuce1": "",
        "cuce2": "",
        "cuce3": "",
        "cuce4": "",
        "cuce5": "",
        "cuce6": "",
        "r1": "11" if solo_vigentes else "",
        "subasta": "",
        "tipo": "Simple",
        "operacion": tipo,
        "autocorrector": "",
        "nroRegistros": PAGE_SIZE,
        "draw": (start // PAGE_SIZE) + 1,
        "start": start,
        "length": PAGE_SIZE,
        "captcha": "",
    }
    label = {"B": "bienes", "O": "obras", "S": "servicios", "C": "consultoria"}
    for code in tipos_contratacion:
        if code in label:
            data[label[code]] = code

    r = await _request(session, "POST", OPERACION_ENDPOINT, data=data, headers=AJAX_HEADERS)
    try:
        return r.json()
    except ValueError as e:
        raise FetchFailed(
            f"search page start={start} tipo={tipo!r} returned non-JSON body "
            f"(likely a stale token -> homepage fallback): {e!r}"
        ) from e
