"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` block on the article page. Axios emits
               this as a single script tag containing a JSON *list*
               (`[NewsMediaOrganization, NewsArticle]`), not a bare dict --
               unlike most other outlets in this portfolio. Both list and
               dict shapes are handled here for robustness.
  S2-rss    -- site-wide RSS 2.0 feed (`api.axios.com/feed/`) for `latest`
               mode. Unusually rich for RSS: full `content:encoded` body,
               multiple `dc:creator` tags (co-bylines), `media:content`
               thumbnail, and `category`.
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
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        content_encoded = item.find("content:encoded")
        creators = [c.text.strip() for c in item.find_all("dc:creator") if c.text]
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
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
                "content": content_encoded.text.strip() if content_encoded else None,
                "creators": creators,
                "categories": categories,
            }
        )
    return items
