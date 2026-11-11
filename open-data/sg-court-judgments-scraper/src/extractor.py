"""Parsing logic -- turns elitigation.sg's server-rendered HTML into
dataset-ready records.

elitigation.sg exposes no JSON API, no JSON-LD and no `__NEXT_DATA__`, so
"raw passthrough" here means the portal's own displayed values, kept
verbatim: the neutral citation exactly as printed (`[2026] SGHC 175`), the
court's own catchword tags, the case number in its own format
(`HC/OC 483/2024`), and the full judgment text unmodified apart from
whitespace normalisation. Nothing is renamed into a different taxonomy or
re-derived.
"""

import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

# The listing links each judgment as /gd/s/<id>, e.g. /gd/s/2026_SGHC_175
JUDGMENT_HREF_RE = re.compile(r"/gd/s/([^/?#\"']+)")
# Decision date is only machine-readable inside the filter link's own
# data attribute: data-searchparam='DecisionDate:"2026-08-28"'
DECISION_DATE_RE = re.compile(r'DecisionDate:"([0-9]{4}-[0-9]{2}-[0-9]{2})"')
# Judgment ids look like <year>_<courtCode>_<number>, e.g. 2026_SGHCA_22
JUDGMENT_ID_RE = re.compile(r"^(\d{4})_([A-Z]+)_(\d+)$")
# Neutral citations as the courts print them: [2026] SGHC 175,
# [2026] SGHC(I) 15, [2026] SGDC 273 ...
CITATION_RE = re.compile(r"^\[\d{4}\]\s*SG[A-Z]*(?:\([A-Z]+\))?\s*\d+$")

def _clean_catchword(value: str | None) -> str | None:
    """Catchwords come in three different bracket styles depending on the
    court and the era (all confirmed live):
      SGHC/SGHC(I): "[Contract - Discharge - Breach]"      (whole line bracketed)
      SGDC:         "[Civil Procedure] - [Enforcement]"    (each segment bracketed)
      1965 SGHC:    "Betting, Gaming and Lotteries - Betting"  (no brackets)
    Stripping the brackets and collapsing whitespace normalises all three
    into the same topic string the listing page shows, without altering the
    court's own wording.
    """
    if not value:
        return None
    cleaned = " ".join(value.replace("[", " ").replace("]", " ").split())
    return cleaned or None


def _catchwords_from(nodes) -> list[str]:
    out: list[str] = []
    for node in nodes:
        cw = _clean_catchword(node.text(separator=" ", strip=True))
        if cw and cw not in out:
            out.append(cw)
    return out


class UnexpectedShape(Exception):
    """Upstream HTML shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _txt(node, default=None):
    if node is None:
        return default
    # NBSP is used throughout the case-number fields ("Claim No\xa0483")
    return node.text(separator=" ", strip=True).replace("\xa0", " ").strip() or default


def extract_search_page(html: str) -> list[dict]:
    """Returns raw judgment summary dicts from one listing page.

    An empty list means the query legitimately matched nothing (or we
    paged past the end). A page with no results container at all is a
    shape change, not a no-match.
    """
    tree = HTMLParser(html)
    if tree.css_first("form#gdlistForm") is None:
        raise UnexpectedShape(
            "form#gdlistForm not found on listing page -- page shape has likely changed."
        )

    rows = []
    for card in tree.css("div.card"):
        link = card.css_first("a.gd-heardertext")
        if link is None:
            continue  # defensive: a non-result card shouldn't sink the page

        href = link.attributes.get("href") or ""
        m = JUDGMENT_HREF_RE.search(href)
        judgment_id = m.group(1) if m else None

        citation = _txt(card.css_first("a.citation-num-link"))
        if citation:
            # The portal prints the citation with a trailing separator
            # pipe ("[2026] SGHC 175 |") purely for layout.
            citation = citation.rstrip("| ").strip()

        date_link = card.css_first("a.decision-date-link")
        decision_date = None
        decision_date_text = _txt(date_link)
        if date_link is not None:
            dm = DECISION_DATE_RE.search(date_link.attributes.get("data-searchparam") or "")
            if dm:
                decision_date = dm.group(1)
        if decision_date_text:
            decision_date_text = (
                decision_date_text.replace("Decision Date:", "").rstrip("| ").strip()
            )

        catchwords = _catchwords_from(card.css("a.gd-cw"))

        year = court_code = None
        if judgment_id:
            im = JUDGMENT_ID_RE.match(judgment_id)
            if im:
                year, court_code = int(im.group(1)), im.group(2)

        rows.append({
            "judgmentId": judgment_id,
            "caseTitle": _txt(link),
            "citation": citation,
            "decisionDate": decision_date,
            "decisionDateText": decision_date_text,
            "caseNumber": _txt(card.css_first("a.case-num-link")),
            "catchwords": catchwords,
            "year": year,
            "courtCode": court_code,
            "judgmentUrl": f"https://www.elitigation.sg/gd/s/{judgment_id}" if judgment_id else None,
        })
    return rows


def extract_judgment(html: str, judgment_id: str) -> dict | None:
    """Full judgment page. Returns None when the page 200'd but carries no
    judgment body -- which is exactly what an unknown/invalid judgment id
    produces (confirmed live: HTTP 200, ~3.7 KB, no #divJudgement)."""
    tree = HTMLParser(html)
    body = tree.css_first("#divJudgement")
    if body is None:
        return None

    full_text = body.text(separator=" ", strip=True).replace("\xa0", " ")
    full_text = re.sub(r"[ \t]{2,}", " ", full_text).strip()
    if not full_text:
        return None

    catchwords = _catchwords_from(body.css(".catchwords"))

    year = court_code = None
    im = JUDGMENT_ID_RE.match(judgment_id)
    if im:
        year, court_code = int(im.group(1)), im.group(2)

    # Shape varies by court. Supreme Court judgments tag the neutral
    # citation `.HN-NeutralCit` and the case number `.CaseNumber`. District
    # and Magistrates' Court judgments have no `.HN-NeutralCit` at all and
    # instead emit TWO `.CaseNumber` nodes -- the citation in one, the real
    # case number in the other. Both are read from what the court actually
    # printed; nothing is synthesised when neither is present.
    citation = _txt(body.css_first(".HN-NeutralCit"))
    case_number = None
    case_number_nodes = [_txt(n) for n in body.css(".CaseNumber")]
    case_number_nodes = [c for c in case_number_nodes if c]
    for value in case_number_nodes:
        if CITATION_RE.match(value):
            citation = citation or value
        elif case_number is None:
            case_number = value

    # `.title` is reused for boilerplate: District Court judgments open with
    # a redaction-instruction template ("Please delete where applicable -")
    # in the same class as the court name. Pick the node that actually names
    # a court rather than blindly taking the first.
    court_name = None
    for node in body.css(".title"):
        value = _txt(node)
        if value and "court" in value.lower():
            court_name = value
            break

    return {
        "judgmentId": judgment_id,
        "citation": citation,
        "courtName": court_name,
        "caseNumber": case_number,
        "coram": _txt(body.css_first(".HN-Coram")),
        "judgeAuthor": _txt(body.css_first(".Judg-Author")),
        "catchwords": catchwords,
        "year": year,
        "courtCode": court_code,
        "fullText": full_text,
        "fullTextLength": len(full_text),
        "judgmentUrl": f"https://www.elitigation.sg/gd/s/{judgment_id}",
    }


def merge_listing_and_judgment(row: dict, detail: dict) -> dict:
    """Detail-page values win, but only where the detail page actually has
    one. The two pages genuinely carry different subsets -- e.g. catchwords
    are tagged elements on the listing but untagged prose on the judgment,
    and District Court judgments omit the neutral citation the listing
    shows. A naive {**row, **detail} silently blanks those fields.
    """
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
