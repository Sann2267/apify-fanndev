"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- inquirer.net (WordPress-based, all verticals --
               newsinfo/lifestyle/business/etc. subdomains) emits a
               `NewsArticle` ld+json block that DOES include `articleBody`,
               unlike most of this portfolio -- but two quirks require
               handling:
               1. The raw ld+json text itself contains unescaped literal
                  control characters (raw newlines inside a JSON string
                  value) that make strict `json.loads` raise
                  "Invalid control character" -- must parse with
                  `strict=False`.
               2. `articleBody`'s value is **double HTML-entity-escaped**
                  raw WordPress Gutenberg block markup (e.g.
                  `&amp;lt;!-- wp:paragraph --&amp;gt;&amp;lt;p&amp;gt;...`).
                  It must be `html.unescape()`d **twice** before it becomes
                  real HTML (`<!-- wp:paragraph --><p>...`), then parsed
                  with BeautifulSoup and only `<p>` tags collected --
                  `<figure>`/`<figcaption>` (image + caption blocks) are
                  automatically excluded since they aren't `<p>` tags.
  S2-rss    -- site-wide feed (`/fullfeed`, covers every subdomain/vertical)
               for `latest` mode. `description` is single HTML-entity-escaped
               HTML (a teaser plus a literal "Keep on reading: <a>title</a>"
               boilerplate sentence) -- unescaped and tag-stripped, but the
               "Keep on reading" text itself is preserved (it's real teaser
               content the site generates, not an encoding artifact).
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(html_text: str) -> dict | None:
    soup = BeautifulSoup(html_text, "lxml")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            # strict=False: inquirer.net's ld+json contains raw control
            # characters inside string values (see module docstring).
            data = json.loads(script.string, strict=False)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def _clean_html_text(raw: str | None, unescape_times: int = 1) -> str | None:
    if not raw:
        return raw
    text = raw
    for _ in range(unescape_times):
        text = html.unescape(text)
    cleaned = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    return cleaned or None


def extract_article(html_text: str, url: str) -> dict:
    article = _find_news_article(html_text)
    if article is None:
        raise UnexpectedShape("No NewsArticle node found in ld+json -- page shape has likely changed.")

    raw_body = article.get("articleBody")
    if not raw_body:
        raise UnexpectedShape("articleBody missing from NewsArticle node -- page shape has likely changed.")
    # Double-unescape: the raw value is HTML-entity-escaped HTML that is
    # itself entity-escaped again (WordPress Gutenberg block export quirk).
    real_html = html.unescape(html.unescape(raw_body))
    body_soup = BeautifulSoup(real_html, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in body_soup.find_all("p") if p.get_text(strip=True)]
    if not paragraphs:
        raise UnexpectedShape("No <p> paragraphs found after unescaping articleBody -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else (image if isinstance(image, str) else None)

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "image": image_url,
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
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        media = item.find("media:content")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": _clean_html_text(description.text if description else None, unescape_times=1),
                "imageUrl": media.get("url") if media else None,
            }
        )
    return items
