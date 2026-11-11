"""Parsing for HonduCompras 1.0's ASP.NET WebForms pages
(`sicc.honducompras.gob.hn/HC/procesos/*.aspx`), plus the raw-passthrough
record builders.

Three page shapes matter here, all plain server-rendered HTML (no JSON, no
client-side JS driving the data):

1. The bare search form (`GET busquedahistorico.aspx`, or any `POST`
   response) -- carries every hidden/select field the postback protocol
   needs. `extract_form_fields` pulls out the COMPLETE current set rather
   than a hand-typed subset (see `constants.py` docstring for why).
2. The results page (`POST` response) -- an `id="...gvResultados"` ASP.NET
   `GridView` `<table>`, one `<tr>` per tender.
3. The tender detail page (`GET ProcesoHistorico.aspx?...`) -- an
   `id="...dvProceso"` label/value `<table>` plus up to four Infragistics
   tabbed data grids (line items, documents, bidders, award).
"""

import re
from datetime import datetime, timezone
from urllib.parse import unquote

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Postback form fields
# ---------------------------------------------------------------------------


def extract_form_fields(page_html: str) -> dict:
    """Pull every hidden `<input>` and every `<select>`'s currently-selected
    `<option>` out of the page's single `<form>`, keyed by `name`. This is
    the COMPLETE field set needed to round-trip a postback -- a hand-typed
    subset is not safe here (Infragistics date-chooser controls carry extra
    hidden calendar-state fields that must be echoed back unchanged, or the
    server throws a 500).

    Raises `UnexpectedShape` if the page has no `<form>` at all (e.g. an
    error page was returned instead of the expected search/results page).
    """
    soup = BeautifulSoup(page_html, "lxml")
    form = soup.find("form")
    if form is None:
        raise UnexpectedShape("no <form> found on page -- likely an error/redirect page")

    fields: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "text").lower()
        if itype in ("checkbox", "radio") and not inp.has_attr("checked"):
            continue
        fields[name] = inp.get("value", "")
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        fields[name] = opt.get("value", "") if opt else ""
    return fields


def resolve_entidad_value(page_html: str, query: str) -> str | None:
    """Case-insensitive substring match of `query` against the institution
    (`ddlEntidades`) dropdown's option text on the search-form page. Returns
    the option's `value` (a numeric ID string), or `None` if nothing matched
    (caller should fall back to "0" / (Todas) and log a warning -- this is
    a usability nicety, not a hard failure)."""
    soup = BeautifulSoup(page_html, "lxml")
    select = soup.find("select", attrs={"name": re.compile(r"ddlEntidades$")})
    if select is None:
        return None
    needle = query.strip().lower()
    if not needle:
        return None
    for opt in select.find_all("option"):
        if needle in opt.get_text(strip=True).lower():
            return opt.get("value")
    return None


# ---------------------------------------------------------------------------
# List (search results) page
# ---------------------------------------------------------------------------


def _resolve_detail_url(href: str) -> str:
    from src.constants import DETAIL_BASE

    return DETAIL_BASE + href


def parse_list_rows(page_html: str) -> list[dict]:
    """Parse a `busquedahistorico.aspx` POST response into one dict per
    tender row. Returns `[]` if the results `<table>` is simply absent (a
    legitimate "this filter matched nothing" outcome -- the GridView is not
    rendered at all when there are zero rows, there is no distinct
    zero-results marker to check instead). Raises `UnexpectedShape` if the
    table IS present but not a single row could be parsed out of it
    (upstream markup changed)."""
    soup = BeautifulSoup(page_html, "lxml")
    table = soup.find(id=lambda x: x and x.endswith("gvResultados"))
    if table is None:
        return []

    rows = []
    for tr in table.find_all("tr", recursive=False):
        first_td = tr.find("td", recursive=False)
        if first_td is None:
            continue
        b_tags = first_td.find_all("b")
        if not b_tags or "expediente" not in b_tags[0].get_text(strip=True).lower():
            continue  # header row or the trailing page-number-links row
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue
        spans0 = tds[0].find_all("span")
        spans3 = tds[3].find_all("span")
        a = tds[4].find("a", href=True)
        rows.append(
            {
                "expediente": spans0[0].get_text(strip=True) if len(spans0) > 0 else None,
                "entidad": spans0[1].get_text(strip=True) if len(spans0) > 1 else None,
                "unidadCompra": spans0[2].get_text(strip=True) if len(spans0) > 2 else None,
                "objetoCompra": spans0[3].get_text(strip=True) if len(spans0) > 3 else None,
                "etapa": tds[1].get_text(strip=True),
                "modalidad": tds[2].get_text(strip=True),
                "fechaInicio": spans3[0].get_text(strip=True) if len(spans3) > 0 else None,
                "fechaCierre": spans3[1].get_text(strip=True) if len(spans3) > 1 else None,
                "detailUrl": _resolve_detail_url(a["href"]) if a else None,
            }
        )
    if not rows:
        raise UnexpectedShape("#...gvResultados present but no data rows parsed out of it")
    return rows


def has_next_page(page_html: str, page_num: int) -> bool:
    """True if a `__doPostBack('...gvResultados','Page$<page_num>')` link
    exists anywhere in the page -- the pager only lists page numbers it
    actually has (plus a '...' and a '>>' last-page link), so this is a
    reliable "is there a page N" check."""
    return f"gvResultados','Page${page_num}'" in page_html


def build_list_record(row: dict, filters: dict) -> dict:
    return {
        "_input": filters,
        "_source": "S1-aspnet-gridview",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


def build_error_record(input_value, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

_TAB_LABEL_RE = re.compile(r"_tmpl(\d+)_wdg(\w+)$")
_SKIP_WIDGET_SUFFIXES = ("_clientState", "_eppool")


def _parse_tab_widgets(soup: BeautifulSoup) -> dict[str, list[dict]]:
    """Parse the (up to four) Infragistics `WebDataGrid` tabs on a detail
    page -- "Productos y/o Servicios Solicitados", "Documentos",
    "Participantes", "Adjudicado a". A tab with no data simply has an empty
    (self-closed) row container, which correctly yields `[]`, not an error."""
    tab_names = [s.get_text(strip=True) for s in soup.select(".igtab_THText")]

    tabs: dict[str, list[dict]] = {}
    for div in soup.find_all(id=re.compile(r"_tmpl\d+_wdg\w+$")):
        div_id = div.get("id", "")
        if div_id.endswith(_SKIP_WIDGET_SUFFIXES):
            continue
        m = _TAB_LABEL_RE.search(div_id)
        if not m:
            continue
        idx, widget_name = int(m.group(1)), m.group(2)
        tab_name = tab_names[idx] if idx < len(tab_names) else widget_name

        headers = [th.get_text(strip=True) for th in div.select("th.igg_HeaderCaption")]
        data_rows = []
        for tr in div.select("tbody.ig_Item tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
            if not cells:
                continue
            if headers and len(cells) == len(headers):
                data_rows.append(dict(zip(headers, cells)))
            else:
                data_rows.append({"value": cells})
        tabs[tab_name] = data_rows
    return tabs


def parse_detail(page_html: str, url: str) -> dict:
    """Parse a `ProcesoHistorico.aspx` detail page. Raises `UnexpectedShape`
    if the `#...dvProceso` label/value table isn't found (upstream markup
    changed, or the page came back as something unexpected)."""
    soup = BeautifulSoup(page_html, "lxml")
    table = soup.find(id=lambda x: x and x.endswith("dvProceso"))
    if table is None:
        raise UnexpectedShape("#...dvProceso details table not found on detail page")

    fields: dict[str, str] = {}
    for tr in table.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != 2:
            continue
        label = tds[0].get_text(strip=True).rstrip(":")
        value = tds[1].get_text(" ", strip=True)
        if label:
            fields[label] = value
    if not fields:
        raise UnexpectedShape("#...dvProceso present but no label/value rows parsed out of it")

    email_a = table.find("a", href=re.compile(r"^mailto:", re.I))
    # Some entries have stray trailing whitespace baked into the source
    # mailto href (observed as literal "%20" padding) -- unquote + strip it.
    contacto_email = unquote(email_a["href"][len("mailto:") :]).strip() if email_a else None

    tabs = _parse_tab_widgets(soup)

    return {
        "url": url,
        **fields,
        "contactoEmail": contacto_email,
        "productos": tabs.get("Productos y/o Servicios Solicitados", []),
        "documentos": tabs.get("Documentos", []),
        "participantes": tabs.get("Participantes", []),
        "adjudicadoA": tabs.get("Adjudicado a", []),
    }


def build_detail_record(url: str, detail: dict) -> dict:
    return {
        "_input": url,
        "_source": "S1-aspnet-detail",
        "_scrapedAt": utc_now_iso(),
        **detail,
    }
