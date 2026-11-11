"""HTTP client for Nicaragua's SISCAE public procurement search
(`www.gestion.nicaraguacompra.gob.ni/siscae/portal/adquisiciones-gestion/*`).

No login, no CAPTCHA, no TLS-fingerprint gate observed during recon -- see
`constants.py` for the full recon summary. `curl_cffi` `chrome124` is used
for portfolio-wide consistency. The server is occasionally slow (one POST
search hit a clean 40s timeout with 0 bytes, then succeeded normally on
retry at 90s) -- not a block signal, so retries use a generous timeout.

The retry loop wraps ALL request calls broadly: `curl_cffi`'s own exception
hierarchy (`CurlError` -> `OSError`) does NOT inherit from Python's builtin
`ConnectionError`/`TimeoutError` despite sharing class names, so a narrower
except list would silently miss real transient failures (portfolio-wide
Babak 22b fix).
"""

import asyncio

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    SEARCH_FORM_URL,
    STATUS_LIST_URL,
    TLS_PROFILE,
)
from src.extractor import UnexpectedShape, extract_form_fields, parse_procedure_rows, resolve_select_value

_SEARCH_FORM_ID = "inicioBusqForm"
_SUBMIT_BUTTON_LABEL = "Buscar"

_KEYWORD_FIELD = "inicioBusqForm:nombreAdqId"
_NUMERO_FIELD = "inicioBusqForm:numeroAdqId"
_ESTADO_FIELD = "inicioBusqForm:estadoAdqPuId"
_INSTITUCION_FIELD = "inicioBusqForm:institucion3Id"
_DEPARTAMENTO_FIELD = "inicioBusqForm:departamentoId"
_RESULTADOS_FIELD = "inicioBusqForm:resultadosItems"
_LINK_HIDDEN_FIELD = "inicioBusqForm:_link_hidden_"


class FetchFailed(Exception):
    """A request completed (no exception) but returned a non-200 status or
    an empty body -- treated as retryable up to MAX_RETRIES, then raised."""


class SiscaeClient:
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

    async def fetch_by_status(self, estado: str) -> list[dict]:
        """Quick single-status browse -- a stateless GET, no session/form
        state needed. Returns whatever currently matches `estado` (observed
        ~10 rows per status during recon -- upstream's own live volume, not
        a page-size cap this actor imposes)."""
        r = await self._with_retry("GET", STATUS_LIST_URL, params={"proc_estado": estado})
        return parse_procedure_rows(r.text)  # [] or raises UnexpectedShape -- not swallowed

    async def search(
        self,
        *,
        keyword: str = "",
        numero: str = "",
        estados: list[str] | None = None,
        institucion_query: str = "",
        departamento_query: str = "",
        resultados_items: str = "CINCUENTA",
    ) -> tuple[list[dict], dict]:
        """Runs the full search form (`inicioBusqForm`) POST -- supports
        keyword/number/institution/department substring filters, multiple
        status values at once, and up to 100 results per page
        (`resultados_items="CIEN"`). Returns `(rows, filters_used)`.
        """
        r = await self._with_retry("GET", SEARCH_FORM_URL)
        form_html = r.text
        fields, action_url = extract_form_fields(form_html, _SEARCH_FORM_ID)  # raises UnexpectedShape -- not swallowed
        if not action_url:
            raise RuntimeError("search form has no action URL -- upstream markup likely changed")

        institucion_value = "-1"
        if institucion_query:
            resolved = resolve_select_value(form_html, _SEARCH_FORM_ID, _INSTITUCION_FIELD, institucion_query)
            if resolved:
                institucion_value = resolved

        departamento_value = "-1"
        if departamento_query:
            resolved = resolve_select_value(form_html, _SEARCH_FORM_ID, _DEPARTAMENTO_FIELD, departamento_query)
            if resolved:
                departamento_value = resolved

        estados = estados or ["VIGENTE"]
        filters_used = {
            "keyword": keyword or None,
            "numero": numero or None,
            "estados": estados,
            "institucion": institucion_query or None,
            "institucionValue": institucion_value,
            "departamento": departamento_query or None,
            "departamentoValue": departamento_value,
            "resultadosItems": resultados_items,
        }

        fields.update(
            {
                _KEYWORD_FIELD: keyword,
                _NUMERO_FIELD: numero,
                _INSTITUCION_FIELD: institucion_value,
                _DEPARTAMENTO_FIELD: departamento_value,
                _RESULTADOS_FIELD: resultados_items,
                f"{_SEARCH_FORM_ID}_SUBMIT": "1",
                "autoScroll": "0",
                _LINK_HIDDEN_FIELD: "",
            }
        )

        # Find the "Buscar" submit button generically and add it as the
        # clicked control -- its auto-generated component id changes across
        # unrelated form edits, so it's read from the live page, not hardcoded.
        soup = BeautifulSoup(form_html, "lxml")
        form = soup.find("form", attrs={"id": _SEARCH_FORM_ID})
        buscar_btn = form.find("input", attrs={"type": "submit", "value": _SUBMIT_BUTTON_LABEL}) if form else None
        if buscar_btn and buscar_btn.get("name"):
            fields[buscar_btn["name"]] = _SUBMIT_BUTTON_LABEL

        # inicioBusqForm:estadoAdqPuId is a repeatable checkbox field -- send
        # one pair per selected status, on top of whatever extract_form_fields
        # kept from the (single, pre-checked) default.
        fields.pop(_ESTADO_FIELD, None)
        form_pairs = list(fields.items()) + [(_ESTADO_FIELD, e) for e in estados]

        r2 = await self._with_retry("POST", action_url, data=form_pairs, headers={"Referer": SEARCH_FORM_URL})
        rows = parse_procedure_rows(r2.text)  # [] or raises UnexpectedShape -- not swallowed
        return rows, filters_used

    async def close(self):
        await self.session.close()
