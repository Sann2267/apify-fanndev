"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- channelnewsasia.com emits a single `application/ld+json`
               block per article as a `@graph` array containing a
               `NewsArticle` node (headline/description/dates/author/
               publisher) but **no `articleBody` field**. Full text must be
               read from the HTML: `div.text > div.text-long` blocks, in
               document order, each containing `<p>` tags. Most articles
               have exactly one such block; longform/brand-studio articles
               (e.g. syndicated Financial Times pieces) split the body
               across many sequential blocks -- all must be concatenated,
               not just the first.
  S2-rss    -- site-wide feed (`/api/v1/rss-outbound-feed`, explicitly
               allowed in robots.txt) for `latest` mode. Fields: title,
               link, guid, pubDate, category, media:thumbnail. Most items
               have an empty `<description/>`.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        candidates = graph if isinstance(graph, list) else ([data] if isinstance(data, dict) else [])
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def extract_article(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    article = _find_news_article(html)
    if article is None:
        raise UnexpectedShape("No NewsArticle node found in ld+json @graph -- page shape has likely changed.")

    body_blocks = soup.select("div.text > div.text-long")
    if not body_blocks:
        raise UnexpectedShape("div.text > div.text-long not found -- page shape has likely changed.")

    paragraphs = []
    for block in body_blocks:
        for p in block.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        raise UnexpectedShape("No body paragraphs extracted from text-long blocks -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

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
        "image": (article.get("image") or {}).get("url") if isinstance(article.get("image"), dict) else None,
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
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        category = item.find("category")
        thumb = item.find("media:thumbnail")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": description.text.strip() if description and description.text else None,
                "category": category.text.strip() if category and category.text else None,
                "thumbnailUrl": thumb.get("url") if thumb else None,
            }
        )
    return items
