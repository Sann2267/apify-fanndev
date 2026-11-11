"""HTML parsing + record shaping.

Listing rows (`div.list-item`) are shared between /authors and
/affiliations, but carry different inner blocks, so each has its own
parser. Score values arrive Indonesian-formatted (`12.748` means twelve
thousand seven hundred forty-eight, not 12.748) -- see `parse_number`.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE_URL

_WS = re.compile(r"\s+")
_SINTA_ID = re.compile(r"SINTA ID\s*:\s*(\d+)")
_PROFILE_ID = re.compile(r"/(?:authors|affiliations)/profile/(\d+)")
_TOTALS = re.compile(
    r"Page\s+([\d.,]+)\s+of\s+([\d.,]+)\s*\|\s*Total Records\s+([\d.,]+)", re.I
)


def _txt(node) -> str:
    return _WS.sub(" ", node.get_text(" ", strip=True)).strip() if node else ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_number(raw: str | None):
    """SINTA renders numbers with Indonesian separators: `12.748` is 12,748
    and `1.610.976` is 1,610,976 -- the dot is a THOUSANDS separator, not a
    decimal point. Parsing these with float() would silently turn a
    12,748-point score into 12.748, so dots are stripped and the value is
    returned as an int. A value with a comma decimal (rare here) keeps its
    fractional part.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    s = s.replace(".", "")
    try:
        return int(s)
    except ValueError:
        return None


def _score_pairs(node) -> dict:
    """`<div class="pr-num">12.748</div><div class="pr-txt">SINTA Score
    Overall</div>` pairs, keyed by their label."""
    out = {}
    for num in node.select("div.pr-num"):
        label_node = num.find_next_sibling("div", class_="pr-txt")
        label = _txt(label_node)
        if label:
            out[label] = parse_number(_txt(num))
    return out


def _metrics_table(node) -> dict:
    """The listing card's Metrics table: rows of
    `<div class="pr-txt-metric">Scopus H-index</div> : <div>26</div>`.
    Note some rows are marked `d-none` (hidden in the UI) but still carry a
    real value -- they are read anyway rather than dropped."""
    out = {}
    cells = [_txt(d) for d in node.select("div.pr-txt-metric")]
    for i in range(0, len(cells) - 2, 3):
        label, sep, value = cells[i], cells[i + 1], cells[i + 2]
        if label and sep.strip() == ":":
            out[label] = parse_number(value)
    return out


def parse_totals(page_html: str) -> dict:
    m = _TOTALS.search(_WS.sub(" ", BeautifulSoup(page_html, "lxml").get_text(" ", strip=True)))
    if not m:
        return {}
    return {
        "page": parse_number(m.group(1)),
        "totalPages": parse_number(m.group(2)),
        "totalRecords": parse_number(m.group(3)),
    }


def parse_authors(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "lxml")
    out = []
    for card in soup.select("div.list-item"):
        name_link = card.select_one(".profile-name a")
        if not name_link:
            continue
        affil = card.select_one(".profile-affil a")
        dept = card.select_one(".profile-dept a")
        gs_node = card.select_one(".profile-name span.d-none")
        sinta_id = _SINTA_ID.search(_txt(card.select_one(".profile-id")) or "")
        profile_url = name_link.get("href")
        scores = _score_pairs(card)
        metrics = _metrics_table(card)
        img = card.select_one("img.avatar")

        out.append(
            {
                "sintaId": sinta_id.group(1) if sinta_id else None,
                "name": _txt(name_link),
                "profileUrl": profile_url,
                "googleScholarId": _txt(gs_node) or None,
                "affiliation": _txt(affil) or None,
                "affiliationId": (
                    _PROFILE_ID.search(affil.get("href")).group(1)
                    if affil and _PROFILE_ID.search(affil.get("href") or "")
                    else None
                ),
                "department": _txt(dept) or None,
                "subjects": [_txt(li) for li in card.select("ul.subject-list li")] or None,
                "sintaScoreOverall": scores.get("SINTA Score Overall"),
                "sintaScore3Yr": scores.get("SINTA Score 3Yr"),
                "scopusHIndex": metrics.get("Scopus H-index"),
                "wosHIndex": metrics.get("Wos H-index"),
                "googleHIndex": metrics.get("Google Scholar H-index"),
                "imageUrl": img.get("src") if img else None,
            }
        )
    return out


def parse_affiliations(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "lxml")
    out = []
    for card in soup.select("div.list-item"):
        link = card.select_one('a[href*="/affiliations/profile/"]')
        if not link:
            continue
        scores = _score_pairs(card)
        img = card.select_one("img")
        meta = card.select_one("div.meta-side")
        out.append(
            {
                "affiliationId": (
                    _PROFILE_ID.search(link.get("href")).group(1)
                    if _PROFILE_ID.search(link.get("href") or "")
                    else None
                ),
                "name": _txt(link),
                "profileUrl": link.get("href"),
                "sintaScoreOverall": scores.get("SINTA Score Overall"),
                "sintaScore3Yr": scores.get("SINTA Score 3 Yr") or scores.get("SINTA Score 3Yr"),
                "metaText": _txt(meta) or None,
                "imageUrl": img.get("src") if img else None,
            }
        )
    return out


def parse_author_profile(page_html: str, profile_url: str) -> dict:
    soup = BeautifulSoup(page_html, "lxml")
    name = _txt(soup.select_one("h3")) or _txt(soup.select_one("h1"))
    meta = soup.select_one("div.meta-profile")
    affil = meta.select_one('a[href*="/affiliations/profile/"]') if meta else None
    dept = meta.select_one('a[href*="/departments/profile/"]') if meta else None
    sinta_id = _SINTA_ID.search(_txt(meta) or "")
    scores = _score_pairs(soup.select_one("div.stat-profile") or soup)

    # The per-source metrics table: rows are Article / Citation / Cited
    # Document / H-Index, columns are Scopus / GScholar / WOS.
    publications = {}
    table = soup.select_one("table.stat-table")
    if table:
        headers = [_txt(th) for th in table.select("thead th")][1:]
        for row in table.select("tbody tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            label = _txt(cells[0])
            for header, cell in zip(headers, cells[1:]):
                if label and header:
                    publications[f"{header} {label}"] = parse_number(_txt(cell))

    return {
        "sintaId": sinta_id.group(1) if sinta_id else None,
        "name": name or None,
        "profileUrl": profile_url,
        "affiliation": _txt(affil) or None,
        "affiliationId": (
            _PROFILE_ID.search(affil.get("href")).group(1)
            if affil and _PROFILE_ID.search(affil.get("href") or "")
            else None
        ),
        "department": _txt(dept) or None,
        "subjects": [_txt(a) for a in soup.select("div.profile-subject a")] or None,
        "sintaScoreOverall": scores.get("SINTA Score Overall"),
        "sintaScore3Yr": scores.get("SINTA Score 3Yr"),
        "affilScore": scores.get("Affil Score"),
        "affilScore3Yr": scores.get("Affil Score 3Yr"),
        "publications": publications or None,
    }


def sinta_id_from_input(raw: str) -> str:
    s = (raw or "").strip()
    m = _PROFILE_ID.search(s)
    if m:
        return m.group(1)
    return s if s.isdigit() else ""


def absolute(path: str) -> str:
    return path if path.startswith("http") else f"{BASE_URL}{path}"


def wrap(item: dict, input_value: str, source: str = "S1-html", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type
    record.update(item)
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
