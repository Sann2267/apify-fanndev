"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block on the article page.
               Rich shape: byline (author array with jobTitle/url), editor,
               full NewsMediaOrganization publisher block, mainEntityOfPage.
  S2-atom   -- site-wide Atom feed (`/rss`) for `latest` mode. Atom, not RSS
               2.0 -- <entry>/<id>/<updated>/<content type="html"> instead of
               <item>/<guid>/<pubDate>/<description>.
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


def extract_feed_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for entry in soup.find_all("entry"):
        title = entry.find("title")
        entry_id = entry.find("id")
        updated = entry.find("updated")
        content = entry.find("content")
        category = entry.find_all("category")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-atom",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": entry_id.text.strip() if entry_id else None,
                "updated": updated.text.strip() if updated else None,
                "content": content.text.strip() if content else None,
                "categories": [c.get("term") for c in category if c.get("term")],
            }
        )
    return items
