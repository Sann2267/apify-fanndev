"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block on the article page.
               The page emits 8 separate ld+json script tags (many
               `SiteNavigationElement` blocks, `BreadcrumbList`, `WebPage`,
               `ImageObject`, `NewsArticle`, `NewsMediaOrganization`,
               `ProfilePage`, `Website`, `ViewAction`) -- this picks out the
               `NewsArticle` one specifically. Carries full articleBody
               plain text.
  S2-rss    -- site-wide `stories.rss` feed for `latest` mode. Same
               Quintype/AssetType CMS shape as other India actors in this
               portfolio: title/link/guid/pubDate plus atom:author,
               media:keywords, category, and a full-HTML content:encoded
               body.
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


def extract_article(html: str, url: str) -> dict:
    for match in JSON_LD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
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
    """Parse the site-wide `stories.rss` feed.

    BeautifulSoup's `xml` (lxml-xml) parser strips namespace prefixes from
    tag names, so `atom:author`/`atom:name` become findable as
    "author"/"name", `media:keywords` as "keywords", `media:content` as
    "content", `media:thumbnail` as "thumbnail", and `content:encoded` as
    "encoded". Confirmed against a live fetch on 2026-08-26 (same shape as
    newindianexpress-scraper's identically-named feed -- both sites run the
    same Quintype/AssetType CMS).
    """
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        category = item.find("category")
        author_block = item.find("author")
        author_name = author_block.find("name") if author_block else None
        author_uri = author_block.find("uri") if author_block else None
        keywords = item.find("keywords")
        media_content = item.find("content")
        thumbnail = item.find("thumbnail")
        content_encoded = item.find("encoded")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link.text.strip() if link else None,
                "guid": guid.text.strip() if guid else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description and description.text.strip() else None,
                "category": category.text.strip() if category else None,
                "author": author_name.text.strip() if author_name else None,
                "authorUrl": author_uri.text.strip() if author_uri else None,
                "keywords": keywords.text.strip() if keywords else None,
                "image": media_content.get("url") if media_content else None,
                "thumbnail": thumbnail.get("url") if thumbnail else None,
                "contentEncoded": content_encoded.text.strip() if content_encoded else None,
            }
        )
    return items
