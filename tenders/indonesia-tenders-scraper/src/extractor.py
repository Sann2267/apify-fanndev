"""Record shaping for SPSE Nasional (LKPP's national tender search).

Two upstream shapes feed this actor:

1. `POST /nasional/dt/lelang` (list mode) -- a DataTables server-side
   listing endpoint. Each row is a fixed-position 15-element array (not an
   object with keys) -- the field meaning of each index was reverse
   engineered from the search page's own render function
   (`/nasional/public/js/*` inline script) and cross-checked against the
   labeled fields on the detail page for the same tender. See
   CRAWLING_METHOD.md for the full index map.

2. `GET /nasional/lelang/<kode>/pengumumanlelang` (detail mode) -- a
   server-rendered HTML page: a `<table>` of Indonesian label/value rows
   (`Kode Tender`, `Nama Tender`, `Tahun Anggaran`, ...). Parsed generically
   by label rather than fixed position, with a translation table for known
   labels and a slugified fallback key for any label not yet seen -- so an
   upstream field this actor doesn't recognize is still passed through
   under a generated key instead of silently dropped.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

BADGE_RE = re.compile(r"<span[^>]*class=['\"]badge[^'\"]*['\"][^>]*>([^<]*)</span>")
TAG_RE = re.compile(r"<[^>]+>")
YEAR_RE = re.compile(r"\b(20\d{2})\b")


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_title(raw: str) -> tuple[str, list[str]]:
    """Strips the embedded status-badge <span> tags SPSE sometimes injects
    straight into the title string (e.g. "... <span class='badge
    badge-warning'>Tender Ulang</span>") and returns (clean_title, badges)."""
    badges = [b.strip() for b in BADGE_RE.findall(raw) if b.strip()]
    clean = TAG_RE.sub("", raw).strip().strip(",").strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean, badges


def build_list_record(row: list, input_tag: str) -> dict:
    if not isinstance(row, list) or len(row) < 11:
        raise UnexpectedShape(
            f"[{input_tag}] row is not a >=11-element array -- "
            f"got: {row!r} -- upstream table shape has likely changed"
        )

    title, badges = _clean_title(str(row[1] or ""))
    jenis_ta = str(row[8] or "")
    if " - TA " in jenis_ta:
        jenis_pengadaan, ta_part = jenis_ta.split(" - TA ", 1)
    else:
        jenis_pengadaan, ta_part = jenis_ta, ""
    tahun_anggaran = [int(y) for y in YEAR_RE.findall(ta_part)]

    return {
        "_input": input_tag,
        "_source": "S1-dt-lelang",
        "_scrapedAt": utc_now_iso(),
        "kode": row[0],
        "namaPaket": title,
        "statusBadges": badges,
        "instansi": row[2],
        "tahapanSaatIni": row[3],
        "nilaiHPS": row[4],
        "metodeKualifikasi": row[5],
        "jenis": row[6],
        "metodeEvaluasi": row[7],
        "jenisPengadaan": jenis_pengadaan.strip() or None,
        "tahunAnggaran": tahun_anggaran,
        "nilaiKontrak": row[10] if row[10] and "belum dibuat" not in str(row[10]) else None,
        "kontrakSudahDibuat": bool(row[10]) and "belum dibuat" not in str(row[10] or ""),
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

_LABEL_MAP = {
    "kode tender": "kodeTender",
    "nama tender": "namaTender",
    "uraian singkat pekerjaan": "uraianSingkatPekerjaan",
    "tanggal pembuatan": "tanggalPembuatan",
    "tahap tender saat ini": "tahapTenderSaatIni",
    "k/l/pd/instansi lainnya": "instansi",
    "satuan kerja": "satuanKerja",
    "jenis pengadaan": "jenisPengadaan",
    "metode pengadaan": "metodePengadaan",
    "khusus orang asli papua (oap)": "khususOrangAsliPapua",
    "tahun anggaran": "tahunAnggaranRaw",
    "jenis kontrak": "jenisKontrak",
    "lokasi pekerjaan": "lokasiPekerjaan",
    "kualifikasi usaha": "kualifikasiUsaha",
    "syarat kualifikasi": "syaratKualifikasi",
    "rencana umum pengadaan": "rencanaUmumPengadaan",
}


def _slugify(label: str) -> str:
    key = _LABEL_MAP.get(label.strip().lower())
    if key:
        return key
    words = re.findall(r"[a-zA-Z0-9]+", label)
    if not words:
        return "field"
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def _row_text(cell) -> str:
    for a in cell.find_all("a"):
        href = a.get("href")
        if href and href not in (a.get_text(strip=True) or ""):
            a.replace_with(f"{a.get_text(strip=True)} [{href}]")
    text = cell.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _parse_rup(cell) -> list[dict]:
    """The nested "Rencana Umum Pengadaan" mini-table: Kode RUP / Nama Paket
    / Sumber Dana, one row per funding source line item."""
    out = []
    inner = cell.find("table")
    if not inner:
        return out
    for tr in inner.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) == 3:
            out.append(
                {
                    "kodeRup": cells[0].get_text(strip=True),
                    "namaPaket": cells[1].get_text(strip=True),
                    "sumberDana": cells[2].get_text(strip=True),
                }
            )
    return out


def build_detail_record(kode: str, html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    table = soup.select_one("table.table-bordered")
    if table is None:
        raise UnexpectedShape(
            f"[detail kode={kode}] no table.table-bordered found on the pengumumanlelang page -- "
            "upstream page shape has likely changed"
        )

    fields: dict = {}
    for tr in table.find_all("tr", recursive=False) or table.find("tbody").find_all("tr"):
        ths = tr.find_all("th", recursive=False)
        tds = tr.find_all("td", recursive=False)
        if not ths or len(ths) != len(tds):
            continue
        for th, td in zip(ths, tds):
            label = th.get_text(strip=True)
            if not label:
                continue
            key = _slugify(label)
            if key == "rencanaUmumPengadaan":
                fields[key] = _parse_rup(td)
            elif key == "lokasiPekerjaan":
                fields[key] = [li.get_text(strip=True) for li in td.find_all("li")] or [_row_text(td)]
            else:
                fields[key] = _row_text(td)

    if "kodeTender" not in fields and "namaTender" not in fields:
        raise UnexpectedShape(
            f"[detail kode={kode}] found a table.table-bordered but no 'Kode Tender'/'Nama Tender' "
            f"row inside it -- keys parsed: {list(fields.keys())} -- upstream page shape has likely changed"
        )

    ta_raw = fields.get("tahunAnggaranRaw") or ""
    fields["tahunAnggaran"] = [int(y) for y in YEAR_RE.findall(ta_raw)]

    return {
        "_input": kode,
        "_source": "S1-pengumumanlelang-detail",
        "_scrapedAt": utc_now_iso(),
        "kode": kode,
        **fields,
    }
