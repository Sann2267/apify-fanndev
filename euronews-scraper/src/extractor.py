"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html  -- euronews.com emits one ld+json block shaped as
             `{"@context": ..., "@graph": [...]}` (a second, separate
             block on the page carries a `BreadcrumbList`). The extractor
             scans the `@graph` array for the entry whose `@type` is
             `NewsArticle` (headline, description, articleBody, author
             (list of `Person`), dateCreated/dateModified/datePublished,
             image, articleSection) and, separately, the entry whose
             `@type` is `Organization` (used to resolve the publisher
             name -- `NewsArticle.publisher` is only a bare `{"@id": ...}`
             reference, not an inline object). The ld+json `articleBody`
             string has paragraph breaks stripped (sentences run together
             with no separating space in places), so full text is instead
             pulled from HTML `div.c-article-content > p` (direct-child
             `<p>` tags only -- the container also holds `<div>` ad/video-
             embed/related-articles widgets and occasional `<h2>`
             subheadings, none of which carry nested `<p>` tags, confirmed
             across 3 sampled articles; subheadings are intentionally
             dropped from articleBody).
  S2-rss   -- `/rss`, standard RSS 2.0 (title/link/guid/pubDate/
             description, no category field), description is a short
             teaser only (not full article text). The feed mixes text
             articles with `/video/...` items; video pages carry a
             `VideoObject` ld+json block instead of `NewsArticle`, so
             feeding a video link into `article` mode correctly raises
             `UnexpectedShape` (fail loud, not a silently empty body).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_graph_entries(soup: BeautifulSoup) -> list[dict]:
    """Return the `@graph` array from the first ld+json block that has one."""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            return data["@graph"]
    return []


def _find_by_type(graph: list[dict], type_name: str) -> dict | None:
    for entry in graph:
        if isinstance(entry, dict) and entry.get("@type") == type_name:
            return entry
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.c-article-content")
    if body_el is None:
        raise UnexpectedShape("No div.c-article-content element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p", recursive=False)]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    graph = _find_graph_entries(soup)
    news_article = _find_by_type(graph, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    organization = _find_by_type(graph, "Organization")
    publisher = organization.get("name") if organization else None

    authors = news_article.get("author") or []
    if isinstance(authors, dict):
        authors = [authors]
    author_names = [a.get("name") for a in authors if isinstance(a, dict) and a.get("name")]

    image = news_article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else image

    article_section = news_article.get("articleSection")
    if isinstance(article_section, list):
        article_section = article_section[0] if article_section else None

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": image_url,
        "articleSection": article_section,
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
        description = item.find("description")
        pub_date = item.find("pubDate")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": description.text.strip() if description and description.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
