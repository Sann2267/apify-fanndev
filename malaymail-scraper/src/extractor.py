"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- malaymail.com emits a `NewsArticle` ld+json block on every
               sampled article page (`<script data-cfasync="false"
               type="application/ld+json">`, attribute order NOT
               `type=` first, so the regex must not assume it). It carries
               headline, description, articleSection, image, datePublished,
               dateModified, author.name (real byline, not a generic
               "Malay Mail" placeholder -- verified against an opinion
               column), publisher, keywords -- but NOT the article body
               text. The full body lives in the page HTML itself, inside
               `<div class="article-body">` as a sequence of <p> tags
               interleaved with ad placeholder <div>s (`#mm-story-outstream`,
               `.vodus-banner`, `#mm-story-mreg-*`, `#mm-teads`,
               `.sidebar-square-ad`) that are stripped out before joining
               paragraph text. Passed through close to verbatim
               (raw-passthrough convention) with `articleBody` (plain text)
               and `content` (raw inner HTML of the article-body div) added
               as convenience fields.
  S2-rss    -- site-wide feed (`/feed/rss`), 50 items per fetch. Each <item>
               carries <content:encoded> with the FULL article HTML (not
               just a teaser), dc:creator, a single dc:subject element
               (comma-separated keyword string, NOT repeated <category>
               tags like most of the portfolio), and a media:thumbnail
               image.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSONLD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)

AD_SELECTORS = [
    "div[id^='mm-story']",
    "div[id^='mm-teads']",
    "div.vodus-banner",
    "div.sidebar-square-ad",
    "script",
]


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flatten_html(raw_html: str | None) -> str | None:
    """Article body HTML (article-page article-body div, or RSS
    content:encoded) is raw CMS HTML (<p>, <div class="image_body"> etc).
    Join paragraph text into a plain-text article body convenience field."""
    if not raw_html:
        return None
    soup = BeautifulSoup(raw_html, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs) or None


def _extract_jsonld(html: str) -> dict:
    import json

    m = JSONLD_RE.search(html)
    if not m:
        raise UnexpectedShape('<script type="application/ld+json"> tag not found -- page shape has likely changed.')
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"ld+json present but not valid JSON: {e}") from e
    if data.get("@type") != "NewsArticle" or "headline" not in data:
        raise UnexpectedShape(f"ld+json present but not a NewsArticle; got @type={data.get('@type')!r}")
    return data


def _extract_body_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    body = soup.select_one("div.article-body")
    if not body:
        return None
    for sel in AD_SELECTORS:
        for tag in body.select(sel):
            tag.decompose()
    return body.decode_contents().strip() or None


def extract_article(html: str, url: str) -> dict:
    jsonld = _extract_jsonld(html)
    body_html = _extract_body_html(html)
    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        **jsonld,
        "content": body_html,
        "articleBody": _flatten_html(body_html),
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
        subject = item.find("subject")  # dc:subject -- single comma-separated string
        categories = None
        if subject and subject.text and subject.text.strip():
            categories = [c.strip() for c in subject.text.split(",") if c.strip()]
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
                "categories": categories,
                "content": content_text,
                "articleBody": _flatten_html(content_text),
                "image": thumbnail.get("url") if thumbnail else None,
            }
        )
    return items
