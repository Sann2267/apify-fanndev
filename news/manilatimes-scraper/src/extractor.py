"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- manilatimes.net emits a single `NewsArticle` ld+json
               block with headline/description/dates/author/articleSection/
               keywords/image/isAccessibleForFree, and it DOES carry an
               `articleBody` string -- but that string has no paragraph
               breaks (sentences run together, e.g. "...its logo.In a
               statement...") and its quotes/dashes are HTML-entity-escaped
               (`&ldquo;`, `&rsquo;`, `&mdash;`). Full, properly-paragraphed
               text instead comes from HTML: `div.article-body > p`
               (matches article pages across News/Business/Sports/TMT
               Newswire sections; a stray empty leading `<p>` appears on
               some wire-service reprints and is filtered out).
               **Quirks:** (1) the raw ld+json script text contains literal
               unescaped control characters (real newline bytes inside a
               JSON string value), so `json.loads` must use `strict=False`
               or it raises "Invalid control character at...". (2) the
               `description` field is plain text but HTML-entity-escaped on
               some articles ("MANILA, Philippines &mdash; June Mar...") and
               already-clean on others -- `html.unescape()`d unconditionally
               (safe no-op when no entities present).
  S2-rss    -- site-wide "Latest News" feed (`/latest/feed/`, spans every
               section) for `latest` mode. Unusually generous: the RSS
               `<description>` CDATA block carries the FULL article body as
               real `<p>`-tagged HTML (single HTML-entity-escaped inside the
               CDATA, e.g. `&ldquo;`), not just a teaser -- unescaped and
               tag-stripped into a paragraph-joined `description` field.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(html_text: str) -> dict | None:
    soup = BeautifulSoup(html_text, "lxml")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            # strict=False: manilatimes.net's ld+json contains raw control
            # characters inside string values (see module docstring).
            data = json.loads(script.string, strict=False)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def _clean_description(raw: str | None) -> str | None:
    """The ld+json `description` field is plain text but HTML-entity-escaped
    (e.g. "MANILA, Philippines &mdash; June Mar Fajardo..." -- real dash
    entity, not literal text) on some articles, and already-clean on others.
    A single html.unescape() is a safe no-op when no entities are present."""
    if not raw:
        return raw
    return html.unescape(raw)


def _clean_html_text(raw: str | None, unescape_times: int = 1) -> str | None:
    """Unescape HTML entities then join <p> paragraphs with blank lines.
    Falls back to plain get_text() if no <p> tags survive (e.g. a bare
    teaser sentence with no markup at all)."""
    if not raw:
        return raw
    text = raw
    for _ in range(unescape_times):
        text = html.unescape(text)
    soup = BeautifulSoup(text, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    if paragraphs:
        return "\n\n".join(paragraphs)
    cleaned = soup.get_text(" ", strip=True)
    return cleaned or None


def extract_article(html_text: str, url: str) -> dict:
    article = _find_news_article(html_text)
    if article is None:
        raise UnexpectedShape("No NewsArticle node found in ld+json -- page shape has likely changed.")

    soup = BeautifulSoup(html_text, "lxml")
    body_div = soup.select_one("div.article-body")
    if body_div is None:
        raise UnexpectedShape("div.article-body not found -- page shape has likely changed.")

    paragraphs = [
        p.get_text(" ", strip=True) for p in body_div.find_all("p") if p.get_text(strip=True)
    ]
    if not paragraphs:
        raise UnexpectedShape("No body paragraphs extracted from article-body -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    author = article.get("author")
    if isinstance(author, list):
        author_name = ", ".join(a.get("name") for a in author if isinstance(a, dict) and a.get("name"))
    elif isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else (image if isinstance(image, str) else None)

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": _clean_description(article.get("description")),
        "articleBody": article_body,
        "articleSection": article.get("articleSection"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "keywords": article.get("keywords"),
        "image": image_url,
        "isAccessibleForFree": article.get("isAccessibleForFree"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        author = item.find("dc:creator")
        category = item.find("category")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        media_thumb = item.find("media:thumbnail")
        media_content = item.find("media:content")
        image_url = media_thumb.get("url") if media_thumb else (media_content.get("url") if media_content else None)
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "author": author.text.strip() if author and author.text else None,
                "category": category.text.strip() if category and category.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": _clean_html_text(description.text if description else None, unescape_times=1),
                "imageUrl": image_url,
            }
        )
    return items
