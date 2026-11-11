"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld   -- `application/ld+json` NewsArticle block on the article
                 page. The page emits 5 separate ld+json script tags
                 (WebPage, BreadcrumbList, NewsMediaOrganization, a
                 SiteNavigationElement list, and a single-element list
                 wrapping the NewsArticle) -- this picks out the
                 NewsArticle one specifically.
  S2-sitemap  -- Google News sitemap (`news-sitemap.xml`) for `latest`
                 mode. title/link/pubDate/keywords/image only.
"""

import html
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


def _unescape(value):
    """Recursively undo moneycontrol's habit of embedding literal HTML
    entities (&rsquo;, &nbsp;, &ldquo;, ...) straight into JSON-LD string
    values -- these are not JSON escapes (`json.loads` already handles
    those), they're HTML entities the CMS writes directly into the text.
    """
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, dict):
        return {k: _unescape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unescape(v) for v in value]
    return value


def _parse_jsonld_blocks(html_text: str) -> list:
    blocks = []
    for match in JSON_LD_RE.finditer(html_text):
        try:
            # strict=False: moneycontrol's NewsArticle ld+json block embeds
            # raw, unescaped control characters (literal \r\n) inside
            # `articleBody` -- technically invalid JSON under strict mode.
            # Confirmed live 2026-08-27: strict json.loads raises "Invalid
            # control character" on every article sampled; strict=False
            # (RFC-lenient) parses the same bytes cleanly.
            blocks.append(json.loads(match.group(1), strict=False))
        except json.JSONDecodeError:
            continue
    return blocks


def extract_article(html_text: str, url: str) -> dict:
    blocks = _parse_jsonld_blocks(html_text)

    for data in blocks:
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                return {
                    "_input": url,
                    "_source": "S1-jsonld",
                    "_scrapedAt": utc_now_iso(),
                    **_unescape(item),
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


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    url_nodes = soup.find_all("url")
    if not url_nodes:
        raise UnexpectedShape(
            "No <url> elements found in news sitemap -- sitemap shape has likely changed."
        )

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        title_tag = url_node.find("news:title")
        pub_date_tag = url_node.find("news:publication_date")
        keywords_tag = url_node.find("news:keywords")
        image_tag = url_node.find("image:loc")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None,
                "link": link,
                "pubDate": pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None,
                "keywords": html.unescape(keywords_tag.text.strip()) if keywords_tag and keywords_tag.text else None,
                "image": image_tag.text.strip() if image_tag and image_tag.text else None,
            }
        )

    # Confirmed newest-first in file order on every sample taken, but sort
    # descending by publication date defensively anyway.
    results.sort(key=lambda r: r["pubDate"] or "", reverse=True)
    return results
