"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- vice.com (WordPress) emits TWO separate ld+json script
               tags per article: one wraps an `@graph` array (`Article`,
               `WebPage`, `ImageObject`, `BreadcrumbList`, `WebSite`,
               `Organization`, `Person` nodes -- generic SEO plugin output,
               `Article` not `NewsArticle`), and a second, STANDALONE dict
               with `"@type": "NewsArticle"` carrying headline/author/
               keywords/dates/image but **no `articleBody` or
               `description`**. The extractor only needs the second one.
               `description` is read from `meta[property="og:description"]`
               instead. Full text: `div.entry-content` (WordPress Gutenberg
               block content, `wp-block-post-content` class) -- collecting
               all `<p class="wp-block-paragraph">` tags naturally skips
               interspersed ad-slot `<div class="code-block">` wrappers
               (empty placeholder divs, no `<p>` inside them) and video
               embed divs, since neither are `<p>` elements.
  S2-rss    -- site-wide feed (`/en/rss`) for `latest` mode. WordPress
               default feed: `description` is HTML-entity-escaped HTML
               ending in a literal "The post &lt;a&gt;Title&lt;/a&gt;
               appeared first on &lt;a&gt;VICE&lt;/a&gt;." boilerplate
               (unescaped and tag-stripped, boilerplate text kept -- it's
               real feed content, not noise). `content:encoded` carries the
               full body HTML (also unescaped for convenience).
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def _clean_html_text(raw: str | None) -> str | None:
    if not raw:
        return raw
    unescaped = html.unescape(raw)
    text = BeautifulSoup(unescaped, "lxml").get_text(" ", strip=True)
    return text or None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No standalone NewsArticle ld+json block found -- page shape has likely changed.")

    body_div = soup.select_one("div.entry-content")
    if body_div is None:
        raise UnexpectedShape("div.entry-content not found -- page shape has likely changed.")

    paragraphs = [p.get_text(" ", strip=True) for p in body_div.find_all("p") if p.get_text(strip=True)]
    if not paragraphs:
        raise UnexpectedShape("No <p> paragraphs found in entry-content -- page shape has likely changed.")
    article_body = "\n\n".join(paragraphs)

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    description = og_desc["content"].strip() if og_desc and og_desc.get("content") else None

    author = article.get("author")
    if isinstance(author, list):
        author_name = ", ".join(a.get("name") for a in author if isinstance(a, dict) and a.get("name"))
    elif isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": description,
        "articleBody": article_body,
        "articleSection": article.get("articleSection"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "keywords": article.get("keywords"),
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
        creator = item.find("dc:creator") or item.find("creator")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        encoded = item.find("encoded")
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "author": creator.text.strip() if creator and creator.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": _clean_html_text(description.text if description else None),
                "contentHtml": html.unescape(encoded.text) if encoded and encoded.text else None,
                "categories": categories,
            }
        )
    return items
