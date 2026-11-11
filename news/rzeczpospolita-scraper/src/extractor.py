"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- rp.pl emits a single `NewsArticle` ld+json block with
               `headline`, `description`, `keywords`, `datePublished`,
               `dateModified`, `isAccessibleForFree` (paywall metering
               flag), `isPartOf` (subscription-tier product info),
               `author`/`creator` (arrays of `Person`), `publisher`,
               `image` -- but **no `articleBody`**. Full text comes from
               HTML `p.article--paragraph--text` (exact class match --
               the article body div also contains "Czytaj więcej" /
               "Read more" related-article widgets that use *different*
               classes, `subtitle` and `lead`, so matching this exact
               class excludes them without extra filtering). **Quirk:**
               the CMS hard-wraps paragraph text with literal `\n`
               characters mid-sentence in the source HTML (for template
               readability, not markup) -- `get_text()` alone leaves
               these embedded newlines in place, so every paragraph is
               passed through a whitespace-collapse regex before joining.
  S2-sitemap -- Google News sitemap
               (`/sitemaps/news-sitemap.xml`, advertised in robots.txt).
               Standard shape: `news:title`, `news:publication_date`.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

_WHITESPACE_RE = re.compile(r"\s+")


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


def _person_names(value) -> list[str]:
    if not value:
        return []
    people = value if isinstance(value, list) else [value]
    return [p.get("name") for p in people if isinstance(p, dict) and p.get("name")]


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    paragraphs = [_WHITESPACE_RE.sub(" ", p.get_text(" ", strip=True)).strip() for p in soup.select("p.article--paragraph--text")]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("No p.article--paragraph--text paragraphs found -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    publisher = news_article.get("publisher") or {}
    is_part_of = news_article.get("isPartOf") or {}
    is_accessible_for_free = news_article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "authors": _person_names(news_article.get("author")),
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "keywords": news_article.get("keywords"),
        "articleSection": news_article.get("articleSection"),
        "isAccessibleForFree": is_accessible_for_free,
        "_paywalled": is_accessible_for_free is False,
        "subscriptionTier": is_part_of.get("name") if isinstance(is_part_of, dict) else None,
        "image": news_article.get("image", {}).get("url") if isinstance(news_article.get("image"), dict) else None,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
