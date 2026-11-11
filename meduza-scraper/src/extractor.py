"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html -- meduza.io emits exactly one ld+json block per page. `/news/`
             and `/short/` pages type it `NewsArticle`; `/feature/` pages
             type it `Article`; `/video/` pages type it `VideoObject`. That
             block carries `headline`, `description`, `image`,
             `author`/`publisher` (both `NewsMediaOrganization`, name
             "Meduza" in every sample -- wire-style attribution, not
             individual bylines), `datePublished`, `dateModified`,
             `inLanguage` -- but **no articleBody**. Full text comes from
             HTML `div.GeneralMaterial-module-article > p` (a stable,
             un-hashed container class; the `<p>` tags themselves carry a
             webpack-hashed class suffix that is NOT relied on -- only the
             tag name is used). This container is populated identically on
             the ru and /en/ editions.

             `/short/` pages render their body text into a lazy-loaded
             `<img alt="...">` placeholder instead of `<p>` tags, and
             `/video/` pages carry no textual body at all -- both degrade
             to a metadata-only record with `_warning:
             "no_body_extracted_non_article_layout"` rather than raising,
             since that is their normal (not broken) shape. A `NewsArticle`
             or `Article` page with an empty body IS treated as broken
             (raises UnexpectedShape) since those two types are always
             supposed to carry a full-text body.

             EN-edition articles that were AI-translated from the Russian
             original append a disclosure notice as three ordinary <p>
             tags inside the same body container ("At Meduza, we are
             committed to transparency about our use of artificial
             intelligence..."). These are stripped out of articleBody by
             substring match -- confirmed present on every EN sample
             checked during recon, absent on every RU sample checked.
  S2-rss  -- `/rss/all` (ru) or `/rss/en/all` (en edition). Standard RSS
             2.0: `title`, `link`, `guid`, `pubDate`, `description` (a
             short teaser, not the full article -- unlike rt-scraper's
             feed, Meduza's `<description>` is HTML-wrapped but still just
             a 1-3 sentence summary; use `article` mode against `link` for
             full text).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import AI_DISCLOSURE_MARKERS, TEXT_LD_TYPES


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_ld_json(soup: BeautifulSoup) -> dict | None:
    """Return the article-like ld+json block, preferring NewsArticle/Article/
    VideoObject over any other @type the page might also emit; falls back to
    the first parseable block if none of those are found."""
    blocks = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            blocks.append(data)
    for b in blocks:
        if b.get("@type") in TEXT_LD_TYPES or b.get("@type") == "VideoObject":
            return b
    return blocks[0] if blocks else None


def _is_boilerplate(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in AI_DISCLOSURE_MARKERS)


def _paragraphs_to_text(container) -> str:
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p and not _is_boilerplate(p)]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    ld = _find_ld_json(soup)
    if ld is None:
        raise UnexpectedShape("No ld+json block found -- page shape has likely changed.")

    container = soup.select_one("div.GeneralMaterial-module-article")
    article_body = _paragraphs_to_text(container) if container is not None else ""

    content_type = ld.get("@type")
    if content_type in TEXT_LD_TYPES and not article_body:
        raise UnexpectedShape(
            f"{content_type} page had no extractable body -- "
            "div.GeneralMaterial-module-article shape has likely changed."
        )

    author = ld.get("author") or {}
    publisher = ld.get("publisher") or {}

    record = {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": ld.get("headline"),
        "description": ld.get("description"),
        "articleBody": article_body or None,
        "author": author.get("name") if isinstance(author, dict) else author,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "datePublished": ld.get("datePublished"),
        "dateModified": ld.get("dateModified"),
        "image": ld.get("image"),
        "inLanguage": ld.get("inLanguage"),
        "contentType": content_type,
    }
    if not article_body:
        record["_warning"] = "no_body_extracted_non_article_layout"
    return record


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        teaser = item.find("description")
        pub_date = item.find("pubDate")

        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "teaser": teaser.text.strip() if teaser and teaser.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
