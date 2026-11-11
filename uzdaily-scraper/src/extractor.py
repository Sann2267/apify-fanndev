"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- uzdaily.uz (Drupal-based) emits a single `NewsArticle`
             ld+json block per article (plus a separate `BreadcrumbList`
             block, ignored) that carries **everything needed directly**:
             `headline`, `description`, `articleBody` (real plain text,
             not HTML), `author` (Person object with name + profile url),
             `image` (array of URL strings), `datePublished`,
             `dateModified`, `articleSection`, `keywords` (comma-separated
             string), `wordCount`, `isAccessibleForFree`, `publisher`.
             No HTML-scraping fallback is needed for article mode.
             `articleBody` uses literal `\\r\\n\\r\\n` as the paragraph
             separator (no HTML tags inside it) -- `_clean_article_body()`
             normalizes this to `\\n\\n`-joined paragraphs with internal
             whitespace/line-wraps collapsed.
  S2-rss   -- `/en/rss/`, a standard RSS 2.0 feed (~20 items, newest
             first). Items carry `title`, `link`, `description` (short
             teaser, not full body), `guid`, `pubDate`, `category`, and an
             `<enclosure>` lead-image URL. No full article text in the
             feed (unlike Kazinform's `/feed.xml`), so `latest` mode
             records carry only the teaser, not `articleBody`.
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


def _clean_article_body(raw: str | None) -> str | None:
    """Normalize the site's literal `\\r\\n\\r\\n`-separated paragraphs
    into `\\n\\n`-joined text, collapsing any stray single-newline
    line-wraps (e.g. inside a trailing byline signature) into spaces."""
    if not raw:
        return None
    text = raw.replace("\r\n", "\n")
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in text.split("\n\n")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs) or None


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def _images(news_article: dict) -> list[str]:
    image = news_article.get("image")
    if isinstance(image, str):
        return [image]
    if isinstance(image, dict):
        url = image.get("url")
        return [url] if url else []
    if isinstance(image, list):
        out = []
        for img in image:
            if isinstance(img, str):
                out.append(img)
            elif isinstance(img, dict) and img.get("url"):
                out.append(img["url"])
        return out
    return []


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = _clean_article_body(news_article.get("articleBody"))
    if not article_body:
        raise UnexpectedShape("articleBody missing/empty in NewsArticle ld+json -- page shape has likely changed.")

    author = news_article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author
    author_url = author.get("url") if isinstance(author, dict) else None

    publisher = news_article.get("publisher")
    publisher_name = publisher.get("name") if isinstance(publisher, dict) else publisher

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": author_name,
        "authorUrl": author_url,
        "publisher": publisher_name,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "images": _images(news_article),
        "articleSection": news_article.get("articleSection"),
        "keywords": news_article.get("keywords"),
        "wordCount": news_article.get("wordCount"),
        "isAccessibleForFree": news_article.get("isAccessibleForFree"),
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
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        category = item.find("category")
        enclosure = item.find("enclosure")

        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "teaser": teaser.text.strip() if teaser and teaser.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "category": category.text.strip() if category and category.text else None,
                "thumbnail": enclosure.get("url") if enclosure else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
