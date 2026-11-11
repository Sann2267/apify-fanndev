"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld  -- article pages emit 6 separate ld+json script tags. The one
                actually consumed here is a **bare** `"@type": "newsarticle"`
                block (lowercase, non-standard casing) which already carries
                the full plain-text `articleBody` -- no HTML fallback
                needed. A *separate* `@graph`-wrapped block also carries an
                `"Article"` node with `keywords`/`wordCount` that the
                `newsarticle` block never has -- those two fields are
                merged in from that companion node when present.
  S2-sitemap -- `/googlenews.xml` for `latest` mode (this site exposes no
                RSS feed -- `/feed` and `/rss` both 500 with a WordPress
                `wp_die` "No feed available" error).
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSON_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)

# Lowercase on purpose -- this site's standalone article ld+json block uses
# `"@type": "newsarticle"` (all lowercase), not the standard-cased
# `"NewsArticle"` seen on other outlets in this portfolio. Matched
# case-insensitively below to be defensive either way.
ARTICLE_TYPES = {"newsarticle", "reportagenewsarticle"}
GRAPH_ARTICLE_TYPES = {"article"}


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_article(html_text: str, url: str) -> dict:
    primary = None
    graph_article = None

    for match in JSON_LD_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            # One block on this site (SiteNavigationElement/WebSite, etc.)
            # can be malformed -- harmless, just skip and keep scanning.
            continue

        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            for node in data["@graph"]:
                if isinstance(node, dict) and str(node.get("@type", "")).lower() in GRAPH_ARTICLE_TYPES:
                    graph_article = node
            continue

        if (
            isinstance(data, dict)
            and str(data.get("@type", "")).lower() in ARTICLE_TYPES
            and "articleBody" in data
        ):
            primary = data

    if primary is None:
        raise UnexpectedShape(
            "No newsarticle ld+json block with articleBody found -- page shape has likely changed."
        )

    record = dict(primary)
    # keywords/wordCount only ever appear on the companion @graph "Article"
    # node on this site, never on the standalone newsarticle block itself
    # -- merge them in without clobbering anything primary already has.
    if graph_article:
        for field in ("keywords", "wordCount", "commentCount"):
            if field not in record and field in graph_article:
                record[field] = graph_article[field]

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        **record,
    }


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
            "No <url> elements found in Google News sitemap -- sitemap shape has likely changed."
        )

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        title_tag = url_node.find("news:title")
        date_tag = url_node.find("news:publication_date")
        keywords_tag = url_node.find("news:keywords")
        title = html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None
        pub_date = date_tag.text.strip() if date_tag and date_tag.text else None
        keywords = (
            [k.strip() for k in keywords_tag.text.split(",") if k.strip()]
            if keywords_tag and keywords_tag.text
            else None
        )
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "publicationDate": pub_date,
                "keywords": keywords,
            }
        )

    # Confirmed newest-first in file order during recon (five consecutive
    # entries in strictly descending publication_date) -- sorted
    # defensively anyway, matching portfolio convention.
    results.sort(key=lambda r: r["publicationDate"] or "", reverse=True)
    return results
