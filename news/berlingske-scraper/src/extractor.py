"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-nextdata -- `__NEXT_DATA__` script tag, `props.pageProps.article`. This
                 is a rich block-based article object (id, title, headline,
                 categories, tags, contributions/byline, body as a list of
                 `ParagraphNode`/`TextNode` blocks, payWall, relatedArticles)
                 -- the richest available shape, passed through verbatim
                 (raw-passthrough convention) with a flattened `articleText`
                 convenience field added.
  S2-sitemap  -- for `latest` mode: Google News sitemap `<url>` entry
                 (loc/news:title/news:publication_date only -- no body).

The page also carries a `WebSite` ld+json block, but NOT a `NewsArticle`
one -- unlike the rest of the portfolio, JSON-LD is not useful here and
__NEXT_DATA__ is the only source, not a fallback.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flatten_body(body_blocks) -> str | None:
    if not isinstance(body_blocks, list):
        return None
    paragraphs = []
    for block in body_blocks:
        if not isinstance(block, dict):
            continue
        text = "".join(
            child.get("value", "")
            for child in block.get("children", [])
            if isinstance(child, dict) and "value" in child
        )
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs) or None


def _extract_next_data_article(html: str) -> dict:
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise UnexpectedShape("__NEXT_DATA__ script tag not found -- page shape has likely changed.")
    try:
        nd = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__NEXT_DATA__ present but not valid JSON: {e}") from e
    article = nd.get("props", {}).get("pageProps", {}).get("article")
    if not article or "body" not in article or "title" not in article:
        raise UnexpectedShape(
            f"pageProps.article missing expected keys; got={list((article or {}).keys())}"
        )
    return article


def extract_article(html: str, url: str) -> dict:
    """raw is upstream payload (passthrough); returns dataset-ready record."""
    article = _extract_next_data_article(html)
    pay_wall = article.get("payWall")

    return {
        "_input": url,
        "_source": "S1-nextdata",
        "_scrapedAt": utc_now_iso(),
        "_paywalled": bool(pay_wall),
        **article,
        "articleText": _flatten_body(article.get("body")),
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
    for url_tag in soup.find_all("url")[:limit]:
        loc = url_tag.find("loc")
        news = url_tag.find("news:news") or url_tag.find("news")
        title = news.find("news:title") if news else None
        if title is None and news is not None:
            title = news.find("title")
        pub_date = news.find("news:publication_date") if news else None
        if pub_date is None and news is not None:
            pub_date = news.find("publication_date")
        items.append(
            {
                "_input": "latest:berlingske.dk",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": loc.text.strip() if loc else None,
                "publicationDate": pub_date.text.strip() if pub_date else None,
            }
        )
    return items
