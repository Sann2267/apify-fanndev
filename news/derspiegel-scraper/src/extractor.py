"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html   -- JSON-LD `NewsArticle` block (emitted as a JSON *list*
               alongside a `BreadcrumbList`, not a single dict) supplies
               headline/author/dates/section/keywords/`isAccessibleForFree`,
               but carries NO `articleBody`. Body text is pulled from HTML:
               `div[data-area="body"] > div[data-area="text"] > p`, which is
               only present on free articles. Premium ("SPIEGEL+") articles
               replace those text divs with a single
               `div[data-area="paywall"]` and no `articleBody` is available
               at all -- this is a hard paywall, not a teaser, so the
               record is returned with `_paywalled: true` and no fabricated
               body text rather than silently emitting an empty string.
  S2-rss    -- site-wide headline feed for `latest` mode. Includes
               `<content:encoded>` (same text as `<description>` on this
               feed, not a longer version) and a single `<category>`.
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
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                return item
    return None


def _extract_body_text(soup: BeautifulSoup) -> tuple[str | None, bool]:
    """Returns (articleBody or None, is_paywalled)."""
    body_div = soup.select_one('div[data-area="body"]')
    if body_div is None:
        raise UnexpectedShape(
            'div[data-area="body"] not found -- page shape has likely changed.'
        )
    if body_div.select_one('div[data-area="paywall"]') is not None:
        return None, True
    text_divs = body_div.select('div[data-area="text"]')
    if not text_divs:
        raise UnexpectedShape(
            'No div[data-area="text"] or div[data-area="paywall"] found inside '
            "body div -- page shape has likely changed."
        )
    paragraphs = [
        p.get_text(" ", strip=True)
        for td in text_divs
        for p in td.find_all("p")
        if p.get_text(strip=True)
    ]
    if not paragraphs:
        raise UnexpectedShape(
            "Text divs present but no paragraph text extracted -- page shape "
            "has likely changed."
        )
    return "\n\n".join(paragraphs), False


def extract_article(html: str, url: str) -> dict:
    data = _find_article_jsonld(html)
    if data is None:
        raise UnexpectedShape(
            "No NewsArticle ld+json block found -- page shape has likely changed."
        )
    soup = BeautifulSoup(html, "lxml")
    article_body, is_paywalled = _extract_body_text(soup)
    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        **data,
        "articleBody": article_body,
        "_paywalled": is_paywalled,
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
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link.text.strip().split("#")[0] if link else None,
                "guid": guid.text.strip() if guid else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
                "categories": categories,
            }
        )
    return items
