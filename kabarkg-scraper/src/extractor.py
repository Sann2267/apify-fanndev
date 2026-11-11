"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- en.kabar.kg (Kabar's English edition) emits ONE
             `NewsArticle` ld+json block (a flat dict, not a `@graph`) per
             article page carrying `headline`, `description`, `image`
             (already a list of URL strings on every sample seen),
             `datePublished`, `dateModified`, `author`/`publisher` (both
             `{"@type": "Organization", "name": "Kabar"}` -- wire-service
             content, agency-attributed rather than a named byline) --
             but **no `articleBody`**. Full text comes from HTML
             `div.page-article-text-block > p` (Draft.js-style rich-text
             export: plain `<p data-block-key="...">` tags with the
             occasional `<img>` as a direct sibling, not nested inside a
             `<p>`, so `find_all("p")` skips images automatically).
             The page carries a `category` (the first link inside the
             first of two `div.page-article-data` blocks, e.g. "Central
             Asia", "WNG-2026") and an optional `sourceCredit` (plain
             text in the second `div.page-article-data` block, right
             before the body, e.g. "Akorda", "WNG media headquarters" --
             present on republished/attributed wire content, ABSENT
             entirely -- no second block at all -- on agency-original
             stories).
             **Known CMS quirk:** at least one sampled article
             (`kazakhstan-approves-digital-qazaqstan-action-plan-
             through-2029`) has an `articleBody` genuinely truncated
             mid-word server-side (ends "...personal informa", no
             closing punctuation) -- confirmed stable across repeat
             fetches and matching `Content-Length`, so this is upstream
             CMS content, not a fetch artifact. Passed through as-is,
             not treated as an extraction failure (the container and
             `<p>` tags are well-formed; only the last paragraph's text
             is cut short upstream).
  S2-sitemap -- `/news-sitemap.xml`, a Google News sitemap (referenced
             from robots.txt). No working RSS/Atom feed exists (`/feed`
             and `/feed/` 301-redirect to a path that itself 404s).
             Confirmed newest-first in file order (50 items observed on
             one fetch, top entry matched the freshest homepage story at
             fetch time) -- `extract_sitemap_items()` still sorts
             descending by `news:publication_date` defensively, in case
             ordering isn't guaranteed on every fetch. Only `loc`,
             `news:title`, and `news:publication_date` are carried --
             no full body, so `latest` mode returns headlines only.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text or None


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.page-article-text-block")
    if body_el is None:
        raise UnexpectedShape("No div.page-article-text-block element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    publisher = news_article.get("publisher") or {}

    # Two `div.page-article-data` blocks can appear: the first, right
    # after <h1>, holds the category link (+ date/views, not otherwise
    # captured since datePublished/dateModified already come from
    # ld+json); the second, right before the body, holds an optional
    # source-credit line ("Akorda", "WNG media headquarters") and is
    # absent entirely on agency-original stories with no attributed
    # source.
    data_divs = soup.find_all("div", class_="page-article-data")
    header_div = data_divs[0] if data_divs else None
    source_div = data_divs[1] if len(data_divs) > 1 else None

    category_link = header_div.find("a") if header_div else None
    category = _clean_text(category_link.get_text(" ", strip=True)) if category_link else None
    source_credit = _clean_text(source_div.get_text(" ", strip=True)) if source_div else None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": author.get("name") if isinstance(author, dict) else author,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "category": category,
        "sourceCredit": source_credit,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
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
        raise UnexpectedShape("No <url> elements found in news sitemap -- sitemap shape has likely changed.")

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        title_tag = url_node.find("news:title")
        pub_date_tag = url_node.find("news:publication_date")
        title = title_tag.text.strip() if title_tag and title_tag.text else None
        pub_date = pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "pubDate": pub_date,
            }
        )

    # Confirmed newest-first in file order on every sample taken, but sort
    # descending by publication date defensively anyway.
    results.sort(key=lambda r: r["pubDate"] or "", reverse=True)
    return results
