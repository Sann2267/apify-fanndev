"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html  -- tuoitrenews.vn (served from news.tuoitre.vn after the
             standard 302 redirect) emits 3 separate ld+json blocks: a
             `NewsArticle` block, a `BreadcrumbList`, and an
             `Organization` block -- the extractor scans all blocks and
             picks the one whose `@type` is `NewsArticle`. That block
             carries `headline`, `description`, `datePublished`,
             `dateModified`, `author` (a `Person`, individual bylines
             unlike wire-service outlets), and `publisher` (an
             `Organization`) -- but **no `articleBody`**. Full text is
             pulled from HTML `div.detail-content > p` instead, EXCLUDING
             `<p>` tags nested inside `<figcaption>` (photo captions,
             would otherwise pollute the body text) and inside any
             `[relatednewsboxtype]` block (related-articles widget with
             no `<p>` tags in practice, excluded defensively anyway).
             HTML entities in ld+json string fields (e.g. `&#39;` in
             headlines like "Ho Chi Minh City's...") are unescaped.
  S2-rss   -- `/rss` (redirects to `news.tuoitre.vn/rss`), standard RSS
             2.0 with title/link/description/enclosure/author/pubDate --
             NO `guid`, NO `category` field on this feed (confirmed absent
             across 50 sampled items). `description` is a short teaser
             only (not full article text).
"""

import html as html_module
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unescape(value):
    if isinstance(value, str):
        return html_module.unescape(value)
    return value


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.detail-content")
    if body_el is None:
        raise UnexpectedShape("No div.detail-content element found -- page shape has likely changed.")
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in body_el.find_all("p")
        if not p.find_parent("figcaption") and not p.find_parent(attrs={"relatednewsboxtype": True})
    ]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    publisher = news_article.get("publisher") or {}
    image = news_article.get("image") or {}

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(news_article.get("headline")),
        "description": _unescape(news_article.get("description")),
        "articleBody": article_body,
        "author": _unescape(author.get("name")) if isinstance(author, dict) else _unescape(author),
        "publisher": _unescape(publisher.get("name")) if isinstance(publisher, dict) else _unescape(publisher),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": image.get("url") if isinstance(image, dict) else image,
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
        author = item.find("author")
        pub_date = item.find("pubDate")
        enclosure = item.find("enclosure")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": description.text.strip() if description and description.text else None,
                "author": author.text.strip() if author and author.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "image": enclosure.get("url") if enclosure else None,
            }
        )
    return items
