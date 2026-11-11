"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- gulfnews.com emits several standalone ld+json script tags
               per article (`BreadcrumbList`, sometimes `Article` and/or
               `LiveBlogPosting` for live-updating stories, and always a
               `NewsArticle`) -- the extractor scans all blocks and picks
               the one with `"@type": "NewsArticle"`. That node **includes
               `articleBody` directly** (full text, verified 4-13 KB across
               3 sampled articles incl. a live-updating world-news piece),
               plus `author` (a LIST of `{"@type": "Person", "name": ...}`
               -- often multiple bylines/wire contributors on one story),
               `keywords` and `description` (present on some articles, not
               others -- both optional per sample variance, read with
               `.get()`). No HTML fallback needed. **Quirk:** `articleBody`
               contains literal un-decoded HTML entities inline (`&nbsp;`
               confirmed in samples) -- these are not JSON escapes (which
               `json.loads` already handles), they're HTML entities the CMS
               embedded directly into the text value, so a second pass of
               `html.unescape()` is applied to `headline`/`description`/
               `articleBody` to clean them up.
  S2-sitemap -- Google News sitemap (`/news_sitemap.xml`, advertised in
               robots.txt) for `latest` mode. `news:title`,
               `news:publication_date`, `news:keywords`, plus `image:image`
               blocks (lead + inline images, first one used as the
               headline thumbnail).
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


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("articleBody missing from NewsArticle node -- page shape has likely changed.")
    # CMS embeds literal HTML entities (e.g. &nbsp;) directly in the text --
    # unescape after JSON parsing, this is not a JSON-escaping concern.
    article_body = html.unescape(article_body)

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
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": html.unescape(article["headline"]) if article.get("headline") else None,
        "description": html.unescape(article["description"]) if article.get("description") else None,
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


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        keywords = url_node.find("news:keywords")
        image = url_node.find("image:loc")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "keywords": [k.strip() for k in keywords.text.split(",")] if keywords and keywords.text else [],
                "imageUrl": image.text.strip() if image and image.text else None,
            }
        )
    return items
