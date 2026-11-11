"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` block, a JSON *list* of
               [NewsArticle, BreadcrumbList] (bild.de emits a list, not a
               single dict -- unlike most of the portfolio). The NewsArticle
               entry never carries `articleBody`, so full text is pulled
               separately from the HTML `div.article-body` container and
               attached as `articleBody`.
  S2-sitemap -- for `latest` mode: Google News sitemap `<url>` entry
                (loc/news:title/news:publication_date/news:keywords only --
                no body).

BILD enforces a genuine (not cosmetic) "BILDplus" paywall on a subset of
articles: `isAccessibleForFree: false` in the ld+json block correlates with
a short teaser body (~400-650 chars) instead of the full ~1800-4700 chars.
This extractor never fabricates missing text -- it records `_paywalled` and
whatever teaser/full text the page actually served, same tier as
business-standard-scraper / washingtonpost-scraper.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_json_ld_article(html_bytes: bytes) -> tuple[dict, "BeautifulSoup"]:
    soup = BeautifulSoup(html_bytes, "lxml")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not tag.string:
            continue
        try:
            data = json.loads(tag.string)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "NewsArticle":
                return item, soup
    raise UnexpectedShape(
        "No NewsArticle ld+json block found -- page shape has likely changed."
    )


def _extract_body_text(soup: "BeautifulSoup") -> str | None:
    el = soup.select_one("div.article-body") or soup.select_one("article")
    if el is None:
        return None
    paras = el.find_all("p")
    if paras:
        text = "\n\n".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))
    else:
        text = el.get_text(separator="\n\n", strip=True)
    return text or None


def extract_article(html_bytes: bytes, url: str) -> dict:
    """raw is upstream payload (passthrough); returns dataset-ready record."""
    article, soup = _extract_json_ld_article(html_bytes)
    body_text = _extract_body_text(soup)
    is_free = article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "_paywalled": (is_free is False),
        **article,
        "articleBody": body_text,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_sitemap_items(xml_bytes: bytes, limit: int) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    ns_news = "{http://www.google.com/schemas/sitemap-news/0.9}"
    for url_tag in soup.find_all("url")[:limit]:
        loc = url_tag.find("loc")
        news = url_tag.find("news:news") or url_tag.find("news")
        title = news.find("news:title") if news else None
        if title is None and news is not None:
            title = news.find("title")
        pub_date = news.find("news:publication_date") if news else None
        if pub_date is None and news is not None:
            pub_date = news.find("publication_date")
        keywords = news.find("news:keywords") if news else None
        if keywords is None and news is not None:
            keywords = news.find("keywords")
        items.append(
            {
                "_input": "latest:bild.de",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": loc.text.strip() if loc else None,
                "publicationDate": pub_date.text.strip() if pub_date else None,
                "keywords": keywords.text.strip() if keywords else None,
            }
        )
    return items
