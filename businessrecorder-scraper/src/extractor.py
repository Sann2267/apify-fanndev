"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html     -- brecorder.com emits a `NewsArticle` ld+json block (one of
                 3 ld+json blocks on the page, alongside an untyped block
                 and a `BreadcrumbList` -- the extractor scans all blocks
                 and picks the one whose `@type` is `NewsArticle`) that
                 carries `headline`, `description`, `datePublished`,
                 `dateModified`, `author` (list of `Person`), `publisher`
                 (`Organization`), `image`, `url`, `mainEntityOfPage`, and
                 `copyrightYear` -- but **no `articleBody`**. That whole
                 block is passed through raw/verbatim (minimal renaming
                 per portfolio convention) and full text is pulled
                 separately from HTML `div.story__content > p` (confirmed
                 on hard-news, markets, opinion, and analysis article
                 types -- no ad/related-article junk paragraphs observed).
  S2-sitemap  -- `/feeds/sitemap`, a Google News-flavored XML sitemap
                 (no RSS/Atom feed exists on this site -- confirmed 404 on
                 every standard path). Lists the ~100 most recently
                 published articles site-wide, each `<url>` block carrying
                 a nested `<news:news>` block with `news:title` and
                 `news:publication_date` (date-only granularity, no time
                 component). Sitemap order is not strictly chronological,
                 so items are re-sorted by the numeric article ID embedded
                 in the URL (`/news/<id>/...`), descending, as a more
                 reliable "newest first" proxy.
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

_ARTICLE_ID_RE = re.compile(r"/news/(\d+)/")


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

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    body_el = soup.select_one("div.story__content")
    if body_el is None:
        raise UnexpectedShape("No div.story__content element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    # CMS leaves raw HTML entities (e.g. &#039;) inside plain-text ld+json
    # fields like `description` -- unescape defensively, same pattern seen
    # in gulfnews-scraper/philstar-scraper.
    if isinstance(news_article.get("description"), str):
        news_article["description"] = html.unescape(news_article["description"])
    if isinstance(news_article.get("headline"), str):
        news_article["headline"] = html.unescape(news_article["headline"])

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        **news_article,
        "articleBody": article_body,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_sitemap_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        news = url_tag.find("news:news")
        if loc is None or loc.text is None or news is None:
            # Non-news entries (section/landing pages like /markets, /world)
            # share the same sitemap -- only <url> blocks with a nested
            # <news:news> block are actual articles.
            continue
        link = loc.text.strip()
        title_tag = news.find("news:title")
        pub_date_tag = news.find("news:publication_date")
        lang_tag = news.find("news:language")
        m = _ARTICLE_ID_RE.search(link)
        article_id = int(m.group(1)) if m else 0
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title_tag.text.strip() if title_tag and title_tag.text else None,
                "link": link,
                "publicationDate": pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None,
                "language": lang_tag.text.strip() if lang_tag and lang_tag.text else None,
                "_articleId": article_id,
            }
        )
    items.sort(key=lambda item: item["_articleId"], reverse=True)
    for item in items:
        del item["_articleId"]
    return items
