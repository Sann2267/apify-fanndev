"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block on the article page.
               The page emits 5 separate ld+json script tags (Organization,
               WebPage, BreadcrumbList, NewsArticle, ItemList nav) -- this
               picks out the NewsArticle one specifically.
  S2-rss    -- site-wide RSS 2.0 feed (`/rss.xml`) for `latest` mode.
               title/link/guid/pubDate/description/category/creator, plus
               full HTML in `content:encoded`.
"""

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


def _parse_ld_json(raw: str):
    """deccanchronicle.com's NewsArticle ld+json block sometimes embeds a
    literal, unescaped tab character inside `articleBody` (confirmed on a
    live sample 2026-08-26). That's invalid per strict JSON (control chars
    must be \\-escaped), so `json.loads` raises `JSONDecodeError` with
    `strict=True` (the default). `strict=False` accepts it -- same fallback
    used for other portfolio sites with the same CMS quirk.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(raw, strict=False)


def extract_article(html: str, url: str) -> dict:
    for match in JSON_LD_RE.finditer(html):
        try:
            data = _parse_ld_json(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") in ARTICLE_TYPES:
            return {
                "_input": url,
                "_source": "S1-jsonld",
                "_scrapedAt": utc_now_iso(),
                **data,
            }
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                    return {
                        "_input": url,
                        "_source": "S1-jsonld",
                        "_scrapedAt": utc_now_iso(),
                        **item,
                    }
    raise UnexpectedShape(
        "No NewsArticle ld+json block found -- page shape has likely changed."
    )


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        category = item.find("category")
        creator = item.find("dc:creator") or item.find("creator")
        content_encoded = item.find("content:encoded") or item.find("encoded")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link.text.strip() if link else None,
                "guid": guid.text.strip() if guid else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
                "category": category.text.strip() if category else None,
                "creator": creator.text.strip() if creator else None,
                "contentEncoded": content_encoded.text.strip() if content_encoded else None,
            }
        )
    return items
