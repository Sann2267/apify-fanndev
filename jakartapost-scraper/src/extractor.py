"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- thejakartapost.com emits a `NewsArticle` ld+json block
               with headline/dates/author/publisher and an
               `isAccessibleForFree` flag (string `"true"`/`"false"`), but
               NO `articleBody` or `description` field. `description` is
               instead read from `meta[property="og:description"]`.
               Full text lives in HTML: `div.tjp-single__content` wraps the
               body, with the first paragraph split unusually into
               `div.tjp-opening > h1.tjp-opening__char` (drop-cap first
               letter) + `p.tjp-opening__txt` (rest of the sentence) --
               concatenated with NO space to reform the real first word.
               Subsequent paragraphs are bare `<p>` **direct children** of
               `.tjp-single__content`, interspersed with ad/newsletter `<div>`
               wrappers at the same level -- `find_all(..., recursive=False)`
               naturally skips those wrapper divs' inner `<p>` tags.
  S2-sitemap -- Google News sitemap (`/sitemap_news.xml`) for `latest` mode.
               `news:title`, `news:publication_date`, `loc`.
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

    content = soup.select_one(".tjp-single__content")
    if content is None:
        raise UnexpectedShape(".tjp-single__content not found -- page shape has likely changed.")

    paragraphs = []
    opening = content.select_one(".tjp-opening")
    if opening is not None:
        char = opening.select_one(".tjp-opening__char")
        rest = opening.select_one(".tjp-opening__txt")
        first_para = (char.get_text(strip=True) if char else "") + (
            rest.get_text(" ", strip=True) if rest else ""
        )
        if first_para:
            paragraphs.append(first_para)

    for p in content.find_all("p", recursive=False):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)

    if not paragraphs:
        raise UnexpectedShape("No body paragraphs extracted from tjp-single__content -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    description = og_desc["content"].strip() if og_desc and og_desc.get("content") else None

    author = article.get("author")
    if isinstance(author, list):
        author_name = ", ".join(a.get("name") for a in author if isinstance(a, dict) and a.get("name"))
    elif isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else None

    is_free_raw = article.get("isAccessibleForFree")
    is_paywalled = str(is_free_raw).strip().lower() == "false"

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": description,
        "articleBody": article_body,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "image": image_url,
        "_paywalled": is_paywalled,
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
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
