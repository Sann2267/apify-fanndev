"""Record shaping for SICOES's Convocatorias (public tender) search results.

Each raw row from `operacion.php` is a dict keyed by session-randomized
strings (e.g. "iz8cNB9P") -- the client's `handshake()` reads that session's
own `colsConvocatoriasSimple` key list, in the same fixed positional order
as the `<thead>` on the live search page (see `constants.COLUMN_ORDER` and
CRAWLING_METHOD.md). `build_list_record` zips the two together to recover
stable field names before this actor ever emits anything.

The "Archivos"/"Formularios"/"Reportes" columns carry raw HTML with
JS `onclick` handlers wired to encrypted download tokens and (for the
"Ver Ficha" summary PDF) a Cloudflare Turnstile CAPTCHA gate -- neither is
reproducible over plain HTTP (see CRAWLING_METHOD.md), so this actor does
not attempt to fetch the underlying PDFs. It does surface which document
labels are available (`documentLabels`) and the process's own reference
CUCE so a user can look the tender up manually.
"""

import re
from datetime import datetime, timezone

from src.constants import COLUMN_ORDER

_ANCHOR_TEXT_RE = re.compile(r"<a[^>]*>([^<]+)</a>")


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _document_labels(archivos_html: str | None) -> list[str]:
    if not archivos_html:
        return []
    return [m.strip() for m in _ANCHOR_TEXT_RE.findall(archivos_html) if m.strip()]


def build_list_record(row: dict, session_cols: list[str], tipo: str) -> dict:
    if not isinstance(row, dict):
        raise UnexpectedShape(f"[tipo={tipo}] row was not a dict: {type(row)}")

    values = {}
    for name, key in zip(COLUMN_ORDER, session_cols):
        values[name] = row.get(key)

    if not values.get("cuce"):
        raise UnexpectedShape(
            f"[tipo={tipo}] row missing a CUCE after positional column mapping -- keys seen: "
            f"{list(row.keys())} vs expected session_cols={session_cols} -- "
            "SICOES's table shape or column order has likely changed"
        )

    return {
        "_input": f"list:tipo={tipo}",
        "_source": "S1-operacion-php",
        "_scrapedAt": utc_now_iso(),
        "cuce": values.get("cuce"),
        "entidad": values.get("entidad"),
        "tipoContratacion": values.get("tipoContratacion"),
        "modalidad": values.get("modalidad"),
        "objetoContratacion": values.get("objetoContratacion"),
        "subastaElectronica": values.get("subastaElectronica"),
        "fechaPublicacion": values.get("fechaPublicacion"),
        "fechaPresentacionPropuestas": values.get("fechaPresentacionPropuestas"),
        "estado": values.get("estado"),
        "documentLabels": _document_labels(values.get("archivosHtml")),
        "tipo": tipo,
        "sourceUrl": (
            "https://www.sicoes.gob.bo/portal/contrataciones/busqueda/convocatorias.php"
            f"?tipo={tipo}"
        ),
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
