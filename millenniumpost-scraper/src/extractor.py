"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld  -- `application/ld+json` NewsArticle block on the article page.
               The page emits 7 separate ld+json script tags (Article,
               NewsArticle, Organization, WebSite, BreadcrumbList,
               SiteNavigationElement, WebPage) -- this picks out the
               NewsArticle one specifically. Carries full articleBody plain
               text, no HTML entity/escaping quirks observed.
  S2-sitemap -- `/news-sitemap-daily.xml` (Google News sitemap) for `latest`
               mode. The site-wide `/rss` and `/feed` endpoints both 200 but
               return an empty, stale Hocalwire RSS channel (zero items),
               so the sitemap is used instead. Each `<url>` carries `loc`,
               `news:title`, `news:publication_date`.
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
    # Prefer an explicit @type == "NewsArticle" block over the generic
    # "Article" block that precedes it on the page (both carry the same
    # fields on this CMS, but NewsArticle is the more specific/canonical
    # schema.org type -- see CRAWLING_METHOD.md).
    fallback = None
    for match in JSON_LD_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if item_type == "NewsArticle":
                return {
                    "_input": url,
                    "_source": "S1-jsonld",
                    "_scrapedAt": utc_now_iso(),
                    **item,
                }
            if item_type in ARTICLE_TYPES and fallback is None:
                fallback = item
    if fallback is not None:
        return {
            "_input": url,
            "_source": "S1-jsonld",
            "_scrapedAt": utc_now_iso(),
            **fallback,
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
        title = html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None
        pub_date = pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None
        image_tag = url_node.find("image:loc")
        image = image_tag.text.strip() if image_tag and image_tag.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "pubDate": pub_date,
                "image": image,
            }
        )

    # Confirmed newest-first in file order on every sample taken, but sort
    # descending by publication date defensively anyway.
    results.sort(key=lambda r: r["pubDate"] or "", reverse=True)
    return results
