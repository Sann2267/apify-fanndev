"""HTML parsing + record shaping.

Two parsers:

* `parse_cards` -- one listing page -> one record per lawyer card. Anchored
  on the schema.org `LocalBusiness` microdata each card carries
  (`itemprop=name` / `address` / `addressLocality`), with the numeric bits
  (rating, rating count, years of experience) read out of the card's own
  text because upstream does not mark them up.
* `parse_profile` -- one `/advocate-<slug>` page -> the full profile.

Both are written to degrade field-by-field: a missing block yields a null
field, never an exception, so one layout tweak upstream cannot empty a
whole run.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE_URL, PROFILE_PREFIX

_WS = re.compile(r"\s+")
_RATING = re.compile(r"([0-9](?:\.[0-9])?)\s*\|")
_RATING_COUNT = re.compile(r"\|\s*([0-9,]+)\s*\+?\s*user ratings", re.I)
_EXPERIENCE = re.compile(r"([0-9]{1,2})\s*years?\s*Experience", re.I)
_ENROLLED = re.compile(
    r"enrolled with the ([A-Za-z ,&']+?) in ((?:19|20)[0-9]{2})", re.I
)
_ANSWERS = re.compile(r"\(([0-9,]+)\s*\+?\s*answers?\)", re.I)


def _txt(node) -> str:
    return _WS.sub(" ", node.get_text(" ", strip=True)).strip() if node else ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug_from_input(raw: str) -> str:
    """Accepts a full URL, a `/advocate-x` path, or a bare slug and returns
    the `advocate-...` path segment."""
    s = (raw or "").strip().split("?")[0].split("#")[0].rstrip("/")
    s = re.sub(r"^https?://(?:www\.)?lawrato\.com", "", s, flags=re.I)
    s = s.lstrip("/")
    if not s:
        return ""
    return s if s.startswith("advocate-") else f"advocate-{s}"


def _int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select("div.lawyer-item"):
        link = card.select_one(f'a[href*="{PROFILE_PREFIX}"]')
        href = link.get("href") if link else None
        if href and href.startswith("/"):
            href = f"{BASE_URL}{href}"
        text = _txt(card)
        name = _txt(card.select_one("[itemprop=name]")) or (link.get("title") if link else "")
        rating = _RATING.search(text)
        count = _RATING_COUNT.search(text)
        exp = _EXPERIENCE.search(text)
        locality = _txt(card.select_one("[itemprop=addressLocality]")) or _txt(
            card.select_one("[itemprop=address]")
        )
        img = card.select_one("img.media-object")
        out.append(
            {
                "name": name.strip(", ") if name else None,
                "profileUrl": href,
                "slug": href.rsplit("/", 1)[-1] if href else None,
                "rating": float(rating.group(1)) if rating else None,
                "ratingCount": _int(count.group(1)) if count else None,
                "ratingCountIsMinimum": bool(count and "+" in text[count.start(): count.end()]),
                "experienceYears": _int(exp.group(1)) if exp else None,
                "locality": locality.strip(", ") or None,
                "imageUrl": img.get("src") if img else None,
                "cardText": text or None,
            }
        )
    return out


def _section_items(soup, heading: str) -> list[str]:
    """Return the items under an `<h2>` whose text starts with `heading`.

    Upstream renders these two sections with *different* markup, and both
    live inside `.panel1` containers:

        <h2>Courts</h2>          -> <ul class="list-inline list-court panel1"><li>..
        <h2>Specialization</h2>  -> <div class="panel1">a<br/>b<br/>c</div>

    A naive `find_next("ul")` therefore returns the Courts list for BOTH
    headings (the Specialization div has no <ul> of its own, so the search
    runs on into the next section) -- which silently duplicated Courts into
    `specializations`. Matching the first following `ul` **or** `.panel1`
    div, whichever comes first, keeps the two apart.
    """
    for h in soup.select("h2"):
        if not _txt(h).lower().startswith(heading.lower()):
            continue
        node = h.find_next(
            lambda t: t.name == "ul" or (t.name == "div" and "panel1" in (t.get("class") or []))
        )
        if node is None:
            continue
        if node.name == "ul":
            items = [_txt(li) for li in node.select("li")]
        else:
            items = [line.strip() for line in node.get_text("\n").split("\n")]
        items = [i for i in items if i]
        if items:
            return items
    return []


def parse_profile(html: str, profile_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    text = _WS.sub(" ", soup.get_text(" ", strip=True))

    name = _txt(soup.select_one("div.name h2")) or _txt(soup.select_one("h1"))
    rating_node = soup.select_one("div.rating")
    rating_text = _txt(rating_node)
    rating = _RATING.search(rating_text)
    count = _RATING_COUNT.search(rating_text)

    # City comes from the breadcrumb ("Lawyers in Faridabad"), which is the
    # only place it appears as a clean value rather than inside prose.
    city = None
    for a in soup.select('a[href*="/lawyers/"]'):
        label = _txt(a)
        if label.lower().startswith("lawyers in "):
            city = label[len("Lawyers in "):].strip()
            break

    languages = None
    for node in soup.select("div.mobile-info div, div"):
        t = _txt(node)
        if t.lower().startswith("language(s) spoken:"):
            languages = [x.strip() for x in t.split(":", 1)[1].split(",") if x.strip()]
            break

    practice_areas = []
    for h in soup.select("h2"):
        if _txt(h).lower().startswith("practice areas"):
            block = h.find_parent("div") or h.parent
            for span in block.select("span"):
                label = _txt(span)
                if label and len(label) < 200:
                    practice_areas.append(label)
            break

    enrolled = _ENROLLED.search(text)
    answers = _ANSWERS.search(text)
    exp = _EXPERIENCE.search(text)
    img = soup.select_one("div.lawyer-detail img, img.img-responsive")

    return {
        "name": name or None,
        "profileUrl": profile_url,
        "slug": profile_url.rsplit("/", 1)[-1],
        "isVerified": bool(soup.select_one("div.verified")),
        "rating": float(rating.group(1)) if rating else None,
        "ratingCount": _int(count.group(1)) if count else None,
        "city": city,
        "experienceYears": _int(exp.group(1)) if exp else None,
        "languages": languages,
        "practiceAreas": practice_areas or None,
        "specializations": _section_items(soup, "Specialization") or None,
        "courts": _section_items(soup, "Courts") or None,
        "barCouncil": enrolled.group(1).strip() if enrolled else None,
        "enrolledYear": _int(enrolled.group(2)) if enrolled else None,
        "answeredQuestions": _int(answers.group(1)) if answers else None,
        "imageUrl": img.get("src") if img else None,
    }


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
