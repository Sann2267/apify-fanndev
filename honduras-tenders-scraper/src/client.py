"""HTTP client for Honduras' ONCAE legacy tender search
(`sicc.honducompras.gob.hn/HC/procesos/*.aspx`).

No WAF, no CAPTCHA, no TLS-fingerprint gate observed during recon -- plain
IIS fronting an old ASP.NET WebForms app. `curl_cffi` `chrome124` is used
for portfolio-wide consistency. The server itself is genuinely slow/flaky
(20-40s response times, occasional timeouts with a mostly-complete response
already received) -- NOT a block signal, so retries use a generous timeout
and do not treat a timeout as fatal until `MAX_RETRIES` is exhausted.

The retry loop wraps ALL request calls broadly: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures (portfolio-wide
Babak 22b fix).
"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    LIST_PAGE_DELAY,
    LIST_URL,
    MAX_LIST_PAGES_SAFETY_CAP,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
)
from src.extractor import (
    UnexpectedShape,
    extract_form_fields,
    has_next_page,
    parse_list_rows,
    resolve_entidad_value,
)

_SEARCH_BUTTON_FIELD = "ctl00$cphCuerpo$wpParametros$btnBuscar"
_ENTIDAD_FIELD = "ctl00$cphCuerpo$wpParametros$ddlEntidades"
_UC_FIELD = "ctl00$cphCuerpo$wpParametros$ddlUC"
_ETAPA_FIELD = "ctl00$cphCuerpo$wpParametros$ddlEtapas"
_MODALIDAD_FIELD = "ctl00$cphCuerpo$wpParametros$ddlModalidad"
_TIPO_ADQ_FIELD = "ctl00$cphCuerpo$wpParametros$ddlTipoAdquisicion"
_EXPEDIENTE_FIELD = "ctl00$cphCuerpo$wpParametros$txtExpediente"
_FECHA_INICIO_FIELD = "ctl00_cphCuerpo_wpParametros_wdInicio_input"
_FECHA_FIN_FIELD = "ctl00_cphCuerpo_wpParametros_wdFin_input"
_GRID_EVENT_TARGET = "ctl00$cphCuerpo$gvResultados"


class FetchFailed(Exception):
    """A request completed (no exception) but returned a non-200 status or
    an empty body -- treated as retryable up to MAX_RETRIES, then raised."""


class HonduComprasClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=REQUEST_TIMEOUT,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if r.status_code == 200 and r.text:
                    return r
                last_exc = FetchFailed(f"{method} {url} -> HTTP {r.status_code}, {len(r.text)} bytes")
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
            await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {method} {url}: {last_exc!r}")

    async def search_list(
        self,
        *,
        entidad_query: str | None = None,
        etapa: str = "0",
        modalidad: str = "0",
        tipo_adquisicion: str = "0",
        expediente: str = "",
        fecha_inicio: str = "",
        fecha_fin: str = "",
        max_results: int = 50,
    ) -> tuple[list[dict], dict]:
        """Runs the search POST plus as many `Page$N` pagination postbacks
        as needed to reach `max_results` (or run out of pages), all on this
        client's own session (required -- each postback's `__EVENTVALIDATION`
        is tied to the session that issued the prior response). Returns
        `(rows, filters_used)` -- `filters_used` echoes back what was
        actually applied (e.g. the resolved entidad ID) for the `_input`
        envelope field.
        """
        r = await self._with_retry("GET", LIST_URL)
        fields = extract_form_fields(r.text)

        entidad_value = "0"
        if entidad_query:
            resolved = resolve_entidad_value(r.text, entidad_query)
            if resolved:
                entidad_value = resolved

        filters_used = {
            "entidad": entidad_query or None,
            "entidadValue": entidad_value,
            "etapa": etapa,
            "modalidad": modalidad,
            "tipoAdquisicion": tipo_adquisicion,
            "expediente": expediente or None,
            "fechaInicio": fecha_inicio or None,
            "fechaFin": fecha_fin or None,
        }

        fields.update(
            {
                _ENTIDAD_FIELD: entidad_value,
                _UC_FIELD: "0",
                _ETAPA_FIELD: etapa,
                _MODALIDAD_FIELD: modalidad,
                _TIPO_ADQ_FIELD: tipo_adquisicion,
                _EXPEDIENTE_FIELD: expediente,
                _FECHA_INICIO_FIELD: fecha_inicio,
                _FECHA_FIN_FIELD: fecha_fin,
                _SEARCH_BUTTON_FIELD: "Buscar",
            }
        )

        r2 = await self._with_retry("POST", LIST_URL, data=fields)
        all_rows = parse_list_rows(r2.text)  # [] or raises UnexpectedShape -- not swallowed

        prev_html = r2.text
        page_num = 2
        while len(all_rows) < max_results and page_num <= MAX_LIST_PAGES_SAFETY_CAP:
            if not has_next_page(prev_html, page_num):
                break
            fields2 = extract_form_fields(prev_html)
            fields2.pop(_SEARCH_BUTTON_FIELD, None)
            fields2["__EVENTTARGET"] = _GRID_EVENT_TARGET
            fields2["__EVENTARGUMENT"] = f"Page${page_num}"

            r3 = await self._with_retry("POST", LIST_URL, data=fields2)
            try:
                page_rows = parse_list_rows(r3.text)
            except UnexpectedShape:
                break  # ran off the end of the pager unexpectedly -- stop, keep what we have
            if not page_rows:
                break

            all_rows.extend(page_rows)
            prev_html = r3.text
            page_num += 1
            if len(all_rows) < max_results:
                await asyncio.sleep(LIST_PAGE_DELAY)

        return all_rows[:max_results], filters_used

    async def fetch_detail(self, url: str) -> str:
        """Detail pages are stateless `GET`s -- confirmed during recon by
        fetching one on a freshly-created session with no prior request.
        Returns the raw HTML; parsing is the caller's job (so `main.py` can
        catch `UnexpectedShape` per-URL without re-fetching)."""
        r = await self._with_retry("GET", url)
        return r.text

    async def close(self):
        await self.session.close()
