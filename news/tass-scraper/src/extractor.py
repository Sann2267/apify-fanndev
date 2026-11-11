"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html  -- tass.com emits a `NewsArticle` ld+json block (one of 3
             ld+json blocks on the page, alongside an `Organization` block
             and a `@graph` of `SiteNavigationElement` entries -- the
             extractor scans all blocks and picks the one whose `@type`
             is `NewsArticle`) that carries `headline`, `datePublished`,
             `dateModified`, `author`/`publisher` (both `Organization`,
             since bylines are agency-attributed not individual), and
             `description` -- but **no `articleBody`**. Full text is
             pulled from HTML `div.text-block > p` instead (plain `<p>`
             tags, no extra wrapper classes to filter, confirmed on both
             a short 3-paragraph brief and a longer 4-paragraph story).
  S2-rss   -- `/rss/v2.xml`, standard RSS 2.0 (title/link/guid/pubDate/
             description/category), description is a short teaser only
             (not full article text).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    body_el = soup.select_one("div.text-block")
    if body_el is None:
        raise UnexpectedShape("No div.text-block element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    publisher = news_article.get("publisher") or {}

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": author.get("name") if isinstance(author, dict) else author,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
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
        category = item.find("category")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": description.text.strip() if description and description.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "category": category.text.strip() if category and category.text else None,
            }
        )
    return items
