"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html  -- fool.com emits **no ld+json at all** (like Global Times,
             the second actor in the portfolio with this gap). All
             metadata comes from plain `<meta>` tags: `og:title`,
             `og:description`, `article:published_time` (proper
             ISO-8601), and `meta[name=author]` (a single display name,
             not a byline URL). Full text comes from
             `div.article-body > p`, with `p.caption` elements (image
             attribution lines like "Image source: The Motley Fool.")
             `.decompose()`d first since they are not article prose.
             Ticker references (`<span class="ticker">(NASDAQ: MRVL)</span>`)
             are left inline -- they read naturally as part of the
             sentence via plain `get_text()`.
  S2-rss   -- `/feeds/index.aspx`, RSS 2.0 with `<content:encoded>`
             carrying the **full article body as HTML-escaped HTML**
             (double-escaped: the feed XML itself escapes the HTML
             entities, so `&lt;p&gt;` etc. need `html.unescape()` before
             the string is valid HTML to parse). The last `<p>` in every
             sampled item is a "Continue reading" link back to the
             article and is dropped (matched by literal text, not by a
             class, since none is present).
"""

import re
from datetime import datetime, timezone
from html import unescape

from bs4 import BeautifulSoup

_WHITESPACE_RE = re.compile(r"\s+")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content") if tag else None


def _paragraphs_to_text(container, drop_continue_reading: bool = False) -> str:
    for caption in container.find_all("p", class_="caption"):
        caption.decompose()
    paragraphs = []
    for p in container.find_all("p"):
        text = _WHITESPACE_RE.sub(" ", p.get_text(" ", strip=True)).strip()
        if not text:
            continue
        if drop_continue_reading and text.lower() == "continue reading":
            continue
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.article-body")
    if body_el is None:
        raise UnexpectedShape("No div.article-body element found -- page shape has likely changed.")
    article_body = _paragraphs_to_text(body_el)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    headline = _meta(soup, property="og:title")
    if headline and headline.endswith(" | The Motley Fool"):
        headline = headline[: -len(" | The Motley Fool")]

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "description": _meta(soup, property="og:description"),
        "articleBody": article_body,
        "author": _meta(soup, name="author"),
        "datePublished": _meta(soup, property="article:published_time"),
        "image": _meta(soup, property="og:image"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        description = item.find("description")
        author = item.find("author")
        pub_date = item.find("pubDate")
        content_encoded = item.find("content:encoded") or item.find("encoded")

        article_body = None
        if content_encoded and content_encoded.text:
            content_soup = BeautifulSoup(unescape(content_encoded.text), "lxml")
            article_body = _paragraphs_to_text(content_soup, drop_continue_reading=True) or None

        link_text = link.text.strip() if link and link.text else None
        if link_text:
            link_text = link_text.split("?source=")[0]

        author_text = author.text.strip() if author and author.text else None
        if author_text and "(" in author_text and author_text.endswith(")"):
            # RSS <author> is "email (Display Name)" -- keep the display name only.
            author_text = author_text.split("(", 1)[1].rstrip(")")

        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link_text,
                "description": description.text.strip() if description and description.text else None,
                "author": author_text,
                "articleBody": article_body,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
