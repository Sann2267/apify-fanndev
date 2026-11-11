"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- qazinform.com (Kazinform's English edition) emits a
             `NewsArticle` ld+json block plus a `BreadcrumbList` block --
             the extractor scans all ld+json blocks and picks the one
             whose `@type` is `NewsArticle`. That block carries
             `headline`, `description`, `image`, `publisher`
             (Organization, name literally "«Inform»" -- the agency's
             legacy Russian legal name, kept as raw passthrough),
             `datePublished`, `dateModified` -- but **no `articleBody`
             and no `author`**. Full text comes from HTML
             `div.article__body-text > p` and the byline from
             `a.article__author-name` (a `div.article__author-position`
             sits alongside it but was observed carrying untranslated
             Russian text -- e.g. "Автор" -- on every sample; kept
             as-is, raw passthrough, not translated).
  S2-feed  -- `/feed.xml`, a ROR-format sitemap/RSS hybrid whose
             `<content:encoded>` carries the full article HTML
             (header/h1, `div.info` with a Russian-language relative
             timestamp and the author name, a lead figure/caption, the
             body paragraphs, and a trailing `<ul class="tags">`).
             Unlike the live article page, this feed's body **also
             includes the lede sentence** (matching the item
             `<description>`), wrapped in a malformed
             `<p><strong><p>...</p></strong></p>` fragment that lxml's
             auto-repair turns into two adjacent, textually-identical
             `<p>` tags. `_paragraphs_to_text()` drops immediately-
             repeated paragraph text to undo that duplication without
             dropping any real content.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def _paragraphs_to_text(container) -> str:
    """Join <p> text, dropping any paragraph identical to the one right
    before it -- undoes the malformed-nested-<p> duplication described
    in the module docstring (S2-feed content:encoded only; harmless
    no-op everywhere else)."""
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    deduped = []
    for p in paragraphs:
        if deduped and deduped[-1] == p:
            continue
        deduped.append(p)
    return "\n\n".join(deduped)


def _images_from_ld(news_article: dict) -> list[str]:
    image = news_article.get("image")
    if isinstance(image, dict):
        image = [image]
    elif not isinstance(image, list):
        image = []
    return [img.get("url") for img in image if isinstance(img, dict) and img.get("url")]


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.article__body-text")
    if body_el is None:
        raise UnexpectedShape("No div.article__body-text element found -- page shape has likely changed.")
    article_body = _paragraphs_to_text(body_el)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    publisher = news_article.get("publisher") or {}
    author_el = soup.select_one("a.article__author-name")
    position_el = soup.select_one("div.article__author-position")

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": _clean_text(author_el.get_text(" ", strip=True)) if author_el else None,
        "authorPosition": _clean_text(position_el.get_text(" ", strip=True)) if position_el else None,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "images": _images_from_ld(news_article),
    }


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
        teaser = item.find("description")
        pub_date = item.find("pubDate")
        thumb = item.find("media:thumbnail") or item.find("thumbnail")
        content_encoded = item.find("content:encoded") or item.find("encoded")

        article_body = None
        author = None
        if content_encoded and content_encoded.text:
            content_soup = BeautifulSoup(content_encoded.text, "lxml")
            article_body = _paragraphs_to_text(content_soup) or None
            author_el = content_soup.select_one("div.author")
            author = _clean_text(author_el.get_text(" ", strip=True)) if author_el else None

        items.append(
            {
                "_input": "latest",
                "_source": "S2-feed",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "teaser": teaser.text.strip() if teaser and teaser.text else None,
                "articleBody": article_body,
                "author": author,
                "thumbnail": thumb.get("url") if thumb else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
