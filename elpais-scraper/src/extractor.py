"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- english.elpais.com emits 4 ld+json blocks per article page
               (a WebPage @graph, the article record, a SiteNavigationElement
               list, and an ItemList) -- the extractor scans all blocks and
               picks the one whose `@type` contains "NewsArticle" (the field
               is an array here, e.g. ["NewsArticle", "Article",
               "ReportageNewsArticle"] or [..., "OpinionNewsArticle"], not a
               bare string like TASS). Unlike TASS, this block DOES carry a
               full `articleBody` -- confirmed matching (same paragraph text,
               same trailing newsletter-signup CTA sentence) against the
               HTML `div.a_c[data-dtm-region="articulo_cuerpo"] > p` render
               across 8 sampled articles, so JSON-LD is used directly as the
               primary (and only) body source per the JSON-LD-first
               principle -- no HTML fallback needed while it keeps agreeing.
  S2-rss    -- feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada,
               standard RSS 2.0 with Media RSS + Dublin Core extensions
               (title/link/guid/pubDate/description/dc:creator/category*/
               media:content). description is a short teaser only (not full
               article text).

Paywall: `isAccessibleForFree` is present on every sampled article and was
`True` on all 8 samples across usa/international/technology/society/opinion/
climate/eps/economy-and-business sections -- the English edition appears to
be fully open-access, unlike EL PAIS's Spanish-language metered paywall.
The `_paywalled` flag is still derived defensively from the real field
(never hardcoded True) so a subscriber-only article encountered later is
flagged correctly instead of silently passed off as free.
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
        if not isinstance(data, dict):
            continue
        t = data.get("@type")
        if t == "NewsArticle" or (isinstance(t, list) and "NewsArticle" in t):
            return data
    return None


def _flatten_names(value) -> str | None:
    """author/publisher can be a dict, a list of dicts, or a bare string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, list):
        names = [v.get("name") if isinstance(v, dict) else v for v in value]
        names = [n for n in names if n]
        return ", ".join(names) if names else None
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = news_article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("articleBody missing/empty in ld+json -- page shape has likely changed.")

    is_accessible = news_article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "_paywalled": (is_accessible is False),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": _flatten_names(news_article.get("author")),
        "publisher": _flatten_names(news_article.get("publisher")),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "articleSection": news_article.get("articleSection"),
        "keywords": news_article.get("keywords"),
        "image": news_article.get("image"),
        "isAccessibleForFree": is_accessible,
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
        guid = item.find("guid")
        description = item.find("description")
        pub_date = item.find("pubDate")
        creator = item.find("creator")
        categories = item.find_all("category")
        media = item.find("content")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "description": description.text.strip() if description and description.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "creator": creator.text.strip() if creator and creator.text else None,
                "categories": [c.text.strip() for c in categories if c.text] or None,
                "image": media.get("url") if media else None,
            }
        )
    return items
