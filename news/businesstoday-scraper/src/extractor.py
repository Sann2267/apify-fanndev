"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block. Present on every
               article page sampled (multiple verticals: india, latest/
               economy), carrying the full plain-text `articleBody`. Raw
               passthrough of the NewsArticle dict, near-verbatim.
  S2-rss    -- site-wide "latest" RSS feed for `latest` mode.
               title/link/description/pubDate/guid.
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


def _parse_jsonld_blocks(html: str) -> list:
    blocks = []
    for match in JSON_LD_RE.finditer(html):
        try:
            # strict=False: kept as cheap insurance -- indiatoday-scraper (same
            # ITGD/Living Media CMS family) needs this because its NewsArticle
            # ld+json embeds raw unescaped control characters. Not observed to
            # trigger on any businesstoday.in sample checked (strict json.loads
            # parsed cleanly on every article during recon), but the lenient
            # parse is a no-op when the bytes are already valid strict JSON.
            blocks.append(json.loads(match.group(1), strict=False))
        except json.JSONDecodeError:
            continue
    return blocks


def extract_article(html: str, url: str) -> dict:
    blocks = _parse_jsonld_blocks(html)

    for data in blocks:
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
        pub_date = item.find("pubDate")
        description = item.find("description")
        guid = item.find("guid")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link.text.strip() if link else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
                "guid": guid.text.strip() if guid else None,
            }
        )
    return items
