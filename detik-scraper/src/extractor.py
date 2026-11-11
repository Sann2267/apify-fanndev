"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- news.detik.com emits 3 ld+json blocks per article
               (BreadcrumbList, WebPage, NewsArticle); the extractor picks
               the `NewsArticle` node for headline/description/dates/author.
               It has NO `articleBody` field. Full text lives in HTML:
               `div.detail__body-text` (also carries a second class,
               `itp_bodycontent`) wraps the body as bare `<p>` tags. One
               quirk: an inline ad placeholder paragraph
               (`<p class="para_caption">SCROLL TO CONTINUE WITH
               CONTENT</p>`) is interspersed mid-article and must be
               excluded by its `para_caption` class, not by text matching
               (the literal string is an ad-slot label, not real content).
               Empty `<p>` tags (spacing artifacts) are also common and
               skipped.
  S2-sitemap -- Google News sitemap for the main news channel
               (`/berita/sitemap_news.xml`) for `latest` mode. `news:title`,
               `news:publication_date`, `loc` (CDATA-wrapped, unwrapped
               transparently by the XML parser), `news:keywords`.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def extract_article(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle node found in ld+json -- page shape has likely changed.")

    body_div = soup.select_one("div.detail__body-text")
    if body_div is None:
        raise UnexpectedShape("div.detail__body-text not found -- page shape has likely changed.")

    paragraphs = []
    for p in body_div.find_all("p"):
        classes = p.get("class") or []
        if "para_caption" in classes:
            continue
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)
    if not paragraphs:
        raise UnexpectedShape("No body paragraphs extracted from detail__body-text -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "image": image_url,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        keywords = url_node.find("news:keywords")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "keywords": [k.strip() for k in keywords.text.split(",")] if keywords and keywords.text else [],
            }
        )
    return items
