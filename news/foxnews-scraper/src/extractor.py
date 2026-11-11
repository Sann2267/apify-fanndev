"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- foxnews.com emits a `@graph` array ld+json block
               (WebSite/NewsMediaOrganization/WebPage/NewsArticle/
               ImageObject/VideoObject/Person nodes all in one script tag)
               -- the extractor scans the graph for the `NewsArticle` node,
               which DOES include `articleBody` directly (rare in this
               portfolio), plus `isAccessibleForFree` (real boolean here,
               not a string like several other sites), `wordCount`, and a
               nested `author` object (`{"@id": ..., "name": ..., "url":
               ...}`). No HTML fallback needed.
  S2-rss    -- site-wide Google Publisher feed
               (`moxie.foxnews.com/google-publisher/latest.xml`) for
               `latest` mode. Carries `content:encoded` with the FULL
               article HTML body already inline (single HTML-entity-escaped,
               standard RSS convention) -- richer than most portfolio latest
               feeds, which normally only carry a teaser. Also carries many
               `<category>` tags per item (internal taxonomy IDs mixed with
               human-readable labels).
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
        except json.JSONDecodeError:
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        candidates = graph if isinstance(graph, list) else ([data] if isinstance(data, dict) else [])
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle node found in ld+json @graph -- page shape has likely changed.")

    article_body = article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("articleBody missing from NewsArticle node -- page shape has likely changed.")

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

    image = article.get("image")
    if isinstance(image, dict):
        image_url = image.get("url")
    elif isinstance(image, list) and image and isinstance(image[0], dict):
        image_url = image[0].get("url")
    else:
        image_url = None

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "articleSection": article.get("articleSection"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "keywords": article.get("keywords"),
        "wordCount": article.get("wordCount"),
        "isAccessibleForFree": article.get("isAccessibleForFree"),
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
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        encoded = item.find("encoded")
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
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
                "contentHtml": encoded.text.strip() if encoded and encoded.text else None,
                "categories": categories,
            }
        )
    return items
