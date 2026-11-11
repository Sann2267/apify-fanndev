"""Parsing + raw-passthrough record builders for ARMP Madagascar's three
public e-GP data sources: `avis` (live calls for tender), `dossiers` (the
multi-year archive), and `contrats` (awarded contracts).

Each shape is genuinely different upstream (server-rendered HTML grouped by
region, a server-rendered HTML search-result table with an embedded detail
modal per row, and a real JSON endpoint respectively) -- see constants.py
for the full recon summary of why.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

REGION_HEADER_RE = re.compile(r"REGION\s*:\s*(.+?)\s*\(\s*(\d+)\s*avis\s*\)", re.IGNORECASE)
ENTITE_RE = re.compile(r"<b>([^<]*)</b>")
REF_RE = re.compile(r"<b>Ref:</b>\s*([^<]*)")
MODE_RE = re.compile(r"<b>Mode:</b>\s*([^<]*)")
NUMERO_RE = re.compile(r"<b>N°\s*</b>\s*([^<]*)")
DU_RE = re.compile(r"Du:\s*([^|]*)")
AU_RE = re.compile(r"Au:\s*([^|]*)")

MODAL_DETAIL_RE = re.compile(
    r'<div class="modal fade" id="detail([^"]+)".*?'
    r"DATE DU DOSSIER</b></td>\s*<td><text[^>]*/>\s*([^<]*)</text>.*?"
    r"FINANCEMENT</b></td>\s*<td><text[^>]*/>\s*([^<]*)</text>.*?"
    r"NOM DE LA PRMP</b></td>\s*<td><text[^>]*/>\s*([^<]*)</text>",
    re.S,
)


class UnexpectedShape(Exception):
    """Raised when a page/response no longer matches the structure this
    parser was written against -- must NOT be swallowed (see project
    convention: fail loud, never silently emit an empty/corrupt record)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


# ---------------------------------------------------------------------------
# avis -- live calls for tender, grouped by region (GET index.php)
# ---------------------------------------------------------------------------


def parse_avis_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    region_headers = [h for h in soup.find_all("h7") if REGION_HEADER_RE.search(h.get_text(" ", strip=True))]
    if not region_headers:
        raise UnexpectedShape("No 'REGION : ... (N avis)' section headers found on index.php -- page shape may have changed")

    rows: list[dict] = []
    for header in region_headers:
        m = REGION_HEADER_RE.search(header.get_text(" ", strip=True))
        region_name = m.group(1).strip()
        table = header.find_next("table")
        if table is None:
            continue
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            td0_html = tds[0].decode_contents()
            entite_m = ENTITE_RE.search(td0_html)
            ref_m = REF_RE.search(td0_html)
            mode_m = MODE_RE.search(td0_html)
            numero_m = NUMERO_RE.search(td0_html)
            date_text = tds[2].get_text("|", strip=True)
            du_m = DU_RE.search(date_text)
            au_m = AU_RE.search(date_text)
            pdf_link = tds[3].find("a", href=True)

            rows.append(
                {
                    "region": region_name,
                    "entite": _clean(entite_m.group(1)) if entite_m else None,
                    "reference": _clean(ref_m.group(1)) if ref_m else None,
                    "modePassation": _clean(mode_m.group(1)) if mode_m else None,
                    "numero": _clean(numero_m.group(1)) if numero_m else None,
                    "objet": _clean(tds[1].get_text(" ", strip=True)),
                    "dateDu": _clean(du_m.group(1)) if du_m else None,
                    "dateAu": _clean(au_m.group(1)) if au_m else None,
                    "noticePdfUrl": pdf_link["href"] if pdf_link else None,
                }
            )

    if not rows:
        raise UnexpectedShape("Found region headers but zero avis rows on index.php -- table shape may have changed")
    return rows


# ---------------------------------------------------------------------------
# dossiers -- multi-year searchable archive (POST dossier_sub_list_modal.php)
# ---------------------------------------------------------------------------


def parse_dossiers_page(html: str) -> list[dict]:
    # The results table always comes before the (much larger) per-row detail
    # modals in document order -- cutting there keeps BeautifulSoup off the
    # multi-ten-MB modal blob when all we need here is the summary table.
    table_html = html.split('<div class="modal fade"', 1)[0]
    soup = BeautifulSoup(table_html, "lxml")
    table = soup.find("table", id="example1") or soup.find("table")
    if table is None:
        raise UnexpectedShape("No results table found in dossier archive response -- page shape may have changed")

    tbody = table.find("tbody") or table
    trs = tbody.find_all("tr")
    if not trs:
        raise UnexpectedShape("Dossier archive table has no <tr> rows -- page shape may have changed")

    rows = []
    for tr in trs:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        rows.append(
            {
                "institution": _clean(tds[0].get_text(" ", strip=True)),
                "modePassationLabel": _clean(tds[1].get_text(" ", strip=True)),
                "natureMarche": _clean(tds[2].get_text(" ", strip=True)),
                "reference": _clean(tds[3].get_text(" ", strip=True)),
                "numero": _clean(tds[4].get_text(" ", strip=True)),
                "objet": _clean(tds[5].get_text(" ", strip=True)),
            }
        )

    if not rows:
        raise UnexpectedShape("Dossier archive table rows all had fewer than 6 columns -- shape may have changed")
    return rows


def merge_dossier_modal_detail(html: str, rows: list[dict]) -> None:
    """Best-effort enrichment from each row's own embedded detail modal
    (dossier date, financing source, PRMP officer name). Mutates `rows` in
    place and never raises: this is supplementary data riding along in the
    same response we already downloaded, not a separate request, so a
    parsing miss here just means those few extra fields stay absent --
    the core row from parse_dossiers_page() above is already a complete
    record without it."""
    wanted = {r["numero"] for r in rows if r.get("numero")}
    if not wanted:
        return
    detail_by_numero: dict[str, dict] = {}
    try:
        for m in MODAL_DETAIL_RE.finditer(html):
            numero = m.group(1)
            if numero in wanted and numero not in detail_by_numero:
                detail_by_numero[numero] = {
                    "dateDossier": _clean(m.group(2)),
                    "financement": _clean(m.group(3)),
                    "prmpNom": _clean(m.group(4)),
                }
    except Exception:  # noqa: BLE001 -- enrichment only, never fatal
        return
    for r in rows:
        extra = detail_by_numero.get(r.get("numero"))
        if extra:
            r.update(extra)


# ---------------------------------------------------------------------------
# contrats -- awarded contracts, a real JSON endpoint (POST contrat_action.php)
# ---------------------------------------------------------------------------


def parse_contrats_json(text: str) -> list[dict]:
    start = text.find("{")
    if start == -1:
        raise UnexpectedShape("Awarded-contracts endpoint returned no JSON object -- response shape may have changed")
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"Awarded-contracts endpoint returned malformed JSON: {e}") from e

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise UnexpectedShape("Awarded-contracts JSON has no top-level 'data' list -- shape may have changed")
    return data  # raw passthrough of upstream's own field names


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

RECORD_TYPES = {"avis": "TENDER_AVIS", "dossiers": "TENDER_DOSSIER", "contrats": "TENDER_CONTRAT"}


def build_record(list_type: str, source: str, fields: dict) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": RECORD_TYPES.get(list_type, list_type),
        **fields,
    }


def build_error_record(list_type: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": f"list:{list_type}",
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
