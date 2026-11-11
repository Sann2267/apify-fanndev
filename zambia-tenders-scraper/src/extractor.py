"""Parse ZPPA e-GP HTML into dataset-ready records.

There is no JSON API anywhere in this flow (see CRAWLING_METHOD.md) -- every
record is derived from server-rendered HTML tables/definition-lists. Per
this portfolio's raw-passthrough convention (.ai/conventions/dataset-envelope.md)
field labels are kept as close to the site's own wording as possible: table
column headers and detail-page field labels are turned into camelCase keys
programmatically (not a hardcoded field list), so a label the site adds
later still flows through instead of being silently dropped.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

RESOURCE_ID_RE = re.compile(r"resourceId=(\d+)")
GRID_ID_RE = re.compile(r"d-(\d+)-p=\d+")


class UnexpectedShape(Exception):
    """Raised when a page that returned HTTP 200 doesn't contain the HTML
    structure this actor expects (grid/table markup, dt/dl detail block) --
    signals a site redesign rather than a normal empty-result page. See
    .ai/CLAUDE.md principle #6: fail loud, never emit a silently-empty
    "success" record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _label_to_key(label: str) -> str:
    """'Name of Procuring Entity' -> 'nameOfProcuringEntity'. Strips
    punctuation/non-breaking-spaces, camelCases on whitespace."""
    label = label.replace("\xa0", " ")
    words = re.findall(r"[A-Za-z0-9]+", label)
    if not words:
        return "field"
    first, *rest = words
    return first.lower() + "".join(w[:1].upper() + w[1:].lower() for w in rest)


def _resource_id_from_href(href: str | None) -> str | None:
    if not href:
        return None
    m = RESOURCE_ID_RE.search(href)
    return m.group(1) if m else None


def find_grid_id(html: str) -> str | None:
    """Extracts the dynamic per-session grid widget id (e.g. '3680181' from
    `d-3680181-p=2`) used to build pagination URLs for the Opened Bid
    Details table. Tied to the session's JSESSIONID -- must be re-extracted
    if the client establishes a new session."""
    m = GRID_ID_RE.search(html)
    return m.group(1) if m else None


def parse_opened_tenders_page(html: str) -> list[dict]:
    """Parses one page (10 rows) of the "Opened Bid Details" listing
    (`common/viewOpenedTenders.do`) -- ZPPA's only browsable-without-login,
    paginated tender listing (150k+ historical records). Column headers are
    read live from <thead> rather than hardcoded, so a reordered/renamed
    column still maps correctly."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="T01")
    if table is None or table.thead is None or table.tbody is None:
        raise UnexpectedShape("Opened Bid Details table (table#T01) not found in page")

    headers = [th.get_text(strip=True) for th in table.thead.find_all("th")]
    if not headers:
        raise UnexpectedShape("Opened Bid Details table has no <th> headers")
    keys = [_label_to_key(h) if h != "#" else "position" for h in headers]

    rows = []
    for tr in table.tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != len(keys):
            raise UnexpectedShape(
                f"Row has {len(cells)} cells, expected {len(keys)} (headers={headers})"
            )
        row: dict = {}
        resource_id = None
        opened_bids_url = None
        for key, td in zip(keys, cells):
            a = td.find("a")
            text = td.get_text(strip=True)
            row[key] = text
            if a and a.get("href"):
                href = a["href"]
                rid = _resource_id_from_href(href)
                if rid and key != "openedBids":
                    resource_id = rid
                    row["detailUrl"] = f"https://eprocure.zppa.org.zm{href}"
                elif key == "openedBids":
                    opened_bids_url = f"https://eprocure.zppa.org.zm{href}"
        if resource_id:
            row["resourceId"] = resource_id
        if opened_bids_url:
            row["openedBidsUrl"] = opened_bids_url
        rows.append(row)
    return rows


def parse_latest_widget(html: str) -> list[dict]:
    """Parses the homepage's "Latest Tenders" widget (`home.do`) --
    currently-open (not yet past bid-submission deadline) tenders, freely
    viewable including their detail pages. Small, fixed-size (~10 items),
    no pagination available without hitting the CAPTCHA-gated search form
    (see CRAWLING_METHOD.md known limits)."""
    soup = BeautifulSoup(html, "lxml")
    widget = soup.find("div", class_="LatestTenders")
    if widget is None:
        raise UnexpectedShape("'Latest Tenders' widget (div.LatestTenders) not found on home page")
    ul = widget.find("ul", class_="news")
    if ul is None:
        raise UnexpectedShape("'Latest Tenders' widget has no <ul class=news> list")

    items = []
    for li in ul.find_all("li"):
        a = li.find("a")
        if a is None or not a.get("href"):
            continue
        resource_id = _resource_id_from_href(a["href"])
        date_span = a.find("span", class_="eventDate")
        date_parts = [s.get_text(strip=True) for s in date_span.find_all("span")] if date_span else []
        title = a.get_text(" ", strip=True)
        for part in date_parts:
            title = title.replace(part, "", 1)
        title = re.sub(r"\s+", " ", title).strip()
        items.append(
            {
                "resourceId": resource_id,
                "title": title,
                "publishedDateParts": date_parts,  # e.g. ["26", "Aug", "26"] (day, mon, yy)
                "detailUrl": f"https://eprocure.zppa.org.zm{a['href']}",
            }
        )
    return items


def parse_detail_page(html: str) -> dict:
    """Parses a tender's full detail page (`cft/prepareViewCfTWS.do`).
    Only called on a 200 response -- the login-redirect case (302 to
    /cas/login, for tenders past their bid-submission deadline) is handled
    by the caller before this function runs. Every <dt>/<dd> pair in the
    field list is included dynamically -- field count/labels vary by tender
    type (goods/works/services, national/international, etc.), confirmed
    live (one sample had 27 fields; not all tenders will have the same
    set)."""
    soup = BeautifulSoup(html, "lxml")
    h2 = soup.find("h2", class_="d-flex")
    if h2 is None or h2.find("span") is None:
        raise UnexpectedShape("Tender detail heading (h2.d-flex > span) not found")
    title = h2.find("span").get_text(" ", strip=True)
    title = re.sub(r"^Tender:\s*", "", title).strip()

    dl = soup.find("dl", class_="row")
    if dl is None:
        raise UnexpectedShape("Tender detail field list (dl.row) not found")

    fields: dict = {}
    raw_fields = []
    procuring_entity_url = None
    dts = dl.find_all("dt", recursive=False)
    dds = dl.find_all("dd", recursive=False)
    if not dts or len(dts) != len(dds):
        raise UnexpectedShape(f"Mismatched dt/dd counts: {len(dts)} dt vs {len(dds)} dd")

    for dt, dd in zip(dts, dds):
        label = dt.get_text(strip=True).rstrip(":").strip()
        value = dd.get_text(" ", strip=True)
        key = _label_to_key(label)
        fields[key] = value
        raw_fields.append({"label": label, "value": value})
        a = dd.find("a")
        if a and a.get("href") and "prepareViewCAOrganisation.do" in a["href"]:
            procuring_entity_url = f"https://eprocure.zppa.org.zm{a['href']}"

    result = {
        "title": title,
        "fields": fields,
        "rawFields": raw_fields,
    }
    if procuring_entity_url:
        result["procuringEntityUrl"] = procuring_entity_url
    return result


def build_list_record(query: str, row: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-opened-tenders-html",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_latest_record(query: str, item: dict, detail: dict | None, detail_error: str | None) -> dict:
    record = {
        "_input": query,
        "_source": "S1-latest-widget-html",
        "_scrapedAt": utc_now_iso(),
        **item,
    }
    if detail:
        record["detail"] = detail
    if detail_error:
        record["detailError"] = detail_error
    return record


def build_detail_record(query: str, resource_id: str, detail: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-detail-html",
        "_scrapedAt": utc_now_iso(),
        "resourceId": resource_id,
        **detail,
    }


def build_error(query: str, error_kind: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
