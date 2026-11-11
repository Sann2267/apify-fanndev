"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html   -- JSON-LD `NewsArticle` block on the article page supplies
               headline/author/date/section/image metadata, but has NO
               `articleBody` on this site (WordPress REST API is locked
               down with a 401, so there's no JSON body source either).
               Article text is pulled from the direct-child `<p>` tags of
               `div.single__content.entry-content`, stopping at the first
               `<hr>` (marks the end of the article, start of a "follow us
               on social" footer block). Paragraphs carrying a `class`
               attribute (newsletter CTAs, "never miss a story" inline
               modules) are skipped -- real body paragraphs are bare `<p>`.
  S2-rss    -- site-wide WordPress feed for `latest` mode.
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


def _find_article_jsonld(html: str) -> dict | None:
    for match in JSON_LD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") in ARTICLE_TYPES:
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                    return item
    return None


def _extract_body_text(soup: BeautifulSoup) -> str:
    content = soup.select_one("div.single__content.entry-content")
    if content is None:
        raise UnexpectedShape(
            "div.single__content.entry-content not found -- page shape has likely changed."
        )
    paragraphs = []
    for child in content.find_all(recursive=False):
        if child.name == "hr":
            break
        if child.name == "p" and not child.get("class"):
            text = child.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        raise UnexpectedShape(
            "No body paragraphs extracted from entry-content -- page shape has likely changed."
        )
    return "\n\n".join(paragraphs)


def extract_article(html: str, url: str) -> dict:
    data = _find_article_jsonld(html)
    if data is None:
        raise UnexpectedShape(
            "No NewsArticle ld+json block found -- page shape has likely changed."
        )
    soup = BeautifulSoup(html, "lxml")
    article_body = _extract_body_text(soup)
    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        **data,
        "articleBody": article_body,
    }


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
        creator = item.find("dc:creator")
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
                "creator": creator.text.strip() if creator else None,
            }
        )
    return items
