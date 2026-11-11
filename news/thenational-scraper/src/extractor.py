"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- thenationalnews.com runs on Arc Publishing (same CMS family
               as washingtonpost-scraper, both owned by Washington Post
               parent Nash Holdings) and emits 3 standalone ld+json script
               tags per article (`Organization`, `NewsArticle`,
               `BreadcrumbList`) -- the extractor scans all of them and
               picks the `NewsArticle` node, which **includes `articleBody`
               directly** (verified 1.8-3.9 KB across 3 sampled articles
               spanning news/US, news/UAE, and sport). Unlike most of this
               portfolio, the body is NOT wrapped in `<p>` tags at all --
               it's a flat string with occasional inline `<a>` anchor tags
               (in-body links to related articles) and paragraph breaks
               flattened to plain double-spaces. The extractor therefore
               parses with BeautifulSoup and takes `.get_text()` directly
               (no `find_all("p")` -- there are no `<p>` tags to find).
               `author` is always a LIST of `Person` dicts (sometimes just
               `{"name": "The National"}` for staff/wire copy, sometimes a
               named byline with a nested `image` field for the author's
               headshot) -- names joined with `", "`. No `isAccessibleForFree`
               or other paywall marker found in any sample.
  S2-sitemap -- Arc Publishing outbound news sitemap
               (`/arc/outboundfeeds/news-sitemap/?outputType=xml`,
               advertised in robots.txt), richer than most portfolio
               sitemaps: `news:title`, `news:publication_date`, `lastmod`,
               plus a single `image:image` block (loc + caption) per entry.
"""

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

    raw_body = article.get("articleBody")
    if not raw_body:
        raise UnexpectedShape("articleBody missing from NewsArticle node -- page shape has likely changed.")
    # No <p> wrapping on this CMS -- flat string with inline <a> tags only.
    article_body = BeautifulSoup(raw_body, "lxml").get_text()
    if not article_body.strip():
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    author = article.get("author")
    if isinstance(author, list):
        author_name = ", ".join(a.get("name") for a in author if isinstance(a, dict) and a.get("name"))
    elif isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else (image if isinstance(image, str) else None)

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
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
        image = url_node.find("image:loc")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "imageUrl": image.text.strip() if image and image.text else None,
            }
        )
    return items
