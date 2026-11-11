"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block on the article page.
               A single script tag, bare dict (not a list).
  S2-atom   -- site-wide feed for `latest` mode is **Atom**, not RSS 2.0
               (`<feed>/<entry>` with `<link rel="alternate">`, `<summary>`,
               `<published>`/`<updated>`, `<author><name>`, `<category
               term="...">`) -- unlike every other outlet in this portfolio.
               A dedicated parser is used instead of the shared
               `extract_rss_items` RSS-2.0 helper.
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
    """Parse Vox's Atom feed (`<feed>/<entry>`), not RSS 2.0."""
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for entry in soup.find_all("entry"):
        title = entry.find("title")
        link_tag = entry.find("link", rel="alternate") or entry.find("link")
        entry_id = entry.find("id")
        published = entry.find("published")
        updated = entry.find("updated")
        summary = entry.find("summary")
        author = entry.find("author")
        author_name = author.find("name") if author else None
        categories = [
            c.get("term").strip() for c in entry.find_all("category") if c.get("term")
        ]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-atom",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link_tag.get("href").strip() if link_tag and link_tag.get("href") else None,
                "guid": entry_id.text.strip() if entry_id else None,
                "pubDate": published.text.strip() if published else None,
                "updated": updated.text.strip() if updated else None,
                "description": summary.text.strip() if summary else None,
                "author": author_name.text.strip() if author_name else None,
                "categories": categories,
            }
        )
    return items
