"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld  -- koreatimes.co.kr emits a `NewsArticle` ld+json block (plus
               an unrelated `FAQPage` block on some pages, ignored) that
               **includes `articleBody` directly** (verified 3.9 KB on a
               sampled business article). `author` is always a LIST of
               `Person` dicts -- joined with `", "` when multiple. No
               `isAccessibleForFree` or other paywall marker was found.
               **Soft-404 handling (important, confirmed by recon):** an
               invalid/removed article URL still returns **HTTP 200** with
               a generic section-listing page (page `<title>` is just
               `"<Section> - The Korea Times"`, zero ld+json blocks at
               all) instead of a real 404. Since "zero ld+json blocks"
               could also mean genuine upstream schema drift on a real
               article, the extractor distinguishes the two cases using
               `<link rel="canonical">`: a real article's canonical URL
               always matches the requested path exactly; a soft-404
               resolves to the **shorter section-root canonical**
               (e.g. requesting `.../business/companies/20260823/typo`
               canonicalizes to `.../business/companies`, dropping the
               date+slug segments). If canonical != requested path AND no
               NewsArticle block is found, it's treated as `not_found`; if
               canonical *does* match and there's still no NewsArticle
               block, that's genuine `UnexpectedShape` (schema drift).
  S2-sitemap -- rolling news sitemap (`/sitemap/news.xml`, reached via
               `sitemap.xml` -> `sitemap-sections.xml` -> this file --
               NOT the same-named `sitemap-news.xml`, which is a decoy/stub
               that resolves to an empty sitemapindex). `news:title` has
               the site-name suffix (`" - The Korea Times"`) baked directly
               into the value (unlike article pages' clean ld+json
               `headline`) -- passed through as-is as `title`, matching
               what the sitemap actually contains rather than
               reconstructing a "cleaned" version. `news:keywords` is
               comma-separated (single keyword in the sampled entry, but
               the split-and-strip logic used elsewhere in this portfolio
               still applies for multi-keyword entries), plus one
               `image:image` block per entry.
"""

import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """Page resolved (HTTP 200) but is koreatimes.co.kr's soft-404 -- a
    generic section-listing page with no NewsArticle ld+json block, whose
    canonical URL points to the section root rather than the requested
    article path. Confirmed via recon 2026-08-24, see CRAWLING_METHOD.md."""


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


def _canonical_matches(soup: BeautifulSoup, url: str) -> bool:
    canon = soup.find("link", rel="canonical")
    if canon is None or not canon.get("href"):
        return True  # no canonical tag -- can't use this signal, assume real
    return urlsplit(canon["href"]).path.rstrip("/") == urlsplit(url).path.rstrip("/")


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        if not _canonical_matches(soup, url):
            raise ArticleNotFound("Canonical URL points to section root -- soft-404 page.")
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("articleBody missing from NewsArticle node -- page shape has likely changed.")

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
