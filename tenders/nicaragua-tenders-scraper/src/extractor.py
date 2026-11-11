"""Parsing for SISCAE's JBoss Portal / Apache MyFaces (JSF) portlet pages
(`www.gestion.nicaraguacompra.gob.ni/siscae/portal/adquisiciones-gestion/*`).

Two page shapes matter here, both plain server-rendered HTML (no JSON, no
client-side JS driving the data) -- and both render the exact same
`listadoProcedimientos` JSF grid component, so one parser
(`parse_procedure_rows`) handles either source:

1. `busquedaProcedimientosVigentes?proc_estado=<ESTADO>` -- a stateless GET,
   quick single-status browse.
2. `busqueda?accion=todos` (`inicioBusqForm`) POST results -- the full
   search form, supports keyword/institution/department/status(es)/page
   size. This actor's client extracts the form's COMPLETE current field set
   generically (like this portfolio's Honduras actor) rather than a
   hand-typed subset, since MyFaces portlet forms carry several other hidden
   fields (`_SUBMIT`, `autoScroll`, `_link_hidden_`) that must round-trip.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Search form fields (POST path only)
# ---------------------------------------------------------------------------


def extract_form_fields(page_html: str, form_id: str) -> tuple[dict, str | None]:
    """Pulls every hidden `<input>` and every `<select>`'s currently-selected
    `<option>` out of the named `<form>`, plus the form's own `action` URL
    (which embeds this session's JBoss Portal window id and jsessionid).
    Checkbox/radio inputs are only included if pre-checked -- callers overlay
    their own desired checkbox values on top (see `client.py`, `estadoAdqPuId`
    is repeatable). Raises `UnexpectedShape` if the form itself isn't found
    (e.g. an error/redirect page came back instead)."""
    soup = BeautifulSoup(page_html, "lxml")
    form = soup.find("form", attrs={"id": form_id})
    if form is None:
        raise UnexpectedShape(f"no <form id={form_id!r}> found on page -- likely an error/redirect page")

    fields: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "text").lower()
        if itype in ("checkbox", "radio") and not inp.has_attr("checked"):
            continue
        if itype == "submit":
            continue  # caller adds the specific button name=value it wants to "click"
        fields[name] = inp.get("value", "")
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        fields[name] = opt.get("value", "") if opt else ""
    return fields, form.get("action")


def resolve_select_value(page_html: str, form_id: str, select_name: str, query: str) -> str | None:
    """Case-insensitive substring match of `query` against a `<select>`'s
    option text (e.g. institution/department dropdowns). Returns the
    matching option's `value`, or `None` if nothing matched (caller falls
    back to the default/'Todas' option)."""
    soup = BeautifulSoup(page_html, "lxml")
    form = soup.find("form", attrs={"id": form_id})
    if form is None:
        return None
    select = form.find("select", attrs={"name": select_name})
    if select is None:
        return None
    needle = query.strip().lower()
    if not needle:
        return None
    for opt in select.find_all("option"):
        if needle in opt.get_text(strip=True).lower():
            return opt.get("value")
    return None


# ---------------------------------------------------------------------------
# Procedure list rows (shared by both GET-by-status and POST-search results)
# ---------------------------------------------------------------------------


def _leaf_spans(tag) -> list:
    """Spans with no nested `<span>` child, in document order -- this JSF
    grid nests a nav/label `<span>` around each real value `<span>`, so a
    plain `find_all('span')` would double-count every value."""
    return [s for s in tag.find_all("span") if not s.find("span")]


def _parse_one_row(tr) -> dict:
    tds = tr.find_all("td", recursive=False)
    if len(tds) < 2:
        raise UnexpectedShape(f"procedure row has {len(tds)} <td> cells, expected >= 2")

    # Column 1 (~10%): procedure type + number, two stacked leaf spans.
    type_spans = [s.get_text(strip=True) for s in _leaf_spans(tds[0])]
    tipo = type_spans[0] if len(type_spans) > 0 else None
    numero = type_spans[1] if len(type_spans) > 1 else None

    # Column 2 (~75%): a "grid" table of label:value fields (Estado, Codigo
    # SIGAF, Publicacion, Cierre, Ultima Actualizacion -- label set can vary
    # slightly by status), followed by a sibling table with
    # institucion / clasificacion(es) / objeto (title), one per row, no
    # explicit label spans.
    fields: dict[str, str] = {}
    institucion = objeto = None
    clasificaciones: list[str] = []

    grid_table = tds[1].find("table", class_="grid")
    if grid_table is not None:
        texts = [s.get_text(strip=True) for s in _leaf_spans(grid_table)]
        for i in range(0, len(texts) - 1, 2):
            label = texts[i].rstrip(":").strip()
            if label:
                fields[label] = texts[i + 1]

        info_table = grid_table.find_next_sibling("table")
        if info_table is not None:
            inner = info_table.find("tbody") or info_table
            info_rows = inner.find_all("tr", recursive=False)
            if len(info_rows) > 0:
                institucion = info_rows[0].get_text(strip=True) or None
            if len(info_rows) > 1:
                # Multiple classifications render as sibling leaf spans with a
                # literal ", " separator span between them -- drop
                # punctuation-only fragments, keep the real category strings.
                clasificaciones = [
                    t
                    for t in (s.get_text(strip=True) for s in _leaf_spans(info_rows[1]))
                    if t and t.strip(",;. ") != ""
                ]
            if len(info_rows) > 2:
                objeto = info_rows[2].get_text(strip=True) or None

    if tipo is None and not fields and institucion is None:
        raise UnexpectedShape("procedure row parsed no recognizable fields at all -- upstream markup likely changed")

    # "Cierre" label varies by status (cierreV / cierreVigenteV etc. as HTML
    # ids, but the visible label text is consistently a variant of "Cierre")
    cierre = next((v for k, v in fields.items() if k.lower().startswith("cierre")), None)

    return {
        "tipoProcedimiento": tipo,
        "numeroProcedimiento": numero,
        "estado": fields.get("Estado"),
        "codigoSigaf": fields.get("Código SIGAF") or fields.get("Codigo SIGAF"),
        "publicacion": fields.get("Publicación") or fields.get("Publicacion"),
        "cierre": cierre,
        "ultimaActualizacion": fields.get("Última Actualización") or fields.get("Ultima Actualizacion"),
        "institucion": institucion,
        "clasificaciones": clasificaciones,
        "objeto": objeto,
    }


def parse_procedure_rows(page_html: str) -> list[dict]:
    """Parses the `listadoProcedimientos` JSF grid (shared by the
    GET-by-status and POST-search paths) into one dict per procedure.
    Returns `[]` if the container `<tbody>` is simply absent (a legitimate
    "this search matched nothing" outcome). Raises `UnexpectedShape` if the
    container IS present but not a single row could be parsed (upstream
    markup changed)."""
    soup = BeautifulSoup(page_html, "lxml")
    tbody = soup.find(id=lambda x: x and x.endswith(":listadoProcedimientos:tbody_element"))
    if tbody is None:
        return []

    rows = []
    for tr in tbody.find_all("tr", recursive=False):
        rows.append(_parse_one_row(tr))
    if not rows:
        raise UnexpectedShape("#...listadoProcedimientos:tbody_element present but no data rows parsed out of it")
    return rows


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def build_list_record(row: dict, filters: dict) -> dict:
    return {
        "_input": filters,
        "_source": "S1-jsf-portlet-grid",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error_record(input_value, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
