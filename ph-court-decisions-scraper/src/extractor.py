"""Parsing logic -- turns the E-Library's server-rendered HTML into
dataset-ready records.

elibrary.judiciary.gov.ph exposes no JSON API, no JSON-LD and no
`__NEXT_DATA__`, so "raw passthrough" here means the portal's own displayed
values, kept verbatim: the case number exactly as the Court prints it
("G.R. No. 241587", "A.M. No. P-26-390 [Formerly OCA IPI No. 19-4946-P]"),
the Philippine Reports citation when the decision has been reported
("930 Phil. 215"), the division line ("EN BANC", "FIRST DIVISION"), the
ponente as signed ("LEONEN, SAJ.:", "PER CURIAM:") and the full opinion text
unmodified apart from whitespace normalisation. Nothing is renamed into a
different taxonomy or re-derived.
"""

import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.constants import (
    BASE_URL,
    DTSEARCH_INDEX_ERROR_MARKER,
    MONTH_TO_NUMBER,
    SHOWDOCS_URL,
)

# Listing links each decision as /thebookshelf/showdocs/1/<docId>
SHOWDOCS_HREF_RE = re.compile(r"/thebookshelf/showdocs/\d+/(\d+)")
# dtSearch result links carry their own, unrelated numbering: ...?cmd=getdoc&DocId=69244&...
DTSEARCH_DOCID_RE = re.compile(r"[?&]DocId=(\d+)")
# "August 06, 2025" / "September 21, 2022" -- the only date format either page prints.
LONG_DATE_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})")
# The bracketed header line. The two views separate the case number from the
# date with DIFFERENT punctuation, confirmed live:
#   document page: "[ G.R. No. 279772, June 29, 2026 ]"          (comma)
#   dtSearch hit:  "[ G.R. No. 176317. July 23, 2014 ]"          (period)
#   nested number: "[ A.M. No. P-26-390 [Formerly OCA IPI No. 19-4946-P], June 10, 2026 ]"
# The case part is greedy so the split lands on the LAST separator that is
# actually followed by a date -- case numbers are full of their own periods
# ("G.R. No.") and administrative-matter numbers carry nested commas.
CASE_AND_DATE_RE = re.compile(
    r"^\s*\[?\s*(?P<case>.+)[,.]\s*(?P<date>[A-Za-z]+\s+\d{1,2},\s*\d{4})\s*\]?\s*$"
)
# Philippine Reports citation, printed bare above the caption when the
# decision has been reported: "930 Phil. 215", "322 Phil. 677".
REPORTER_CITATION_RE = re.compile(r"^(\d+\s+Phil\.\s+\d+)")
# Document type is printed letter-spaced: "D E C I S I O N", "R E S O L U T I O N".
DOC_TYPE_RE = re.compile(
    r"((?:D\s*E\s*C\s*I\s*S\s*I\s*O\s*N)|(?:R\s*E\s*S\s*O\s*L\s*U\s*T\s*I\s*O\s*N))\s*$"
)
# Footer the CMS appends inside the content container on every document.
CMS_FOOTER_RE = re.compile(r"\s*Source:\s*Supreme Court E-Library.*$", re.S)
PRINTER_CHROME_RE = re.compile(r"^\s*View printer friendly version\s*")
# dtSearch's document view hyperlinks the reporter citation to the official
# Philippine Reports PDF and appends "← click for PDF copy" next to it.
PDF_CHROME_RE = re.compile(r"\s*(?:←|<-)?\s*click for PDF copy\s*")
PHILREP_PDF_HREF_RE = re.compile(r"""href=["']([^"']*/assets/pdf/philrep/[^"']+)["']""", re.I)
# An unknown document id still answers HTTP 200 -- the body carries this
# instead of a decision. Treating it as a 106-character judgment would be a
# silent corruption, so it is detected explicitly.
SOFT_404_MARKERS = (
    "Document Search Error",
    "Document not available on the database",
)
# "Search returned 5,000 result(s)."
SEARCH_TOTAL_RE = re.compile(r"returned\s+([\d,]+)\s+result")
# "No. of hits: 24"
HIT_COUNT_RE = re.compile(r"(\d+)\s*$")


class UnexpectedShape(Exception):
    """Upstream HTML shape changed in a way we don't recognize."""


class BrokenSearchIndex(Exception):
    """dtSearch answered 200 but could not open the index it was asked for."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _txt(node, default=None):
    if node is None:
        return default
    return node.text(separator=" ", strip=True).replace("\xa0", " ").strip() or default


def _collapse(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.replace("\xa0", " ").split()) or None


def parse_long_date(value: str | None) -> str | None:
    """"August 06, 2025" -> "2025-08-06". Returns None rather than guessing
    when the month word isn't one the portal actually uses."""
    if not value:
        return None
    m = LONG_DATE_RE.search(value)
    if not m:
        return None
    month = MONTH_TO_NUMBER.get(m.group(1).strip().lower())
    if not month:
        return None
    try:
        return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"
    except ValueError:
        return None


def _split_case_and_date(line: str | None) -> tuple[str | None, str | None]:
    """"[ G.R. No. 279772, June 29, 2026 ]" -> ("G.R. No. 279772", "June 29, 2026")"""
    line = _collapse(line)
    if not line:
        return None, None
    m = CASE_AND_DATE_RE.match(line)
    if not m:
        return line.strip("[] ").strip() or None, None
    return _collapse(m.group("case")), _collapse(m.group("date"))


def _split_title_and_doc_type(value: str | None) -> tuple[str | None, str | None]:
    """The caption <h3> often has the document type glued to the party line:
    "...RESPONDENT.D E C I S I O N". Split it back apart, and normalise the
    letter-spaced form to a plain word."""
    value = _collapse(value)
    if not value:
        return None, None
    m = DOC_TYPE_RE.search(value)
    if not m:
        return value, None
    doc_type = re.sub(r"\s+", "", m.group(1)).upper()
    title = _collapse(value[: m.start()])
    return title, doc_type


def _decision_body_text(container) -> str:
    text = container.text(separator=" ", strip=True).replace("\xa0", " ")
    text = PRINTER_CHROME_RE.sub("", text)
    text = PDF_CHROME_RE.sub(" ", text)
    text = CMS_FOOTER_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def is_soft_404(container) -> bool:
    head = container.text(separator=" ", strip=True)[:600]
    return any(marker in head for marker in SOFT_404_MARKERS)


def _parse_decision_container(container, doc_id: str | None, document_url: str) -> dict | None:
    """Shared shape for both document views (the portal's `showdocs` page and
    dtSearch's own document view): a caption block of
    division / [case number, date] / party line, then the ponente in bold,
    then the opinion."""
    full_text = _decision_body_text(container)
    if not full_text:
        return None

    headings = [_collapse(_txt(h)) for h in container.css("h2")]
    headings = [h for h in headings if h]

    division = None
    case_line = None
    for h in headings:
        # The case/date line is the bracketed one; the division is the plain one.
        if "[" in h or LONG_DATE_RE.search(h):
            case_line = case_line or h
        elif division is None:
            division = h
    if case_line is None and headings:
        case_line = headings[-1]

    case_number, decision_date_text = _split_case_and_date(case_line)
    case_title, document_type = _split_title_and_doc_type(_txt(container.css_first("h3")))

    # The reporter citation is printed as bare text before the caption, so it
    # only survives in the container's leading text, not in any element.
    reporter_citation = None
    leading = PRINTER_CHROME_RE.sub("", _collapse(full_text) or "")
    rm = REPORTER_CITATION_RE.match(leading)
    if rm:
        reporter_citation = rm.group(1)

    ponente = _collapse(_txt(container.css_first("strong")))
    if ponente:
        ponente = ponente.rstrip(":").strip() or None

    # dtSearch's document view links the reporter citation to the official
    # Philippine Reports PDF; the portal's own page prints it as bare text.
    reporter_pdf_url = None
    pm = PHILREP_PDF_HREF_RE.search(container.html or "")
    if pm:
        href = pm.group(1)
        reporter_pdf_url = href if href.startswith("http") else f"{BASE_URL}{href}"

    return {
        "docId": doc_id,
        "caseNumber": case_number,
        "caseTitle": case_title,
        "documentType": document_type,
        "division": division,
        "ponente": ponente,
        "reporterCitation": reporter_citation,
        "reporterPdfUrl": reporter_pdf_url,
        "decisionDate": parse_long_date(decision_date_text),
        "decisionDateText": decision_date_text,
        "fullText": full_text,
        "fullTextLength": len(full_text),
        "documentUrl": document_url,
    }


def extract_listing_page(html: str) -> list[dict]:
    """Rows from one `/thebookshelf/docmonth/<Mon>/<Year>/<page>` page.

    An empty list means we paged past the end of that month -- the portal
    prints no next-page links, so that is the only stop signal available. A
    page with no listing container at all is a shape change, not an empty
    month."""
    tree = HTMLParser(html)
    if tree.css_first("div.single_content") is None:
        raise UnexpectedShape(
            "div.single_content not found on listing page -- page shape has likely changed."
        )

    rows = []
    for link in tree.css("a[href*='/thebookshelf/showdocs/']"):
        href = link.attributes.get("href") or ""
        m = SHOWDOCS_HREF_RE.search(href)
        if not m:
            continue
        doc_id = m.group(1)

        case_number = _collapse(_txt(link.css_first("strong")))
        case_title = _collapse(_txt(link.css_first("small")))

        # The date is the anchor's own trailing text, after the <small> party
        # line -- it is not wrapped in any element of its own.
        anchor_text = _collapse(_txt(link)) or ""
        decision_date_text = None
        dm = LONG_DATE_RE.search(anchor_text)
        if dm:
            decision_date_text = _collapse(dm.group(0))

        rows.append({
            "docId": doc_id,
            "caseNumber": case_number,
            "caseTitle": case_title,
            "decisionDate": parse_long_date(decision_date_text),
            "decisionDateText": decision_date_text,
            "documentUrl": f"{SHOWDOCS_URL}/{doc_id}",
        })
    return rows


def extract_decision(html: str, doc_id: str) -> dict | None:
    """Full decision page. Returns None when the page 200'd but carries no
    document body -- which is what an unknown/invalid document id produces
    (confirmed live: HTTP 200 with a "Document Search Error / Document not
    available on the database" body instead of a decision)."""
    tree = HTMLParser(html)
    container = tree.css_first("div.single_content")
    if container is None or is_soft_404(container):
        return None
    return _parse_decision_container(container, doc_id, f"{SHOWDOCS_URL}/{doc_id}")


def extract_dtsearch_document(html: str, document_url: str, doc_id: str | None) -> dict | None:
    """dtSearch's own document view. Same caption layout as the portal page
    but with no `.single_content` wrapper -- the whole body is the document."""
    tree = HTMLParser(html)
    container = tree.body
    if container is None or is_soft_404(container):
        return None
    return _parse_decision_container(container, doc_id, document_url)


def extract_search_page(html: str) -> dict:
    """One dtSearch result page.

    Returns {"total": int|None, "rows": [...]}. Raises BrokenSearchIndex when
    dtSearch reports it cannot open the requested index -- three of the
    corpora the judiciary lists are broken server-side, and that must not be
    reported as "no matches"."""
    tree = HTMLParser(html)
    body_text = _collapse(_txt(tree.body)) or ""

    if DTSEARCH_INDEX_ERROR_MARKER in body_text:
        raise BrokenSearchIndex(body_text[:300])

    total = None
    tm = SEARCH_TOTAL_RE.search(body_text)
    if tm:
        try:
            total = int(tm.group(1).replace(",", ""))
        except ValueError:
            total = None
    elif "Search Results" not in body_text:
        raise UnexpectedShape(
            "dtSearch response carried neither a result count nor a 'Search Results' "
            "heading -- engine output shape has likely changed."
        )

    rows = []
    for link in tree.css("a[href*='getdoc']"):
        href = (link.attributes.get("href") or "").replace("&amp;", "&")
        # dtSearch prints its own links as http://; the host resets plain-HTTP
        # connections, so they are only usable over https.
        if href.startswith("http://"):
            href = "https://" + href[len("http://"):]

        snippet_node = link.css_first("p.synopsis_hits")
        hits_node = link.css_first("p.number_of_hits")

        # The caption is the anchor's own text, before the snippet paragraphs.
        caption = _collapse(_txt(link)) or ""
        for child_text in (_txt(snippet_node), _txt(hits_node)):
            if child_text:
                caption = caption.replace(_collapse(child_text) or "", "")
        caption = _collapse(caption)

        case_number, decision_date_text = _split_case_and_date(caption)

        hit_count = None
        hits_text = _collapse(_txt(hits_node)) or ""
        hm = HIT_COUNT_RE.search(hits_text)
        if hm:
            try:
                hit_count = int(hm.group(1))
            except ValueError:
                hit_count = None

        did = DTSEARCH_DOCID_RE.search(href)

        rows.append({
            "dtSearchDocId": did.group(1) if did else None,
            "caseNumber": case_number,
            "decisionDate": parse_long_date(decision_date_text),
            "decisionDateText": decision_date_text,
            "snippet": _collapse(_txt(snippet_node)),
            "hitCount": hit_count,
            "documentUrl": href,
        })

    return {"total": total, "rows": rows}


def extract_next_page_form(html: str) -> dict | None:
    """dtSearch paginates by re-POSTing its own hidden `NextPageForm`, which
    carries the engine-resolved index token and the next `startAt`. Reading
    the server's own form is safer than rebuilding those params by hand."""
    m = re.search(r"<form[^>]*NextPageForm[^>]*>([\s\S]*?)</form>", html, re.I)
    if not m:
        return None
    fields = dict(
        re.findall(
            r"""<input[^>]*name=["']([^"']+)["'][^>]*value=["']([^"']*)["']""",
            m.group(1),
            re.I,
        )
    )
    return fields or None


def merge_listing_and_decision(row: dict, detail: dict) -> dict:
    """Detail-page values win, but only where the detail page actually has
    one. The two views carry genuinely different subsets -- the listing has a
    clean party line while the document page glues the document type onto it,
    and only the document page has the reporter citation. A naive
    {**row, **detail} silently blanks the fields the other side owns."""
    merged = dict(row)
    for key, value in detail.items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
    return merged


def wrap(item: dict, input_value: str, source: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
