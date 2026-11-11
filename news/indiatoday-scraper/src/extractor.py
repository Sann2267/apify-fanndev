"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld       -- `application/ld+json` NewsArticle block. Present on
                      EVERY page template sampled, including
                      `/.../video/<slug>-<id>` pages (same pattern as
                      ndtv-scraper). On plain-text verticals (business/india/
                      technology/movies/sports/world/science/education/
                      horoscopes/cities/...) it carries the full plain-text
                      `articleBody`. On video pages that NewsArticle node has
                      no `articleBody` -- only `description` (a short
                      caption) -- while the fuller `VideoObject` block on the
                      same page (video URL, duration, thumbnail) is not
                      extracted; see Known limits in CRAWLING_METHOD.md.
  S1b-jsonld-video -- `application/ld+json` VideoObject block. Defensive
                      fallback only, used if a page ever lacks a NewsArticle
                      node entirely (not observed on any of the templates
                      sampled -- article, video, or programme/show pages all
                      carried NewsArticle).
  S2-rss          -- site-wide "Latest Stories" RSS feed for `latest` mode.
                      title/link/pubDate/description only, no guid, no byline.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSON_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)

ARTICLE_TYPES = {"NewsArticle", "ReportageNewsArticle", "Article"}
VIDEO_TYPES = {"VideoObject"}


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_jsonld_blocks(html: str) -> list:
    blocks = []
    for match in JSON_LD_RE.finditer(html):
        try:
            # strict=False: India Today's NewsArticle ld+json block embeds
            # raw, unescaped control characters (literal newlines) inside
            # `articleBody` -- technically invalid JSON under strict mode.
            # Confirmed live 2026-08-26: strict json.loads raises
            # "Invalid control character" on every article sampled;
            # strict=False (RFC-lenient) parses the same bytes cleanly.
            blocks.append(json.loads(match.group(1), strict=False))
        except json.JSONDecodeError:
            continue
    return blocks


def extract_article(html: str, url: str) -> dict:
    blocks = _parse_jsonld_blocks(html)

    # S1: plain-text article template (NewsArticle)
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

    # S1b: defensive fallback (VideoObject) -- not observed to trigger on any
    # sampled page (video pages carry a thin NewsArticle too), kept in case a
    # future template variant drops the NewsArticle node.
    for data in blocks:
        if isinstance(data, dict) and data.get("@type") in VIDEO_TYPES:
            return {
                "_input": url,
                "_source": "S1b-jsonld-video",
                "_scrapedAt": utc_now_iso(),
                **data,
            }

    raise UnexpectedShape(
        "No NewsArticle or VideoObject ld+json block found -- page shape has "
        "likely changed."
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
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link.text.strip() if link else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
            }
        )
    return items
