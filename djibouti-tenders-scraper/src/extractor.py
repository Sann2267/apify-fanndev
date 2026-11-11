"""Parsing + record builders for marchespublics.gouv.dj's two pages:
`current` (/marches, Livewire cards) and `awards` (/attribution, a plain
HTML table) -- genuinely different markup, parsed separately.
"""

from bs4 import BeautifulSoup, NavigableString

from src.constants import BASE


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (fail loud, never silently
    emit an empty/corrupt record)."""


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    return text or None


def _labeled_pairs_from_strong(container) -> dict[str, str | None]:
    """`/marches` cards repeat `<div class="col-md-6"><strong>Label
    :</strong> value</div>` -- read every such div's own text minus its
    `<strong>` label text."""
    pairs: dict[str, str | None] = {}
    for div in container.select("div.col-md-6"):
        strong = div.find("strong")
        if strong is None:
            continue
        label = _clean(strong.get_text(" ", strip=True)).rstrip(" :")
        full_text = _clean(div.get_text(" ", strip=True)) or ""
        label_text = _clean(strong.get_text(" ", strip=True)) or ""
        value = _clean(full_text[len(label_text) :]) if full_text.startswith(label_text) else _clean(full_text)
        pairs[label] = value
    return pairs


def _labeled_pairs_from_bold_br(cell) -> dict[str, str | None]:
    """`/attribution`'s first column repeats `<b>Label :</b> value<br/>`
    inline within one `<td>` -- walk its children, tracking the current
    label as each `<b>` is seen and accumulating following text nodes as
    that label's value until the next `<b>`."""
    pairs: dict[str, str | None] = {}
    current_label: str | None = None
    buffer: list[str] = []

    def flush():
        if current_label is not None:
            pairs[current_label] = _clean(" ".join(buffer))

    for node in cell.children:
        if getattr(node, "name", None) == "b":
            flush()
            current_label = _clean(node.get_text(" ", strip=True)).rstrip(" :")
            buffer = []
        elif getattr(node, "name", None) == "br":
            continue
        elif isinstance(node, NavigableString):
            buffer.append(str(node))
        else:
            buffer.append(node.get_text(" ", strip=True))
    flush()
    return pairs


# ---------------------------------------------------------------------------
# current -- /marches (Livewire cards)
# ---------------------------------------------------------------------------


def parse_current_cards(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    titles = [
        a for a in soup.select("div.card__title a[href]") if a["href"].startswith(f"{BASE}/marche/")
    ]
    cards = [a.find_parent("div", class_="card") for a in titles]
    cards = [c for c in cards if c is not None]
    if not cards:
        raise UnexpectedShape(f"{label}: no 'card__title' tender cards found -- page layout may have changed")

    records = []
    for card in cards:
        title_link = card.select_one("div.card__title a")
        title = _clean(title_link.get_text(" ", strip=True))
        detail_url = title_link.get("href")
        desc = card.select_one("div.card__description")
        fields = _labeled_pairs_from_strong(desc) if desc else {}
        records.append(
            {
                "title": title,
                "detailUrl": detail_url,
                "code": fields.get("Code"),
                "administrationContractante": fields.get("Administration Contractante"),
                "nature": fields.get("Nature"),
                "modalite": fields.get("Modalite de recherche") or fields.get("Modalité de recherche"),
                "dateParution": fields.get("Date de parution"),
                "dateLimiteRemiseOffres": fields.get("Date limite de remise des offres"),
                "lieuExecution": fields.get("Lieu d'execution") or fields.get("Lieu d'exécution"),
                "procedure": fields.get("Procedure") or fields.get("Procédure"),
            }
        )
    return records


def build_current_record(raw: dict) -> dict:
    return {k: raw.get(k) for k in ("title", "detailUrl", "code", "administrationContractante", "nature", "modalite", "dateParution", "dateLimiteRemiseOffres", "lieuExecution", "procedure")}


# ---------------------------------------------------------------------------
# awards -- /attribution (plain table)
# ---------------------------------------------------------------------------


def parse_award_rows(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr.row100.body")
    if not rows:
        raise UnexpectedShape(f"{label}: no 'row100 body' award rows found -- page layout may have changed")

    records = []
    for tr in rows:
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        fields = _labeled_pairs_from_bold_br(cells[0])
        supplier = _clean(cells[1].get_text(" ", strip=True))
        amount = _clean(cells[2].get_text(" ", strip=True))
        detail_link = cells[3].find("a", href=True) if len(cells) > 3 else None
        records.append(
            {
                "designation": fields.get("Designation") or fields.get("Désignation"),
                "procedure": fields.get("Procedure") or fields.get("Procédure"),
                "projet": fields.get("Projet"),
                "institution": fields.get("Institution"),
                "supplier": supplier,
                "amountDJF": amount,
                "detailUrl": detail_link["href"] if detail_link else None,
            }
        )

    if not records:
        raise UnexpectedShape(f"{label}: award rows found but zero records extracted -- page layout may have changed")
    return records


def build_award_record(raw: dict) -> dict:
    return {k: raw.get(k) for k in ("designation", "procedure", "projet", "institution", "supplier", "amountDJF", "detailUrl")}


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


RECORD_TYPES = {"current": "CURRENT_TENDER", "awards": "TENDER_AWARD"}
SOURCE_TAGS = {
    "current": "S1-livewire-html-marches",
    "awards": "S1-html-table-attribution",
}


def build_record(list_type: str, fields: dict) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": SOURCE_TAGS.get(list_type, list_type),
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
