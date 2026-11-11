"""Parsing logic -- turns topjobs.lk HTML responses into dataset-ready
records.

Per .ai/conventions/dataset-envelope.md, this is raw-passthrough of the
site's own structured fields (title, employer, dates, job-ref, job-type
badges, ...) -- topjobs.lk itself is a classic server-rendered JSP app with
no JSON API and no reliable `__NEXT_DATA__`-equivalent, so "raw passthrough"
here means the exact field values the HTML exposes (BeautifulSoup id/class
selectors), not a renamed/normalized shape. A `jsonLd` field carries the
site's own `JobPosting` schema.org block verbatim when present (only some
detail pages have it -- see constants.py).
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.constants import DETAIL_URL, SITE_BASE


class UnexpectedShape(Exception):
    """Upstream HTML shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def wrap_search_item(item: dict, input_value: str) -> dict:
    return wrap(item, input_value, "S1-search-html")


def wrap_detail(item: dict, input_value: str) -> dict:
    return wrap(item, input_value, "S1-detail-html")


# ---------------------------------------------------------------------------
# Job identifier parsing / URL building
# ---------------------------------------------------------------------------

_JC_RE = re.compile(r"[?&]jc=([^&]+)")
_AC_RE = re.compile(r"[?&]ac=([^&]+)")
_EC_RE = re.compile(r"[?&]ec=([^&]+)")


def parse_job_params(value: str) -> tuple[str, str, str]:
    """Accepts a full topjobs.lk `employer/JobAdvertismentServlet?...` detail
    URL (as produced by this actor's own `detailUrl` field, or copy-pasted
    from a browser) and pulls out the jc/ac/ec triple. All three are
    required by the site -- jc alone 302s to an error page (see
    constants.py)."""
    value = value.strip()
    jc = _JC_RE.search(value)
    ac = _AC_RE.search(value)
    ec = _EC_RE.search(value)
    if not (jc and ac and ec):
        raise ValueError(
            f"Could not find jc/ac/ec in {value!r} -- expected a topjobs.lk job "
            "detail URL, e.g. https://topjobs.lk/employer/JobAdvertismentServlet"
            "?rid=0&ac=<code>&jc=<code>&ec=<code>&pg=applicant/vacancybyfunctionalarea.jsp"
            " (copy it from this actor's own `detailUrl` search-result field, or "
            "from a topjobs.lk listing page)."
        )
    return jc.group(1), ac.group(1), ec.group(1)


def build_detail_url(jc: str, ac: str, ec: str, rid: str = "0") -> str:
    return f"{DETAIL_URL}?rid={rid}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"


def is_not_found(final_url: str) -> bool:
    """topjobs.lk 302s an invalid/mismatched jc+ac+ec triple to
    util/errorPage.jsp?errCode=601 rather than returning a 404 -- confirmed
    live. Checked against the *final* URL after redirects."""
    return "errorPage.jsp" in final_url


# ---------------------------------------------------------------------------
# Search / browse results (applicant/vacancybyfunctionalarea.jsp)
# ---------------------------------------------------------------------------

_CREATE_ALERT_RE = re.compile(
    r"createAlert\('(?P<idx>\d+)'\s*,\s*'(?P<ac>[^']*)'\s*,\s*'(?P<jc>[^']*)'\s*,\s*'(?P<ec>[^']*)'"
)
_TOTAL_RE = re.compile(r'class="cl-red"[^>]*>\(([\d,]+)\)\s*Jobs', re.I)


def _parse_row(tr) -> dict | None:
    onclick = tr.get("onclick", "")
    m = _CREATE_ALERT_RE.search(onclick)
    if not m:
        return None  # banner/promo row, not a job listing row
    h2 = tr.find("h2")
    if h2 is None:
        return None  # layout row with no job in it
    position = h2.get_text(strip=True)
    h1 = tr.find("h1")
    employer = h1.get_text(strip=True) if h1 else None
    jc, ac, ec = m.group("jc"), m.group("ac"), m.group("ec")
    if not position or not jc or not ac or not ec:
        raise UnexpectedShape(
            f"Search result row missing required identifiers "
            f"(position={position!r}, jc={jc!r}, ac={ac!r}, ec={ec!r}) -- shape has likely changed."
        )
    tds = tr.find_all("td", recursive=False)
    job_ref_no = tds[1].get_text(strip=True) if len(tds) > 1 else None
    opening_date = tds[4].get_text(strip=True) if len(tds) > 4 else None
    closing_date = tds[5].get_text(strip=True) if len(tds) > 5 else None
    town = tds[6].get_text(strip=True) if len(tds) > 6 else None
    return {
        "jobRefNo": job_ref_no,
        "position": position,
        "employer": employer,
        "town": town,
        "openingDate": opening_date,
        "closingDate": closing_date,
        "jc": jc,
        "ac": ac,
        "ec": ec,
        "detailUrl": build_detail_url(jc, ac, ec, m.group("idx")),
    }


def extract_search_page(html: str) -> tuple[list[dict], int | None]:
    """Returns (job_summaries, total_reported_by_site) for one page (up to
    1000 rows) of applicant/vacancybyfunctionalarea.jsp."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr[onclick^='createAlert']")
    items = [r for r in (_parse_row(tr) for tr in rows) if r is not None]

    m = _TOTAL_RE.search(html)
    total = int(m.group(1).replace(",", "")) if m else None

    if not items and total is None:
        # Could be a legitimate zero-result page (confirmed live: a
        # keyword+checkbox combo with a real empty intersection renders an
        # empty `cate-pg-title` with no count at all) -- only raise if the
        # page doesn't even look like a search-results page anymore.
        if "jb-list" not in html:
            raise UnexpectedShape(
                "Search results page missing the expected `jb-list` container -- shape has likely changed."
            )
        total = 0
    return items, total


# ---------------------------------------------------------------------------
# Job detail (employer/JobAdvertismentServlet)
# ---------------------------------------------------------------------------


def _extract_json_ld(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def extract_detail_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    position_el = soup.find(id="position")
    employer_el = soup.find(id="employer")
    if position_el is None or employer_el is None:
        raise UnexpectedShape("Detail page missing #position/#employer -- shape has likely changed.")

    position = position_el.get_text(strip=True)
    employer = employer_el.get_text(strip=True) or employer_el.get("title")
    if not position or not employer:
        raise UnexpectedShape(
            f"Detail page #position/#employer present but empty (position={position!r}, employer={employer!r})."
        )

    closing_date_el = soup.find(id="endDate")
    job_ref_el = soup.find(id="jobRefNum")
    location_el = soup.find(id="adview-job-location")
    job_type = [lbl.get_text(strip=True) for lbl in soup.select(".lbl_fulltime") if lbl.get_text(strip=True)]

    remark = soup.find(id="remark")
    desc_img = remark.find("img") if remark else None
    description_image_url = urljoin(SITE_BASE, desc_img["src"]) if desc_img and desc_img.get("src") else None

    logo_el = soup.find(id="logo")
    company_logo_url = urljoin(SITE_BASE, logo_el["src"]) if logo_el and logo_el.get("src") else None

    website_el = soup.find(id="url")
    company_website = (website_el.get("href") or None) if website_el else None

    email_el = soup.find(id="txtAVECompanyEmail")
    company_email = (email_el.get("value") or None) if email_el else None

    js_code_el = soup.find(id="jsCode")
    job_spec_code = js_code_el.get("value") if js_code_el else None

    record = {
        "position": position,
        "employer": employer,
        "location": location_el.get_text(" ", strip=True) if location_el else None,
        "jobRefNo": job_ref_el.get_text(strip=True) if job_ref_el else None,
        "closingDate": closing_date_el.get_text(strip=True) if closing_date_el else None,
        "jobType": job_type,
        "descriptionImageUrl": description_image_url,
        "companyLogoUrl": company_logo_url,
        "companyWebsite": company_website,
        "companyEmail": company_email,
        "jobSpecCode": job_spec_code,
    }
    ld = _extract_json_ld(soup)
    if ld is not None:
        record["jsonLd"] = ld
    return record
