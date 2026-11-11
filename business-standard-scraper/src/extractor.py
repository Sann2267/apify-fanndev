"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` NewsArticle block on the article page.
               The page emits 5 separate ld+json script tags
               (NewsMediaOrganization, WebPage, SiteNavigationElement,
               BreadcrumbList, NewsArticle) -- this picks out the
               NewsArticle one specifically. `articleBody` is full text for
               free articles, truncated to a short teaser for `bs:premium`
               (paywalled) ones -- passed through verbatim either way.
  S2-rss    -- site-wide `/rss/latest.rss` feed for `latest` mode. Custom
               namespaced fields beyond standard RSS 2.0: `dc:creator`
               (byline), `bs:premium` (paywall flag), `bs:keywords`,
               `media:content`/`media:thumbnail` (lead image).
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


class ArticleNotFound(Exception):
    """Page resolved (HTTP 200) but is business-standard.com's soft-404 --
    it still emits a NewsArticle ld+json block, but a blank/placeholder one
    (no `headline`, `url` literally ends in "comundefined"). Confirmed via
    recon 2026-08-24, see CRAWLING_METHOD.md."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_soft_404(data: dict) -> bool:
    return not data.get("headline") and not data.get("articleBody")


def extract_article(html: str, url: str) -> dict:
    for match in JSON_LD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                if _is_soft_404(item):
                    raise ArticleNotFound(
                        "NewsArticle block is a blank soft-404 placeholder."
                    )
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
        creator = item.find("dc:creator")
        premium = item.find("bs:premium")
        keywords = item.find("bs:keywords")
        media = item.find("media:content")
        thumbnail = media.find("media:thumbnail") if media else None
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
                "author": creator.text.strip() if creator else None,
                "isPremium": (premium.text.strip().lower() == "true") if premium else False,
                "keywords": keywords.text.strip() if keywords else None,
                "imageUrl": media.get("url") if media else None,
                "thumbnailUrl": thumbnail.get("url") if thumbnail else None,
            }
        )
    return items
