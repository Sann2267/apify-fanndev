"""Parsing logic.

Two independent extraction strategies (see CRAWLING_METHOD.md for full
recon rationale):

- **Search** (`extract_search_page`): SSR HTML, CSS selectors over
  `div.job-item-search-result` cards -- topcv.vn has no public JSON API
  behind its search UI, so this is the highest tier actually available for
  listing results (S1-html).
- **Detail** (`extract_detail_jsonld`): the individual job page's own
  public schema.org `JobPosting` JSON-LD block, passed through close to
  verbatim (S1-jsonld) -- the highest-priority tier in this portfolio, and
  no auth/session of any kind is needed to see it.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import CITY_IDS, CITY_NAMES, SITE_BASE


class UnexpectedShape(Exception):
    """Upstream HTML/JSON-LD shape changed in a way we don't recognize."""


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


# ---------------------------------------------------------------------------
# Vietnamese slugify + city resolution -- see constants.py docstring for how
# the URL scheme (/tim-viec-lam-{slug}[-tai-{citySlug}-kl{id}]) was
# reverse-engineered live.
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def resolve_city(city: str) -> tuple[str, int]:
    """Accepts a city slug (e.g. "ha-noi"), a bare numeric ID (e.g. "1"),
    or a free-text Vietnamese/English name (e.g. "Hà Nội", "Ho Chi Minh")
    and returns (slug, id). Raises ValueError if it can't be resolved
    against topcv.vn's own city list (see constants.CITY_IDS)."""
    raw = city.strip()
    if raw.isdigit():
        cid = int(raw)
        for slug, i in CITY_IDS.items():
            if i == cid:
                return slug, cid
        raise ValueError(f"Unknown city id: {raw!r}")
    slug = slugify(raw)
    if slug in CITY_IDS:
        return slug, CITY_IDS[slug]
    raise ValueError(
        f"Could not resolve city {city!r} (tried slug {slug!r}) against topcv.vn's known city list."
    )


def build_search_url(keyword: str | None, city: tuple[str, int] | None, page: int) -> str:
    keyword_slug = slugify(keyword) if keyword else None
    if keyword_slug and city:
        city_slug, city_id = city
        path = f"/tim-viec-lam-{keyword_slug}-tai-{city_slug}-kl{city_id}"
    elif keyword_slug:
        path = f"/tim-viec-lam-{keyword_slug}"
    elif city:
        city_slug, city_id = city
        path = f"/tim-viec-lam-moi-nhat-tai-{city_slug}-l{city_id}"
    else:
        path = "/tim-viec-lam-moi-nhat"
    url = f"{SITE_BASE}{path}"
    return f"{url}?page={page}" if page > 1 else url


# ---------------------------------------------------------------------------
# Search results (SSR HTML)
# ---------------------------------------------------------------------------

_JOB_URL_ID_RE = re.compile(r"/viec-lam/[^/]+/(\d+)\.html")


def parse_job_id_from_url(url: str) -> str | None:
    m = _JOB_URL_ID_RE.search(url)
    return m.group(1) if m else None


def _text(el) -> str | None:
    if el is None:
        return None
    t = el.get_text(strip=True)
    return t or None


def extract_search_page(html: str) -> tuple[list[dict], int, int]:
    """Returns (job_summaries, current_page, total_pages) for one page of
    a `/tim-viec-lam-*` search results page."""
    soup = BeautifulSoup(html, "lxml")

    cards = soup.select("div.job-item-search-result[data-job-id]")
    if not cards:
        # Distinguish "genuinely zero results for this search" (heading
        # present, says 0) from "page shape changed" (heading itself
        # missing -- that's the real UnexpectedShape signal).
        heading = soup.select_one("#search-job-heading")
        if heading is None:
            raise UnexpectedShape("Search page missing #search-job-heading -- page shape has likely changed.")
        return [], 1, 1

    items = []
    for card in cards:
        job_id = card.get("data-job-id")
        title_a = card.select_one("h3.title a")
        title = _text(title_a.select_one("span")) if title_a else None
        url = title_a.get("href", "").split("?")[0] if title_a else None
        if not job_id or not title or not url:
            raise UnexpectedShape(f"Search card missing job_id/title/url (job_id={job_id!r}) -- page shape has likely changed.")

        company_a = card.select_one("a.company")
        company_name = _text(company_a.select_one(".company-name")) if company_a else None
        company_url = company_a.get("href") if company_a else None

        salary_text = _text(card.select_one("label.title-salary")) or _text(card.select_one(".info label.salary"))
        city_text = _text(card.select_one(".info a.address .city-text"))
        experience_text = _text(card.select_one("label.exp"))

        tag_primary_a = card.select_one("div.tag a.item-tag")
        tag_primary = _text(tag_primary_a)
        remaining_tags_el = card.select_one("div.tag span.remaining-items")
        remaining_tags_raw = remaining_tags_el.get("title") if remaining_tags_el else None
        tags = [t.strip() for t in remaining_tags_raw.split(",")] if remaining_tags_raw else []
        if tag_primary:
            tags = [tag_primary] + tags

        posted_label = card.select_one("label.address.label-update")
        posted_text = _text(posted_label)
        posted_updated_text = posted_label.get("title") if posted_label else None

        avatar_img = card.select_one(".avatar img")
        company_logo_url = avatar_img.get("data-src") or avatar_img.get("src") if avatar_img else None

        is_verified_employer = card.select_one(".icon-verified-employer") is not None

        items.append({
            "job_id": job_id,
            "title": title,
            "url": url,
            "company_name": company_name,
            "company_url": company_url,
            "company_logo_url": company_logo_url,
            "salary_text": salary_text,
            "city": city_text,
            "experience_text": experience_text,
            "tags": tags,
            "posted_text": posted_text,
            "posted_updated_text": posted_updated_text,
            "is_verified_employer": is_verified_employer,
        })

    current_page, total_pages = 1, 1
    paginate_text = soup.select_one("#job-listing-paginate-text")
    if paginate_text:
        m = re.search(r"(\d+)\D+(\d+)", paginate_text.get_text(" ", strip=True))
        if m:
            current_page, total_pages = int(m.group(1)), int(m.group(2))

    return items, current_page, total_pages


def wrap_search_item(item: dict, input_value: str) -> dict:
    return wrap(item, input_value, "S1-html-search")


# ---------------------------------------------------------------------------
# Detail (JSON-LD JobPosting)
# ---------------------------------------------------------------------------

def is_not_found_url(final_url: str) -> bool:
    """topcv.vn redirects an invalid/expired job ID to the bare
    /viec-lam listing root (still HTTP 200) rather than a real 404 --
    confirmed live. Any real job detail page's resolved URL always keeps
    a /viec-lam/<slug>/<id>.html path."""
    return final_url.rstrip("/") == SITE_BASE + "/viec-lam"


def extract_detail_jsonld(html: str) -> dict | None:
    """Returns the raw JobPosting JSON-LD object, or None if the page
    doesn't carry one (treated as not-found by the caller)."""
    soup = BeautifulSoup(html, "lxml")
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def wrap_detail(data: dict, input_value: str) -> dict:
    return wrap(data, input_value, "S1-jsonld")
