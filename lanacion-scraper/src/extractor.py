"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- lanacion.com.ar runs on Arc Publishing (same CMS family as
               eluniversal-scraper) and emits 5-10 separate ld+json blocks
               per article page (`NewsMediaOrganization`, `WebSite`,
               `BreadcrumbList`, plus the article node itself). Regular news
               stories use `@type: "NewsArticle"`; opinion columns use a
               distinct `@type: "OpinionNewsArticle"` (same shape, extra
               `creator` field, individual `Person` byline instead of the
               `Organization` byline used for staff/wire stories) -- the
               extractor accepts either type. **`articleBody` is present in
               full** directly in the ld+json (confirmed on 25 articles
               across politica/el-mundo/sociedad/seguridad/opinion sections,
               short breaking-news briefs through long-form opinion pieces)
               -- no HTML fallback needed, unlike tass-scraper/
               eluniversal-scraper.
               `author` is a dict (`{"@type": "Organization", "name": "LA
               NACION"}`) for staff/wire content or a list of
               `{"@type": "Person", "name": ...}` dicts for bylined opinion
               columns -- both shapes are normalized to a comma-joined name
               string. `publisher` is only a JSON-LD `@id` reference
               (`{"@id": "https://www.lanacion.com.ar/#organization"}`), not
               a resolved name -- passed through raw rather than fabricated,
               per raw-passthrough convention. `image` and `keywords` are
               already list-shaped in the source JSON (unlike
               eluniversal-scraper's comma-string `keywords`) and are passed
               through verbatim.
  S2-rss     -- `/arc/outboundfeeds/rss/`, standard RSS 2.0 (title/link/
               guid/pubDate/description/category) plus a `content:encoded`
               CDATA block carrying the full article HTML -- NOT parsed
               here to keep `latest` mode a lightweight headline listing
               consistent with the rest of the portfolio; use `article`
               mode against `link` for the full clean-text record.

Paywall handling: every ld+json article node carries `isAccessibleForFree`
(bool) and, on some articles, an `isPartOf` block naming the subscription
product (e.g. `"Acceso Digital Monthly Test"` / productID
`lanacion.com.ar:acceso_digital`) -- evidence the site runs a metered
paywall even though every sampled article during recon came back
`isAccessibleForFree: true` with a full, non-truncated body (paywall
appears to be enforced client-side via JS for human readers, not on the
server-rendered HTML this actor reads). Both fields are passed through
raw, and `_paywalled` is derived defensively (`True` only when
`isAccessibleForFree` is explicitly `false`) so a future tightening of the
paywall is reflected accurately rather than silently ignored.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup

KNOWN_ARTICLE_TYPES = {"NewsArticle", "OpinionNewsArticle"}


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_article_node(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") in KNOWN_ARTICLE_TYPES:
                return node
    return None


def _normalize_author(author) -> str | None:
    if isinstance(author, list):
        names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]
        return ", ".join(names) if names else None
    if isinstance(author, dict):
        return author.get("name")
    if isinstance(author, str):
        return author
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_article_node(soup)
    if article is None:
        raise UnexpectedShape(
            "No NewsArticle/OpinionNewsArticle ld+json block found -- page shape has likely changed."
        )

    article_body = article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("ld+json article node has no articleBody -- page shape has likely changed.")

    is_free = article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": _normalize_author(article.get("author")),
        "articleSection": article.get("articleSection"),
        "isAccessibleForFree": is_free,
        "_paywalled": is_free is False,
        "isPartOf": article.get("isPartOf"),
        "keywords": article.get("keywords") or [],
        "image": article.get("image"),
        "publisher": article.get("publisher"),
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
