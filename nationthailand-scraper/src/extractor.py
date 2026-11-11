"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- nationthailand.com emits 5 ld+json blocks per article page
               (2x `Organization`, `WebSite`, `BreadcrumbList`, and the
               `NewsArticle` itself) -- the extractor scans all blocks and
               picks the one whose `@type` is `NewsArticle`. It carries
               `headline`, `description`, `keywords`, `articleSection`,
               `dateCreated`/`datePublished`/`dateModified`, `author`,
               `publisher`, `image`, and `isAccessibleForFree` -- and it
               DOES have an `articleBody` key, but that field is just the
               short deck/teaser (confirmed identical to `description`,
               ~140-150 chars on 2 samples), NOT the full article -- full
               text is pulled separately from HTML `div.content-detail >
               p` instead.
  Soft-404   -- a nonexistent article ID returns HTTP 200 rendering the
               homepage shell (same byte length as a real homepage fetch),
               not a distinct error page or a real 404 status. Detected via
               `<link rel="canonical">`: on a real article it matches the
               requested URL; on the soft-404 shell it always points to
               the bare homepage (`https://www.nationthailand.com/`)
               instead -- a mismatch is treated as `not_found`.
  S2-sitemap -- `/sitemap/latest` (advertised via `Sitemap:` in
               robots.txt), a Google News-flavored XML sitemap. Most
               `<url>` entries are category/tag landing pages with no
               `<news:news>` block -- only entries that DO carry one are
               real articles (confirmed: 5 of the first ~10 entries are
               category pages, filtered out). `news:title` and
               `news:publication_date` are used directly; document order
               is already newest-first.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class SoftNotFound(Exception):
    """Page returned HTTP 200 but is actually the soft-404 homepage shell."""


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


def is_soft_404(soup: BeautifulSoup, url: str) -> bool:
    canonical = soup.find("link", rel="canonical")
    if canonical is None or not canonical.get("href"):
        return False
    canon_href = canonical["href"].rstrip("/")
    return canon_href in ("https://www.nationthailand.com", "http://www.nationthailand.com") and url.rstrip(
        "/"
    ) != canon_href


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    if is_soft_404(soup, url):
        raise SoftNotFound("Canonical link points at the bare homepage -- article does not exist.")

    body_el = soup.select_one("div.content-detail")
    if body_el is None:
        raise UnexpectedShape("No div.content-detail element found -- page shape has likely changed.")
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
    is_free = news_article.get("isAccessibleForFree")

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
        "articleSection": news_article.get("articleSection"),
        "keywords": news_article.get("keywords"),
        "image": news_article.get("image"),
        "isAccessibleForFree": is_free,
        "_paywalled": is_free is False,
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
        news = url_tag.find("news:news")
        if news is None:
            # Category/tag landing pages share this sitemap but have no
            # <news:news> block -- only entries with one are real articles.
            continue
        loc = url_tag.find("loc")
        if loc is None or not loc.text:
            continue
        title_tag = news.find("news:title")
        pub_date_tag = news.find("news:publication_date")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title_tag.text.strip() if title_tag and title_tag.text else None,
                "link": loc.text.strip(),
                "publicationDate": pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None,
            }
        )
    return items
