"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block on the article page.
               The page emits 8 separate ld+json script tags (NewsArticle,
               ProfilePage, WebPage, BreadcrumbList, WebSite,
               SiteNavigationElement, ViewAction, plus one that fails to
               parse -- a SiteNavigationElement block containing a raw
               control character, harmless since it's never the NewsArticle
               block) -- this picks out the NewsArticle one specifically. It
               is a bare dict (not wrapped in an `@graph`), and already
               carries the full plain-text `articleBody` -- no HTML fallback
               needed.
  S2-sitemap -- `/recent-sitemap.xml` for `latest` mode. loc/lastmod/
               image:title only (this site exposes no RSS feed -- /feed
               returns 403).
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


def extract_article(html_text: str, url: str) -> dict:
    for match in JSON_LD_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            # At least one non-article ld+json block on this site (a
            # SiteNavigationElement) contains a raw control character and
            # fails to parse -- harmless, just skip it and keep scanning.
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


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    url_nodes = soup.find_all("url")
    if not url_nodes:
        raise UnexpectedShape(
            "No <url> elements found in recent sitemap -- sitemap shape has likely changed."
        )

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        lastmod_tag = url_node.find("lastmod")
        title_tag = url_node.find("image:title")
        lastmod = lastmod_tag.text.strip() if lastmod_tag and lastmod_tag.text else None
        title = html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "lastmod": lastmod,
            }
        )

    # Not confirmed strictly newest-first in file order (spot-checked
    # adjacent entries out of order during recon) -- sort descending by
    # lastmod defensively.
    results.sort(key=lambda r: r["lastmod"] or "", reverse=True)
    return results
