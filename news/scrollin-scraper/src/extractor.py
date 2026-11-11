"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- `application/ld+json` NewsArticle block on the article
                     page (headline/author/publisher/dates/keywords/image),
                     merged with the full article text pulled separately
                     from the `<div id="article-contents" class="article-
                     body">` HTML container -- scroll.in's NewsArticle
                     ld+json block never carries `articleBody` itself.
  S2-sitemap      -- Google News sitemap for `latest` mode.
                     title/link/publication-date/keywords only.
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSON_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)

ARTICLE_TYPES = {"NewsArticle", "ReportageNewsArticle", "Article"}


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unescape(value):
    """Recursively html.unescape() every string in a JSON-LD-shaped value.

    Defensive only -- no double-escaping was observed in recon on any of
    the 4 sampled articles (article/magazine/reel/latest content types),
    but this is cheap insurance against a future CMS quirk, matching the
    rest of the portfolio's convention.
    """
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, list):
        return [_unescape(v) for v in value]
    if isinstance(value, dict):
        return {k: _unescape(v) for k, v in value.items()}
    return value


def _find_article_node(html_text: str) -> dict | None:
    for match in JSON_LD_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") in ARTICLE_TYPES:
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                    return item
    return None


def _extract_body_text(soup: BeautifulSoup) -> str | None:
    container = soup.find("div", id="article-contents", class_="article-body")
    if container is None:
        # Fall back to class-only match in case the id ever drops.
        container = soup.find("div", class_="article-body")
    if container is None:
        return None
    # Direct-child <p> tags only -- embeds (cms-block-embed figures,
    # blockquote widgets) sit as siblings alongside the <p> tags inside the
    # same container and can carry their own nested <p> tags (e.g. social
    # embeds), which recursive=True would incorrectly pull in.
    paras = container.find_all("p", recursive=False)
    if not paras:
        return None
    text = "\n\n".join(p.get_text(" ", strip=True) for p in paras if p.get_text(strip=True))
    return html.unescape(text) if text else None


def extract_article(html_text: str, url: str) -> dict:
    node = _find_article_node(html_text)
    if node is None:
        raise UnexpectedShape(
            "No NewsArticle ld+json block found -- page shape has likely changed."
        )
    node = _unescape(node)

    soup = BeautifulSoup(html_text, "lxml")
    body_text = _extract_body_text(soup)
    if body_text is None:
        raise UnexpectedShape(
            "NewsArticle ld+json found but no #article-contents.article-body "
            "HTML container -- page shape has likely changed."
        )

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        **node,
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


NEWS_NS = "{http://www.google.com/schemas/sitemap-news/0.9}"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    """Parse the Google News sitemap into latest-mode records.

    Uses BeautifulSoup's XML parser (consistent with the rest of the
    portfolio) rather than ElementTree, so namespaced tags are addressed by
    local name (`news:title` -> `find("news:title")`) instead of
    Clark-notation.
    """
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        news = url_tag.find("news:news")
        title = news.find("news:title") if news else None
        pub_date = news.find("news:publication_date") if news else None
        keywords = news.find("news:keywords") if news else None
        image = url_tag.find("image:loc")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": html.unescape(title.text.strip()) if title else None,
                "link": loc.text.strip() if loc else None,
                "publication_date": pub_date.text.strip() if pub_date else None,
                "keywords": html.unescape(keywords.text.strip()) if keywords else None,
                "image": image.text.strip() if image else None,
            }
        )
    # Defensive sort -- observed already newest-first in file order during
    # recon, but sort explicitly in case that ordering isn't guaranteed on
    # every fetch (mirrors guardian-nigeria-scraper precedent).
    items.sort(key=lambda i: i.get("publication_date") or "", reverse=True)
    return items
