"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- saudigazette.com.sa emits exactly one
             `<script type="application/ld+json">` `NewsArticle` block per
             article (plus a second, unrelated site-wide `Organization`
             block -- the extractor scans all ld+json tags and picks the
             one with `"@type": "NewsArticle"`). That node carries
             `headline`, `description`, `datePublished`, `dateModified`,
             `author` (`{"@type": "Person", "name": ...}` -- varies
             genuinely per article: `"Saudi Gazette"` for staff/wire
             pieces filed under the outlet's own byline, `"Agencies"` for
             wire copy, or `"By <Name>*"` for opinion columns -- the raw
             "By "-prefixed, asterisk-suffixed string is kept verbatim,
             not cleaned, per the portfolio's minimal-renaming
             convention), `publisher.name` (always `"Saudi Gazette"`),
             `image.url`, and `keywords` -- but **no `articleBody`**.
             `description` and `keywords` on some articles are the CMS's
             auto-generated filler (e.g. `keywords` is sometimes just the
             headline's words comma-joined) rather than genuinely curated
             tags -- passed through as-is, not filtered.
             Full text instead comes from HTML: `div.body-div`,
             direct-child `<p>`/`<h2>`/`<h3>`/`<blockquote>` tags only.
             Inline `<picture>` elements (in-article images) sit inside
             their own `<p>` wrapper at the same level and are excluded
             automatically since they produce no text via `get_text()`
             (empty strings are dropped). `category` is not present in the
             ld+json at all -- pulled instead from the single active
             breadcrumb link, `div.breadcrumbs a.breadcrumb`.
  S2-sitemap -- Google News sitemap (`/sitemaps/news_sitemap.xml`,
             advertised via `Sitemap:` in robots.txt) for `latest` mode.
             Rolling window of the newest ~80 articles (observed items
             timestamped within the last few minutes of a live fetch),
             `news:title`/`news:publication_date`/`news:keywords` per
             `<url>` entry, no `image:*` namespace on this feed (unlike
             gulfnews-scraper's). No RSS feed exists: `/rss.xml` 301s to
             the site's own `/404` page, and `/rss` soft-200s to an HTML
             placeholder page (`<title>RSS - Latest News...</title>`, no
             `<item>`/`<rss>` XML at all) -- both dead ends, see
             CRAWLING_METHOD.md.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unescape(value):
    if isinstance(value, str):
        return html.unescape(value)
    return value


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


def _extract_body(soup: BeautifulSoup) -> str:
    div = soup.select_one("div.body-div")
    if div is None:
        raise UnexpectedShape("No div.body-div found -- page shape has likely changed.")
    paragraphs = [
        el.get_text(" ", strip=True)
        for el in div.find_all(["p", "h2", "h3", "blockquote"], recursive=False)
        if el.get_text(strip=True)
    ]
    return "\n\n".join(paragraphs)


def _extract_category(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one("div.breadcrumbs a.breadcrumb")
    return tag.get_text(strip=True) if tag else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    author = article.get("author")
    author_name = _unescape(author.get("name")) if isinstance(author, dict) else None

    publisher = article.get("publisher")
    publisher_name = _unescape(publisher.get("name")) if isinstance(publisher, dict) else None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline")),
        "description": _unescape(article.get("description")),
        "articleBody": article_body,
        "category": _extract_category(soup),
        "author": author_name,
        "publisher": publisher_name,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "image": image_url,
        "keywords": _unescape(article.get("keywords")),
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
    urls = soup.find_all("url")
    if not urls:
        raise UnexpectedShape("No <url> elements found in news sitemap -- sitemap shape has likely changed.")
    results = []
    for u in urls:
        loc = u.find("loc")
        title = u.find("news:title")
        pub_date = u.find("news:publication_date")
        keywords = u.find("news:keywords")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "keywords": [k.strip() for k in keywords.text.split(",")] if keywords and keywords.text else [],
            }
        )
    return results
