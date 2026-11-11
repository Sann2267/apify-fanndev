"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- philstar.com emits a single `NewsArticle` ld+json block
               (headline/alternativeHeadline/description/dates/author/
               articleSection/keywords) but NO `articleBody` field. Full
               text lives in HTML: `div.article__content > p`, bare
               paragraphs, no ad placeholders or stray empty tags observed
               in samples -- simpler than most of this portfolio.
               **Quirk:** the ld+json `description` value is itself
               HTML-entity-escaped HTML (`"&lt;p&gt;...text...&lt;/p&gt;\r\n"`)
               rather than plain text -- must be unescaped and stripped of
               tags, or downstream consumers get literal `&lt;p&gt;` noise.
  S2-rss    -- site-wide feed (`/rss/headlines`) for `latest` mode.
               Standard RSS 2.0 with `author` present directly on each
               `<item>` (unusual -- most portfolio feeds only carry
               author on the article page, not the feed).
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def _clean_description(raw: str | None) -> str | None:
    """Unescape HTML entities and strip tags -- philstar's ld+json description
    is HTML-entity-escaped markup, not plain text (see module docstring).
    Unescaping must happen BEFORE parsing: entity decoding inside an HTML
    parser only ever produces literal text, never re-tokenizes as tags."""
    if not raw:
        return raw
    unescaped = html.unescape(raw)
    text = BeautifulSoup(unescaped, "lxml").get_text(" ", strip=True)
    return text or None


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

    body_div = soup.select_one("div.article__content")
    if body_div is None:
        raise UnexpectedShape("div.article__content not found -- page shape has likely changed.")

    paragraphs = [
        p.get_text(" ", strip=True) for p in body_div.find_all("p") if p.get_text(strip=True)
    ]
    if not paragraphs:
        raise UnexpectedShape("No body paragraphs extracted from article__content -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    author = article.get("author")
    if isinstance(author, list):
        author_name = ", ".join(a.get("name") for a in author if isinstance(a, dict) and a.get("name"))
    elif isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else None

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
        author = item.find("author")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "author": author.text.strip() if author and author.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": description.text.strip() if description and description.text else None,
            }
        )
    return items
