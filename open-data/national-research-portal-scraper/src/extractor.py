"""Per-portal parsers and record shaping.

One output schema covers three very different sources, so every parser maps
onto the same vocabulary: ``title``, ``authors``, ``source`` (the journal or
proceedings), ``year``, ``url``. Portal-specific extras stay under ``_raw``
rather than being forced into shared fields.

Garuda's markup has one quirk worth naming: text sits inside ``<xmp>``
elements, a deprecated tag whose content is treated as literal text. It is what
lets the portal print titles containing raw HTML without escaping them, and it
means a naive ``.text()`` on the parent concatenates several values -- so each
``<xmp>`` is read individually.
"""

import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.constants import GARUDA_BASE, KCI_ARTICLE, PORTAL_NAMES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(text) -> str | None:
    if text is None:
        return None
    value = re.sub(r"\s+", " ", str(text)).strip()
    return value or None


def to_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = re.sub(r"[^\d]", "", str(value))
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def year_from(text):
    """Pull a 4-digit year out of a citation string like
    'Vol. 1 No. 2 (2024): June-September 2024'."""
    for m in re.finditer(r"(19|20)\d{2}", str(text or "")):
        return int(m.group(0))
    return None


def _envelope(input_value: str, portal: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": f"S1-{portal}",
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        "portal": portal,
        "portalName": PORTAL_NAMES.get(portal, portal),
    }


# --- Garuda ---------------------------------------------------------------

def garuda_total(html: str, kind: str):
    if kind == "documents":
        m = re.search(r"Found\s+([\d,]+)\s+documents", html)
    elif kind == "authors":
        m = re.search(r":\s*([\d,]+)\s+Authors", html)
    else:
        m = re.search(r"Found\s+([\d,]+)", html)
    return to_int(m.group(1)) if m else None


def parse_garuda_documents(query: str, html: str) -> list[dict]:
    tree = HTMLParser(html)
    out = []
    for item in tree.css("div.article-item"):
        title_link = item.css_first("a.title-article")
        if not title_link:
            continue
        href = title_link.attributes.get("href") or ""
        authors = []
        for a in item.css("a.author-article"):
            name = clean(a.text())
            if name:
                authors.append({"name": name, "authorId": (a.attributes.get("href") or "").rsplit("/", 1)[-1] or None})

        subtitles = [clean(x.text()) for x in item.css("xmp.subtitle-article") if clean(x.text())]
        citation = subtitles[0] if subtitles else None
        publisher = subtitles[1] if len(subtitles) > 1 else None

        links = {}
        for a in item.css("a.title-citation"):
            label = clean(a.text()) or ""
            url = a.attributes.get("href") or ""
            if url.startswith("http"):
                if "Download" in label:
                    links["downloadUrl"] = url
                elif "Original Source" in label:
                    links["sourceUrl"] = url

        record = _envelope(query, "garuda", "ARTICLE")
        record.update(
            {
                "title": clean(title_link.text()),
                "url": f"{GARUDA_BASE}{href}" if href else None,
                "documentId": href.rsplit("/", 1)[-1] if href else None,
                "authors": authors,
                "authorNames": "; ".join(a["name"] for a in authors) or None,
                "source": citation,
                "publisher": publisher,
                "year": year_from(citation),
                **links,
                "_raw": {"citation": citation, "publisher": publisher},
            }
        )
        out.append(record)
    return out


def parse_garuda_journals(query: str, html: str) -> list[dict]:
    tree = HTMLParser(html)
    out = []
    for row in tree.css("tr"):
        link = row.css_first("a.title-journal")
        if not link:
            continue
        href = link.attributes.get("href") or ""
        subtitle_nodes = row.css("a.subtitle-journal")
        publisher = clean(subtitle_nodes[0].text()) if subtitle_nodes else None

        text = clean(row.text()) or ""
        issn = re.search(r"ISSN\s*:\s*([0-9Xx-]{4,12})", text)
        eissn = re.search(r"EISSN\s*:\s*([0-9Xx-]{4,12})", text)
        img = row.css_first("img")

        record = _envelope(query, "garuda", "JOURNAL")
        record.update(
            {
                "title": clean(link.text()),
                "url": f"{GARUDA_BASE}{href}" if href else None,
                "journalId": href.rsplit("/", 1)[-1] if href else None,
                "publisher": publisher,
                "issn": issn.group(1) if issn and issn.group(1) != "-" else None,
                "eissn": eissn.group(1) if eissn and eissn.group(1) != "-" else None,
                "coverImageUrl": f"{GARUDA_BASE}{img.attributes.get('src')}" if img and img.attributes.get("src") else None,
                "_raw": {"rowText": text[:500]},
            }
        )
        out.append(record)
    return out


def parse_garuda_authors(query: str, html: str) -> list[dict]:
    tree = HTMLParser(html)
    out = []
    for row in tree.css("tr"):
        link = row.css_first("a.title-author")
        if not link:
            continue
        href = link.attributes.get("href") or ""
        subtitle = row.css_first("div.subtitle-author")
        subtitle_text = clean(subtitle.text()) if subtitle else None
        docs = re.search(r"([\d,]+)\s+Docs", clean(row.text()) or "")

        record = _envelope(query, "garuda", "AUTHOR")
        record.update(
            {
                "name": clean(link.text()),
                "url": f"{GARUDA_BASE}{href}" if href else None,
                "authorId": href.rsplit("/", 1)[-1] if href else None,
                "affiliation": subtitle_text,
                "documentCount": to_int(docs.group(1)) if docs else None,
                "_raw": {"subtitle": subtitle_text},
            }
        )
        out.append(record)
    return out


# --- CiNii ----------------------------------------------------------------

def parse_cinii(query: str, payload: dict) -> tuple[list[dict], int | None]:
    items = payload.get("items") or []
    total = to_int(payload.get("opensearch:totalResults"))
    out = []
    for item in items:
        creators = item.get("dc:creator") or []
        if isinstance(creators, str):
            creators = [creators]
        publication = item.get("prism:publicationName") or item.get("dc:publisher")
        if isinstance(publication, list):
            publication = publication[0] if publication else None
        date = item.get("prism:publicationDate") or item.get("dc:date")

        record = _envelope(query, "cinii", "ARTICLE")
        record.update(
            {
                "title": clean(item.get("title")),
                "url": clean(item.get("@id") or (item.get("link") or {}).get("@id")),
                "documentId": (clean(item.get("@id")) or "").rsplit("/", 1)[-1] or None,
                "authors": [{"name": clean(c), "authorId": None} for c in creators if clean(c)],
                "authorNames": "; ".join(clean(c) for c in creators if clean(c)) or None,
                "source": clean(publication),
                "publisher": clean(item.get("dc:publisher")) if not isinstance(item.get("dc:publisher"), list) else clean((item.get("dc:publisher") or [None])[0]),
                "year": year_from(date) or year_from(item.get("dc:date")),
                "publicationDate": clean(date),
                "doi": clean(item.get("prism:doi")),
                "description": clean(item.get("description")),
                "dataUrl": clean((item.get("rdfs:seeAlso") or {}).get("@id")),
                "_raw": item,
            }
        )
        out.append(record)
    return out, total


# --- KCI ------------------------------------------------------------------

_ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
# Volume may be absent: "32(4)" and a bare "(53)" both occur.
_KCI_VOL_RE = re.compile(r"(\d+)?\s*\((\d+)\)")
# Row prefix: sequence number plus the indexing tier ("KCI 등재", "KCI 등재후보", ...).
_KCI_PREFIX_RE = re.compile(r"^\s*\d+\s*\.\s*(KCI\s*\S+)?\s*")
_KCI_PAGES_RE = re.compile(r"pp\.\s*([\d]+\s*~\s*[\d]+)")
_KCI_DATE_RE = re.compile(r"(\d{4})\.(\d{2})")
_KCI_CITED_RE = re.compile(r"피인용 횟수\s*:\s*(\d+)")  # "cited count : N"


def parse_kci_row(row_text: str, title: str | None) -> dict:
    """Pull structured fields out of a KCI result row.

    A row is one run-on string: index number, indexing status, title, each
    author followed by their ORCID, the publishing society, the journal,
    volume(issue), page range, YYYY.MM, subject area and the citation count.
    ORCIDs are the only unambiguous delimiter in it -- they separate the author
    block from the journal block -- so they anchor the parse. Everything stays
    available in _raw, because a run-on string is exactly the kind of upstream
    format that changes without warning.
    """
    text = clean(row_text) or ""
    if title:
        text = text.replace(title, " ", 1)
    prefix = _KCI_PREFIX_RE.match(text)
    index_tier = clean(prefix.group(1)) if prefix and prefix.group(1) else None
    text = _KCI_PREFIX_RE.sub("", text)

    authors = []
    for m in _ORCID_RE.finditer(text):
        before = text[: m.start()]
        # The author's name is the trailing words before their ORCID, after the
        # previous ORCID (if any).
        prev = list(_ORCID_RE.finditer(before))
        start = prev[-1].end() if prev else 0
        name = clean(before[start:])
        if name:
            authors.append({"name": name, "authorId": m.group(1)})

    last_orcid = list(_ORCID_RE.finditer(text))
    tail = text[last_orcid[-1].end():] if last_orcid else text

    vol = _KCI_VOL_RE.search(tail)
    pages = _KCI_PAGES_RE.search(tail)
    date = _KCI_DATE_RE.search(tail)
    cited = _KCI_CITED_RE.search(text)

    journal_part = tail[: vol.start()] if vol else tail
    journal_part = clean(re.sub(r"^외\s*\d+명", "", clean(journal_part) or ""))  # drop "and N others"
    society = None
    society_match = re.match(r"(\([^)]*\)\S*)", journal_part or "")
    if society_match:
        society = clean(society_match.group(1))
        journal_part = clean((journal_part or "")[society_match.end():])

    return {
        "authors": authors,
        "authorNames": "; ".join(a["name"] for a in authors) or None,
        "source": journal_part or None,
        "publisher": society,
        "volume": vol.group(1) if vol else None,
        "issue": vol.group(2) if vol else None,
        "pages": clean(pages.group(1)) if pages else None,
        "publicationDate": f"{date.group(1)}-{date.group(2)}" if date else None,
        "year": int(date.group(1)) if date else None,
        "citationCount": to_int(cited.group(1)) if cited else None,
        "indexTier": index_tier,
    }


def parse_kci(query: str, html: str) -> tuple[list[dict], int | None]:
    # Script blocks carry the same article links as the list, so they are cut
    # out first -- otherwise every row is duplicated by its own JS handler.
    body = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    tree = HTMLParser(body)
    total = None
    m = re.search(r"([\d,]{2,})\s*(?:건|results)", body)
    if m:
        total = to_int(m.group(1))

    out = []
    seen = set()
    for link in tree.css('a[href*="ciSereArtiView.kci"]'):
        href = link.attributes.get("href") or ""
        arti_id = re.search(r"artiId=([A-Za-z0-9]+)", href)
        arti_id = arti_id.group(1) if arti_id else None
        title = clean(link.text())
        if not arti_id or not title or arti_id in seen:
            continue
        seen.add(arti_id)

        # The row carrying the link holds the author/journal/year text.
        row = link.parent
        for _ in range(4):
            if row is not None and row.tag == "tr":
                break
            row = row.parent if row is not None else None
        row_text = clean(row.text()) if row is not None else None

        parsed = parse_kci_row(row_text or "", title)
        record = _envelope(query, "kci", "ARTICLE")
        record.update(
            {
                "title": title,
                "url": KCI_ARTICLE.format(arti_id=arti_id),
                "documentId": arti_id,
                **parsed,
                "_raw": {"rowText": row_text},
            }
        )
        out.append(record)
    return out, total


# --- shared ---------------------------------------------------------------

def wrap_source(portal: str, url: str, ok: bool, detail: str, sample: dict | None = None) -> dict:
    record = _envelope("reference", portal, "SOURCE")
    record.update(
        {
            "url": url,
            "isAvailable": ok,
            "detail": detail,
            "sample": sample or {},
        }
    )
    return record


def extract_error(input_value: str, portal: str, error_kind: str, detail: str = "") -> dict:
    record = _envelope(input_value, portal, "ERROR")
    record.update({"_error": error_kind, "_errorDetail": detail})
    return record
