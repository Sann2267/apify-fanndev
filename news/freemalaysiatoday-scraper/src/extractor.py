"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-nextdata -- freemalaysiatoday.com is a headless WordPress site (WPGraphQL
               backend) rendered through a Next.js frontend. It does NOT emit
               a NewsArticle ld+json block anywhere -- no <script
               type="application/ld+json"> tags were found on sampled article
               pages at all. The full post object instead lives in the
               `__NEXT_DATA__` script tag at `props.pageProps.post`: title,
               content (raw WordPress HTML), excerpt, date/dateGmt/modifiedGmt,
               author.node, categories.edges[].node, tags.edges[].node,
               featuredImage.node. Passed through close to verbatim
               (raw-passthrough convention) with a flattened `articleBody`
               plain-text convenience field added from `content`.
  S2-rss    -- site-wide feed (`/feeds/rss/headlines`), 50 items per fetch.
               Unusually rich for a "latest" feed: each <item> carries
               <content:encoded> with the FULL article HTML (not just a
               teaser), plus dc:creator, multiple <category> tags, and a
               media:thumbnail image.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flatten_html(raw_html: str | None) -> str | None:
    """post.content / RSS content:encoded is raw WordPress HTML (<p>,
    <figure>, embedded <img> etc). Join paragraph text into a plain-text
    article body convenience field."""
    if not raw_html:
        return None
    soup = BeautifulSoup(raw_html, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs) or None


def _extract_next_data_post(html: str) -> dict:
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise UnexpectedShape("__NEXT_DATA__ script tag not found -- page shape has likely changed.")
    try:
        nd = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__NEXT_DATA__ present but not valid JSON: {e}") from e
    post = nd.get("props", {}).get("pageProps", {}).get("post")
    if not post or "content" not in post or "title" not in post:
        raise UnexpectedShape(
            f"pageProps.post missing expected keys; got={list((post or {}).keys())}"
        )
    return post


def extract_article(html: str, url: str) -> dict:
    post = _extract_next_data_post(html)
    return {
        "_input": url,
        "_source": "S1-nextdata",
        "_scrapedAt": utc_now_iso(),
        **post,
        "articleBody": _flatten_html(post.get("content")),
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
        creator = item.find("creator")  # dc:creator
        pub_date = item.find("pubDate")
        guid = item.find("guid")
        description = item.find("description")
        content_encoded = item.find("encoded")  # content:encoded
        thumbnail = item.find("thumbnail")  # media:thumbnail
        categories = [c.text.strip() for c in item.find_all("category") if c.text and c.text.strip()]
        content_text = content_encoded.text if content_encoded and content_encoded.text else None
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "creator": creator.text.strip() if creator and creator.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "description": description.text.strip() if description and description.text else None,
                "categories": categories or None,
                "content": content_text,
                "articleBody": _flatten_html(content_text),
                "image": thumbnail.get("url") if thumbnail else None,
            }
        )
    return items
