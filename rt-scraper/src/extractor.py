"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html  -- rt.com emits an `Organization` block, a `BreadcrumbList`
             block, and a `NewsArticle` block -- the extractor scans all
             ld+json blocks and picks the one whose `@type` is
             `NewsArticle`. That block carries `headline`, `description`,
             `image`, `author`/`publisher` (Organization "RT"),
             `datePublished`, `dateModified` -- but **no `articleBody`**.
             Full text comes from HTML `div.article__text > p` (plain
             `<p>` tags, no ad/embed noise found across a 21-paragraph
             sample).
  S2-rss   -- `/rss/`, RSS 2.0 with a `<content:encoded>` element that
             (unusually for this portfolio) carries the **full article
             HTML**, not just a teaser -- parsed the same way as the
             article-page body (`<p>` tags joined with blank lines). The
             `<description>` element is a short teaser with an embedded
             `<img>` + "Read Full Article at RT.com" link and is kept
             separately, unparsed, for reference.
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


def _paragraphs_to_text(container) -> str:
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.article__text")
    if body_el is None:
        raise UnexpectedShape("No div.article__text element found -- page shape has likely changed.")
    article_body = _paragraphs_to_text(body_el)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    publisher = news_article.get("publisher") or {}
    image = news_article.get("image") or []
    image_urls = [img.get("url") for img in image if isinstance(img, dict) and img.get("url")]

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
        "images": image_urls,
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
        content_encoded = item.find("content:encoded") or item.find("encoded")
        pub_date = item.find("pubDate")

        article_body = None
        if content_encoded and content_encoded.text:
            content_soup = BeautifulSoup(content_encoded.text, "lxml")
            article_body = _paragraphs_to_text(content_soup) or None

        link_text = link.text.strip() if link and link.text else None
        if link_text:
            link_text = link_text.split("?utm_source=")[0]

        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link_text,
                "teaser": teaser.text.strip() if teaser and teaser.text else None,
                "articleBody": article_body,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
