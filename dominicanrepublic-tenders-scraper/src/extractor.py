"""Record shaping for DGCP's public procurement REST API.

Every `/procesos` row is passed through **verbatim** (raw passthrough,
minimal renaming -- see .ai/CLAUDE.md principle #5): DGCP's own Spanish
field names (`codigo_proceso`, `unidad_compra`, `monto_estimado`,
`fecha_publicacion`, ...) are kept as-is rather than translated or renamed,
so nothing drifts silently if DGCP adds/renames a field upstream. This
actor's own additions are limited to the `_input`/`_source`/`_scrapedAt`
envelope and, on detail records, the nested `contratos`/`ofertas`/
`articulos` arrays (also passed through verbatim) plus small `*Count`
convenience fields.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_list_record(row: dict, filters_desc: str) -> dict:
    if not isinstance(row, dict) or "codigo_proceso" not in row:
        raise UnexpectedShape(
            f"[list {filters_desc}] row missing 'codigo_proceso' -- keys seen: "
            f"{list(row.keys()) if isinstance(row, dict) else type(row)} -- "
            "upstream /procesos shape has likely changed"
        )
    return {
        "_input": f"list:{filters_desc}",
        "_source": "S1-api-procesos",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_detail_record(codigo_proceso: str, data: dict) -> dict:
    proceso = data.get("proceso")
    if not isinstance(proceso, dict) or "codigo_proceso" not in proceso:
        raise UnexpectedShape(
            f"[detail {codigo_proceso}] 'proceso' missing/malformed -- "
            f"keys seen: {list(data.keys()) if isinstance(data, dict) else type(data)} -- "
            "upstream API shape has likely changed"
        )
    contratos = data.get("contratos") or []
    ofertas = data.get("ofertas") or []
    articulos = data.get("articulos") or []
    return {
        "_input": codigo_proceso,
        "_source": "S1-api-procesos+contratos+ofertas+articulos",
        "_scrapedAt": utc_now_iso(),
        **proceso,
        "contratos": contratos,
        "contratosCount": len(contratos),
        "contratosTotalUpstream": data.get("contratos_total_upstream"),
        "ofertas": ofertas,
        "ofertasCount": len(ofertas),
        "ofertasTotalUpstream": data.get("ofertas_total_upstream"),
        "articulos": articulos,
        "articulosCount": len(articulos),
        "articulosTotalUpstream": data.get("articulos_total_upstream"),
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
