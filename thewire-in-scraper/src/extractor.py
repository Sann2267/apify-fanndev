"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` `NewsArticle` block on the m.thewire.in
               article page (the site's server-rendered mobile subdomain --
               see constants.py for why the desktop thewire.in domain can't
               be scraped directly). The page emits 7 separate ld+json
               script tags (NewsArticle, WebPage, ProfilePage, BreadcrumbList,
               NewsMediaOrganization, WebSite, SiteNavigationElement) -- this
               picks out the NewsArticle one specifically. Unlike some other
               outlets in this portfolio, `articleBody` is carried directly
               on this node (no separate HTML-body merge needed).
  S2-sitemap -- category-1 sitemap for `latest` mode. `loc`/`lastmod`/
               `image:title`/`image:loc` only -- no dedicated per-item
               `<title>` tag outside the image block, no Google News sitemap
               namespace (unlike guardian-nigeria/scroll.in).
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSON_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)

ARTICLE_TYPES = {"NewsArticle", "ReportageNewsArticle", "Article"}

# Matches thewire.in / www.thewire.in article URLs -- anything else
# (m.thewire.in, or an already-fully-qualified other URL) is left alone.
DESKTOP_URL_RE = re.compile(r"^https?://(?:www\.)?thewire\.in/(.+)$", re.I)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_article_url(url: str) -> str:
    """Rewrite a desktop thewire.in/www.thewire.in article URL to its
    m.thewire.in/article/... equivalent -- see constants.py for why this is
    required (the desktop domain is a client-side-rendered SPA shell with no
    server-side content). m.thewire.in URLs pass through unchanged.
    """
    url = url.strip()
    match = DESKTOP_URL_RE.match(url)
    if match:
        return f"https://m.thewire.in/article/{match.group(1)}"
    return url


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


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        lastmod = url_tag.find("lastmod")
        image = url_tag.find("image:image")
        image_title = image.find("image:title") if image else None
        image_loc = image.find("image:loc") if image else None
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": image_title.text.strip() if image_title and image_title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "pubDate": lastmod.text.strip() if lastmod and lastmod.text else None,
                "image": image_loc.text.strip() if image_loc and image_loc.text else None,
            }
        )
    # Confirmed already newest-first in file order during recon (2026-08-26),
    # but sort descending by pubDate defensively anyway in case that
    # ordering isn't guaranteed on every fetch (mirrors guardian-nigeria/
    # scrollin precedent).
    items.sort(key=lambda i: i.get("pubDate") or "", reverse=True)
    return items
